import requests
import os
import re
from supabase import create_client, Client 
from dotenv import load_dotenv

load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

def scan_kit(name, data):
    """Scans the passive and spells for keywords pertaining to the kit"""
    spells = data.get('spells', [])
    passive = data.get('passive', {})
    # all_descriptions = [passive.get('description', '')] + [s.get('description', '') + " " + s.get('tooltips', '') for s in spells]
    all_descriptions = [passive.get('description', '').lower()]
    for s in spells:
        desc = s.get('description', '').lower()
        tip = s.get('tooltip', '').lower()
        all_descriptions.append(f"{desc} {tip}")
    full_text = " ".join(all_descriptions)
    champ_name_lower = name.lower()
    if(name == "annie"):
        print(full_text)

    # KEYWORDS and mapping occurrences
    mechanics = {
        "hard_cc": len(re.findall(r'(stun|knockup|knock up|knocking them aside|aside|airborne|suppression|suppress|fear|charm|taunt|knockback|knock back|berserk|polymorph|drag|drags)', full_text)),
        "soft_cc": len(re.findall(r'(slow|root|snare|silence|blind|grounded|ground)', full_text)),
        "dash": len(re.findall(r'(dash|leap|jump|lunge)', full_text)),
        "blink": len(re.findall(r'(blink|teleport)', full_text)),
        "ms_steroid": len(re.findall(r'(bonus movement speed|bonus movespeed|move speed|movement speed)', full_text)),
        "invis": len(re.findall(r'(invisible|stealth|camouflage)', full_text)),
        "untargetable": len(re.findall(r'(untargetable)', full_text)),
        "invulnerable": len(re.findall(r'(invulnerable|stasis)', full_text)),
        "aoe": len(re.findall(r'(all enemies| nearby enemies| area|enemies in|each enemy)', full_text)),
        "terrain": len(re.findall(r'(terrain|wall|pillar|cataclysm)', full_text)),
        "resets": any(w in full_text for w in ['refresh', 'takedown']) and any(w in full_text for w in ['cooldown', 'reset']),
        "execute": any(w in full_text for w in ['execute', 'below % health', 'less than % health']),
        "global": any(w in full_text for w in ['global', 'anywhere on the map', 'entire map']),
        # "disengage": len(re.findall(r'(knock back|push back|away from)', full_text))
    }

    shield_self, shield_ally, heal_self, heal_ally = 0, 0, 0, 0
    point_and_click = False
    # PNC Edge Cases
    # Cuz im too lazy to find out exact keywords
    pnc_overrides = [
        "Annie", "Twisted Fate", "Pantheon", "Vi", "Malzahar",
        "Lulu", "Fiddlesticks", "Nocturne", "Ryze", "Maokai"
    ]
    if name in pnc_overrides:
        point_and_click = True

    for s in spells:
        d = s.get('description', '') + " " + s.get('tooltips', '').lower()
        # if 'shield' in d:
        #     if any(x in d for x in ['ally', 'allies', 'teamate']): shield_ally += 1
        #     else: shield_self += 1
        # if any(x in d for x in ['heal', 'restore']):
        #     if any (x in d for x in ['ally', 'allies', 'teamate']): heal_ally += 1
        #     else: heal_self += 1
        if 'shield' in d:
            # Independent Check 1: Is it for an ally?
            if any(x in d for x in ['ally', 'allies', 'teammate']):
                shield_ally += 1
            
            # Independent Check 2: Is it for self?
            # We check if it mentions the name, 'self', or 'her/himself'
            # OR if it doesn't mention an ally at all (Selfish shield)
            is_self = any(x in d for x in [champ_name_lower, 'self', 'herself', 'himself'])
            no_ally_mentioned = not any(x in d for x in ['ally', 'allies', 'teammate'])
            
            if is_self or no_ally_mentioned:
                shield_self += 1

        if any(x in d for x in ['heal', 'restore']):
            if any(x in d for x in ['ally', 'allies', 'teammate']):
                heal_ally += 1
            
            is_self = any(x in d for x in [champ_name_lower, 'self', 'herself', 'himself'])
            no_ally_mentioned = not any(x in d for x in ['ally', 'allies', 'teammate'])
            
            if is_self or no_ally_mentioned:
                heal_self += 1
        

    # print(f"{mechanics}\n {shield_self}\n {shield_ally}\n {heal_self}\n {heal_ally}\n {point_and_click}")
    return mechanics, shield_self, shield_ally, heal_self, heal_ally, point_and_click
# def scan_kit(name, data):
#     """
#     Scans the passive and spells for mechanical keywords.
#     Fixes case-sensitivity bugs and DataDragon key typos.
#     """
#     spells = data.get('spells', [])
#     passive = data.get('passive', {})
#     champ_name_lower = name.lower()
    
