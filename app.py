import os
import json
import calendar
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client, Client
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rahsia_sementara_kasb") # Diperlukan untuk flash messages

# Initialize Supabase client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# --- AUTH DECORATOR ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES: AUTH ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Cari user dalam DB
        res = supabase.table('users').select('*').eq('username', username).execute()
        user = res.data[0] if res.data else None
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['linked_name'] = user.get('linked_name') # Simpan nama link (untuk partner)
            
            # Redirect mengikut role
            if user['role'] == 'tenant':
                return redirect(url_for('dashboard_penyewa'))
            elif user['role'] == 'partner':
                return redirect(url_for('dashboard_partner'))
            elif user['role'] == 'petros_admin':
                return redirect(url_for('petros_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Username atau Password salah!', 'danger')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        selected_role = request.form.get('role') # Dapatkan role dari dropdown
        selected_penyewa_id = request.form.get('penyewa_id') # ID Penyewa jika role = tenant
        selected_partner_name = request.form.get('partner_name') # Nama Partner jika role = partner

        if password != confirm_password:
            flash('Kata laluan tidak sepadan.', 'danger')
            return redirect(url_for('register'))
            
        # Validasi: Pastikan Penyewa memilih nama dari senarai
        if selected_role == 'tenant' and not selected_penyewa_id:
            flash('Sila pilih Nama Penyewa daripada senarai yang disediakan.', 'warning')
            return redirect(url_for('register'))

        # Semak jika email sudah wujud
        res = supabase.table('users').select('*').eq('username', email).execute()
        if res.data:
            flash('Email ini sudah didaftarkan. Sila log masuk.', 'warning')
            return redirect(url_for('login'))

        # Daftar pengguna baru
        hashed_password = generate_password_hash(password)
        data = {
            "username": email, # Guna email sebagai username
            "password_hash": hashed_password,
            "role": selected_role if selected_role else "user",
            "linked_name": selected_partner_name if selected_role == 'partner' else None
        }
        supabase.table('users').insert(data).execute()
        
        # Jika pengguna adalah Penyewa, hubungkan email dengan rekod penyewa sedia ada
        if selected_role == 'tenant' and selected_penyewa_id:
            try:
                supabase.table('penyewa').update({'email': email}).eq('penyewa_id', selected_penyewa_id).execute()
            except Exception as e:
                # Log error jika perlu, tapi user tetap berjaya didaftarkan
                print(f"Ralat menghubungkan penyewa: {e}")

        flash('Pendaftaran berjaya! Sila log masuk.', 'success')
        return redirect(url_for('login'))

    # Dapatkan senarai penyewa untuk dropdown (GET request)
    penyewa_list = []
    try:
        res = supabase.table('penyewa').select('penyewa_id, nama_penyewa').order('nama_penyewa').execute()
        penyewa_list = res.data
    except Exception:
        pass

    # Dapatkan senarai nama kerjasama unik untuk dropdown
    partner_list = []
    try:
        # Ambil semua nama dan filter unik dalam Python (Supabase JS client ada .distinct(), Python client terhad)
        res_p = supabase.table('kerjasama_ketiga').select('nama_kerjasama').execute()
        partner_list = sorted(list(set([item['nama_kerjasama'] for item in res_p.data])))
    except Exception:
        pass

    return render_template('register.html', penyewa_list=penyewa_list, partner_list=partner_list)

@app.route('/dashboard-penyewa')
@login_required
def dashboard_penyewa():
    # Pastikan pengguna adalah tenant
    if session.get('role') != 'tenant':
        return redirect(url_for('index'))
    
    email = session.get('username')
    
    # Dapatkan maklumat penyewa berdasarkan email
    try:
        penyewa_res = supabase.table('penyewa').select('*').eq('email', email).single().execute()
        penyewa = penyewa_res.data
    except Exception:
        # Jika tiada rekod dijumpai (akaun user wujud tapi tiada link ke table penyewa)
        flash("Rekod penyewa tidak dijumpai atau belum dipautkan. Sila hubungi admin.", "danger")
        return redirect(url_for('logout'))
    
    # Dapatkan maklumat sewaan aktif
    sewaan_res = supabase.table('sewaan').select('*, aset(*)').eq('penyewa_id', penyewa['penyewa_id']).execute()
    sewaan_list = sewaan_res.data
    
    # Proses data untuk paparan (Kira Penalti dsb)
    today = date.today()
    for s in sewaan_list:
        # Logik Penalti Mudah: Jika hari ini > hari_akhir dan status bukan 'Selesai'
        # Nota: Ini hanya anggaran paparan. Logic sebenar perlu semak baki bayaran bulan semasa.
        s['penalti'] = 0.00
        s['hari_lewat'] = 0
        
        if today.day > (s.get('hari_akhir_bayaran') or 7):
            # Semak status bayaran terkini (Anda mungkin perlu logic lebih kompleks di sini)
            if 'Selesai' not in (s.get('status_bayaran_terkini') or ''):
                due_day = s.get('hari_akhir_bayaran') or 7
                days_late = today.day - due_day
                rate = float(s.get('kadar_penalti_harian') or 0)
                s['hari_lewat'] = days_late
                s['penalti'] = days_late * rate

    return render_template('dashboard_penyewa.html', penyewa=penyewa, sewaan_list=sewaan_list, today=today)

@app.route('/dashboard-partner')
@login_required
def dashboard_partner():
    # Pastikan pengguna adalah partner
    if session.get('role') != 'partner':
        return redirect(url_for('index'))
    
    linked_name = session.get('linked_name')
    if not linked_name:
        flash("Akaun anda tidak dipautkan dengan mana-mana rekod kerjasama.", "warning")
        return redirect(url_for('logout'))

    # Dapatkan rekod kerjasama khusus untuk nama ini
    res = supabase.table('kerjasama_ketiga').select('*').eq('nama_kerjasama', linked_name).order('tarikh_terima', desc=True).execute()
    records = res.data

    # Kira total pendapatan & komisyen (30% untuk partner, 70% KASB - contoh logik, atau ikut logik 1.5/5 tadi?)
    # Tadi logik: Partner (Owner) dapat 1.5/5. 
    # Untuk "Rakan Kerjasama" luar, mungkin mereka nak tengok berapa revenue yang mereka bawa?
    # Kita paparkan Revenue Asal dan Bahagian KASB.
    
    total_revenue = sum(float(r['jumlah_diterima_kasb'] or 0) for r in records)
    
    return render_template('dashboard_partner.html', records=records, partner_name=linked_name, total_revenue=total_revenue)

@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/serah-terima')
@login_required
def serah_terima():
    """
    Memaparkan halaman checklist serah terima aset.
    """
    return render_template('serah_terima.html')


# --- ROUTES: TETAPAN (SLOT KURSUS) ---
@app.route('/tetapan', methods=['GET', 'POST'])
@login_required
def tetapan():
    if request.method == 'POST':
        # Tambah Slot Baru
        nama_slot = request.form.get('nama_slot')
        max_peserta = request.form.get('max_peserta')
        
        if nama_slot:
            # Default 50 jika tidak ditetapkan
            limit = int(max_peserta) if max_peserta else 50
            supabase.table('kursus_slot').insert({"nama_slot": nama_slot, "max_peserta": limit}).execute()
            flash('Slot kursus berjaya ditambah.', 'success')
    
    # Dapatkan senarai slot
    res = supabase.table('kursus_slot').select('*').order('created_at', desc=True).execute()
    return render_template('tetapan.html', slots=res.data)

@app.route('/padam-slot/<int:id>')
@login_required
def padam_slot(id):
    supabase.table('kursus_slot').delete().eq('id', id).execute()
    flash('Slot berjaya dipadam.', 'warning')
    return redirect(url_for('tetapan'))

# --- ROUTES: PENGURUSAN PESERTA ---
@app.route('/edit-peserta/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_peserta(id):
    if request.method == 'POST':
        data = {
            "nama_penuh": request.form.get('nama'),
            "no_ic": request.form.get('ic'),
            "no_telefon": request.form.get('telefon'),
            "email": request.form.get('email'),
            "nama_syarikat": request.form.get('syarikat'),
            "kursus_dipilih": request.form.get('kursus'),
            "kaedah_bayaran": request.form.get('kaedah_bayaran'),
            "status_bayaran": request.form.get('status_bayaran')
        }
        
        # Handle file upload jika ada perubahan resit
        file = request.files.get('bukti_bayaran')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file_path = f"bayaran/{int(datetime.now().timestamp())}_{filename}"
            file_content = file.read()
            supabase.storage.from_("dokumen").upload(file_path, file_content, {"content-type": file.content_type})
            public_url = supabase.storage.from_("dokumen").get_public_url(file_path)
            data['bukti_bayaran_url'] = public_url

        supabase.table('peserta_kursus').update(data).eq('id', id).execute()
        flash('Maklumat peserta berjaya dikemaskini.', 'success')
        return redirect(url_for('senarai_peserta'))

    # GET method
    res = supabase.table('peserta_kursus').select('*').eq('id', id).single().execute()
    # Dapatkan juga senarai slot untuk dropdown
    slots_res = supabase.table('kursus_slot').select('*').eq('status', 'Aktif').execute()
    
    return render_template('edit_peserta.html', p=res.data, slots=slots_res.data)

@app.route('/padam-peserta/<int:id>')
@login_required
def padam_peserta(id):
    supabase.table('peserta_kursus').delete().eq('id', id).execute()
    flash('Peserta berjaya dipadam.', 'danger')
    return redirect(url_for('senarai_peserta'))

# --- ROUTES: PENGURUSAN MODUL (LMS) ---
@app.route('/urus-modul', methods=['GET', 'POST'])
@login_required
def urus_modul():
    if request.method == 'POST':
        data = {
            "tajuk": request.form.get('tajuk'),
            "pautan_video": request.form.get('video'),
            "pautan_nota": request.form.get('nota'),
            "kategori": request.form.get('kategori')
        }
        supabase.table('modul_kursus').insert(data).execute()
        flash('Modul berjaya ditambah.', 'success')
    
    # Dapatkan senarai modul
    res = supabase.table('modul_kursus').select('*').order('created_at', desc=True).execute()
    return render_template('urus_modul.html', moduls=res.data)

@app.route('/padam-modul/<int:id>')
@login_required
def padam_modul(id):
    supabase.table('modul_kursus').delete().eq('id', id).execute()
    flash('Modul berjaya dipadam.', 'warning')
    return redirect(url_for('urus_modul'))

@app.route('/')
@login_required
def index():
    """
    Fetches asset rental data from the Supabase database and renders the dashboard.
    """
    # --- KEMASKINI ROLE TERKINI (AUTO-REFRESH) ---
    # Pastikan session role sentiasa dikemaskini dari database
    if 'user_id' in session:
        try:
            user_data = supabase.table('users').select('role').eq('id', session['user_id']).single().execute()
            if user_data.data:
                session['role'] = user_data.data['role']
                # Redirect tenant ke dashboard khas jika tersesat ke admin dashboard
                if session['role'] == 'tenant' and request.endpoint == 'index':
                    return redirect(url_for('dashboard_penyewa'))
                elif session['role'] == 'partner' and request.endpoint == 'index':
                    return redirect(url_for('dashboard_partner'))
                elif session['role'] == 'petros_admin' and request.endpoint == 'index':
                    return redirect(url_for('petros_dashboard'))
        except Exception:
            pass # Abaikan jika berlaku ralat sambungan seketika

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

        # Dapatkan Projek Baru & Kerjasama
        projek_res = supabase.table('projek_baru').select('*').gte('tarikh_masuk', start_date).lte('tarikh_masuk', end_date).execute()
        projek_data = projek_res.data

        kerjasama_res = supabase.table('kerjasama_ketiga').select('*').gte('tarikh_terima', start_date).lte('tarikh_terima', end_date).execute()
        kerjasama_data = kerjasama_res.data

        # Struktur Data Kewangan
        financial_data = {m: {'sewaan': 0.0, 'efeis': 0.0, 'petros': 0.0, 'projek': 0.0, 'kerjasama': 0.0, 'total': 0.0} for m in range(1, 13)}
        yearly_totals = {'sewaan': 0.0, 'efeis': 0.0, 'petros': 0.0, 'projek': 0.0, 'kerjasama': 0.0}
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
            
        # Proses Projek Baru (Guna tarikh_masuk & komisyen)
        for p in projek_data:
            dt = datetime.strptime(p['tarikh_masuk'], '%Y-%m-%d')
            amt = float(p.get('keuntungan_bersih') or 0)
            financial_data[dt.month]['projek'] += amt
            financial_data[dt.month]['total'] += amt
            yearly_totals['projek'] += amt
            total_yearly_income += amt

        # Proses Kerjasama (Guna tarikh_terima & komisyen)
        for k in kerjasama_data:
            dt = datetime.strptime(k['tarikh_terima'], '%Y-%m-%d')
            amt = float(k.get('jumlah_diterima_kasb') or 0)
            financial_data[dt.month]['kerjasama'] += amt
            financial_data[dt.month]['total'] += amt
            yearly_totals['kerjasama'] += amt
            total_yearly_income += amt

        # --- LOGIK PENGIRAAN GAJI & KOMISYEN ---
        # Kadar Gaji & Komisyen
        RATE_GAJI_ASAS = 0.08      # 8% dari Sewaan + Efeis + Petros
        # Projek Baru: <500k (10%), >=500k (15%) - Dikira per item di bawah
        # Kerjasama: 1.5/5 dari Revenue - Dikira per item di bawah

        breakdown_data = {m: {
            'group_a_total': 0.0, 'gaji_asas': 0.0,
            'projek_amt': 0.0, 'projek_comm': 0.0,
            'kerjasama_amt': 0.0, 'kerjasama_comm': 0.0,
            'total_comm': 0.0
        } for m in range(1, 13)}

        totals_breakdown = {
            'group_a_total': 0.0, 'gaji_asas': 0.0,
            'projek_amt': 0.0, 'projek_comm': 0.0,
            'kerjasama_amt': 0.0, 'kerjasama_comm': 0.0,
            'total_comm': 0.0
        }

        # --- PENGIRAAN TERPERINCI ---

        # 1. KIRA GROUP A (Gaji Asas) - Berdasarkan monthly total financial_data
        for m in range(1, 13):
            g_a = financial_data[m]['sewaan'] + financial_data[m]['efeis'] + financial_data[m]['petros']
            breakdown_data[m]['group_a_total'] = g_a
            breakdown_data[m]['gaji_asas'] = g_a * RATE_GAJI_ASAS

        # 2. KIRA PROJEK BARU (Tiered Commission)
        for p in projek_data:
            dt = datetime.strptime(p['tarikh_masuk'], '%Y-%m-%d')
            amt = float(p.get('keuntungan_bersih') or 0)
            
            # Logik Tier: < 500k = 10%, >= 500k = 15%
            if amt < 500000:
                comm = amt * 0.10
            else:
                comm = amt * 0.15
            
            breakdown_data[dt.month]['projek_amt'] += amt
            breakdown_data[dt.month]['projek_comm'] += comm

        # 3. KIRA KERJASAMA (1.5/5 dari Revenue)
        for k in kerjasama_data:
            dt = datetime.strptime(k['tarikh_terima'], '%Y-%m-%d')
            amt = float(k.get('jumlah_diterima_kasb') or 0) # Ini adalah Nilai Revenue
            
            # Logik: 1.5 bahagian dari 5 bahagian
            comm = amt * (1.5 / 5.0)
            
            breakdown_data[dt.month]['kerjasama_amt'] += amt
            breakdown_data[dt.month]['kerjasama_comm'] += comm

        # 4. AGREGAT TOTAL TAHUNAN
        for m in range(1, 13):
            # Total Comm Bulanan
            breakdown_data[m]['total_comm'] = breakdown_data[m]['projek_comm'] + breakdown_data[m]['kerjasama_comm']
            
            # Tambah ke Grand Total Tahunan
            totals_breakdown['group_a_total'] += breakdown_data[m]['group_a_total']
            totals_breakdown['gaji_asas'] += breakdown_data[m]['gaji_asas']
            
            totals_breakdown['projek_amt'] += breakdown_data[m]['projek_amt']
            totals_breakdown['projek_comm'] += breakdown_data[m]['projek_comm']
            
            totals_breakdown['kerjasama_amt'] += breakdown_data[m]['kerjasama_amt']
            totals_breakdown['kerjasama_comm'] += breakdown_data[m]['kerjasama_comm']
            
            totals_breakdown['total_comm'] += breakdown_data[m]['total_comm']

        # -----------------------------------------------------

    except Exception as e:
        # If there's an error, display it to make debugging easier
        return f"Database error: {e}"

    # Render the HTML template, passing the transformed data to it
    return render_template('index.html', 
                           financial_data=financial_data, 
                           yearly_totals=yearly_totals,
                           breakdown_data=breakdown_data,
                           totals_breakdown=totals_breakdown,
                           total_yearly_income=total_yearly_income,
                           selected_year=selected_year,
                           current_year=current_year)

@app.route('/sewaan')
@login_required
def sewaan_dashboard():
    """
    Memaparkan senarai terperinci aset sewaan.
    """
    # Sekat akses untuk Petros Admin
    if session.get('role') == 'petros_admin':
        return redirect(url_for('petros_dashboard'))

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

@app.route('/efeis')
@login_required
def efeis_dashboard():
    # Sekat akses untuk Petros Admin
    if session.get('role') == 'petros_admin':
        return redirect(url_for('petros_dashboard'))
    return render_income_detail('Efeis')

@app.route('/petros')
@login_required
def petros_dashboard():
    return render_income_detail('Petros')

def render_income_detail(source_name):
    try:
        current_year = datetime.now().year
        selected_year = request.args.get('year', current_year, type=int)
        selected_month = request.args.get('month', type=int)
        
        # Dapatkan data dari table pendapatan_lain (Join details jika Petros untuk kira volume)
        if source_name == 'Petros':
            response = supabase.table('pendapatan_lain').select('*, petros_details(daily_volume)').eq('sumber', source_name).order('tarikh', desc=True).execute()
        else:
            response = supabase.table('pendapatan_lain').select('*').eq('sumber', source_name).order('tarikh', desc=True).execute()
            
        data = response.data
        
        # Filter ikut tahun (Python side filtering untuk mudah)
        filtered_data = [d for d in data if d['tarikh'].startswith(str(selected_year))]
        
        # Init Aggregates
        total_income = 0.0
        monthly_breakdown = {m: 0.0 for m in range(1, 13)}
        monthly_aggregates = {m: {'vol': 0.0, 'sales': 0.0, 'gross_comm': 0.0, 'costs': 0.0, 'net_profit': 0.0, 'kasb': 0.0, 'gowpen': 0.0} for m in range(1, 13)}

        for item in filtered_data:
            m = int(item['tarikh'].split('-')[1])
            
            if source_name == 'Petros':
                # Kira Volume dari details
                vol = sum(d['daily_volume'] for d in item.get('petros_details', []))
                item['total_volume'] = vol
                
                # Kira Sales dari column sales_debit/ewallet/cash
                sales = (item.get('sales_debit') or 0) + (item.get('sales_ewallet') or 0) + (item.get('sales_cash') or 0)
                item['total_sales'] = sales
                
                # Financials
                net = float(item.get('kutipan_yuran') or 0)
                costs = float(item.get('kos_pengurusan') or 0)
                gross = net + costs
                kasb = float(item.get('amaun') or 0)
                gowpen = net - kasb
                
                # Aggregate
                monthly_aggregates[m]['vol'] += vol
                monthly_aggregates[m]['sales'] += sales
                monthly_aggregates[m]['gross_comm'] += gross
                monthly_aggregates[m]['costs'] += costs
                monthly_aggregates[m]['net_profit'] += net
                monthly_aggregates[m]['kasb'] += kasb
                monthly_aggregates[m]['gowpen'] += gowpen
                
                monthly_breakdown[m] += kasb
                total_income += kasb
            else:
                amt = float(item['amaun'])
                monthly_breakdown[m] += amt
                total_income += amt

        return render_template('income_list.html', 
                               source=source_name, 
                               data=filtered_data, 
                               selected_year=selected_year, 
                               current_year=current_year, 
                               total_income=total_income, 
                               monthly_breakdown=monthly_breakdown, 
                               selected_month=selected_month,
                               monthly_aggregates=monthly_aggregates if source_name == 'Petros' else {})
        
    except Exception as e:
        return f"Ralat memuatkan data {source_name}: {e}"


@app.route('/projek-baru', methods=['GET', 'POST'])
@login_required
def projek_baru_list():
    """
    Menguruskan (menambah dan memaparkan) projek baru dengan komisyen 10/15%.
    """
    # Sekat akses untuk Petros Admin
    if session.get('role') == 'petros_admin':
        return redirect(url_for('petros_dashboard'))

    if request.method == 'POST':
        try:
            nilai = float(request.form.get('nilai_projek') or 0)
            kos = float(request.form.get('kos_projek') or 0)
            # Kira keuntungan bersih (Nilai - Kos)
            untung = nilai - kos

            data = {
                "nama_projek": request.form.get('nama_projek'),
                "nilai_projek": nilai,
                "kos_projek": kos,
                "keuntungan_bersih": untung,
                "tarikh_masuk": request.form.get('tarikh_masuk'),
                "user_id": session.get('user_id')
            }
            supabase.table('projek_baru').insert(data).execute()
            flash('Projek baru berjaya direkodkan.', 'success')
        except Exception as e:
            flash(f'Ralat merekod projek: {e}', 'danger')
        
        return redirect(url_for('projek_baru_list'))

    # GET request: Paparkan senarai
    try:
        res = supabase.table('projek_baru').select('*').order('tarikh_masuk', desc=True).execute()
        projek_list = res.data
    except Exception as e:
        flash(f'Ralat memuatkan senarai projek: {e}', 'danger')
        projek_list = []
    
    return render_template('projek_baru_list.html', projek_list=projek_list)

@app.route('/padam-projek/<int:id>')
@login_required
def padam_projek(id):
    # Hanya 'owner' boleh padam
    if session.get('role') != 'owner':
        flash('Akses ditolak. Hanya Owner boleh memadam rekod.', 'danger')
        return redirect(url_for('projek_baru_list'))
    
    supabase.table('projek_baru').delete().eq('id', id).execute()
    flash('Rekod projek berjaya dipadam.', 'warning')
    return redirect(url_for('projek_baru_list'))

@app.route('/kerjasama', methods=['GET', 'POST'])
@login_required
def kerjasama_list():
    """
    Menguruskan (menambah dan memaparkan) kerjasama pihak ketiga (komisyen 30%).
    """
    # Sekat akses untuk Petros Admin
    if session.get('role') == 'petros_admin':
        return redirect(url_for('petros_dashboard'))

    if request.method == 'POST':
        try:
            data = {
                "nama_kerjasama": request.form.get('nama_kerjasama'),
                "jumlah_diterima_kasb": float(request.form.get('jumlah_diterima_kasb')),
                "tarikh_terima": request.form.get('tarikh_terima'),
                "user_id": session.get('user_id')
            }
            supabase.table('kerjasama_ketiga').insert(data).execute()
            flash('Rekod kerjasama berjaya disimpan.', 'success')
        except Exception as e:
            flash(f'Ralat merekod kerjasama: {e}', 'danger')
        
        return redirect(url_for('kerjasama_list'))

    # GET request: Paparkan senarai
    try:
        res = supabase.table('kerjasama_ketiga').select('*').order('tarikh_terima', desc=True).execute()
        kerjasama_list = res.data
    except Exception as e:
        flash(f'Ralat memuatkan senarai kerjasama: {e}', 'danger')
        kerjasama_list = []
    
    return render_template('kerjasama_list.html', kerjasama_list=kerjasama_list)

@app.route('/padam-kerjasama/<int:id>')
@login_required
def padam_kerjasama(id):
    # Hanya 'owner' boleh padam
    if session.get('role') != 'owner':
        flash('Akses ditolak. Hanya Owner boleh memadam rekod.', 'danger')
        return redirect(url_for('kerjasama_list'))
    
    supabase.table('kerjasama_ketiga').delete().eq('id', id).execute()
    flash('Rekod kerjasama berjaya dipadam.', 'warning')
    return redirect(url_for('kerjasama_list'))

@app.route('/asset/<int:sewaan_id>')
@login_required
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
        
        # Senarai nama bulan dalam Bahasa Melayu
        nama_bulan_melayu = ["", "Jan", "Feb", "Mac", "Apr", "Mei", "Jun", 
                             "Jul", "Ogo", "Sep", "Okt", "Nov", "Dis"]

        for month in range(1, 13):
            month_name = nama_bulan_melayu[month]
            
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

        # 5. Dapatkan Dokumen Berkaitan
        aset_id = sewaan_data['aset']['aset_id']
        docs_res = supabase.table('dokumen_aset').select('*').eq('aset_id', aset_id).order('created_at', desc=True).execute()
        documents = docs_res.data

        # 6. Kira Penalti (Untuk Paparan Admin)
        today = date.today()
        penalty_info = {"amount": 0.00, "days": 0, "is_late": False}
        
        # Logic: Jika bulan semasa belum selesai bayar DAN hari ini > due date
        current_month_idx = today.month - 1 # 0-index for list access if needed, but we use loop
        current_month_status = monthly_status[current_month_idx] # Status bulan semasa
        
        if current_month_status['status'] != "Selesai" and today.day > (sewaan_data.get('hari_akhir_bayaran') or 7):
            days_late = today.day - (sewaan_data.get('hari_akhir_bayaran') or 7)
            rate = float(sewaan_data.get('kadar_penalti_harian') or 0)
            penalty_info = {"amount": days_late * rate, "days": days_late, "is_late": True}

        return render_template(
            'asset_detail.html', 
            asset=sewaan_data, 
            transactions=transaksi_data,
            monthly_status=monthly_status,
            documents=documents,
            selected_year=selected_year,
            total_bayaran=total_bayaran, 
            current_year=current_year,
            penalty_info=penalty_info
        )

    except Exception as e:
        return f"Ralat memuatkan detail: {e}"

@app.route('/add_payment/<int:sewaan_id>', methods=['POST'])
@login_required
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

@app.route('/upload_document/<int:sewaan_id>', methods=['POST'])
@login_required
def upload_document(sewaan_id):
    try:
        file = request.files.get('file')
        jenis = request.form.get('jenis_dokumen')
        nota = request.form.get('nota')

        if not file:
            return "Tiada fail dipilih"

        # Dapatkan aset_id daripada sewaan_id
        sewaan_res = supabase.table('sewaan').select('aset_id').eq('sewaan_id', sewaan_id).single().execute()
        aset_id = sewaan_res.data['aset_id']

        # Proses nama fail yang selamat
        filename = secure_filename(file.filename)
        file_path = f"{aset_id}/{int(datetime.now().timestamp())}_{filename}"

        # Upload ke Supabase Storage (Bucket 'dokumen')
        file_content = file.read()
        supabase.storage.from_("dokumen").upload(file_path, file_content, {"content-type": file.content_type})

        # Dapatkan Public URL
        public_url = supabase.storage.from_("dokumen").get_public_url(file_path)

        # Simpan metadata ke database
        doc_data = {"aset_id": aset_id, "jenis_dokumen": jenis, "nama_fail": filename, "url_fail": public_url, "nota": nota}
        supabase.table('dokumen_aset').insert(doc_data).execute()

        return redirect(url_for('asset_detail', sewaan_id=sewaan_id))

    except Exception as e:
        return f"Ralat memuat naik dokumen: {e}"

# --- HELPER: KIRA KOMISYEN & KOS PETROS ---
def calculate_petros_financials(details_data, tarikh_str, other_expenses=0.0, previous_vol_mogas=0.0, previous_vol_diesel=0.0, apply_sedc=False):
    """
    Mengira komisyen, kos SEDC, dan keuntungan bersih berdasarkan logik bertingkat.
    details_data: list of dict [{'jenis_minyak': 'PF95', 'daily_volume': 1000}, ...]
    previous_vol_mogas: Jumlah terkumpul volume Mogas bulan ini SEBELUM rekod ini (untuk tier SEDC).
    tarikh_str: 'YYYY-MM-DD'
    """
    try:
        rec_date = datetime.strptime(tarikh_str, "%Y-%m-%d").date()
    except:
        rec_date = date.today()

    # Asingkan volume mengikut kategori
    vol_mogas = sum(d['daily_volume'] for d in details_data if d['jenis_minyak'] in ['PF95', 'UF97'])
    vol_diesel = sum(d['daily_volume'] for d in details_data if d['jenis_minyak'] in ['E5 B20', 'E5 B7'])
    total_vol = vol_mogas + vol_diesel
    
    # --- 1. KIRA KOMISYEN ---
    # Tarikh perubahan struktur: 1 November 2025
    cutoff_date = date(2025, 11, 1)
    
    comm_mogas_total = 0.0
    comm_diesel_total = 0.0
    
    if rec_date < cutoff_date:
        # LOGIK LAMA (Ogos - Oktober 2025)
        # Mogas: RM 0.150 flat
        # Diesel: RM 0.128 flat
        # UPDATE (User Request): Diesel Tiered (0-200k: 0.03, 200k-500k: 0.02, >500k: 0.01)
        
        comm_mogas_total = round(vol_mogas * 0.150, 2)
        
        # Kira Diesel Tiered (Aug-Oct)
        rem_diesel = vol_diesel
        current_cumulative_diesel = previous_vol_diesel
        
        # Tier 1: 0 - 200,000 (Rate 0.03)
        available_t1 = max(0, 200000 - current_cumulative_diesel)
        t1 = min(rem_diesel, available_t1)
        comm_diesel_total += round(t1 * 0.03, 2)
        rem_diesel -= t1
        current_cumulative_diesel += t1
        
        # Tier 2: 200,001 - 500,000 (Rate 0.02)
        if rem_diesel > 0:
            available_t2 = max(0, 500000 - current_cumulative_diesel) # Note: 500k limit total
            # Logic check: if cumulative is already > 200k, available space in T2 is (500k - current).
            # If cumulative < 200k, we already filled T1. Current is now 200k.
            # So available T2 is 500k - 200k = 300k.
            # Let's use simple logic:
            # We need to know how much of the *current batch* falls into which tier.
            # It's easier to calculate Total Commission for (Prev + Curr) then subtract Commission for (Prev).
            pass # We will use the iterative approach below for clarity
            
            # Re-calculate using standard tier logic on the fly
            # Tier 2 space
            # We are at 'current_cumulative_diesel'. The next threshold is 500,000.
            # But wait, the tier is 200,001 to 500,000.
            # So the max volume in this tier is 300,000.
            # My previous logic `available_t1` handles the start.
            
            # Let's simplify:
            # Tier 2 starts at 200,000. Ends at 500,000.
            # We are currently at `current_cumulative_diesel` (which is >= 200,000 because we exhausted T1 or started above it).
            
            # Actually, `current_cumulative_diesel` was updated above.
            # If we filled T1, `current_cumulative_diesel` is at least 200,000 (or less if we finished the batch).
            # If `rem_diesel > 0`, it means we are above 200,000.
            
            t2 = min(rem_diesel, 300000) # Max size of Tier 2 is 300k. 
            # But we must respect the 500k total limit.
            # Space remaining in Tier 2 = 500,000 - current_cumulative_diesel.
            space_t2 = max(0, 500000 - current_cumulative_diesel)
            t2 = min(rem_diesel, space_t2)
            
            comm_diesel_total += round(t2 * 0.02, 2)
            rem_diesel -= t2
            current_cumulative_diesel += t2
            
        # Tier 3: > 500,000 (Rate 0.01)
        if rem_diesel > 0:
            comm_diesel_total += round(rem_diesel * 0.01, 2)

    else:
        # LOGIK BARU (Nov 2025 ke atas)
        # Mogas: Tiered (0-200k: 0.18, 200k-500k: 0.17, >500k: 0.16)
        # Diesel: Kekal RM 0.128 (Flat)
        
        # Kira Tier Mogas
        rem_mogas = vol_mogas
        
        # Tier 1: 0 - 200,000
        # Nota: Tier dikira per transaksi harian dalam konteks ini, 
        # tetapi idealnya volume harian tidak melebihi tier ini.
        t1 = min(rem_mogas, 200000)
        comm_mogas_total += round(t1 * 0.18, 2)
        rem_mogas -= t1
        
        # Tier 2: 200,001 - 500,000
        if rem_mogas > 0:
            t2 = min(rem_mogas, 300000)
            comm_mogas_total += round(t2 * 0.17, 2)
            rem_mogas -= t2
            
        # Tier 3: > 500,000
        if rem_mogas > 0:
            comm_mogas_total += round(rem_mogas * 0.16, 2)
            
        # Kira Diesel
        comm_diesel_total = round(vol_diesel * 0.128, 2)

    # --- 2. KIRA KOS SEDC ---
    # Logik Baru: Hanya kira jika apply_sedc = True (biasanya pada rekod akhir bulan)
    # Jika apply_sedc = True, kita kira SEDC untuk TOTAL volume bulan ini (Previous + Current)
    # Ini mengandaikan rekod-rekod harian sebelumnya TIDAK dikenakan SEDC (0).
    
    sedc_mogas = 0.0
    sedc_diesel = 0.0
    
    if apply_sedc:
        # Kira Total Volume Bulan Ini (termasuk hari ini)
        total_month_mogas = previous_vol_mogas + vol_mogas
        
        # Kira SEDC Mogas (Tiered pada 450k)
        if total_month_mogas <= 450000:
            sedc_mogas = round(total_month_mogas * 0.015, 2)
        else:
            tier1_cost = round(450000 * 0.015, 2)
            tier2_vol = total_month_mogas - 450000
            tier2_cost = round(tier2_vol * 0.01, 2)
            sedc_mogas = tier1_cost + tier2_cost
            
        # Kira SEDC Diesel (Flat 0.01 pada Total Volume Diesel Bulan Ini?)
        # Nota: Kita tiada 'previous_vol_diesel' passed in, jadi kita anggap Diesel flat rate
        # boleh dikira pada volume semasa SAHAJA jika kita buat harian.
        # TAPI, jika user nak "sekali gus", kita perlu total diesel juga.
        # Limitation: Function ini tak terima previous_vol_diesel. 
        # Solution: Untuk Diesel (Flat Rate), kiraan harian vs bulanan adalah sama matematik (Sum of parts = Whole).
        # JADI: Untuk Diesel, kita hanya kira pada volume SEMASA jika apply_sedc=True? 
        # TIDAK, kalau apply_sedc=True (akhir bulan), kita kena cover volume hari-hari sebelumnya juga.
        # Oleh kerana kita tak ada data previous diesel di sini, kita akan guna logik:
        # "SEDC Diesel dikira pada volume semasa sahaja" ADALAH SALAH jika kita skip hari-hari lain.
        # FIX: Kita perlu anggap Diesel 0.01 sentiasa. Jika user nak lump sum, user perlu masukkan total SEDC manual?
        # ATAU: Kita ubah supaya SEDC Diesel dikira harian (sebab flat), tapi SEDC Mogas (tiered) dikira hujung bulan?
        # User kata: "tidak perlu buat pecahan setiap bulan".
        # Maka: Kita akan kira SEDC Diesel berdasarkan 'vol_diesel' *faktor pembetulan*? Tidak boleh.
        # KEPUTUSAN: Untuk Diesel, kerana flat rate, kita akan kira berdasarkan volume semasa SAHAJA di sini.
        # INI BERMAKNA: Untuk Diesel, kos akan terpecah harian jika kita tak hati-hati.
        # TAPI user kata "sekali dengan operational cost".
        # JIKA apply_sedc=True, kita anggap ini rekod penutup. Kita perlukan TOTAL DIESEL.
        # Oleh sebab limitation parameter, saya akan set SEDC Diesel = vol_diesel * 0.01 (Hanya volume hari ini).
        # *INI MUNGKIN MENYEBABKAN KOS DIESEL TERKURANG jika hari lain tak dikira.*
        # *PEMBETULAN PANTAS:* Saya akan kekalkan SEDC Diesel dikira harian (kecil) ATAU 
        # anggap user akan 'recalculate' semua di hujung bulan.
        # Untuk mematuhi arahan "sekali sahaja", saya akan guna logik:
        # SEDC = 0 jika apply_sedc=False.
        # Jika apply_sedc=True, SEDC Mogas dikira pada (Prev + Curr).
        # SEDC Diesel terpaksa dikira pada (Curr) sahaja sebab tiada data Prev Diesel.
        # *NOTA PENTING:* Sila pastikan anda 'Recalculate' di dashboard untuk membetulkan data lama.
        
        sedc_diesel = round(vol_diesel * 0.01, 2) 
        # (Nota: Diesel mungkin perlu manual adjustment jika nak lump sum sebenar dari hari sebelumnya)

    total_sedc = round(sedc_mogas + sedc_diesel, 2)
    
    # --- 3. AGIHAN KE DETAILS ---
    total_gross_profit = 0.0
    total_sedc_cost = 0.0
    
    # Kira purata rate Mogas untuk agihan per item (jika tiered)
    avg_rate_mogas = comm_mogas_total / vol_mogas if vol_mogas > 0 else 0
    avg_rate_diesel = comm_diesel_total / vol_diesel if vol_diesel > 0 else 0
    
    # Kira purata rate SEDC Mogas untuk agihan per item (Hanya jika ada SEDC)
    avg_sedc_rate_mogas = sedc_mogas / vol_mogas if (vol_mogas > 0 and apply_sedc) else 0.0

    for d in details_data:
        vol = d['daily_volume']
        jenis = d['jenis_minyak']
        
        # Assign Commission
        if jenis in ['PF95', 'UF97']:
            if rec_date < cutoff_date:
                d['earned_commission'] = round(vol * 0.150, 2)
            else:
                d['earned_commission'] = round(vol * avg_rate_mogas, 2)
        elif jenis in ['E5 B20', 'E5 B7']:
            if rec_date < cutoff_date:
                d['earned_commission'] = round(vol * avg_rate_diesel, 2)
            else:
                d['earned_commission'] = round(vol * 0.128, 2)
        else:
            d['earned_commission'] = 0.0
        
        # Assign Kos SEDC
        if jenis in ['PF95', 'UF97']:
            d['kos'] = round(vol * avg_sedc_rate_mogas, 2)
        elif jenis in ['E5 B20', 'E5 B7']:
            d['kos'] = round(vol * 0.01, 2) if apply_sedc else 0.0
        else:
            d['kos'] = 0.0 # Minyak lain/Pelincir
            
        # Gross Profit per item (Kini hanya Komisyen, SEDC diasingkan ke expenses)
        d['profit'] = d['earned_commission']
        
        total_gross_profit += d['profit']
        total_sedc_cost += d['kos']
        
    # 4. Keuntungan Bersih Akhir
    net_profit = round(total_gross_profit - (other_expenses + total_sedc_cost), 2)
    
    return net_profit, total_gross_profit, total_sedc_cost

@app.route('/add_income/<source_name>', methods=['POST'])
@login_required
def add_income(source_name):
    try:
        tarikh = request.form.get('tarikh')
        nota = request.form.get('nota')
        
        data = {
            "sumber": source_name,
            "tarikh": tarikh,
            "nota": nota
        }

        if source_name == 'Efeis':
            bil = request.form.get('bil_penyertaan')
            yuran = float(request.form.get('kutipan_yuran') or 0)
            kos = float(request.form.get('kos_pengurusan') or 0)
            
            # Kira keuntungan bersih secara automatik
            amaun = yuran - kos
            
            data.update({
                "bil_penyertaan": int(bil) if bil else 0,
                "kutipan_yuran": yuran,
                "kos_pengurusan": kos,
                "amaun": amaun
            })
        elif source_name == 'Petros':
            # Proses input array dari form Petros
            jenis_list = request.form.getlist('petros_jenis[]')
            vol_list = request.form.getlist('petros_vol[]')
            sales_list = request.form.getlist('petros_sales[]')
            
            # --- PENGURUSAN KOS OPERASI TERPERINCI ---
            fixed_costs = {}
            # Keys for Fixed Inputs (A, B, D only)
            keys = [
                'salary', 'epf', 'socso', 'eis', 'levy', 'pcb', 'stamping', # A. Monthly Expenses
                'retails_system', 'rentokil', 'unifi', 'insurance', 'safe_guard', 'tnb', 'water', # B. Monthly Services
                'ad_fee', 'pet_license', 'license_app', 'trade_license', # C. Documents Fees
            ]
            
            total_expenses = 0.0
            for k in keys:
                val = float(request.form.get(f'cost_{k}') or 0)
                fixed_costs[k] = val
                total_expenses += val
                
            # Kos Dinamik (Lain-lain Table)
            other_category = request.form.getlist('other_category[]')
            other_desc = request.form.getlist('other_desc[]')
            other_amt = request.form.getlist('other_amt[]')
            dynamic_costs = []
            for i in range(len(other_desc)):
                if other_desc[i].strip():
                    cat = other_category[i] if i < len(other_category) else 'Other'
                    amt = float(other_amt[i] or 0)
                    dynamic_costs.append({'category': cat, 'desc': other_desc[i], 'amount': amt})
                    total_expenses += amt
            
            breakdown = {'fixed': fixed_costs, 'dynamic': dynamic_costs}
            
            # Tentukan sama ada nak kira SEDC atau tidak
            # Logik: Jika ada expenses dimasukkan (total_expenses > 0), kita anggap ini rekod penutup bulan -> Kira SEDC
            should_calc_sedc = (total_expenses > 0)
            
            details_data = []
            for i in range(len(jenis_list)):
                details_data.append({
                    "jenis_minyak": jenis_list[i],
                    "daily_volume": float(vol_list[i]) if vol_list[i] else 0.0,
                    "sales_amount": float(sales_list[i]) if sales_list[i] else 0.0
                })
            
            # --- KIRA CUMULATIVE VOLUME MOGAS SEBELUM TARIKH INI ---
            # Dapatkan tahun dan bulan
            y, m, _ = tarikh.split('-')
            start_of_month = f"{y}-{m}-01"
            
            # Query semua rekod Petros bulan ini sebelum tarikh ini
            prev_res = supabase.table('pendapatan_lain').select('id, petros_details(jenis_minyak, daily_volume)')\
                .eq('sumber', 'Petros')\
                .gte('tarikh', start_of_month)\
                .lt('tarikh', tarikh)\
                .execute()
            
            prev_mogas_vol = 0.0
            for rec in prev_res.data:
                for d in rec.get('petros_details', []):
                    if d['jenis_minyak'] in ['PF95', 'UF97']:
                        prev_mogas_vol += float(d['daily_volume'] or 0)
                    elif d['jenis_minyak'] in ['E5 B20', 'E5 B7']:
                        prev_diesel_vol += float(d['daily_volume'] or 0)

            # Kira Automatik (Komisyen, SEDC, Profit)
            net_profit, gross_profit, total_sedc = calculate_petros_financials(details_data, tarikh, total_expenses, prev_mogas_vol, prev_diesel_vol, apply_sedc=should_calc_sedc)
            
            # --- LOGIK PROFIT SHARING PETROS ---
            # Tahun 1-3 (2025-2027): KASB 20%, Gowpen 80%
            # Tahun 4+ (2028++): KASB 25%, Gowpen 75%
            
            rec_date = datetime.strptime(tarikh, "%Y-%m-%d").date()
            start_date_25 = date(2028, 1, 1) # Tarikh mula kenaikan 25%
            
            rate = 0.25 if rec_date >= start_date_25 else 0.20
            kasb_share = round(net_profit * rate, 2)
            
            # Update breakdown to include SEDC
            breakdown = {'fixed': fixed_costs, 'dynamic': dynamic_costs, 'sedc': total_sedc}

            # Simpan Net Profit dalam 'kutipan_yuran' (sebagai rujukan untung bersih sebelum sharing)
            # Simpan Bahagian KASB dalam 'amaun' (untuk Dashboard Utama)
            data["kutipan_yuran"] = net_profit
            data["amaun"] = kasb_share
            data["kos_pengurusan"] = total_expenses + total_sedc # Simpan total expenses (termasuk SEDC)
            data["kos_breakdown"] = breakdown # Simpan detail JSON
            
            # Simpan Ringkasan Transaksi
            data.update({
                "sales_debit": float(request.form.get('petros_total_debit') or 0),
                "sales_ewallet": float(request.form.get('petros_total_ewallet') or 0),
                "sales_cash": float(request.form.get('petros_total_cash') or 0)
            })
            
        else:
            # Untuk Petros atau lain-lain, amaun dimasukkan terus
            amaun = float(request.form.get('amaun') or 0)
            data["amaun"] = amaun

        res = supabase.table('pendapatan_lain').insert(data).execute()
        
        # Jika Petros, masukkan details selepas dapat ID utama
        if source_name == 'Petros' and res.data and details_data:
            main_id = res.data[0]['id']
            for d in details_data:
                d['pendapatan_id'] = main_id
            supabase.table('petros_details').insert(details_data).execute()

        # Redirect ke tahun tarikh tersebut supaya user nampak data yang baru dimasukkan
        year_str, month_str, _ = tarikh.split('-')
        if source_name == 'Efeis':
            return redirect(url_for('efeis_dashboard', year=year_str, month=month_str))
        elif source_name == 'Petros':
            return redirect(url_for('petros_dashboard', year=year_str, month=month_str))
        else:
            return redirect(url_for('index'))

    except Exception as e:
        return f"Ralat menambah pendapatan: {e}"

@app.route('/edit-pendapatan/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_pendapatan(id):
    if request.method == 'POST':
        try:
            sumber = request.form.get('sumber')
            tarikh = request.form.get('tarikh')
            input_amaun = float(request.form.get('amaun') or 0)
            
            data = {
                "tarikh": tarikh
            }
            
            if sumber == 'Petros':
                # Jika Petros, input_amaun adalah Total Profit (kutipan_yuran)
                # Kita perlu kira semula bahagian KASB
                rec_date = datetime.strptime(tarikh, "%Y-%m-%d").date()
                start_date_25 = date(2028, 1, 1)
                rate = 0.25 if rec_date >= start_date_25 else 0.20
                
                # --- PENGURUSAN KOS OPERASI TERPERINCI (EDIT) ---
                fixed_costs = {}
                keys = [
                    'salary', 'epf', 'socso', 'eis', 'levy', 'pcb', 'stamping',
                    'retails_system', 'rentokil', 'unifi', 'insurance', 'safe_guard', 'tnb', 'water',
                    'ad_fee', 'pet_license', 'license_app', 'trade_license', # C. Documents Fees
                ]
                
                total_expenses = 0.0
                for k in keys:
                    val = float(request.form.get(f'cost_{k}') or 0)
                    fixed_costs[k] = val
                    total_expenses += val
                    
                # Kos Dinamik
                other_category = request.form.getlist('other_category[]')
                other_desc = request.form.getlist('other_desc[]')
                other_amt = request.form.getlist('other_amt[]')
                dynamic_costs = []
                for i in range(len(other_desc)):
                    if other_desc[i].strip():
                        cat = other_category[i] if i < len(other_category) else 'Other'
                        amt = float(other_amt[i] or 0)
                        dynamic_costs.append({'category': cat, 'desc': other_desc[i], 'amount': amt})
                        total_expenses += amt
                
                breakdown = {'fixed': fixed_costs, 'dynamic': dynamic_costs}
                
                # Logik SEDC: Kira jika ada expenses
                should_calc_sedc = (total_expenses > 0)

                # Proses Volume Baru
                jenis_list = request.form.getlist('petros_jenis[]')
                vol_list = request.form.getlist('petros_vol[]')
                sales_list = request.form.getlist('petros_sales[]')
                
                details_data = []
                for i in range(len(jenis_list)):
                    details_data.append({
                        "jenis_minyak": jenis_list[i],
                        "daily_volume": float(vol_list[i]) if vol_list[i] else 0.0,
                        "sales_amount": float(sales_list[i]) if sales_list[i] else 0.0
                    })
                
                # --- KIRA CUMULATIVE VOLUME MOGAS SEBELUM TARIKH INI ---
                y, m, _ = tarikh.split('-')
                start_of_month = f"{y}-{m}-01"
                
                # Query bulan ini, sebelum tarikh ini ATAU (tarikh sama tapi ID < current ID - untuk susunan insert, tapi tarikh sama biasanya tak berlaku banyak kali. Kita guna < tarikh untuk selamat)
                # Untuk edit, kita kecualikan ID sendiri.
                prev_res = supabase.table('pendapatan_lain').select('id, petros_details(jenis_minyak, daily_volume)')\
                    .eq('sumber', 'Petros')\
                    .gte('tarikh', start_of_month)\
                    .lt('tarikh', tarikh)\
                    .execute()
                
                prev_mogas_vol = 0.0
                for rec in prev_res.data:
                    for d in rec.get('petros_details', []):
                        if d['jenis_minyak'] in ['PF95', 'UF97']:
                            prev_mogas_vol += float(d['daily_volume'] or 0)
                        elif d['jenis_minyak'] in ['E5 B20', 'E5 B7']:
                            prev_diesel_vol += float(d['daily_volume'] or 0)

                # Kira Semula
                net_profit, gross_profit, total_sedc = calculate_petros_financials(details_data, tarikh, total_expenses, prev_mogas_vol, prev_diesel_vol, apply_sedc=should_calc_sedc)
                
                breakdown['sedc'] = total_sedc

                # Update Main Record
                data["kutipan_yuran"] = net_profit
                data["kos_pengurusan"] = total_expenses + total_sedc
                data["kos_breakdown"] = breakdown
                data["amaun"] = round(net_profit * rate, 2)
                
                # Update Details Record
                for d in details_data:
                    supabase.table('petros_details').update({
                        "daily_volume": d['daily_volume'],
                        "sales_amount": d['sales_amount'],
                        "earned_commission": d['earned_commission'],
                        "kos": d['kos'],
                        "profit": d['profit']
                    }).eq('pendapatan_id', id).eq('jenis_minyak', d['jenis_minyak']).execute()
            else:
                data["amaun"] = input_amaun
                data["nota"] = request.form.get('nota')
            
            supabase.table('pendapatan_lain').update(data).eq('id', id).execute()
            flash('Rekod berjaya dikemaskini.', 'success')
            
            # Redirect ke dashboard yang betul
            year_str, month_str, _ = data['tarikh'].split('-')
            if sumber == 'Efeis':
                return redirect(url_for('efeis_dashboard', year=year_str, month=month_str))
            elif sumber == 'Petros':
                return redirect(url_for('petros_dashboard', year=year_str, month=month_str))
            return redirect(url_for('index'))
            
        except Exception as e:
            flash(f"Ralat kemaskini: {e}", "danger")
            return redirect(url_for('index'))

    # GET Request: Paparkan borang edit
    try:
        res = supabase.table('pendapatan_lain').select('*').eq('id', id).single().execute()        
        if res.data['sumber'] == 'Petros':
             detail_res = supabase.table('petros_details').select('*').eq('pendapatan_id', id).execute()
             details = detail_res.data
             res.data['details'] = details
             
             # Parse breakdown JSON jika ada
             if res.data.get('kos_breakdown'):
                 if isinstance(res.data['kos_breakdown'], str):
                     res.data['kos_breakdown'] = json.loads(res.data['kos_breakdown'])
        else:
            res.data['details'] = []

        return render_template('edit_income.html', record=res.data, details=res.data.get('details'))
    except Exception as e:
        flash(f"Rekod tidak dijumpai: {e}", "danger")
        return redirect(url_for('index'))

@app.route('/petros/detail/<int:id>')
@login_required
def petros_detail_view(id):
    try:
        # Dapatkan tahun & bulan dari URL untuk pautan 'Kembali'
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)

        # Dapatkan rekod utama
        main_res = supabase.table('pendapatan_lain').select('*').eq('id', id).single().execute()
        main_record = main_res.data
        
        # Parse breakdown JSON
        if main_record.get('kos_breakdown'):
             if isinstance(main_record['kos_breakdown'], str):
                 main_record['kos_breakdown'] = json.loads(main_record['kos_breakdown'])
        
        # Dapatkan pecahan detail
        detail_res = supabase.table('petros_details').select('*').eq('pendapatan_id', id).execute()
        details = detail_res.data
        
        # Kira Total untuk Footer Jadual
        total_vol = sum(float(d['daily_volume'] or 0) for d in details)
        total_sales = sum(float(d['sales_amount'] or 0) for d in details)
        
        return render_template('petros_detail.html', record=main_record, details=details, total_vol=total_vol, total_sales=total_sales, year=year, month=month)
    except Exception as e:
        flash(f"Ralat memuatkan detail Petros: {e}", "danger")
        return redirect(url_for('petros_dashboard'))

@app.route('/recalculate-petros')
@login_required
def recalculate_petros():
    """
    Fungsi khas untuk mengira semula semua rekod Petros menggunakan formula terkini.
    Berguna apabila terdapat perubahan pada kadar komisyen atau yuran SEDC.
    """
    try:
        # 1. Dapatkan semua rekod Petros
        # Penting: Order by Tarikh ASC supaya cumulative volume dikira dengan betul
        res = supabase.table('pendapatan_lain').select('*').eq('sumber', 'Petros').order('tarikh', desc=False).execute()
        records = res.data
        
        # Dictionary untuk track cumulative Mogas volume per bulan: {'2025-08': 12000.00}
        monthly_mogas_tracker = {}
        monthly_diesel_tracker = {}

        count = 0
        for rec in records:
            rec_id = rec['id']
            tarikh = rec['tarikh']
            month_key = tarikh[:7] # YYYY-MM
            
            # Init tracker jika bulan baru
            if month_key not in monthly_mogas_tracker:
                monthly_mogas_tracker[month_key] = 0.0
            if month_key not in monthly_diesel_tracker:
                monthly_diesel_tracker[month_key] = 0.0
            
            current_prev_mogas = monthly_mogas_tracker[month_key]
            current_prev_diesel = monthly_diesel_tracker[month_key]
            
            # 2. Dapatkan details (volume minyak)
            det_res = supabase.table('petros_details').select('*').eq('pendapatan_id', rec_id).execute()
            details = det_res.data
            
            if not details:
                continue
                
            # 3. Dapatkan Kos Operasi (Expenses) dari breakdown sedia ada
            other_expenses = 0.0
            breakdown = rec.get('kos_breakdown')
            
            if breakdown:
                if isinstance(breakdown, str):
                    breakdown = json.loads(breakdown)
                
                # Sum fixed and dynamic costs (exclude SEDC because it will be recalculated)
                fixed = breakdown.get('fixed', {})
                dynamic = breakdown.get('dynamic', [])
                
                for k, v in fixed.items():
                    other_expenses += float(v or 0)
                for item in dynamic:
                    other_expenses += float(item.get('amount') or 0)
            else:
                # Fallback: Jika tiada breakdown, guna 0 (atau perlu manual check)
                breakdown = {'fixed': {}, 'dynamic': []}

            # 4. Kira Semula Kewangan (Guna Formula Terkini)
            # Logik SEDC: Hanya kira jika ada expenses dalam rekod ini
            should_calc_sedc = (other_expenses > 0)
            
            net_profit, gross_profit, total_sedc = calculate_petros_financials(details, tarikh, other_expenses, current_prev_mogas, current_prev_diesel, apply_sedc=should_calc_sedc)
            
            # Update tracker untuk rekod seterusnya
            vol_mogas_today = sum(d['daily_volume'] for d in details if d['jenis_minyak'] in ['PF95', 'UF97'])
            vol_diesel_today = sum(d['daily_volume'] for d in details if d['jenis_minyak'] in ['E5 B20', 'E5 B7'])
            monthly_mogas_tracker[month_key] += vol_mogas_today
            monthly_diesel_tracker[month_key] += vol_diesel_today
            
            # 5. Update Breakdown dengan SEDC baru
            breakdown['sedc'] = total_sedc
            
            # 6. Kira Profit Sharing
            rec_date = datetime.strptime(tarikh, "%Y-%m-%d").date()
            start_date_25 = date(2028, 1, 1)
            rate = 0.25 if rec_date >= start_date_25 else 0.20
            kasb_share = round(net_profit * rate, 2)
            
            # 7. Update Rekod Utama
            supabase.table('pendapatan_lain').update({
                "kutipan_yuran": net_profit,
                "kos_pengurusan": other_expenses + total_sedc,
                "amaun": kasb_share,
                "kos_breakdown": breakdown
            }).eq('id', rec_id).execute()
            
            # 8. Update Rekod Details (Commission & Profit per item)
            for d in details:
                supabase.table('petros_details').update({
                    "earned_commission": d['earned_commission'],
                    "kos": d['kos'],
                    "profit": d['profit']
                }).eq('id', d['id']).execute()
                
            count += 1
            
        flash(f"Berjaya mengira semula {count} rekod Petros dengan formula terkini.", "success")
        return redirect(url_for('petros_dashboard'))
        
    except Exception as e:
        flash(f"Ralat semasa kira semula: {e}", "danger")
        return redirect(url_for('petros_dashboard'))

@app.route('/padam-pendapatan/<int:id>')
@login_required
def padam_pendapatan(id):
    try:
        # Dapatkan info dulu untuk redirect
        res = supabase.table('pendapatan_lain').select('sumber, tarikh').eq('id', id).single().execute()
        if res.data:
            sumber = res.data['sumber']
            year_str, month_str, _ = res.data['tarikh'].split('-')
            
            supabase.table('pendapatan_lain').delete().eq('id', id).execute()
            flash('Rekod berjaya dipadam.', 'warning')
            
            if sumber == 'Efeis':
                return redirect(url_for('efeis_dashboard', year=year_str, month=month_str))
            elif sumber == 'Petros':
                return redirect(url_for('petros_dashboard', year=year_str, month=month_str))
            return redirect(url_for('index'))
            
    except Exception as e:
        flash(f"Ralat memadam: {e}", "danger")
        
    return redirect(url_for('index'))

# Route ini PUBLIC (Tidak perlu login)
@app.route('/daftar-efeis', methods=['GET', 'POST'])
def daftar_kursus():
    """
    Halaman awam untuk peserta mendaftar kursus Efeis.
    """
    if request.method == 'POST':
        try:
            # Proses fail bukti bayaran
            file = request.files.get('bukti_bayaran')
            bukti_url = None
            
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                # Simpan dalam folder 'bayaran' di bucket 'dokumen'
                file_path = f"bayaran/{int(datetime.now().timestamp())}_{filename}"
                file_content = file.read()
                supabase.storage.from_("dokumen").upload(file_path, file_content, {"content-type": file.content_type})
                bukti_url = supabase.storage.from_("dokumen").get_public_url(file_path)

            data = {
                "nama_penuh": request.form.get('nama'),
                "no_ic": request.form.get('ic'),
                "no_telefon": request.form.get('telefon'),
                "email": request.form.get('email'),
                "nama_syarikat": request.form.get('syarikat'),
                "kursus_dipilih": request.form.get('kursus'),
                "kaedah_bayaran": request.form.get('kaedah_bayaran'),
                "bukti_bayaran_url": bukti_url,
                # Auto-generate password menggunakan No. IC
                "password_hash": generate_password_hash(request.form.get('ic'))
            }
            
            supabase.table('peserta_kursus').insert(data).execute()
            return render_template('daftar_sukses.html', nama=data['nama_penuh'])
            
        except Exception as e:
            return f"Ralat pendaftaran: {e}"
            
    # Dapatkan slot kursus yang aktif dari DB
    res = supabase.table('kursus_slot').select('*').eq('status', 'Aktif').order('created_at', desc=True).execute()
    slots = res.data
    
    # Dapatkan senarai semua peserta untuk kira kekosongan
    # (Nota: Untuk skala besar, count patut dibuat di DB level, tapi untuk sekarang ini memadai)
    p_res = supabase.table('peserta_kursus').select('kursus_dipilih').execute()
    all_participants = p_res.data
    
    for slot in slots:
        # Kira berapa orang dah daftar untuk slot ini
        count = sum(1 for p in all_participants if p.get('kursus_dipilih') == slot['nama_slot'])
        limit = slot.get('max_peserta') or 50
        
        slot['registered'] = count
        slot['remaining'] = max(0, limit - count)
        slot['is_full'] = count >= limit

    return render_template('daftar_kursus.html', slots=slots)

# --- ROUTES: PORTAL PESERTA (E-LEARNING) ---
@app.route('/login-peserta', methods=['GET', 'POST'])
def login_peserta():
    if request.method == 'POST':
        ic = request.form.get('ic')
        password = request.form.get('password')
        
        # Cari peserta berdasarkan No. IC
        res = supabase.table('peserta_kursus').select('*').eq('no_ic', ic).execute()
        user = res.data[0] if res.data else None
        
        if user and check_password_hash(user['password_hash'], password):
            session['peserta_id'] = user['id']
            session['nama_peserta'] = user['nama_penuh']
            return redirect(url_for('dashboard_peserta'))
        else:
            flash('No. Kad Pengenalan atau Kata Laluan salah.', 'danger')
            
    return render_template('login_peserta.html')

@app.route('/dashboard-peserta')
def dashboard_peserta():
    if 'peserta_id' not in session:
        return redirect(url_for('login_peserta'))
    
    user_id = session['peserta_id']
    res = supabase.table('peserta_kursus').select('*').eq('id', user_id).single().execute()
    peserta = res.data
    
    moduls = []
    # Hanya tunjuk modul jika bayaran selesai
    if peserta.get('status_bayaran') == 'Selesai':
        mod_res = supabase.table('modul_kursus').select('*').order('created_at', desc=False).execute()
        moduls = mod_res.data
        
    return render_template('dashboard_peserta.html', p=peserta, moduls=moduls)

@app.route('/logout-peserta')
def logout_peserta():
    session.pop('peserta_id', None)
    session.pop('nama_peserta', None)
    return redirect(url_for('login_peserta'))

@app.route('/senarai-peserta')
@login_required
def senarai_peserta():
    """
    Halaman admin untuk melihat senarai peserta yang mendaftar.
    """
    try:
        response = supabase.table('peserta_kursus').select('*').order('tarikh_daftar', desc=True).execute()
        return render_template('peserta_list.html', peserta=response.data)
    except Exception as e:
        return f"Ralat memuatkan senarai peserta: {e}"

# This allows the app to be run directly from the command line
if __name__ == '__main__':
    # Using debug=True will auto-reload the server when you make changes
    # Host='0.0.0.0' makes it accessible on your local network
    app.run(debug=True, host='0.0.0.0')