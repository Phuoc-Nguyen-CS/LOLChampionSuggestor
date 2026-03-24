import pandas as pd
from supabase import create_client

# Project A (The Buffer)
buffer_client = create_client("BUFFER_URL", "BUFFER_SERVICE_KEY")
# Project B (The Main)
main_client = create_client("SUPABASE_URL", "SUPABASE_KEY")

def migrate():
    print("Downloading data from buffer...")
    res = buffer_client.table("match_participants").select("*").execute()
    data = res.data
    
    # 2. Batch upload to main (1000 rows at a time to avoid timeouts)
    print(f"Migrating {len(data)} rows to main project...")
    for i in range(0, len(data), 1000):
        batch = data[i:i+1000]
        main_client.table("match_participants").insert(batch).execute()
        print(f"Migrated batch {i//1000 + 1}")

migrate()