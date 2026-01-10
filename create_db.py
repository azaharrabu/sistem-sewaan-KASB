import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Initialize Supabase client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def create_tables():
    """Create tables in the Supabase database."""
    try:
        # Create assets table
        supabase.table("assets").upsert({
            "id": 1, 
            "lokasi": "DESA TUN RAZAK (NO.52)",
            "penyewa": "TADIKA (ROSYAZAIMA PUTEH/ZUHAIRI)",
            "sewa": 3500.00,
            "status_bayaran": "Pembayaran Berjalan"
        }).execute()
        print("Table 'assets' created successfully.")

        # Create tenants table
        supabase.table("tenants").upsert({
            "id": 1,
            "nama": "TADIKA (ROSYAZAIMA PUTEH/ZUHAIRI)",
            "asset_id": 1
        }).execute()
        print("Table 'tenants' created successfully.")

        # Create payments table
        supabase.table("payments").upsert({
            "id": 1,
            "asset_id": 1,
            "bulan": "Januari",
            "tahun": 2025,
            "jumlah": 3500.00,
            "status": "Selesai"
        }).execute()
        print("Table 'payments' created successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    create_tables()