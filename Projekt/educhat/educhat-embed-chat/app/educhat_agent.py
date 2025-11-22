import os, sys, json, re, time
from textwrap import fill
from datetime import datetime, timezone
from slugify import slugify
import requests
from openai import OpenAI

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.environ.get("QDRANT_COLLECTION", "weiterbildung")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
TOP_K = int(os.environ.get("TOP_K", "5"))
MIN_SCORE = float(os.environ.get("MIN_SCORE", "0.65"))
WRAP_COLS = int(os.environ.get("WRAP_COLS", "100"))

BLOCK_WORDS = {"password", "admin access", "bypass", "prompt injection"}

EDUCHAT_SYSTEM_PROMPT = """Du bist ein präziser Bildungsassistent, der NUR auf Basis der bereitgestellten Dokumente antwortet.

WICHTIGE REGELN:
1. Antworte NUR mit Informationen aus den bereitgestellten Quellen
2. Wenn die Quellen die Frage nicht beantworten, sage "Das kann ich aus den vorhandenen Informationen nicht beantworten."
3. Zitiere konkret aus den Quellen - keine eigenen Ergänzungen
4. Keine Spekulationen, keine Annahmen, keine externen Kenntnisse
5. Bei Unklarheiten: Frage nach Präzisierung oder verweise auf vorhandene Themen

Antwortformat:
- Kurze, präzise Antwort basierend auf den Quellen
- Klare Quellenangabe [1], [2], etc.
- Keine Einleitung wie "Laut den Dokumenten..." - direkt zur Sache"""


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
                     headers={"Content-Type": "application/json"},
                     data=json.dumps(body), timeout=30)
    if r.status_code >= 400:
        _die(f"Collection-Create fehlgeschlagen: {r.status_code} {r.text}")


def embed_texts(client: OpenAI, texts):
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def upsert_points(points):
    payload = {"points": points}
    r = requests.put(f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true",
                     headers={"Content-Type": "application/json"},
                     data=json.dumps(payload), timeout=120)
    if r.status_code >= 400:
        _die(f"Upsert fehlgeschlagen: {r.status_code} {r.text}")


