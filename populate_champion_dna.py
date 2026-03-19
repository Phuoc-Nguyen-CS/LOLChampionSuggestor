import requests
import os
import re
from supabase import create_client, Client 
from dotenv import load_dotenv

load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

def scan_kit(data):
    """Scans the passive and spells for keywords pertaining to the kit"""
    spells = data.get('spells', [])
    passive = data.get('passive', {})
    all_descriptions = [passive.get('description', '')] + [s.get('description', '') + " " + s.get('tooltips', '') for s in spells]
    full_text = " ".join(all_descriptions).lower()
    # print(full_text)

    # KEYWORDS and mapping occurrences
    mechanics = {
        "hard_cc": len(re.findall(r'(stun|knockup|knock up|airborne|suppression|suppress|fear|charm|taunt|knockback|knock back|berserk|polymorph|drag|drags)', full_text)),
        "soft_cc": len(re.findall(r'(slow|root|snare|silence|blind|grounded|ground)', full_text)),
        "dash": len(re.findall(r'(dash|leap|jump|lunge)', full_text)),
        "blink": len(re.findall(r'(blink|teleport)', full_text)),
        "ms_steroid": len(re.findall(r'(bonus movement speed|bonus movespeed)', full_text)),
        "invis": len(re.findall(r'(invisible|stealth|camouflage)', full_text)),
        "untargetable": len(re.findall(r'(untargetable)', full_text)),
        "invulnerable": len(re.findall(r'(invulnerable|stasis)', full_text)),
        "aoe": len(re.findall(r'(all enemies| nearby enemies| area|enemies in|each enemy)', full_text)),
        "terrain": len(re.findall(r'(terrain|wall|pillar|cataclysm)', full_text)),
        "resets": any(w in full_text for w in ['refresh', 'takedown']) and any(w in full_text for w in ['cooldown', 'reset']),
        "execute": any(w in full_text for w in ['execute', 'below % health', 'less than % health']),
        "global": any(w in full_text for w in ['global', 'anywhere on the map', 'entire map']),
        "disengage": len(re.findall(r'(knock back|push back|away from)', full_text))
    }

    shield_self, shield_ally, heal_self, heal_ally = 0, 0, 0, 0
    point_and_click = False
    if re.findall(r'(Annie)', full_text):
        point_and_click = True

    for s in spells:
        d = s.get('description', '') + " " + s.get('tooltips', '').lower()
        if 'shield' in d:
            if any(x in d for x in ['ally', 'allies', 'teamate']): shield_ally += 1
            else: shield_self += 1
        if any(x in d for x in ['heal', 'restore']):
            if any (x in d for x in ['ally', 'allies', 'teamate']): heal_ally += 1
            else: heal_self += 1
        if any (cc in d for cc in ['stun', 'root', 'slow']) and "target" in d and "skillshot" not in d:
            point_and_click = True
        

    # print(f"{mechanics}\n {shield_self}\n {shield_ally}\n {heal_self}\n {heal_ally}\n {point_and_click}")
    return mechanics, shield_self, shield_ally, heal_self, heal_ally, point_and_click


def populate_champion_dna():
    print("Fetching champion data...")
    patch = requests.get("https://ddragon.leagueoflegends.com/api/versions.json").json()[0]
    data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/championFull.json").json()['data']

    profiles = []
    dna_profiles = []
    for key, champ in data.items():
        stats = champ.get('stats', {})
        tags = champ.get('tags', [])
        mechs, s_self, s_ally, h_self, h_ally, pnc = scan_kit(champ)

        dmg_type = "AD"
        if "Mage" in tags: dmg_type = "AP"
        if champ['name'] in ['Katarina', 'Kayle', 'Varus', 'Kai\'Sa', 'Jax', 'Shyvanna', 'Kog\'Maw', 'Udyr']: dmg_type = "HYBRID"

        burst_score = 0.5 # Default starting point

        if "Assassin" in tags:
            burst_score = 0.9  # Highest burst
        elif "Mage" in tags:
            burst_score = 0.8  # High burst (most LoL mages are combo-based)
        elif "Marksman" in tags:
            burst_score = 0.2  # Very low burst, high sustained
        elif "Tank" in tags:
            burst_score = 0.3  # Low burst
        elif "Support" in tags:
            # Enchanters have low burst; Mage-supports (Lux/Zyra) are caught by "Mage" tag
            burst_score = 0.2
        
        # If they are a Fighter but have high attack info, they are likely a "Diver" (Bursty)
        if "Fighter" in tags:
            if champ['info']['attack'] > 7:
                burst_score = 0.7 # Renekton, Vi, Jarvan
            else:
                burst_score = 0.4 # Jax, Trundle (Sustained)

        profiles.append({
            "champion_id": int(champ['key']),
            "name": champ['name'],
            "primary_role": tags[0].upper(),
            "damage_type": dmg_type,
            "tags": ", ".join(tags),
            
            # Base Stats (Raw Numeric)
            "attack_range": int(stats['attackrange']),
            "base_hp": int(stats['hp']),
            "hp_growth": float(stats['hpperlevel']),
            "hp_regen": float(stats['hpregen']),
            "hp_regen_per_level": float(stats['hpregenperlevel']),
            "base_ad": int(stats['attackdamage']),
            "ad_growth": float(stats['attackdamageperlevel']),
            "armor_growth": float(stats['armorperlevel']),
            "mr_growth": float(stats['spellblockperlevel']),
            "base_ms": int(stats['movespeed']),
            "base_mana": int(stats['mp']),
            "mana_per_level": float(stats['mpperlevel']),
            "base_attack_speed": float(stats['attackspeed']),
            "attack_speed_per_level": float(stats['attackspeedperlevel']),

            # Combat Style (DNA-based)
            "burst_score": burst_score,
            "point_and_click_cc": pnc,
            "has_execute": mechs['execute'],

            # Map Impact & Movement
            "has_global_ult": mechs['global'],
            "disengage_spells": mechs['disengage'],
            "dash_count": mechs['dash'],
            "blink_count": mechs['blink'],
            "ms_steroid": mechs['ms_steroid'],

            # Mechanics
            "hard_cc_spells": mechs['hard_cc'],
            "soft_cc_spells": mechs['soft_cc'],
            "invis_spells": mechs['invis'],
            "shield_spells_self": s_self,
            "shield_spells_allies": s_ally,
            "heal_spells_self": h_self,
            "heal_spells_allies": h_ally,
            "aoe_spells": mechs['aoe'],
            "untargetable_spells": mechs['untargetable'],
            "invulnerable_spells": mechs['invulnerable'],
            "has_resets": mechs['resets'],
            "terrain_change": mechs['terrain']
        })

        try:
            supabase.table("champion_dna").upsert(profiles).execute()
            print(f"Updated {len(profiles)} champions")
        except Exception as e:
            print(f"Sync failed: {e}")

if __name__ == "__main__":
    populate_champion_dna()
