import os
import json
import pandas as pd
import numpy as np
import xgboost as xgb
import optuna 
import shap
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, KFold
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class DraftModelTrainer:
    def __init__(self):
        self.client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        
        self.feature_cols = [
            'engage_delta', 
            'catch_delta', 
            'range_delta', 
            'tankiness_delta',
            'synergy_delta'
        ]
        self.target_col = 'label'
        self.scaler = StandardScaler()
        self.best_params = None
        self.model = None

    def load_data(self):
        print("[DATABASE] Pulling training data...")
        response = self.client.table("xgboost_training_view").select("*").execute()
        df = pd.DataFrame(response.data).fillna(0)
        
        # Scaling is vital so large numbers (tankiness) don't drown out small numbers (engage)
        df[self.feature_cols] = self.scaler.fit_transform(df[self.feature_cols])
        
        X = df[self.feature_cols]
        y = df[self.target_col].astype(int)
        
        # Split 15% into a "Vault" that Optuna never sees
        return train_test_split(X, y, test_size=0.15, random_state=42)

    def tune_hyperparameters(self, x_train, y_train):
        """Automated search for best parameters using 5-Fold CV."""
        print("[OPTUNA] Searching for optimal parameters...")

        def objective(trial):
            param = {
                'objective': 'binary:logistic',
                'n_estimators': trial.suggest_int('n_estimators', 100, 600),
                'max_depth': trial.suggest_int('max_depth', 2, 4),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.05),
                'subsample': trial.suggest_float('subsample', 0.6, 0.9),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 0.9),
                'min_child_weight': trial.suggest_int('min_child_weight', 5, 20),
                'random_state': 42,
                'early_stopping_rounds': 20 # Modern API placement
            }
            
            kf = KFold(n_splits=5, shuffle=True, random_state=42)
            scores = []
            
            for t_idx, v_idx in kf.split(x_train):
                xt, xv = x_train.iloc[t_idx], x_train.iloc[v_idx]
                yt, yv = y_train.iloc[t_idx], y_train.iloc[v_idx]
                
                model = xgb.XGBClassifier(**param)
                model.fit(xt, yt, eval_set=[(xv, yv)], verbose=False)
                
                probs = model.predict_proba(xv)[:, 1]
                scores.append(roc_auc_score(yv, probs))
                
            return np.mean(scores)

        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=30)
        self.best_params = study.best_params
        print(f"[OPTUNA] Best CV ROC-AUC: {study.best_value:.4f}")

    def finalize_and_explain(self, x_train, y_train, x_test, y_test):
        """Trains final model and generates SHAP report."""
        print("[MODEL] Finalizing production model...")
        
        final_params = self.best_params.copy()
        final_params['early_stopping_rounds'] = 50
        
        xt, xv, yt, yv = train_test_split(x_train, y_train, test_size=0.1, random_state=42)
        
        self.model = xgb.XGBClassifier(**final_params)
        self.model.fit(xt, yt, eval_set=[(xv, yv)], verbose=False)

        # Evaluation on the "Vault" Test Set
        probs = self.model.predict_proba(x_test)[:, 1]
        print(f"[FINAL STATS] Unbiased ROC-AUC: {roc_auc_score(y_test, probs):.4f}")

        # SHAP Plotting
        print("[SHAP] Generating logic visualization...")
        explainer = shap.TreeExplainer(self.model)
        shap_values = explainer.shap_values(x_test)
        
        plt.figure(figsize=(10, 6))
        shap.summary_plot(shap_values, x_test, feature_names=self.feature_cols, show=False)
        os.makedirs("models", exist_ok=True)
        plt.savefig("models/shap_summary.png", bbox_inches='tight')

    def save_artifacts(self):
        self.model.save_model("models/champion_model.json")
        with open("models/feature_list.json", 'w') as f:
            json.dump(self.feature_cols, f)
        print("[STORAGE] Artifacts saved. System is ready for Inference.")

if __name__ == "__main__":
    trainer = DraftModelTrainer()
    x_train, x_test, y_train, y_test = trainer.load_data()
    trainer.tune_hyperparameters(x_train, y_train)
    trainer.finalize_and_explain(x_train, y_train, x_test, y_test)
    trainer.save_artifacts()