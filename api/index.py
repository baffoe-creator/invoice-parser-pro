from fastapi import FastAPI
import os
import sys

app = FastAPI()


@app.get("/")
async def root():
    return {
        "message": "✅ MINIMAL APP WORKING!",
        "status": "healthy",
        "environment": "vercel" if os.getenv("VERCEL") else "local",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "Invoice Parser Pro",
        "python_version": sys.version.split()[0],
    }


handler = app
