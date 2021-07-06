import os
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2 import service_account


def auth_to_google_sheets():
    """Shows basic usage of the Drive v3 API.
    Prints the names and ids of the first 10 files the user has access to.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = service_account.Credentials.from_service_account_info(
                {
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": os.environ.get(
                        "GOOGLE_CLIENT_CERT_URL"
                    ),
                    "client_email": os.environ.get("GOOGLE_CLIENT_EMAIL"),
                    "type": "service_account",
                    "project_id": os.environ.get("GOOGLE_PROJECT_NAME"),
                    "private_key_id": os.environ.get("GOOGLE_PRIVATE_KEY_ID"),
                    "private_key": os.environ.get(
                        "GOOGLE_PRIVATE_KEY"
                    ).replace("\\n", "\n"),
                    "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
                }
            )

    return build("sheets", "v4", credentials=creds).spreadsheets()
