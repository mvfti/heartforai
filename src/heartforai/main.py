"""
Main application entry point that combines custom routes with Chainlit
"""
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import chainlit as cl
from chainlit.cli import run_chainlit

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

def mount_custom_pages(app: FastAPI):
    """Mount custom pages and API routes to Chainlit's FastAPI app"""

    # Mount static files if not already mounted
    try:
        app.mount("/public", StaticFiles(directory=str(PROJECT_ROOT / "public")), name="public")
    except Exception:
        pass  # Already mounted

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

# This will be called by Chainlit to mount our custom routes
@cl.on_mount
def on_mount(app: FastAPI):
    """Called when Chainlit mounts the FastAPI app"""
    mount_custom_pages(app)
