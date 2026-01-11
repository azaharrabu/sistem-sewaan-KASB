import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# --- RUANGAN INPUT DATA (SILA ISI DI SINI) ---
# Format: {"tarikh": "YYYY-MM-DD", "amaun": 1234.50, "nota": "..."}

# DATA EFEIS: Sila isikan jumlah sebenar di sini berdasarkan Laporan FST
# Gantikan 0.00 dengan jumlah pendapatan sebenar.
DATA_EFEIS = [
    {"tarikh": "2025-02-21", "bil": 39, "yuran": 39100.00, "kos": 17087.50, "amaun": 22012.50, "nota": "Kursus Efeis (21 Feb 2025)"},
    {"tarikh": "2025-05-02", "bil": 38, "yuran": 41200.00, "kos": 18085.00, "amaun": 23115.00, "nota": "Kursus Efeis (02 Mei 2025)"},
    {"tarikh": "2025-05-16", "bil": 35, "yuran": 42000.00, "kos": 20645.00, "amaun": 21355.00, "nota": "Kursus Efeis (16 Mei 2025)"},
    {"tarikh": "2025-07-04", "bil": 43, "yuran": 42250.00, "kos": 17630.00, "amaun": 24620.00, "nota": "Kursus Efeis (04 Jul 2025)"},
    {"tarikh": "2025-08-15", "bil": 42, "yuran": 41450.00, "kos": 18867.50, "amaun": 22582.50, "nota": "Kursus Efeis (15 Ogos 2025)"},
    {"tarikh": "2025-10-31", "bil": 38, "yuran": 40650.00, "kos": 16990.00, "amaun": 23660.00, "nota": "Kursus Efeis (31 Okt 2025)"},
    {"tarikh": "2025-12-12", "bil": 38, "yuran": 38250.00, "kos": 18060.00, "amaun": 20190.00, "nota": "Kursus Efeis (12 Dis 2025)"},
]

# DATA PETROS: Format sama seperti Cleanpro Express.
# Sila masukkan nilai sebenar kemudian.
DATA_PETROS = [
    {"tarikh": "2025-01-31", "amaun": 0.00, "nota": "Profit Petros Jan 2025"},
    {"tarikh": "2025-02-28", "amaun": 0.00, "nota": "Profit Petros Feb 2025"},
    {"tarikh": "2025-03-31", "amaun": 0.00, "nota": "Profit Petros Mac 2025"},
    {"tarikh": "2025-04-30", "amaun": 0.00, "nota": "Profit Petros Apr 2025"},
    {"tarikh": "2025-05-31", "amaun": 0.00, "nota": "Profit Petros Mei 2025"},
    {"tarikh": "2025-06-30", "amaun": 0.00, "nota": "Profit Petros Jun 2025"},
    {"tarikh": "2025-07-31", "amaun": 0.00, "nota": "Profit Petros Jul 2025"},
    {"tarikh": "2025-08-31", "amaun": 0.00, "nota": "Profit Petros Ogos 2025"},
    {"tarikh": "2025-09-30", "amaun": 0.00, "nota": "Profit Petros Sep 2025"},
    {"tarikh": "2025-10-31", "amaun": 0.00, "nota": "Profit Petros Okt 2025"},
    {"tarikh": "2025-11-30", "amaun": 0.00, "nota": "Profit Petros Nov 2025"},
    {"tarikh": "2025-12-31", "amaun": 0.00, "nota": "Profit Petros Dis 2025"},
]
# ---------------------------------------------

def seed_other_income():
    print("Memulakan kemaskini data Efeis & Petros...")

    # Gabungkan data
    all_data = []
    for item in DATA_EFEIS:
        if item['amaun'] > 0:
            all_data.append({
                "sumber": "Efeis", 
                "tarikh": item['tarikh'], 
                "amaun": item['amaun'], 
                "nota": item['nota'],
                "bil_penyertaan": item.get('bil', 0),
                "kutipan_yuran": item.get('yuran', 0.00),
                "kos_pengurusan": item.get('kos', 0.00)
            })
    
    for item in DATA_PETROS:
        if item['amaun'] > 0:
            all_data.append({"sumber": "Petros", "tarikh": item['tarikh'], "amaun": item['amaun'], "nota": item['nota']})

    # Padam data lama tahun 2025 (untuk elak duplicate jika run banyak kali)
    # Nota: Kita delete berdasarkan range tarikh 2025
    supabase.table('pendapatan_lain').delete().gte('tarikh', '2025-01-01').lte('tarikh', '2025-12-31').execute()
    print("Data lama 2025 dipadam.")

    if not all_data:
        print("Tiada data baru untuk dimasukkan (Semua amaun 0).")
        return

    # Masukkan data baru
    batch_size = 50
    for i in range(0, len(all_data), batch_size):
        batch = all_data[i:i + batch_size]
        supabase.table('pendapatan_lain').insert(batch).execute()
    
    print(f"✅ {len(all_data)} rekod berjaya dimasukkan!")

if __name__ == "__main__":
    seed_other_income()