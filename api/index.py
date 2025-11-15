from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import sys

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://invoice-parser-proo.onrender.com",  # Your frontend URL
        "http://localhost:3000",  # For local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
