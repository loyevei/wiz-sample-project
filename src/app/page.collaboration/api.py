import json
import os
import uuid
from datetime import datetime

DATA_DIR = "/opt/app/data"
PROJECTS_FILE = os.path.join(DATA_DIR, "collab_projects.json")
DISCUSSIONS_FILE = os.path.join(DATA_DIR, "collab_discussions.json")
ACTIVITY_FILE = os.path.join(DATA_DIR, "collab_activity.json")
REPORTS_FILE = os.path.join(DATA_DIR, "project_reports.json")
NOTES_FILE = os.path.join(DATA_DIR, "experiment_notes.json")
DATASET_FILE = os.path.join(DATA_DIR, "experiment_dataset_records.json")
TRACE_FILE = os.path.join(DATA_DIR, "research_evidence_traces.json")
COLLECTION_META_PATH = os.path.join(DATA_DIR, "collection_meta.json")

os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(filepath):
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _add_activity(act_type, message, detail=""):
    activities = _load_json(ACTIVITY_FILE)
    activities.insert(0, {
        "id": str(uuid.uuid4())[:8],
        "type": act_type,
        "message": message,
        "detail": detail,
        "created": datetime.now().isoformat()
    })
    # Keep only latest 100 entries
    activities = activities[:100]
    _save_json(ACTIVITY_FILE, activities)


# ===== Projects =====

def list_projects():
    projects = _load_json(PROJECTS_FILE)
    wiz.response.status(200, projects)


def save_project():
    project_id = wiz.request.query("id", "")
    name = wiz.request.query("name", "")
    description = wiz.request.query("description", "")
    members_raw = wiz.request.query("members", "")
    status = wiz.request.query("status", "active")
    objective = wiz.request.query("objective", "")
    tags = wiz.request.query("tags", "")
    collection = wiz.request.query("collection", "")

    if not name.strip():
        wiz.response.status(400, message="프로젝트 이름을 입력해주세요.")

    # Parse members
    if isinstance(members_raw, str):
        members = [m.strip() for m in members_raw.split(",") if m.strip()]
    elif isinstance(members_raw, list):
        members = members_raw
    else:
        members = []

    projects = _load_json(PROJECTS_FILE)
    now = datetime.now().isoformat()

    if project_id:
        # Update existing
        for p in projects:
            if p["id"] == project_id:
                p["name"] = name
                p["description"] = description
                p["members"] = members
                p["status"] = status
                p["objective"] = objective
                p["tags"] = tags
                p["collection"] = collection
                p["updated"] = now
                break
        _save_json(PROJECTS_FILE, projects)
        _add_activity("project_updated", f"프로젝트 '{name}' 수정됨")
    else:
        # Create new
        new_project = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "description": description,
            "members": members,
            "status": status,
            "objective": objective,
            "tags": tags,
            "collection": collection,
            "created": now,
            "updated": now
        }
        projects.insert(0, new_project)
        _save_json(PROJECTS_FILE, projects)
        _add_activity("project_created", f"새 프로젝트 '{name}' 생성됨", f"멤버: {', '.join(members) if members else '없음'}")

    wiz.response.status(200)


def delete_project():
    project_id = wiz.request.query("id", "")
    if not project_id:
        wiz.response.status(400, message="ID가 필요합니다.")

    projects = _load_json(PROJECTS_FILE)
    name = ""
    for p in projects:
        if p["id"] == project_id:
            name = p.get("name", "")
            break

    projects = [p for p in projects if p["id"] != project_id]
    _save_json(PROJECTS_FILE, projects)

    if name:
        _add_activity("project_deleted", f"프로젝트 '{name}' 삭제됨")

    wiz.response.status(200)


# ===== Discussions =====

def list_discussions():
    discussions = _load_json(DISCUSSIONS_FILE)
    wiz.response.status(200, discussions)


def save_discussion():
    disc_id = wiz.request.query("id", "")
    title = wiz.request.query("title", "")
    content = wiz.request.query("content", "")
    reply = wiz.request.query("reply", "")

    discussions = _load_json(DISCUSSIONS_FILE)
    now = datetime.now().isoformat()

    if disc_id and reply:
        # Add reply to existing discussion
        for d in discussions:
            if d["id"] == disc_id:
                if "replies" not in d:
                    d["replies"] = []
                d["replies"].append({
                    "id": str(uuid.uuid4())[:8],
                    "content": reply,
                    "author": "사용자",
                    "created": now
                })
                d["updated"] = now
                _save_json(DISCUSSIONS_FILE, discussions)
                _add_activity("reply_added", f"토론 '{d['title']}'에 답글 추가됨")
                break
        wiz.response.status(200)
        return

    if not title.strip():
        wiz.response.status(400, message="제목을 입력해주세요.")

    if disc_id:
        # Update existing discussion
        for d in discussions:
            if d["id"] == disc_id:
                d["title"] = title
                d["content"] = content
                d["updated"] = now
                break
        _save_json(DISCUSSIONS_FILE, discussions)
        _add_activity("discussion_created", f"토론 '{title}' 수정됨")
    else:
        # Create new discussion
        new_disc = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "content": content,
            "author": "사용자",
            "replies": [],
            "created": now,
            "updated": now
        }
        discussions.insert(0, new_disc)
        _save_json(DISCUSSIONS_FILE, discussions)
        _add_activity("discussion_created", f"새 토론 '{title}' 작성됨")

    wiz.response.status(200)


