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
                note["updated_at"] = datetime.now().isoformat()
                break
    else:
        note = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "date": date,
            "content": content,
            "tags": tags,
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
