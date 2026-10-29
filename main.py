"""Stable ASGI entry point: uvicorn main:app."""
from moneliora.application import create_app

app = create_app()
