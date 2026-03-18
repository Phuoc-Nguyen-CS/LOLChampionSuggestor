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
    patch = requests.get("https://ddragon.leagueoflegends.com/api/versions.json").json()[0]
    data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/champion.json").json()['data']
    
    profiles = []
    for key, champ in data.items():
        tags = champ['tags']
        info = champ['info'] # Contains Attack, Defense, Magic, Difficulty
        primary_tag = tags[0].upper()
        
        # DAMAGE TYPE
        damage_type = "AD"
        if "Mage" in tags or "Support" in tags:
            damage_type = "AP"
        
        # CC TIER
        cc_tier = 1
        if "Tank" in tags or "Support" in tags: cc_tier = 3
        elif "Fighter" in tags or "Mage" in tags: cc_tier = 2

        # AUTOMATED UTILITY TIER
        # Tier 3: Traditional "Support" primary tag + High Magic/Defense (Enchanters/Wardens)
        # Tier 2: Secondary "Support" tag or high Defense/CC
        # Tier 1: No support tags (Carry-focused)
        
        utility_tier = 1
        if "Support" in tags:
            # If they are a Support and have high magic/defense info, they are peelers/enchanters
            if info['magic'] > 7 or info['defense'] > 6:
                utility_tier = 3 # Lulu, Janna, Braum, Thresh
            else:
                utility_tier = 2 # Karma, Pyke, Lux
        elif "Tank" in tags and info['defense'] > 7:
            utility_tier = 2 # Non-support tanks like Ornn/Sion provide utility via peel
        
        # MOBILITY TIER
        mobility_tier = 1
        if "Assassin" in tags: mobility_tier = 3
        elif "Fighter" in tags or info['attack'] > 7: mobility_tier = 2

        # ENGAGE TIER
        engage_tier = 1
        if "Tank" in tags and info['defense'] > 7: engage_tier = 3
        elif "Vanguard" in tags or "Diver" in tags: engage_tier = 3
        elif "Support" in tags and info['Defense'] > 5: engage_tier = 3

        profiles.append({
            "champion_id": int(champ['key']),
            "name": champ['name'],
            "damage_type": damage_type,
            "role_class": primary_tag,
            "cc_tier": cc_tier,
            "utility_tier": utility_tier,
            "mobility_tier": mobility_tier,
            "engage_tier": engage_tier,
        })


    try:
        supabase.table("champion_profiles").upsert(profiles).execute()
        print(f"Successfully profiled {len(profiles)} champions with Utility Tiers")
    except Exception as e:
        print(f"Error populating profiles: {e}")

def get_profiles_from_db():
    response = supabase.table("champion_profiles").select("*").execute()
    return response.data

if __name__ == "__main__":
    # Run this once to setup your static data
    populate_champion_profiles()