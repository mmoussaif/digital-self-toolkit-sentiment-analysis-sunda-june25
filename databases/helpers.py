import json
import os
from datetime import datetime

# Supabase imports with availability check
try:
    from supabase import Client, create_client

    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None
    create_client = None


def is_supabase_available():
    """Check if Supabase is available."""
    return SUPABASE_AVAILABLE


def get_supabase_client(table_name: str | None = None):
    """Get Supabase client if environment variables are set.

    Args:
        table_name: Optional table name to test connection with
    """
    if not SUPABASE_AVAILABLE:
        print("⚠️ Supabase not available - install with: pip install supabase")
        return None

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")

    if not url or not key:
        print(
            "⚠️ Supabase environment variables not set (SUPABASE_URL, SUPABASE_ANON_KEY)"
        )
        return None

    if create_client is None:
        print("⚠️ Supabase create_client not available")
        return None

    client = create_client(url, key)

    # Check if we need to authenticate (optional table test)
    if table_name:
        test_result = client.table(table_name).select("id").limit(1).execute()
        print(
            f"✅ Supabase connection successful (found {len(test_result.data)} existing records in {table_name})"
        )
    else:
        print("✅ Supabase client created successfully")

    return client


def save_data_to_json(
    data: list,
    filename_prefix: str = "data",
    data_dir: str = "data",
    file_prefix: str = "",
):
    """Save data to JSON file with timestamp.

    Args:
        data: List of data to save
        filename_prefix: Prefix for the filename
        data_dir: Directory to save the file in
        file_prefix: Additional prefix for the filename (e.g., "failed_")
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{data_dir}/{file_prefix}{filename_prefix}_{len(data)}_{timestamp}.json"

    # Create data directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"📁 {len(data)} records saved to {filename}")
    return filename


def print_supabase_error_help(error_details: str, table_name: str | None = None):
    """Print helpful error messages for common Supabase errors."""
    print(f"❌ Error with Supabase: {error_details}")

    # Provide specific troubleshooting based on error
    if "405" in error_details or "Method Not Allowed" in error_details:
        print("💡 This usually means:")
        print("   - Row Level Security (RLS) is enabled and requires authentication")
        print("   - API key doesn't have INSERT permissions")
    elif "404" in error_details or "not found" in error_details:
        if table_name:
            print(
                f"💡 Table '{table_name}' not found. Run the database setup script first."
            )
        else:
            print("💡 Table not found. Run the database setup script first.")
    elif "401" in error_details or "unauthorized" in error_details:
        print("💡 Authentication required.")
    elif "PGRST204" in error_details:
        print("💡 Column doesn't exist in database table.")
