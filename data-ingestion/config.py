"""
Configuration management for data ingestion pipeline.

Set up your API keys in a .env file in the data-ingestion directory:

GOOGLE_PLACES_API_KEY=your_google_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
"""

import os
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# API Keys
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# OpenAI Configuration
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # cost-effective model
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "16000"))
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))

# Scraping Configuration
MAX_HTML_LENGTH = int(os.getenv("MAX_HTML_LENGTH", "50000"))  # truncate HTML to avoid huge token costss
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))  # seconds
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

# Rate Limiting
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "1.0"))  # seconds between API calls

# Directory Paths
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
SAMPLES_DIR = BASE_DIR / "samples"
LOGS_DIR = BASE_DIR / "logs"
SCRIPTS_DIR = BASE_DIR / "scripts"

# Ensure directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
SAMPLES_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
SCRIPTS_DIR.mkdir(exist_ok=True)

# CSV Schema
CSV_FIELDNAMES = [
    "doc_id",
    "name",
    "address",
    "phone",
    "website",
    "services",
    "population",
    "eligibility",
    "intake",
    "hours",
    "capacity",
    "cost",
    "contact_email",
    "notes"
]

# Search Configuration for Google Places API
SEARCH_LOCATIONS: List[Dict] = [
    {"name": "Dallas", "lat": 32.7767, "lng": -96.7970, "radius": 25000},
    {"name": "Fort Worth", "lat": 32.7555, "lng": -97.3308, "radius": 25000},
    {"name": "Arlington", "lat": 32.7357, "lng": -97.1081, "radius": 20000},
    {"name": "Plano", "lat": 33.0198, "lng": -96.6989, "radius": 20000},
    {"name": "Garland", "lat": 32.9126, "lng": -96.6389, "radius": 15000},
    {"name": "Irving", "lat": 32.8140, "lng": -96.9489, "radius": 15000},
    {"name": "Richardson", "lat": 32.9483, "lng": -96.7299, "radius": 15000},
    {"name": "Frisco", "lat": 33.1507, "lng": -96.8236, "radius": 15000},
    {"name": "McKinney", "lat": 33.1972, "lng": -96.6397, "radius": 15000},
    {"name": "Mesquite", "lat": 32.7668, "lng": -96.5992, "radius": 12000},
    {"name": "Denton", "lat": 33.2148, "lng": -97.1331, "radius": 15000},
]

SEARCH_QUERIES = [
    "community health center",
    "mental health clinic",
    "homeless services",
    "free clinic",
    "FQHC",
    "substance abuse treatment",
    "domestic violence shelter",
    "food bank",
    "housing assistance",
    "crisis counseling",
    "public health department",
    "low cost medical clinic",
]

# Validation
def validate_config() -> bool:
    """Validate that required configuration is present."""
    errors = []
    
    if not GOOGLE_PLACES_API_KEY:
        errors.append("GOOGLE_PLACES_API_KEY not set")
    
    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY not set")
    
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        print("\nPlease create a .env file in the data-ingestion directory with:")
        print("  GOOGLE_PLACES_API_KEY=your_key_here")
        print("  OPENAI_API_KEY=your_key_here")
        return False
    
    return True


if __name__ == "__main__":
    # Test configuration
    print("Configuration loaded:")
    print(f"  Google Places API Key: {'✓' if GOOGLE_PLACES_API_KEY else '✗'}")
    print(f"  OpenAI API Key: {'✓' if OPENAI_API_KEY else '✗'}")
    print(f"  Output directory: {OUTPUT_DIR}")
    print(f"  OpenAI model: {OPENAI_MODEL}")
    print(f"\nSearch locations: {len(SEARCH_LOCATIONS)}")
    print(f"Search queries: {len(SEARCH_QUERIES)}")
    print(f"\nValid configuration: {validate_config()}")

