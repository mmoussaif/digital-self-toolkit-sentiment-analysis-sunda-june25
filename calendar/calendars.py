import json
import os
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Calendar API scope for reading calendar events
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def authenticate_calendar():
    """Authenticate and return Calendar service object."""
    creds = None

    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # You need to download credentials.json from Google Cloud Console
            flow = InstalledAppFlow.from_client_secrets_file(
                "../credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def extract_event_data(event):
    """Extract comprehensive event data from calendar event."""
    try:
        event_data = {
            "id": event.get("id"),
            "status": event.get("status"),
            "created": event.get("created"),
            "updated": event.get("updated"),
            "summary": event.get("summary", "No title"),
            "description": event.get("description", ""),
            "location": event.get("location", ""),
            "creator": event.get("creator", {}),
            "organizer": event.get("organizer", {}),
            "start": event.get("start", {}),
            "end": event.get("end", {}),
            "attendees": event.get("attendees", []),
            "recurrence": event.get("recurrence", []),
            "html_link": event.get("htmlLink", ""),
            "event_type": event.get("eventType", "default"),
        }

        return event_data

    except Exception as e:
        print(f"Error extracting event data: {e}")
        return None


def get_recent_events(count=10, days_back=30):
    """Get recent calendar events and save them to JSON."""
    try:
        service = authenticate_calendar()

        # Calculate date range (last 30 days by default)
        now = datetime.utcnow()
        start_time = (now - timedelta(days=days_back)).isoformat() + "Z"
        end_time = now.isoformat() + "Z"

        print(f"Retrieving events from the last {days_back} days...")

        # Get events from primary calendar
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_time,
                timeMax=end_time,
                maxResults=count,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        if not events:
            print("No events found.")
            return

        print(f"Found {len(events)} events...")

        all_events = []

        # Process each event
        for i, event in enumerate(events, 1):
            print(
                f"Processing event {i}/{len(events)} (ID: {event.get('id', 'Unknown')})"
            )

            # Extract full event data
            event_data = extract_event_data(event)

            if event_data:
                # Add timestamp for when this was saved
                event_data["saved_at"] = datetime.now().isoformat()
                all_events.append(event_data)

                # Get start time for display
                start = event.get("start", {})
                start_time_str = start.get(
                    "dateTime", start.get("date", "Unknown time")
                )

                print(f"  Title: {event_data['summary']}")
                print(f"  Start: {start_time_str}")
                print(f"  Location: {event_data['location'] or 'No location'}")
            else:
                print(f"  Failed to retrieve event data for event {i}")

        if all_events:
            # Save all events to JSON file
            filename = f"data/recent_events_{len(all_events)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(all_events, f, indent=2, ensure_ascii=False)

            print(f"\n{len(all_events)} events saved successfully to {filename}")
        else:
            print("No event data was successfully retrieved.")

    except HttpError as error:
        print(f"An HTTP error occurred: {error}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    get_recent_events()
