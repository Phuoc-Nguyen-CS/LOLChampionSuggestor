import os
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, log_loss
from sklearn.preprocessing import StandardScaler
from supabase import create_client, Client
import json

class DraftModelTrainer:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        self.client: Client = None
        
        self.feature_cols = [
            'range_delta', 'phys_dmg_delta', 'magic_dmg_delta', 'waveclear_delta',
            'mobility_delta', 'lockdown_delta', 'pick_delta', 'save_delta',
            'peel_delta', 'steroid_delta', 'tankiness_delta'
        ]
        self.target_col = 'label'
        self.scaler = StandardScaler()

    def init_connection(self):
        self.client = create_client(self.supabase_url, self.supabase_key)
        print("[INFO] Connected to Supabase.")

    def load_training_data(self) -> pd.DataFrame:
        print("[DATABASE] Pulling training data...")
        all_data = []
        offset, chunk_size = 0, 1000
        while True:
            res = self.client.table("xgboost_training_view").select("*").range(offset, offset + chunk_size - 1).execute()
            if not res.data: break
            all_data.extend(res.data)
            offset += chunk_size
        return pd.DataFrame(all_data)

    def preprocess(self, df: pd.DataFrame):
        df = df.fillna(0)
        
        # FEATURE INTERACTION: Support utility * Total Team Damage
        # This highlights the 'Force Multiplier' effect of Enchanters
        df['synergy_index'] = (df['peel_delta'] + df['save_delta']) * \
                              (df['phys_dmg_delta'].abs() + df['magic_dmg_delta'].abs())
        
        self.feature_cols.append('synergy_index')

        # STANDARD SCALING: Normalizes tankiness (1000s) and peel (1-5)
        df[self.feature_cols] = self.scaler.fit_transform(df[self.feature_cols])

        X = df[self.feature_cols]
        y = df[self.target_col].astype(int)
        return train_test_split(X, y, test_size=0.15, random_state=42)

    def train_model(self, x_train, y_train, x_test, y_test):
        print("[MODEL] Training Classifier...")
        
        params = {
            'objective': 'binary:logistic',
            'n_estimators': 2000,
            'learning_rate': 0.02,
            'max_depth': 5,
            'subsample': 0.6,
            'colsample_bytree': 0.6,
            'gamma': 1,
            'random_state': 42,
            'early_stopping_rounds': 100 
        }

        self.model = xgb.XGBClassifier(**params)
        
        # Remove early_stopping_rounds from here
        self.model.fit(
            x_train, y_train,
            eval_set=[(x_test, y_test)],
            verbose=False
        )
        print("[MODEL] Training Completed.")

    def evaluate(self, x_test, y_test):
        preds = self.model.predict(x_test)
        probs = self.model.predict_proba(x_test)[:, 1]
        
        print(f"[STATS] Accuracy: {accuracy_score(y_test, preds):.4f}")
        print(f"[STATS] ROC-AUC Score: {roc_auc_score(y_test, probs):.4f}")
        print(f"[STATS] Log Loss: {log_loss(y_test, probs):.4f}")

        # Explainable AI: What is actually winning games?
        importance = sorted(zip(self.feature_cols, self.model.feature_importances_), key=lambda x: x[1], reverse=True)
        print("[ANALYSIS] Top Win Drivers:")
        for feat, score in importance[:5]:
            print(f" - {feat}: {score:.4f}")

if __name__ == "__main__":
    trainer = DraftModelTrainer()
    trainer.init_connection()
    data = trainer.load_training_data()
    x_train, x_test, y_train, y_test = trainer.preprocess(data)
    trainer.train_model(x_train, y_train, x_test, y_test)
    trainer.evaluate(x_test, y_test)