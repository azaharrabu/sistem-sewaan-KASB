import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# --- SILA ISI DATA DARI PDF ANDA DI SINI ---

# Contoh Struktur Data untuk Bulan Ogos
DATA_BULANAN = [
    {
        "bulan": "2025-08-31", # Tarikh akhir bulan
        "nota": "Petros Income August 2025",
        "total_profit": 15000.00, # Masukkan Total Profit Bulan Ogos
        "details": [
            # Jenis Minyak, Daily Volume, Commission, Kos, Profit
            {"jenis": "RON 95", "vol": 12000, "comm": 5000, "kos": 1000, "profit": 4000},
            {"jenis": "RON 97", "vol": 5000, "comm": 3000, "kos": 500, "profit": 2500},
            {"jenis": "Diesel", "vol": 20000, "comm": 8000, "kos": 2000, "profit": 6000},
            {"jenis": "Minyak Pelincir", "vol": 0, "comm": 500, "kos": 100, "profit": 400},
        ]
    },
    {
        "bulan": "2025-09-30",
        "nota": "Petros Income September 2025",
        "total_profit": 16500.00, 
        "details": [
            {"jenis": "RON 95", "vol": 12500, "comm": 5200, "kos": 1100, "profit": 4100},
            {"jenis": "RON 97", "vol": 5100, "comm": 3100, "kos": 550, "profit": 2550},
            {"jenis": "Diesel", "vol": 21000, "comm": 8500, "kos": 2100, "profit": 6400},
        ]
    },
    {
        "bulan": "2025-10-31",
        "nota": "Petros Income October 2025",
        "total_profit": 14800.00, 
        "details": [
            {"jenis": "RON 95", "vol": 11000, "comm": 4800, "kos": 900, "profit": 3900},
            {"jenis": "RON 97", "vol": 4800, "comm": 2900, "kos": 400, "profit": 2500},
            {"jenis": "Diesel", "vol": 19000, "comm": 7800, "kos": 1900, "profit": 5900},
        ]
    }
]

def seed_petros():
    print("Memasukkan data Petros...")

    for data in DATA_BULANAN:
        # Kira pembahagian keuntungan (20% KASB untuk 2025)
        total_profit = float(data['total_profit'])
        kasb_share = total_profit * 0.20

        # 1. Masukkan/Update Rekod Utama di pendapatan_lain
        # Kita check kalau dah ada, kita update. Kalau belum, insert.
        existing = supabase.table('pendapatan_lain').select('id').eq('sumber', 'Petros').eq('tarikh', data['bulan']).execute()
        
        main_id = None
        
        if existing.data:
            main_id = existing.data[0]['id']
            supabase.table('pendapatan_lain').update({
                "kutipan_yuran": total_profit, # Total Profit
                "amaun": kasb_share,           # Bahagian KASB (20%)
                "nota": data['nota']
            }).eq('id', main_id).execute()
            print(f"Updated main record for {data['bulan']}")
        else:
            res = supabase.table('pendapatan_lain').insert({
                "sumber": "Petros",
                "tarikh": data['bulan'],
                "kutipan_yuran": total_profit, # Total Profit
                "amaun": kasb_share,           # Bahagian KASB (20%)
                "nota": data['nota']
            }).execute()
            main_id = res.data[0]['id']
            print(f"Inserted main record for {data['bulan']}")

        # 2. Masukkan Details (Padam lama, masukkan baru untuk elak duplicate)
        supabase.table('petros_details').delete().eq('pendapatan_id', main_id).execute()
        
        detail_inserts = []
        for d in data['details']:
            detail_inserts.append({
                "pendapatan_id": main_id,
                "jenis_minyak": d['jenis'],
                "daily_volume": d['vol'],
                "earned_commission": d['comm'],
                "kos": d['kos'],
                "profit": d['profit']
            })
        
        if detail_inserts:
            supabase.table('petros_details').insert(detail_inserts).execute()
            print(f"Inserted {len(detail_inserts)} details for {data['bulan']}")

if __name__ == "__main__":
    seed_petros()