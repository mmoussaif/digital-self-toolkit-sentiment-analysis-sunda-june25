# WhatsApp

Uses [whatsmeow](https://github.com/tulir/whatsmeow) library to extract recent WhatsApp messages and save them to JSON files. You will need to leave it on as Whatsapp messages come in.

## Steps

- Install Go (sorry)
- Run `go mod download` to install dependencies
- Run `go run main.go` to start the WhatsApp client
- Scan the QR code shown in Whatsapp to add a new device
- Keep syncing/receiving messages, then Ctrl-C.
- Messages will be saved to a JSON file in the data directory.
