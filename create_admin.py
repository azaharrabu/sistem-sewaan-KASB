import os
from supabase import create_client, Client
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def create_admin_user():
    username = "admin"
    password = "admin123"  # <--- Kata laluan sementara anda
    
    hashed_password = generate_password_hash(password)
    
    # Semak jika user sudah wujud untuk elak error
    res = supabase.table('users').select('*').eq('username', username).execute()
    if res.data:
        print(f"User '{username}' sudah wujud.")
        return
    
    data = {"username": username, "password_hash": hashed_password, "role": "admin"}
    supabase.table('users').insert(data).execute()
    print(f"User '{username}' berjaya dicipta dengan password '{password}'")

if __name__ == "__main__":
    create_admin_user()