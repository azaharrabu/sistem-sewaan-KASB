import os
import random
from datetime import date
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def seed_2025_data():
    print("Memulakan proses menjana data pembayaran tahun 2025...")
    
    # Dapatkan semua sewaan
    try:
        response = supabase.table('sewaan').select('*').execute()
        sewaan_list = response.data

        transactions = []

        for sewaan in sewaan_list:
            sewaan_id = sewaan['sewaan_id']
            sewa_bulanan = sewaan['sewa_bulanan_rm']
            status_terkini = sewaan['status_bayaran_terkini']
            
            # Tentukan berapa bulan nak generate (1-12)
            # Jika 'Berjalan', bayar penuh 12 bulan. 
            # Jika 'Tertunggak', kita anggap bayar sampai bulan 10 sahaja sebagai contoh data.
            bulan_dibayar = 12
            if status_terkini and 'Tertunggak' in str(status_terkini):
                bulan_dibayar = 10 

            for bulan in range(1, bulan_dibayar + 1):
                # Jana tarikh rawak antara 1hb hingga 7hb setiap bulan
                hari = random.randint(1, 7)
                
                tarikh_bayaran = date(2025, bulan, hari).isoformat()
                
                # Masukkan data
                transactions.append({
                    "sewaan_id": sewaan_id,
                    "tarikh_bayaran": tarikh_bayaran,
                    "amaun_bayaran": sewa_bulanan,
                    "nota": f"Bayaran Sewa Bulan {bulan}/2025 (Auto-Generated)"
                })

        if transactions:
            # Insert in batches to be safe
            batch_size = 50
            for i in range(0, len(transactions), batch_size):
                batch = transactions[i:i + batch_size]
                supabase.table('transaksi_bayaran').insert(batch).execute()
                print(f"Dimasukkan {len(batch)} transaksi...")
            
            print("✅ Berjaya menjana data pembayaran 2025!")
    except Exception as e:
        print(f"Ralat: {e}")

if __name__ == "__main__":
    seed_2025_data()