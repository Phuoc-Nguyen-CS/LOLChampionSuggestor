import os
from dotenv import load_dotenv
from supabase import create_client
from inference_engine import InferenceEngine, DraftSimulator

load_dotenv()

def run_system_check():
    """Verifies that all components can speak to each other."""
    print("[INIT] Starting Draft System Compatibility Check...")
    
    # 1. Setup Paths
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    model_path = os.path.join(project_root, "ML", "models", "champion_model.json")
    feature_path = os.path.join(project_root, "ML", "models", "feature_list.json")

    # 2. Initialize Engine
    client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    engine = InferenceEngine(model_path, feature_path, client)
    
    try:
        engine.initialize()
        simulator = DraftSimulator(engine)
        print("[SUCCESS] InferenceEngine and DraftSimulator handshake complete.\n")
    except Exception as e:
        print(f"[CRITICAL] Handshake Failed: {e}")
        return

    # 3. Standardized Test Scenarios
    scenarios = [
        {
            "name": "Scenario 1: The Synergy",
            "description": "Looking for a Jungler to synergize with a heavy-engage Mid/Top duo.",
            "pos": "JUNGLE",
            "allies": ["Orianna", "Malphite"],
            "enemies": ["Yasuo", "Jinx"]
        },
        {
            "name": "Scenario 2: The 'All AD'",
            "description": "Team drafted all AD. Enemy drafted heavy Armor tanks. Top laner MUST pick AP.",
            "pos": "TOP",
            "allies": ["Zed", "Talon", "Draven", "Pyke"],
            "enemies": ["Rammus", "Ornn", "Jhin", "Braum", "Orianna"]
        },
        {
            "name": "Scenario 3: Protect the President",
            "description": "Team has a hypercarry. Enemies have heavy dive assassins.",
            "pos": "SUPPORT",
            "allies": ["Kog'Maw", "Ornn", "Syndra", "Rammus"],
            "enemies": ["Talon", "Akali", "Vi", "Jinx", "Karma"]
        },
        {
            "name": "Scenario 4: First Pick (Blind Draft)",
            "description": "Testing if the model suggests universally safe/strong Bottom laners.",
            "pos": "BOTTOM",
            "allies": [],
            "enemies": []
        },
        {
            "name": "Scenario 5: Last Pick Counter",
            "description": "Testing exact counter-picking logic for the Bottom Lane.",
            "pos": "BOTTOM",
            "allies": ["Shen", "Amumu", "Ahri", "Leona"],
            "enemies": ["Vayne", "Lulu", "Zac", "Syndra", "Jax"]
        },
        {
            "name": "Scenario 6: Anh's Game",
            "description": "Mid lane last pick from Anh's Ranked Game",
            "pos": "MID",
            "allies": ["Maokai", "Nunu & Willump", "Yone", "Ziggs"],
            "enemies": ["Shaco", "Morgana", "Ashe", "Lux", "Tryndamere"]
        }
    ]

    for test in scenarios:
        print(f"--- Running {test['name']} ---")
        print(f"Allies: {test['allies']}")
        print(f"Enemies: {test['enemies']}")
        print(f"Position: {test['pos']}")
        recs = simulator.suggest_picks(test['allies'], test['enemies'], test['pos'])
        
        if not recs:
            print("    [!] Warning: No recommendations returned.")
        for i, rec in enumerate(recs, 1):
            print(f"    {i}. {rec['name'].ljust(15)} | Win Prob: {rec['win_prob']:.2%}")
        print("")

if __name__ == "__main__":
    run_system_check()
