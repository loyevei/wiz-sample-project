import json
import os
import uuid
from itertools import product
from datetime import datetime

DATA_DIR = "/opt/app/data"

def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def _load_json(filename, default=None):
    _ensure_dir()
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default if default is not None else []

def _save_json(filename, data):
    _ensure_dir()
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_doe():
    factors_str = wiz.request.query("factors", "[]")
    try:
        factors = json.loads(factors_str)
    except:
        wiz.response.status(400, message="Invalid factors data")

    if not factors:
        wiz.response.status(400, message="No factors provided")

    # 각 인자별 레벨 값 생성
    factor_levels = {}
    for f in factors:
        name = f.get("name", "")
        min_val = float(f.get("min", 0))
        max_val = float(f.get("max", 1))
        levels = int(f.get("levels", 3))
        if levels < 2:
            levels = 2

        if levels == 1:
            factor_levels[name] = [min_val]
        else:
            step = (max_val - min_val) / (levels - 1)
            factor_levels[name] = [round(min_val + step * i, 4) for i in range(levels)]

    # 풀 팩토리얼 설계
    names = list(factor_levels.keys())
    level_values = [factor_levels[n] for n in names]
    combinations = list(product(*level_values))

    matrix = []
    for combo in combinations:
        row = {}
        for i, name in enumerate(names):
            row[name] = combo[i]
        matrix.append(row)

    wiz.response.status(200, {"matrix": matrix, "total": len(matrix)})

def list_notes():
    notes = _load_json("experiment_notes.json", [])
    notes.sort(key=lambda x: x.get("date", ""), reverse=True)
    wiz.response.status(200, notes)

def save_note():
    note_id = wiz.request.query("id", "")
    title = wiz.request.query("title", "")
    date = wiz.request.query("date", "")
    content = wiz.request.query("content", "")
    tags = wiz.request.query("tags", "")
    source_type = wiz.request.query("source_type", "manual")
    source_ref = wiz.request.query("source_ref", "")
    auto_generated = wiz.request.query("auto_generated", "false") == "true"

    if not title.strip():
        wiz.response.status(400, message="Title is required")

    notes = _load_json("experiment_notes.json", [])

    if note_id:
        for note in notes:
            if note["id"] == note_id:
                note["title"] = title
                note["date"] = date
                note["content"] = content
                note["tags"] = tags
                note["source_type"] = source_type
                note["source_ref"] = source_ref
                note["auto_generated"] = auto_generated
                note["updated_at"] = datetime.now().isoformat()
                break
    else:
        note = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "date": date,
            "content": content,
            "tags": tags,
            "source_type": source_type,
            "source_ref": source_ref,
            "auto_generated": auto_generated,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        notes.append(note)

    _save_json("experiment_notes.json", notes)
    wiz.response.status(200, True)

def delete_note():
    note_id = wiz.request.query("id", "")
    if not note_id:
        wiz.response.status(400, message="Note ID is required")

    notes = _load_json("experiment_notes.json", [])
    notes = [n for n in notes if n["id"] != note_id]
    _save_json("experiment_notes.json", notes)
    wiz.response.status(200, True)

def generate_note_template():
    title = wiz.request.query("title", "")
    context_raw = wiz.request.query("context", "{}")
    try:
        context = json.loads(context_raw)
    except Exception:
        context = {}

    factors = context.get("factors", [])
    doe_matrix = context.get("doeMatrix", [])
    recipes = context.get("recipes", [])
    selected_recipe = context.get("selectedRecipe", {})
    collection = context.get("collection", "")

    factor_names = [f.get("name", "") for f in factors if f.get("name")]
    recipe_name = selected_recipe.get("name") or (recipes[0].get("name") if recipes else "")
    recipe_summary = []
    if selected_recipe or recipes:
        recipe = selected_recipe if selected_recipe else recipes[0]
        recipe_summary = [
            f"가스: {recipe.get('gas', '-')}",
            f"압력: {recipe.get('pressure', '-')} mTorr",
            f"파워: {recipe.get('power', '-')} W",
            f"온도: {recipe.get('temperature', '-')} °C",
            f"시간: {recipe.get('time', '-')} s"
        ]

    note_title = title.strip() or recipe_name or "자동 생성 연구 노트"
    body = [
        f"# {note_title}",
        "",
        f"- 작성일: {datetime.now().strftime('%Y-%m-%d')}",
        f"- 컬렉션: {collection or '-'}",
        f"- DOE 조합 수: {len(doe_matrix)}",
        f"- 핵심 인자: {', '.join(factor_names) if factor_names else '-'}",
        "",
        "## 실험 배경",
        "- 본 노트는 현재 설정된 실험 인자 및 레시피를 기반으로 자동 생성되었습니다.",
        "- 변경된 조건과 결과를 하단 관찰 섹션에 이어서 기록하세요.",
        "",
        "## 레시피 요약",
    ]
    if recipe_summary:
        body.extend([f"- {item}" for item in recipe_summary])
    else:
        body.append("- 등록된 레시피 없음")
    body.extend([
        "",
        "## 관찰 결과",
        "- 초기 플라즈마 점화 상태:",
        "- 공정 중 스펙트럼/안정성 변화:",
        "- 결과물 특성(식각/증착/균일도 등):",
        "",
        "## 다음 액션",
        "- DOE 결과를 데이터셋 페이지에 구조화 저장",
        "- 재현성 확인을 위한 반복 실험 계획",
        "- 필요한 경우 연구 근거 추적과 프로젝트 보고서에 연결"
    ])

    tags = ["auto-note"]
    if factor_names:
        tags.extend(factor_names[:3])
    if recipe_name:
        tags.append(recipe_name)

    wiz.response.status(200, {
        "title": note_title,
        "date": datetime.now().strftime('%Y-%m-%d'),
        "content": "\n".join(body),
        "tags": ", ".join(tags)
    })

def list_recipes():
    recipes = _load_json("experiment_recipes.json", [])
    recipes.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    wiz.response.status(200, recipes)

def save_recipe():
    recipe_id = wiz.request.query("id", "")
    name = wiz.request.query("name", "")
    gas = wiz.request.query("gas", "Ar")
    pressure = wiz.request.query("pressure", "100")
    power = wiz.request.query("power", "300")
    temperature = wiz.request.query("temperature", "25")
    time_val = wiz.request.query("time", "60")
    description = wiz.request.query("description", "")

    if not name.strip():
        wiz.response.status(400, message="Recipe name is required")

    recipes = _load_json("experiment_recipes.json", [])

    if recipe_id:
        for recipe in recipes:
            if recipe["id"] == recipe_id:
                recipe["name"] = name
                recipe["gas"] = gas
                recipe["pressure"] = pressure
                recipe["power"] = power
                recipe["temperature"] = temperature
                recipe["time"] = time_val
                recipe["description"] = description
                recipe["updated_at"] = datetime.now().isoformat()
                break
    else:
        recipe = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "gas": gas,
            "pressure": pressure,
            "power": power,
            "temperature": temperature,
            "time": time_val,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        recipes.append(recipe)

    _save_json("experiment_recipes.json", recipes)
    wiz.response.status(200, True)

def delete_recipe():
    recipe_id = wiz.request.query("id", "")
    if not recipe_id:
        wiz.response.status(400, message="Recipe ID is required")

    recipes = _load_json("experiment_recipes.json", [])
    recipes = [r for r in recipes if r["id"] != recipe_id]
    _save_json("experiment_recipes.json", recipes)
    wiz.response.status(200, True)
