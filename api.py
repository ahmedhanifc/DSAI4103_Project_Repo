import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
import pandas as pd
import json
import joblib
import requests
from openai import OpenAI
from dotenv import load_dotenv
import random                                                            

INTERVAL_SECONDS = 5  # change this to control frequency

CATEGORY_COLUMNS = [
    ("product_category_grouped_electronics", "Electronics"),
    ("product_category_grouped_fashion", "Fashion"),
    ("product_category_grouped_food_drink", "Food & Drink"),
    ("product_category_grouped_furniture", "Furniture"),
    ("product_category_grouped_health_beauty", "Health & Beauty"),
    ("product_category_grouped_home_appliances", "Home Appliances"),
    ("product_category_grouped_home_comfort", "Home Comfort"),
    ("product_category_grouped_leisure_media", "Leisure & Media"),
    ("product_category_grouped_others", "Others"),
]

def derive_product_category(row: dict) -> str:
    for col, label in CATEGORY_COLUMNS:
        if row.get(col) == 1:
            return label
    return "Others"

def derive_seller_prep_bucket(days: float) -> str:
    if days <= 5:  return "1-5d"
    if days <= 10: return "6-10d"
    if days <= 15: return "11-15d"
    if days <= 20: return "16-20d"
    return "20d+"

def compute_rolling(store: list, window: int = 20) -> dict:
    recent = store[-window:]
    total = len(recent)
    if total == 0:
        return {"rolling_atrisk_rate": 0.0, "rolling_avg_prob": 0.0,
                "avg_prep_flagged": None, "avg_lag_flagged": None}
    flagged = [r for r in recent if r["prediction"] == 1]
    return {
        "rolling_atrisk_rate": round(len(flagged) / total, 4),
        "rolling_avg_prob":    round(sum(r["probability"] for r in recent) / total, 4),
        "avg_prep_flagged":    round(sum(r["seller_prep_days"] for r in flagged) / len(flagged), 2) if flagged else None,
        "avg_lag_flagged":     round(sum(r["approval_lag_hrs"]  for r in flagged) / len(flagged), 2) if flagged else None,
    }

HISTORY_FILE = "predictions_history.json"

def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_history(store: list):
    with open(HISTORY_FILE, "w") as f:
        json.dump(store, f)

predictions_store = []
model = scaler = col_stats = model_numerical_columns = client = powerbi_push_url = None                    
                                                                                        

def load_package(filepath):                                                               
    return joblib.load(filepath)                                                        

def setup():
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key and api_key != "YOUR_KEY_HERE":
        print("API key loaded")
        return OpenAI()
    else:
        print("API key not found - check your .env file")
        return None

def push_to_powerbi(result: dict):
    url = powerbi_push_url
    # print(f"Pushing to Power BI: {result}")
    print("url:", url)
    if not url:
        return
    payload = [{
        "timestamp":            result["timestamp"],
        "probability":          result["probability"],
        "prediction":           result["prediction"],
        "seller_prep_days":     result.get("seller_prep_days"),
        "approval_lag_hrs":     result.get("approval_lag_hrs"),
        "estimated_window_days": result.get("estimated_window_days"),
        "product_category":     result.get("product_category"),
        "seller_prep_bucket":   result.get("seller_prep_bucket"),
        "rolling_atrisk_rate":  result.get("rolling_atrisk_rate"),
        "rolling_avg_prob":     result.get("rolling_avg_prob"),
        "avg_prep_flagged":     result.get("avg_prep_flagged"),
        "avg_lag_flagged":      result.get("avg_lag_flagged"),
    }]

    print(payload)
    try:
        print("Result pushed to Power BI")
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Power BI push error: {e}")                                                                       

# def build_column_stats(X: pd.DataFrame) -> dict:                                          
#     stats = {}                                                                          
#     for col in X.columns:                                                                 
#         s = X[col]
#         if s.nunique() <= 2:                                                              
#             stats[col] = {"type": "binary", "p": round(float(s.mean()), 4)}             
#         else:                                                                             
#             stats[col] = {
#                 "type": "continuous",                                                     
#                 "min": round(float(s.min()), 4),                                        
#                 "max": round(float(s.max()), 4),                                          
#                 "mean": round(float(s.mean()), 4),                                      
#                 "p25": round(float(s.quantile(0.25)), 4),                                 
#                 "p75": round(float(s.quantile(0.75)), 4),
#             }                                                                             
#     return stats                  

