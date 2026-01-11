import os
import calendar
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rahsia_sementara_kasb") # Diperlukan untuk flash messages

# Initialize Supabase client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

@app.route('/')
def index():
    """
    Fetches asset rental data from the Supabase database and renders the dashboard.
    """
    try:
        # --- LOGIK BARU: KIRA PENDAPATAN BULANAN & TAHUNAN ---
        current_year = datetime.now().year
        selected_year = request.args.get('year', current_year, type=int)
        
        start_date = f"{selected_year}-01-01"
        end_date = f"{selected_year}-12-31"

        # Dapatkan semua transaksi untuk tahun yang dipilih
        tx_res = supabase.table('transaksi_bayaran').select('amaun_bayaran, tarikh_bayaran').gte('tarikh_bayaran', start_date).lte('tarikh_bayaran', end_date).execute()
        transactions = tx_res.data

        # Dapatkan pendapatan lain (Efeis & Petros)
        other_res = supabase.table('pendapatan_lain').select('*').gte('tarikh', start_date).lte('tarikh', end_date).execute()
        other_data = other_res.data

        # Struktur Data Kewangan: { bulan: { 'sewaan': 0, 'efeis': 0, 'petros': 0, 'total': 0 } }
        financial_data = {m: {'sewaan': 0.0, 'efeis': 0.0, 'petros': 0.0, 'total': 0.0} for m in range(1, 13)}
        yearly_totals = {'sewaan': 0.0, 'efeis': 0.0, 'petros': 0.0}
        total_yearly_income = 0.00

        # Proses Sewaan
        for t in transactions:
            dt = datetime.strptime(t['tarikh_bayaran'], '%Y-%m-%d')
            amt = float(t['amaun_bayaran'])
            financial_data[dt.month]['sewaan'] += amt
            financial_data[dt.month]['total'] += amt
            yearly_totals['sewaan'] += amt
            total_yearly_income += amt

        # Proses Pendapatan Lain
        for item in other_data:
            dt = datetime.strptime(item['tarikh'], '%Y-%m-%d')
            amt = float(item['amaun'])
            src = item['sumber'].lower() # 'efeis' atau 'petros'
            if src in financial_data[dt.month]:
                financial_data[dt.month][src] += amt
                yearly_totals[src] += amt
            
            financial_data[dt.month]['total'] += amt
            total_yearly_income += amt

        # -----------------------------------------------------

    except Exception as e:
        # If there's an error, display it to make debugging easier
        return f"Database error: {e}"

    # Render the HTML template, passing the transformed data to it
    return render_template('index.html', 
                           financial_data=financial_data, 
                           yearly_totals=yearly_totals,
                           total_yearly_income=total_yearly_income,
                           selected_year=selected_year,
                           current_year=current_year)

@app.route('/sewaan')
def sewaan_dashboard():
    """
    Memaparkan senarai terperinci aset sewaan.
    """
    try:
        # Fetch data from Supabase, joining tables
        response = supabase.table('sewaan').select('*, aset(id_aset, lokasi), penyewa(nama_penyewa)').order('aset_id', desc=False).execute()
        
        api_data = response.data
        template_data = []
        
        for item in api_data:
            penyewa_nama = item.get('penyewa', {}).get('nama_penyewa') if item.get('penyewa') else 'Tiada Maklumat'
            
            template_data.append({
                'sewaan_id': item.get('sewaan_id'),
                'id': item.get('aset', {}).get('id_aset', 'N/A'),
                'lokasi': item.get('aset', {}).get('lokasi', 'N/A'),
                'penyewa': penyewa_nama,
                'sewa': item.get('sewa_bulanan_rm', 0.00),
                'status_bayaran': item.get('status_bayaran_terkini', 'N/A')
            })
            
        return render_template('sewaan_list.html', data=template_data)
        
    except Exception as e:
        return f"Ralat memuatkan senarai sewaan: {e}"

