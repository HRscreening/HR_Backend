from dotenv import load_dotenv
import os
import uvicorn

load_dotenv()

env = os.getenv("ENVIRONMENT", "Development")

port = int(os.getenv("PORT", 8000))

if env == "Development":
    host = "127.0.0.1"
    reload = True
else:
    host = "0.0.0.0"   
    reload = False

print(f"ENV: {env}")
print(f"Starting server on {host}:{port} (reload={reload})")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload
    )