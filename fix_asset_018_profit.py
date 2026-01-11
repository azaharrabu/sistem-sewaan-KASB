import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# --- RUANGAN INPUT DATA (SILA ISI DI SINI) ---
TARGET_ASSET_ID = "ASSET-018"

# Masukkan senarai bayaran sebenar mengikut fail anda.
# PENTING: Sila rujuk fail rekod anda dan masukkan jumlah sebenar di bawah.
# Saya (AI) tidak dapat melihat fail asal anda, jadi saya letakkan 0.00 sebagai placeholder.
DATA_PROFIT_SHARING = [
    {"tarikh": "2025-01-17", "amaun": 2147.20, "nota": "Profit Sharing Jan 2025"},
    {"tarikh": "2025-02-15", "amaun": 1987.80, "nota": "Profit Sharing Feb 2025"},
    {"tarikh": "2025-03-13", "amaun": 1206.52, "nota": "Profit Sharing Mac 2025"},
    {"tarikh": "2025-04-16", "amaun": 1648.60, "nota": "Profit Sharing Apr 2025"},
    {"tarikh": "2025-05-13", "amaun": 1162.30, "nota": "Profit Sharing Mei 2025"},
    {"tarikh": "2025-06-12", "amaun": 333.60, "nota": "Profit Sharing Jun 2025"},
    {"tarikh": "2025-07-14", "amaun": 115.20, "nota": "Profit Sharing Jul 2025"},
    {"tarikh": "2025-08-14", "amaun": 123.00, "nota": "Profit Sharing Ogos 2025"},
    {"tarikh": "2025-09-19", "amaun": 417.84, "nota": "Profit Sharing Sep 2025"},
    {"tarikh": "2025-10-16", "amaun": 660.60, "nota": "Profit Sharing Okt 2025"},
    {"tarikh": "2025-11-14", "amaun": 122.20, "nota": "Profit Sharing Nov 2025"},
    {"tarikh": "2025-12-31", "amaun": 0.00, "nota": "Profit Sharing Dis 2025"},
]
# ---------------------------------------------

def fix_profit_sharing_data():
    print(f"Memulakan kemaskini Profit Sharing untuk {TARGET_ASSET_ID}...")

    # 1. Dapatkan ID database
    res_aset = supabase.table('aset').select('aset_id').eq('id_aset', TARGET_ASSET_ID).execute()
    if not res_aset.data:
        print("Aset tidak dijumpai!")
        return
    aset_db_id = res_aset.data[0]['aset_id']

    res_sewaan = supabase.table('sewaan').select('sewaan_id').eq('aset_id', aset_db_id).execute()
    if not res_sewaan.data:
        print("Rekod sewaan tidak dijumpai!")
        return
    sewaan_id = res_sewaan.data[0]['sewaan_id']

    # 2. Pastikan Sewa Bulanan adalah 0.00 (Sebab Profit Sharing)
    supabase.table('sewaan').update({"sewa_bulanan_rm": 0.00}).eq('sewaan_id', sewaan_id).execute()
    print("Sewa bulanan ditetapkan kepada RM 0.00 (Mod Profit Sharing).")

    # 3. Padam rekod lama 2025
    supabase.table('transaksi_bayaran').delete().eq('sewaan_id', sewaan_id).gte('tarikh_bayaran', '2025-01-01').lte('tarikh_bayaran', '2025-12-31').execute()
    print("Rekod lama 2025 dipadam.")

    # 4. Masukkan data sebenar
    transactions = []
    for item in DATA_PROFIT_SHARING:
        if item['amaun'] > 0: # Hanya masukkan jika ada keuntungan (optional, atau masukkan semua)
            transactions.append({
                "sewaan_id": sewaan_id,
                "tarikh_bayaran": item['tarikh'],
                "amaun_bayaran": item['amaun'],
                "nota": item['nota']
            })
    
    if transactions:
        supabase.table('transaksi_bayaran').insert(transactions).execute()
        print(f"✅ {len(transactions)} rekod keuntungan berjaya dimasukkan!")
    else:
        print("Tiada data keuntungan untuk dimasukkan (semua amaun 0).")

if __name__ == "__main__":
    fix_profit_sharing_data()