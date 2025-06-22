#!/usr/bin/env python3
"""
Verify iMessage and WhatsApp data in Supabase database
"""

import os

from dateutil.parser import parse as parse_date
from supabase import Client, create_client


def verify_messages():
    """Verify iMessage and WhatsApp data in Supabase and show date distribution."""

    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_key:
        print("❌ SUPABASE_URL and SUPABASE_ANON_KEY environment variables must be set")
        return

    print("🔗 Connecting to Supabase...")
    supabase: Client = create_client(supabase_url, supabase_key)

    try:
        # Check iMessages
        print("\n📱 === iMESSAGE ANALYSIS ===")

        # Get total iMessage count
        total_response = supabase.table("imessages").select("id").limit(1).execute()
        total_count = len(total_response.data) if total_response.data else 0
        print(f"📊 Total iMessages in database: {total_count:,}")

        # Get user messages count
        user_response = (
            supabase.table("imessages")
            .select("id")
            .eq("is_from_me", True)
            .limit(5000)
            .execute()
        )
        user_count = len(user_response.data) if user_response.data else 0
        print(f"📊 User iMessages (is_from_me=true): {user_count:,}")

        if user_count > 0:
            # Sample user messages with dates
            sample_response = (
                supabase.table("imessages")
                .select("service, contact, is_from_me, text")
                .eq("is_from_me", True)
                .limit(5)
                .execute()
            )

            print("\n🔍 Sample user iMessages:")
            for i, message in enumerate(sample_response.data[:3]):
                text_preview = (
                    message.get("text", "")[:50] + "..."
                    if len(message.get("text", "")) > 50
                    else message.get("text", "")
                )
                print(f"  Message {i + 1}:")
                print(f"    service: '{message.get('service')}'")
                print(f"    contact: '{message.get('contact')}'")
                print(f"    is_from_me: {message.get('is_from_me')}")
                print(f"    text: '{text_preview}'")
                print()

            # Check the specific problematic message
            print("\n🔍 Checking messages from +16172164332:")
            problem_contact_response = (
                supabase.table("imessages")
                .select("service, contact, is_from_me, text")
                .eq("contact", "+16172164332")
                .limit(10)
                .execute()
            )

            for i, message in enumerate(problem_contact_response.data):
                text_preview = (
                    message.get("text", "")[:80] + "..."
                    if len(message.get("text", "")) > 80
                    else message.get("text", "")
                )
                is_from_me = message.get("is_from_me")
                print(f"  Message {i + 1}: is_from_me={is_from_me}")
                print(f"    text: '{text_preview}'")
                print()

            # Double-check: get all messages with that specific text
            print("\n🔍 Searching for the specific message text:")
            specific_message_response = (
                supabase.table("imessages")
                .select("service, contact, is_from_me, text")
                .ilike("text", "%I'm totally stumped%")
                .execute()
            )

            for i, message in enumerate(specific_message_response.data):
                print(f"  Found message {i + 1}:")
                print(f"    contact: '{message.get('contact')}'")
                print(f"    is_from_me: {message.get('is_from_me')}")
                print(f"    text: '{message.get('text')}'")
                print()

        # Check WhatsApp messages
        print("\n💬 === WHATSAPP ANALYSIS ===")

        # Get total WhatsApp count
        wa_total_response = (
            supabase.table("whatsapp_messages").select("id").limit(1).execute()
        )
        wa_total_count = len(wa_total_response.data) if wa_total_response.data else 0
        print(f"📊 Total WhatsApp messages in database: {wa_total_count:,}")

        # Get user WhatsApp messages count
        wa_user_response = (
            supabase.table("whatsapp_messages")
            .select("id")
            .eq("from_name", "Me")
            .limit(5000)
            .execute()
        )
        wa_user_count = len(wa_user_response.data) if wa_user_response.data else 0
        print(f"📊 User WhatsApp messages (from_name='Me'): {wa_user_count:,}")

        if wa_user_count > 0:
            # Sample user WhatsApp messages
            wa_sample_response = (
                supabase.table("whatsapp_messages")
                .select("timestamp, from_name, chat_name, text")
                .eq("from_name", "Me")
                .limit(5)
                .execute()
            )

            print("\n🔍 Sample user WhatsApp messages:")
            for i, message in enumerate(wa_sample_response.data[:3]):
                text_preview = (
                    message.get("text", "")[:50] + "..."
                    if len(message.get("text", "")) > 50
                    else message.get("text", "")
                )
                print(f"  Message {i + 1}:")
                print(f"    timestamp: '{message.get('timestamp')}'")
                print(f"    from_name: '{message.get('from_name')}'")
                print(f"    chat_name: '{message.get('chat_name')}'")
                print(f"    text: '{text_preview}'")
                print()

        # Analyze date ranges for user messages
        print("\n📅 === DATE ANALYSIS ===")

        # Get recent user messages from both sources
        recent_imessages = (
            supabase.table("imessages")
            .select("service")
            .eq("is_from_me", True)
            .order("service", desc=True)
            .limit(100)
            .execute()
        )
        recent_whatsapp = (
            supabase.table("whatsapp_messages")
            .select("timestamp")
            .eq("from_name", "Me")
            .order("timestamp", desc=True)
            .limit(100)
            .execute()
        )

        # Parse dates
        imessage_dates = []
        for msg in recent_imessages.data:
            try:
                date = parse_date(msg["service"]).date()
                imessage_dates.append(date.isoformat())
            except:
                pass

        whatsapp_dates = []
        for msg in recent_whatsapp.data:
            try:
                date = parse_date(msg["timestamp"]).date()
                whatsapp_dates.append(date.isoformat())
            except:
                pass

        if imessage_dates:
            print("📱 Recent iMessage dates (user messages):")
            unique_dates = sorted(set(imessage_dates))[-10:]  # Last 10 unique dates
            for date in unique_dates:
                count = imessage_dates.count(date)
                print(f"  {date}: {count} messages")

        if whatsapp_dates:
            print("\n💬 Recent WhatsApp dates (user messages):")
            unique_dates = sorted(set(whatsapp_dates))[-10:]  # Last 10 unique dates
            for date in unique_dates:
                count = whatsapp_dates.count(date)
                print(f"  {date}: {count} messages")

        # Suggest analysis date range
        all_dates = imessage_dates + whatsapp_dates
        if all_dates:
            unique_dates = sorted(set(all_dates))
            if len(unique_dates) >= 30:
                suggested_start = unique_dates[-30]
                suggested_end = unique_dates[-1]
            else:
                suggested_start = unique_dates[0]
                suggested_end = unique_dates[-1]

            total_messages = len(all_dates)
            print("\n💡 SUGGESTED ANALYSIS RANGE:")
            print(f"  From: {suggested_start}")
            print(f"  To: {suggested_end}")
            print(f"  Total user messages in recent data: {total_messages:,}")
            print(f"  Days with data: {len(unique_dates)}")

    except Exception as e:
        print(f"❌ Error querying Supabase: {e}")


if __name__ == "__main__":
    verify_messages()
