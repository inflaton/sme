"""
Class to access gmail using API
"""

import base64
import os

from bs4 import BeautifulSoup

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from src.llm.models import ModelRouter


class GmailOcrService:
    """
    Class to access gmail using API and perform OCR on the attachments
    """

    cwd = os.getcwd()

    GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
    CREDENTIALS_PATH = f"{cwd}/src/credentials/credentials.json"
    TOKEN_PATH = f"{cwd}/src/credentials/token.json"

    creds: Credentials = None
    gmail_service = None

    def __init__(self):
        self.__buld_credentials()
        self.__build_gmail_service()

    def __buld_credentials(self):
        if os.path.exists(self.TOKEN_PATH):
            self.creds = Credentials.from_authorized_user_file(
                self.TOKEN_PATH, self.GMAIL_SCOPES
            )

        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.CREDENTIALS_PATH, self.GMAIL_SCOPES
                )
                self.creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(self.TOKEN_PATH, "w", encoding="utf-8") as token:
                token.write(self.creds.to_json())

    def __build_gmail_service(self):
        self.gmail_service = build("gmail", "v1", credentials=self.creds)

    def __process_parts(self, message_id, parts, save_path="attachments"):
        body_message = ""
        body_html = ""
        attachment_data = []

        for part in parts:
            mimeType = part.get("mimeType", "")
            body = part.get("body", {})
            data = body.get("data", "")
            filename = part.get("filename")

            if "multipart" in mimeType:
                subparts = part.get("parts", [])
                new_message, new_html, new_attachment_data = self.__process_parts(
                    message_id, subparts, save_path
                )
                body_message += new_message
                body_html += new_html
                attachment_data.extend(new_attachment_data)

            elif mimeType == "text/plain":
                try:
                    new_message = base64.urlsafe_b64decode(data).decode("utf-8")
                    body_message += new_message
                except Exception as e:
                    print(f"Error decoding text/plain: {e}")

            elif mimeType == "text/html":
                try:
                    new_html = base64.urlsafe_b64decode(data).decode("utf-8")
                    body_html += new_html
                except Exception as e:
                    print(f"Error decoding text/html: {e}")

            elif filename:
                # Handle attachments
                try:
                    if "attachmentId" in body:
                        attachment = (
                            self.gmail_service.users()
                            .messages()
                            .attachments()
                            .get(
                                userId="me",
                                messageId=message_id,
                                id=body["attachmentId"],
                            )
                            .execute()
                        )
                        attachment_data.append(
                            self.__attachments_ocr(attachment["data"])
                        )

                except Exception as e:
                    print(f"Error saving attachment: {e}")

            return body_message, body_html, attachment_data

    def __get_llm_model(self, temperature: float = 0.8):
        return ModelRouter().get_model(temperature=0)

    def get_data(self):
        """
        Get emails
        """
        if self.gmail_service is None:
            return

        messages = self.gmail_service.users().messages().list(userId="me").execute()

        parsed_emails = []
        for message in messages["messages"]:
            emails_output = {
                "subject": "",
                "from_email": "",
                "content": "",
                "attachments": [],
            }
            msg = (
                self.gmail_service.users()
                .messages()
                .get(userId="me", id=message["id"])
                .execute()
            )
            subject = [
                header["value"]
                for header in msg["payload"]["headers"]
                if header["name"] == "Subject"
            ]
            from_email = [
                header["value"]
                for header in msg["payload"]["headers"]
                if header["name"] == "From"
            ]
            body_message, body_html, attachment_data = self.__process_parts(
                message["id"], [msg["payload"]]
            )
            content = (
                body_message
                if body_message
                else BeautifulSoup(body_html, "html.parser").text
            )
            emails_output["subject"] = subject
            emails_output["from_email"] = from_email[0] if from_email else ""
            emails_output["content"] = content
            emails_output["attachments"] = attachment_data

            parsed_emails.append(emails_output)
            print(emails_output)

    def __attachments_ocr(self, image: str) -> str:
        model = self.__get_llm_model()["model"]

        image_part = {
            "type": "image_url",
            "image_url": f"data:image/jpeg;base64,{image}",
        }
        text_part = {
            "type": "text",
            "text": "Please find data useful for invoice reconciliation in this image. This includes the invoice reference number, invoice date, paid date and the invoice value",
        }

        content_parts = [image_part, text_part]

        message = [HumanMessage(content=content_parts)]

        chain = message | model | StrOutputParser()
        return chain.invoke()


if __name__ == "__main__":
    GmailOcrService().get_data()
