# HR Backend - AI-Powered HR Screening Platform

A FastAPI-based backend service for an AI-powered HR screening and candidate management platform. This system helps organizations streamline their recruitment process by managing job postings, candidate applications, resume parsing, and automated screening with AI assistance.

## Features

- **User Management**: Multi-role authentication system (Individual/Organization roles)
- **Organization Management**: Support for multi-tenant organizations
- **Job Management**: Create and manage job postings with customizable rubrics
- **Candidate Management**: Track candidates and their application history
- **Resume Processing**: PDF resume parsing and storage
- **Application Tracking**: Complete application lifecycle management
- **Scoring System**: AI-powered candidate scoring based on customizable rubrics
- **Authentication**: JWT-based authentication with email verification
- **AI Integration**: Support for OpenAI and Google Gemini APIs
- **Database Migrations**: Alembic-based database version control

## Technology Stack

- **Framework**: FastAPI (Python 3.12+)
- **Database**: PostgreSQL with pgvector extension
- **ORM**: SQLAlchemy (Async)
- **Migrations**: Alembic
- **Authentication**: JWT tokens with passlib
- **Resume Parsing**: PDFPlumber
- **API Documentation**: Auto-generated Swagger/OpenAPI docs
- **LLM Integration**: OpenAI and Google Gemini APIs
- **Monitoring**: LangChain tracking (optional)

## Prerequisites

- Python 3.12 or higher
- PostgreSQL database
- pip or uv (Python package manager)
- Virtual environment (recommended)

## Installation

1. **Clone the repository**
```bash
git clone https://github.com/HRscreening/HR_Backend.git
cd HR_Backend
```

2. **Create and activate a virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**

Using pip:
```bash
pip install -r requirements.txt
```

Or using uv:
```bash
uv pip install -e .
```

## Configuration

Create a `.env` file in the root directory with the following variables:

```env
# Environment
ENVIRONMENT=Development  # or Production

# Server Configuration
PORT=8000
HOST=127.0.0.1

# Database
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_DB_PASSWORD@localhost:5432/CareerAI

# JWT Configuration
SECRET_KEY=your-randomly-generated-secret-key  # Generate with: openssl rand -hex 32
ALGORITHM=HS256
EXPIRATION_MINUTES=300

# Email Configuration (for OTP/verification)
SENDER_EMAIL=your_email@gmail.com
SENDER_MAIL_PASSWORD=your_app_password

# AI/LLM API Keys
OPENAI_API_KEY=your_openai_api_key
GOOGLE_API_KEY=your_google_api_key

# LangChain Tracking (optional)
LANGCHAIN_TRACKING_ENABLED=false
LANGCHAIN_API_KEY=your_langchain_api_key
```

## Database Setup

1. **Create PostgreSQL database**
```bash
createdb CareerAI
```

2. **Enable pgvector extension** (if using vector embeddings)
```sql
CREATE EXTENSION vector;
```

3. **Run database migrations**
```bash
alembic upgrade head
```

## Running the Application

### Development Mode

```bash
python server.py
```

Or directly with uvicorn:
```bash
uvicorn main:app --reload --port 8000
```

The API will be available at:
- API: `http://localhost:8000`
- Interactive API docs: `http://localhost:8000/docs`
- Alternative API docs: `http://localhost:8000/redoc`

## Project Structure

```
HR_Backend/
├── alembic/                 # Database migrations
│   ├── versions/           # Migration scripts
│   └── env.py             # Alembic configuration
├── configs/                # Configuration files
│   ├── env_config.py      # Environment variables
│   ├── log_config.py      # Logging configuration
│   └── postgres_db.py     # Database connection
├── models/                 # SQLAlchemy models
│   ├── user_model.py      # User model
│   ├── organization_model.py
│   ├── job_model.py       # Job postings
│   ├── candidate_model.py # Candidate profiles
│   ├── application_model.py
│   ├── resume_model.py    # Resume storage
│   ├── rubric_model.py    # Scoring rubrics
│   ├── score_model.py     # Candidate scores
│   └── enums.py          # Enum definitions
├── routes/                # API routes
│   └── auth_routes.py    # Authentication endpoints
├── schemas/               # Pydantic schemas
│   └── auth_schemas.py   # Request/response models
├── services/             # Business logic
│   ├── auth_services.py  # Authentication services
│   ├── user_services.py  # User management
│   └── errors/          # Custom exceptions
├── utils/                # Utility functions
│   ├── jwt.py           # JWT token handling
│   ├── security.py      # Password hashing
│   ├── extract_pdf.py   # PDF parsing
│   ├── send_otp.py      # Email OTP
│   └── verify_token.py  # Token verification
├── middlewares/         # Middleware components
│   └── verify_user.py   # Authentication middleware
├── main.py             # FastAPI application
├── server.py           # Server entry point
├── requirements.txt    # Python dependencies
└── pyproject.toml      # Project metadata
```

## API Endpoints

### Authentication

#### User Signup
```http
POST /api/auth/signup
Content-Type: application/json

{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "securepassword",
  "role": "INDIVIDUAL"
}
```

### Health Check
```http
GET /
```

More endpoints will be added as the API develops.

## Database Models

- **User**: User accounts with role-based access
- **Organization**: Company/organization profiles
- **Job**: Job postings with status tracking
- **Candidate**: Candidate profiles
- **Application**: Job applications linking candidates to jobs
- **Resume**: Parsed resume data
- **Rubric**: Scoring criteria for jobs
- **Score**: Candidate scores per rubric

## Development

### Creating New Migrations

```bash
alembic revision --autogenerate -m "description of changes"
alembic upgrade head
```

### Running Tests

```bash
pytest  # When tests are added
```

## CORS Configuration

The application allows requests from:
- `http://localhost:5173`
- `http://localhost:5174`

Update the CORS settings in `main.py` for production deployments.

## Security Notes

- Always use strong `SECRET_KEY` in production
- Use environment variables for sensitive data
- Never commit `.env` files to version control
- Use HTTPS in production
- Regularly update dependencies for security patches
- Enable email verification for production

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is private. All rights reserved.

## Support

For questions or issues, please contact the development team or open an issue in the repository.
