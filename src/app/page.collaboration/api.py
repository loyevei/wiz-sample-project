import json
import os
import uuid
from datetime import datetime

DATA_DIR = "/opt/app/data"
PROJECTS_FILE = os.path.join(DATA_DIR, "collab_projects.json")
DISCUSSIONS_FILE = os.path.join(DATA_DIR, "collab_discussions.json")
ACTIVITY_FILE = os.path.join(DATA_DIR, "collab_activity.json")

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


def add_activity():
    act_type = wiz.request.query("type", "info")
    message = wiz.request.query("message", "")
    detail = wiz.request.query("detail", "")

    if not message.strip():
        wiz.response.status(400, message="메시지를 입력해주세요.")

    _add_activity(act_type, message, detail)
    wiz.response.status(200)
