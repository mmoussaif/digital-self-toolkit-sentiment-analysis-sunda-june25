#!/usr/bin/env python3
"""
iMessage Exporter
Exports iMessage data using the imessage-reader package and saves to Supabase or JSON file.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to Python path to enable imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from imessage_reader import fetch_data

from databases.helpers import get_supabase_client, save_data_to_json


def save_imessages_to_supabase(supabase_client, imessages: list):
    """Save iMessage data to Supabase database."""

    # Limit to first 100 messages to avoid timeout
    limited_messages = imessages[:100]
    print(
        f"Processing first {len(limited_messages)} messages out of {len(imessages)} total"
    )

    # Transform entries for database storage
    db_entries = []
    for msg in limited_messages:
        # Truncate very long messages to prevent index issues
        text = msg["text"] or ""
        if len(text.encode("utf-8")) > 1000:
            text = text[:1000] + "..." if len(text) > 1000 else text

        # Truncate contact name
        contact = msg["contact"] or ""
        if len(contact.encode("utf-8")) > 500:
            contact = contact[:500] + "..." if len(contact) > 500 else contact

        db_entry = {
            "contact": contact,
            "text": text,
            "service": msg["service"],
            "account": msg["account"],
            "is_from_me": msg["is_from_me"],
            "timestamp": msg["timestamp"],
        }
        db_entries.append(db_entry)

    # Insert all entries at once
    result = supabase_client.table("imessages").insert(db_entries).execute()
    return result


def extract_imessage_data():
    """Extract iMessage data from chat.db"""
    # Default path to chat.db on macOS
    db_path = Path("imessage/data/chat.db")

    # If chat.db doesn't exist in default location, try local data directory
    if not db_path.exists():
        db_path = Path.cwd() / "imessage" / "data" / "chat.db"

    if not db_path.exists():
        print(
            "❌ Error: chat.db not found in default location or imessage/data/ directory"
        )
        print(
            "💡 Tip: Copy chat.db to the imessage/data/ directory or ensure Full Disk Access is granted"
        )
        return None

    print(f"📖 Reading messages from: {db_path}")

    # Create FetchData instance
    fd = fetch_data.FetchData(str(db_path))

    # Get all messages
    messages = fd.get_messages()

    # Convert to more structured format
    structured_messages = []
    for msg in messages:
        # msg is a tuple: (user_id, message, service, account, is_from_me, timestamp)
        structured_msg = {
            "contact": msg[0] if msg[0] else "Unknown",
            "text": msg[1] if msg[1] else "",
            "service": msg[2] if msg[2] else "Unknown",
            "account": msg[3] if msg[3] else "",
            "is_from_me": bool(msg[4]) if len(msg) > 4 else False,
            "timestamp": msg[5] if len(msg) > 5 else "",
        }
        structured_messages.append(structured_msg)

    return structured_messages


def save_imessages_data(imessages: list):
    """Save iMessage data to Supabase if configured, otherwise save to JSON."""
    supabase_client = get_supabase_client("imessages")

    if supabase_client:
        print(f"Saving {len(imessages)} iMessages to Supabase...")
        result = save_imessages_to_supabase(supabase_client, imessages)
        if result and result.data:
            print(f"✅ Successfully saved {len(result.data)} iMessages to Supabase")
        else:
            print("❌ Failed to save to Supabase, falling back to JSON...")
            save_data_to_json(imessages, "imessages", "imessage/data", "failed_")
    else:
        print("Supabase not configured, saving to JSON...")
        save_data_to_json(imessages, "imessages", "imessage/data")


def save_imessages():
    """
    Extract iMessage data and save to Supabase or JSON file.
    """
    print("Extracting iMessage data...")

    # Extract messages
    imessages = extract_imessage_data()

    if imessages is None:
        return None

    print(f"Total messages extracted: {len(imessages)}")

    # Save the data
    save_imessages_data(imessages)

    return imessages


def main():
    """
    Main function to extract and save iMessage data.
    """
    print("iMessage Data Extractor")
    print("=" * 50)

    # Extract and save messages
    save_imessages()


if __name__ == "__main__":
    main()