def ingest_topic(client: OpenAI, topic: str, max_chunks=5):
    # einfache Generierung kurzer Chunks über Chat Completion
    sysmsg = "Erzeuge prägnante Textabschnitte (2–4 Sätze) zu einem Thema, JSON-Array mit title, content, tags."
    usermsg = f"Thema: {topic}\nErzeuge {max_chunks} Chunks als JSON-Array."
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": sysmsg},
                  {"role": "user", "content": usermsg}],
        temperature=0.2,
        max_tokens=800
    )
    txt = resp.choices[0].message.content.strip()
    start, end = txt.find("["), txt.rfind("]")
    if start == -1 or end == -1:
        _die("Antwort enthielt kein JSON-Array.")
    chunks = json.loads(txt[start:end + 1])[:max_chunks]
    vectors = embed_texts(client, [c.get("content", "") for c in chunks])

    doc_id = f"doc-{slugify(topic) or 'topic'}"
    created_at = _now()
    points = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors), start=1):
        points.append({
            "id": int(time.time() * 1000) + i,
            "vector": vec,
            "payload": {
                "title": chunk.get("title", f"Chunk {i}"),
                "content": chunk.get("content", ""),
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
                      headers={"Content-Type": "application/json"},
                      data=json.dumps(body), timeout=60)
    if r.status_code >= 400:
        _die(f"Search fehlgeschlagen: {r.status_code} {r.text}")
    return r.json().get("result", [])


def is_answer_hallucinating(answer, context, question):
    """Einfache Validierung ob die Antwort halluziniert"""
    answer_lower = answer.lower()
    question_lower = question.lower()
    context_lower = context.lower()

    # Wenn Antwort Behauptungen macht aber keine Quellen zitiert
    if "[" not in answer and "quelle" not in answer_lower:
        # Für komplexe Antworten ohne Zitate: Risiko
        if len(answer) > 100 and not any(
                word in answer_lower for word in ["weiß nicht", "nicht beantworten", "keine information"]):
            return True

    # Wenn spezifische Frage aber generische Antwort
    specific_question = any(word in question_lower for word in ["wie", "was", "welche", "warum"])
    generic_answer = any(
        phrase in answer_lower for phrase in ["kontaktiere", "website", "mehr informationen", "besuche uns"])

    if specific_question and generic_answer:
        return True

    return False


def generate_fallback_answer(hits):
    """Generiere eine konservative Fallback-Antwort"""
    if not hits:
        return "Ich habe dazu keine Informationen in den Bildungsdaten gefunden."

    sources_info = []
    for i, hit in enumerate(hits[:3], 1):
        payload = hit.get("payload", {}) or {}
        title = payload.get("title", "Ohne Titel")
        score = hit.get("score", 0.0)

        sources_info.append(f"[{i}] {title} (Relevanz: {score:.2f})")

    return f"Ich habe {len(hits)} relevante Dokumente gefunden, kann aber keine konkrete Antwort sicher ableiten:\n" + "\n".join(
        sources_info)


def answer_from_hits_improved(hits, question):
    """Verbesserte Antwort-Generierung mit strengerer Quellenbindung"""
    if not hits:
        return "Ich habe dazu keine Informationen in den vorhandenen Bildungsdaten gefunden."

    # Filtere nur hochqualitative Treffer
    high_quality_hits = [h for h in hits if h.get("score", 0.0) >= MIN_SCORE]

    if not high_quality_hits:
        return "Die gefundenen Informationen sind nicht ausreichend relevant, um Ihre Frage sicher zu beantworten."

    # Bereite Quellen für den Prompt vor
    context_parts = []
    for i, hit in enumerate(high_quality_hits[:3], 1):
        payload = hit.get("payload", {}) or {}
        content = payload.get("content", "").strip()
        title = payload.get("title", "").strip()

        if content:
            context_parts.append(f"[Quelle {i} - {title}]: {content}")

    if not context_parts:
        return "In den relevanten Dokumenten wurden keine konkreten Inhalte zu Ihrer Frage gefunden."

    context = "\n\n".join(context_parts)

    # Prompt mit strengen Anweisungen
    prompt = f"""FRAGE: {question}

VERFÜGBARE QUELLEN:
{context}

ANWEISUNGEN:
- Beantworte die Frage NUR mit den oben genannten Quellen
- Wenn die Quellen die Frage nicht vollständig beantworten, sage das explizit
- Keine Ergänzungen aus eigenem Wissen
- Zitiere die Quellen mit [1], [2] etc.
- Kurze, präzise Antwort"""

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": EDUCHAT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Sehr niedrig für Konsistenz
            max_tokens=500
        )

        answer = response.choices[0].message.content.strip()

        # Sicherheits-Check: Antwort validieren
        if is_answer_hallucinating(answer, context, question):
            return "Ich kann diese Frage auf Basis der verfügbaren Informationen nicht sicher beantworten."

        return answer

    except Exception as e:
        print(f"OpenAI Fehler: {e}", file=sys.stderr)
        # Fallback: Einfache Quellen-Auflistung
        return generate_fallback_answer(high_quality_hits)


def answer_from_hits(hits):
    """Einfache Antwort für Kompatibilität"""
    if not hits:
        return "Ich weiß es nicht auf Basis der vorhandenen Daten."
    if hits[0].get("score", 0.0) < MIN_SCORE:
        return "Ich weiß es nicht auf Basis der vorhandenen Daten."

    lines = []
    for i, h in enumerate(hits, start=1):
        p = h.get("payload", {}) or {}
        lines.append(f"[{i}] {p.get('title', '')}")
        if p.get("content"):
            lines.append(fill(p["content"], width=WRAP_COLS))
        lines.append(f"Quelle: {p.get('source', '-')} | doc_id={p.get('doc_id', '-')} | chunk={p.get('chunk_id', '-')}")
        lines.append("")
    return "\n".join(lines).strip()


def run_chat_improved():
    """Verbesserte Chat-Funktion mit konservativeren Antworten"""
    client = OpenAI(api_key=OPENAI_API_KEY)

    print("=== EDUCHAT - Bildungsassistent ===")
    print("Ich antworte nur auf Basis verfügbarer Bildungsdaten.")
    print("Eingabe ':exit' zum Beenden\n")

    conversation_history = []

    while True:
        try:
            question = input("Frage: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAuf Wiedersehen!");
            break

        if question.lower() in {":exit", "exit", ":q", "quit"}:
            print("Auf Wiedersehen!");
            break

        # Sicherheitscheck
        if any(w in question.lower() for w in BLOCK_WORDS):
            print("Sicherheitshinweis: Diese Anfrage kann nicht bearbeitet werden.");
            continue

        try:
            # Embedding für Suche
            vec = embed_texts(client, [question])[0]
            hits = search(vec)

            # Verbesserte Antwort-Generierung
            answer = answer_from_hits_improved(hits, question)

            print(f"\nAntwort: {answer}")
            print("-" * 80)

            # Konversationshistorie für Kontext (optional)
            conversation_history.append({"question": question, "answer": answer})

        except Exception as e:
            print(f"Fehler: {e}")
            print("Bitte versuchen Sie es erneut oder formulieren Sie Ihre Frage anders.")


def run_chat():
    """Original Chat-Funktion für Kompatibilität"""
    if any(b in os.environ.get("BLOCK_OVERRIDE", "").lower() for b in ["true", "1", "yes"]):
        blocked = set()
    else:
        blocked = BLOCK_WORDS

    client = OpenAI(api_key=OPENAI_API_KEY)
    print("SentinelAI – Console-Chat (nur Inhalte aus Qdrant). ':exit' zum Beenden.")
    while True:
        try:
            q = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTschüss.");
            break
        if q.lower() in {":exit", "exit", ":q", "quit"}:
            print("Tschüss.");
            break
        if any(w in q.lower() for w in blocked):
            print("Sicherheitsmeldung: Anfrage blockiert.");
            continue
        try:
            vec = embed_texts(client, [q])[0]
            hits = search(vec)
            print(answer_from_hits(hits))
            print("-" * 60)
        except Exception as e:
            print(f"Fehler: {e}", file=sys.stderr)


def main():
    if not OPENAI_API_KEY:
        _die("Bitte OPENAI_API_KEY setzen.")
    ensure_collection()
    if len(sys.argv) >= 3 and sys.argv[1] == "ingest":
        topic = " ".join(sys.argv[2:])
        ingest_topic(OpenAI(api_key=OPENAI_API_KEY), topic, max_chunks=5)
    elif len(sys.argv) >= 2 and sys.argv[1] == "improved":
        run_chat_improved()
    else:
        run_chat()


if __name__ == "__main__":
    main()