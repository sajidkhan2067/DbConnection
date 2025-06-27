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
# DB & OpenAI config from environment
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": int(os.getenv("DB_PORT", 5432))
}
# openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

class NLQuery(BaseModel):
    question: str

# Only employees table for the LLM's context
DB_SCHEMA = "Table employees: id (int), name (text), age (int)"

def run_query(sql):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            try:
                return cur.fetchall()
            except Exception:
                return "Query executed (no results fetched)"

@app.post("/ask_db")
def ask_db(data: NLQuery):
    prompt = (
        f"You are an expert SQL assistant. Only use this table and columns:\n"
        f"{DB_SCHEMA}\n"
        f"Question: {data.question}\n"
        "Reply with ONLY a safe SELECT, INSERT SQL query (no explanation, no DML, no DROP/DELETE/UPDATE):"
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200
    )
    sql = response.choices[0].message.content.strip()
    if not sql.lower().startswith("select"):
        raise HTTPException(status_code=400, detail="LLM did not generate a SELECT query. Aborting for safety.")
    try:
        results = run_query(sql)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"sql": sql, "results": results}