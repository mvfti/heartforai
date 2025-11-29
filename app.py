"""
Main application that combines custom routes with Chainlit
Run with: chainlit run app.py
"""
import json
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.routing import APIRoute
import chainlit as cl

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent

# Import Chainlit handlers FIRST so they register their routes
# Use heartforai package directly (it's installed via pyproject.toml)
from heartforai.claim_assistant import *

# Get Chainlit's FastAPI app instance AFTER importing handlers
from chainlit.server import app as chainlit_app

# Mount static files
try:
    chainlit_app.mount("/public", StaticFiles(directory=str(PROJECT_ROOT / "public")), name="public")
except Exception as e:
    print(f"Static files mounting note: {e}")

# Now add custom routes - these will be prepended to the router to take priority
def add_custom_routes():
    """Add custom routes with higher priority"""

    async def home():
        """Serve the landing page"""
        return FileResponse(PROJECT_ROOT / "public" / "index.html")

    async def dashboard():
        """Serve the dashboard page"""
        return FileResponse(PROJECT_ROOT / "public" / "dashboard.html")

    async def get_progress():
        """API endpoint to get claim progress data"""
        try:
            from datetime import datetime, timedelta
            import random as rand

            # Read current session policy
            session_file = PROJECT_ROOT / "database" / "current_session.json"
            if not session_file.exists():
                # Fallback to static progress.json if no session exists
                progress_file = PROJECT_ROOT / "database" / "progress.json"
                with open(progress_file, 'r') as f:
                    data = json.load(f)
                return JSONResponse(content=data)

            with open(session_file, 'r') as f:
                policy_data = json.load(f)

            # Generate dynamic progress based on policy
            now = datetime.now()

            # Generate claim ID based on policy ID
            claim_id = f"CLM-{policy_data['policy_id'][-6:]}"

            # Randomly determine current stage (1-5)
            current_stage = rand.randint(2, 4)  # Usually between stage 2 and 4

            stages = [
                {
                    "id": 1,
                    "name": "Claim Submitted",
                    "description": "Your claim has been received",
                    "status": "completed",
                    "date": (now - timedelta(days=3)).isoformat()
                },
                {
                    "id": 2,
                    "name": "Case Assigned to Claim Handler",
                    "description": "A dedicated claim handler has been assigned to your case",
                    "status": "completed" if current_stage >= 2 else "pending",
                    "date": (now - timedelta(days=2)).isoformat() if current_stage >= 2 else None
                },
                {
                    "id": 3,
                    "name": "Expert Assessment",
                    "description": "Expert is assessing your claim",
                    "status": "in_progress" if current_stage == 3 else ("completed" if current_stage > 3 else "pending"),
                    "date": (now - timedelta(days=1)).isoformat() if current_stage > 3 else None
                },
                {
                    "id": 4,
                    "name": "Claim Approved",
                    "description": "Final decision on your claim",
                    "status": "in_progress" if current_stage == 4 else ("completed" if current_stage > 4 else "pending"),
                    "date": None if current_stage <= 4 else now.isoformat()
                },
                {
                    "id": 5,
                    "name": "Payment Processed",
                    "description": "Payment has been initiated",
                    "status": "completed" if current_stage > 4 else "pending",
                    "date": None
                }
            ]

            # Calculate progress percentage
            progress_percentage = (current_stage / 5) * 100

            # Estimate completion date
            estimated_completion = (now + timedelta(days=(5 - current_stage) * 2)).date().isoformat()

            data = {
                "claim_id": claim_id,
                "user_name": policy_data.get("client_name", "Unknown"),
                "policy_id": policy_data.get("policy_id", "Unknown"),
                "product_name": policy_data.get("product_name", ""),
                "stages": stages,
                "current_stage": current_stage,
                "progress_percentage": int(progress_percentage),
                "estimated_completion": estimated_completion,
                "last_updated": now.isoformat()
            }

            return JSONResponse(content=data)
        except FileNotFoundError:
            return JSONResponse({"error": "Progress data not found"}, status_code=404)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    # Create routes with explicit priority
    home_route = APIRoute("/home", home, methods=["GET"], include_in_schema=False)
    dashboard_route = APIRoute("/dashboard", dashboard, methods=["GET"], include_in_schema=False)
    api_route = APIRoute("/api/progress", get_progress, methods=["GET"], include_in_schema=False)

    # Prepend our routes to the beginning of the routes list for higher priority
    chainlit_app.router.routes.insert(0, api_route)
    chainlit_app.router.routes.insert(0, dashboard_route)
    chainlit_app.router.routes.insert(0, home_route)

add_custom_routes()

# Note:
# - Chainlit UI (chat) is automatically mounted at / (root)
# - Landing page accessible at /home
# - Dashboard accessible at /dashboard
# - Progress API accessible at /api/progress
