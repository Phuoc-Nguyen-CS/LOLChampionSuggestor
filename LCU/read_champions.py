# read_champions.py
# Get the most recent patch and the champions associated with it

import requests

def get_latest_patch():
    url = "https://ddragon.leagueoflegends.com/api/versions.json"
    response = requests.get(url)
    if response.status_code == 200:
        version = response.json()
        return version[0]

def build_champion_dic(version):
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
    response = requests.get(url)

    if response.status_code != 200:
        print("Failed to get the data set")
        return {}

    champ_data = response.json().get('data', {})
    id_to_name = {}
    
    for internal_name, details in champ_data.items():
        num_id = int(details['key'])
        champ_name = details['name']

        id_to_name[num_id] = champ_name

    return id_to_name

def get_champion_mapping():
    patch = get_latest_patch()
    if not patch:
        print("Error getting the patch")
        return {}
    return build_champion_dic(patch)

if __name__ == "__main__":
    print("Fetching the latest Riot patch version...")
    latest_patch = get_latest_patch()

    if latest_patch:
        print(f"Latest Patch is {latest_patch}")
        print("Downloading champion data")

        champ_dict = build_champion_dic(latest_patch)
        print(f"Successfully loaded {len(champ_dict)} into memory")

        test_ids = [103, 64, 266, 0, 13]
        for champ_id in test_ids:
            name = champ_dict.get(champ_id, "DNE")
            print(f"ID {champ_id} -> {name}")