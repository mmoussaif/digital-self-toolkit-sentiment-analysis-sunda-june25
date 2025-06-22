# Digital Self Toolkit

Here you will find some trusted starter code to download/access personal data from different sources.

Create a new Python venv and install requirements.txt. Then run `npm install` for the TS/JS data importers. Then look at the README files in each subdirectory to get started.

Run all the python scripts from the root e.g. `python3 ./gmail/gmail.py`

WARNING: These scripts download personal data to files. I did my best to download to .gitignored locations BUT ALWAYS CHECK BEFORE YOU COMMIT TO MAKE SURE NO PERSONAL DATA IS COMMITTED TO ANY FORK YOU MAKE OF THIS REPO.

You can optionally follow instructions in `database` to create a Supabase database that holds the imported data, rather than outputting files. Needed for iOS.

## Types of data supported:

- Browser history (Chrome)
- Google calendar
- Gmail email
- iMessage
- iPhone location
- Whatsapp
- Computer screen OCR history (Broken?)
