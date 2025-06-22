package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/mdp/qrterminal"
	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types/events"
	waLog "go.mau.fi/whatsmeow/util/log"
	_ "github.com/mattn/go-sqlite3"
)

// MessageData represents a WhatsApp message for JSON export
type MessageData struct {
	ID          string    `json:"id"`
	Timestamp   time.Time `json:"timestamp"`
	FromJID     string    `json:"from_jid"`
	FromName    string    `json:"from_name"`
	ChatJID     string    `json:"chat_jid"`
	ChatName    string    `json:"chat_name"`
	MessageType string    `json:"message_type"`
	Text        string    `json:"text"`
	IsFromMe    bool      `json:"is_from_me"`
	IsGroup     bool      `json:"is_group"`
}

var messages []MessageData
var client *whatsmeow.Client

func eventHandler(evt interface{}) {
	switch v := evt.(type) {
	case *events.Message:
		// Extract message data
		msg := MessageData{
			ID:        v.Info.ID,
			Timestamp: v.Info.Timestamp,
			FromJID:   v.Info.Sender.String(),
			ChatJID:   v.Info.Chat.String(),
			IsFromMe:  v.Info.IsFromMe,
			IsGroup:   v.Info.IsGroup,
		}

		// Get sender name
		if v.Info.IsFromMe {
			msg.FromName = "Me"
		} else if v.Info.IsGroup {
			// Try to get participant name from pushname or contact
			if v.Info.PushName != "" {
				msg.FromName = v.Info.PushName
			} else {
				msg.FromName = v.Info.Sender.User
			}
		} else {
			// Direct message - try to get contact name
			if v.Info.PushName != "" {
				msg.FromName = v.Info.PushName
			} else {
				msg.FromName = v.Info.Sender.User
			}
		}

		// Get chat name
		if v.Info.IsGroup {
			// For groups, we'll use the JID for now
			msg.ChatName = v.Info.Chat.User
		} else {
			msg.ChatName = msg.FromName
		}

		// Extract message content
		if v.Message.GetConversation() != "" {
			msg.MessageType = "text"
			msg.Text = v.Message.GetConversation()
		} else if v.Message.GetExtendedTextMessage() != nil {
			msg.MessageType = "extended_text"
			msg.Text = v.Message.GetExtendedTextMessage().GetText()
		} else if v.Message.GetImageMessage() != nil {
			msg.MessageType = "image"
			msg.Text = v.Message.GetImageMessage().GetCaption()
		} else if v.Message.GetVideoMessage() != nil {
			msg.MessageType = "video"
			msg.Text = v.Message.GetVideoMessage().GetCaption()
		} else if v.Message.GetAudioMessage() != nil {
			msg.MessageType = "audio"
			msg.Text = "[Audio Message]"
		} else if v.Message.GetDocumentMessage() != nil {
			msg.MessageType = "document"
			msg.Text = fmt.Sprintf("[Document: %s]", v.Message.GetDocumentMessage().GetTitle())
		} else {
			msg.MessageType = "other"
			msg.Text = "[Unsupported message type]"
		}

		messages = append(messages, msg)
		fmt.Printf("New message from %s in %s: %s\n", msg.FromName, msg.ChatName, msg.Text)

	case *events.Receipt:
		// Handle message receipts (read, delivered, etc.)
		fmt.Printf("Receipt: %s for %s\n", v.Type, v.MessageIDs)
	}
}

func main() {
	// Create logs directory if it doesn't exist
	os.MkdirAll("logs", 0755)
	
	// Setup logging
	dbLog := waLog.Stdout("Database", "INFO", true)
	clientLog := waLog.Stdout("Client", "INFO", true)

	// Create database store
	ctx := context.Background()
	container, err := sqlstore.New(ctx, "sqlite3", "file:session.db?_foreign_keys=on", dbLog)
	if err != nil {
		log.Fatalf("Failed to create database: %v", err)
	}

	// Get first device from store
	deviceStore, err := container.GetFirstDevice(ctx)
	if err != nil {
		log.Fatalf("Failed to get device: %v", err)
	}

	// Create client
	client = whatsmeow.NewClient(deviceStore, clientLog)
	client.AddEventHandler(eventHandler)

	// Connect to WhatsApp
	if client.Store.ID == nil {
		// No previous session, need to pair
		qrChan, _ := client.GetQRChannel(context.Background())
		err = client.Connect()
		if err != nil {
			log.Fatalf("Failed to connect: %v", err)
		}

		for evt := range qrChan {
			if evt.Event == "code" {
				fmt.Println("QR Code:")
				qrterminal.GenerateHalfBlock(evt.Code, qrterminal.L, os.Stdout)
				fmt.Println("Scan this QR code with your WhatsApp mobile app")
			} else {
				fmt.Printf("QR channel result: %s\n", evt.Event)
				if evt.Event == "success" {
					fmt.Println("Successfully paired!")
					break
				}
			}
		}
	} else {
		// Previous session exists, just connect
		err = client.Connect()
		if err != nil {
			log.Fatalf("Failed to connect: %v", err)
		}
		fmt.Println("Connected to WhatsApp!")
	}

	// Setup graceful shutdown
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)

	fmt.Println("WhatsApp message extractor is running...")
	fmt.Println("Send some messages to see them appear here.")
	fmt.Println("Press Ctrl+C to stop and save messages to JSON file.")

	// Wait for interrupt signal
	<-c

	// Save messages to JSON file
	saveMessagesToJSON()

	// Disconnect
	client.Disconnect()
	fmt.Println("Disconnected from WhatsApp")
}

func saveMessagesToJSON() {
	if len(messages) == 0 {
		fmt.Println("No messages to save")
		return
	}

	// Create data directory if it doesn't exist
	os.MkdirAll("data", 0755)

	// Create filename with timestamp
	timestamp := time.Now().Format("2006-01-02_15-04-05")
	filename := filepath.Join("data", fmt.Sprintf("whatsapp_messages_%s.json", timestamp))

	// Convert messages to JSON
	jsonData, err := json.MarshalIndent(messages, "", "  ")
	if err != nil {
		log.Printf("Failed to marshal messages to JSON: %v", err)
		return
	}

	// Write to file
	err = os.WriteFile(filename, jsonData, 0644)
	if err != nil {
		log.Printf("Failed to write messages to file: %v", err)
		return
	}

	fmt.Printf("Saved %d messages to %s\n", len(messages), filename)
} 