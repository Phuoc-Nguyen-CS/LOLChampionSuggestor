from abc import ABC, abstractmethod
from typing import Any, List
import pandas as pd
import logging

class ModelAdapter(ABC):
    """Abstract interface for all models to ensure engine compatibility."""
    @abstractmethod
    def predict(self, raw_data: pd.DataFrame) -> Any:
        pass

class XGBoostChampionAdapter(ModelAdapter):
    def __init__(self, model: Any, production_features: List[str], logger: logging.Logger = None):
        self.model = model
        # Features we are adding to the production
        self.production_features = production_features
        self.logger = logger or logging.getLogger(__name__)

    def _preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Handles feature alignment, noise reduction, and missing values.
        This is the 'Buffer' that prevents downstream breaks.
        """
        # 1. Noise Identification: Find columns in input that are NOT in production_features
        extra_features = set(df.columns) - set(self.production_features)
        if extra_features:
            self.logger.debug(f"Filtering out noisy features: {extra_features}")

        # 2. Alignment & Filling: Use reindex to both drop noise and fill missing ones.
        # This ensures the column order matches training exactly.
        missing_features = set(self.production_features) - set(df.columns)
        if missing_features:
            self.logger.warning(f"Missing expected features, filling with 0.0: {missing_features}")

        return df.reindex(columns=self.production_features, fill_value=0.0)

    def predict(self, raw_data: pd.DataFrame) -> Any:
        processed_data = self._preprocess(raw_data)
        return self.model.predict(processed_data)

    def predict_proba(self, raw_data: pd.DataFrame) -> Any:
        """Returns probabilities for classification tasks."""
        processed_data = self._preprocess(raw_data)
        if hasattr(self.model, 'predict_proba'):
            return self.model.predict_proba(processed_data)
        return None 