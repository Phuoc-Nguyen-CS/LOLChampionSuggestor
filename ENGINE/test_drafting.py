import unittest
from unittest.mock import MagicMock
import pandas as pd
from inference_engine import InferenceEngine

class TestInferenceEngine(unittest.TestCase):
    
    def setUp(self):
        """Mocks the DB and XGBoost Model to test pure calculation logic."""
        self.engine = InferenceEngine("dummy.json", "dummy.json", db_client=None)
        self.engine.feature_cols = ['range_delta', 'mobility_delta', 'phys_dmg_delta']
        
        # Force the mock model to output a 65% win rate
        self.engine.model = MagicMock()
        self.engine.model.predict.return_value = [0.65] 
        
        # Inject Mock Data mimicking Layer 1 and 2
        mock_data = pd.DataFrame({
            'name': ['Annie', 'Zed', 'Ashe'],
            'lookup_name': ['annie', 'zed', 'ashe'],
            'attack_range': [600, 125, 600],
            'effective mobility': [0, 4, 0],
            'physical_dmg_share': [0.05, 0.95, 0.85]
        })
        self.engine.champion_data = mock_data

    def test_delta_calculation_math(self):
        """Verifies Allies - Enemies summation is mathematically flawless."""
        allies = ["Annie", "Ashe"]  # Range: 600 + 600 = 1200
        enemies = ["Zed"]           # Range: 125
        
        deltas = self.engine.calculate_deltas(allies, enemies)
        
        self.assertEqual(deltas['range_delta'], 1075.0) # 1200 - 125
        self.assertEqual(deltas['mobility_delta'], -4.0) # (0 + 0) - 4
        self.assertAlmostEqual(deltas['phys_dmg_delta'], -0.05, places=5) # (0.05+0.85) - 0.95

    def test_missing_champion_handling(self):
        """Ensures the engine cleanly rejects bad inputs."""
        with self.assertRaises(ValueError):
            self.engine.calculate_deltas(["Batman"], ["Zed"])

    def test_prediction_pipeline(self):
        """Verifies prediction returns properly formatted float."""
        deltas = {'range_delta': 100, 'mobility_delta': 2, 'phys_dmg_delta': 0.1}
        prob = self.engine.predict_win_probability(deltas)
        self.assertEqual(prob, 0.65)
        self.assertTrue(self.engine.model.predict.called)

if __name__ == "__main__":
    unittest.main()