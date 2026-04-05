import os
from supabase import create_client, Client
from configs.env_config import SUPABASE_URL, SUPABASE_API_KEY

supabase: Client = None

if SUPABASE_URL and SUPABASE_URL != "your-supabase-url" and SUPABASE_API_KEY and SUPABASE_API_KEY != "your-supabase-api-key":
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)
    except Exception as e:
        print(f"Warning: Failed to initialize Supabase client: {e}")
