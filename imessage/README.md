# iMessage (macOS)

Uses 3rd party library: https://github.com/niftycode/imessage_reader

## Steps

First copy your chat.db file to an accessible place. You must do this in Finder for now

- `open ~/Library/Messages`
- Copy `chat.db`
- Paste it into this directory's `data` folder (which is safely gitignored)

Then run imessage.py to extract:

```
python imessage.py
```

TODO: Automate copying of chat.db
