import pandas as pd
import sqlite3
import os

DB_FILE = 'sewaan.db'
CSV_FILE = 'senarai_aset_sewaan.csv'
TABLE_NAME = 'aset'

def migrate():
    """
    Migrates data from CSV to SQLite database, overwriting the existing database.
    """
    if not os.path.exists(CSV_FILE):
        print(f"Ralat: Fail '{CSV_FILE}' tidak dijumpai.")
        return

    # Remove the old database file to ensure a fresh start
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"Pangkalan data lama '{DB_FILE}' telah dipadam.")

    try:
        df = pd.read_csv(CSV_FILE)
        
        # Clean and prepare the data
        # Ensure all expected columns exist, fill with defaults if not
        expected_columns = {
            'ID Aset': 'ID_Aset',
            'Lokasi': 'Lokasi',
            'Penyewa': 'Nama_Penyewa',
            'Sewa (RM)': 'Sewa_Bulanan_RM',
            'Status Bayaran': 'Status_Bayaran_Terkini'
        }
        
        # Rename columns that exist
        df.rename(columns={k: v for k, v in expected_columns.items() if k in df.columns}, inplace=True)
        
        # Fill missing values for the now-renamed columns
        if 'Nama_Penyewa' in df.columns:
            df['Nama_Penyewa'] = df['Nama_Penyewa'].fillna('')
        if 'Status_Bayaran_Terkini' in df.columns:
            df['Status_Bayaran_Terkini'] = df['Status_Bayaran_Terkini'].fillna('Tiada Maklumat')
        if 'Sewa_Bulanan_RM' in df.columns:
            df['Sewa_Bulanan_RM'] = df['Sewa_Bulanan_RM'].fillna(0)


        conn = sqlite3.connect(DB_FILE)
        # Use if_exists='replace' to drop the table if it already exists and create a new one
        df.to_sql(TABLE_NAME, conn, if_exists='replace', index=False)
        conn.close()
        print(f"Berjaya! Data dari '{CSV_FILE}' telah dimuat naik ke pangkalan data '{DB_FILE}'.")
    except Exception as e:
        print(f"Satu ralat telah berlaku: {e}")

if __name__ == '__main__':
    migrate()
