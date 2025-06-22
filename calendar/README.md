# Calendar Event Saver

This script saves your recent Google Calendar events to a JSON file.

## Steps

Follow the same setup steps as in the [Gmail README](../gmail/README.md), but enable the **Google Calendar API** instead of the Gmail API:

- Go to the [Google Cloud Console](https://console.cloud.google.com/)
- Use the same project or create a new one
- Enable the **Google Calendar API** for your project
- Use the same `credentials.json` file from the Gmail setup
- You may need to add your Google account as a test user if not already done

Run the script:

```bash
python calendar2.py
```

On first run, it will use the same authentication flow as the Gmail script. The `token.json` file will be updated with Calendar API permissions.

The script will create a JSON file with a timestamp in the filename (e.g., `recent_events_10_20231215_143022.json`) containing:

- Event metadata (ID, status, created/updated timestamps)
- Event details (summary, description, start/end times, location)
- Attendees information
- Recurrence rules if applicable
- Timestamp of when the events were saved

Note that we cannot call the file "calendar.py" because it interferes.
