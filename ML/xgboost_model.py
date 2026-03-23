import os
import json
import pandas as pd
import numpy as np
import xgboost as xgb
import optuna 
import shap
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, KFold
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class DraftModelTrainer:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        self.client: Client = None
        
        self.feature_cols = [
            'anti_dive_score', 'kiting_delta', 
            'frontline_survival_index', 'catch_delta', 'raw_range_delta'
        ]
        self.target_col = 'label'
        self.scaler = StandardScaler()
        self.best_params = None

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
        df[self.feature_cols] = self.scaler.fit_transform(df[self.feature_cols])
        X = df[self.feature_cols]
        y = df[self.target_col].astype(int)
        
        # We split into 'Experimental Data' (train) and 'Vault Data' (test)
        # Optuna NEVER sees the Vault Data.
        return train_test_split(X, y, test_size=0.15, random_state=42)
    
    def tune_hyperparameters(self, x_train, y_train):
        """Uses 5-Fold Cross-Validation so the parameters are stable, not lucky."""
        print("[OPTUNA] Starting K-Fold Cross-Validation...")

        def objective(trial):
            param = {
                'objective': 'binary:logistic',
                'n_estimators': trial.suggest_int('n_estimators', 100, 600),
                'max_depth': trial.suggest_int('max_depth', 2, 4), 
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.05),
                'subsample': trial.suggest_float('subsample', 0.6, 0.8),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 0.8),
                'min_child_weight': trial.suggest_int('min_child_weight', 5, 15),
                'random_state': 42,
                'early_stopping_rounds': 20 
            }
                
            kf = KFold(n_splits=5, shuffle=True, random_state=42)
            cv_scores = []

            for t_idx, v_idx in kf.split(x_train):
                xt, xv = x_train.iloc[t_idx], x_train.iloc[v_idx]
                yt, yv = y_train.iloc[t_idx], y_train.iloc[v_idx]

                model = xgb.XGBClassifier(**param)
                # Removed early_stopping_rounds from fit()
                model.fit(xt, yt, eval_set=[(xv, yv)], verbose=False)
                
                preds = model.predict_proba(xv)[:, 1]
                cv_scores.append(roc_auc_score(yv, preds))
            
            return np.mean(cv_scores)

        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=30)
        
        self.best_params = study.best_params
        print(f"[OPTUNA] Most Stable CV ROC-AUC: {study.best_value:.4f}")
        return self.best_params

    def finalize_and_explain(self, x_train, y_train, x_test, y_test):
        """Trains final model with Early Stopping protection."""
        if self.best_params is None:
            raise ValueError("[ERROR] Best params not found. Ensure Optuna study completed.")

        print("[MODEL] Training production model with Early Stopping...")
        
        # Split a small validation set from training for final early stopping
        xt, xv, yt, yv = train_test_split(x_train, y_train, test_size=0.1, random_state=42)

        # Merge best_params with early_stopping for the final fit
        final_params = self.best_params.copy()
        final_params['early_stopping_rounds'] = 50

        self.model = xgb.XGBClassifier(**final_params)
        self.model.fit(
            xt, yt, 
            eval_set=[(xv, yv)], 
            verbose=False
        )

        probs = self.model.predict_proba(x_test)[:, 1]
        print(f"[FINAL STATS] Unbiased ROC-AUC: {roc_auc_score(y_test, probs):.4f}")
        # SHAP
        explainer = shap.TreeExplainer(self.model)
        shap_values = explainer.shap_values(x_test)
        plt.figure(figsize=(10, 6))
        shap.summary_plot(shap_values, x_test, feature_names=self.feature_cols, show=False)
        os.makedirs("models", exist_ok=True)
        plt.savefig("models/shap_summary.png")

    def save_artifacts(self):
        self.model.save_model("models/champion_model.json")
        with open("models/feature_list.json", 'w') as f:
            json.dump(self.feature_cols, f)
        print("[STORAGE] Artifacts saved.")

if __name__ == "__main__":
    trainer = DraftModelTrainer()
    trainer.init_connection()
    data = trainer.load_training_data()
    x_train, x_test, y_train, y_test = trainer.preprocess(data)
    
    trainer.tune_hyperparameters(x_train, y_train)
    trainer.finalize_and_explain(x_train, y_train, x_test, y_test)
    trainer.save_artifacts()