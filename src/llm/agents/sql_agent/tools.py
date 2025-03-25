"""
Tool set for the agent who is in
charge of parsing the emails
"""

import os
import sqlite3

from langchain.tools import tool

from src.misc.beautified_logging import BeautifiedLogging
from src.data.db.db_scripts import query_sqlite_db
from src.misc.path_parser import get_db_path

cwd = os.getcwd()

logging = BeautifiedLogging()

TABLE_NAME = "transactions"


@tool
def invoice_db_query_tool(invoice_id: str) -> str:
    """
    Search for transaction data in the invoice
    """

    db_path = get_db_path()

    logging.info(
        "Tool",
        f"""
        Query Invoice ID: {invoice_id}
        """,
    )

    try:
        result = query_sqlite_db(
            f"{db_path}/{TABLE_NAME}.db",
            f"SELECT invoice_id, bank_name, transaction_id,amount, recipient_name, sender_name FROM {TABLE_NAME} WHERE invoice_id = '{invoice_id}'",
            throw=True,
        )

        logging.info(
            "Tool",
            f"""
            Query result:
            
            {result}
            """,
        )

        if not result:
            return {"content": "No results"}

        headers = [
            "invoice_id",
            "bank_name",
            "transaction_id",
            "amount",
            "recipient_name",
            "sender_name"
        ]

        parsed_results = ""
        for index, header in enumerate(headers):
            result_data = result[0][index]
            formatted_data = result_data
            if "amount" in header:
                formatted_data = f"${format(float(result_data), ',.2f')}"

            parsed_results += f"{header}: { formatted_data }"
        return {"content": parsed_results}

    except sqlite3.Error as e:
        logging.info("Tool", f"Query error: {e}")
        return {
            "content": "ERROR: Query failed. Please rewrite your query and try again."
        }


@tool
def invoice_db_update_tool(invoice_id: str, email_details: str) -> str:
    """
    Updates transaction data in the table
    by providing invoice_id and email_details
    in the parameter

    The reconciliation_state column will be set to PAID
    """

    db_path = get_db_path()

    logging.info(
        "Tool",
        f"""
        Update table:
        
        {invoice_id}: {email_details}
        """,
    )

    try:
        conn = sqlite3.connect(f"{db_path}/transactions.db")
        cursor = conn.cursor()

        # Create the SQL update query
        sql_query = f"""
        UPDATE {TABLE_NAME}
        SET reconciliation_state = 'PAID', email_details = ?
        WHERE invoice_id = '{invoice_id}'
        """

        # Execute the query with the provided values
        cursor.execute(sql_query, (f"{email_details}",))

        # Commit the changes
        conn.commit()

        logging.info("Tool", "Update success")
        return {"content": "DONE"}
    except sqlite3.Error as e:
        logging.info("Tool", f"Update error: {e}")
        return {
            "content": "ERROR: Query failed. Please rewrite your query and try again."
        }
    finally:
        # Close the connection
        if conn:
            conn.close()
