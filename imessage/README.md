# iMessage (macOS)

Uses 3rd party library: https://github.com/niftycode/imessage_reader

## Steps

First copy your chat.db file to an accessible place. You must do this in Finder for now

- `open ~/Library/Messages`
- Copy `chat.db`
- Paste it into this directory's `data` folder (which is safely gitignored)

Then run imessage.py to extract:

```
# Will look for ./chat.db
python imessage.py

# Will look for ./chat.db and show recipients
python imessage.py -r

# Export to JSON using local chat.db
python imessage.py -o data/messages.json
```

TODO: Automate copying of chat.db
