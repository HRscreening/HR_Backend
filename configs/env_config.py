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
