from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SECRET_KEY")

if not url or not key:
    raise ValueError("Configure SUPABASE_URL e SUPABASE_SECRET_KEY no .env")

supabase = create_client(url, key)