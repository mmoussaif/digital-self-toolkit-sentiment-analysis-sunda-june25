#!/usr/bin/env python3
"""
Calendar Events Extractor
Extracts Google Calendar events and saves to Supabase or JSON file.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Add the parent directory to Python path to enable imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from databases.helpers import get_supabase_client, save_data_to_json

# Calendar API scope for reading calendar events
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def authenticate_calendar():
    """Authenticate and return Calendar service object."""
    creds = None

    # The file token.json stores the user's access and refresh tokens.
    token_path = "calendar/token.json"
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # You need to download credentials.json from Google Cloud Console
            credentials_path = "calendar/credentials.json"
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def extract_event_data(event):
    """Extract comprehensive event data from calendar event."""
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


def save_calendar_events_to_supabase(supabase_client, calendar_events: list):
    """Save calendar events data to Supabase database."""

    # Transform entries for database storage
    db_entries = []
    for event in calendar_events:
        # Truncate very long descriptions to prevent index issues
        description = event["description"] or ""
        if len(description.encode("utf-8")) > 1000:
            description = (
                description[:1000] + "..." if len(description) > 1000 else description
            )

        # Truncate very long summaries as well
        summary = event["summary"] or ""
        if len(summary.encode("utf-8")) > 500:
            summary = summary[:500] + "..." if len(summary) > 500 else summary

        # Truncate location
        location = event["location"] or ""
        if len(location.encode("utf-8")) > 500:
            location = location[:500] + "..." if len(location) > 500 else location

        db_entry = {
            "id": event["id"],
            "status": event["status"],
            "created_at": event["created"],
            "updated_at": event["updated"],
            "summary": summary,
            "description": description,
            "location": location,
            "creator": event["creator"] if event["creator"] else None,
            "organizer": event["organizer"] if event["organizer"] else None,
            "start_time": event["start"],
            "end_time": event["end"],
            "attendees": event["attendees"] if event["attendees"] else None,
            "recurrence": event["recurrence"] if event["recurrence"] else None,
            "html_link": event["html_link"],
            "event_type": event["event_type"],
        }
        db_entries.append(db_entry)

    # Insert all entries at once
    result = supabase_client.table("calendar_events").insert(db_entries).execute()
    return result


def get_recent_events(count=10, days_back=30):
    """Get recent calendar events."""
    service = authenticate_calendar()

    # Calculate date range (last 30 days by default)
    now = datetime.now(timezone.utc)
    start_time = (now - timedelta(days=days_back)).isoformat().replace("+00:00", "Z")
    end_time = now.isoformat().replace("+00:00", "Z")

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
        return []

    print(f"Found {len(events)} events...")

    all_events = []

    # Process each event
    for i, event in enumerate(events, 1):
        print(f"Processing event {i}/{len(events)} (ID: {event.get('id', 'Unknown')})")

        # Extract full event data
        event_data = extract_event_data(event)

        if event_data:
            # Add timestamp for when this was saved
            event_data["saved_at"] = datetime.now().isoformat()
            all_events.append(event_data)

            # Get start time for display
            start = event.get("start", {})
            start_time_str = start.get("dateTime", start.get("date", "Unknown time"))

            print(f"  Title: {event_data['summary']}")
            print(f"  Start: {start_time_str}")
            print(f"  Location: {event_data['location'] or 'No location'}")
        else:
            print(f"  Failed to retrieve event data for event {i}")

    return all_events


def save_calendar_events_data(calendar_events: list):
    """Save calendar events data to Supabase if configured, otherwise save to JSON."""
    supabase_client = get_supabase_client("calendar_events")

    if supabase_client:
        print(f"Saving {len(calendar_events)} calendar events to Supabase...")
        result = save_calendar_events_to_supabase(supabase_client, calendar_events)
        if result and result.data:
            print(
                f"✅ Successfully saved {len(result.data)} calendar events to Supabase"
            )
        else:
            print("❌ Failed to save to Supabase, falling back to JSON...")
            save_data_to_json(
                calendar_events, "calendar_events", "calendar/data", "failed_"
            )
    else:
        print("Supabase not configured, saving to JSON...")
        save_data_to_json(calendar_events, "calendar_events", "calendar/data")


def save_calendar_events():
    """
    Extract calendar events and save to Supabase or JSON file.
    """
    print("Extracting Google Calendar events...")

    # Extract events
    calendar_events = get_recent_events()

    if not calendar_events:
        return None

    print(f"Total events extracted: {len(calendar_events)}")

    # Save the data
    save_calendar_events_data(calendar_events)

    return calendar_events


def main():
    """
    Main function to extract and save Google Calendar events.
    """
    print("Google Calendar Events Extractor")
    print("=" * 50)

    # Extract and save events
    result = save_calendar_events()

    if result:
        print("\nSuccess! Calendar events extracted and saved.")
        print(f"Total events: {len(result)}")
    else:
        print("\nFailed to extract calendar events.")
        print("Make sure you have valid Google Calendar credentials and events.")


if __name__ == "__main__":
    main()
