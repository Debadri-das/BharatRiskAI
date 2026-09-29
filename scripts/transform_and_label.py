"""
Transform raw data into BharatRiskAI model training format and label it.

This script ingests raw data (e.g., CSV, JSON, or dictionary lists) and converts it into the expected feature format for the model.
It also automatically labels data using domain-specific heuristics.
"""

from pathlib import Path
import json
import pandas as pd
import numpy as np
from typing import Dict, List, Union

import sys
sys.path.append("C:\\Users\\datta\\BharatRiskAI")
from ml.models.baseline import heuristic_predict
from ml.preprocessing.clean import FEATURES


# --- Core Transformation Logic ---

def transform_raw_to_features(raw_data: Union[pd.DataFrame, List[Dict], Dict[str, List[float]]]) -> pd.DataFrame:
    """
    Convert raw data into the expected feature format.
    
    Args:
        raw_data: Raw data in CSV, JSON, or dictionary format.
    
    Returns:
        A pandas DataFrame with the expected feature columns.
    """
    # Convert raw data to DataFrame if it's not already
    if isinstance(raw_data, dict):
        raw_df = pd.DataFrame([raw_data])
    elif isinstance(raw_data, list):
        raw_df = pd.DataFrame(raw_data)
    else:
        raw_df = raw_data
    
    # Ensure all required features are present, defaulting to 0 if missing
    for feature in FEATURES:
        if feature not in raw_df.columns:
            raw_df[feature] = 0
    
    # Clean and normalize features
    cleaned_df = raw_df.copy()
    for feature in FEATURES:
        cleaned_df[feature] = cleaned_df[feature].fillna(cleaned_df[feature].median()).clip(lower=0)
    
    return cleaned_df


def label_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Label data using heuristic_predict to generate risk_score.
    
    Args:
        df: DataFrame with features ready for labeling.
    
    Returns:
        DataFrame with an added risk_score column.
    """
    df["risk_score"] = df.apply(lambda row: heuristic_predict(row.to_dict()), axis=1)
    return df


def save_processed_data(df: pd.DataFrame, output_path: Path) -> None:
    """
    Save processed data to CSV.
    
    Args:
        df: Processed DataFrame.
        output_path: Path to save the output file.
    """
    df.to_csv(output_path, index=False)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Transform and label raw data for BharatRiskAI model training.")
    parser.add_argument("--input", type=str, required=True, help="Path to input raw data file (CSV, JSON, or dictionary list)")
    parser.add_argument("--output", type=str, required=True, help="Path to save processed data")
    parser.add_argument("--raw-format", type=str, default="csv", choices=["csv", "json", "dict"], help="Format of input data")
    
    args = parser.parse_args()
    
    # Load raw data
    if args.raw_format == "csv":
        raw_data = pd.read_csv(args.input)
    elif args.raw_format == "json":
        with open(args.input, "r") as f:
            raw_data = json.load(f)
    else:  # dict
        with open(args.input, "r") as f:
            raw_data = json.load(f)
    
    # Transform and label data
    processed_df = transform_raw_to_features(raw_data)
    labeled_df = label_data(processed_df)
    
    # Save processed data
    output_path = Path(args.output)
    save_processed_data(labeled_df, output_path)
    
    print(f"Successfully transformed and labeled data. Output saved to: {output_path}")


if __name__ == "__main__":
    main()