def delete_discussion():
    disc_id = wiz.request.query("id", "")
    if not disc_id:
        wiz.response.status(400, message="ID가 필요합니다.")

    discussions = _load_json(DISCUSSIONS_FILE)
    title = ""
    for d in discussions:
        if d["id"] == disc_id:
            title = d.get("title", "")
            break

    discussions = [d for d in discussions if d["id"] != disc_id]
    _save_json(DISCUSSIONS_FILE, discussions)

    if title:
        _add_activity("discussion_created", f"토론 '{title}' 삭제됨")

    wiz.response.status(200)


# ===== Activity =====

def list_activity():
    activities = _load_json(ACTIVITY_FILE)
    # Return latest 50
    wiz.response.status(200, activities[:50])


def list_collections():
    meta = _load_json(COLLECTION_META_PATH)
    rows = []
    if isinstance(meta, dict):
        for name, info in meta.items():
            rows.append({
                "name": name,
                "short_name": info.get("short_name", "Unknown"),
                "dim": info.get("dim", 0)
            })
    rows.sort(key=lambda item: item.get("name", ""))
    wiz.response.status(200, rows)


def list_reports():
    project_id = wiz.request.query("project_id", "")
    reports = _load_json(REPORTS_FILE)
    if project_id:
        reports = [report for report in reports if report.get("project_id") == project_id]
    wiz.response.status(200, reports)


def generate_project_report():
    project_id = wiz.request.query("project_id", "")
    if not project_id:
        wiz.response.status(400, message="프로젝트 ID가 필요합니다.")

    projects = _load_json(PROJECTS_FILE)
    project = None
    for item in projects:
        if item.get("id") == project_id:
            project = item
            break

    if project is None:
        wiz.response.status(404, message="프로젝트를 찾을 수 없습니다.")

    notes = [note for note in _load_json(NOTES_FILE) if project.get("name", "") in (note.get("title", "") + note.get("content", "")) or project_id == note.get("source_ref", "")]
    datasets = [row for row in _load_json(DATASET_FILE) if row.get("project_id") == project_id]
    traces = [trace for trace in _load_json(TRACE_FILE) if trace.get("meta", {}).get("project_id") == project_id or trace.get("collection") == project.get("collection", "")]

    markdown_lines = [
        f"# 프로젝트 보고서 - {project.get('name', '')}",
        "",
        f"- 상태: {project.get('status', 'active')}",
        f"- 연결 컬렉션: {project.get('collection', '-')}",
        f"- 멤버: {', '.join(project.get('members', [])) if project.get('members') else '-'}",
        "",
        "## 목적",
        project.get('objective', '') or project.get('description', '') or '등록된 목표 없음',
        "",
        f"## 데이터셋 요약 ({len(datasets)}건)",
    ]
    if datasets:
        for row in datasets[:5]:
            markdown_lines.append(f"- {row.get('title', '')}: 조건 {len(row.get('conditions', []))}개 / 결과 {len(row.get('outcomes', []))}개")
    else:
        markdown_lines.append("- 연결된 데이터셋 없음")

    markdown_lines.extend([
        "",
        f"## 연구 근거 추적 ({len(traces)}건)",
    ])
    if traces:
        for trace in traces[:5]:
            markdown_lines.append(f"- {trace.get('title', '')}: 근거 {len(trace.get('evidence', []))}건 / 조건 {', '.join(trace.get('extracted_conditions', [])[:4]) or '-'}")
    else:
        markdown_lines.append("- 저장된 근거 추적 없음")

    markdown_lines.extend([
        "",
        f"## 연구 노트 ({len(notes)}건)",
    ])
    if notes:
        for note in notes[:5]:
            markdown_lines.append(f"- {note.get('title', '')} ({note.get('date', '')})")
    else:
        markdown_lines.append("- 관련 노트 없음")

    slide_outline = [
        {"title": "프로젝트 개요", "bullets": [project.get('name', ''), project.get('objective', '') or project.get('description', ''), f"컬렉션: {project.get('collection', '-')}"]},
        {"title": "실험 데이터셋", "bullets": [f"총 {len(datasets)}건", *[row.get('title', '') for row in datasets[:3]]] if datasets else ["등록 데이터 없음"]},
        {"title": "근거 문헌", "bullets": [trace.get('title', '') for trace in traces[:4]] if traces else ["근거 추적 없음"]},
        {"title": "다음 액션", "bullets": ["핵심 조건 반복 검증", "프로젝트 컬렉션 업데이트", "보고서 기반 발표자료 보강"]}
    ]

    report = {
        "id": str(uuid.uuid4())[:8],
        "project_id": project_id,
        "project_name": project.get('name', ''),
        "markdown": "\n".join(markdown_lines),
        "slides": slide_outline,
        "created": datetime.now().isoformat()
    }

    reports = _load_json(REPORTS_FILE)
    reports.insert(0, report)
    _save_json(REPORTS_FILE, reports[:100])
    _add_activity("report_generated", f"프로젝트 '{project.get('name', '')}' 보고서 생성됨", f"데이터셋 {len(datasets)}건 / 근거 {len(traces)}건")
    wiz.response.status(200, report)


def add_activity():
    act_type = wiz.request.query("type", "info")
    message = wiz.request.query("message", "")
    detail = wiz.request.query("detail", "")

    if not message.strip():
        wiz.response.status(400, message="메시지를 입력해주세요.")

    _add_activity(act_type, message, detail)
    wiz.response.status(200)
