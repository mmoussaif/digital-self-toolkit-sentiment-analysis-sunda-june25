import logging
import os
from collections import defaultdict
from datetime import datetime

import boto3
from dateutil.parser import parse as parse_date
from django.db import models
from supabase import Client, create_client

logger = logging.getLogger(__name__)


class TimeAnalysis(models.Model):
    """Model for storing time-based sentiment analysis results."""

    name = models.CharField(max_length=200, help_text="Name for this analysis")
    description = models.TextField(blank=True, help_text="Description of this analysis")
    start_date = models.DateField(help_text="Start date for analysis period")
    end_date = models.DateField(help_text="End date for analysis period")
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("error", "Error"),
        ],
        default="pending",
    )
    error_message = models.TextField(
        blank=True, help_text="Error message if analysis failed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Time Analysis"
        verbose_name_plural = "Time Analyses"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"

    def save(self, *args, **kwargs):
        """Override save to trigger sentiment analysis when a new analysis is created."""
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new and self.status == "pending":
            print(f"🚀 New TimeAnalysis created: {self.name}")
            print(f"📅 Date range: {self.start_date} to {self.end_date}")
            self.perform_sentiment_analysis()

    def perform_sentiment_analysis(self):
        """
        Perform sentiment analysis on all messages within the date range.
        Groups messages by day and calculates average sentiment using AWS Comprehend.
        """
        print("🔄 Starting sentiment analysis...")

        # Clear ALL existing Day and Message objects (from all TimeAnalyses)
        existing_messages_count = Message.objects.count()
        existing_days_count = Day.objects.count()

        if existing_messages_count > 0:
            print(f"🗑️  Clearing {existing_messages_count} existing Message records...")
            Message.objects.all().delete()
            print("✅ All existing Message records cleared")

        if existing_days_count > 0:
            print(f"🗑️  Clearing {existing_days_count} existing Day records...")
            Day.objects.all().delete()
            print("✅ All existing Day records cleared")
        else:
            print("ℹ️  No existing Day/Message records to clear")

        self.status = "processing"
        self.save(update_fields=["status"])
        print(f"📊 Status updated to: {self.status}")

        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_ANON_KEY")

        print("🔗 Checking Supabase credentials...")
        if not supabase_url or not supabase_key:
            print("❌ Supabase credentials not configured")
            self.status = "error"
            self.error_message = "Supabase credentials not configured"
            self.save(update_fields=["status", "error_message"])
            return
        print("✅ Supabase credentials found")

        # Initialize AWS Comprehend client
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_REGION", "us-east-1")

        print("🔑 Checking AWS credentials...")
        if not aws_access_key or not aws_secret_key:
            print("❌ AWS credentials not configured")
            self.status = "error"
            self.error_message = "AWS credentials not configured"
            self.save(update_fields=["status", "error_message"])
            return
        print(f"✅ AWS credentials found for region: {aws_region}")

        supabase: Client = create_client(supabase_url, supabase_key)
        comprehend = boto3.client(
            "comprehend",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region,
        )

        # Group messages by day - now storing individual messages with metadata
        daily_messages = defaultdict(list)  # date_str -> list of message dicts

        print("📱 Fetching messages from different sources...")
        # Query iMessages
        print("  📩 Querying iMessages...")
        self._fetch_imessages(supabase, daily_messages)

        # Query WhatsApp messages
        print("  💬 Querying WhatsApp messages...")
        self._fetch_whatsapp_messages(supabase, daily_messages)

        total_days_with_messages = len(daily_messages)
        total_messages = sum(len(messages) for messages in daily_messages.values())
        print(
            f"📊 Found {total_messages} messages across {total_days_with_messages} days"
        )

        # Process messages individually for sentiment analysis
        print("🔍 Processing individual messages for sentiment analysis...")
        created_days = 0
        created_messages = 0

        for date_str, message_list in daily_messages.items():
            if not message_list:
                continue

            print(f"  📅 Processing {len(message_list)} messages for {date_str}...")

            # Create Day object
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                day = Day.objects.create(
                    time_analysis=self,
                    date=date_obj,
                    sentiment=0.0,  # Will be updated after processing messages
                    message_count=len(message_list),
                )
                created_days += 1
                print(f"    ✅ Created Day: {date_obj}")
            except Exception as e:
                print(f"    ❌ Error creating Day for {date_str}: {e}")
                logger.error(f"Error creating Day object for {date_str}: {e}")
                continue

            # Process messages in batches for sentiment analysis
            batch_size = 25  # AWS Comprehend BatchDetectSentiment limit
            day_sentiments = []

            for i in range(0, len(message_list), batch_size):
                batch = message_list[i : i + batch_size]
                text_list = [msg["text"] for msg in batch]

                print(
                    f"      Analyzing batch {i // batch_size + 1} ({len(batch)} messages)..."
                )

                # Analyze sentiment for the batch
                sentiment_results = self._analyze_sentiment_batch(comprehend, text_list)

                if sentiment_results:
                    # Create Message objects for successful analyses
                    for j, result in enumerate(sentiment_results):
                        if result is not None:
                            try:
                                message_obj = Message.objects.create(
                                    day=day,
                                    text=batch[j]["text"],
                                    sentiment=result,
                                    source=batch[j]["source"],
                                    contact=batch[j].get("contact", ""),
                                    timestamp=batch[j].get("timestamp"),
                                )
                                day_sentiments.append(result)
                                created_messages += 1
                            except Exception as e:
                                print(f"        ❌ Error creating Message: {e}")
                                logger.error(f"Error creating Message object: {e}")

            # Update day's average sentiment
            if day_sentiments:
                avg_sentiment = sum(day_sentiments) / len(day_sentiments)
                day.sentiment = avg_sentiment
                day.save(update_fields=["sentiment"])
                print(
                    f"    📊 Day {date_str}: avg sentiment {avg_sentiment:.3f} ({len(day_sentiments)} messages)"
                )
            else:
                # No valid messages, delete the day
                day.delete()
                created_days -= 1
                print(f"    ❌ No valid messages for {date_str}, deleted day")

        print(
            f"🎉 Analysis complete! Created {created_days} Day records and {created_messages} Message records"
        )
        self.status = "completed"
        self.save(update_fields=["status"])
        print(f"📊 Status updated to: {self.status}")

    def _fetch_imessages(self, supabase: Client, daily_messages: dict):
        """Fetch iMessages from Supabase and group by day."""
        try:
            # The actual timestamps are in the 'service' column, not 'timestamp'
            # We can filter at the database level since service contains proper datetime strings
            # Only include messages sent BY the user (is_from_me = true)
            start_datetime = f"{self.start_date} 00:00:00"
            end_datetime = f"{self.end_date} 23:59:59"

            print(
                f"    📱 Querying iMessages from {start_datetime} to {end_datetime} (only sent by user)"
            )

            # Fetch messages with pagination
            all_messages = []
            batch_size = 1000
            offset = 0

            while True:
                response = (
                    supabase.table("imessages")
                    .select("text, service, contact, is_from_me")
                    .gte("service", start_datetime)
                    .lte("service", end_datetime)
                    .eq("is_from_me", True)  # Only messages sent by the user
                    .range(offset, offset + batch_size - 1)
                    .execute()
                )

                if not response.data:
                    break

                all_messages.extend(response.data)
                offset += batch_size

                print(
                    f"      Fetched batch {offset // batch_size}: {len(response.data)} messages (total: {len(all_messages)})"
                )

                if len(response.data) < batch_size:
                    break  # No more data

            print(
                f"    📱 Found {len(all_messages)} iMessages sent by user in date range"
            )

            # Verify we only have user messages
            user_messages = [
                msg for msg in all_messages if msg.get("is_from_me") == True
            ]
            if len(user_messages) != len(all_messages):
                print(
                    f"    ⚠️  Warning: Found {len(all_messages) - len(user_messages)} non-user iMessages that shouldn't be there!"
                )

            # Group messages by date
            for message in all_messages:
                if message.get("text") and message.get("service"):
                    # Double-check this is from the user
                    if not message.get("is_from_me"):
                        print(
                            f"    ⚠️  Skipping iMessage not from user: is_from_me={message.get('is_from_me')}"
                        )
                        continue

                    # Debug: Check for problematic message
                    if "I'm totally stumped" in message.get("text", ""):
                        print("    🔍 FOUND PROBLEMATIC MESSAGE:")
                        print(f"        text: '{message.get('text')}'")
                        print(f"        contact: '{message.get('contact')}'")
                        print(f"        is_from_me: {message.get('is_from_me')}")
                        print(f"        service: '{message.get('service')}'")

                    try:
                        # Parse the service field as timestamp
                        parsed_date = parse_date(message["service"]).date()

                        if self.start_date <= parsed_date <= self.end_date:
                            date_str = parsed_date.isoformat()
                            daily_messages[date_str].append(
                                {
                                    "text": message["text"],
                                    "source": "iMessage",
                                    "contact": message.get(
                                        "contact", ""
                                    ),  # This is the recipient
                                    "timestamp": message["service"],
                                }
                            )

                    except Exception as e:
                        logger.warning(
                            f"Error parsing iMessage service timestamp '{message.get('service')}': {e}"
                        )

        except Exception as e:
            print(f"    ❌ Error fetching iMessages: {e}")
            logger.error(f"Error fetching iMessages: {e}")

    def _fetch_whatsapp_messages(self, supabase: Client, daily_messages: dict):
        """Fetch WhatsApp messages from Supabase and group by day."""
        try:
            # WhatsApp messages have proper TIMESTAMPTZ, so we can filter at DB level
            # Only include messages sent BY the user (from_name = "Me")
            print(
                f"    💬 Querying WhatsApp messages from {self.start_date} to {self.end_date} (only sent by user)"
            )

            # Fetch messages with pagination - get more fields to identify recipient
            all_messages = []
            batch_size = 1000
            offset = 0

            while True:
                response = (
                    supabase.table("whatsapp_messages")
                    .select("text, timestamp, from_name, chat_name")
                    .gte("timestamp", self.start_date.isoformat())
                    .lte("timestamp", self.end_date.isoformat())
                    .eq("from_name", "Me")  # Only messages sent by the user
                    .range(offset, offset + batch_size - 1)
                    .execute()
                )

                if not response.data:
                    break

                all_messages.extend(response.data)
                offset += batch_size

                print(
                    f"      Fetched batch {offset // batch_size}: {len(response.data)} messages (total: {len(all_messages)})"
                )

                if len(response.data) < batch_size:
                    break  # No more data

            print(
                f"    💬 Found {len(all_messages)} WhatsApp messages sent by user in date range"
            )

            # Verify we only have user messages
            user_messages = [
                msg for msg in all_messages if msg.get("from_name") == "Me"
            ]
            if len(user_messages) != len(all_messages):
                print(
                    f"    ⚠️  Warning: Found {len(all_messages) - len(user_messages)} non-user messages that shouldn't be there!"
                )

            # Group messages by date
            for message in all_messages:
                if message.get("text") and message.get("timestamp"):
                    # Double-check this is from the user
                    if message.get("from_name") != "Me":
                        print(
                            f"    ⚠️  Skipping message not from user: from_name='{message.get('from_name')}'"
                        )
                        continue

                    # Debug: Check for problematic message
                    if "I'm totally stumped" in message.get("text", ""):
                        print("    🔍 FOUND PROBLEMATIC MESSAGE IN WHATSAPP:")
                        print(f"        text: '{message.get('text')}'")
                        print(f"        chat_name: '{message.get('chat_name')}'")
                        print(f"        from_name: '{message.get('from_name')}'")
                        print(f"        timestamp: '{message.get('timestamp')}'")

                    try:
                        # Parse timestamp (should be proper TIMESTAMPTZ)
                        parsed_date = parse_date(message["timestamp"]).date()

                        if self.start_date <= parsed_date <= self.end_date:
                            date_str = parsed_date.isoformat()

                            # For WhatsApp, the recipient is usually in chat_name or to_name
                            recipient = message.get("chat_name") or "Unknown"

                            daily_messages[date_str].append(
                                {
                                    "text": message["text"],
                                    "source": "WhatsApp",
                                    "contact": recipient,  # Store the recipient, not sender
                                    "timestamp": message["timestamp"],
                                }
                            )

                    except Exception as e:
                        logger.warning(
                            f"Error parsing WhatsApp timestamp '{message.get('timestamp')}': {e}"
                        )

        except Exception as e:
            print(f"    ❌ Error fetching WhatsApp messages: {e}")
            logger.error(f"Error fetching WhatsApp messages: {e}")

    def _fetch_gmail_emails(self, supabase: Client, daily_messages: dict):
        """Fetch Gmail emails from Supabase and group by day."""
        try:
            response = (
                supabase.table("gmail_emails")
                .select("body_text, internal_date")
                .gte("internal_date", int(self.start_date.strftime("%s")) * 1000)
                .lte("internal_date", int(self.end_date.strftime("%s")) * 1000)
                .execute()
            )

            print(f"    ✉️  Found {len(response.data)} Gmail emails")
            for email in response.data:
                if email.get("body_text"):
                    try:
                        # Gmail internal_date is in milliseconds
                        timestamp = datetime.fromtimestamp(
                            email["internal_date"] / 1000
                        ).date()
                        date_str = timestamp.isoformat()
                        if self.start_date <= timestamp <= self.end_date:
                            daily_messages[date_str].append(
                                {
                                    "text": email["body_text"],
                                    "source": "Gmail",
                                    "contact": "",
                                    "timestamp": email["internal_date"],
                                }
                            )
                    except Exception as e:
                        logger.warning(f"Error parsing Gmail timestamp: {e}")

        except Exception as e:
            logger.error(f"Error fetching Gmail emails: {e}")

    def _analyze_sentiment_batch(
        self, comprehend, text_list: list[str]
    ) -> list[float | None]:
        """
        Analyze sentiment using AWS Comprehend BatchDetectSentiment API.
        Returns a list of scores from -1.0 (very negative) to 1.0 (very positive), or None if error.
        """
        try:
            response = comprehend.batch_detect_sentiment(
                TextList=text_list, LanguageCode="en"
            )

            results: list[float | None] = [None] * len(text_list)

            # Process successful results
            for result in response.get("ResultList", []):
                index = result["Index"]
                sentiment = result["Sentiment"]
                scores = result["SentimentScore"]

                # Convert sentiment to numerical score
                if sentiment == "POSITIVE":
                    results[index] = scores["Positive"] - scores["Negative"]
                elif sentiment == "NEGATIVE":
                    results[index] = -(scores["Negative"] - scores["Positive"])
                elif sentiment == "NEUTRAL":
                    results[index] = scores["Positive"] - scores["Negative"]
                else:  # MIXED
                    results[index] = (scores["Positive"] - scores["Negative"]) * 0.5

            # Log errors for failed items
            for error in response.get("ErrorList", []):
                logger.error(
                    f"Error analyzing sentiment for item {error['Index']}: {error['ErrorMessage']}"
                )

            return results

        except Exception as e:
            logger.error(f"Error in batch sentiment analysis: {e}")
            return [None] * len(text_list)


class Day(models.Model):
    """Model for storing daily sentiment analysis results."""

    time_analysis = models.ForeignKey(
        TimeAnalysis, on_delete=models.CASCADE, related_name="days"
    )
    date = models.DateField(help_text="Date for this day's analysis")
    sentiment = models.FloatField(
        help_text="Average sentiment score from -1.0 (negative) to 1.0 (positive)"
    )
    message_count = models.PositiveIntegerField(
        default=0, help_text="Number of messages analyzed for this day"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Day"
        verbose_name_plural = "Days"
        ordering = ["date"]
        unique_together = ["time_analysis", "date"]

    def __str__(self):
        return f"{self.date} - Sentiment: {self.sentiment:.2f}"

    @property
    def sentiment_label(self):
        """Return human-readable sentiment label."""
        if self.sentiment > 0.3:
            return "Positive"
        elif self.sentiment < -0.3:
            return "Negative"
        else:
            return "Neutral"

    def get_top_messages(self, limit=5, happiest=True):
        """Get top happiest or saddest messages for this day."""
        if happiest:
            return self.messages.order_by("-sentiment")[:limit]
        else:
            return self.messages.order_by("sentiment")[:limit]

    @property
    def happiest_messages(self):
        """Get top 5 happiest messages for this day."""
        return self.get_top_messages(limit=5, happiest=True)

    @property
    def saddest_messages(self):
        """Get top 5 saddest messages for this day."""
        return self.get_top_messages(limit=5, happiest=False)


class Message(models.Model):
    """Model for storing individual message sentiment analysis results."""

    day = models.ForeignKey(Day, on_delete=models.CASCADE, related_name="messages")
    text = models.TextField(help_text="The message text")
    sentiment = models.FloatField(
        help_text="Sentiment score from -1.0 (negative) to 1.0 (positive)"
    )
    source = models.CharField(
        max_length=20,
        choices=[
            ("iMessage", "iMessage"),
            ("WhatsApp", "WhatsApp"),
            ("Gmail", "Gmail"),
        ],
        help_text="Source of the message",
    )
    contact = models.CharField(
        max_length=200, blank=True, help_text="Contact or recipient"
    )
    timestamp = models.CharField(
        max_length=100, blank=True, help_text="Original timestamp from source"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ["-sentiment"]  # Default to happiest first

    def __str__(self):
        preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f"{self.source} - {self.sentiment:.2f} - {preview}"

    @property
    def sentiment_label(self):
        """Return human-readable sentiment label."""
        if self.sentiment > 0.3:
            return "Positive"
        elif self.sentiment < -0.3:
            return "Negative"
        else:
            return "Neutral"
