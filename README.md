# Overview

This project is a delivery risk prediction system built on the Olist Brazilian e-commerce dataset. The notebook (main.ipynb) covers the full ML pipeline: ingesting and merging multiple CSVs (orders, customers, products, sellers, payments, reviews), engineering key features like seller_prep_days (time from order approval to carrier handoff) and approval_lag_hrs, then training an XGBoost classifier to flag orders at risk of late delivery. The pipeline includes EDA, outlier handling, class imbalance awareness, scaling, AutoML, explainability, and a fairness module. 

The API (api.py) is a FastAPI server that operationalises the model in real-time. Every 5 seconds it uses GPT-4o-mini to synthesise a realistic order row based on training data statistics, scores it through the XGBoost model, and streams the result — including rolling at-risk rates over the last 20 predictions — to a Power BI dashboard via a push dataset URL. A bias injection step inflates probabilities for demo purposes to simulate a higher rate of at-risk cases. Prediction history is persisted to disk and exposed via /predictions and /predictions/latest REST endpoints.

## How to Run

Running the Scoring Script
- uvicorn api:app --reload 