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


def save_imessages_to_supabase(supabase_client, imessages: list, batch_size: int = 100):
    """Save iMessage data to Supabase database in batches."""

    if not imessages:
        print("No messages to process")
        return None

    total_messages = len(imessages)
    total_batches = (total_messages + batch_size - 1) // batch_size  # Ceiling division
    successful_inserts = 0
    failed_batches = []

    print(
        f"Processing {total_messages} messages in {total_batches} batches of {batch_size}"
    )

    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_messages)
        batch_messages = imessages[start_idx:end_idx]

        print(
            f"Processing batch {batch_num + 1}/{total_batches} ({len(batch_messages)} messages)..."
        )

        # Transform entries for database storage
        db_entries = []
        for msg in batch_messages:
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

        # Insert batch to Supabase
        try:
            result = supabase_client.table("imessages").insert(db_entries).execute()
            if result and result.data:
                successful_inserts += len(result.data)
                print(
                    f"✅ Batch {batch_num + 1} completed: {len(result.data)} messages saved"
                )
            else:
                print(f"❌ Batch {batch_num + 1} failed: No data returned")
                failed_batches.append(batch_num + 1)
        except Exception as e:
            print(f"❌ Batch {batch_num + 1} failed with error: {str(e)}")
            failed_batches.append(batch_num + 1)
            continue

    # Summary
    print("\n📊 Batch processing complete:")
    print(f"  - Total messages processed: {total_messages}")
    print(f"  - Successfully inserted: {successful_inserts}")
    print(f"  - Failed batches: {len(failed_batches)}")
    if failed_batches:
        print(f"  - Failed batch numbers: {failed_batches}")

    return {
        "total_messages": total_messages,
        "successful_inserts": successful_inserts,
        "failed_batches": failed_batches,
    }


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

    # Debug: Print the first few messages to understand the tuple structure
    print(f"🔍 Debug: Found {len(messages)} total messages")
    if messages:
        print("🔍 Debug: First message tuple structure:")
        first_msg = messages[0]
        print(f"  Tuple length: {len(first_msg)}")
        for i, item in enumerate(first_msg):
            print(f"  Index {i}: {repr(item)} (type: {type(item).__name__})")
        print()

    # Convert to more structured format
    structured_messages = []
    for msg in messages:
        # Based on documentation and research, the tuple structure appears to be:
        # (user_id, message, date, service, account, is_from_me, ...)
        # But let's be more defensive about accessing the fields

        try:
            # Safely extract fields with bounds checking
            contact = msg[0] if len(msg) > 0 and msg[0] else "Unknown"
            text = msg[1] if len(msg) > 1 and msg[1] else ""

            # The actual position of is_from_me may vary, let's check multiple positions
            is_from_me = False
            if len(msg) > 5:
                # Check if position 5 contains boolean-like data
                potential_is_from_me = msg[5]
                if isinstance(potential_is_from_me, (bool, int)):
                    is_from_me = bool(potential_is_from_me)
                    print(
                        f"🔍 Debug: Found is_from_me at position 5: {is_from_me} for message: '{text[:50]}...'"
                    )
                else:
                    print(
                        f"🔍 Debug: Position 5 is not boolean/int: {type(potential_is_from_me)} = {potential_is_from_me}"
                    )

            # Try alternative positions for is_from_me
            if len(msg) > 4 and not isinstance(msg[4], str):
                potential_is_from_me = msg[4]
                if isinstance(potential_is_from_me, (bool, int)):
                    is_from_me = bool(potential_is_from_me)
                    print(
                        f"🔍 Debug: Found is_from_me at position 4: {is_from_me} for message: '{text[:50]}...'"
                    )

            # Extract other fields safely
            service = msg[2] if len(msg) > 2 and msg[2] else "Unknown"
            account = msg[3] if len(msg) > 3 and msg[3] else ""
            timestamp = (
                msg[4]
                if len(msg) > 4 and isinstance(msg[4], str)
                else (msg[2] if len(msg) > 2 and isinstance(msg[2], str) else "")
            )

            # If we find a date-like string, use it as timestamp
            for i in range(len(msg)):
                if (
                    isinstance(msg[i], str)
                    and len(msg[i]) > 10
                    and ("-" in msg[i] or ":" in msg[i])
                ):
                    timestamp = msg[i]
                    break

            structured_msg = {
                "contact": contact,
                "text": text,
                "service": service,
                "account": account,
                "is_from_me": is_from_me,
                "timestamp": timestamp,
            }
            structured_messages.append(structured_msg)

        except Exception as e:
            print(f"⚠️  Error processing message tuple {msg}: {e}")
            continue

    # Additional debugging - show some sample structured messages
    print(f"🔍 Debug: Processed {len(structured_messages)} messages")
    if structured_messages:
        print("🔍 Debug: Sample structured messages:")
        for i, msg in enumerate(structured_messages[:5]):
            print(
                f"  Message {i + 1}: is_from_me={msg['is_from_me']}, text='{msg['text'][:50]}...'"
            )

        # Count messages by is_from_me
        from_me_count = sum(1 for msg in structured_messages if msg["is_from_me"])
        not_from_me_count = sum(
            1 for msg in structured_messages if not msg["is_from_me"]
        )
        print(
            f"🔍 Debug: Messages from me: {from_me_count}, Messages not from me: {not_from_me_count}"
        )

    return structured_messages


def save_imessages_data(imessages: list):
    """Save iMessage data to Supabase if configured, otherwise save to JSON."""
    supabase_client = get_supabase_client("imessages")

    if supabase_client:
        print(f"Saving {len(imessages)} iMessages to Supabase...")
        result = save_imessages_to_supabase(supabase_client, imessages)
        if result and result.get("successful_inserts", 0) > 0:
            print(
                f"✅ Successfully saved {result['successful_inserts']} iMessages to Supabase"
            )
            if result.get("failed_batches"):
                print(
                    f"⚠️  {len(result['failed_batches'])} batches failed - some data may not have been saved"
                )
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
