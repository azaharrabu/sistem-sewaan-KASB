import pandas as pd
import sqlite3
import os

DB_FILE = 'sewaan.db'
CSV_FILE = 'senarai_aset_sewaan.csv'
TABLE_NAME = 'aset'

def migrate():
    """
    Reads data from a CSV file and migrates it to a SQLite database table.
    The script will not run if the database file already exists to prevent duplication.
    """
    if not os.path.exists(CSV_FILE):
        print(f"Ralat: Fail '{CSV_FILE}' tidak dijumpai.")
        return

    if os.path.exists(DB_FILE):
        print(f"Pangkalan data '{DB_FILE}' sudah wujud. Migrasi dibatalkan untuk mengelak data berganda.")
        return

    try:
        # Baca data dari CSV
        df = pd.read_csv(CSV_FILE)
        
        # Sambung ke pangkalan data SQLite (ia akan dicipta jika tidak wujud)
        conn = sqlite3.connect(DB_FILE)
        
        # Gunakan pandas to_sql untuk memindahkan data ke jadual
        # 'if_exists='fail'' akan menyebabkan ralat jika jadual sudah wujud
        df.to_sql(TABLE_NAME, conn, if_exists='fail', index=False)
        
        conn.close()
        
        print(f"Berjaya! Data dari '{CSV_FILE}' telah dimuat naik ke jadual '{TABLE_NAME}' dalam '{DB_FILE}'.")

    except Exception as e:
        print(f"Satu ralat telah berlaku: {e}")

if __name__ == '__main__':
    migrate()
