import os
import sys

# Debug awal: Pastikan skrip mula berjalan
print("DEBUG: Skrip Python sedang dimulakan...", flush=True)

try:
    from supabase import create_client, Client
    from dotenv import load_dotenv
    print("DEBUG: Library berjaya diimport.")
except ImportError as e:
    print(f"DEBUG: Ralat import library - {e}")
    sys.exit(1)

# Load environment variables
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("DEBUG: Ralat - Fail .env tidak dijumpai atau kunci Supabase tiada.")
    sys.exit(1)

print("DEBUG: Menyambung ke Supabase...")
supabase: Client = create_client(url, key)

def fix_petros():
    print("DEBUG: Memulakan fungsi fix_petros...")
    
    try:
        # Dapatkan semua rekod Petros
        res = supabase.table('pendapatan_lain').select('*').eq('sumber', 'Petros').execute()
        records = res.data
        print(f"DEBUG: Jumpa {len(records)} rekod Petros dalam database.")
        
        count = 0
        for rec in records:
            current_total_profit = float(rec.get('kutipan_yuran') or 0)
            current_amaun = float(rec.get('amaun') or 0)
            
            # Jika Total Profit 0 tapi Amaun ada nilai, kita perlu betulkan
            if current_total_profit == 0 and current_amaun > 0:
                print(f"DEBUG: Membaiki ID {rec['id']} ({rec['tarikh']})...")
                
                real_total_profit = current_amaun
                kasb_share = real_total_profit * 0.20
                
                supabase.table('pendapatan_lain').update({
                    "kutipan_yuran": real_total_profit,
                    "amaun": kasb_share
                }).eq('id', rec['id']).execute()
                
                print(f"  -> Fixed: Total Profit RM {real_total_profit} | KASB RM {kasb_share}")
                count += 1
                
        if count == 0:
            print("DEBUG: Tiada rekod yang perlu dibaiki (Semua data nampak betul).")
        else:
            print(f"✅ Selesai! {count} rekod telah dibetulkan.")
            
    except Exception as e:
        print(f"DEBUG: Ralat semasa memproses database: {e}")

if __name__ == "__main__":
    fix_petros()