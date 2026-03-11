#   read_champions.py
#   This is how we grab live champions being picked
#   We need to access the League Client Update API:
#   In it we need to grab the port and password
import os
import requests
import urllib3

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
def extract_draft_state(session_data):
    draft_state = {
        "allies": [],
        "enemies": []
    }

    # Get our team
    for player in session_data.get('myTeam', []):
        champ_id = player.get('championId', 0)
        if champ_id != 0:
            draft_state["allies"].append(champ_id)
    
    # Get enemy team            
    for player in session_data.get('theirTeam', []):
        champ_id = player.get('championId', 0)
        if champ_id != 0:
            draft_state["enemies"].append(champ_id)
    
    return draft_state

if __name__ == "__main__":
    LEAGUE_INSTALL_PATH = "C:\Riot Games\League of Legends"

    print("Fetching LCU credentials...")
    port, password = get_lcu_credentials(LEAGUE_INSTALL_PATH)

    if port and password:
        print(f"Connected! Port: {port} | Password: {password}")
        print("Fetching Champion Select data...\n")

        session_data = get_champ_select_session(port, password)
        current_draft = extract_draft_state(session_data)

        if session_data:
            print(f"Session Keys available: {list(session_data.keys())}")
            print(f"Your team's picks: {current_draft['allies']}")
            print(f"Enemy team's picks: {current_draft['enemies']}")


