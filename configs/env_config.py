import os

# Development or Production Environment
ENVIRONMENT = os.environ.get("ENVIRONMENT", "Development")

if ENVIRONMENT == "Development":
    from dotenv import load_dotenv
    load_dotenv()

# postgress database url
DATABASE_URL = os.environ.get("DATABASE_URL")  or "postgresql+asyncpg://postgres:keshav123@localhost:5432/CareerAI"


# redis configuration
# redis_host = os.environ.get('REDIS_HOST', 'localhost')
# redis_port = int(os.environ.get('REDIS_PORT', 6379))  # cast to int
# redis_username = os.environ.get('REDIS_USERNAME', 'default')
# redis_password = os.environ.get('REDIS_PASSWORD', '')

# EMAIL Configuration
COMPANY_EMAIL = os.getenv("COMPANY_EMAIL", "your_email@gmail.com")

SENDER_EMAIL = os.getenv("SENDER_EMAIL", "your_email@gmail.com")
SENDER_MAIL_PASSWORD = os.getenv("SENDER_MAIL_PASSWORD", "your_app_password")  # Use Gmail App Password
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

# JWT Configuration
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key")
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
EXPIRATION_MINUTES = int(os.environ.get("EXPIRATION_MINUTES", 300))



# LLM API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "")


# Langmith tracking
LANGHAIN_TRACKING_ENABLED = os.getenv("LANGHAIN_TRACKING_ENABLED", "true").lower() == "true"
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")


# Supabase Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "your-supabase-url")
SUPABASE_API_KEY = os.environ.get("SUPABASE_API_KEY", "your-supabase-api-key")
SUPABASE_PUBLIC_URL = os.environ.get("SUPABASE_PUBLIC_URL", "your-supabase-file-initializer")


BASE_UPLOAD_DIR = os.environ.get("BASE_UPLOAD_DIR", "/data/uploads")


# TODO:FIX NAMES
REDIS_HOST = os.environ.get('REDIS_HOST', None)
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))  # cast to int
REDIS_USERNAME = os.environ.get('REDIS_USERNAME', None)
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
DEFAULT_TIMEOUT_REDIS_WORKER = int(os.environ.get("DEFAULT_TIMEOUT_REDIS_WORKER", 600))  # default timeout for redis worker in seconds

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")  # Update this to your actual frontend URL



# ------------------------- Calendar API Configuration -------------------------
Calendar_Client_ID = os.getenv("Calendar_Client_ID", "your-google-client-id")
Calendar_Client_Secret = os.getenv("Calendar_Client_Secret", "your-google-client-secret")
Calendar_Redirect_URI = os.getenv("Calendar_Redirect_URI", "http://localhost:8000/api/oauth/google/calendar/callback")
Google_Calendar_Meet_Creation_link = os.getenv("Google_Calendar_Meet_Creation_link", "https://www.googleapis.com/calendar/v3/calendars/primary/events")
Google_Calendar_Access_Token = os.getenv("Google_Calendar_Access_Token", "your-google-calendar-access-token")
Calendar_Refresh_Token = os.getenv("Calendar_Refresh_Token", "your-google-calendar-refresh-token")


# -------------------------- Fireflies Configuration -------------------------
FireFlies_Bot = os.getenv("FireFlies_Bot", "fred@fireflies.ai")
Fireflies_API_Key = os.getenv("Fireflies_API_Key", "your-fireflies-api-key")
FireFlies_GraphQL_Endpoint = os.getenv("FireFlies_GraphQL_Endpoint", "https://api.fireflies.ai/graphql")