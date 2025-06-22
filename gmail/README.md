# Gmail Email Saver

This script saves your most recent Gmail email to a JSON file.

## Steps

Enable Gmail API:

- Go to the [Google Cloud Console](https://console.cloud.google.com/)
- Create a new project or select an existing one
- Enable the Gmail API for your project
- Go to "Credentials" → "Create credentials" → "OAuth client ID"
- Choose "Desktop application" as the application type
- Give it a name (e.g., "Gmail Email Saver")
- Download the credentials JSON file and save it as `credentials.json` in the root of the repo
- You may need to go to "Audience" and add your Gmail account as a test user.

Run the script:

```bash
python gmail.py
```

On first run, it will open a browser window for you to authenticate with Google. After authentication, it will save a `token.json` file for future use.

The script will create a JSON file with a timestamp in the filename (e.g., `most_recent_email_20231215_143022.json`) containing:

- Email metadata (ID, thread ID, labels)
- Headers (from, to, subject, date, etc.)
- Email body (both text and HTML versions if available)
- Timestamp of when the email was saved
