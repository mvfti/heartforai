"""Model and client configuration"""

import os
from pathlib import Path
from mistralai import Mistral

MISTRAL_MODEL = "mistral-small-2506"
CONDITIONS_FILE_PATH = (
    Path(__file__).parents[2].joinpath("general_conditions/bhf_nl.md")
)
client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))