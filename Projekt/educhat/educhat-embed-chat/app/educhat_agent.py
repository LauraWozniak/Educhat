import os, sys, json, re, time
from textwrap import fill
from datetime import datetime, timezone
from slugify import slugify
import requests
from openai import OpenAI

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
QDRANT_URL     = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION     = os.environ.get("QDRANT_COLLECTION", "sentinel_docs")
EMBED_MODEL    = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
TOP_K          = int(os.environ.get("TOP_K", "5"))
MIN_SCORE      = float(os.environ.get("MIN_SCORE", "0.65"))
WRAP_COLS      = int(os.environ.get("WRAP_COLS", "100"))

BLOCK_WORDS = {"password", "admin access", "bypass", "prompt injection"}

SENTINEL_SYSTEM_PROMPT = """(siehe README: SYSTEM PROMPT (SentinelAI))"""

def _die(msg, code=2):
    print(f"Fehler: {msg}", file=sys.stderr)
    sys.exit(code)

def _now():
    return datetime.now(timezone.utc).isoformat()

def ensure_collection():
    r = requests.get(f"{QDRANT_URL}/collections/{COLLECTION}", timeout=8)
    if r.status_code == 200:
        return
    body = {"vectors": {"size": 1536, "distance": "Cosine"}}
    r = requests.put(f"{QDRANT_URL}/collections/{COLLECTION}",
                     headers={"Content-Type":"application/json"},
                     data=json.dumps(body), timeout=30)
    if r.status_code >= 400:
        _die(f"Collection-Create fehlgeschlagen: {r.status_code} {r.text}")

def embed_texts(client: OpenAI, texts):
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]

def upsert_points(points):
    payload = {"points": points}
    r = requests.put(f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true",
                     headers={"Content-Type":"application/json"},
                     data=json.dumps(payload), timeout=120)
    if r.status_code >= 400:
        _die(f"Upsert fehlgeschlagen: {r.status_code} {r.text}")

def ingest_topic(client: OpenAI, topic: str, max_chunks=5):
    # einfache Generierung kurzer Chunks über Chat Completion
    sysmsg = "Erzeuge prägnante Textabschnitte (2–4 Sätze) zu einem Thema, JSON-Array mit title, content, tags."
    usermsg = f"Thema: {topic}\nErzeuge {max_chunks} Chunks als JSON-Array."
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":sysmsg},
                  {"role":"user","content":usermsg}],
        temperature=0.2,
        max_tokens=800
    )
    txt = resp.choices[0].message.content.strip()
    start, end = txt.find("["), txt.rfind("]")
    if start == -1 or end == -1:
        _die("Antwort enthielt kein JSON-Array.")
    chunks = json.loads(txt[start:end+1])[:max_chunks]
    vectors = embed_texts(client, [c.get("content","") for c in chunks])

    doc_id = f"doc-{slugify(topic) or 'topic'}"
    created_at = _now()
    points = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors), start=1):
        points.append({
            "id": int(time.time()*1000)+i,
            "vector": vec,
            "payload": {
                "title": chunk.get("title", f"Chunk {i}"),
                "content": chunk.get("content",""),
                "tags": chunk.get("tags", []),
                "topic": topic, "doc_id": doc_id,
                "chunk_id": i, "chunk_count": len(chunks),
                "created_at": created_at, "language": "de",
                "source": f"generated:{doc_id}"
            }
        })
    upsert_points(points)
    print(f"Ingestion abgeschlossen. Punkte: {len(points)} in Collection '{COLLECTION}'.")

def search(vector):
    body = {"vector": vector, "limit": TOP_K, "with_payload": True, "with_vector": False}
    r = requests.post(f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
                      headers={"Content-Type":"application/json"},
                      data=json.dumps(body), timeout=60)
    if r.status_code >= 400:
        _die(f"Search fehlgeschlagen: {r.status_code} {r.text}")
    return r.json().get("result", [])

def answer_from_hits(hits):
    if not hits: return "Ich weiß es nicht auf Basis der vorhandenen Daten."
    if hits[0].get("score",0.0) < MIN_SCORE:
        return "Ich weiß es nicht auf Basis der vorhandenen Daten."
    lines=[]
    for i,h in enumerate(hits, start=1):
        p=h.get("payload",{}) or {}
        lines.append(f"[{i}] {p.get('title','')}")
        if p.get("content"): lines.append(fill(p["content"], width=WRAP_COLS))
        lines.append(f"Quelle: {p.get('source','-')} | doc_id={p.get('doc_id','-')} | chunk={p.get('chunk_id','-')}")
        lines.append("")
    return "\n".join(lines).strip()

def run_chat():
    if any(b in os.environ.get("BLOCK_OVERRIDE","" ).lower() for b in ["true","1","yes"]):
        blocked = set()
    else:
        blocked = BLOCK_WORDS

    client = OpenAI(api_key=OPENAI_API_KEY)
    print("SentinelAI – Console-Chat (nur Inhalte aus Qdrant). ':exit' zum Beenden.")
    while True:
        try:
            q = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTschüss."); break
        if q.lower() in {":exit","exit",":q","quit"}: print("Tschüss."); break
        if any(w in q.lower() for w in blocked):
            print("Sicherheitsmeldung: Anfrage blockiert."); continue
        try:
            vec = embed_texts(client, [q])[0]
            hits = search(vec)
            print(answer_from_hits(hits))
            print("-"*60)
        except Exception as e:
            print(f"Fehler: {e}", file=sys.stderr)

def main():
    if not OPENAI_API_KEY: _die("Bitte OPENAI_API_KEY setzen.")
    ensure_collection()
    if len(sys.argv) >= 3 and sys.argv[1] == "ingest":
        topic = " ".join(sys.argv[2:])
        ingest_topic(OpenAI(api_key=OPENAI_API_KEY), topic, max_chunks=5)
    else:
        run_chat()

if __name__ == "__main__":
    main()