# The purpose of this script is to provide a scoring function that can be used in a production environment. It loads the trained model and the scaler, and then uses them to make predictions on new data.

import os
from fastapi import FastAPI                                                               
import pandas as pd
import json
import numpy as np
import joblib
import xgboost as xgb
from openai import OpenAI
from dotenv import load_dotenv



def load_package(filepath):
    """Load a package from a file."""
    return joblib.load(filepath)

def setup():
    """Set up the environment for scoring."""
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key and api_key != "YOUR_KEY_HERE":
        print("API key loaded")
        return OpenAI()
    else:
        print("API key not found - check your .env file")
        return None
    
def build_column_stats(X: pd.DataFrame) -> dict:                                        
      stats = {}
      for col in X.columns:
          s = X[col]
          if s.nunique() <= 2:                                                              
              stats[col] = {"type": "binary", "p": round(float(s.mean()), 4)}
          else:                                                                             
              stats[col] = {                                                              
                  "type": "continuous",                                                     
                  "min": round(float(s.min()), 4),                                        
                  "max": round(float(s.max()), 4),                                          
                  "mean": round(float(s.mean()), 4),
                  "p25": round(float(s.quantile(0.25)), 4),                                 
                  "p75": round(float(s.quantile(0.75)), 4),                                 
              }
      return stats 

def llm_generate_row(client, model_name: str, col_stats: dict) -> dict:
      prompt = f"""Generate one synthetic e-commerce order record for model scoring.        
                                                                                          
  Schema (per-column stats from real data):                                                 
  - binary: pick 0 or 1 using probability p
  - continuous: pick a plausible value within [min, max] consistent with mean               
                                                                                            
  Return ONLY a flat JSON object with exactly these keys as numbers.
                                                                                            
  Schema:                                                                                 
  {json.dumps(col_stats, indent=2)}
  """                                                                                       
      response = client.chat.completions.create(
          model=model_name,                                                                 
          temperature=0.7,                                                                
          response_format={"type": "json_object"},
          messages=[{"role": "user", "content": prompt}],
      )                                                                                     
      return json.loads(response.choices[0].message.content)

import json


def load_json(filepath):

    with open(filepath, 'r') as f:
        json_file = json.load(f)
    return json_file

if __name__ == "__main__":
    client = setup()
    model = load_package("./outputs/final_xgb_model.pkl")
    scaler = load_package("./outputs/full_data_scaler.pkl")                               

    X = pd.read_csv("./outputs/final_X.csv")
    model_numerical_columns = load_json("./outputs/model_numerical_features.json")                                          
    col_stats = build_column_stats(X)  
    print(col_stats)



    # loop
    
    for _ in range(5):                                                                                    
        print("Generating synthetic row via LLM...")
        raw_row = llm_generate_row(client, "gpt-4o-mini", col_stats)      
        print("raw_row:", raw_row)                    
                                                                      
        input_df = pd.DataFrame([{col: raw_row[col] for col in X.columns}])
        scaled_input = input_df.copy()
        scaled_input[model_numerical_columns] = scaler.transform(input_df[model_numerical_columns])
        THRESHOLD = 0.1
        prediction_proba = model.predict_proba(scaled_input)[:, 1]                                
        prediction = (prediction_proba >= THRESHOLD).astype(int)

        print(f"Prediction: {prediction[0]}  |  Probability: {prediction_proba[0]:.4f}")
                                                                                                                         
    # result_df = input_df.copy()
    # result_df["predicted_label"] = prediction
    # result_df["predicted_proba"] = proba                                                  

    # result_df.to_csv("./outputs/scored_results.csv", index=False)                         
    # print(f"Prediction: {prediction[0]}  |  Probability: {proba[0]:.4f}")