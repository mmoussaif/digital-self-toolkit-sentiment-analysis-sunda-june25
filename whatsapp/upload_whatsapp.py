#!/usr/bin/env python3
"""
WhatsApp Messages Uploader
Uploads WhatsApp messages from JSON files produced by main.go to Supabase or saves to JSON file.
"""

import glob
import json
import os
import sys

# Add the parent directory to Python path to enable imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from databases.helpers import get_supabase_client, save_data_to_json


def save_whatsapp_messages_to_supabase(supabase_client, whatsapp_messages: list):
    """Save WhatsApp messages data to Supabase database."""

    # Transform entries for database storage
    db_entries = []
    for msg in whatsapp_messages:
        # Truncate very long messages to prevent index issues
        text = msg.get("text", "") or ""
        if len(text.encode("utf-8")) > 1000:
            text = text[:1000] + "..." if len(text) > 1000 else text

        # Truncate names
        from_name = msg.get("from_name", "") or ""
        if len(from_name.encode("utf-8")) > 500:
            from_name = from_name[:500] + "..." if len(from_name) > 500 else from_name

        chat_name = msg.get("chat_name", "") or ""
        if len(chat_name.encode("utf-8")) > 500:
            chat_name = chat_name[:500] + "..." if len(chat_name) > 500 else chat_name

        db_entry = {
            "id": msg.get("id"),
            "timestamp": msg.get("timestamp"),
            "from_jid": msg.get("from_jid"),
            "from_name": from_name,
            "chat_jid": msg.get("chat_jid"),
            "chat_name": chat_name,
            "message_type": msg.get("message_type"),
            "text": text,
            "is_from_me": msg.get("is_from_me", False),
            "is_group": msg.get("is_group", False),
        }
        db_entries.append(db_entry)

    # Remove duplicates within the batch based on ID
    seen_ids = set()
    unique_entries = []
    for entry in db_entries:
        if entry["id"] not in seen_ids:
            seen_ids.add(entry["id"])
            unique_entries.append(entry)

    print(
        f"📊 Filtered {len(db_entries)} messages down to {len(unique_entries)} unique messages"
    )

    # Use upsert to handle duplicate keys gracefully
    result = supabase_client.table("whatsapp_messages").upsert(unique_entries).execute()
    return result


def find_most_recent_whatsapp_file():
    """Find the most recent WhatsApp messages JSON file."""
    # Look for files matching the pattern in whatsapp/data directory
    pattern = "whatsapp/data/whatsapp_messages_*.json"
    files = glob.glob(pattern)

    if not files:
        print("❌ No WhatsApp messages files found in whatsapp/data/")
        print(
            "💡 Make sure to run the Go script (main.go) first to generate message files"
        )
        return None

    # Sort by modification time, most recent first
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    most_recent = files[0]

    print(f"📁 Found {len(files)} WhatsApp message files")
    print(f"📄 Using most recent: {most_recent}")

    return most_recent


def load_whatsapp_messages(file_path: str):
    """Load WhatsApp messages from JSON file."""
    print(f"📖 Reading messages from: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        messages = json.load(f)

    print(f"📊 Loaded {len(messages)} messages")
    return messages


def save_whatsapp_messages_data(whatsapp_messages: list):
    """Save WhatsApp messages data to Supabase if configured, otherwise save to JSON."""
    supabase_client = get_supabase_client("whatsapp_messages")

    if supabase_client:
        print(f"Saving {len(whatsapp_messages)} WhatsApp messages to Supabase...")
        result = save_whatsapp_messages_to_supabase(supabase_client, whatsapp_messages)
        if result and result.data:
            print(
                f"✅ Successfully saved {len(result.data)} WhatsApp messages to Supabase"
            )
        else:
            print("❌ Failed to save to Supabase, falling back to JSON...")
            save_data_to_json(
                whatsapp_messages, "whatsapp_messages", "whatsapp/data", "failed_"
            )
    else:
        print("Supabase not configured, saving to JSON...")
        save_data_to_json(whatsapp_messages, "whatsapp_messages", "whatsapp/data")


def upload_whatsapp_messages(file_path: str | None = None):
    """
    Upload WhatsApp messages from JSON file to Supabase or save to JSON file.
    """
    print("Uploading WhatsApp messages...")

    # Find the most recent file if no specific file provided
    if file_path is None:
        file_path = find_most_recent_whatsapp_file()
        if file_path is None:
            return None

    # Load messages from file
    whatsapp_messages = load_whatsapp_messages(file_path)

    if not whatsapp_messages:
        print("❌ No messages found in file")
        return None

    # Save the data
    save_whatsapp_messages_data(whatsapp_messages)

    return whatsapp_messages


def main():
    """
    Main function to upload WhatsApp messages.
    """
    print("WhatsApp Messages Uploader")
    print("=" * 50)

    # Upload messages
    result = upload_whatsapp_messages()

    if result:
        print("\nSuccess! WhatsApp messages uploaded and saved.")
        print(f"Total messages: {len(result)}")
    else:
        print("\nFailed to upload WhatsApp messages.")
        print("Make sure you have message files generated by the Go script.")


if __name__ == "__main__":
    main()
