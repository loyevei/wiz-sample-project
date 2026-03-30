import os
import sys
import json
import traceback
import numpy as np
import re
import uuid
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime

from sentence_transformers import SentenceTransformer
from pymilvus import MilvusClient
import season.lib.exception

# ==============================================================================
# 설정
# ==============================================================================
MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
COLLECTION_META_PATH = "/opt/app/data/collection_meta.json"
DEFAULT_COLLECTION = "plasma_papers"
DATA_DIR = "/opt/app/data"
EVIDENCE_TRACE_PATH = os.path.join(DATA_DIR, "research_evidence_traces.json")
PDF_DIR = os.path.join(DATA_DIR, "pdfs")
PROJECTS_FILE = os.path.join(DATA_DIR, "collab_projects.json")

MODEL_REGISTRY = wiz.model("modelregistry").compact()
DEFAULT_MODEL = wiz.model("modelregistry").default_model()

# 플라즈마 도메인 용어 사전
PLASMA_TERMS = [
    "플라즈마", "plasma", "에칭", "etching", "증착", "deposition", "CVD", "PVD",
    "스퍼터링", "sputtering", "이온", "ion", "RF", "DC", "전자", "electron",
    "가스", "gas", "압력", "pressure", "온도", "temperature", "전력", "power",
    "기판", "substrate", "박막", "thin film", "반응", "reaction", "챔버", "chamber",
    "공정", "process", "반도체", "semiconductor", "실리콘", "silicon",
    "산화", "oxidation", "질화", "nitride", "식각", "etch", "균일도", "uniformity",
    "밀도", "density", "속도", "rate", "선택비", "selectivity",
    "OES", "optical emission", "Langmuir", "진단", "diagnostic",
    "토카막", "tokamak", "핵융합", "fusion", "자기장", "magnetic field",
    "전기장", "electric field", "방전", "discharge", "글로우", "glow",
    "아크", "arc", "대기압", "atmospheric", "진공", "vacuum",
    "나노", "nano", "표면", "surface", "계면", "interface",
    "전구체", "precursor", "세정", "cleaning", "패시베이션", "passivation",
    "ALD", "atomic layer", "PECVD", "ICP", "CCP", "마이크로파", "microwave",
    "수소", "hydrogen", "산소", "oxygen", "질소", "nitrogen", "아르곤", "argon",
    "불소", "fluorine", "CF4", "SF6", "Cl2", "HBr", "O2", "Ar", "N2", "H2",
    "시뮬레이션", "simulation", "모델링", "modeling", "머신러닝", "machine learning",
    "딥러닝", "deep learning", "인공지능", "AI", "센서", "sensor",
    "스펙트럼", "spectrum", "파장", "wavelength", "광학", "optical",
    "임피던스", "impedance", "주파수", "frequency", "파워", "power",
    "두께", "thickness", "거칠기", "roughness", "결함", "defect",
    "수율", "yield", "신뢰성", "reliability", "수명", "lifetime"
]

EQUIPMENT_TERMS = [
    "ICP", "CCP", "PECVD", "ALD", "CVD", "PVD", "OES", "Langmuir",
    "microwave", "마이크로파", "tokamak", "챔버", "chamber", "reactor",
    "probe", "mass spectrometry", "RF", "DC"
]

GAS_TERMS = [
    "Ar", "O2", "N2", "H2", "CF4", "SF6", "Cl2", "HBr", "BCl3",
    "CHF3", "C4F8", "SiH4", "He", "Ne", "Xe", "아르곤", "산소", "질소", "수소"
]

MATERIAL_TERMS = [
    "silicon", "실리콘", "Si", "SiO2", "SiN", "GaN", "Al2O3", "TiN",
    "polymer", "폴리머", "graphene", "그래핀", "glass", "유리",
    "wafer", "웨이퍼", "photoresist", "레지스트", "박막", "thin film"
]

OBJECTIVE_KEYWORDS = {
    "균일도 개선": ["uniformity", "균일도"],
    "식각 성능": ["etch rate", "식각", "etching", "선택비", "selectivity"],
    "증착 품질": ["deposition", "증착", "thickness", "막질", "stress", "roughness"],
    "진단/계측": ["diagnostic", "진단", "OES", "Langmuir", "spectroscopy", "sensor"],
    "공정 제어": ["control", "monitoring", "최적화", "optimization", "real-time"],
    "모델링/시뮬레이션": ["simulation", "modeling", "시뮬레이션", "모델링", "numerical"],
    "표면 개질": ["surface", "표면", "adhesion", "hydroph", "passivation", "세정", "cleaning"],
    "결함/손상 저감": ["defect", "결함", "damage", "손상", "reliability", "수율"],
    "플라즈마 원천/방전": ["discharge", "방전", "electron density", "밀도", "plasma source", "RF", "DC"],
}

# ==============================================================================
# 컬렉션 메타데이터 & 모델 관리
# ==============================================================================
def _load_collection_meta():
    meta_helper = wiz.model("collectionmeta")
    return meta_helper.load(COLLECTION_META_PATH)

def _get_collection_model(collection_name):
    meta_helper = wiz.model("collectionmeta")
    return meta_helper.get_model(COLLECTION_META_PATH, collection_name, DEFAULT_MODEL)

def _get_model(model_name=None):
    if model_name is None:
        model_name = DEFAULT_MODEL
    if model_name not in MODEL_REGISTRY:
        model_name = DEFAULT_MODEL
    if not hasattr(sys, '_embedding_models') or sys._embedding_models is None:
        sys._embedding_models = {}
    if model_name not in sys._embedding_models or sys._embedding_models[model_name] is None:
        sys._embedding_models[model_name] = SentenceTransformer(model_name)
    return sys._embedding_models[model_name]

def _get_client():
    if not hasattr(sys, '_milvus_client') or sys._milvus_client is None:
        db_path = MILVUS_URI
        if not db_path.startswith("http"):
            db_dir = os.path.dirname(db_path)
            os.makedirs(db_dir, exist_ok=True)
        sys._milvus_client = MilvusClient(uri=db_path)
    return sys._milvus_client

def _resolve_collection_and_model():
    """요청에서 컬렉션 결정 → 해당 컬렉션의 모델 로드"""
    collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip()
    if not collection_name:
        collection_name = DEFAULT_COLLECTION
    model_name = _get_collection_model(collection_name)
    return collection_name, model_name


def _top_counter_items(counter, limit=6):
    return [
        {"term": term, "count": count}
        for term, count in counter.most_common(limit)
    ]


def _extract_term_counts(text, terms):
    text_lower = (text or "").lower()
    counter = Counter()
    for term in terms:
        occurrences = text_lower.count(term.lower())
        if occurrences > 0:
            counter[term] += occurrences
    return counter


def _extract_entity_facets(text):
    return {
        "equipment": _extract_term_counts(text, EQUIPMENT_TERMS),
        "gases": _extract_term_counts(text, GAS_TERMS),
        "materials": _extract_term_counts(text, MATERIAL_TERMS),
    }


def _extract_objective_tags(text):
    text_lower = (text or "").lower()
    counter = Counter()
    for label, terms in OBJECTIVE_KEYWORDS.items():
        score = 0
        for term in terms:
            score += text_lower.count(term.lower())
        if score > 0:
            counter[label] = score
    return counter


def _jaccard_similarity(a, b):
    if not a or not b:
        return 0.0
    sa = set(a)
    sb = set(b)
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def _safe_year_value(year):
    try:
        value = int(year)
        if 1900 <= value <= 2100:
            return value
    except Exception:
        pass
    return 0


def _load_project_contexts(collection_name):
    projects = _load_json(PROJECTS_FILE, [])
    if not isinstance(projects, list):
        return []
    rows = []
    for project in projects:
        if not isinstance(project, dict):
            continue
        if (project.get("collection", "") or "").strip() != collection_name:
            continue
        rows.append(project)
    return rows


def _parse_json_list(value):
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _research_config():
    try:
        return wiz.config("research")
    except Exception:
        return None


def _config_value(config, key, default=None):
    if config is None:
        return default
    return getattr(config, key, default)


def _kipris_plus_settings():
    config = _research_config()
    return {
        "endpoint": _config_value(config, "kipris_plus_endpoint", ""),
        "api_key": _config_value(config, "kipris_plus_api_key", ""),
        "api_key_param": _config_value(config, "kipris_plus_api_key_param", "accessKey"),
        "query_param": _config_value(config, "kipris_plus_query_param", "word"),
        "docs_start_param": _config_value(config, "kipris_plus_docs_start_param", "docsStart"),
        "docs_count_param": _config_value(config, "kipris_plus_docs_count_param", "docsCount"),
        "docs_start": str(_config_value(config, "kipris_plus_docs_start", "1") or "1"),
        "docs_count": str(_config_value(config, "kipris_plus_docs_count", "10") or "10"),
        "timeout": int(_config_value(config, "kipris_plus_timeout", 20) or 20),
        "response_format": str(_config_value(config, "kipris_plus_response_format", "xml") or "xml").lower(),
        "default_params": dict(_config_value(config, "kipris_plus_default_params", {}) or {}),
    }


def _xml_text(node, tags):
    for tag in tags:
        found = node.find(f".//{tag}")
        if found is not None and found.text and found.text.strip():
            return found.text.strip()
    return ""


def _dict_text(item, keys):
    if not isinstance(item, dict):
        return ""
    for key in keys:
        value = item.get(key, "")
        if value is None:
            continue
        value = str(value).strip()
        if value:
            return value
    return ""


def _extract_kipris_items_from_xml(text):
    root = ET.fromstring(text)
    header = root.find('.//header')
    success = _xml_text(root, ["successYN"]).upper()
    result_msg = _xml_text(root, ["resultMsg", "message"])
    result_code = _xml_text(root, ["resultCode", "code"])

    item_nodes = []
    for path in [".//body/items/item", ".//items/item", ".//item"]:
        item_nodes = root.findall(path)
        if item_nodes:
            break

    return {
        "success": success == "Y" or bool(item_nodes),
        "result_msg": result_msg,
        "result_code": result_code,
        "items": item_nodes,
    }


def _extract_kipris_items_from_json(payload):
    body = payload.get("body", {}) if isinstance(payload, dict) else {}
    items = body.get("items", []) if isinstance(body, dict) else []
    if isinstance(items, dict):
        items = items.get("item", []) or []
    if isinstance(items, dict):
        items = [items]
    header = payload.get("header", {}) if isinstance(payload, dict) else {}
    success = str(header.get("successYN", "") or header.get("successYn", "")).upper()
    return {
        "success": success == "Y" or bool(items),
        "result_msg": str(header.get("resultMsg", "") or header.get("message", "")),
        "result_code": str(header.get("resultCode", "") or header.get("code", "")),
        "items": items if isinstance(items, list) else [],
    }


