import argparse
import os
from supabase import create_client, Client
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)


def upsert_admin_user(username: str, password: str, role: str = "admin"):
    hashed_password = generate_password_hash(password)

    res = supabase.table('users').select('*').eq('username', username).execute()
    if res.data:
        supabase.table('users').update({
            'password_hash': hashed_password,
            'role': role,
        }).eq('username', username).execute()
        print(f"User '{username}' berjaya dikemaskini. Password baru: '{password}'")
        return

    data = {
        "username": username,
        "password_hash": hashed_password,
        "role": role,
    }
    supabase.table('users').insert(data).execute()
    print(f"User '{username}' berjaya dicipta dengan password '{password}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or reset an admin user in Supabase.")
    parser.add_argument("--username", default="admin", help="Username untuk admin")
    parser.add_argument("--password", default="admin123", help="Password untuk admin")
    parser.add_argument("--role", default="admin", help="Role untuk user")
    args = parser.parse_args()

    upsert_admin_user(args.username, args.password, args.role)
