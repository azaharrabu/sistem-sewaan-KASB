import os
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
    penyewa_res = supabase.table('penyewa').select('*').eq('email', email).single().execute()
    if not penyewa_res.data:
        flash("Rekod penyewa tidak dijumpai.", "danger")
        return redirect(url_for('logout'))
    
    penyewa = penyewa_res.data
    
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
    return render_income_detail('Efeis')

@app.route('/petros')
@login_required
def petros_dashboard():
    return render_income_detail('Petros')

def render_income_detail(source_name):
    try:
        current_year = datetime.now().year
        selected_year = request.args.get('year', current_year, type=int)
        
        # Dapatkan data dari table pendapatan_lain
        response = supabase.table('pendapatan_lain').select('*').eq('sumber', source_name).order('tarikh', desc=True).execute()
        data = response.data
        
        # Filter ikut tahun (Python side filtering untuk mudah)
        filtered_data = [d for d in data if d['tarikh'].startswith(str(selected_year))]
        total_income = sum(float(d['amaun']) for d in filtered_data)
        
        # Agregat bulanan untuk paparan jadual
        monthly_breakdown = {m: 0.0 for m in range(1, 13)}
        for item in filtered_data:
            m = int(item['tarikh'].split('-')[1])
            monthly_breakdown[m] += float(item['amaun'])

        return render_template('income_list.html', source=source_name, data=filtered_data, selected_year=selected_year, current_year=current_year, total_income=total_income, monthly_breakdown=monthly_breakdown)
        
    except Exception as e:
        return f"Ralat memuatkan data {source_name}: {e}"


@app.route('/projek-baru', methods=['GET', 'POST'])
@login_required
def projek_baru_list():
    """
    Menguruskan (menambah dan memaparkan) projek baru dengan komisyen 10/15%.
    """
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
            bil = request.form.get('bil_penyertaan', 0)
            yuran = float(request.form.get('kutipan_yuran', 0))
            kos = float(request.form.get('kos_pengurusan', 0))
            
            # Kira keuntungan bersih secara automatik
            amaun = yuran - kos
            
            data.update({
                "bil_penyertaan": int(bil) if bil else 0,
                "kutipan_yuran": yuran,
                "kos_pengurusan": kos,
                "amaun": amaun
            })
        else:
            # Untuk Petros atau lain-lain, amaun dimasukkan terus
            amaun = float(request.form.get('amaun', 0))
            data["amaun"] = amaun

        supabase.table('pendapatan_lain').insert(data).execute()
        
        # Redirect ke tahun tarikh tersebut supaya user nampak data yang baru dimasukkan
        year = tarikh.split('-')[0]
        if source_name == 'Efeis':
            return redirect(url_for('efeis_dashboard', year=year))
        elif source_name == 'Petros':
            return redirect(url_for('petros_dashboard', year=year))
        else:
            return redirect(url_for('index'))

    except Exception as e:
        return f"Ralat menambah pendapatan: {e}"

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