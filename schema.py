import sqlite3

DB_FILE = 'sewaan.db'

def create_payment_table():
    """
    Adds the 'payments' table to the database.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        
        # Create the payments table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_Aset TEXT NOT NULL,
            payment_date DATE NOT NULL,
            amount_paid REAL NOT NULL,
            notes TEXT,
            FOREIGN KEY (ID_Aset) REFERENCES aset (ID_Aset)
        )
        """)
        
        conn.commit()
        conn.close()
        print("Jadual 'payments' berjaya dicipta atau sudah wujud.")
    except Exception as e:
        print(f"Satu ralat telah berlaku: {e}")

if __name__ == '__main__':
    create_payment_table()
