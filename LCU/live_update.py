#   live_update.py
#   This is how we grab live champions being picked
#   We need to access the League Client Update API:
#   In it we need to grab the port and password
import os
import time
import requests
import urllib3
from read_champions import get_champion_mapping

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Gets the port and password for the lcu
def get_lcu_credentials(install_path):
    # Read the lockfile to get the dynamic port and password
    lockfile_path = os.path.join(install_path, 'lockfile')

    if not os.path.exists(lockfile_path):
        print("League Client is not running or the path is not correct.")
        return None, None

    with open(lockfile_path, 'r') as f:
        # Lockfile format: LeagueClient:PID:PORT:PASSWORD:PROTOCOL
        content = f.read()
        parts = content.split(':')
        port = parts[2]
        password = parts[3]
        return port, password 

# Get the data within the session
def get_champ_select_session(port, password):
    # Fetches the current champion select from the LCU
    url = f"https://127.0.0.1:{port}/lol-champ-select/v1/session"

    try:
        # LCU API use basic auth with the username 'riot'
        response = requests.get(
            url,
            auth=('riot', password),
            verify=False
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            print("Not in champ select")
            return None
        else:
            print(f"Error: Received status code {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to LCU: {e}")
        return None

# Grab the draft state
def extract_draft_state(session_data, champ_mapping):
    draft_state = {"allies": [], "enemies": []}

    for player in session_data.get('myTeam', []):
        champ_id = player.get('championId', 0)
        if champ_id != 0:
            name = champ_mapping.get(champ_id, "Unknown")
            draft_state["allies"].append(name)

    for player in session_data.get('theirTeam', []):
        champ_id = player.get('championId', 0)
        if champ_id != 0:
            name = champ_mapping.get(champ_id, "Unknown")
            draft_state["enemies"].append(name)

    return draft_state

if __name__ == "__main__":
    LEAGUE_INSTALL_PATH = "C:\Riot Games\League of Legends"

    # Load the data
    print("Loading champion data...")
    champ_mapping = get_champion_mapping()
    if not champ_mapping:
        print("Failed to load champ data...")
        exit(1)
    
    # Connect to the LCU
    port, password = get_lcu_credentials(LEAGUE_INSTALL_PATH)

    if not port:
        print("LCU failed")

    print(f"Connected to LCU on port {port}. Waiting for Champ Select")

    last_draft_state = None

    try:
        while True:
            session_data = get_champ_select_session(port, password)

            if session_data:
                current_draft = extract_draft_state(session_data, champ_mapping)

                # Prints if theres an update
                if current_draft != last_draft_state:
                    print("\n--- Draft Updated ---")
                    print(f"Allies: {current_draft['allies']}")
                    print(f"Enemies: {current_draft['enemies']}")
                    last_draft_state = current_draft
            else:
                last_draft_state = None
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nClosing live update.")
