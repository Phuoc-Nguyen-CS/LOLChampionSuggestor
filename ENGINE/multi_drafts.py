import os
from dotenv import load_dotenv
from inference_engine import DraftInference

# Load .env before doing anything else
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

def run_test_suite():
    print("Initializing Inference Engine for Test Suite...")
    engine = DraftInference()
    
    # Test scenarios
    test_cases = [
        {
            "name": "Scenario 1: The Synergy",
            "description": "Looking for a Jungler to synergize with a heavy-engage Mid/Top duo.",
            "position": "JUNGLE",
            "rank": "EMERALD",
            "allies": [
                {"name": "Orianna", "damage_type": "AP", "role_class": "MAGE", "cc_tier": 2},
                {"name": "Malphite", "damage_type": "AP", "role_class": "TANK", "cc_tier": 3}
            ],
            "enemies": [
                {"name": "Yasuo", "damage_type": "AD", "role_class": "FIGHTER", "cc_tier": 1},
                {"name": "Jinx", "damage_type": "AD", "role_class": "MARKSMAN", "cc_tier": 1}
            ]
        },
        {
            "name": "Scenario 2: The 'All AD'",
            "description": "Team drafted all AD. Enemy drafted heavy Armor tanks. Top laner MUST pick AP.",
            "position": "TOP",
            "rank": "GRANDMASTER",
            "allies": [
                {"name": "Zed", "damage_type": "AD", "role_class": "ASSASSIN", "cc_tier": 1},
                {"name": "Talon", "damage_type": "AD", "role_class": "ASSASSIN", "cc_tier": 1},
                {"name": "Draven", "damage_type": "AD", "role_class": "MARKSMAN", "cc_tier": 1},
                {"name": "Pyke", "damage_type": "AD", "role_class": "ASSASSIN", "cc_tier": 2}
            ],
            "enemies": [
                {"name": "Rammus", "damage_type": "AP", "role_class": "TANK", "cc_tier": 3},
                {"name": "Ornn", "damage_type": "AD", "role_class": "TANK", "cc_tier": 3},
                {"name": "Jhin", "damage_type": "AD", "role_class": "MARKSMAN", "cc_tier": 1},
                {"name": "Braum", "damage_type": "AP", "role_class": "TANK", "cc_tier": 3},
                {"name": "Orianna", "damage_type": "AP", "role_class": "MAGE", "cc_tier": 2}
            ]
        },
        {
            "name": "Scenario 3: Protect the President",
            "description": "Team has a hypercarry. Enemies have heavy dive assassins.",
            "position": "SUPPORT",
            "rank": "CHALLENGER",
            "allies": [
                {"name": "Kog'Maw", "damage_type": "AP", "role_class": "MARKSMAN", "cc_tier": 1},
                {"name": "Ornn", "damage_type": "AP", "role_class": "TANK", "cc_tier": 3}
            ],
            "enemies": [
                {"name": "Talon", "damage_type": "AD", "role_class": "ASSASSIN", "cc_tier": 1},
                {"name": "Akali", "damage_type": "AP", "role_class": "ASSASSIN", "cc_tier": 1},
                {"name": "Vi", "damage_type": "AD", "role_class": "FIGHTER", "cc_tier": 2}
            ]
        },
        {
            "name": "Scenario 4: First Pick (Blind Draft)",
            "description": "No allies, no enemies. Testing if the model suggests universally safe/strong Mid laners.",
            "position": "BOTTOM",
            "rank": "CHALLENGER",
            "allies": [],
            "enemies": []
        },
        {
            "name": "Scenario 5: Last Pick Counter",
            "description": "Board is fully visible. Testing exact counter-picking logic for the Bottom Lane.",
            "position": "BOTTOM",
            "rank": "DIAMOND",
            "allies": [
                {"name": "Shen", "damage_type": "AD", "role_class": "TANK", "cc_tier": 3},
                {"name": "Amumu", "damage_type": "AP", "role_class": "TANK", "cc_tier": 3},
                {"name": "Ahri", "damage_type": "AP", "role_class": "MAGE", "cc_tier": 2},
                {"name": "Leona", "damage_type": "AP", "role_class": "SUPPORT", "cc_tier": 3}
            ],
            "enemies": [
                {"name": "Vayne", "damage_type": "AD", "role_class": "MARKSMAN", "cc_tier": 1},
                {"name": "Lulu", "damage_type": "AP", "role_class": "SUPPORT", "cc_tier": 2},
                {"name": "Zac", "damage_type": "AP", "role_class": "TANK", "cc_tier": 3},
                {"name": "Syndra", "damage_type": "AP", "role_class": "MAGE", "cc_tier": 2},
                {"name": "Jax", "damage_type": "AD", "role_class": "FIGHTER", "cc_tier": 2}
            ]
        },
        {
            "name": "Scenario 6: Anh's Game",
            "description": "Mid lane last pick from Anh's Ranked Game",
            "position": "MID",
            "rank": "DIAMOND",
            "allies": [
                {"name": "Maokai", "damage_type": "AP", "role_class": "TANK", "cc_tier": 3},
                {"name": "Nunu", "damage_type": "AP", "role_class": "TANK", "cc_tier": 3},
                {"name": "Yone", "damage_type": "AD", "role_class": "FIGHTER", "cc_tier": 2},
                {"name": "Ziggs", "damage_type": "AP", "role_class": "BOTTOM", "cc_tier": 1}
            ],
            "enemies": [
                {"name": "Shaco", "damage_type": "AD", "role_class": "ASSASSIN", "cc_tier": 2},
                {"name": "Morgana", "damage_type": "AP", "role_class": "SUPPORT", "cc_tier": 3},
                {"name": "Ashe", "damage_type": "AD", "role_class": "MARKSMAN", "cc_tier": 3},
                {"name": "Lux", "damage_type": "AP", "role_class": "MAGE", "cc_tier": 2},
                {"name": "Tryndamere", "damage_type": "AD", "role_class": "FIGHTER", "cc_tier": 1}
            ]
        }
    ]

    print(f"\nRunning {len(test_cases)} Test Cases...\n")
    print("="*60)

    for i, test in enumerate(test_cases, 1):
        print(f"\n[TEST] {test['name']}")
        print(f"   Context: Rank: {test['rank']} | Target Role: {test['position']}")
        print(f"   Goal: {test['description']}")
        
        allies_names = [a['name'] for a in test['allies']] if test['allies'] else "None"
        enemies_names = [e['name'] for e in test['enemies']] if test['enemies'] else "None"
        
        print(f"   Allies:  {allies_names}")
        print(f"   Enemies: {enemies_names}")
        print("-" * 40)

        try:
            # Run the engine
            recommendations = engine.suggest_best_pick(
                allies=test['allies'], 
                enemies=test['enemies'], 
                rank=test['rank'], 
                position=test['position']
            )
            
            # Print Results
            for j, rec in enumerate(recommendations, 1):
                # Check if it hit the default 0.5 score
                confidence_flag = "(Low Data/Default)" if rec['score'] == 0.5 else ""
                print(f"    [CHOICE] Pick {j}: {rec['name'].ljust(15)} | Win Prob: {rec['score']:.2%} {confidence_flag}")
                
        except Exception as e:
            print(f"   [FAILED] Test Failed with error: {e}")
            
        print("="*60)

if __name__ == "__main__":
    run_test_suite()