import os
from inference_engine import DraftInference

def test_vacuum_simulation():
    # Initialize the engine (this loads .json models)
    engine = DraftInference()

    print("Starting Vacuum Test for Inference Engine...")

    # Define a Mock Draft State
    # In a real game, these would come from champion_profiles table
    # For a vacuum test, we use the 'DNA' structure model expects
    mock_allies = [
        {"name": "Jarvan IV", "damage_type": "AD", "role_class": "TANK", "cc_tier": 3},
        {"name": "Orianna", "damage_type": "AP", "role_class": "MAGE", "cc_tier": 2}
    ]
    
    mock_enemies = [
        {"name": "Yasuo", "damage_type": "AD", "role_class": "FIGHTER", "cc_tier": 1},
        {"name": "Malphite", "damage_type": "AP", "role_class": "TANK", "cc_tier": 3}
    ]

    # Define Context
    rank = "EMERALD"
    position = "JUNGLE"

    # Run Simulation
    print(f"Draft Context: {rank} - {position}")
    print(f"Allies: {[a['name'] for a in mock_allies]}")
    print(f"Enemies: {[e['name'] for e in mock_enemies]}")
    
    try:
        recommendations = engine.suggest_best_pick(mock_allies, mock_enemies, rank, position)
        
        print("\nTop Suggestions:")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec['name']} (Predicted Win Probability: {rec['score']:.2%})")
            
    except Exception as e:
        print(f"Test Failed: {e}")

if __name__ == "__main__":
    test_vacuum_simulation()