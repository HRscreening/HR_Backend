import os
from supabase import create_client, Client
from configs.env_config import SUPABASE_URL, SUPABASE_API_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)