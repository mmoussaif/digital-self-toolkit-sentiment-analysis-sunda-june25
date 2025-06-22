#!/usr/bin/env python3
"""
Browser History Extractor
Directly extracts Chrome browser history from SQLite database and saves to JSON file.
"""

import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone

# Add the parent directory to Python path to enable imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from databases.helpers import get_supabase_client, save_data_to_json


def get_chrome_history_path():
    """
    Get the path to Chrome's history database based on the operating system.
    """
    import platform

    system = platform.system()

    if system == "Darwin":  # macOS
        return os.path.expanduser(
            "~/Library/Application Support/Google/Chrome/Default/History"
        )
    elif system == "Windows":
        return os.path.expanduser(
            "~\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\History"
        )
    elif system == "Linux":
        return os.path.expanduser("~/.config/google-chrome/Default/History")
    else:
        raise OSError(f"Unsupported operating system: {system}")


def chrome_time_to_datetime(chrome_time):
    """
    Convert Chrome timestamp to Python datetime.
    Chrome uses microseconds since January 1, 1601 UTC.
    """
    if chrome_time == 0:
        return None

    # Chrome epoch starts at January 1, 1601
    # Unix epoch starts at January 1, 1970
    # Difference is 11644473600 seconds
    unix_timestamp = (chrome_time / 1000000) - 11644473600
    return datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)


def save_browser_history_to_supabase(supabase_client, history_entries: list):
    """Save browser history data to Supabase database."""

    # Transform entries for database storage
    db_entries = []
    for entry in history_entries:
        # Truncate very long URLs to prevent index issues (Postgres btree limit ~2704 bytes)
        url = entry["url"]
        if len(url.encode("utf-8")) > 2000:  # Leave some buffer below the limit
            url = url[:2000] + "..." if len(url) > 2000 else url

        # Truncate very long titles as well
        title = entry["title"] or ""
        if len(title.encode("utf-8")) > 500:
            title = title[:500] + "..." if len(title) > 500 else title

        db_entry = {
            "url": url,
            "title": title,
            "visit_count": entry["visit_count"],
            "timestamp": entry["timestamp"],
            "browser": "Google Chrome",  # This matches the default in the schema
            "extraction_date": datetime.now().isoformat(),
        }
        db_entries.append(db_entry)

    # Insert all entries at once
    result = supabase_client.table("browser_history").insert(db_entries).execute()
    return result


def extract_chrome_history():
    """
    Extract Chrome browser history from SQLite database.
    """
    # Get Chrome history database path
    history_path = get_chrome_history_path()

    if not os.path.exists(history_path):
        print(f"Chrome history database not found at: {history_path}")
        return None

    print(f"Found Chrome history database: {history_path}")

    # Create a temporary copy since Chrome locks the database
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_file:
        temp_path = temp_file.name

    shutil.copy2(history_path, temp_path)

    # Connect to the copied database
    conn = sqlite3.connect(temp_path)
    cursor = conn.cursor()

    # Query to get browsing history
    query = """
    SELECT urls.url, urls.title, urls.visit_count, urls.last_visit_time
    FROM urls
    WHERE urls.last_visit_time > 0
    ORDER BY urls.last_visit_time DESC
    """

    cursor.execute(query)
    results = cursor.fetchall()

    print(f"Found {len(results)} history entries")

    # Convert to structured data
    history_entries = []
    for url, title, visit_count, last_visit_time in results:
        # Convert timestamp safely
        timestamp_dt = (
            chrome_time_to_datetime(last_visit_time) if last_visit_time else None
        )

        entry = {
            "url": url,
            "title": title or "",
            "visit_count": visit_count,
            "timestamp": timestamp_dt.isoformat() if timestamp_dt else None,
        }
        history_entries.append(entry)

    conn.close()

    # Clean up temporary file
    if os.path.exists(temp_path):
        os.unlink(temp_path)

    return history_entries


def save_browser_history_data(history_entries: list):
    """Save browser history data to Supabase if configured, otherwise save to JSON."""
    supabase_client = get_supabase_client("browser_history")

    if supabase_client:
        print(f"Saving {len(history_entries)} history entries to Supabase...")
        result = save_browser_history_to_supabase(supabase_client, history_entries)
        if result and result.data:
            print(
                f"✅ Successfully saved {len(result.data)} history entries to Supabase"
            )
        else:
            print("❌ Failed to save to Supabase, falling back to JSON...")
            save_data_to_json(
                history_entries, "chrome_history", "browser_history/data", "failed_"
            )
    else:
        print("Supabase not configured, saving to JSON...")
        save_data_to_json(history_entries, "chrome_history", "browser_history/data")


def save_browser_history():
    """
    Extract Chrome browser history and save to JSON file.
    """
    print("Extracting Chrome browser history...")

    # Extract history
    history_entries = extract_chrome_history()

    if history_entries is None:
        return None

    print(f"Total entries extracted: {len(history_entries)}")

    # Save the data
    save_browser_history_data(history_entries)

    return history_entries


def main():
    """
    Main function to extract and save Chrome browser history.
    """
    print("Chrome History Extractor")
    print("=" * 50)

    # Extract and save history
    result = save_browser_history()

    if result:
        print("\nSuccess! Chrome history extracted and saved.")
        print(f"Total entries: {len(result)}")
    else:
        print("\nFailed to extract Chrome history.")
        print("Make sure Chrome is installed and you have browsing history.")


if __name__ == "__main__":
    main()
