import json
import os
import uuid
from datetime import datetime

DATA_DIR = "/opt/app/data"
DATASET_FILE = os.path.join(DATA_DIR, "experiment_dataset_records.json")
PROJECTS_FILE = os.path.join(DATA_DIR, "collab_projects.json")
COLLECTION_META_PATH = os.path.join(DATA_DIR, "collection_meta.json")

os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(path, default=None):
    if default is None:
        default = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    if isinstance(default, dict):
        return dict(default)
    return list(default)


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_records():
    rows = _load_json(DATASET_FILE, [])
    rows.sort(key=lambda item: item.get("updated_at", item.get("created_at", "")), reverse=True)
    wiz.response.status(200, rows)


def save_record():
    record_id = wiz.request.query("id", "")
    title = wiz.request.query("title", "")
    project_id = wiz.request.query("project_id", "")
    collection = wiz.request.query("collection", "")
    source_type = wiz.request.query("source_type", "manual")
    notes = wiz.request.query("notes", "")
    tags = wiz.request.query("tags", "")
    conditions_raw = wiz.request.query("conditions", "[]")
    outcomes_raw = wiz.request.query("outcomes", "[]")
    evidence_raw = wiz.request.query("evidence_refs", "[]")

    if not title.strip():
        wiz.response.status(400, message="데이터셋 제목이 필요합니다.")

    try:
        conditions = json.loads(conditions_raw)
    except Exception:
        conditions = []
    try:
        outcomes = json.loads(outcomes_raw)
    except Exception:
        outcomes = []
    try:
        evidence_refs = json.loads(evidence_raw)
    except Exception:
        evidence_refs = []

    rows = _load_json(DATASET_FILE, [])
    now = datetime.now().isoformat()

    payload = {
        "title": title,
        "project_id": project_id,
        "collection": collection,
        "source_type": source_type,
        "notes": notes,
        "tags": tags,
        "conditions": conditions,
        "outcomes": outcomes,
        "evidence_refs": evidence_refs,
        "updated_at": now
    }

    if record_id:
        for row in rows:
            if row.get("id") == record_id:
                row.update(payload)
                break
    else:
        payload["id"] = str(uuid.uuid4())[:8]
        payload["created_at"] = now
        rows.insert(0, payload)

    _save_json(DATASET_FILE, rows)
    wiz.response.status(200, True)


def delete_record():
    record_id = wiz.request.query("id", "")
    if not record_id:
        wiz.response.status(400, message="ID가 필요합니다.")
    rows = _load_json(DATASET_FILE, [])
    rows = [row for row in rows if row.get("id") != record_id]
    _save_json(DATASET_FILE, rows)
    wiz.response.status(200, True)


def list_projects():
    wiz.response.status(200, _load_json(PROJECTS_FILE, []))


def list_collections():
    meta = _load_json(COLLECTION_META_PATH, {})
    rows = []
    for name, info in meta.items():
        rows.append({
            "name": name,
            "short_name": info.get("short_name", "Unknown"),
            "dim": info.get("dim", 0)
        })
    rows.sort(key=lambda item: item.get("name", ""))
    wiz.response.status(200, rows)
