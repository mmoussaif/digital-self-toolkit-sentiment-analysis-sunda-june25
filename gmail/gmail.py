import base64
import os
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from databases.helpers import get_supabase_client, save_data_to_json

# Gmail API scope for reading emails
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def save_email_to_supabase(supabase_client, email_data: dict):
    """Save email data to Supabase database."""

    # Transform the data to match the database schema
    db_email = {
        "id": email_data["id"],
        "thread_id": email_data["thread_id"],
        "label_ids": email_data["label_ids"],
        "snippet": email_data["snippet"],
        "history_id": email_data["history_id"],
        "internal_date": int(email_data["internal_date"])
        if email_data["internal_date"]
        else None,
        "headers": email_data["headers"],
        "mime_type": email_data["mime_type"],
        "body_text": email_data["body"]["text"],
        "body_html": email_data["body"]["html"],
        "saved_at": email_data["saved_at"],
    }

    result = supabase_client.table("gmail_emails").insert(db_email).execute()
    return result


def save_emails_data(all_emails: list):
    """Save emails data to Supabase if configured, otherwise save to JSON."""
    supabase_client = get_supabase_client("gmail_emails")

    if supabase_client:
        print(f"Saving {len(all_emails)} emails to Supabase...")

        successful_saves = 0
        failed_emails = []

        for i, email_data in enumerate(all_emails, 1):
            print(f"Saving email {i}/{len(all_emails)} to Supabase...")
            result = save_email_to_supabase(supabase_client, email_data)
            if result and result.data:
                successful_saves += 1
                print(f"  ✅ Email {i} saved successfully")
            else:
                print(f"  ❌ Failed to save email {i}")
                failed_emails.append(email_data)

        print(
            f"\n📊 Results: {successful_saves}/{len(all_emails)} emails saved to Supabase"
        )

        # Save failed emails to JSON as backup
        if failed_emails:
            print(f"💾 Saving {len(failed_emails)} failed emails to JSON as backup...")
            save_data_to_json(failed_emails, "recent_emails", "gmail/data", "failed_")
    else:
        # Fallback to JSON if Supabase not configured
        print("Supabase not configured, saving to JSON...")
        save_data_to_json(all_emails, "recent_emails", "gmail/data")


def authenticate_gmail():
    """Authenticate and return Gmail service object."""
    creds = None

    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists("gmail/token.json"):
        creds = Credentials.from_authorized_user_file("gmail/token.json", SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # You need to download credentials.json from Google Cloud Console
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open("gmail/token.json", "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def decode_email_content(data):
    """Decode base64 encoded email content."""
    try:
        decoded_bytes = base64.urlsafe_b64decode(data)
        return decoded_bytes.decode("utf-8")
    except Exception as e:
        print(f"Error decoding content: {e}")
        return data


def extract_email_data(service, message_id):
    """Extract comprehensive email data from message ID."""
    try:
        message = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

        email_data = {
            "id": message["id"],
            "thread_id": message["threadId"],
            "label_ids": message.get("labelIds", []),
            "snippet": message.get("snippet", ""),
            "history_id": message.get("historyId"),
            "internal_date": message.get("internalDate"),
            "payload": {},
        }

        payload = message["payload"]
        headers = payload.get("headers", [])

        # Extract important headers
        header_data = {}
        for header in headers:
            name = header["name"]
            value = header["value"]
            if name.lower() in [
                "from",
                "to",
                "subject",
                "date",
                "cc",
                "bcc",
                "reply-to",
            ]:
                header_data[name.lower()] = value

        email_data["headers"] = header_data
        email_data["mime_type"] = payload.get("mimeType", "")

        # Extract body content
        body_data = {"text": "", "html": ""}

        def extract_parts(parts):
            for part in parts:
                mime_type = part.get("mimeType", "")
                if mime_type == "text/plain":
                    if "data" in part["body"]:
                        body_data["text"] = decode_email_content(part["body"]["data"])
                elif mime_type == "text/html":
                    if "data" in part["body"]:
                        body_data["html"] = decode_email_content(part["body"]["data"])
                elif "parts" in part:
                    extract_parts(part["parts"])

        # Handle different payload structures
        if "parts" in payload:
            extract_parts(payload["parts"])
        else:
            # Single part message
            if payload.get("mimeType") == "text/plain" and "data" in payload.get(
                "body", {}
            ):
                body_data["text"] = decode_email_content(payload["body"]["data"])
            elif payload.get("mimeType") == "text/html" and "data" in payload.get(
                "body", {}
            ):
                body_data["html"] = decode_email_content(payload["body"]["data"])

        email_data["body"] = body_data

        return email_data

    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def get_recent_emails(count=10):
    """Get the most recent emails and save them to JSON."""
    try:
        service = authenticate_gmail()

        # Get list of messages (most recent first)
        results = (
            service.users().messages().list(userId="me", maxResults=count).execute()
        )
        messages = results.get("messages", [])

        if not messages:
            print("No messages found.")
            return

        print(f"Retrieving {len(messages)} emails...")

        all_emails = []

        # Process each message
        for i, message in enumerate(messages, 1):
            print(f"Processing email {i}/{len(messages)} (ID: {message['id']})")

            # Extract full email data
            email_data = extract_email_data(service, message["id"])

            if email_data:
                # Add timestamp for when this was saved
                email_data["saved_at"] = datetime.now().isoformat()
                all_emails.append(email_data)

                print(
                    f"  Subject: {email_data['headers'].get('subject', 'No subject')}"
                )
                print(f"  From: {email_data['headers'].get('from', 'Unknown sender')}")
            else:
                print(f"  Failed to retrieve email data for message {i}")

        if all_emails:
            # Save all emails to JSON file
            save_emails_data(all_emails)
        else:
            print("No email data was successfully retrieved.")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    get_recent_emails()
