"""Entrypoint for the InstaRAG HTTP API."""
import os

import uvicorn


def main():
    host = os.getenv("INSTARAG_HOST", "127.0.0.1")
    port = int(os.getenv("INSTARAG_PORT", "8000"))
    uvicorn.run("src.api.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
