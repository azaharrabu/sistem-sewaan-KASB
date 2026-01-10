import os
from flask import Flask, render_template
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

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
        # Fetch data from Supabase, joining tables
        response = supabase.table('sewaan').select('*, aset(id_aset, lokasi), penyewa(nama_penyewa)').execute()
        
        # The data from the API response
        api_data = response.data
        
        # Transform the data for the template
        template_data = []
        for item in api_data:
            penyewa_nama = item.get('penyewa', {}).get('nama_penyewa') if item.get('penyewa') else 'Tiada Maklumat'
            
            template_data.append({
                'id': item.get('aset', {}).get('id_aset', 'N/A'),
                'lokasi': item.get('aset', {}).get('lokasi', 'N/A'),
                'penyewa': penyewa_nama,
                'sewa': item.get('sewa_bulanan_rm', 0.00),
                'status_bayaran': item.get('status_bayaran_terkini', 'N/A')
            })

    except Exception as e:
        # If there's an error, display it to make debugging easier
        return f"Database error: {e}"

    # Render the HTML template, passing the transformed data to it
    return render_template('index.html', data=template_data)

# This allows the app to be run directly from the command line
if __name__ == '__main__':
    # Using debug=True will auto-reload the server when you make changes
    # Host='0.0.0.0' makes it accessible on your local network
    app.run(debug=True, host='0.0.0.0')