@app.route('/asset/<int:sewaan_id>')
def asset_detail(sewaan_id):
    try:
        # 1. Dapatkan maklumat asas sewaan (Aset & Penyewa)
        sewaan_res = supabase.table('sewaan').select('*, aset(*), penyewa(*)').eq('sewaan_id', sewaan_id).single().execute()
        sewaan_data = sewaan_res.data

        # 2. Dapatkan tahun dari query parameter (default tahun semasa)
        current_year = datetime.now().year
        selected_year = request.args.get('year', current_year, type=int)

        # 3. Dapatkan sejarah transaksi untuk tahun tersebut
        start_date = f"{selected_year}-01-01"
        end_date = f"{selected_year}-12-31"
        
        transaksi_res = supabase.table('transaksi_bayaran')\
            .select('*')\
            .eq('sewaan_id', sewaan_id)\
            .gte('tarikh_bayaran', start_date)\
            .lte('tarikh_bayaran', end_date)\
            .order('tarikh_bayaran', desc=True)\
            .execute()
            
        transaksi_data = transaksi_res.data

        # Kira total bayaran tahun ini
        total_bayaran = sum(item['amaun_bayaran'] for item in transaksi_data)

        # 4. Logik Status Bulanan (Jan - Dec)
        monthly_status = []
        sewa_bulanan = float(sewaan_data.get('sewa_bulanan_rm', 0))
        
        for month in range(1, 13):
            month_name = calendar.month_name[month]
            
            # Cari bayaran dalam bulan ini
            bayaran_bulan_ini = sum(
                t['amaun_bayaran'] for t in transaksi_data 
                if int(t['tarikh_bayaran'].split('-')[1]) == month
            )
            
            status = "Tertunggak"
            badge_class = "bg-danger"
            
            # Logic mudah status
            if sewa_bulanan > 0:
                if bayaran_bulan_ini >= sewa_bulanan:
                    status = "Selesai"
                    badge_class = "bg-success"
                elif bayaran_bulan_ini > 0:
                    status = "Sebahagian"
                    badge_class = "bg-warning text-dark"
            else:
                # Logic khas untuk Profit Sharing (Sewa = 0)
                if bayaran_bulan_ini > 0:
                    status = "Diterima"
                    badge_class = "bg-success"
                else:
                    status = "-"
                    badge_class = "bg-secondary"
            
            # Logic Notis (Hanya untuk tahun semasa & bulan yang dah lepas/sedang berlaku)
            today = date.today()
            if selected_year == today.year:
                if month > today.month:
                    status = "-"
                    badge_class = "bg-secondary"
            
            monthly_status.append({
                "month": month_name,
                "paid": bayaran_bulan_ini,
                "status": status,
                "badge": badge_class
            })

        return render_template(
            'asset_detail.html', 
            asset=sewaan_data, 
            transactions=transaksi_data,
            monthly_status=monthly_status,
            selected_year=selected_year,
            total_bayaran=total_bayaran,
            current_year=current_year
        )

    except Exception as e:
        return f"Ralat memuatkan detail: {e}"

@app.route('/add_payment/<int:sewaan_id>', methods=['POST'])
def add_payment(sewaan_id):
    try:
        tarikh = request.form.get('tarikh_bayaran')
        amaun = request.form.get('amaun_bayaran')
        nota = request.form.get('nota')
        
        # Masukkan ke database
        data = {
            "sewaan_id": sewaan_id,
            "tarikh_bayaran": tarikh,
            "amaun_bayaran": float(amaun),
            "nota": nota
        }
        
        supabase.table('transaksi_bayaran').insert(data).execute()
        
        # Update status bayaran terkini di table sewaan (Optional logic: Auto update status)
        # Contoh mudah: Jika bayar, kita anggap "Berjalan". 
        # Logic sebenar mungkin lebih kompleks (check due date).
        supabase.table('sewaan').update({"status_bayaran_terkini": "Pembayaran Berjalan"}).eq("sewaan_id", sewaan_id).execute()

        # Flash message (perlu setup secret key di app config)
        # flash("Pembayaran berjaya direkodkan!", "success")
        
        return redirect(url_for('asset_detail', sewaan_id=sewaan_id))

    except Exception as e:
        return f"Ralat menambah pembayaran: {e}"

# This allows the app to be run directly from the command line
if __name__ == '__main__':
    # Using debug=True will auto-reload the server when you make changes
    # Host='0.0.0.0' makes it accessible on your local network
    app.run(debug=True, host='0.0.0.0')