def _normalize_kipris_patent_item(item, index=0):
    if isinstance(item, ET.Element):
        getter = lambda keys: _xml_text(item, keys)
    else:
        getter = lambda keys: _dict_text(item, keys)

    title = getter(["inventionTitle", "utilityTitle", "title", "koreanTitle", "astrtTitle"])
    abstract = getter(["astrtCont", "abstract", "abstractText", "summary", "inventionSummary"])
    applicant = getter(["applicantName", "applicant", "rightHolderName"])
    application_number = getter(["applicationNumber", "applNum", "applicationNo"])
    publication_number = getter(["publicationNumber", "publicNumber", "laidOpenNumber"])
    register_number = getter(["registerNumber", "regNumber"])
    application_date = getter(["applicationDate", "applDate"])
    publication_date = getter(["publicationDate", "laidOpenDate", "openDate"])
    register_date = getter(["registerDate", "regDate"])

    year = ""
    for candidate in [publication_date, register_date, application_date, title]:
        years = _extract_year_candidates_from_text(candidate)
        if years:
            year = str(max(years))
            break

    combined_text = " ".join([title, abstract, applicant])
    domain_counter = _extract_terms_from_text(combined_text)
    tech_keywords = [term for term, _ in domain_counter.most_common(5)]

    return {
        "title": title or "제목 없음",
        "abstract": abstract or getter(["claimText", "claim"]) or "",
        "authors": applicant,
        "year": year,
        "score": round(max(0.2, 1 - (index * 0.05)), 4),
        "tech_keywords": tech_keywords,
        "application_number": application_number,
        "publication_number": publication_number,
        "register_number": register_number,
        "application_date": application_date,
        "publication_date": publication_date,
        "register_date": register_date,
        "source": "KIPRIS Plus",
        "type": "특허",
    }


def _kipris_plus_patent_search(query):
    settings = _kipris_plus_settings()
    endpoint = (settings.get("endpoint") or "").strip()
    api_key = (settings.get("api_key") or "").strip()

    if not endpoint:
        raise RuntimeError("KIPRIS Plus endpoint가 설정되지 않았습니다. `project/main/config/research.py` 또는 환경변수를 확인하세요.")
    if not api_key:
        raise RuntimeError("KIPRIS Plus API 키가 설정되지 않았습니다. `KIPRIS_PLUS_API_KEY` 또는 `project/main/config/research.py`를 설정하세요.")

    params = {}
    params.update(settings.get("default_params") or {})
    params[settings.get("query_param") or "word"] = query
    params[settings.get("api_key_param") or "accessKey"] = api_key
    if settings.get("docs_start_param"):
        params[settings["docs_start_param"]] = settings.get("docs_start", "1")
    if settings.get("docs_count_param"):
        params[settings["docs_count_param"]] = settings.get("docs_count", "10")

    if settings.get("response_format") == "json":
        params.setdefault("format", "json")

    url = endpoint
    separator = '&' if '?' in endpoint else '?'
    url = f"{endpoint}{separator}{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/xml, application/json, text/xml"})
    with urllib.request.urlopen(req, timeout=settings.get("timeout", 20)) as response:
        raw = response.read().decode("utf-8", "ignore")
        content_type = response.headers.get("Content-Type", "")

    if raw.lstrip().startswith("{") or "json" in content_type.lower():
        parsed = _extract_kipris_items_from_json(json.loads(raw))
    else:
        parsed = _extract_kipris_items_from_xml(raw)

    if not parsed.get("success") and not parsed.get("items"):
        message = parsed.get("result_msg") or "KIPRIS Plus 응답을 해석하지 못했습니다. endpoint/파라미터 구성을 확인하세요."
        raise RuntimeError(message)

    patents = []
    for index, item in enumerate(parsed.get("items") or []):
        patent = _normalize_kipris_patent_item(item, index=index)
        if not patent.get("title") and not patent.get("abstract"):
            continue
        patents.append(patent)
    return patents


def _extract_year_from_filename(filename):
    filename = (filename or "").strip()
    if not filename:
        return ""

    years = re.findall(r'(?<!\d)((?:19|20)\d{2})(?!\d)', filename)
    if not years:
        return ""

    # Prefer the latest valid year in filename.
    valid = []
    for year in years:
        try:
            year_int = int(year)
            if 1900 <= year_int <= 2100:
                valid.append(year_int)
        except Exception:
            pass
    if not valid:
        return ""
    return str(max(valid))


