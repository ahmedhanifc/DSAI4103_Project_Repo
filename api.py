import os                                                                                 
import asyncio
from contextlib import asynccontextmanager                                                
from fastapi import FastAPI                                                               
import pandas as pd
import json                                                                               
import joblib                                                                           
from openai import OpenAI
from dotenv import load_dotenv                                                            

INTERVAL_SECONDS = 10  # change this to control frequency                                 
                                                                                        
predictions_store = []                                                                    
model = scaler = col_stats = model_numerical_columns = client = None                    
                                                                                        

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

def load_json(filepath):                                                                  
    with open(filepath, 'r') as f:
        return json.load(f)                                                               
                                                                                        
def score_row(raw_row: dict) -> dict:
    input_df = pd.DataFrame([raw_row])
    scaled = input_df.copy()                                                              
    scaled[model_numerical_columns] = scaler.transform(input_df[model_numerical_columns])
    proba = float(model.predict_proba(scaled)[:, 1][0])                                   
    return {                                                                              
        **raw_row,
        "probability": round(proba, 4),                                                   
        "prediction": int(proba >= 0.1),                                                
        "timestamp": pd.Timestamp.now().isoformat(),
    }                                                                                     

async def prediction_loop():                                                              
    while True:                                                                         
        try:
            raw_row = await asyncio.to_thread(llm_generate_row, client, "gpt-4o-mini",
col_stats)                                                                                
            result = score_row(raw_row)
            predictions_store.append(result)                                              
            print(f"[{result['timestamp']}] prediction={result['prediction']} | proba={result['probability']:.4f}")                                                       
        except Exception as e:
            print(f"Error: {e}")                                                          
        await asyncio.sleep(INTERVAL_SECONDS)                                           


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, scaler, col_stats, model_numerical_columns, client                      
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