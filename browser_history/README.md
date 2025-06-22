# Chrome History Extractor

This script extracts your Google Chrome browsing history and saves it to a JSON file.

## Steps

Run the script:

```bash
python browser_history/browser_history.py
```

The script will locate your Chrome history database, extract all browsing history entries, and save the data to `data/chrome_history_YYYYMMDD_HHMMSS.json`.

The script creates a JSON file with a timestamp in the filename (e.g., `chrome_history_20241215_143022.json`) containing:

- Extraction date and browser information
- Total count of history entries
- Individual entries with URL, title, visit count, and timestamp
- Chrome timestamps converted to ISO format

## Features

- Directly accesses Chrome's SQLite history database
- No external dependencies beyond Python standard library
- Saves data in structured JSON format
- Includes timestamps, URLs, page titles, and visit counts
- Creates timestamped backup files
- Handles Chrome's database locking by creating temporary copies

## How It Works

The script:

1. Locates Chrome's History database file on your system
2. Creates a temporary copy (since Chrome locks the original file)
3. Queries the SQLite database for browsing history
4. Converts Chrome's timestamp format to standard ISO format
5. Saves the data as structured JSON

## Supported Systems

- **macOS**: `~/Library/Application Support/Google/Chrome/Default/History`
- **Windows**: `%LOCALAPPDATA%\Google\Chrome\User Data\Default\History`
- **Linux**: `~/.config/google-chrome/Default/History`

## Usage

### Run the Script

```bash
python browser-history.py
```

### Output

The script will:

1. Locate your Chrome history database
2. Extract all browsing history entries
3. Save the data to `data/chrome_history_YYYYMMDD_HHMMSS.json`
4. Print a summary of extracted entries

### JSON Format

```json
{
  "extraction_date": "2024-01-01T12:00:00.000000",
  "browser": "Google Chrome",
  "total_entries": 1500,
  "entries": [
    {
      "url": "https://example.com",
      "title": "Example Page",
      "visit_count": 3,
      "timestamp": "2024-01-01T11:30:00.000000+00:00"
    }
  ]
}
```

## Requirements

- Python 3.6+
- Google Chrome installed with browsing history
- Standard library modules: `sqlite3`, `json`, `os`, `shutil`, `tempfile`, `datetime`

## Privacy Note

This tool accesses your Chrome history database directly. The data is saved locally and not transmitted anywhere. Make sure to handle the exported JSON files appropriately to protect your privacy.

## Troubleshooting

- **"Chrome history database not found"**: Make sure Chrome is installed and you have browsing history
- **Permission errors**: Close Chrome completely before running the script
- **Empty results**: Check if Chrome has browsing history and try running with Chrome closed
