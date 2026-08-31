"""Entrypoint for the InstaRAG HTTP API."""
import os
import uvicorn


def main():
    from storage.db import init_db
    init_db()

    host = os.getenv("INSTARAG_HOST", "0.0.0.0")
    # Support both standard cloud PORT (Render, Railway, Fly.io, Cloud Run) and INSTARAG_PORT
    port_str = os.getenv("PORT") or os.getenv("INSTARAG_PORT", "8000")
    port = int(port_str)

    uvicorn.run("src.api.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
