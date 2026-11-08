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


def read_jsonl(path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path, records):
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record) + chr(10))


def log_event(event, **details):
    record = {
        "event": event,
        "date": date.today().isoformat(),
        **details
    }
    with LEDGER.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + chr(10))


def next_id():
    ids = set()

    for record in read_jsonl(STORE):
        ids.add(int(record["id"].split("-")[1]))

    for event in read_jsonl(LEDGER):
        memory_id = event.get("id", "")
        if re.fullmatch(r"m-\d+", memory_id):
            ids.add(int(memory_id.split("-")[1]))

    return f"m-{max(ids, default=0) + 1:04d}"


def remember(text, source, until, kind="episodic",
             supersedes=None):
    records = read_jsonl(STORE)

    if supersedes:
        if not any(r["id"] == supersedes for r in records):
            raise ValueError("Superseded memory ID not found")

    memory_id = next_id()

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
    write_jsonl(STORE, records)
    log_event(
        "remember",
        id=memory_id,
        source=source,
        supersedes=supersedes
    )
    print(f"Saved memory: {memory_id}")


def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def recall(question, top_k=3, threshold=0.05,
           today=None):
    today = today or date.today().isoformat()
    records = read_jsonl(STORE)

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

    query = Counter(tokenize(question))
    documents = [Counter(tokenize(r["text"])) for r in active]

    if not query or not documents:
        log_event("recall", question=question, results=[])
        print("Not in memory.")
        return

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

    q_vector = vector(query)
    scored = []

    for record, doc in zip(active, documents):
        score = cosine(q_vector, vector(doc))
        if score >= threshold and score > 0:
            scored.append((score, record))

    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    results = scored[:top_k]

    log_event(
        "recall",
        question=question,
        results=[
            {"id": r["id"], "score": round(score, 4)}
            for score, r in results
        ]
    )

    if not results:
        print("Not in memory.")
        return

    for score, record in results:
        print(f"Memory ID: {record['id']}")
        print(f"Source: {record['source']}")
        print(f"Date: {record['written']}")
        print(f"Score: {score:.4f}")
        print(f"Memory: {record['text']}")
        print()


def evict(today):
    records = read_jsonl(STORE)

    expired = [
        r for r in records
        if r["retain_until"] < today
    ]
    active = [
        r for r in records
        if r["retain_until"] >= today
    ]

    write_jsonl(STORE, active)

    for record in expired:
        log_event(
            "evict",
            id=record["id"],
            reason="retention_expired",
            effective_date=today
        )

    print(f"Evicted {len(expired)} memories.")


def forget(memory_id, reason):
    records = read_jsonl(STORE)
    remaining = [
        r for r in records
        if r["id"] != memory_id
    ]

    if len(remaining) == len(records):
        print("Memory not found.")
        return

    write_jsonl(STORE, remaining)
    log_event(
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

    args = parser.parse_args()

    if args.command == "remember":
        if not all([args.text, args.source, args.until]):
            parser.error(
                "remember requires --text, --source, --until"
            )
        remember(
            args.text, args.source, args.until,
            args.kind, args.supersedes
        )

    elif args.command == "recall":
        if not args.question:
            parser.error("recall requires --question")
        if args.top_k < 1 or not 0 <= args.threshold <= 1:
            parser.error("Invalid top-k or threshold")
        recall(
            args.question, args.top_k,
            args.threshold, args.today
        )

    elif args.command == "evict":
        evict(args.today or date.today().isoformat())

    elif args.command == "forget":
        if not args.id or not args.reason:
            parser.error("forget requires --id and --reason")
        forget(args.id, args.reason)


if __name__ == "__main__":
    main()
