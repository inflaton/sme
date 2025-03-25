"""
Main entrypoint of the app
"""

import os
import sys
import sqlite3
import traceback
import uuid

from datetime import datetime

import json

from dotenv import load_dotenv

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from src.llm.langgraph.email_recon.assistant import EmailReconInvoicingAssistant
from src.llm.langgraph.tool_based_recon.assistant import (
    ToolBasedEmailReconInvoicingAssistant,
)
from src.data.db.db_scripts import query_sqlite_db, set_db
from src.misc.beautified_logging import BeautifiedLogging
from src.misc.path_parser import get_db_path

from typing import Any


# insert module path
cwd = os.getcwd()
sys.path.insert(0, f"{cwd}/src")

load_dotenv(override=False)


class ReconApp:
    """
    App to run reconciliation agent
    """

    conn = None

    sqlite_path = get_db_path()

    transaction_db_path = f"{sqlite_path}/transactions.db"
    email_db_path = f"{sqlite_path}/emails.db"

    logging = BeautifiedLogging()

    def __init__(
        self,
        supervisor_model: str = os.environ["SUPERVISOR_MODEL"],
        sql_model: str = os.environ["SQL_MODEL"],
        finance_clerk_model: str = os.environ["FINANCE_CLERK_MODEL"],
        vision_model: str = os.environ["VISION_MODEL"],
        max_retries: int = 3,
        batch_size: int = 10,
        tool_based: bool = False,
        reset_db_state: bool = False,
    ):

        self.supervisor_model = supervisor_model
        self.sql_model = sql_model
        self.finance_clerk_model = finance_clerk_model
        self.vision_model = vision_model

        self.max_retries = max_retries
        self.batch_size = batch_size

        self.tool_based = tool_based

        self.__reset_data()

        set_db(reset=reset_db_state)
        self.conn = sqlite3.connect(self.email_db_path)

    def __reset_data(self):
        self.base_result_data = {
            "status": "",
            "response": "",
            "usage": {
                "successful_requests": 0,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_cost": 0,
            },
            "chat_history": [],
        }

        self.empty_usage_stats = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "input_token_details": {"audio": 0, "cache_read": 0},
            "output_token_details": {"audio": 0, "reasoning": 0},
        }

    def __get_emails_in_batches(self, query: str) -> list[str]:
        try:
            # Connect to the SQLite database
            cursor = self.conn.cursor()

            # Execute the query
            cursor.execute(query)

            # Fetch the results in batches
            while True:
                batch = cursor.fetchmany(self.batch_size)
                if not batch:
                    break
                yield batch  # Yield each batch as a generator

        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
        finally:
            # Close the connection
            if self.conn:
                self.conn.close()

    def __parse_timing(self, start_time: datetime) -> str:
        end_time = datetime.now()
        # time_used = (end_time - start_time).microseconds / 1000000
        time_used = (end_time - start_time).total_seconds()

        return {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_time": f"{time_used:.4f}",
        }

    def __parse_chat_history(
        self,
        start_time: datetime,
        chat_history: list[AIMessage, HumanMessage, ToolMessage],
    ) -> list[dict[str, Any]]:
        """Converts chat history to list logs"""
        parsed_data = []
        prev_timestamp = ""
        for msg in chat_history:
            if isinstance(msg, HumanMessage):
                parsed_data.append(
                    {
                        "name": "input",
                        "type": "HumanMessage",
                        "content": msg.content,
                        "timestamp": start_time.isoformat(),
                        "usage": {**self.empty_usage_stats},
                        "model_name": "",
                        "additional_kwargs": {},
                    }
                )
            elif isinstance(msg, ToolMessage):
                parsed_data.append(
                    {
                        "name": msg.name,
                        "type": "ToolMessage",
                        "content": msg.content,
                        "timestamp": prev_timestamp,
                        "usage": {**self.empty_usage_stats},
                        "model_name": "",
                        "additional_kwargs": {},
                    }
                )
            elif isinstance(msg, AIMessage):
                msg_timestamp = msg.additional_kwargs["timestamp"]
                msg_model = (
                    msg.response_metadata["model_name"]
                    if "model_name" in msg.response_metadata
                    else msg.response_metadata["model"]
                    if "model" in msg.response_metadata
                    else "unknown"
                )
                msg_content = msg.content
                msg_kwargs = {}
                if msg.tool_calls:
                    msg_content = (
                        f"Tool calls to {','.join([x['name'] for x in msg.tool_calls])}"
                    )
                    msg_kwargs["tool_calls"] = msg.tool_calls

                parsed_data.append(
                    {
                        "name": msg.additional_kwargs["sender"],
                        "type": "AIMessage",
                        "content": msg_content,
                        "timestamp": msg_timestamp,
                        "usage": msg.usage_metadata,
                        "model_name": msg_model,
                        "additional_kwargs": msg_kwargs,
                    }
                )
                prev_timestamp = msg_timestamp
        return parsed_data

    def __update_email_status(
        self,
        email_id: str,
        start_time: datetime,
        response: str,
        usage: dict[str:Any],
        chat_history: list[AIMessage, HumanMessage, ToolMessage],
    ):
        cursor = self.conn.cursor()

        data_to_save = {
            **usage,
            **self.__parse_timing(start_time),
            "full_logs": json.dumps(
                self.__parse_chat_history(
                    chat_history=chat_history, start_time=start_time
                )
            ),
            "response": response,
            "process_status": (
                "RECURSION_LIMIT_REACHED"
                if "RECURSION ERROR" in response
                else (
                    "API_ERROR"
                    if "EXCEPTION" in response
                    else (
                        "NOT_INVOICE"
                        if "NA" in response
                        else "ERROR" if "ERROR" in response else "SUCCESS"
                    )
                )
            ),
        }

        set_clause = ", ".join(f"{key} = ?" for key in data_to_save.keys())
        where_clause = f"""
            WHERE email_id = "{email_id}"
        """
        update_query = f"UPDATE emails SET {set_clause} {where_clause}"

        parameters = list(data_to_save.values())

        cursor.execute(update_query, parameters)
        self.conn.commit()

    def __email_recon(self, email: str) -> dict[str, Any]:
        try:
            attachments = f"Attachment: {email[5]}" if email[5] else ""

            email_data_string = f"""
            Sender: {email[1]}
            Subject: {email[3]}
            Body: {email[4]}
            {attachments}
            """

            chat_id = str(uuid.uuid4())
            invoicing_asst = None

            if self.tool_based:
                invoicing_asst = ToolBasedEmailReconInvoicingAssistant(
                    supervisor_model=self.supervisor_model,
                    sql_model=self.sql_model,
                    finance_clerk_model=self.finance_clerk_model,
                    vision_model=self.vision_model,
                    transaction_db_path=self.transaction_db_path,
                )
            else:
                invoicing_asst = EmailReconInvoicingAssistant(
                    supervisor_model=self.supervisor_model,
                    sql_model=self.sql_model,
                    finance_clerk_model=self.finance_clerk_model,
                    vision_model=self.vision_model,
                    transaction_db_path=self.transaction_db_path,
                )

            response = invoicing_asst.generate_response(
                f"""
                Help to reconcile invoices using the following email:

                {email_data_string}
                """,
                chat_id,
            )

            usage = invoicing_asst.check_usage()
            chat_history = invoicing_asst.get_chat_history(chat_id)
            return {
                "status": "DONE",
                "response": response,
                "usage": usage,
                "chat_history": chat_history,
            }
        except GraphRecursionError as e:
            print(f"GraphRecursionError occurred: {e}")
            traceback.print_exc()

            return_data = {
                **self.base_result_data,
                "status": "RECURSION ERROR",
                "response": f"RECURSION ERROR: {e}",
            }
            if invoicing_asst is not None:
                usage = invoicing_asst.check_usage()
                chat_history = invoicing_asst.get_chat_history(chat_id)

                return_data["chat_history"] = chat_history
                return_data["usage"] = usage

            return return_data
        except Exception as e:
            print(f"Exception occurred: {e}")
            traceback.print_exc()

            return_data = {
                **self.base_result_data,
                "status": "EXCEPTION",
                "response": f"EXCEPTION: {e}",
            }
            if invoicing_asst is not None:
                usage = invoicing_asst.check_usage()
                chat_history = invoicing_asst.get_chat_history(chat_id)

                return_data["chat_history"] = chat_history
                return_data["usage"] = usage
            return return_data

    def __parse_emails(self, query: str):
        for email_list in self.__get_emails_in_batches(query):
            for email in email_list:
                start_time = datetime.now()
                retry_count = 0
                recon_state = {**self.base_result_data}
                while recon_state["status"] not in ["DONE", "RECUSTION ERROR"]:
                    new_recon_state = self.__email_recon(email)
                    recon_state["status"] = new_recon_state["status"]
                    recon_state["response"] = new_recon_state["response"]
                    recon_state["chat_history"] += new_recon_state["chat_history"]
                    for key in recon_state["usage"]:
                        recon_state["usage"][key] += new_recon_state["usage"].get(
                            key, 0
                        )

                    # retry max_retries times else set to api error
                    if retry_count == self.max_retries:
                        break
                    retry_count += 1

                self.__update_email_status(
                    email_id=email[0],
                    start_time=start_time,
                    response=recon_state["response"],
                    usage=recon_state["usage"],
                    chat_history=recon_state["chat_history"],
                )
                self.__reset_data()

    def __evaluate(self):
        """
        Count number of unprocessed data
        """
        unprocessed_transactions = query_sqlite_db(
            self.transaction_db_path,
            """
            SELECT COUNT(*) FROM transactions WHERE reconciliation_state = "UNPAID"
            """,
        )
        self.logging.info(
            "User",
            f"""
            Unprocessed transactions

            {unprocessed_transactions[0][0]}
            """,
        )

        unprocessed_emails = query_sqlite_db(
            self.email_db_path,
            """
            SELECT COUNT(*) FROM emails WHERE process_status = "NOT_STARTED"
            """,
        )
        self.logging.info(
            "User",
            f"""
            Unprocessed emails

            {unprocessed_emails[0][0]}
            """,
        )

    def run(self, query: str = "SELECT * FROM emails"):
        """
        Run service
        """
        self.__evaluate()
        self.__parse_emails(query)
        self.__evaluate()


if __name__ == "__main__":
    max_entries = os.getenv("MAX_ENTRIES")
    SYS_SQL_QUERY = "SELECT * FROM emails"
    if max_entries:
        SYS_SQL_QUERY = f"{SYS_SQL_QUERY} LIMIT {max_entries}"
    if len(sys.argv) > 1:
        cmd_args = sys.argv[1]
        if cmd_args.startswith("SELECT "):
            SYS_SQL_QUERY = cmd_args

    ReconApp(
        supervisor_model=os.environ["SUPERVISOR_MODEL"],
        sql_model=os.environ["SQL_MODEL"],
        finance_clerk_model=os.environ["FINANCE_CLERK_MODEL"],
        vision_model=os.environ["VISION_MODEL"],
        max_retries=int(
            os.getenv("MAX_RETRIES", "3")
        ),
        batch_size=10,
        tool_based=True,
        reset_db_state=os.getenv("RESET_DB_STATE") == "true",
    ).run(SYS_SQL_QUERY)
