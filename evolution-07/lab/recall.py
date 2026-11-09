import argparse
import json
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent
STORE = BASE / "memory.jsonl"
LEDGER = BASE / "memory-ledger.jsonl"
LEDGER_SCHEMA = "e7-memory-v2"


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record) + chr(10))


def log_event(ledger_path, event, **details):
    ledger_path = Path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": event,
        "schema": LEDGER_SCHEMA,
        "date": date.today().isoformat(),
        **details
    }
    with ledger_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + chr(10))


def next_id(store_path=STORE, ledger_path=LEDGER):
    ids = set()

    for record in read_jsonl(store_path):
        ids.add(int(record["id"].split("-")[1]))

    for event in read_jsonl(ledger_path):
        memory_id = event.get("id", "")
        if re.fullmatch(r"m-\d+", memory_id):
            ids.add(int(memory_id.split("-")[1]))

    return f"m-{max(ids, default=0) + 1:04d}"


def remember(text, source, until, kind="episodic",
             supersedes=None, store_path=STORE,
             ledger_path=LEDGER):
    records = read_jsonl(store_path)

    if supersedes:
        if not any(r["id"] == supersedes for r in records):
            raise ValueError("Superseded memory ID not found")

    memory_id = next_id(store_path, ledger_path)

    record = {
        "id": memory_id,
        "kind": kind,
        "source": source,
        "written": date.today().isoformat(),
        "written_by": "user",
        "retain_until": until,
        "supersedes": supersedes,
        "text": text
    }

    records.append(record)
    write_jsonl(store_path, records)
    log_event(
        ledger_path,
        "remember",
        id=memory_id,
        source=source,
        supersedes=supersedes
    )
    print(f"Saved memory: {memory_id}")


def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def query(question, top_k=3, threshold=0.05,
          today=None, store_path=STORE,
          ledger_path=LEDGER):
    today = today or date.today().isoformat()
    records = read_jsonl(store_path)

    superseded_ids = {
        r["supersedes"]
        for r in records
        if r.get("supersedes")
    }

    active = [
        r for r in records
        if r["retain_until"] >= today
        and r["id"] not in superseded_ids
    ]

    query_tokens = Counter(tokenize(question))
    documents = [Counter(tokenize(r["text"])) for r in active]

    if not query_tokens or not documents:
        log_event(
            ledger_path,
            "recall",
            question=question,
            results=[],
            top_id=None,
            top_source=None,
            top_score=None
        )
        return {
            "question": question,
            "results": [],
            "top_id": None,
            "top_source": None,
            "top_score": None,
        }

    # Local TF-IDF cosine similarity.
    n = len(documents)
    df = Counter()

    for doc in documents:
        df.update(doc.keys())

    def weight(term):
        return math.log((n + 1) / (df[term] + 1)) + 1

    def vector(counts):
        return {
            term: count * weight(term)
            for term, count in counts.items()
        }

    def cosine(a, b):
        numerator = sum(
            a.get(term, 0) * b.get(term, 0)
            for term in a
        )
        norm_a = math.sqrt(sum(v * v for v in a.values()))
        norm_b = math.sqrt(sum(v * v for v in b.values()))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return numerator / (norm_a * norm_b)

    q_vector = vector(query_tokens)
    scored = []

    for record, doc in zip(active, documents):
        score = cosine(q_vector, vector(doc))
        if score >= threshold and score > 0:
            scored.append((score, record))

    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    results = scored[:top_k]

    event_results = [
        {
            "id": record["id"],
            "source": record["source"],
            "score": round(score, 4)
        }
        for score, record in results
    ]
    top = event_results[0] if event_results else {
        "id": None,
        "source": None,
        "score": None
    }

    log_event(
        ledger_path,
        "recall",
        question=question,
        results=event_results,
        top_id=top["id"],
        top_source=top["source"],
        top_score=top["score"]
    )

    return {
        "question": question,
        "results": [
            {
                "id": record["id"],
                "source": record["source"],
                "date": record["written"],
                "score": round(score, 4),
                "text": record["text"],
            }
            for score, record in results
        ],
        "top_id": top["id"],
        "top_source": top["source"],
        "top_score": top["score"],
    }


def recall(question, top_k=3, threshold=0.05,
           today=None, store_path=STORE,
           ledger_path=LEDGER):
    data = query(
        question,
        top_k,
        threshold,
        today,
        store_path,
        ledger_path,
    )

    if not data["results"]:
        print("Not in memory.")
        return

    for item in data["results"]:
        print(f"Memory ID: {item['id']}")
        print(f"Source: {item['source']}")
        print(f"Date: {item['date']}")
        print(f"Score: {item['score']:.4f}")
        print(f"Memory: {item['text']}")
        print()


def evict(today, store_path=STORE, ledger_path=LEDGER):
    records = read_jsonl(store_path)

    expired = [
        r for r in records
        if r["retain_until"] < today
    ]
    active = [
        r for r in records
        if r["retain_until"] >= today
    ]

    write_jsonl(store_path, active)

    for record in expired:
        log_event(
            ledger_path,
            "evict",
            id=record["id"],
            reason="retention_expired",
            effective_date=today
        )

    print(f"Evicted {len(expired)} memories.")


def forget(memory_id, reason, store_path=STORE,
           ledger_path=LEDGER):
    records = read_jsonl(store_path)
    remaining = [
        r for r in records
        if r["id"] != memory_id
    ]

    if len(remaining) == len(records):
        print("Memory not found.")
        return

    write_jsonl(store_path, remaining)
    log_event(
        ledger_path,
        "forget",
        id=memory_id,
        reason=reason
    )
    print(f"Forgot memory: {memory_id}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["remember", "recall", "evict", "forget"]
    )
    parser.add_argument("--text")
    parser.add_argument("--source")
    parser.add_argument("--until")
    parser.add_argument("--kind", default="episodic")
    parser.add_argument("--supersedes")
    parser.add_argument("--question")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--today")
    parser.add_argument("--id")
    parser.add_argument("--reason")
    parser.add_argument("--store")
    parser.add_argument("--ledger")

    args = parser.parse_args()

    store_path = Path(args.store) if args.store else STORE
    ledger_path = Path(args.ledger) if args.ledger else LEDGER

    if args.command == "remember":
        if not all([args.text, args.source, args.until]):
            parser.error(
                "remember requires --text, --source, --until"
            )
        remember(
            args.text, args.source, args.until,
            args.kind, args.supersedes,
            store_path, ledger_path
        )

    elif args.command == "recall":
        if not args.question:
            parser.error("recall requires --question")
        if args.top_k < 1 or not 0 <= args.threshold <= 1:
            parser.error("Invalid top-k or threshold")
        recall(
            args.question, args.top_k,
            args.threshold, args.today,
            store_path, ledger_path
        )

    elif args.command == "evict":
        evict(
            args.today or date.today().isoformat(),
            store_path, ledger_path
        )

    elif args.command == "forget":
        if not args.id or not args.reason:
            parser.error("forget requires --id and --reason")
        forget(
            args.id, args.reason,
            store_path, ledger_path
        )


if __name__ == "__main__":
    main()