def build_column_stats(X: pd.DataFrame, positive_bias: float = 0.0) -> dict:
    stats = {}                                                                            
    for col in X.columns:                                 
        s = X[col]                                                                        
        if s.nunique() <= 2:                              
            p = float(s.mean())
            p = p + positive_bias * (1 - p)
            stats[col] = {"type": "binary", "p": round(p, 4)}                             
        else:
            col_min = float(s.min())                                                      
            col_max = float(s.max())                                                      
            mean = float(s.mean())
            p25 = float(s.quantile(0.25))                                                 
            p75 = float(s.quantile(0.75))                 
                                                                                        
            mean = mean + positive_bias * (col_max - mean)
            p25 = p25 + positive_bias * (col_max - p25) * 0.5                             
            p75 = p75 + positive_bias * (col_max - p75) * 0.5                             

            stats[col] = {                                                                
                "type": "continuous",                     
                "min": round(col_min, 4),                                                 
                "max": round(col_max, 4),
                "mean": round(mean, 4),                                                   
                "p25": round(p25, 4),                     
                "p75": round(p75, 4),
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

def load_json(filepath):                                                                  
    with open(filepath, 'r') as f:
        return json.load(f)                                                               
                                                                                        
def score_row(raw_row: dict) -> dict:
    input_df = pd.DataFrame([raw_row])
    scaled = input_df.copy()                                                              
    scaled[model_numerical_columns] = scaler.transform(input_df[model_numerical_columns])
    proba = float(model.predict_proba(scaled)[:, 1][0])
    random_number = random.random()
    print(f"Generated random number for bias injection: {random_number:.4f}")
    if random_number > 0.3:
      print("Injecting random positive bias to simulate more at-risk cases for demo purposes")                                                         
      boost = random.choice([0.2, 0.3])                                                     
      proba = min(1.0, proba + boost)
      print(f"Original proba: {proba-boost:.4f}, boosted proba: {proba:.4f}")

    return {
        **raw_row,
        "probability": round(proba, 4),
        "prediction": int(proba >= 0.1),
        "timestamp": pd.Timestamp.now().isoformat(),
        "product_category": derive_product_category(raw_row),
        "seller_prep_bucket": derive_seller_prep_bucket(raw_row.get("seller_prep_days", 0)),
    }                                                                                     

async def prediction_loop():                                                              
    while True:                                                                         
        try:
            raw_row = await asyncio.to_thread(llm_generate_row, client, "gpt-4o-mini", col_stats)
            result = score_row(raw_row)
            predictions_store.append(result)
            save_history(predictions_store)
            rolling = compute_rolling(predictions_store)
            result = {**result, **rolling}
            print(f"[{result['timestamp']}] prediction={result['prediction']} | proba={result['probability']:.4f} | at-risk(20)={rolling['rolling_atrisk_rate']:.2%}")
            await asyncio.to_thread(push_to_powerbi, result)
        except Exception as e:
            print(f"Error: {e}")                                                          
        await asyncio.sleep(INTERVAL_SECONDS)                                           


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, scaler, col_stats, model_numerical_columns, client, powerbi_push_url, predictions_store
    predictions_store = load_history()
    print(f"Loaded {len(predictions_store)} predictions from history.")
    powerbi_push_url = os.environ.get("POWERBI_PUSH_URL")                  
    client = setup()
    model = load_package("./outputs/final_xgb_model.pkl")                                 
    scaler = load_package("./outputs/full_data_scaler.pkl")                             
    X = pd.read_csv("./outputs/final_X.csv")                                              
    model_numerical_columns = load_json("./outputs/model_numerical_features.json")
    col_stats = build_column_stats(X)                                                     
    print(f"Setup complete. Generating a prediction every {INTERVAL_SECONDS}s.")          
    task = asyncio.create_task(prediction_loop())
    yield                                                                                 
    task.cancel()                                                                       
                                                                                        

app = FastAPI(lifespan=lifespan)                                                          
                                                                                        
@app.get("/predictions")
def get_predictions():
    """All predictions since server start."""
    return predictions_store                                                              

@app.get("/predictions/latest")                                                           
def get_latest():                                                                       
    """Most recent prediction only."""
    if predictions_store:
        return predictions_store[-1]
    return {"message": "No predictions yet"}