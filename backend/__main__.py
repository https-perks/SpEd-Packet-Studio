import uvicorn
from backend.config import settings

def main() -> None:
    uvicorn.run("backend.main:app", host=settings.api_host, port=settings.api_port, reload=settings.environment == "development")

if __name__ == "__main__":
    main()
