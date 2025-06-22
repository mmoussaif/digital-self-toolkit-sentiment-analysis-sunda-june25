#!/usr/bin/env python3
"""
Browser History Extractor
Directly extracts Chrome browser history from SQLite database and saves to JSON file.
"""

import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone


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


def extract_chrome_history():
    """
    Extract Chrome browser history from SQLite database.
    """
    try:
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

        try:
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
                    chrome_time_to_datetime(last_visit_time)
                    if last_visit_time
                    else None
                )

                entry = {
                    "url": url,
                    "title": title or "",
                    "visit_count": visit_count,
                    "timestamp": timestamp_dt.isoformat() if timestamp_dt else None,
                }
                history_entries.append(entry)

            conn.close()
            return history_entries

        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except Exception as e:
        print(f"Error extracting Chrome history: {e}")
        return None


def save_browser_history():
    """
    Extract Chrome browser history and save to JSON file.
    """
    try:
        print("Extracting Chrome browser history...")

        # Extract history
        history_entries = extract_chrome_history()

        if history_entries is None:
            return None

        # Create structured data
        history_data = {
            "extraction_date": datetime.now().isoformat(),
            "browser": "Google Chrome",
            "total_entries": len(history_entries),
            "entries": history_entries,
        }

        # Create data directory if it doesn't exist
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(data_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chrome_history_{timestamp}.json"
        filepath = os.path.join(data_dir, filename)

        # Save to JSON file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)

        print(f"\nChrome history saved to: {filepath}")
        print(f"Total entries extracted: {len(history_entries)}")

        return filepath

    except Exception as e:
        print(f"Error saving browser history: {e}")
        return None


def main():
    """
    Main function to extract and save Chrome browser history.
    """
    print("Chrome History Extractor")
    print("=" * 50)

    # Extract and save history
    result = save_browser_history()

    if result:
        print(f"\nSuccess! Chrome history saved to: {result}")
    else:
        print("\nFailed to extract Chrome history.")
        print("Make sure Chrome is installed and you have browsing history.")


if __name__ == "__main__":
    main()
