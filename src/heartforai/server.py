"""
Custom server to integrate home page, dashboard, and Chainlit chat
"""
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import chainlit as cl

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Create FastAPI app (Chainlit uses FastAPI under the hood)
app = FastAPI()

# Mount static files
app.mount("/public", StaticFiles(directory=str(PROJECT_ROOT / "public")), name="public")

@app.get("/")
async def home():
    """Serve the home page"""
    return FileResponse(PROJECT_ROOT / "public" / "index.html")

@app.get("/dashboard")
async def dashboard():
    """Serve the dashboard page"""
    return FileResponse(PROJECT_ROOT / "public" / "dashboard.html")

@app.get("/api/progress")
async def get_progress():
    """API endpoint to get claim progress data"""
    try:
        progress_file = PROJECT_ROOT / "database" / "progress.json"
        with open(progress_file, 'r') as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except FileNotFoundError:
        return JSONResponse({"error": "Progress data not found"}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
