import pdfplumber
import pandas as pd
import re

def extract_tables_to_long(file_like) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(file_like) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    if not row or len(row) < 2:
                        continue
                    account = str(row[0]).strip()
                    value = str(row[1]).strip()
                    if account and re.search(r"[A-Za-z]", account) and re.search(r"[-\d,()]", value):
                        rows.append((account, value))
    df = pd.DataFrame(rows, columns=["Account","Value"]).dropna()
    if df.empty:
        return pd.DataFrame({"Account":[], "Value":[]})
    return df
