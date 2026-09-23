"""Loads environment variables from .env for local scripts (data pulls, RAG ingestion, etc.)."""

import os

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
NASA_API_KEY = os.environ.get("NASA_API_KEY")