#     # 1. PREPARE TEXT: Ensure everything is lowercased immediately
#     # FIX: Use 'tooltip' (singular), not 'tooltips'
#     processed_spells = []
#     for s in spells:
#         desc = s.get('description', '').lower()
#         tip = s.get('tooltip', '').lower() # Correct key is singular
#         processed_spells.append(f"{desc} {tip}")
        
#     full_text = passive.get('description', '').lower() + " " + " ".join(processed_spells)

#     # 2. MECHANICS SCANNER (Regex)
#     mechanics = {
#         "hard_cc": len(re.findall(r'(stun|knockup|knock up|knocking them aside|aside|airborne|suppression|suppress|fear|charm|taunt|knockback|knock back|berserk|polymorph|drag|drags)', full_text)),
#         "soft_cc": len(re.findall(r'(slow|root|snare|silence|blind|grounded|ground)', full_text)),
#         "dash": len(re.findall(r'(dash|leap|jump|lunge)', full_text)),
#         "blink": len(re.findall(r'(blink|teleport)', full_text)),
#         "ms_steroid": len(re.findall(r'(bonus movement speed|bonus movespeed|move speed|movement speed)', full_text)),
#         "invis": len(re.findall(r'(invisible|stealth|camouflage)', full_text)),
#         "untargetable": len(re.findall(r'(untargetable)', full_text)),
#         "invulnerable": len(re.findall(r'(invulnerable|stasis)', full_text)),
#         "aoe": len(re.findall(r'(all enemies|nearby enemies|area|enemies in|each enemy)', full_text)),
#         "terrain": len(re.findall(r'(terrain|wall|pillar|cataclysm)', full_text)),
#         "resets": any(w in full_text for w in ['refresh', 'takedown']) and any(w in full_text for w in ['cooldown', 'reset']),
#         "execute": any(w in full_text for w in ['execute', 'below % health', 'less than % health']),
#         "global": any(w in full_text for w in ['global', 'anywhere on the map', 'entire map']),
#         "disengage": len(re.findall(r'(knock back|push back|away from|distance between)', full_text))
#     }

#     # 3. POINT-AND-CLICK CC
#     pnc_overrides = ["Annie", "Twisted Fate", "Pantheon", "Vi", "Malzahar", "Lulu", "Fiddlesticks", "Nocturne", "Ryze", "Maokai"]
#     point_and_click = name in pnc_overrides

#     # 4. SHIELDS & HEALS
#     shield_self, shield_ally, heal_self, heal_ally = 0, 0, 0, 0
    
#     ally_keywords = ['ally', 'allies', 'teammate', 'teamate']
#     self_keywords = ['self', 'himself', 'herself', champ_name_lower]

#     for d in processed_spells:
#         # --- Shield Logic ---
#         if 'shield' in d:
#             # Independent Check 1: Is it for an ally?
#             if any(x in d for x in ally_keywords):
#                 shield_ally += 1
            
#             # Independent Check 2: Is it for self?
#             # Check for name/self keywords OR if NO ally is mentioned (selfish shield)
#             is_self = any(x in d for x in self_keywords)
#             no_ally_mentioned = not any(x in d for x in ally_keywords)
            
#             if is_self or no_ally_mentioned:
#                 shield_self += 1

#         # --- Heal Logic ---
#         if any(x in d for x in ['heal', 'restore', 'recover']):
#             if any(x in d for x in ally_keywords):
#                 heal_ally += 1
            
#             is_self = any(x in d for x in self_keywords)
#             no_ally_mentioned = not any(x in d for x in ally_keywords)
            
#             if is_self or no_ally_mentioned:
#                 heal_self += 1
                
#         # --- standard PnC Check ---
#         if not point_and_click:
#             if any(cc in d for cc in ['stun', 'root', 'slow']) and "target" in d and "skillshot" not in d:
#                 point_and_click = True

#     return mechanics, shield_self, shield_ally, heal_self, heal_ally, point_and_click

def populate_champion_dna():
    print("Fetching champion data...")
    patch = requests.get("https://ddragon.leagueoflegends.com/api/versions.json").json()[0]
    data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/championFull.json").json()['data']
    cdrag_url = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-summary.json"
    cdrag_stats = {str(c['id']): c for c in requests.get(cdrag_url).json()}

    profiles = []
    dna_profiles = []
    for key, champ in data.items():
        stats = champ.get('stats', {})
        tags = champ.get('tags', [])
        c_id = champ['key']
        other_stats = cdrag_stats.get(c_id, {}) # Grabbing the adgrowth from here

        mechs, s_self, s_ally, h_self, h_ally, pnc = scan_kit(champ['name'], champ)

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
            # "ad_growth": float(stats['attackdamageperlevel']),
            "ad_growth": float(other_stats.get('attackDamagePerLevel', stats.get('attackdamageperlevel', 0))),
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
            # "disengage_spells": mechs['disengage'],
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
