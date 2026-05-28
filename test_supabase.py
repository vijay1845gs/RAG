from dotenv import load_dotenv
import os
from supabase import create_client

load_dotenv("backend/.env")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

print("URL:", url)
print("KEY EXISTS:", bool(key))
print("KEY START:", key[:20] if key else "NO KEY")

client = create_client(url, key)

result = client.table("profiles").select("*").limit(1).execute()

print(result)