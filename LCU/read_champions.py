# read_champions.py
# Utility to map Riot's numerical Champion IDs to human-readable names.
import requests

def get_latest_patch():
    """
    Fetches the current live patch version from Riot's DataDragon API.
    """
    url = "https://ddragon.leagueoflegends.com/api/versions.json"
    response = requests.get(url)
    if response.status_code == 200:
        version = response.json()
        return version[0] # Returns latest version, e.g., "14.5.1"
    return None

def build_champion_dic(version):
    """
    Downloads the champion metadata for a specific patch and 
    creates a dictionary mapping {ID: Name}.
    """
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
    response = requests.get(url)

    if response.status_code != 200:
        print("Failed to get the DataDragon dataset.")
        return {}

    champ_data = response.json().get('data', {})
    id_to_name = {}
    
    for internal_name, details in champ_data.items():
        # 'key' is the numerical ID (as a string), 'name' is the display name
        num_id = int(details['key'])
        champ_name = details['name']
        id_to_name[num_id] = champ_name

    return id_to_name

def get_champion_mapping():
    """
    High-level orchestrator used by other scripts to get the mapping 
    without worrying about patch versions.
    """
    patch = get_latest_patch()
    if not patch:
        return {}
    return build_champion_dic(patch)

if __name__ == "__main__":
    # Test block to verify mapping works
    mapping = get_champion_mapping()
    print(f"Mapping initialized with {len(mapping)} champions.")
    print(f"Test ID 53: {mapping.get(53)}") # Should be Blitzcrank