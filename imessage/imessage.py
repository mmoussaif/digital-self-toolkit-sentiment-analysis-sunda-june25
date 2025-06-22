#!/usr/bin/env python3
"""
Simple iMessage exporter using the imessage-reader package.
Exports iMessage data to data/messages.json
"""

import json
from pathlib import Path

from imessage_reader import fetch_data


def main():
    """Export iMessage data to data/messages.json using imessage-reader package"""
    try:
        # Default path to chat.db on macOS
        db_path = Path("data/chat.db")

        # If chat.db doesn't exist in default location, try local data directory
        if not db_path.exists():
            db_path = Path.cwd() / "data" / "chat.db"

        if not db_path.exists():
            print("❌ Error: chat.db not found in default location or data/ directory")
            print(
                "💡 Tip: Copy chat.db to the data/ directory or ensure Full Disk Access is granted"
            )
            return

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

        # Ensure output directory exists
        output_path = Path("data/messages.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Export to JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(structured_messages, f, indent=2, ensure_ascii=False)

        print(f"✅ Exported {len(structured_messages)} messages to {output_path}")

    except Exception as e:
        print(f"❌ Error: {e}")
        print(
            "\n💡 Tip: On macOS, you may need to grant Full Disk Access to your terminal:"
        )
        print("   System Preferences > Security & Privacy > Privacy > Full Disk Access")


if __name__ == "__main__":
    main()