def _extract_year_candidates_from_text(text):
    text = (text or "").strip()
    if not text:
        return []

    candidates = []
    patterns = [
        r'available\s+online[\s\S]{0,80}?((?:19|20)\d{2})',
        r'published[\s\S]{0,80}?((?:19|20)\d{2})',
        r'accepted[\s\S]{0,80}?((?:19|20)\d{2})',
        r'received[\s\S]{0,80}?((?:19|20)\d{2})',
        r'\b(?:applied|journal|vacuum|thin solid films|materials science|micromachines|physics)\b[^\n]{0,60}\(((?:19|20)\d{2})\)',
        r'\(((?:19|20)\d{2})\)',
        r'\b((?:19|20)\d{2})\b',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            year = match.group(1)
            try:
                year_int = int(year)
                if 1900 <= year_int <= 2100:
                    candidates.append(year_int)
            except Exception:
                pass

    # preserve order while deduplicating
    seen = set()
    ordered = []
    for year in candidates:
        if year in seen:
            continue
        seen.add(year)
        ordered.append(year)
    return ordered


def _extract_temporal_signals(text):
    text = (text or "").strip()
    signals = {
        "publication_year": "",
        "online_year": "",
        "accepted_year": "",
        "received_year": "",
    }
    if not text:
        return signals

    patterns = {
        "online_year": [
            r'available\s+online[\s\S]{0,80}?((?:19|20)\d{2})',
            r'online[\s\S]{0,40}?((?:19|20)\d{2})',
        ],
        "publication_year": [
            r'published[\s\S]{0,80}?((?:19|20)\d{2})',
            r'\b(?:applied|journal|vacuum|thin solid films|materials science|micromachines|physics)\b[^\n]{0,60}\(((?:19|20)\d{2})\)',
            r'\(((?:19|20)\d{2})\)',
        ],
        "accepted_year": [
            r'accepted[\s\S]{0,80}?((?:19|20)\d{2})',
        ],
        "received_year": [
            r'received[\s\S]{0,80}?((?:19|20)\d{2})',
        ],
    }

    for key, regex_list in patterns.items():
        for pattern in regex_list:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            year = match.group(1)
            try:
                year_int = int(year)
                if 1900 <= year_int <= 2100:
                    signals[key] = str(year_int)
                    break
            except Exception:
                pass

    if not signals["publication_year"]:
        candidates = _extract_year_candidates_from_text(text)
        if candidates:
            signals["publication_year"] = str(max(candidates))

    return signals


def _extract_best_paper_years(filename="", text=""):
    filename_year = _extract_year_from_filename(filename)
    signals = _extract_temporal_signals(text)

    publication_year = filename_year or signals.get("publication_year", "")
    online_year = signals.get("online_year", "")
    accepted_year = signals.get("accepted_year", "")
    received_year = signals.get("received_year", "")
    primary_year = publication_year or online_year or accepted_year or received_year

    return {
        "year": primary_year,
        "publication_year": publication_year,
        "online_year": online_year,
        "accepted_year": accepted_year,
        "received_year": received_year,
    }


def _is_latest_intent(text):
    q = (text or "").lower()
    return any(token in q for token in ["최신", "최근", "latest", "recent", "newest", "up-to-date"])


def _strip_latest_terms(text):
    cleaned = re.sub(r'\b(latest|recent|newest|up-to-date)\b', ' ', text or '', flags=re.IGNORECASE)
    cleaned = re.sub(r'(최신|최근)', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _load_doc_head_text(client, collection_name, doc_id):
    if client is None or not collection_name or not doc_id:
        return ""
    try:
        rows = client.query(
            collection_name=collection_name,
            filter=f'doc_id == "{doc_id}" && chunk_index == 0',
            output_fields=["text"],
            limit=1,
        )
        if rows:
            return (rows[0].get("text", "") or "")[:4000]
    except Exception:
        pass
    return ""


def _recommend_papers_data(interests="", collection_name=None):
    interests = (interests or "").strip()
    if not interests:
        return []

    if collection_name is None or not str(collection_name).strip():
        collection_name, model_name = _resolve_collection_and_model()
    else:
        collection_name = str(collection_name).strip()
        model_name = _get_collection_model(collection_name)

    client = _get_client()
    if not client.has_collection(collection_name):
        return []

    model = _get_model(model_name)
    latest_intent = _is_latest_intent(interests)
    semantic_query = _strip_latest_terms(interests) if latest_intent else interests
    if not semantic_query:
        semantic_query = interests

    query_vec = model.encode([semantic_query], normalize_embeddings=True)[0].tolist()
    limit = 30 if latest_intent else 15

    results = client.search(
        collection_name=collection_name,
        data=[query_vec],
        limit=limit,
        output_fields=["doc_id", "filename", "chunk_index", "text", "page_num"],
        search_params={"metric_type": "COSINE"}
    )

    seen_docs = set()
    papers = []
    for hit in results[0]:
        entity = hit.get("entity", {})
        doc_id = entity.get("doc_id", "")
        if doc_id in seen_docs:
            continue
        seen_docs.add(doc_id)

        filename = entity.get("filename", doc_id)
        raw_text = entity.get("text", "") or ""
        text_preview = raw_text[:400]
        head_text = _load_doc_head_text(client, collection_name, doc_id)
        year_source_text = "\n\n".join(part for part in [head_text[:4000], raw_text[:2000]] if part)
        doc_title = filename or doc_id or "제목 없음"
        years = _extract_best_paper_years(filename, year_source_text)

        interest_terms = [t.strip().lower() for t in re.split(r'[,\s]+', semantic_query) if t.strip()]
        text_lower = (doc_title + " " + text_preview).lower()
        matched = [t for t in interest_terms if t in text_lower]

        papers.append({
            "doc_id": doc_id,
            "title": doc_title,
            "text": text_preview,
            "abstract": text_preview,
            "score": round(hit.get("distance", 0), 4),
            "authors": "",
            "year": years.get("year", ""),
            "publication_year": years.get("publication_year", ""),
            "online_year": years.get("online_year", ""),
            "accepted_year": years.get("accepted_year", ""),
            "received_year": years.get("received_year", ""),
            "filename": filename,
            "page_num": entity.get("page_num", 0),
            "matched_terms": matched,
            "relevance": "높음" if hit.get("distance", 0) > 0.7 else ("보통" if hit.get("distance", 0) > 0.5 else "낮음")
        })

    if latest_intent:
        papers.sort(key=lambda x: (
            -(int(x.get("year")) if str(x.get("year", "")).isdigit() else 0),
            -float(x.get("score", 0) or 0)
        ))
    else:
        papers.sort(key=lambda x: -float(x.get("score", 0) or 0))

    return papers[:15]


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


def _extract_condition_mentions(text):
    if not text:
        return []
    patterns = [
        r'\b\d+\.?\d*\s*(?:mTorr|Torr|Pa|kPa|mbar)\b',
        r'\b\d+\.?\d*\s*(?:W|kW)\b',
        r'\b\d+\.?\d*\s*(?:sccm|slm)\b',
        r'\b\d+\.?\d*\s*(?:°C|℃|K)\b',
        r'\b\d+\.?\d*\s*(?:MHz|kHz|GHz)\b',
        r'\b(?:Ar|O2|N2|H2|He|CF4|SF6|Cl2|BCl3|HBr|SiH4|C4F8|CHF3)\b'
    ]
    items = []
    seen = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = match.group(0).strip()
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(value)
            if len(items) >= 8:
                return items
    return items


def serve_pdf():
    """PDF 원본 파일 서빙 — doc_id와 collection으로 조회, page 파라미터로 특정 페이지 이동"""
    flask = wiz.response._flask
    doc_id = wiz.request.query("doc_id", "").strip()
    collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip()

    if not doc_id:
        wiz.response.status(400, message="doc_id is required")

    pdf_path = os.path.join(PDF_DIR, collection_name, f"{doc_id}.pdf")
    if not os.path.isfile(pdf_path):
        wiz.response.status(404, message="PDF 파일을 찾을 수 없습니다. 임베딩 이후 업로드된 문서만 원문 조회가 가능합니다.")

    resp = flask.send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=False,
    )
    wiz.response.response(resp)


def _build_evidence_item(entity, score):
    text = entity.get("text", "") or ""
    return {
        "doc_id": entity.get("doc_id", ""),
        "filename": entity.get("filename", ""),
        "chunk_index": entity.get("chunk_index", 0),
        "page_num": entity.get("page_num", 0),
        "text": text[:220],
        "score": round(score or 0, 4),
        "conditions": _extract_condition_mentions(text)
    }


def list_evidence_traces():
    collection_name = wiz.request.query("collection", "").strip()
    traces = _load_json(EVIDENCE_TRACE_PATH, [])
    if collection_name:
        traces = [trace for trace in traces if trace.get("collection") == collection_name]
    wiz.response.status(200, traces=traces[:50])


def save_evidence_trace():
    trace_type = wiz.request.query("trace_type", "general")
    title = wiz.request.query("title", "")
    summary = wiz.request.query("summary", "")
    keyword = wiz.request.query("keyword", "")
    collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip() or DEFAULT_COLLECTION
    evidence_raw = wiz.request.query("evidence", "[]")
    meta_raw = wiz.request.query("meta", "{}")

    if not title.strip():
        wiz.response.status(400, message="추적 제목이 필요합니다.")

    try:
        evidence = json.loads(evidence_raw)
    except Exception:
        evidence = []

    try:
        meta = json.loads(meta_raw)
    except Exception:
        meta = {}

    extracted_conditions = []
    seen_conditions = set()
    normalized_evidence = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        conditions = item.get("conditions", []) or _extract_condition_mentions(item.get("text", ""))
        normalized = dict(item)
        normalized["conditions"] = conditions
        normalized_evidence.append(normalized)
        for condition in conditions:
            key = condition.lower()
            if key in seen_conditions:
                continue
            seen_conditions.add(key)
            extracted_conditions.append(condition)

    traces = _load_json(EVIDENCE_TRACE_PATH, [])
    trace = {
        "id": str(uuid.uuid4())[:8],
        "trace_type": trace_type,
        "title": title,
        "summary": summary,
        "keyword": keyword,
        "collection": collection_name,
        "evidence": normalized_evidence,
        "meta": meta,
        "extracted_conditions": extracted_conditions,
        "created_at": datetime.now().isoformat()
    }
    traces.insert(0, trace)
    _save_json(EVIDENCE_TRACE_PATH, traces[:200])
    wiz.response.status(200, trace=trace)


def _extract_terms_from_text(text):
    text_lower = text.lower()
    counter = Counter()
    for term in PLASMA_TERMS:
        tl = term.lower()
        cnt = text_lower.count(tl)
        if cnt > 0:
            counter[term] += cnt
    return counter


def collections():
    """사용 가능한 컬렉션 목록 반환 (문서 수, 청크 수 포함)"""
    try:
        client = _get_client()
        col_names = client.list_collections()
        meta = _load_collection_meta()
        meta_helper = wiz.model("collectionmeta")

        result = []
        for name in col_names:
            info = meta_helper.normalize_info(meta.get(name, {}))

            # 메타가 없거나 short_name이 Unknown인 경우 dim으로 모델 추론
            if not info or info.get("short_name") == "Unknown":
                try:
                    col_info = client.describe_collection(name)
                    dim = 768
                    for field in col_info.get("fields", []):
                        if field.get("name") == "embedding":
                            params = field.get("params", {})
                            dim = params.get("dim", field.get("dim", 768))
                            if isinstance(dim, str):
                                dim = int(dim)
                            break
                    # dim으로 모델 추론
                    dim_to_model = {}
                    for mname, minfo in MODEL_REGISTRY.items():
                        d = minfo["dim"]
                        if d not in dim_to_model:
                            dim_to_model[d] = mname
                    inferred = dim_to_model.get(dim, DEFAULT_MODEL)
                    inferred_info = MODEL_REGISTRY.get(inferred, {})
                    info = {
                        "model": inferred,
                        "dim": dim,
                        "short_name": inferred_info.get("short_name", inferred)
                    }
                except Exception:
                    pass

            # 통계 조회 (문서 수, 청크 수)
            total_chunks = 0
            total_docs = 0
            try:
                stats_info = client.get_collection_stats(name)
                total_chunks = stats_info.get("row_count", 0)
                if total_chunks > 0:
                    docs = client.query(
                        collection_name=name,
                        filter="chunk_index == 0",
                        output_fields=["doc_id"],
                        limit=10000
                    )
                    total_docs = len(docs)
            except Exception:
                pass

            result.append({
                "name": name,
                "model": info.get("model", DEFAULT_MODEL),
                "short_name": info.get("short_name", "Unknown"),
                "dim": info.get("dim", 768),
                "total_docs": total_docs,
                "total_chunks": total_chunks
            })
        wiz.response.status(200, collections=result)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        wiz.response.status(200, collections=[])


def run_discover_data(keyword="", top_k=20, collection_name=None):
    collection_name = (collection_name or DEFAULT_COLLECTION).strip() or DEFAULT_COLLECTION
    client = _get_client()
    if not client.has_collection(collection_name):
        return {"clusters": [], "message": "컬렉션이 없습니다. 먼저 PDF를 임베딩하세요."}

    if not keyword.strip():
        results = client.query(
            collection_name=collection_name,
            filter="chunk_index == 0",
            output_fields=["doc_id", "filename", "text", "page_num"],
            limit=50
        )
        docs = []
        for r in results:
            docs.append({
                "doc_id": r.get("doc_id", ""),
                "filename": r.get("filename", ""),
                "snippet": r.get("text", "")[:200],
                "page_num": r.get("page_num", 0)
            })
        return {"mode": "overview", "docs": docs, "total": len(docs)}

    model_name = _get_collection_model(collection_name)
    model = _get_model(model_name)
    query_vec = model.encode([keyword], normalize_embeddings=True)[0].tolist()

    search_results = client.search(
        collection_name=collection_name,
        data=[query_vec],
        limit=top_k,
        output_fields=["doc_id", "filename", "chunk_index", "text", "page_num"],
        search_params={"metric_type": "COSINE"}
    )

    doc_groups = {}
    for hit in search_results[0]:
        entity = hit.get("entity", {})
        doc_id = entity.get("doc_id", "unknown")
        if doc_id not in doc_groups:
            doc_groups[doc_id] = {
                "doc_id": doc_id,
                "filename": entity.get("filename", ""),
                "chunks": [],
                "max_score": 0
            }
        score = hit.get("distance", 0)
        doc_groups[doc_id]["chunks"].append({
            "chunk_index": entity.get("chunk_index", 0),
            "text": entity.get("text", "")[:300],
            "score": round(score, 4),
            "page_num": entity.get("page_num", 0)
        })
        if score > doc_groups[doc_id]["max_score"]:
            doc_groups[doc_id]["max_score"] = round(score, 4)

    clusters = sorted(doc_groups.values(), key=lambda x: x["max_score"], reverse=True)
    return {
        "mode": "search",
        "keyword": keyword,
        "clusters": clusters,
        "total_hits": len(search_results[0])
    }


def run_recommend_data(keyword="", collection_name=None):
    if not keyword.strip():
        raise ValueError("추천을 위한 키워드를 입력하세요.")

    collection_name = (collection_name or DEFAULT_COLLECTION).strip() or DEFAULT_COLLECTION
    client = _get_client()
    if not client.has_collection(collection_name):
        return {"recommendations": [], "message": "컬렉션이 없습니다. 먼저 PDF를 임베딩하세요."}

    model_name = _get_collection_model(collection_name)
    model = _get_model(model_name)
    recommendations = []

    query_vec = model.encode([keyword], normalize_embeddings=True)[0].tolist()
    direct_results = client.search(
        collection_name=collection_name,
        data=[query_vec],
        limit=30,
        output_fields=["doc_id", "filename", "chunk_index", "text", "page_num"],
        search_params={"metric_type": "COSINE"}
    )

    all_texts = []
    direct_doc_ids = set()
    for hit in direct_results[0]:
        entity = hit.get("entity", {})
        all_texts.append(entity.get("text", ""))
        direct_doc_ids.add(entity.get("doc_id", ""))

    combined_text = " ".join(all_texts)
    cooccurring = _extract_terms_from_text(combined_text)

    keyword_lower = keyword.lower()
    filtered_terms = []
    for term, freq in cooccurring.most_common(50):
        if term.lower() in keyword_lower or keyword_lower in term.lower():
            continue
        if len(term) <= 1:
            continue
        filtered_terms.append((term, freq))

    cross_queries = []
    for term, freq in filtered_terms[:8]:
        cross_query = f"{keyword} {term}"
        cross_queries.append((cross_query, term, freq))

    for cross_query, co_term, freq in cross_queries[:6]:
        cross_vec = model.encode([cross_query], normalize_embeddings=True)[0].tolist()
        cross_results = client.search(
            collection_name=collection_name,
            data=[cross_vec],
            limit=5,
            output_fields=["doc_id", "filename", "text", "page_num"],
            search_params={"metric_type": "COSINE"}
        )
        if not cross_results[0]:
            continue
        top_hit = cross_results[0][0]
        score = top_hit.get("distance", 0)
        evidence_snippets = []
        for h in cross_results[0][:3]:
            e = h.get("entity", {})
            evidence_snippets.append(_build_evidence_item(e, h.get("distance", 0)))
        recommendations.append({
            "type": "cross_topic",
            "title": f"{keyword} × {co_term}",
            "description": f"'{keyword}'와 '{co_term}'의 교차 영역을 탐구하는 연구 주제입니다. 기존 문헌에서 두 개념이 {freq}회 함께 출현하여 연관성이 확인되었습니다.",
            "relevance": round(score, 4),
            "co_term": co_term,
            "co_frequency": freq,
            "evidence": evidence_snippets
        })

    gap_results = client.search(
        collection_name=collection_name,
        data=[query_vec],
        limit=50,
        output_fields=["doc_id", "filename", "chunk_index", "text", "page_num"],
        search_params={"metric_type": "COSINE"}
    )
    gap_candidates = []
    for hit in gap_results[0]:
        score = hit.get("distance", 0)
        if 0.25 <= score <= 0.65:
            entity = hit.get("entity", {})
            gap_candidates.append({
                "doc_id": entity.get("doc_id", ""),
                "filename": entity.get("filename", ""),
                "text": entity.get("text", ""),
                "score": score
            })

    gap_unique_terms = Counter()
    for gc in gap_candidates:
        terms = _extract_terms_from_text(gc["text"])
        for t, c in terms.items():
            if t.lower() not in keyword_lower and keyword_lower not in t.lower():
                gap_unique_terms[t] += c

    for term, gap_freq in gap_unique_terms.most_common(15):
        direct_freq = cooccurring.get(term, 0)
        if gap_freq > direct_freq * 0.5 and len(term) > 1:
            gap_query = f"{keyword} {term} 연구"
            gap_vec = model.encode([gap_query], normalize_embeddings=True)[0].tolist()
            gap_search = client.search(
                collection_name=collection_name,
                data=[gap_vec],
                limit=3,
                output_fields=["doc_id", "filename", "text", "page_num"],
                search_params={"metric_type": "COSINE"}
            )
            evidence_snippets = []
            for h in gap_search[0]:
                e = h.get("entity", {})
                evidence_snippets.append(_build_evidence_item(e, h.get("distance", 0)))
            recommendations.append({
                "type": "research_gap",
                "title": f"{keyword}에서의 {term} 연구",
                "description": f"'{keyword}' 관련 핵심 문헌에서 '{term}'에 대한 연구가 상대적으로 부족합니다.",
                "relevance": round(gap_search[0][0].get("distance", 0) if gap_search[0] else 0, 4),
                "gap_term": term,
                "gap_frequency": gap_freq,
                "direct_frequency": direct_freq,
                "evidence": evidence_snippets
            })
            if len([r for r in recommendations if r["type"] == "research_gap"]) >= 4:
                break

    expansion_templates = [
        ("{keyword} 최적화 방법", "방법론 확장", "기존 '{keyword}' 연구에 새로운 최적화 방법론을 적용하는 연구 주제입니다."),
        ("{keyword} 실시간 모니터링", "응용 확장", "'{keyword}'의 실시간 모니터링 및 제어 기술로의 확장 가능성을 탐구합니다."),
        ("{keyword} 머신러닝 예측", "AI 융합", "'{keyword}' 데이터에 머신러닝/AI 기법을 적용한 예측 모델 연구입니다."),
        ("{keyword} 시뮬레이션 모델링", "계산 과학", "'{keyword}'의 물리적 현상을 시뮬레이션하고 모델링하는 계산 과학 연구입니다."),
        ("{keyword} 신소재 적용", "소재 확장", "'{keyword}' 기술을 신소재/차세대 소재에 적용하는 연구 방향입니다."),
    ]
    for template_query, category, desc_template in expansion_templates:
        expanded_query = template_query.format(keyword=keyword)
        expanded_desc = desc_template.format(keyword=keyword)
        exp_vec = model.encode([expanded_query], normalize_embeddings=True)[0].tolist()
        exp_results = client.search(
            collection_name=collection_name,
            data=[exp_vec],
            limit=3,
            output_fields=["doc_id", "filename", "text", "page_num"],
            search_params={"metric_type": "COSINE"}
        )
        if not exp_results[0]:
            continue
        top_score = exp_results[0][0].get("distance", 0)
        evidence_snippets = []
        for h in exp_results[0]:
            e = h.get("entity", {})
            evidence_snippets.append(_build_evidence_item(e, h.get("distance", 0)))
        recommendations.append({
            "type": "expansion",
            "title": expanded_query,
            "description": expanded_desc,
            "category": category,
            "relevance": round(top_score, 4),
            "evidence": evidence_snippets
        })

    seen_titles = set()
    unique_recs = []
    for r in recommendations:
        if r["title"] not in seen_titles:
            seen_titles.add(r["title"])
            unique_recs.append(r)
    type_order = {"cross_topic": 0, "research_gap": 1, "expansion": 2}
    unique_recs.sort(key=lambda x: (type_order.get(x["type"], 9), -x["relevance"]))
    return {
        "keyword": keyword,
        "recommendations": unique_recs,
        "total": len(unique_recs),
        "stats": {
            "cross_topic": len([r for r in unique_recs if r["type"] == "cross_topic"]),
            "research_gap": len([r for r in unique_recs if r["type"] == "research_gap"]),
            "expansion": len([r for r in unique_recs if r["type"] == "expansion"]),
            "docs_analyzed": len(direct_doc_ids),
            "terms_found": len(filtered_terms)
        }
    }


def discover():
    """키워드 기반 연구 주제 발굴 - 유사 문서 클러스터링"""
    try:
        keyword = wiz.request.query("keyword", "")
        top_k = int(wiz.request.query("top_k", "20"))
        collection_name, model_name = _resolve_collection_and_model()
        result = run_discover_data(keyword=keyword, top_k=top_k, collection_name=collection_name)
        wiz.response.status(200, **result)

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def recommend():
    """키워드 기반 탐색 후 새로운 연구 주제 추천"""
    try:
        keyword = wiz.request.query("keyword", "")
        if not keyword.strip():
            wiz.response.status(400, message="추천을 위한 키워드를 입력하세요.")
            return

        collection_name, model_name = _resolve_collection_and_model()
        result = run_recommend_data(keyword=keyword, collection_name=collection_name)
        wiz.response.status(200, **result)

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def related():
    """특정 문서의 관련 연구 주제 찾기"""
    try:
        doc_id = wiz.request.query("doc_id", "")
        if not doc_id:
            wiz.response.status(400, message="doc_id가 필요합니다.")

        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        model = _get_model(model_name)

        source_chunks = client.query(
            collection_name=collection_name,
            filter=f'doc_id == "{doc_id}" and chunk_index == 0',
            output_fields=["text", "filename"]
        )

        if not source_chunks:
            wiz.response.status(404, message="문서를 찾을 수 없습니다.")

        source_text = source_chunks[0].get("text", "")
        source_filename = source_chunks[0].get("filename", "")

        query_vec = model.encode([source_text], normalize_embeddings=True)[0].tolist()

        search_results = client.search(
            collection_name=collection_name,
            data=[query_vec],
            limit=30,
            output_fields=["doc_id", "filename", "chunk_index", "text", "page_num"],
            search_params={"metric_type": "COSINE"}
        )

        related_docs = {}
        for hit in search_results[0]:
            entity = hit.get("entity", {})
            hit_doc_id = entity.get("doc_id", "")
            if hit_doc_id == doc_id:
                continue
            if hit_doc_id not in related_docs:
                related_docs[hit_doc_id] = {
                    "doc_id": hit_doc_id,
                    "filename": entity.get("filename", ""),
                    "score": round(hit.get("distance", 0), 4),
                    "snippet": entity.get("text", "")[:200]
                }

        related_list = sorted(related_docs.values(), key=lambda x: x["score"], reverse=True)[:10]

        wiz.response.status(200,
            source_doc_id=doc_id,
            source_filename=source_filename,
            related=related_list)

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def keywords():
    """저장된 문서들에서 핵심 키워드/주제어 추출"""
    try:
        collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip()
        if not collection_name:
            collection_name = DEFAULT_COLLECTION

        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, keywords=[], message="컬렉션이 없습니다.")
            return

        results = client.query(
            collection_name=collection_name,
            filter="chunk_index == 0",
            output_fields=["text", "filename", "doc_id"],
            limit=100
        )

        term_counter = Counter()
        doc_term_map = {}

        for r in results:
            text = r.get("text", "").lower()
            doc_id = r.get("doc_id", "")
            filename = r.get("filename", "")
            for term in PLASMA_TERMS:
                tl = term.lower()
                count = text.count(tl)
                if count > 0:
                    term_counter[term] += count
                    if term not in doc_term_map:
                        doc_term_map[term] = []
                    doc_term_map[term].append({"doc_id": doc_id, "filename": filename})

        keywords_list = []
        for term, count in term_counter.most_common(30):
            keywords_list.append({
                "term": term,
                "frequency": count,
                "doc_count": len(doc_term_map.get(term, [])),
                "docs": doc_term_map.get(term, [])[:5]
            })

        wiz.response.status(200, keywords=keywords_list, total_docs=len(results))

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def topic_map():
    """토픽 클러스터링 & 2D 토픽 맵 생성"""
    try:
        collection_name, model_name = _resolve_collection_and_model()
        max_chunks = int(wiz.request.query("max_chunks", "500"))
        user_keywords = wiz.request.query("user_keywords", "").strip()
        seen_doc_ids = set(_parse_json_list(wiz.request.query("seen_doc_ids", "[]")))
        project_collection = wiz.request.query("project_collection", "").strip() or collection_name

        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, clusters=[], points=[], message="컬렉션이 없습니다.")
            return

        # 1. 청크 데이터 + 벡터 추출 (chunk_index==0: 문서 대표 청크)
        doc_chunks = client.query(
            collection_name=collection_name,
            filter="chunk_index == 0",
            output_fields=["doc_id", "filename", "text", "embedding", "page_num"],
            limit=max_chunks
        )

        if len(doc_chunks) < 3:
            wiz.response.status(200, clusters=[], points=[],
                message=f"클러스터링에 최소 3개 문서가 필요합니다. (현재 {len(doc_chunks)}개)")
            return

        # 벡터 & 메타데이터 분리
        embeddings = []
        doc_ids = []
        filenames = []
        texts = []
        page_nums = []
        for chunk in doc_chunks:
            emb = chunk.get("embedding", [])
            if emb and len(emb) > 0:
                embeddings.append(emb)
                doc_ids.append(chunk.get("doc_id", ""))
                filenames.append(chunk.get("filename", ""))
                texts.append(chunk.get("text", ""))
            page_nums.append(chunk.get("page_num", 0))

        if len(embeddings) < 3:
            wiz.response.status(200, clusters=[], points=[],
                message="유효한 임베딩 벡터가 부족합니다.")
            return

        X = np.array(embeddings, dtype=np.float32)
        n_samples = X.shape[0]

        # 2. UMAP 2D 투영
        coords_2d = None
        try:
            import umap
            n_neighbors = min(15, n_samples - 1)
            if n_neighbors < 2:
                n_neighbors = 2
            reducer = umap.UMAP(
                n_components=2,
                n_neighbors=n_neighbors,
                min_dist=0.1,
                metric='cosine',
                random_state=42
            )
            coords_2d = reducer.fit_transform(X)
        except Exception:
            # Fallback: PCA
            from sklearn.decomposition import PCA
            pca = PCA(n_components=2, random_state=42)
            coords_2d = pca.fit_transform(X)

        # 좌표 정규화 (0~100 범위)
        if coords_2d is not None:
            for dim in range(2):
                mn = coords_2d[:, dim].min()
                mx = coords_2d[:, dim].max()
                rng = mx - mn if mx - mn > 0 else 1.0
                coords_2d[:, dim] = (coords_2d[:, dim] - mn) / rng * 100

        # 3. HDBSCAN 클러스터링
        labels = None
        try:
            import hdbscan
            min_cluster = max(2, n_samples // 10)
            min_cluster = min(min_cluster, 5)
            min_samples_val = max(1, min(3, n_samples // 10))
            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=min_cluster,
                min_samples=min_samples_val,
                metric='euclidean',
                cluster_selection_epsilon=0.0,
                cluster_selection_method='eom'
            )
            labels = clusterer.fit_predict(X)
        except Exception:
            pass

        if labels is None or len(set(labels)) <= 1:
            # Fallback: KMeans
            from sklearn.cluster import KMeans
            n_clusters = max(2, min(n_samples // 3, 8))
            km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = km.fit_predict(X)

        # 4. 클러스터별 키워드 추출 (PLASMA_TERMS 기반 TF-IDF 스타일)
        cluster_ids = sorted(set(labels))
        # 노이즈 레이블(-1) 처리: "기타" 클러스터로 통합
        cluster_map = {}  # cluster_id -> list of indices
        for idx, label in enumerate(labels):
            cid = int(label) if label >= 0 else -1
            if cid not in cluster_map:
                cluster_map[cid] = []
            cluster_map[cid].append(idx)

        # 전체 문서 term frequency (DF 계산용)
        global_df = Counter()
        doc_terms_list = []
        for text in texts:
            doc_terms = _extract_terms_from_text(text)
            doc_terms_list.append(doc_terms)
            for term in doc_terms:
                global_df[term] += 1

        total_docs_count = len(texts)

        # 클러스터 정보 구성
        clusters_result = []
        color_palette = [
            "#8b5cf6", "#f59e0b", "#10b981", "#3b82f6",
            "#ef4444", "#06b6d4", "#ec4899", "#84cc16",
            "#f97316", "#6366f1", "#14b8a6", "#a855f7"
        ]

        for cid in sorted(cluster_map.keys()):
            indices = cluster_map[cid]

            # TF-IDF 스타일 키워드 추출
            cluster_tf = Counter()
            for i in indices:
                for term, cnt in doc_terms_list[i].items():
                    cluster_tf[term] += cnt

            # TF-IDF 점수 계산
            tfidf_scores = {}
            for term, tf in cluster_tf.items():
                df = global_df.get(term, 1)
                idf = np.log(total_docs_count / df + 1)
                tfidf_scores[term] = tf * idf

            top_keywords = sorted(tfidf_scores.items(), key=lambda x: -x[1])[:8]

            # 클러스터 중심 좌표
            cluster_coords = coords_2d[indices]
            center_x = float(np.mean(cluster_coords[:, 0]))
            center_y = float(np.mean(cluster_coords[:, 1]))
            cluster_vecs = X[indices]
            center_vec = np.mean(cluster_vecs, axis=0)

            # 클러스터 밀도 (평균 내부 거리의 역수)
            if len(indices) > 1:
                dists = np.linalg.norm(cluster_vecs - center_vec, axis=1)
                avg_dist = float(np.mean(dists))
                density = round(1.0 / (avg_dist + 0.001), 4)
            else:
                density = 0.0

            cluster_label = "기타 (미분류)" if cid == -1 else f"토픽 {cid + 1}"
            color_idx = (cid + 1) % len(color_palette) if cid >= 0 else 0
            color = "#9ca3af" if cid == -1 else color_palette[color_idx]

            # 유니크 문서 목록
            unique_docs = {}
            condition_counter = Counter()
            equipment_counter = Counter()
            gas_counter = Counter()
            material_counter = Counter()
            objective_counter = Counter()
            year_counter = Counter()

            for i in indices:
                similarity = float(np.dot(X[i], center_vec) /
                                   (np.linalg.norm(X[i]) * np.linalg.norm(center_vec) + 1e-8))
                doc_id = doc_ids[i]
                filename = filenames[i]
                text = texts[i] or ""
                page_num = page_nums[i]
                years = _extract_best_paper_years(filename, text)
                conditions = _extract_condition_mentions(text)
                for condition in conditions:
                    condition_counter[condition] += 1
                facets = _extract_entity_facets(text)
                equipment_counter.update(facets["equipment"])
                gas_counter.update(facets["gases"])
                material_counter.update(facets["materials"])
                objectives = _extract_objective_tags(text)
                objective_counter.update(objectives)
                if years.get("publication_year"):
                    year_counter[years["publication_year"]] += 1

                doc_payload = {
                    "doc_id": doc_id,
                    "filename": filename,
                    "snippet": text[:220],
                    "page_num": page_num,
                    "similarity": round(similarity, 4),
                    "year": years.get("year", ""),
                    "publication_year": years.get("publication_year", ""),
                    "online_year": years.get("online_year", ""),
                    "accepted_year": years.get("accepted_year", ""),
                    "received_year": years.get("received_year", ""),
                    "conditions": conditions,
                    "chunks": [{
                        "chunk_index": 0,
                        "text": text[:300],
                        "score": round(similarity, 4),
                        "page_num": page_num,
                    }],
                    "max_score": round(similarity, 4),
                }

                existing = unique_docs.get(doc_id)
                if existing is None or doc_payload["max_score"] > existing.get("max_score", 0):
                    unique_docs[doc_id] = doc_payload

            doc_list = sorted(unique_docs.values(), key=lambda item: (-item.get("max_score", 0), item.get("filename", "")))
            latest_docs = sorted(
                doc_list,
                key=lambda item: (-_safe_year_value(item.get("year")), -float(item.get("max_score", 0) or 0))
            )[:3]
            core_docs = doc_list[:3]
            year_distribution = [
                {"year": year, "count": count}
                for year, count in sorted(year_counter.items(), key=lambda item: (-_safe_year_value(item[0]), -item[1]))[:8]
            ]
            dominant_objectives = [
                {"term": term, "count": count}
                for term, count in objective_counter.most_common(5)
            ]

            clusters_result.append({
                "id": int(cid),
                "label": cluster_label,
                "color": color,
                "doc_count": len(unique_docs),
                "chunk_count": len(indices),
                "keywords": [{"term": t, "score": round(s, 2)} for t, s in top_keywords],
                "center": {"x": round(center_x, 2), "y": round(center_y, 2)},
                "density": density,
                "docs": doc_list,
                "latest_docs": latest_docs,
                "core_docs": core_docs,
                "year_distribution": year_distribution,
                "condition_distribution": _top_counter_items(condition_counter, limit=8),
                "entity_distribution": {
                    "equipment": _top_counter_items(equipment_counter, limit=6),
                    "gases": _top_counter_items(gas_counter, limit=6),
                    "materials": _top_counter_items(material_counter, limit=6),
                },
                "objectives": dominant_objectives,
                "condition_signals": [item["term"] for item in _top_counter_items(condition_counter, limit=6)],
                "objective_signals": [item["term"] for item in dominant_objectives],
            })

        # 5. 포인트 데이터 (2D 좌표 + 클러스터 레이블)
        points = []
        for idx in range(n_samples):
            cid = int(labels[idx]) if labels[idx] >= 0 else -1
            # 해당 클러스터의 색상
            color_idx = (cid + 1) % len(color_palette) if cid >= 0 else 0
            color = "#9ca3af" if cid == -1 else color_palette[color_idx]

            points.append({
                "x": round(float(coords_2d[idx, 0]), 2),
                "y": round(float(coords_2d[idx, 1]), 2),
                "cluster_id": cid,
                "doc_id": doc_ids[idx],
                "filename": filenames[idx],
                "page_num": page_nums[idx],
                "color": color
            })

        # 클러스터를 문서 수 역순 정렬 (기타는 마지막)
        clusters_result.sort(key=lambda c: (c["id"] == -1, -c["doc_count"]))

        # 6. 클러스터 간 관계 분석
        relationships = []
        valid_clusters = [c for c in clusters_result if c["id"] != -1]
        valid_cluster_map = {c["id"]: c for c in valid_clusters}
        if len(valid_clusters) >= 2:
            for i in range(len(valid_clusters)):
                for j in range(i + 1, len(valid_clusters)):
                    c1 = valid_clusters[i]
                    c2 = valid_clusters[j]
                    dx = c1["center"]["x"] - c2["center"]["x"]
                    dy = c1["center"]["y"] - c2["center"]["y"]
                    dist_2d = (dx**2 + dy**2) ** 0.5
                    indices_1 = cluster_map[c1["id"]]
                    indices_2 = cluster_map[c2["id"]]
                    center_vec_1 = np.mean(X[indices_1], axis=0)
                    center_vec_2 = np.mean(X[indices_2], axis=0)
                    cos_sim = float(np.dot(center_vec_1, center_vec_2) /
                                   (np.linalg.norm(center_vec_1) * np.linalg.norm(center_vec_2) + 1e-8))
                    kw1 = set(k["term"] for k in c1["keywords"])
                    kw2 = set(k["term"] for k in c2["keywords"])
                    shared = kw1 & kw2
                    if cos_sim > 0.7:
                        relation = "similar"
                    elif cos_sim > 0.4:
                        relation = "related"
                    else:
                        relation = "distinct"
                    relationships.append({
                        "cluster_a": c1["id"], "cluster_b": c2["id"],
                        "label_a": c1["label"], "label_b": c2["label"],
                        "color_a": c1["color"], "color_b": c2["color"],
                        "center_a": c1["center"], "center_b": c2["center"],
                        "distance_2d": round(dist_2d, 2),
                        "cosine_similarity": round(cos_sim, 4),
                        "shared_keywords": list(shared),
                        "condition_similarity": round(_jaccard_similarity(c1.get("condition_signals", []), c2.get("condition_signals", [])), 4),
                        "objective_similarity": round(_jaccard_similarity(c1.get("objective_signals", []), c2.get("objective_signals", [])), 4),
                        "relation": relation
                    })
            relationships.sort(key=lambda x: -x["cosine_similarity"])

        # 7. 브릿지 문서 탐지
        bridge_docs = []
        if len(valid_clusters) >= 2:
            for idx in range(n_samples):
                doc_cluster = int(labels[idx]) if labels[idx] >= 0 else -1
                if doc_cluster == -1:
                    continue
                cluster_sims = []
                for c in valid_clusters:
                    c_indices = cluster_map[c["id"]]
                    center_vec = np.mean(X[c_indices], axis=0)
                    sim = float(np.dot(X[idx], center_vec) /
                               (np.linalg.norm(X[idx]) * np.linalg.norm(center_vec) + 1e-8))
                    cluster_sims.append({"cluster_id": c["id"], "label": c["label"],
                                        "color": c["color"], "similarity": round(sim, 4)})
                cluster_sims.sort(key=lambda x: -x["similarity"])
                if len(cluster_sims) >= 2:
                    primary = cluster_sims[0]
                    secondary = cluster_sims[1]
                    if secondary["similarity"] > 0.5 and secondary["cluster_id"] != doc_cluster:
                        bridge_docs.append({
                            "doc_id": doc_ids[idx],
                            "filename": filenames[idx],
                            "page_num": page_nums[idx],
                            "snippet": texts[idx][:220],
                            "primary_cluster": primary,
                            "secondary_cluster": secondary,
                            "bridge_score": round(secondary["similarity"], 4)
                        })
            bridge_docs.sort(key=lambda x: -x["bridge_score"])
            bridge_docs = bridge_docs[:10]

        for cluster in valid_clusters:
            linked_bridge_docs = []
            for bridge_doc in bridge_docs:
                primary_id = bridge_doc.get("primary_cluster", {}).get("cluster_id")
                secondary_id = bridge_doc.get("secondary_cluster", {}).get("cluster_id")
                if cluster["id"] not in (primary_id, secondary_id):
                    continue
                linked_bridge_docs.append(bridge_doc)
            cluster["bridge_docs"] = linked_bridge_docs[:3]

        # 8. 클러스터별 대표 문장 추출
        for c in clusters_result:
            if c["id"] == -1:
                c["representative_snippet"] = ""
                c["representative_doc"] = ""
                continue
            c_indices = cluster_map.get(c["id"], [])
            if not c_indices:
                c["representative_snippet"] = ""
                c["representative_doc"] = ""
                continue
            center_vec = np.mean(X[c_indices], axis=0)
            best_idx = c_indices[0]
            best_sim = -1
            for ci in c_indices:
                sim = float(np.dot(X[ci], center_vec) /
                           (np.linalg.norm(X[ci]) * np.linalg.norm(center_vec) + 1e-8))
                if sim > best_sim:
                    best_sim = sim
                    best_idx = ci
            c["representative_snippet"] = texts[best_idx][:300]
            c["representative_doc"] = filenames[best_idx]

        contrast_pairs = []
        if len(valid_clusters) >= 2:
            for rel in relationships:
                cond_sim = rel.get("condition_similarity", 0)
                obj_sim = rel.get("objective_similarity", 0)
                if cond_sim < 0.2 or obj_sim > 0.25:
                    continue
                cluster_a = valid_cluster_map.get(rel["cluster_a"])
                cluster_b = valid_cluster_map.get(rel["cluster_b"])
                if cluster_a is None or cluster_b is None:
                    continue
                shared_conditions = sorted(
                    list(set(cluster_a.get("condition_signals", [])) & set(cluster_b.get("condition_signals", [])))
                )[:5]
                distinct_objectives = sorted(
                    list((set(cluster_a.get("objective_signals", [])) ^ set(cluster_b.get("objective_signals", []))))
                )[:6]
                contrast_pairs.append({
                    "cluster_a": rel["cluster_a"],
                    "cluster_b": rel["cluster_b"],
                    "label_a": rel["label_a"],
                    "label_b": rel["label_b"],
                    "color_a": rel["color_a"],
                    "color_b": rel["color_b"],
                    "condition_similarity": round(cond_sim, 4),
                    "objective_similarity": round(obj_sim, 4),
                    "shared_conditions": shared_conditions,
                    "distinct_objectives": distinct_objectives,
                })
            contrast_pairs.sort(key=lambda item: (-item["condition_similarity"], item["objective_similarity"]))
            contrast_pairs = contrast_pairs[:8]

        personalization = {
            "user_keyword_matches": [],
            "unseen_topics": [],
            "project_linked_topics": [],
            "active_keywords": user_keywords,
            "linked_projects": [],
        }

        if user_keywords and valid_clusters:
            try:
                user_model = _get_model(model_name)
                user_vec = user_model.encode([user_keywords], normalize_embeddings=True)[0]
                keyword_matches = []
                for cluster in valid_clusters:
                    c_indices = cluster_map[cluster["id"]]
                    center_vec = np.mean(X[c_indices], axis=0)
                    score = float(np.dot(user_vec, center_vec) /
                                  (np.linalg.norm(user_vec) * np.linalg.norm(center_vec) + 1e-8))
                    keyword_matches.append({
                        "cluster_id": cluster["id"],
                        "label": cluster["label"],
                        "color": cluster["color"],
                        "score": round(score, 4),
                        "keywords": cluster.get("keywords", [])[:4],
                        "reason": f"내 연구 키워드와 토픽 중심 유사도 {(score * 100):.0f}%"
                    })
                keyword_matches.sort(key=lambda item: -item["score"])
                personalization["user_keyword_matches"] = keyword_matches[:3]
            except Exception:
                pass

        if valid_clusters:
            unseen_topics = []
            for cluster in valid_clusters:
                cluster_doc_ids = [doc.get("doc_id", "") for doc in cluster.get("docs", [])]
                seen_count = sum(1 for doc_id in cluster_doc_ids if doc_id in seen_doc_ids)
                unseen_ratio = 1.0
                if cluster_doc_ids:
                    unseen_ratio = 1 - (seen_count / len(cluster_doc_ids))
                unseen_topics.append({
                    "cluster_id": cluster["id"],
                    "label": cluster["label"],
                    "color": cluster["color"],
                    "unseen_ratio": round(unseen_ratio, 4),
                    "seen_count": seen_count,
                    "doc_count": len(cluster_doc_ids),
                    "reason": "아직 열람하지 않은 문서 비중이 높은 토픽"
                })
            unseen_topics.sort(key=lambda item: (-item["unseen_ratio"], item["seen_count"], -item["doc_count"]))
            personalization["unseen_topics"] = unseen_topics[:3]

        linked_projects = _load_project_contexts(project_collection)
        personalization["linked_projects"] = [
            {
                "id": project.get("id", ""),
                "name": project.get("name", ""),
                "collection": project.get("collection", ""),
            }
            for project in linked_projects[:5]
        ]
        if linked_projects and valid_clusters:
            project_topics = []
            for cluster in valid_clusters:
                cluster_terms = set(k.get("term") for k in cluster.get("keywords", []) if k.get("term"))
                cluster_terms.update(cluster.get("objective_signals", []))
                project_score = 0
                matched_projects = []
                for project in linked_projects:
                    project_text = " ".join([
                        project.get("name", "") or "",
                        project.get("description", "") or "",
                        project.get("objective", "") or "",
                        project.get("tags", "") or "",
                    ]).lower()
                    matched = [term for term in cluster_terms if term and str(term).lower() in project_text]
                    if matched:
                        project_score += len(matched)
                        matched_projects.append({
                            "name": project.get("name", ""),
                            "matched_terms": matched[:4]
                        })
                if project_score <= 0:
                    continue
                project_topics.append({
                    "cluster_id": cluster["id"],
                    "label": cluster["label"],
                    "color": cluster["color"],
                    "score": project_score,
                    "projects": matched_projects[:3],
                    "reason": "연결된 프로젝트 설명/목표와 키워드가 겹치는 토픽"
                })
            project_topics.sort(key=lambda item: -item["score"])
            personalization["project_linked_topics"] = project_topics[:3]

        # 9. 전체 맵 해석 요약
        summary_parts = []
        n_valid = len(valid_clusters)
        summary_parts.append(f"총 {n_samples}개 문서가 {n_valid}개의 토픽 클러스터로 분류되었습니다.")
        if valid_clusters:
            densest = max(valid_clusters, key=lambda c: c["density"])
            largest = max(valid_clusters, key=lambda c: c["doc_count"])
            summary_parts.append(
                f"가장 큰 토픽은 '{largest['label']}'({largest['doc_count']}문서)이며, "
                f"가장 밀집된 토픽은 '{densest['label']}'(밀도 {densest['density']:.1f})입니다."
            )
        if relationships:
            closest = relationships[0]
            summary_parts.append(
                f"'{closest['label_a']}'와 '{closest['label_b']}'은 "
                f"유사도 {closest['cosine_similarity']:.2f}로 가장 밀접하게 연관되어 있습니다."
            )
            if len(relationships) > 1:
                most_distinct = relationships[-1]
                if most_distinct["cosine_similarity"] < 0.4:
                    summary_parts.append(
                        f"반면 '{most_distinct['label_a']}'와 '{most_distinct['label_b']}'은 "
                        f"유사도 {most_distinct['cosine_similarity']:.2f}로 가장 독립적인 연구 영역입니다."
                    )
        if bridge_docs:
            summary_parts.append(
                f"클러스터 간 교차 영역에 위치한 브릿지 문서가 {len(bridge_docs)}건 탐지되었습니다. "
                f"이 문서들은 서로 다른 연구 주제를 연결하는 역할을 합니다."
            )
        if contrast_pairs:
            top_contrast = contrast_pairs[0]
            summary_parts.append(
                f"또한 '{top_contrast['label_a']}'와 '{top_contrast['label_b']}'은 조건은 유사하지만 연구 목적은 다른 대비 토픽으로 탐지되었습니다."
            )
        noise_count = len(cluster_map.get(-1, []))
        if noise_count > 0:
            summary_parts.append(f"미분류 문서는 {noise_count}건으로, 독립적이거나 새로운 연구 방향일 수 있습니다.")

        interpretation = {
            "summary": " ".join(summary_parts),
            "relationships": relationships[:15],
            "bridge_docs": bridge_docs,
            "contrast_pairs": contrast_pairs,
            "personalization": personalization,
        }

        wiz.response.status(200,
            clusters=clusters_result,
            points=points,
            total_docs=n_samples,
            n_clusters=len([c for c in clusters_result if c["id"] != -1]),
            method="HDBSCAN+UMAP",
            interpretation=interpretation
        )

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def gap_detector():
    """Research Gap Detector - 벡터 공간 밀도 분석으로 연구 공백 탐지"""
    try:
        keywords_input = wiz.request.query("keywords", "")
        if not keywords_input.strip():
            wiz.response.status(400, message="분석할 키워드를 입력하세요.")
            return

        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, gaps=[], keyword_densities=[], message="컬렉션이 없습니다.")
            return

        model = _get_model(model_name)

        # 키워드 파싱 (쉼표 구분)
        kw_list = [k.strip() for k in keywords_input.split(",") if k.strip()]
        if len(kw_list) == 0:
            wiz.response.status(400, message="유효한 키워드를 입력하세요.")
            return

        # 각 키워드별 밀도 분석
        keyword_densities = []
        keyword_vecs = {}
        for kw in kw_list:
            vec = model.encode([kw], normalize_embeddings=True)[0].tolist()
            keyword_vecs[kw] = vec

            results = client.search(
                collection_name=collection_name,
                data=[vec],
                limit=20,
                output_fields=["doc_id", "filename", "chunk_index", "text", "page_num"],
                search_params={"metric_type": "COSINE"}
            )

            if not results[0]:
                keyword_densities.append({
                    "keyword": kw,
                    "density": 0,
                    "avg_similarity": 0,
                    "doc_count": 0,
                    "top_docs": []
                })
                continue

            # 밀도 계산: 상위 K개 결과의 평균 유사도 (COSINE이므로 높을수록 밀접)
            scores = [hit.get("distance", 0) for hit in results[0]]
            avg_score = sum(scores) / len(scores)

            # KNN 밀도: 가까운 K개의 평균 거리의 역수
            top5_scores = sorted(scores, reverse=True)[:5]
            knn_density = sum(top5_scores) / len(top5_scores) if top5_scores else 0

            # 유니크 문서
            unique_docs = {}
            for hit in results[0]:
                entity = hit.get("entity", {})
                doc_id = entity.get("doc_id", "")
                if doc_id not in unique_docs:
                    unique_docs[doc_id] = {
                        "doc_id": doc_id,
                        "filename": entity.get("filename", ""),
                        "score": round(hit.get("distance", 0), 4),
                        "snippet": entity.get("text", "")[:150]
                    }

            keyword_densities.append({
                "keyword": kw,
                "density": round(knn_density, 4),
                "avg_similarity": round(avg_score, 4),
                "doc_count": len(unique_docs),
                "top_docs": list(unique_docs.values())[:5]
            })

        # 교차 키워드 조합 밀도 분석
        gaps = []
        from itertools import combinations

        if len(kw_list) >= 2:
            for kw_combo in combinations(kw_list, 2):
                combined_query = f"{kw_combo[0]} {kw_combo[1]}"
                combo_vec = model.encode([combined_query], normalize_embeddings=True)[0].tolist()
                combo_results = client.search(
                    collection_name=collection_name,
                    data=[combo_vec],
                    limit=20,
                    output_fields=["doc_id", "filename", "text", "page_num"],
                    search_params={"metric_type": "COSINE"}
                )

                if combo_results[0]:
                    combo_scores = [h.get("distance", 0) for h in combo_results[0]]
                    combo_density = sum(combo_scores[:5]) / min(5, len(combo_scores))

                    # 개별 키워드 밀도의 평균과 비교
                    individual_densities = []
                    for kd in keyword_densities:
                        if kd["keyword"] in kw_combo:
                            individual_densities.append(kd["density"])
                    avg_individual = sum(individual_densities) / len(individual_densities) if individual_densities else 0

                    # gap_score: 개별 밀도 대비 조합 밀도가 낮을수록 연구 공백
                    gap_score = max(0, avg_individual - combo_density)

                    # 관련 문서
                    unique_combo_docs = {}
                    for hit in combo_results[0]:
                        entity = hit.get("entity", {})
                        doc_id = entity.get("doc_id", "")
                        if doc_id not in unique_combo_docs:
                            unique_combo_docs[doc_id] = {
                                "doc_id": doc_id,
                                "filename": entity.get("filename", ""),
                                "score": round(hit.get("distance", 0), 4),
                                "snippet": entity.get("text", "")[:150]
                            }

                    # 잠재력 판단
                    if gap_score > 0.1:
                        potential = "높음"
                    elif gap_score > 0.05:
                        potential = "보통"
                    else:
                        potential = "낮음"

                    gaps.append({
                        "keywords": list(kw_combo),
                        "combined_query": combined_query,
                        "combo_density": round(combo_density, 4),
                        "avg_individual_density": round(avg_individual, 4),
                        "gap_score": round(gap_score, 4),
                        "potential": potential,
                        "doc_count": len(unique_combo_docs),
                        "related_docs": list(unique_combo_docs.values())[:5],
                        "description": f"'{kw_combo[0]}'와 '{kw_combo[1]}'의 교차 영역은 개별 주제(밀도 {avg_individual:.2f}) 대비 조합 밀도({combo_density:.2f})가 {'낮아' if gap_score > 0.05 else '유사하여'} {'잠재적 연구 공백' if gap_score > 0.05 else '충분히 연구된 영역'}으로 판단됩니다."
                    })
                else:
                    gaps.append({
                        "keywords": list(kw_combo),
                        "combined_query": combined_query,
                        "combo_density": 0,
                        "avg_individual_density": 0,
                        "gap_score": 1.0,
                        "potential": "높음",
                        "doc_count": 0,
                        "related_docs": [],
                        "description": f"'{kw_combo[0]}'와 '{kw_combo[1]}'의 교차 영역에 관련 문서가 전혀 없습니다. 미개척 연구 영역입니다."
                    })

        # 단일 키워드 중 밀도가 낮은 것도 gap으로 추가
        for kd in keyword_densities:
            if kd["density"] < 0.35:
                gaps.append({
                    "keywords": [kd["keyword"]],
                    "combined_query": kd["keyword"],
                    "combo_density": kd["density"],
                    "avg_individual_density": kd["density"],
                    "gap_score": round(max(0, 0.5 - kd["density"]), 4),
                    "potential": "높음" if kd["density"] < 0.2 else "보통",
                    "doc_count": kd["doc_count"],
                    "related_docs": kd["top_docs"],
                    "description": f"'{kd['keyword']}' 주제는 벡터 공간에서 밀도({kd['density']:.2f})가 낮아 관련 연구가 부족한 영역입니다."
                })

        # gap_score 역순 정렬
        gaps.sort(key=lambda x: -x["gap_score"])

        wiz.response.status(200,
            gaps=gaps,
            keyword_densities=keyword_densities,
            total_keywords=len(kw_list),
            total_gaps=len(gaps)
        )

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def generate_hypothesis():
    """가설 자동 생성 - 연구 조건 입력 → 관련 논문 검색 → 패턴 기반 가설 생성"""
    try:
        condition = wiz.request.query("condition", "")
        if not condition.strip():
            wiz.response.status(400, message="연구 조건을 입력하세요.")
            return

        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, hypotheses=[], message="컬렉션이 없습니다.")
            return

        model = _get_model(model_name)

        # Step 1: 조건 벡터화 → Milvus 검색
        condition_vec = model.encode([condition], normalize_embeddings=True)[0].tolist()
        results = client.search(
            collection_name=collection_name,
            data=[condition_vec],
            limit=30,
            output_fields=["doc_id", "filename", "chunk_index", "text", "page_num"],
            search_params={"metric_type": "COSINE"}
        )

        if not results[0]:
            wiz.response.status(200, hypotheses=[], evidence_docs=[], novel_terms=[],
                message="관련 문헌을 찾을 수 없습니다.")
            return

        # Step 2: 검색된 논문에서 공통 용어/패턴 추출
        all_texts = []
        evidence_docs = {}
        for hit in results[0]:
            entity = hit.get("entity", {})
            text = entity.get("text", "")
            all_texts.append(text)
            doc_id = entity.get("doc_id", "")
            if doc_id not in evidence_docs:
                evidence_docs[doc_id] = dict(_build_evidence_item(entity, hit.get("distance", 0)))
                evidence_docs[doc_id]["snippet"] = text[:200]

        # 공통 용어 추출
        combined_text = " ".join(all_texts)
        terms = _extract_terms_from_text(combined_text)
        condition_terms = _extract_terms_from_text(condition)

        # 조건에 없는 관련 용어 (새로운 변수 후보)
        novel_terms = []
        for term, freq in terms.most_common(30):
            if term.lower() not in condition.lower():
                novel_terms.append((term, freq))

        # Step 3: 템플릿 기반 가설 생성
        hypotheses = []

        # 조건에서 핵심 키워드 추출
        condition_keywords = [t for t, f in condition_terms.most_common(5)]
        if not condition_keywords:
            # 조건 텍스트에서 PLASMA_TERMS가 없으면 원문 사용
            condition_keywords = [condition[:30]]

        main_kw = condition_keywords[0] if condition_keywords else condition[:20]

        # 가설 템플릿들
        templates = [
            {
                "type": "parameter_optimization",
                "type_label": "파라미터 최적화",
                "title_template": "{main_kw}에서 {novel_term}의 최적 조건 탐색",
                "desc_template": "기존 문헌 분석 결과, {main_kw} 공정에서 {novel_term}이(가) 중요한 변수로 확인되었으나, 최적 조건에 대한 체계적 연구가 부족합니다. {novel_term}을(를) 변수로 설정한 파라미터 최적화 실험이 필요합니다.",
                "experiment": "{novel_term}을(를) 다단계로 변화시키며 {main_kw} 성능 지표를 측정하는 DOE(실험 설계) 기반 연구를 제안합니다.",
                "min_terms": 1
            },
            {
                "type": "mechanism_study",
                "type_label": "메커니즘 규명",
                "title_template": "{main_kw} 과정에서 {novel_term}의 메커니즘 규명",
                "desc_template": "관련 문헌에서 {novel_term}이(가) {main_kw}에 영향을 미치는 것으로 보고되었으나, 정확한 물리적/화학적 메커니즘은 아직 명확하지 않습니다. 분광학적 진단과 시뮬레이션을 통한 메커니즘 연구가 제안됩니다.",
                "experiment": "OES, Langmuir probe 등 진단 장비를 활용한 {novel_term} 기반 {main_kw} 메커니즘 분석을 제안합니다.",
                "min_terms": 1
            },
            {
                "type": "cross_domain",
                "type_label": "교차 도메인",
                "title_template": "{novel_term1}과 {novel_term2}의 상호작용이 {main_kw}에 미치는 영향",
                "desc_template": "{novel_term1}과(와) {novel_term2}은(는) 각각 {main_kw}와 관련된 중요한 변수이지만, 두 변수의 상호작용 효과에 대한 연구는 제한적입니다. 복합 효과 분석이 새로운 연구 방향이 될 수 있습니다.",
                "experiment": "2-factor factorial design으로 {novel_term1}과 {novel_term2}의 상호작용 효과를 분석하는 실험을 제안합니다.",
                "min_terms": 2
            },
            {
                "type": "novel_application",
                "type_label": "신규 응용",
                "title_template": "{main_kw} 기술의 {novel_term} 분야 적용 가능성",
                "desc_template": "기존 {main_kw} 연구는 특정 분야에 집중되어 있으나, {novel_term} 분야로의 확장 적용이 유망합니다. 관련 문헌에서 간접적 연관성이 확인되었으며, 직접적인 적용 연구가 필요합니다.",
                "experiment": "{main_kw} 기반 공정을 {novel_term} 소재/응용에 적용한 pilot 실험을 제안합니다.",
                "min_terms": 1
            },
            {
                "type": "prediction_model",
                "type_label": "예측 모델",
                "title_template": "{main_kw} 결과 예측을 위한 {novel_term} 기반 모델링",
                "desc_template": "{main_kw} 공정의 결과를 {novel_term} 데이터를 활용하여 예측하는 모델을 구축할 수 있습니다. 관련 문헌의 실험 데이터를 기반으로 머신러닝/통계적 모델 개발이 가능합니다.",
                "experiment": "기존 실험 데이터 수집 → {novel_term} 기반 feature engineering → ML 모델 훈련 및 검증 파이프라인을 제안합니다.",
                "min_terms": 1
            }
        ]

        evidence_list = list(evidence_docs.values())[:10]

        for i, template in enumerate(templates):
            if template["min_terms"] > len(novel_terms):
                continue

            if template["min_terms"] == 2 and len(novel_terms) >= 2:
                nt1 = novel_terms[0][0]
                nt2 = novel_terms[1][0]
                title = template["title_template"].format(main_kw=main_kw, novel_term1=nt1, novel_term2=nt2)
                desc = template["desc_template"].format(main_kw=main_kw, novel_term1=nt1, novel_term2=nt2)
                exp = template["experiment"].format(main_kw=main_kw, novel_term1=nt1, novel_term2=nt2)
            else:
                idx = min(i, len(novel_terms) - 1)
                nt = novel_terms[idx][0]
                title = template["title_template"].format(main_kw=main_kw, novel_term=nt)
                desc = template["desc_template"].format(main_kw=main_kw, novel_term=nt)
                exp = template["experiment"].format(main_kw=main_kw, novel_term=nt)

            # 가설 벡터 → 관련도 계산
            hyp_vec = model.encode([title], normalize_embeddings=True)[0].tolist()
            hyp_results = client.search(
                collection_name=collection_name,
                data=[hyp_vec],
                limit=3,
                output_fields=["doc_id", "filename", "text", "page_num"],
                search_params={"metric_type": "COSINE"}
            )

            hyp_evidence = []
            confidence = 0
            if hyp_results[0]:
                confidence = hyp_results[0][0].get("distance", 0)
                for h in hyp_results[0]:
                    e = h.get("entity", {})
                    hyp_evidence.append(_build_evidence_item(e, h.get("distance", 0)))

            hypotheses.append({
                "type": template["type"],
                "type_label": template["type_label"],
                "title": title,
                "description": desc,
                "experiment_design": exp,
                "confidence": round(confidence, 4),
                "evidence": hyp_evidence,
                "novel_terms": [nt for nt, _ in novel_terms[:3]]
            })

        # 신뢰도 역순 정렬
        hypotheses.sort(key=lambda x: -x["confidence"])

        wiz.response.status(200,
            condition=condition,
            hypotheses=hypotheses,
            total=len(hypotheses),
            evidence_docs=evidence_list,
            novel_terms=[{"term": t, "frequency": f} for t, f in novel_terms[:10]]
        )

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# 논문 추천 (recommend)
# ==============================================================================
def recommend_papers():
    """관심 분야 기반 논문 추천 — 컬렉션 벡터 검색으로 유사 문헌 반환"""
    try:
        interests = wiz.request.query("interests", "")
        collection_name, _model_name = _resolve_collection_and_model()

        if not interests.strip():
            wiz.response.status(400, message="관심 분야를 입력하세요.")

        papers = _recommend_papers_data(interests=interests, collection_name=collection_name)
        wiz.response.status(200, papers)

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# 제안서 생성 (proposal)
# ==============================================================================
def generate_proposal():
    """연구 제안서 초안 생성 — 벡터 검색으로 관련 문헌을 찾고 구조화된 제안서 생성"""
    try:
        title = wiz.request.query("title", "")
        objective = wiz.request.query("objective", "")
        keywords = wiz.request.query("keywords", "")
        collection_name, model_name = _resolve_collection_and_model()

        if not title.strip():
            wiz.response.status(400, message="연구 제목을 입력하세요.")

        client = _get_client()
        model = _get_model(model_name)

        # 키워드 기반으로 관련 문헌 검색
        search_text = f"{title} {objective} {keywords}"
        query_vec = model.encode([search_text], normalize_embeddings=True)[0].tolist()

        references = []
        context_texts = []
        reference_details = []

        if client.has_collection(collection_name):
            results = client.search(
                collection_name=collection_name,
                data=[query_vec],
                limit=8,
                output_fields=["doc_id", "filename", "chunk_index", "text", "page_num"],
                search_params={"metric_type": "COSINE"}
            )

            seen_docs = set()
            for hit in results[0]:
                entity = hit.get("entity", {})
                doc_id = entity.get("doc_id", "")
                if doc_id in seen_docs:
                    continue
                seen_docs.add(doc_id)
                ref_title = entity.get("filename", "") or doc_id or "Unknown"
                ref_str = ref_title
                references.append(ref_str)
                context_texts.append((entity.get("text", "") or "")[:300])
                reference_details.append(_build_evidence_item(entity, hit.get("distance", 0)))

        # 키워드 처리
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        kw_str = ", ".join(kw_list) if kw_list else "플라즈마 공정"

        # 관련 문헌에서 핵심 용어 추출
        all_context = " ".join(context_texts)
        domain_counter = _extract_terms_from_text(all_context)
        top_terms = [t for t, _ in domain_counter.most_common(10)]
        terms_str = ", ".join(top_terms[:5]) if top_terms else kw_str

        # 구조화된 제안서 생성
        obj_text = f" {objective}" if objective else ""
        ref_count = len(references)

        proposal = {
            "title": title,
            "background": (
                f"본 연구는 '{title}'에 관한 것으로, {kw_str} 분야의 최근 연구 동향을 기반으로 합니다.\n\n"
                f"관련 문헌 {ref_count}편을 분석한 결과, 해당 분야에서 {terms_str} 등의 핵심 주제가 활발히 "
                f"연구되고 있으며, 추가적인 연구가 필요한 것으로 판단됩니다.\n\n"
                f"특히, 기존 연구에서는 개별 파라미터의 영향에 초점을 맞추었으나, "
                f"복합적인 상호작용 효과에 대한 체계적인 연구는 부족한 실정입니다."
                f"{obj_text}"
            ),
            "objective": (
                f"본 연구의 주요 목표는 다음과 같습니다:\n\n"
                f"1) {kw_str} 관련 핵심 파라미터의 체계적 규명\n"
                f"2) 공정 조건 최적화를 통한 성능 향상 방안 도출\n"
                f"3) 실험적 검증과 이론적 모델링의 상호 보완적 분석\n"
                f"4) 재현 가능한 표준 공정 조건 확립"
            ),
            "methodology": (
                f"1단계: 문헌 조사 및 예비 실험\n"
                f"  - {kw_str} 관련 국내외 문헌 심층 분석 (참고문헌 {ref_count}편 포함)\n"
                f"  - 주요 공정 파라미터 선정 및 실험 범위 결정\n\n"
                f"2단계: 체계적 실험 설계 (DOE)\n"
                f"  - 요인 배치법을 활용한 실험 설계\n"
                f"  - {terms_str} 등 핵심 변수의 주효과 및 교호작용 분석\n\n"
                f"3단계: 데이터 분석 및 모델링\n"
                f"  - 통계적 유의성 검정 (ANOVA, 회귀분석)\n"
                f"  - 반응표면분석법(RSM)을 통한 최적 조건 도출\n"
                f"  - 물리적 메커니즘 기반 해석\n\n"
                f"4단계: 검증 및 응용\n"
                f"  - 최적 조건 재현성 검증 (3회 이상 반복)\n"
                f"  - 스케일업 가능성 평가\n"
                f"  - 결과 해석 및 학술 논문 작성"
            ),
            "expected_results": (
                f"본 연구를 통해 다음과 같은 성과를 기대합니다:\n\n"
                f"• {kw_str} 분야에서의 새로운 과학적 지견 확보\n"
                f"• 핵심 공정 파라미터 간 상호작용 메커니즘 규명\n"
                f"• 관련 공정의 효율성 및 재현성 향상\n"
                f"• 국내외 학술지 논문 1~2편 게재\n"
                f"• 관련 특허 출원 검토"
            ),
            "references": references,
            "reference_details": reference_details,
            "keywords": kw_list if kw_list else [kw_str],
            "related_terms": top_terms[:8]
        }

        wiz.response.status(200, proposal)

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# 특허 검색 (patent)
# ==============================================================================
def search_patents():
    """KIPRIS Plus API 기반 특허 검색"""
    try:
        query = wiz.request.query("query", "")

        if not query.strip():
            wiz.response.status(400, message="검색어를 입력하세요.")
        patents = _kipris_plus_patent_search(query.strip())
        wiz.response.status(200, patents=patents, source="KIPRIS Plus")

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(502, message=str(e))
