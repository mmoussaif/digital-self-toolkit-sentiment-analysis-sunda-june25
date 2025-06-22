# WhatsApp Message Extractor

A simple Go application that uses the [whatsmeow](https://github.com/tulir/whatsmeow) library to extract recent WhatsApp messages and save them to JSON files.

## Features

- Connects to WhatsApp Web using QR code authentication
- Extracts incoming messages in real-time
- Supports text, image, video, audio, and document messages
- Saves messages to timestamped JSON files in the `data/` directory
- Handles both individual and group chats

## Prerequisites

- Go 1.21 or higher
- A WhatsApp account
- Mobile device with WhatsApp installed for QR code scanning

## Installation & Setup

1. **Clone or download this repository**

2. **Install dependencies:**

   ```bash
   go mod tidy
   ```

3. **Run the application:**

   ```bash
   go run main.go
   ```

4. **Scan the QR code:**

   - A QR code will appear in your terminal
   - Open WhatsApp on your mobile device
   - Go to Settings > Linked Devices > Link a Device
   - Scan the QR code displayed in the terminal

5. **Start receiving messages:**
   - The app will now listen for incoming WhatsApp messages
   - Messages will be displayed in the terminal as they arrive
   - Press `Ctrl+C` to stop the application and save all captured messages to a JSON file

## Output Format

Messages are saved to `data/whatsapp_messages_YYYY-MM-DD_HH-MM-SS.json` with the following structure:

```json
[
  {
    "id": "message_id",
    "timestamp": "2024-01-15T10:30:00Z",
    "from_jid": "sender@whatsapp.net",
    "from_name": "Sender Name",
    "chat_jid": "chat@whatsapp.net",
    "chat_name": "Chat Name",
    "message_type": "text",
    "text": "Hello, world!",
    "is_from_me": false,
    "is_group": false
  }
]
```

## Supported Message Types

- **text**: Regular text messages
- **extended_text**: Text messages with formatting or links
- **image**: Image messages (saves caption if available)
- **video**: Video messages (saves caption if available)
- **audio**: Audio/voice messages
- **document**: Document files
- **other**: Unsupported message types

## Files Created

- `session.db`: SQLite database storing WhatsApp session data (keep this file to avoid re-pairing)
- `data/whatsapp_messages_*.json`: JSON files containing extracted messages
- `logs/`: Directory for application logs

## Important Notes

- **Privacy**: This tool captures all incoming messages. Use responsibly and in compliance with privacy laws.
- **Session Persistence**: The `session.db` file stores your WhatsApp session. Keep it secure and don't share it.
- **Real-time Only**: This tool only captures messages received while it's running. It doesn't fetch message history.
- **Rate Limits**: WhatsApp may impose rate limits. Don't abuse the API.

## Troubleshooting

### QR Code Not Appearing

- Ensure your terminal supports UTF-8 characters
- Try running in a different terminal application

### Connection Issues

- Check your internet connection
- Ensure WhatsApp Web is not open in a browser simultaneously
- Delete `session.db` to force re-pairing if needed

### Build Issues

- Ensure you have Go 1.21 or higher: `go version`
- Run `go mod tidy` to install dependencies

## Dependencies

- [whatsmeow](https://github.com/tulir/whatsmeow): WhatsApp Web API library
- [qrterminal](https://github.com/mdp/qrterminal): Terminal QR code display
- Standard Go libraries for JSON handling and SQLite

## Legal & Ethical Use

This tool is for educational and personal use only. Please:

- Respect privacy and obtain consent before monitoring messages
- Comply with local laws and regulations
- Don't use for spam or malicious purposes
- Follow WhatsApp's Terms of Service

## License

This project uses the whatsmeow library which is licensed under MPL-2.0. Check individual component licenses for complete information.
