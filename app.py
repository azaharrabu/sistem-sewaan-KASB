import pandas as pd
from flask import Flask, render_template
import sqlite3
import os

# Initialize the Flask app
app = Flask(__name__)

DB_FILE = 'sewaan.db'
CSV_FILE = 'senarai_aset_sewaan.csv'
TABLE_NAME = 'aset'


import sqlite3
from flask import Flask, render_template, request, redirect, url_for
import os
from datetime import datetime

# Initialize the Flask app
# ... (kod sedia ada)

# Define the main route
@app.route('/')
def index():
    """
    Reads data from the database, calculates current month's payment status,
    and renders the dashboard.
    """
    if not os.path.exists(DB_FILE):
        return "Pangkalan data tidak dijumpai. Sila lawati /migrate untuk memulakan."

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get the current month in YYYY-MM format
    current_month = datetime.now().strftime('%Y-%m')

    try:
        cur.execute(f"SELECT * FROM {TABLE_NAME}")
        assets_rows = cur.fetchall()
        
        data = []
        for asset_row in assets_rows:
            asset = dict(asset_row)
            
            # Get sum of payments for the current month for this asset
            cur.execute("""
                SELECT SUM(amount_paid) 
                FROM payments 
                WHERE ID_Aset = ? AND strftime('%Y-%m', payment_date) = ?
            """, (asset['ID_Aset'], current_month))
            
            result = cur.fetchone()
            paid_this_month = result[0] if result[0] is not None else 0.0
            
            # Calculate payment status
            expected_rent = asset.get('Sewa_Bulanan_RM', 0.0)
            if expected_rent > 0:
                if paid_this_month >= expected_rent:
                    asset['payment_status'] = 'Lunas'
                elif paid_this_month > 0:
                    asset['payment_status'] = 'Bayaran separa'
                else:
                    asset['payment_status'] = 'Belum Bayar'
            else:
                asset['payment_status'] = 'N/A' # Not Applicable for free rent

            data.append(asset)
        
    except sqlite3.Error as e:
        return f"Ralat pangkalan data: {e}"
    finally:
        conn.close()

    # Render the HTML template, passing the data to it
    return render_template('index.html', data=data)

from flask import Flask, render_template, request, redirect, url_for

# (kod sedia ada di sini...)

@app.route('/asset/<asset_id>')
def asset_detail(asset_id):
    """
    Displays the details and payment history for a specific asset.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch asset details
    cur.execute(f"SELECT * FROM {TABLE_NAME} WHERE ID_Aset = ?", (asset_id,))
    asset = cur.fetchone()

    # Fetch payment history
    cur.execute("SELECT * FROM payments WHERE ID_Aset = ? ORDER BY payment_date DESC", (asset_id,))
    payments = cur.fetchall()

    conn.close()

    if asset is None:
        return "Aset tidak dijumpai.", 404

    return render_template('asset_detail.html', asset=asset, payments=payments)

@app.route('/add_payment/<asset_id>', methods=['POST'])
def add_payment(asset_id):
    """
    Handles the form submission for adding a new payment record.
    """
    payment_date = request.form['payment_date']
    amount_paid = request.form['amount_paid']
    notes = request.form.get('notes', '') # .get doesn't raise error if key missing

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO payments (ID_Aset, payment_date, amount_paid, notes)
        VALUES (?, ?, ?, ?)
    """, (asset_id, payment_date, amount_paid, notes))
    conn.commit()
    conn.close()

    return redirect(url_for('asset_detail', asset_id=asset_id))


# This allows the app to be run directly from the command line
if __name__ == '__main__':
    # Using debug=True will auto-reload the server when you make changes
    # Host='0.0.0.0' makes it accessible on your local network
    app.run(debug=True, host='0.0.0.0')
