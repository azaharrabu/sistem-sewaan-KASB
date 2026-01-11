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

# DATA EFEIS: Sila rujuk page 'Laporan FST' dalam fail anda.
# Masukkan amaun pada bulan yang ada kursus sahaja. Biarkan 0.00 jika tiada.
DATA_EFEIS = [
    {"tarikh": "2025-01-31", "amaun": 0.00, "nota": "Kursus Efeis Jan 2025"},
    {"tarikh": "2025-02-28", "amaun": 0.00, "nota": "Kursus Efeis Feb 2025"},
    {"tarikh": "2025-03-31", "amaun": 0.00, "nota": "Kursus Efeis Mac 2025"},
    {"tarikh": "2025-04-30", "amaun": 0.00, "nota": "Kursus Efeis Apr 2025"},
    {"tarikh": "2025-05-31", "amaun": 0.00, "nota": "Kursus Efeis Mei 2025"},
    {"tarikh": "2025-06-30", "amaun": 0.00, "nota": "Kursus Efeis Jun 2025"},
    {"tarikh": "2025-07-31", "amaun": 0.00, "nota": "Kursus Efeis Jul 2025"},
    {"tarikh": "2025-08-31", "amaun": 0.00, "nota": "Kursus Efeis Ogos 2025"},
    {"tarikh": "2025-09-30", "amaun": 0.00, "nota": "Kursus Efeis Sep 2025"},
    {"tarikh": "2025-10-31", "amaun": 0.00, "nota": "Kursus Efeis Okt 2025"},
    {"tarikh": "2025-11-30", "amaun": 0.00, "nota": "Kursus Efeis Nov 2025"},
    {"tarikh": "2025-12-31", "amaun": 0.00, "nota": "Kursus Efeis Dis 2025"},
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
            all_data.append({"sumber": "Efeis", "tarikh": item['tarikh'], "amaun": item['amaun'], "nota": item['nota']})
    
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