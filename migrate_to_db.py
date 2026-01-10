import os
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
import numpy as np

# Load environment variables from .env file
load_dotenv()

# Initialize Supabase client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def migrate_data():
    """
    Migrates data from a CSV file to Supabase tables (aset, penyewa, sewaan),
    handling relationships and preventing duplicates.
    """
    try:
        # Read data from CSV
        df = pd.read_csv("senarai_aset_sewaan.csv")

        # Replace NaN values with None for database compatibility
        df = df.replace({np.nan: None})

        for _, row in df.iterrows():
            # 1. Handle Penyewa (Tenant)
            penyewa_id = None
            nama_penyewa = row["Nama_Penyewa"]
            
            if nama_penyewa and nama_penyewa.strip().upper() != 'KOSONG':
                # Check if tenant exists
                response = supabase.table("penyewa").select("penyewa_id").eq("nama_penyewa", nama_penyewa).execute()
                
                if response.data:
                    penyewa_id = response.data[0]['penyewa_id']
                else:
                    # Insert new tenant if not found
                    penyewa_data = {
                        "nama_penyewa": nama_penyewa,
                        "no_telefon_penyewa": row["No_Telefon_Penyewa"]
                    }
                    response = supabase.table("penyewa").insert(penyewa_data).execute()
                    if response.data:
                        penyewa_id = response.data[0]['penyewa_id']

            # 2. Handle Aset (Asset)
            aset_id_val = None
            id_aset_csv = row["ID_Aset"]
            if id_aset_csv:
                # Check if asset exists
                response = supabase.table("aset").select("aset_id").eq("id_aset", id_aset_csv).execute()

                if response.data:
                    aset_id_val = response.data[0]['aset_id']
                else:
                    # Insert new asset if not found
                    asset_data = {
                        "id_aset": id_aset_csv,
                        "jenis_aset": row["Jenis_Aset"],
                        "lokasi": row["Lokasi"]
                    }
                    response = supabase.table("aset").insert(asset_data).execute()
                    if response.data:
                        aset_id_val = response.data[0]['aset_id']

            # 3. Handle Sewaan (Rental)
            if aset_id_val and penyewa_id:
                # Check if rental record already exists to avoid duplicates
                response = supabase.table("sewaan").select("sewaan_id").eq("aset_id", aset_id_val).eq("penyewa_id", penyewa_id).execute()
                
                if not response.data:
                    sewaan_data = {
                        "aset_id": aset_id_val,
                        "penyewa_id": penyewa_id,
                        "sewa_bulanan_rm": row["Sewa_Bulanan_RM"] if row["Sewa_Bulanan_RM"] else 0,
                        "status_bayaran_terkini": row["Status_Bayaran_Terkini"]
                        # Tarikh_Mula_Sewa and Status_Perjanjian are often null
                        # Add them here if you want to import them, converting to a valid date format if necessary
                        # "tarikh_mula_sewa": row["Tarikh_Mula_Sewa"] if row["Tarikh_Mula_Sewa"] else None,
                        # "status_perjanjian": row["Status_Perjanjian"] if row["Status_Perjanjian"] else None,
                    }
                    supabase.table("sewaan").insert(sewaan_data).execute()
        
        print("Data migration completed successfully.")

    except Exception as e:
        print(f"An error occurred during data migration: {e}")

if __name__ == "__main__":
    migrate_data()
