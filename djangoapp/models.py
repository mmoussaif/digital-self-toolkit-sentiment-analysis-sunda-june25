import logging
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse

import boto3
from dateutil.parser import parse as parse_date
from django.db import models
from supabase import Client, create_client

from .location_clustering import process_location_data

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

        # Clear ALL existing Day, Message, and Location objects (from all TimeAnalyses)
        existing_messages_count = Message.objects.count()
        existing_days_count = Day.objects.count()
        existing_locations_count = Location.objects.count()

        if existing_messages_count > 0:
            print(f"🗑️  Clearing {existing_messages_count} existing Message records...")
            Message.objects.all().delete()
            print("✅ All existing Message records cleared")

        if existing_days_count > 0:
            print(f"🗑️  Clearing {existing_days_count} existing Day records...")
            Day.objects.all().delete()
            print("✅ All existing Day records cleared")

        if existing_locations_count > 0:
            print(
                f"🗑️  Clearing {existing_locations_count} existing Location records..."
            )
            Location.objects.all().delete()
            print("✅ All existing Location records cleared")

        if (
            existing_messages_count == 0
            and existing_days_count == 0
            and existing_locations_count == 0
        ):
            print("ℹ️  No existing Day/Message/Location records to clear")

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

        # Fetch location data
        print("📍 Fetching location data...")
        self._fetch_location_data(supabase)

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

        # SECOND PASS: Website correlation analysis
        print("\n🌐 Starting website correlation analysis (second pass)...")
        self._analyze_website_correlations(supabase)

        # THIRD PASS: Person correlation analysis
        print("\n👥 Starting person correlation analysis (third pass)...")
        self._analyze_person_correlations(daily_messages)

        # FOURTH PASS: Place correlation analysis
        print("\n📍 Starting place correlation analysis (fourth pass)...")
        self._analyze_place_correlations()

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

                    # Skip unsupported message types
                    if "[Unsupported message type]" in message.get("text", ""):
                        print("    ⚠️  Skipping unsupported message type")
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

                    # Skip unsupported message types
                    if "[Unsupported message type]" in message.get("text", ""):
                        print("    ⚠️  Skipping unsupported message type")
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

    def _fetch_location_data(self, supabase: Client):
        """Fetch location data from Supabase and store it."""
        try:
            # Convert date range to timestamps for filtering
            start_datetime = f"{self.start_date} 00:00:00"
            end_datetime = f"{self.end_date} 23:59:59"

            print(
                f"    📍 Querying location data from {start_datetime} to {end_datetime}"
            )

            # Fetch location data with pagination
            all_locations = []
            batch_size = 1000
            offset = 0

            while True:
                response = (
                    supabase.table("location_history")
                    .select(
                        "timestamp, latitude, longitude, accuracy, altitude, speed, heading, activity_type, location_name, address, source"
                    )
                    .gte("timestamp", start_datetime)
                    .lte("timestamp", end_datetime)
                    .range(offset, offset + batch_size - 1)
                    .execute()
                )

                if not response.data:
                    break

                all_locations.extend(response.data)
                offset += batch_size

                print(
                    f"      Fetched batch {offset // batch_size}: {len(response.data)} locations (total: {len(all_locations)})"
                )

                if len(response.data) < batch_size:
                    break  # No more data

            print(f"    📍 Found {len(all_locations)} location records in date range")

            if not all_locations:
                print("    ℹ️  No location data to process")
                return

            # Convert to temporary objects for clustering
            location_objects = []
            for location_data in all_locations:
                try:
                    timestamp = parse_date(location_data["timestamp"])

                    # Ensure all fields have proper default values to avoid NULL constraint issues
                    location_obj = {
                        "timestamp": timestamp,
                        "latitude": location_data.get("latitude"),
                        "longitude": location_data.get("longitude"),
                        "accuracy": location_data.get("accuracy"),
                        "altitude": location_data.get("altitude"),
                        "speed": location_data.get("speed"),
                        "heading": location_data.get("heading"),
                        "activity_type": location_data.get("activity_type") or "",
                        "location_name": location_data.get("location_name") or "",
                        "address": location_data.get("address") or "",
                        "source": location_data.get("source") or "ios",
                    }
                    location_objects.append(location_obj)
                except Exception as e:
                    print(f"      ❌ Error parsing location data: {e}")
                    logger.warning(f"Error parsing location data: {e}")

            print(
                f"    🔍 Clustering {len(location_objects)} location points using new methodology..."
            )

            # Convert to format expected by new clustering algorithm
            gps_data = []
            for loc_obj in location_objects:
                gps_data.append(
                    {
                        "latitude": loc_obj["latitude"],
                        "longitude": loc_obj["longitude"],
                        "timestamp": loc_obj["timestamp"].isoformat(),
                        "activity_type": loc_obj.get("activity_type", ""),
                        "location_name": loc_obj.get("location_name", ""),
                        "address": loc_obj.get("address", ""),
                        "source": loc_obj.get("source", "ios"),
                    }
                )

            # Use the new clustering approach
            location_clusters = process_location_data(
                gps_data,
                stay_distance_threshold=100,  # 100m for stay point detection
                stay_time_threshold=10,  # 10 minutes minimum
                cluster_distance_threshold=200,  # 200m for clustering stay points
                min_cluster_visits=2,  # At least 2 visits to be significant
            )

            # Convert LocationCluster objects to Django Location models
            locations = []
            for cluster in location_clusters:
                location = Location.objects.create(
                    time_analysis=self,
                    name=cluster.name,
                    center_latitude=cluster.center_latitude,
                    center_longitude=cluster.center_longitude,
                    visit_count=cluster.visit_count,
                    total_time_minutes=int(cluster.total_time_minutes),
                    first_visit=cluster.first_visit,
                    last_visit=cluster.last_visit,
                    address=cluster.address,
                    activity_types=dict(cluster.activity_types),
                )
                locations.append(location)

            print(
                f"    📍 Created {len(locations)} distinct locations from new clustering methodology"
            )

        except Exception as e:
            print(f"    ❌ Error fetching location data: {e}")
            logger.error(f"Error fetching location data: {e}")

    def _cluster_locations(
        self, location_data: list, cluster_radius_meters: int = 200
    ) -> list:
        """
        Cluster nearby GPS points into distinct locations using distance-based clustering.
        Returns a list of created Location objects.
        """
        if not location_data:
            return []

        print(
            f"      🔍 Starting clustering with {len(location_data)} GPS points (radius: {cluster_radius_meters}m)"
        )

        # Sort by timestamp
        location_data.sort(key=lambda x: x["timestamp"])

        locations = []
        unclustered = location_data.copy()
        cluster_id = 1

        while unclustered:
            # Start a new cluster with the first unclustered point
            seed_point = unclustered.pop(0)
            cluster_points = [seed_point]

            print(
                f"        Cluster {cluster_id}: Started with seed at {seed_point['latitude']}, {seed_point['longitude']}"
            )

            # Find all points within cluster radius of the seed
            remaining = []
            for point in unclustered:
                distance = self._calculate_distance(
                    seed_point["latitude"],
                    seed_point["longitude"],
                    point["latitude"],
                    point["longitude"],
                )
                if distance <= cluster_radius_meters:
                    cluster_points.append(point)
                    print(f"          Added point {distance:.0f}m away")
                else:
                    remaining.append(point)

            unclustered = remaining

            print(
                f"        Cluster {cluster_id}: Final size {len(cluster_points)} points"
            )

            # Only create location if we have enough points (reduces noise)
            if len(cluster_points) >= 2:  # Require at least 2 points for a location
                location = self._create_location_from_cluster(cluster_points)
                if location:
                    locations.append(location)
                    print(f"        ✅ Created location from cluster {cluster_id}")
                else:
                    print(
                        f"        ❌ Failed to create location from cluster {cluster_id}"
                    )
            else:
                print(
                    f"        ⚠️  Skipping cluster {cluster_id} (too few points: {len(cluster_points)})"
                )

            cluster_id += 1

        print(
            f"      📊 Clustering complete: {len(locations)} locations from {len(location_data)} GPS points"
        )
        return locations

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in meters using Haversine formula."""
        lat1, lon1, lat2, lon2 = map(
            math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)]
        )

        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        r = 6371000  # Earth's radius in meters

        return c * r

    def _create_location_from_cluster(self, cluster_points: list):
        """Create a Location object from a cluster of GPS points."""
        if not cluster_points:
            return None

        try:
            # Calculate center coordinates (simple average)
            center_lat = sum(
                float(point["latitude"]) for point in cluster_points
            ) / len(cluster_points)
            center_lon = sum(
                float(point["longitude"]) for point in cluster_points
            ) / len(cluster_points)

            # Sort by timestamp to get first and last visits
            cluster_points.sort(key=lambda x: x["timestamp"])
            first_visit = cluster_points[0]["timestamp"]
            last_visit = cluster_points[-1]["timestamp"]

            # Count activity types
            activity_types = {}
            for point in cluster_points:
                activity = point.get("activity_type")
                if activity:
                    activity_types[activity] = activity_types.get(activity, 0) + 1

            # Get a name (use location_name if available, otherwise use address)
            location_name = ""
            for point in cluster_points:
                if point.get("location_name"):
                    location_name = point["location_name"]
                    break

            location_address = ""
            for point in cluster_points:
                if point.get("address"):
                    location_address = point["address"]
                    break

            # Estimate time spent (rough calculation based on point density)
            total_time_minutes = len(cluster_points) * 30  # 30 minutes per GPS point

            # Create Location object
            location = Location.objects.create(
                time_analysis=self,
                name=location_name,
                center_latitude=center_lat,
                center_longitude=center_lon,
                visit_count=len(cluster_points),
                total_time_minutes=total_time_minutes,
                first_visit=first_visit,
                last_visit=last_visit,
                address=location_address,
                activity_types=activity_types,
            )

            print(f"      ✅ Created location: {location}")
            return location

        except Exception as e:
            print(f"      ❌ Error creating location from cluster: {e}")
            logger.error(f"Error creating location from cluster: {e}")
            return None

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

    def _analyze_website_correlations(self, supabase: Client):
        """
        Second pass: Analyze correlation between website visits and daily sentiment scores.
        """
        print("🔍 Fetching browser history data...")

        # Clear existing WebsiteAnalysis records for this TimeAnalysis
        existing_website_count = WebsiteAnalysis.objects.filter(
            time_analysis=self
        ).count()
        if existing_website_count > 0:
            print(
                f"🗑️  Clearing {existing_website_count} existing WebsiteAnalysis records..."
            )
            WebsiteAnalysis.objects.filter(time_analysis=self).delete()
            print("✅ Existing WebsiteAnalysis records cleared")

        # Fetch browser history for the date range
        daily_website_visits = defaultdict(set)  # date_str -> set of domains
        domain_example_urls = {}  # domain -> example_url
        self._fetch_browser_history(supabase, daily_website_visits, domain_example_urls)

        # Get all days with sentiment scores
        days_with_sentiment = Day.objects.filter(
            time_analysis=self, sentiment__isnull=False
        ).order_by("date")
        if not days_with_sentiment.exists():
            print(
                "❌ No days with sentiment scores found for website correlation analysis"
            )
            return

        print(f"📊 Found {days_with_sentiment.count()} days with sentiment scores")

        # Collect all unique domains
        all_domains = set()
        for domains in daily_website_visits.values():
            all_domains.update(domains)

        print(f"🌐 Found {len(all_domains)} unique website domains")

        if not all_domains:
            print("❌ No browser history data found for correlation analysis")
            return

        # Calculate correlations for each domain
        website_analyses = []
        for domain in all_domains:
            print(f"  📈 Analyzing correlation for {domain}...")
            correlation_data = self._calculate_domain_correlation(
                domain, days_with_sentiment, daily_website_visits
            )

            if correlation_data:
                website_analysis = WebsiteAnalysis.objects.create(
                    time_analysis=self,
                    domain=domain,
                    example_url=domain_example_urls.get(domain, ""),
                    correlation_coefficient=correlation_data["correlation"],
                    days_visited=correlation_data["days_visited"],
                    days_not_visited=correlation_data["days_not_visited"],
                    avg_sentiment_when_visited=correlation_data[
                        "avg_sentiment_visited"
                    ],
                    avg_sentiment_when_not_visited=correlation_data[
                        "avg_sentiment_not_visited"
                    ],
                    total_visits=correlation_data["total_visits"],
                    significance_score=correlation_data["significance_score"],
                )
                website_analyses.append(website_analysis)

        print(
            f"🎉 Website correlation analysis complete! Created {len(website_analyses)} WebsiteAnalysis records"
        )

        # Show top correlations
        if website_analyses:
            print("\n📊 Top positive correlations (websites that make you happier):")
            positive_correlations = sorted(
                [wa for wa in website_analyses if wa.correlation_coefficient > 0],
                key=lambda x: x.correlation_coefficient,
                reverse=True,
            )[:5]
            for wa in positive_correlations:
                print(
                    f"  🟢 {wa.domain}: {wa.correlation_coefficient:.3f} (visited {wa.days_visited} days)"
                )

            print("\n📊 Top negative correlations (websites that make you sadder):")
            negative_correlations = sorted(
                [wa for wa in website_analyses if wa.correlation_coefficient < 0],
                key=lambda x: x.correlation_coefficient,
            )[:5]
            for wa in negative_correlations:
                print(
                    f"  🔴 {wa.domain}: {wa.correlation_coefficient:.3f} (visited {wa.days_visited} days)"
                )

    def _fetch_browser_history(
        self, supabase: Client, daily_website_visits: dict, domain_example_urls: dict
    ):
        """Fetch browser history from Supabase and group by day and domain."""
        try:
            # Convert date range to timestamps for filtering
            start_datetime = f"{self.start_date} 00:00:00"
            end_datetime = f"{self.end_date} 23:59:59"

            print(
                f"    🌐 Querying browser history from {start_datetime} to {end_datetime}"
            )

            # Fetch browser history with pagination
            all_visits = []
            batch_size = 1000
            offset = 0

            while True:
                response = (
                    supabase.table("browser_history")
                    .select("url, timestamp, visit_count")
                    .gte("timestamp", start_datetime)
                    .lte("timestamp", end_datetime)
                    .range(offset, offset + batch_size - 1)
                    .execute()
                )

                if not response.data:
                    break

                all_visits.extend(response.data)
                offset += batch_size

                print(
                    f"      Fetched batch {offset // batch_size}: {len(response.data)} visits (total: {len(all_visits)})"
                )

                if len(response.data) < batch_size:
                    break  # No more data

            print(
                f"    🌐 Found {len(all_visits)} browser history records in date range"
            )

            # Group visits by date and extract domains
            for visit in all_visits:
                if visit.get("url") and visit.get("timestamp"):
                    try:
                        # Parse timestamp
                        parsed_date = parse_date(visit["timestamp"]).date()

                        if self.start_date <= parsed_date <= self.end_date:
                            # Extract domain from URL
                            domain = self._extract_domain(visit["url"])
                            if domain:
                                date_str = parsed_date.isoformat()
                                daily_website_visits[date_str].add(domain)

                                # Store example URL for this domain (keep first occurrence)
                                if domain not in domain_example_urls:
                                    domain_example_urls[domain] = visit["url"]

                    except Exception as e:
                        logger.warning(
                            f"Error parsing browser history timestamp '{visit.get('timestamp')}': {e}"
                        )

        except Exception as e:
            print(f"    ❌ Error fetching browser history: {e}")
            logger.error(f"Error fetching browser history: {e}")

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL, removing www. prefix."""
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()

            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]

            return domain
        except Exception as e:
            logger.warning(f"Error extracting domain from URL '{url}': {e}")
            return ""

    def _calculate_domain_correlation(
        self, domain: str, days_with_sentiment, daily_website_visits: dict
    ):
        """Calculate correlation between domain visits and sentiment scores."""
        try:
            # Prepare data for correlation calculation
            sentiment_scores = []
            domain_presence = []  # 1 if domain visited, 0 if not

            days_visited = 0
            days_not_visited = 0
            sentiment_when_visited = []
            sentiment_when_not_visited = []
            total_visits = 0

            for day in days_with_sentiment:
                date_str = day.date.isoformat()
                sentiment_scores.append(day.sentiment)

                # Check if domain was visited on this day
                domains_visited = daily_website_visits.get(date_str, set())
                if domain in domains_visited:
                    domain_presence.append(1)
                    days_visited += 1
                    sentiment_when_visited.append(day.sentiment)
                    total_visits += (
                        1  # Simplified - could count actual visits if needed
                    )
                else:
                    domain_presence.append(0)
                    days_not_visited += 1
                    sentiment_when_not_visited.append(day.sentiment)

            # Need at least some visits to calculate meaningful correlation
            if days_visited < 2 or days_not_visited < 2 or total_visits < 3:
                print(
                    f"    ⚠️  Skipping {domain}: insufficient data (visited: {days_visited}, not visited: {days_not_visited}, total visits: {total_visits})"
                )
                return None

            # Calculate Pearson correlation coefficient
            correlation = self._calculate_pearson_correlation(
                sentiment_scores, domain_presence
            )

            # Calculate significance score (simple metric based on sample size and correlation strength)
            significance_score = (
                abs(correlation) * min(days_visited, days_not_visited) / 10.0
            )

            return {
                "correlation": correlation,
                "days_visited": days_visited,
                "days_not_visited": days_not_visited,
                "avg_sentiment_visited": sum(sentiment_when_visited)
                / len(sentiment_when_visited)
                if sentiment_when_visited
                else 0,
                "avg_sentiment_not_visited": sum(sentiment_when_not_visited)
                / len(sentiment_when_not_visited)
                if sentiment_when_not_visited
                else 0,
                "total_visits": total_visits,
                "significance_score": significance_score,
            }

        except Exception as e:
            logger.error(f"Error calculating correlation for domain {domain}: {e}")
            return None

    def _calculate_pearson_correlation(self, x: list, y: list) -> float:
        """Calculate Pearson correlation coefficient between two lists."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_x_sq = sum(xi * xi for xi in x)
        sum_y_sq = sum(yi * yi for yi in y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))

        numerator = n * sum_xy - sum_x * sum_y
        denominator = math.sqrt(
            (n * sum_x_sq - sum_x * sum_x) * (n * sum_y_sq - sum_y * sum_y)
        )

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def _analyze_person_correlations(self, daily_messages: dict):
        """
        Third pass: Analyze correlation between interacting with specific people and daily sentiment scores.
        """
        print("🔍 Analyzing person interaction data...")

        # Clear existing PersonAnalysis records for this TimeAnalysis
        existing_person_count = PersonAnalysis.objects.filter(
            time_analysis=self
        ).count()
        if existing_person_count > 0:
            print(
                f"🗑️  Clearing {existing_person_count} existing PersonAnalysis records..."
            )
            PersonAnalysis.objects.filter(time_analysis=self).delete()
            print("✅ Existing PersonAnalysis records cleared")

        # Extract person interactions from the daily_messages that were already fetched
        daily_person_interactions = defaultdict(set)  # date_str -> set of contact names
        self._extract_person_interactions(daily_messages, daily_person_interactions)

        # Get all days with sentiment scores
        days_with_sentiment = Day.objects.filter(
            time_analysis=self, sentiment__isnull=False
        ).order_by("date")
        if not days_with_sentiment.exists():
            print(
                "❌ No days with sentiment scores found for person correlation analysis"
            )
            return

        print(f"📊 Found {days_with_sentiment.count()} days with sentiment scores")

        # Collect all unique contacts
        all_contacts = set()
        for contacts in daily_person_interactions.values():
            all_contacts.update(contacts)

        print(f"👥 Found {len(all_contacts)} unique contacts")

        if not all_contacts:
            print("❌ No contact interaction data found for correlation analysis")
            return

        # Calculate correlations for each contact
        person_analyses = []
        for contact in all_contacts:
            print(f"  📈 Analyzing correlation for {contact}...")
            correlation_data = self._calculate_person_correlation(
                contact, days_with_sentiment, daily_person_interactions
            )

            if correlation_data:
                person_analysis = PersonAnalysis.objects.create(
                    time_analysis=self,
                    contact_name=contact,
                    correlation_coefficient=correlation_data["correlation"],
                    days_interacted=correlation_data["days_interacted"],
                    days_not_interacted=correlation_data["days_not_interacted"],
                    avg_sentiment_when_interacted=correlation_data[
                        "avg_sentiment_interacted"
                    ],
                    avg_sentiment_when_not_interacted=correlation_data[
                        "avg_sentiment_not_interacted"
                    ],
                    total_messages=correlation_data["total_messages"],
                    significance_score=correlation_data["significance_score"],
                )
                person_analyses.append(person_analysis)

        print(
            f"🎉 Person correlation analysis complete! Created {len(person_analyses)} PersonAnalysis records"
        )

        # Show top correlations
        if person_analyses:
            print("\n📊 Top positive correlations (people who make you happier):")
            positive_correlations = sorted(
                [pa for pa in person_analyses if pa.correlation_coefficient > 0],
                key=lambda x: x.correlation_coefficient,
                reverse=True,
            )[:5]
            for pa in positive_correlations:
                print(
                    f"  🟢 {pa.contact_name}: {pa.correlation_coefficient:.3f} (interacted {pa.days_interacted} days)"
                )

            print("\n📊 Top negative correlations (people who make you sadder):")
            negative_correlations = sorted(
                [pa for pa in person_analyses if pa.correlation_coefficient < 0],
                key=lambda x: x.correlation_coefficient,
            )[:5]
            for pa in negative_correlations:
                print(
                    f"  🔴 {pa.contact_name}: {pa.correlation_coefficient:.3f} (interacted {pa.days_interacted} days)"
                )

    def _extract_person_interactions(
        self, daily_messages: dict, daily_person_interactions: dict
    ):
        """Extract person interactions from the daily messages that were already fetched."""
        print("    👥 Extracting person interactions from message data...")

        for date_str, message_list in daily_messages.items():
            contacts_for_day = set()

            for message in message_list:
                contact = message.get("contact", "").strip()
                if contact and contact != "Unknown" and contact != "":
                    # Normalize contact names
                    contact = self._normalize_contact_name(contact)
                    if contact:
                        contacts_for_day.add(contact)

            if contacts_for_day:
                daily_person_interactions[date_str] = contacts_for_day
                print(f"      {date_str}: {len(contacts_for_day)} unique contacts")

        total_interactions = sum(
            len(contacts) for contacts in daily_person_interactions.values()
        )
        print(
            f"    👥 Extracted {total_interactions} person interactions across {len(daily_person_interactions)} days"
        )

    def _normalize_contact_name(self, contact: str) -> str:
        """Normalize contact names for consistent matching."""
        if not contact or contact.strip() == "":
            return ""

        contact = contact.strip()

        # Skip generic/system contacts
        skip_contacts = {
            "unknown",
            "me",
            "",
            "system",
            "group",
            "chat",
            "whatsapp",
            "imessage",
            "sms",
            "mms",
        }

        if contact.lower() in skip_contacts:
            return ""

        # For WhatsApp group names, extract meaningful part
        if " group" in contact.lower() or "group " in contact.lower():
            # Keep group names but clean them up
            contact = contact.replace(" Group", "").replace(" group", "")

        return contact

    def _calculate_person_correlation(
        self, contact: str, days_with_sentiment, daily_person_interactions: dict
    ):
        """Calculate correlation between interacting with a person and sentiment scores."""
        try:
            # Prepare data for correlation calculation
            sentiment_scores = []
            person_interaction = []  # 1 if interacted with person, 0 if not

            days_interacted = 0
            days_not_interacted = 0
            sentiment_when_interacted = []
            sentiment_when_not_interacted = []
            total_messages = 0

            for day in days_with_sentiment:
                date_str = day.date.isoformat()
                sentiment_scores.append(day.sentiment)

                # Check if we interacted with this person on this day
                contacts_for_day = daily_person_interactions.get(date_str, set())
                if contact in contacts_for_day:
                    person_interaction.append(1)
                    days_interacted += 1
                    sentiment_when_interacted.append(day.sentiment)
                    total_messages += (
                        1  # Simplified - could count actual messages if needed
                    )
                else:
                    person_interaction.append(0)
                    days_not_interacted += 1
                    sentiment_when_not_interacted.append(day.sentiment)

            # Need at least some interactions to calculate meaningful correlation
            if days_interacted < 2 or days_not_interacted < 2:
                print(
                    f"    ⚠️  Skipping {contact}: insufficient data (interacted: {days_interacted}, not interacted: {days_not_interacted})"
                )
                return None

            # Calculate Pearson correlation coefficient
            correlation = self._calculate_pearson_correlation(
                sentiment_scores, person_interaction
            )

            # Calculate significance score (simple metric based on sample size and correlation strength)
            significance_score = (
                abs(correlation) * min(days_interacted, days_not_interacted) / 10.0
            )

            return {
                "correlation": correlation,
                "days_interacted": days_interacted,
                "days_not_interacted": days_not_interacted,
                "avg_sentiment_interacted": sum(sentiment_when_interacted)
                / len(sentiment_when_interacted)
                if sentiment_when_interacted
                else 0,
                "avg_sentiment_not_interacted": sum(sentiment_when_not_interacted)
                / len(sentiment_when_not_interacted)
                if sentiment_when_not_interacted
                else 0,
                "total_messages": total_messages,
                "significance_score": significance_score,
            }

        except Exception as e:
            logger.error(f"Error calculating correlation for contact {contact}: {e}")
            return None

    def _analyze_place_correlations(self):
        """
        Fourth pass: Analyze correlation between being at specific places and daily sentiment scores.
        """
        print("🔍 Analyzing place correlation data...")

        # Clear existing PlaceAnalysis records for this TimeAnalysis
        existing_place_count = PlaceAnalysis.objects.filter(time_analysis=self).count()
        if existing_place_count > 0:
            print(
                f"🗑️  Clearing {existing_place_count} existing PlaceAnalysis records..."
            )
            PlaceAnalysis.objects.filter(time_analysis=self).delete()
            print("✅ Existing PlaceAnalysis records cleared")

        # Get all days with sentiment scores
        days_with_sentiment = Day.objects.filter(
            time_analysis=self, sentiment__isnull=False
        ).order_by("date")
        if not days_with_sentiment.exists():
            print(
                "❌ No days with sentiment scores found for place correlation analysis"
            )
            return

        print(f"📊 Found {days_with_sentiment.count()} days with sentiment scores")

        # Get all locations for this time analysis
        locations = Location.objects.filter(time_analysis=self)
        if not locations.exists():
            print("❌ No location data found for correlation analysis")
            return

        print(f"📍 Found {locations.count()} locations")

        # Extract daily place presence from location data
        daily_place_presence = self._extract_daily_place_presence(
            locations, days_with_sentiment
        )

        # Collect all unique location IDs
        all_location_ids = set()
        for location_ids in daily_place_presence.values():
            all_location_ids.update(location_ids)

        print(f"📍 Found {len(all_location_ids)} unique locations with presence data")

        if not all_location_ids:
            print("❌ No location presence data found for correlation analysis")
            return

        # Calculate correlations for each location
        place_analyses = []
        for location_id in all_location_ids:
            location = locations.get(id=location_id)
            print(
                f"  📈 Analyzing correlation for {location.name or f'Location {location_id}'}..."
            )
            correlation_data = self._calculate_place_correlation(
                location, days_with_sentiment, daily_place_presence
            )

            if correlation_data:
                place_analysis = PlaceAnalysis.objects.create(
                    time_analysis=self,
                    location=location,
                    correlation_coefficient=correlation_data["correlation"],
                    days_present=correlation_data["days_present"],
                    days_not_present=correlation_data["days_not_present"],
                    avg_sentiment_when_present=correlation_data[
                        "avg_sentiment_present"
                    ],
                    avg_sentiment_when_not_present=correlation_data[
                        "avg_sentiment_not_present"
                    ],
                    total_visits=correlation_data["total_visits"],
                    significance_score=correlation_data["significance_score"],
                )
                place_analyses.append(place_analysis)

        print(
            f"🎉 Place correlation analysis complete! Created {len(place_analyses)} PlaceAnalysis records"
        )

        # Show top correlations
        if place_analyses:
            print("\n📊 Top positive correlations (places that make you happier):")
            positive_correlations = sorted(
                [pa for pa in place_analyses if pa.correlation_coefficient > 0],
                key=lambda x: x.correlation_coefficient,
                reverse=True,
            )[:5]
            for pa in positive_correlations:
                location_name = pa.location.name or f"Location {pa.location.id}"
                print(
                    f"  🟢 {location_name}: {pa.correlation_coefficient:.3f} (present {pa.days_present} days)"
                )

            print("\n📊 Top negative correlations (places that make you sadder):")
            negative_correlations = sorted(
                [pa for pa in place_analyses if pa.correlation_coefficient < 0],
                key=lambda x: x.correlation_coefficient,
            )[:5]
            for pa in negative_correlations:
                location_name = pa.location.name or f"Location {pa.location.id}"
                print(
                    f"  🔴 {location_name}: {pa.correlation_coefficient:.3f} (present {pa.days_present} days)"
                )

    def _extract_daily_place_presence(self, locations, days_with_sentiment):
        """Extract daily place presence from location data."""
        print("    📍 Extracting daily place presence from location data...")

        daily_place_presence = defaultdict(set)  # date_str -> set of location_ids

        for location in locations:
            # For each location, determine which days the user was present
            # We'll use a simple approach: if the location has visits during the analysis period,
            # distribute them across the days proportionally

            if not location.first_visit or not location.last_visit:
                continue

            # Convert to dates
            first_date = location.first_visit.date()
            last_date = location.last_visit.date()

            # For simplicity, we'll assume the user was at this location on days
            # proportional to their visit count and total time
            # This is a rough approximation - in reality, we'd need more detailed GPS data

            # Calculate average days per visit (rough estimate)
            total_days_in_period = (last_date - first_date).days + 1
            if total_days_in_period <= 0:
                total_days_in_period = 1

            # If they spent significant time at this location, mark presence
            # Use a threshold based on total time and visit count
            time_threshold = 60  # 60 minutes minimum to consider "present"

            if location.total_time_minutes >= time_threshold:
                # For locations with significant time, mark presence for multiple days
                # based on visit count and time distribution
                days_to_mark = min(location.visit_count, total_days_in_period)

                # Distribute days evenly across the period
                if days_to_mark > 0:
                    for i in range(days_to_mark):
                        # Calculate which day to mark (spread evenly)
                        day_offset = int(i * total_days_in_period / days_to_mark)
                        target_date = first_date + timedelta(days=day_offset)

                        # Only mark if this date is within our analysis period
                        if self.start_date <= target_date <= self.end_date:
                            date_str = target_date.isoformat()
                            daily_place_presence[date_str].add(location.pk)

        total_presence_records = sum(
            len(location_ids) for location_ids in daily_place_presence.values()
        )
        print(
            f"    📍 Extracted {total_presence_records} place presence records across {len(daily_place_presence)} days"
        )

        return daily_place_presence

    def _calculate_place_correlation(
        self, location, days_with_sentiment, daily_place_presence: dict
    ):
        """Calculate correlation between being at a specific place and sentiment scores."""
        try:
            # Prepare data for correlation calculation
            sentiment_scores = []
            place_presence = []  # 1 if present at place, 0 if not

            days_present = 0
            days_not_present = 0
            sentiment_when_present = []
            sentiment_when_not_present = []
            total_visits = location.visit_count

            for day in days_with_sentiment:
                date_str = day.date.isoformat()
                sentiment_scores.append(day.sentiment)

                # Check if we were at this place on this day
                location_ids_for_day = daily_place_presence.get(date_str, set())
                if location.pk in location_ids_for_day:
                    place_presence.append(1)
                    days_present += 1
                    sentiment_when_present.append(day.sentiment)
                else:
                    place_presence.append(0)
                    days_not_present += 1
                    sentiment_when_not_present.append(day.sentiment)

            # Need at least some presence data to calculate meaningful correlation
            if days_present < 2 or days_not_present < 2:
                location_name = location.name or f"Location {location.pk}"
                print(
                    f"    ⚠️  Skipping {location_name}: insufficient data (present: {days_present}, not present: {days_not_present})"
                )
                return None

            # Calculate Pearson correlation coefficient
            correlation = self._calculate_pearson_correlation(
                sentiment_scores, place_presence
            )

            # Calculate significance score (simple metric based on sample size and correlation strength)
            significance_score = (
                abs(correlation) * min(days_present, days_not_present) / 10.0
            )

            return {
                "correlation": correlation,
                "days_present": days_present,
                "days_not_present": days_not_present,
                "avg_sentiment_present": sum(sentiment_when_present)
                / len(sentiment_when_present)
                if sentiment_when_present
                else 0,
                "avg_sentiment_not_present": sum(sentiment_when_not_present)
                / len(sentiment_when_not_present)
                if sentiment_when_not_present
                else 0,
                "total_visits": total_visits,
                "significance_score": significance_score,
            }

        except Exception as e:
            location_name = location.name or f"Location {location.pk}"
            logger.error(
                f"Error calculating correlation for location {location_name}: {e}"
            )
            return None


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


class Location(models.Model):
    """Model for storing clustered locations from GPS data."""

    time_analysis = models.ForeignKey(
        TimeAnalysis, on_delete=models.CASCADE, related_name="locations"
    )
    name = models.CharField(
        max_length=200, blank=True, help_text="Name or description of this location"
    )
    center_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        help_text="Center latitude of clustered GPS points",
    )
    center_longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        help_text="Center longitude of clustered GPS points",
    )
    visit_count = models.PositiveIntegerField(
        default=0, help_text="Number of GPS points in this cluster"
    )
    total_time_minutes = models.PositiveIntegerField(
        default=0, help_text="Total time spent at this location in minutes"
    )
    first_visit = models.DateTimeField(
        null=True, blank=True, help_text="First recorded visit to this location"
    )
    last_visit = models.DateTimeField(
        null=True, blank=True, help_text="Last recorded visit to this location"
    )
    address = models.TextField(
        null=True, blank=True, help_text="Address of this location"
    )
    activity_types = models.JSONField(
        default=dict, help_text="Activity types and their counts at this location"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Location"
        verbose_name_plural = "Locations"
        ordering = ["-visit_count"]

    def __str__(self):
        name = self.name or f"{self.center_latitude}, {self.center_longitude}"
        return f"{name} ({self.visit_count} visits, {self.total_time_minutes}min)"

    @property
    def coordinates(self):
        """Return center coordinates as a tuple."""
        return (float(self.center_latitude), float(self.center_longitude))

    @property
    def average_time_per_visit(self):
        """Return average time per visit in minutes."""
        if self.visit_count > 0:
            return self.total_time_minutes / self.visit_count
        return 0


class WebsiteAnalysis(models.Model):
    """Model for storing website-happiness correlations."""

    time_analysis = models.ForeignKey(
        TimeAnalysis, on_delete=models.CASCADE, related_name="website_analyses"
    )
    domain = models.CharField(max_length=200, help_text="Website domain")
    example_url = models.URLField(
        max_length=500, blank=True, help_text="Example URL from this domain"
    )
    correlation_coefficient = models.FloatField(
        help_text="Correlation coefficient between website visits and sentiment scores"
    )
    days_visited = models.PositiveIntegerField(
        help_text="Number of days the website was visited"
    )
    days_not_visited = models.PositiveIntegerField(
        help_text="Number of days the website was not visited"
    )
    avg_sentiment_when_visited = models.FloatField(
        help_text="Average sentiment score when the website was visited"
    )
    avg_sentiment_when_not_visited = models.FloatField(
        help_text="Average sentiment score when the website was not visited"
    )
    total_visits = models.PositiveIntegerField(
        help_text="Total number of visits to the website"
    )
    significance_score = models.FloatField(
        help_text="Significance score of the correlation"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Website Analysis"
        verbose_name_plural = "Website Analyses"
        ordering = ["-correlation_coefficient"]

    def __str__(self):
        return f"{self.domain} - Correlation: {self.correlation_coefficient:.3f} (visited {self.days_visited} days)"


class PersonAnalysis(models.Model):
    """Model for storing person-happiness correlations."""

    time_analysis = models.ForeignKey(
        TimeAnalysis, on_delete=models.CASCADE, related_name="person_analyses"
    )
    contact_name = models.CharField(max_length=200, help_text="Contact or person name")
    correlation_coefficient = models.FloatField(
        help_text="Correlation coefficient between interactions with this person and sentiment scores"
    )
    days_interacted = models.PositiveIntegerField(
        help_text="Number of days you interacted with this person"
    )
    days_not_interacted = models.PositiveIntegerField(
        help_text="Number of days you did not interact with this person"
    )
    avg_sentiment_when_interacted = models.FloatField(
        help_text="Average sentiment score when you interacted with this person"
    )
    avg_sentiment_when_not_interacted = models.FloatField(
        help_text="Average sentiment score when you did not interact with this person"
    )
    total_messages = models.PositiveIntegerField(
        help_text="Total number of messages exchanged with this person"
    )
    significance_score = models.FloatField(
        help_text="Significance score of the correlation"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Person Analysis"
        verbose_name_plural = "Person Analyses"
        ordering = ["-correlation_coefficient"]

    def __str__(self):
        return f"{self.contact_name} - Correlation: {self.correlation_coefficient:.3f} (interacted {self.days_interacted} days)"


class PlaceAnalysis(models.Model):
    """Model for storing place-happiness correlations."""

    time_analysis = models.ForeignKey(
        TimeAnalysis, on_delete=models.CASCADE, related_name="place_analyses"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        help_text="The location this analysis refers to",
    )
    correlation_coefficient = models.FloatField(
        help_text="Correlation coefficient between being at this place and sentiment scores"
    )
    days_present = models.PositiveIntegerField(
        help_text="Number of days you were present at this place"
    )
    days_not_present = models.PositiveIntegerField(
        help_text="Number of days you were not present at this place"
    )
    avg_sentiment_when_present = models.FloatField(
        help_text="Average sentiment score when you were at this place"
    )
    avg_sentiment_when_not_present = models.FloatField(
        help_text="Average sentiment score when you were not at this place"
    )
    total_visits = models.PositiveIntegerField(
        help_text="Total number of visits to this place"
    )
    significance_score = models.FloatField(
        help_text="Significance score of the correlation"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Place Analysis"
        verbose_name_plural = "Place Analyses"
        ordering = ["-correlation_coefficient"]

    def __str__(self):
        location_name = self.location.name or f"Location {self.location.pk}"
        return f"{location_name} - Correlation: {self.correlation_coefficient:.3f} (present {self.days_present} days)"
