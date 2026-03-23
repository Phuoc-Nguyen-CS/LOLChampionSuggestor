import os
from dotenv import load_dotenv
from supabase import create_client
from inference_engine import InferenceEngine, DraftSimulator

# Load configuration
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

def run_test_suite():
    print("[INIT] Starting Multi-Draft Simulation Suite...")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, ".."))

    # Construct absolute paths to ML artifacts
    model_path = os.path.join(project_root, "ML", "models", "champion_model.json")
    feature_path = os.path.join(project_root, "ML", "models", "feature_list.json")

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    client = create_client(url, key)

    engine = InferenceEngine(
        model_path=model_path,
        feature_list_path=feature_path,
        db_client=client
    )
    engine.initialize()
    simulator = DraftSimulator(engine)

    # Test Scenarios
    test_cases = [
        {
            "name": "Scenario 1: The Synergy",
            "description": "Looking for a Jungler to synergize with a heavy-engage Mid/Top duo.",
            "position": "JUNGLE",
            "allies": ["Orianna", "Malphite"],
            "enemies": ["Yasuo", "Jinx"]
        },
        {
            "name": "Scenario 2: The 'All AD'",
            "description": "Team drafted all AD. Enemy drafted heavy Armor tanks. Top laner MUST pick AP.",
            "position": "TOP",
            "allies": ["Zed", "Talon", "Draven", "Pyke"],
            "enemies": ["Rammus", "Ornn", "Jhin", "Braum", "Orianna"]
        },
        {
            "name": "Scenario 3: Protect the President",
            "description": "Team has a hypercarry. Enemies have heavy dive assassins.",
            "position": "SUPPORT",
            "allies": ["Kog'Maw", "Ornn", "Syndra", "Rammus"],
            "enemies": ["Talon", "Akali", "Vi", "Jinx", "Karma"]
        },
        {
            "name": "Scenario 4: First Pick (Blind Draft)",
            "description": "Testing if the model suggests universally safe/strong Bottom laners.",
            "position": "BOTTOM",
            "allies": [],
            "enemies": []
        },
        {
            "name": "Scenario 5: Last Pick Counter",
            "description": "Testing exact counter-picking logic for the Bottom Lane.",
            "position": "BOTTOM",
            "allies": ["Shen", "Amumu", "Ahri", "Leona"],
            "enemies": ["Vayne", "Lulu", "Zac", "Syndra", "Jax"]
        },
        {
            "name": "Scenario 6: Anh's Game",
            "description": "Mid lane last pick from Anh's Ranked Game",
            "position": "MID",
            "allies": ["Maokai", "Nunu & Willump", "Yone", "Ziggs"],
            "enemies": ["Shaco", "Morgana", "Ashe", "Lux", "Tryndamere"]
        }
    ]

    print(f"\n[SYSTEM] Running {len(test_cases)} Test Cases...\n")
    print("="*60)

    for test in test_cases:
        print(f"\n[TEST] {test['name']} (Position: {test['position']})")
        print(f"[ALLIES] {test['allies']}")
        print(f"[ENEMIES] {test['enemies']}")
        print(f"   Goal: {test['description']}")
        
        try:
            # Use the simulator to evaluate role-valid candidates
            recommendations = simulator.evaluate_candidates(
                allies=test['allies'], 
                enemies=test['enemies'], 
                position=test['position']
            )
            
            if not recommendations:
                print("    [EMPTY] No valid champions found for this role/criteria.")
            
            for j, rec in enumerate(recommendations, 1):
                print(f"    [CHOICE] Pick {j}: {rec['name'].ljust(15)} | Win Prob: {rec['score']:.2%}")
                
        except Exception as e:
            print(f"   [FAILED] Error during execution: {e}")
            
        print("="*60)

if __name__ == "__main__":
    run_test_suite()