#!/usr/bin/env python3
"""
Supabase Database Setup Script
Creates tables for storing personal data from various sources.
"""

import os
from typing import Dict

from supabase import Client, create_client


class SupabaseSetup:
    def __init__(self, url: str = None, key: str = None):
        """Initialize Supabase client with URL and API key."""
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_ANON_KEY")

        if not self.url or not self.key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_ANON_KEY environment variables must be set"
            )

        self.supabase: Client = create_client(self.url, self.key)

    def create_tables(self):
        """Create all required tables for personal data storage."""
        tables = [
            self._browser_history_table(),
            self._calendar_events_table(),
            self._gmail_emails_table(),
            self._imessages_table(),
            self._whatsapp_messages_table(),
            self._screen_activity_table(),
            self._location_history_table(),
        ]

        print("Creating Supabase tables...")

        for table_sql in tables:
            try:
                # Execute SQL using Supabase's RPC function or direct SQL execution
                # Note: This requires a database function or direct SQL access
                print(table_sql)
            except Exception as e:
                print(f"Error creating table: {e}")

    def _browser_history_table(self) -> str:
        """SQL for browser history table."""
        return """
        CREATE TABLE IF NOT EXISTS browser_history (
            id BIGSERIAL PRIMARY KEY,
            url TEXT NOT NULL,
            title TEXT,
            visit_count INTEGER DEFAULT 1,
            timestamp TIMESTAMPTZ,
            browser TEXT DEFAULT 'Chrome',
            extraction_date TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_browser_history_timestamp ON browser_history(timestamp);
        CREATE INDEX IF NOT EXISTS idx_browser_history_url ON browser_history(url);
        CREATE INDEX IF NOT EXISTS idx_browser_history_extraction_date ON browser_history(extraction_date);
        """

    def _calendar_events_table(self) -> str:
        """SQL for calendar events table."""
        return """
        CREATE TABLE IF NOT EXISTS calendar_events (
            id TEXT PRIMARY KEY,
            status TEXT,
            created_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ,
            summary TEXT,
            description TEXT,
            location TEXT,
            creator JSONB,
            organizer JSONB,
            start_time JSONB,
            end_time JSONB,
            attendees JSONB,
            recurrence JSONB,
            html_link TEXT,
            event_type TEXT DEFAULT 'default',
            saved_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_calendar_events_start_time ON calendar_events((start_time->>'dateTime'));
        CREATE INDEX IF NOT EXISTS idx_calendar_events_summary ON calendar_events(summary);
        CREATE INDEX IF NOT EXISTS idx_calendar_events_saved_at ON calendar_events(saved_at);
        """

    def _gmail_emails_table(self) -> str:
        """SQL for Gmail emails table."""
        return """
        CREATE TABLE IF NOT EXISTS gmail_emails (
            id TEXT PRIMARY KEY,
            thread_id TEXT,
            label_ids JSONB,
            snippet TEXT,
            history_id TEXT,
            internal_date BIGINT,
            headers JSONB,
            mime_type TEXT,
            body_text TEXT,
            body_html TEXT,
            saved_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_gmail_emails_thread_id ON gmail_emails(thread_id);
        CREATE INDEX IF NOT EXISTS idx_gmail_emails_internal_date ON gmail_emails(internal_date);
        CREATE INDEX IF NOT EXISTS idx_gmail_emails_saved_at ON gmail_emails(saved_at);
        CREATE INDEX IF NOT EXISTS idx_gmail_emails_sender ON gmail_emails((headers->>'from'));
        CREATE INDEX IF NOT EXISTS idx_gmail_emails_subject ON gmail_emails((headers->>'subject'));
        CREATE INDEX IF NOT EXISTS idx_gmail_emails_labels ON gmail_emails USING GIN(label_ids);
        """

    def _imessages_table(self) -> str:
        """SQL for iMessages table."""
        return """
        CREATE TABLE IF NOT EXISTS imessages (
            id BIGSERIAL PRIMARY KEY,
            contact TEXT,
            text TEXT,
            service TEXT,
            account TEXT,
            is_from_me BOOLEAN DEFAULT FALSE,
            timestamp TEXT,
            saved_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_imessages_contact ON imessages(contact);
        CREATE INDEX IF NOT EXISTS idx_imessages_timestamp ON imessages(timestamp);
        CREATE INDEX IF NOT EXISTS idx_imessages_is_from_me ON imessages(is_from_me);
        CREATE INDEX IF NOT EXISTS idx_imessages_saved_at ON imessages(saved_at);
        """

    def _whatsapp_messages_table(self) -> str:
        """SQL for WhatsApp messages table."""
        return """
        CREATE TABLE IF NOT EXISTS whatsapp_messages (
            id TEXT PRIMARY KEY,
            timestamp TIMESTAMPTZ,
            from_jid TEXT,
            from_name TEXT,
            chat_jid TEXT,
            chat_name TEXT,
            message_type TEXT,
            text TEXT,
            is_from_me BOOLEAN DEFAULT FALSE,
            is_group BOOLEAN DEFAULT FALSE,
            saved_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_timestamp ON whatsapp_messages(timestamp);
        CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_chat_jid ON whatsapp_messages(chat_jid);
        CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_from_jid ON whatsapp_messages(from_jid);
        CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_is_from_me ON whatsapp_messages(is_from_me);
        CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_saved_at ON whatsapp_messages(saved_at);
        """

    def _screen_activity_table(self) -> str:
        """SQL for screen activity table."""
        return """
        CREATE TABLE IF NOT EXISTS screen_activity (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ,
            text TEXT,
            app_name TEXT,
            window_name TEXT,
            has_frame BOOLEAN DEFAULT FALSE,
            frame TEXT, -- base64 encoded screenshot
            extracted_at TIMESTAMPTZ,
            hours_back INTEGER,
            activity_type TEXT DEFAULT 'ocr', -- 'ocr' or 'audio'
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_screen_activity_timestamp ON screen_activity(timestamp);
        CREATE INDEX IF NOT EXISTS idx_screen_activity_app_name ON screen_activity(app_name);
        CREATE INDEX IF NOT EXISTS idx_screen_activity_activity_type ON screen_activity(activity_type);
        CREATE INDEX IF NOT EXISTS idx_screen_activity_extracted_at ON screen_activity(extracted_at);
        """

    def _location_history_table(self) -> str:
        """SQL for location history table (placeholder for future iOS data)."""
        return """
        CREATE TABLE IF NOT EXISTS location_history (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ,
            latitude DECIMAL(10, 8),
            longitude DECIMAL(11, 8),
            accuracy DECIMAL,
            altitude DECIMAL,
            speed DECIMAL,
            heading DECIMAL,
            activity_type TEXT, -- 'walking', 'driving', 'stationary', etc.
            location_name TEXT,
            address TEXT,
            source TEXT DEFAULT 'ios', -- 'ios', 'android', 'manual'
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_location_history_timestamp ON location_history(timestamp);
        CREATE INDEX IF NOT EXISTS idx_location_history_coordinates ON location_history(latitude, longitude);
        CREATE INDEX IF NOT EXISTS idx_location_history_activity_type ON location_history(activity_type);
        CREATE INDEX IF NOT EXISTS idx_location_history_source ON location_history(source);
        """

    def get_table_schemas(self) -> Dict[str, str]:
        """Return dictionary of table names and their SQL schemas."""
        return {
            "browser_history": self._browser_history_table(),
            "calendar_events": self._calendar_events_table(),
            "gmail_emails": self._gmail_emails_table(),
            "imessages": self._imessages_table(),
            "whatsapp_messages": self._whatsapp_messages_table(),
            "screen_activity": self._screen_activity_table(),
            "location_history": self._location_history_table(),
        }


def main():
    """Main function to set up Supabase database."""
    print("Supabase Database Setup")
    print("=" * 50)

    try:
        # Initialize Supabase setup
        setup = SupabaseSetup()

        # Create tables
        setup.create_tables()

        print("\n✅ Database setup completed!")
        print("\nNext steps:")
        print(
            "1. Copy the SQL statements above and run them in your Supabase SQL editor"
        )
        print("2. Set up Row Level Security (RLS) policies if needed")
        print("3. Test the connection using test_connection.py")

    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        print("\nTroubleshooting:")
        print(
            "1. Make sure SUPABASE_URL and SUPABASE_ANON_KEY are set in your environment"
        )
        print("2. Verify your Supabase project is accessible")
        print("3. Check your API key permissions")


if __name__ == "__main__":
    main()
