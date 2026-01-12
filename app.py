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
            return redirect(url_for('index'))
        else:
            flash('Username atau Password salah!', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

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

        return render_template(
            'asset_detail.html', 
            asset=sewaan_data, 
            transactions=transaksi_data,
            monthly_status=monthly_status,
            documents=documents,
            selected_year=selected_year,
            total_bayaran=total_bayaran,
            current_year=current_year
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