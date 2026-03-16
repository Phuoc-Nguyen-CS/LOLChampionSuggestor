# champion_profiles.py
# Gets the characterisitics of the champions
# We only need to run this once or when there is a major update to a champion
import requests
from supabase import Client, create_client
import os
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
RIOT_API_KEY = os.environ.get("RIOT_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def populate_champion_profiles():
    print("Fetching latest champion data from DataDragon...")
    # Get latest patch and champ data
    patch = requests.get("https://ddragon.leagueoflegends.com/api/versions.json").json()[0]
    data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/champion.json").json()['data']
    
    profiles = []
    for key, champ in data.items():
        # Heuristic to determine damage type
        # (Simplified: Mages/Enchanters = AP, Marksmen/Assassins = AD)
        tags = champ['tags']
        primary_tag = tags[0].upper()
        
        damage_type = "AD"
        if "Mage" in tags or "Support" in tags:
            damage_type = "AP"
        
        # CC Tier Heuristic (3 = Tank/Support, 2 = Fighter/Mage, 1 = Assassin/Marksman)
        cc_tier = 1
        if "Tank" in tags or "Support" in tags: cc_tier = 3
        elif "Fighter" in tags or "Mage" in tags: cc_tier = 2

        profiles.append({
            "champion_id": int(champ['key']),
            "name": champ['name'],
            "damage_type": damage_type,
            "role_class": primary_tag,
            "cc_tier": cc_tier
        })

    # 2. Bulk Insert into Supabase
    try:
        supabase.table("champion_profiles").upsert(profiles).execute()
        print(f"Successfully profiled {len(profiles)} champions!")
    except Exception as e:
        print(f"Error populating profiles: {e}")

def get_profiles_from_db():
    response = supabase.table("champion_profiles").select("*").execute()
    return response.data

if __name__ == "__main__":
    # Run this once to setup your static data
    populate_champion_profiles()