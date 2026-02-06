import os
from dotenv import load_dotenv

load_dotenv()

# Development or Production Environment
ENVIRONMENT = os.environ.get("ENVIRONMENT", "Development")



# postgress database url
DATABASE_URL = os.environ.get("DATABASE_URL")  or "postgresql+asyncpg://postgres:keshav123@localhost:5432/CareerAI"


# redis configuration
# redis_host = os.environ.get('REDIS_HOST', 'localhost')
# redis_port = int(os.environ.get('REDIS_PORT', 6379))  # cast to int
# redis_username = os.environ.get('REDIS_USERNAME', 'default')
# redis_password = os.environ.get('REDIS_PASSWORD', '')

# EMAIL Configuration
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "your_email@gmail.com")
SENDER_MAIL_PASSWORD = os.getenv("SENDER_MAIL_PASSWORD", "your_app_password")  # Use Gmail App Password

# JWT Configuration
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key")
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
EXPIRATION_MINUTES = int(os.environ.get("EXPIRATION_MINUTES", 300))



# LLM API Keys
OPENAI_API_KEY =  os.environ["OPENAI_API_KEY"]=os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.environ["GOOGLE_API_KEY"]=os.getenv("GOOGLE_API_KEY")


# Langmith tracking
LANGHAIN_TRACKING_ENABLED = os.getenv("LANGHAIN_TRACKING_ENABLED", "true").lower() == "true"
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")


# Supabase Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "your-supabase-url")
SUPABASE_API_KEY = os.environ.get("SUPABASE_API_KEY", "your-supabase-api-key")
SUPABASE_PUBLIC_URL = os.environ.get("SUPABASE_PUBLIC_URL", "your-supabase-file-initializer")


BASE_UPLOAD_DIR = os.environ.get("BASE_UPLOAD_DIR", "/data/uploads")

REDIS_HOST = os.environ.get('REDIS_HOST', None)
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))  # cast to int
REDIS_USERNAME = os.environ.get('REDIS_USERNAME', None)
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
DEFAULT_TIMEOUT_REDIS_WORKER = int(os.environ.get("DEFAULT_TIMEOUT_REDIS_WORKER", 600))  # default timeout for redis worker in seconds