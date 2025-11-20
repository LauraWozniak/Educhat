import os, json
from typing import List, Optional
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY","")
QDRANT_URL     = os.environ.get("QDRANT_URL","http://qdrant:6333")
COLLECTION     = os.environ.get("QDRANT_COLLECTION","sentinel_docs")
EMBED_MODEL    = os.environ.get("EMBED_MODEL","text-embedding-3-small")
MIN_SCORE      = float(os.environ.get("MIN_SCORE","0.7"))
TOP_K          = int(os.environ.get("TOP_K","5"))

BLOCK_WORDS = {"password","admin access","bypass","prompt injection"}

app = FastAPI(title="educhat-embed-chat", version="1.0")

class AnalyzeRequest(BaseModel):
    logline: str
    mode: Optional[str] = "similarity"  # future: "classify"

class IngestItem(BaseModel):
    title: str
    content: str
    tags: Optional[List[str]] = []

def embed_text(client: OpenAI, text: str):
    r = client.embeddings.create(model=EMBED_MODEL, input=[text])
    return r.data[0].embedding

def qdrant_search(vec):
    body = {"vector": vec, "limit": TOP_K, "with_payload": True, "with_vector": False}
    r = requests.post(f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
                      headers={"Content-Type":"application/json"},
                      data=json.dumps(body), timeout=60)
    if r.status_code >= 400:
        raise HTTPException(502, f"Qdrant-Fehler: {r.status_code} {r.text}")
    return r.json().get("result", [])

@app.get("/health")
def health():
    return {"status":"ok"}

@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    if not OPENAI_API_KEY:
        raise HTTPException(500, "OPENAI_API_KEY fehlt")
    if any(w in req.logline.lower() for w in BLOCK_WORDS):
        return {"alert":"blocked","reason":"Sicherheits-Schlüsselwort erkannt"}

    client = OpenAI(api_key=OPENAI_API_KEY)
    vec = embed_text(client, req.logline)
    hits = qdrant_search(vec)
    max_score = hits[0]["score"] if hits else 0.0
    if not hits or max_score < MIN_SCORE:
        return {"alert":"unknown","reason":"Keine ausreichende Ähnlichkeit", "max_score":max_score, "hits":[]}

    evidence = []
    for h in hits:
        p = h.get("payload", {}) or {}
        evidence.append({"score":h.get("score",0.0),"title":p.get("title",""),"content":p.get("content","")[:400]})
    return {"alert":"similar-pattern","max_score":max_score, "evidence": evidence[:3]}

@app.post("/ingest")
def ingest(items: List[IngestItem]):
    # einfacher Upsert für API-Nutzer
    points=[]
    for i, it in enumerate(items, start=1):
        points.append({
          "id": i,
          "vector": [0.0]*1536,  # Dummy – echtes Ingest bitte über Service A oder Embedding hier erweitern
          "payload": {"title": it.title, "content": it.content, "tags": it.tags, "source": "api:manual"}
        })
    r = requests.put(f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true",
                     headers={"Content-Type":"application/json"},
                     data=json.dumps({"points":points}))
    if r.status_code >= 400:
        raise HTTPException(502, f"Upsert-Fehler: {r.status_code} {r.text}")
    return {"status":"ok","count":len(points)}