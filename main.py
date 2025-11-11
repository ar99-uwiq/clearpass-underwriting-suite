from fastapi import FastAPI, UploadFile, File
import pandas as pd
from shared.parsing import parse_financials, compute_ratios

app = FastAPI(title="ClearPass API", version="0.1.0")

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    if file.filename.lower().endswith(".csv"):
        df = pd.read_csv(file.file)
    else:
        df = pd.read_excel(file.file)
    basics, _ = parse_financials(df)
    ratios = compute_ratios(basics)
    return {"basics": basics, "ratios": ratios}
