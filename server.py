from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

import psycopg2
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

client = OpenAI()
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": int(os.getenv("DB_PORT", 5432))
}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

class NLQuery(BaseModel):
    question: str

DB_SCHEMA = "Table employees: id (int), name (text), age (int)"

def run_query(sql):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            sql_lower = sql.strip().lower()
            if sql_lower.startswith("select"):
                cur.execute(sql)
                return {"type": "select", "data": cur.fetchall()}
            elif sql_lower.startswith("insert"):
                cur.execute(sql)
                conn.commit()
                return {"type": "insert", "rowcount": cur.rowcount}
            else:
                raise Exception("Only SELECT and INSERT queries are allowed.")

@app.post("/ask_db")
def ask_db(data: NLQuery):
    prompt = (
        f"You are an expert SQL assistant. Only use this table and columns:\n"
        f"{DB_SCHEMA}\n"
        f"Question: {data.question}\n"
        "Reply with ONLY a safe SELECT or INSERT SQL query (no explanation, no DML except INSERT, no DROP/DELETE/UPDATE/ALTER):"
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200
    )
    sql = response.choices[0].message.content.strip()
    if not (sql.lower().startswith("select") or sql.lower().startswith("insert")):
        raise HTTPException(status_code=400, detail="LLM did not generate a SELECT or INSERT query. Aborting for safety.")
    try:
        qresult = run_query(sql)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Format the result for the frontend
    if qresult["type"] == "select":
        results = qresult["data"]
        return {"sql": sql, "results": results}
    elif qresult["type"] == "insert":
        return {"sql": sql, "results": f"Inserted {qresult['rowcount']} row(s)."}
    else:
        return {"sql": sql, "results": "Unknown result."}
