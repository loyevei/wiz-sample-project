import os
import sys
import json
import traceback
import re
import numpy as np
from collections import Counter, defaultdict

from sentence_transformers import SentenceTransformer
from pymilvus import MilvusClient
import season.lib.exception

# ==============================================================================
# 설정
# ==============================================================================
MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
COLLECTION_META_PATH = "/opt/app/data/collection_meta.json"
PARAM_DB_DIR = "/opt/app/data"
DEFAULT_COLLECTION = "plasma_papers"

MODEL_REGISTRY = {
    "snunlp/KR-SBERT-V40K-klueNLI-augSTS": {"dim": 768, "short_name": "KR-SBERT"},
    "BM-K/KoSimCSE-roberta-multitask": {"dim": 768, "short_name": "KoSimCSE"},
    "jhgan/ko-sroberta-multitask": {"dim": 768, "short_name": "ko-sroberta"},
    "sentence-transformers/all-MiniLM-L6-v2": {"dim": 384, "short_name": "MiniLM-L6"},
    "sentence-transformers/all-mpnet-base-v2": {"dim": 768, "short_name": "MPNet"},
    "BAAI/bge-base-en-v1.5": {"dim": 768, "short_name": "BGE-base"},
    "intfloat/multilingual-e5-large": {"dim": 1024, "short_name": "mE5-Large"},
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": {"dim": 384, "short_name": "MiniLM-L12"}
}
DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

# ==============================================================================
# 파라미터 추출 패턴 (FN-0001)
# ==============================================================================
PARAM_PATTERNS = {
    "pressure": {
        "label": "압력 (Pressure)", "category": "condition", "base_unit": "mTorr",
        "patterns": [
            (r'(\d+\.?\d*)\s*mTorr', "mTorr"),
            (r'(\d+\.?\d*)\s*Torr\b', "Torr"),
            (r'(\d+\.?\d*)\s*Pa\b', "Pa"),
            (r'(\d+\.?\d*)\s*kPa\b', "kPa"),
            (r'(\d+\.?\d*)\s*mbar\b', "mbar"),
        ]
    },
    "rf_power": {
        "label": "RF 전력 (Power)", "category": "condition", "base_unit": "W",
        "patterns": [
            (r'(\d+\.?\d*)\s*kW\b', "kW"),
            (r'(\d+\.?\d*)\s*W\b', "W"),
        ]
    },
    "gas_flow": {
        "label": "가스 유량 (Gas Flow)", "category": "condition", "base_unit": "sccm",
        "patterns": [
            (r'(\d+\.?\d*)\s*sccm\b', "sccm"),
            (r'(\d+\.?\d*)\s*slm\b', "slm"),
        ]
    },
    "temperature": {
        "label": "온도 (Temperature)", "category": "condition", "base_unit": "°C",
        "patterns": [
            (r'(\d+\.?\d*)\s*°C', "°C"),
            (r'(\d+\.?\d*)\s*℃', "°C"),
            (r'(\d+\.?\d*)\s*K\b', "K"),
        ]
    },
    "frequency": {
        "label": "주파수 (Frequency)", "category": "condition", "base_unit": "MHz",
        "patterns": [
            (r'(\d+\.?\d*)\s*MHz\b', "MHz"),
            (r'(\d+\.?\d*)\s*kHz\b', "kHz"),
            (r'(\d+\.?\d*)\s*GHz\b', "GHz"),
        ]
    },
    "bias_voltage": {
        "label": "바이어스 전압 (Bias)", "category": "condition", "base_unit": "V",
        "patterns": [
            (r'(?:bias|Vdc|Vpp|self[- ]bias)\s*(?:voltage)?\s*(?:of|=|:|\s)*[-\u2212]?\s*(\d+\.?\d*)\s*V\b', "V"),
            (r'[-\u2212](\d+\.?\d*)\s*V\b', "V"),
        ]
    },
    "electrode_gap": {
        "label": "전극 간격 (Gap)", "category": "condition", "base_unit": "mm",
        "patterns": [
            (r'(?:gap|distance|spacing)\s*(?:of|=|:|\s)+(\d+\.?\d*)\s*(mm|cm)\b', None),
            (r'(\d+\.?\d*)\s*(mm|cm)\s*(?:gap|distance|spacing)', None),
        ]
    },
    "etch_rate": {
        "label": "식각 속도 (Etch Rate)", "category": "result", "base_unit": "nm/min",
        "patterns": [
            (r'(?:etch(?:ing)?)\s*(?:rate|speed)?\s*(?:of|=|:|was|is|\s)*(\d+\.?\d*)\s*(nm/min|Å/min|μm/min|nm/s)', None),
            (r'(\d+\.?\d*)\s*(nm/min|Å/min|μm/min|nm/s)\s*(?:etch)', None),
        ]
    },
    "deposition_rate": {
        "label": "증착 속도 (Deposition Rate)", "category": "result", "base_unit": "nm/min",
        "patterns": [
            (r'(?:deposition|deposit(?:ed)?|growth)\s*(?:rate|speed)?\s*(?:of|=|:|was|is|\s)*(\d+\.?\d*)\s*(nm/min|Å/min|nm/s|Å/s)', None),
            (r'(\d+\.?\d*)\s*(nm/min|Å/min|nm/s|Å/s)\s*(?:deposition|growth)', None),
        ]
    },
    "uniformity": {
        "label": "균일도 (Uniformity)", "category": "result", "base_unit": "%",
        "patterns": [
            (r'(?:uniformity)\s*(?:of|=|:|\s)*[±]?\s*(\d+\.?\d*)\s*(%)', None),
            (r'[±]\s*(\d+\.?\d*)\s*(%)\s*(?:uniformity)', None),
        ]
    },
    "selectivity": {
        "label": "선택비 (Selectivity)", "category": "result", "base_unit": ":1",
        "patterns": [
            (r'(?:selectivity)\s*(?:of|=|:|\s)*(?:about|approximately|~)?\s*(\d+\.?\d*)', ":1"),
        ]
    },
}

UNIT_CONVERSIONS = {
    ("Torr", "mTorr"): ("multiply", 1000.0),
    ("Pa", "mTorr"): ("multiply", 7.50062),
    ("kPa", "mTorr"): ("multiply", 7500.62),
    ("mbar", "mTorr"): ("multiply", 750.062),
    ("kW", "W"): ("multiply", 1000.0),
    ("slm", "sccm"): ("multiply", 1000.0),
    ("K", "°C"): ("add", -273.15),
    ("GHz", "MHz"): ("multiply", 1000.0),
    ("kHz", "MHz"): ("multiply", 0.001),
    ("Å/min", "nm/min"): ("multiply", 0.1),
    ("μm/min", "nm/min"): ("multiply", 1000.0),
    ("nm/s", "nm/min"): ("multiply", 60.0),
    ("Å/s", "nm/min"): ("multiply", 6.0),
    ("cm", "mm"): ("multiply", 10.0),
}

GAS_SPECIES = [
    "Ar", "O2", "N2", "H2", "He", "Ne", "Kr", "Xe",
    "CF4", "C4F8", "C4F6", "CHF3", "CH2F2", "C2F6", "NF3",
    "SF6", "Cl2", "BCl3", "HBr", "SiH4", "SiCl4",
    "NH3", "N2O", "CO2", "CO", "CH4", "C2H2",
    "TiCl4", "WF6", "TEOS", "TMA", "TMGa",
]

# ==============================================================================
# 인프라 함수
# ==============================================================================
def _load_collection_meta():
    if os.path.exists(COLLECTION_META_PATH):
        try:
            with open(COLLECTION_META_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _get_collection_model(collection_name):
    meta = _load_collection_meta()
    return meta.get(collection_name, {}).get("model", DEFAULT_MODEL)

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
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        sys._milvus_client = MilvusClient(uri=db_path)
    return sys._milvus_client

def _resolve_collection_and_model():
    collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip()
    if not collection_name:
        collection_name = DEFAULT_COLLECTION
    model_name = _get_collection_model(collection_name)
    return collection_name, model_name

# ==============================================================================
# 파라미터 추출 헬퍼
# ==============================================================================
def _convert_to_base(value, unit, base_unit):
    if unit == base_unit:
        return value
    key = (unit, base_unit)
    if key in UNIT_CONVERSIONS:
        op, factor = UNIT_CONVERSIONS[key]
        if op == "add":
            return value + factor
        return value * factor
    return value

def _extract_parameters_from_text(text):
    """텍스트에서 플라즈마 공정 파라미터 추출"""
    extracted = {}
    for param_key, pinfo in PARAM_PATTERNS.items():
        values = []
        for pattern, norm_unit in pinfo["patterns"]:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    val = float(m.group(1))
                    if val <= 0 or val >= 1e8:
                        continue
                    if norm_unit:
                        unit = norm_unit
                    else:
                        unit = m.group(2) if m.lastindex >= 2 else pinfo["base_unit"]
                    base_val = _convert_to_base(val, unit, pinfo["base_unit"])
                    ctx_s = max(0, m.start() - 50)
                    ctx_e = min(len(text), m.end() + 50)
                    values.append({
                        "raw_value": val, "raw_unit": unit,
                        "value": round(base_val, 4),
                        "unit": pinfo["base_unit"],
                        "context": text[ctx_s:ctx_e].strip()
                    })
                except (ValueError, IndexError):
                    pass
        if values:
            seen = set()
            unique = []
            for v in values:
                k = f"{v['value']}_{v['unit']}"
                if k not in seen:
                    seen.add(k)
                    unique.append(v)
            extracted[param_key] = {
                "label": pinfo["label"],
                "category": pinfo["category"],
                "values": unique
            }
    # 가스 종류 추출
    found_gases = []
    for gas in GAS_SPECIES:
        if re.search(r'\b' + re.escape(gas) + r'\b', text):
            found_gases.append(gas)
    if found_gases:
        extracted["gas_species"] = {
            "label": "가스 종류 (Gas Species)",
            "category": "condition",
            "values": [{"value": g, "unit": "", "context": ""} for g in found_gases]
        }
    return extracted

def _get_param_db_path(collection_name):
    return os.path.join(PARAM_DB_DIR, f"param_db_{collection_name}.json")

def _load_param_db(collection_name):
    path = _get_param_db_path(collection_name)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def _save_param_db(collection_name, data):
    path = _get_param_db_path(collection_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _compute_param_summary(param_db):
    """파라미터 DB 전체 통계 요약"""
    summary = {}
    all_params = set()
    for doc_id, doc_info in param_db.get("documents", {}).items():
        for pk in doc_info.get("params", {}).keys():
            all_params.add(pk)

    for pk in all_params:
        if pk == "gas_species":
            gas_counter = Counter()
            dc = 0
            for doc_id, doc_info in param_db.get("documents", {}).items():
                if "gas_species" in doc_info.get("params", {}):
                    dc += 1
                    for v in doc_info["params"]["gas_species"].get("values", []):
                        gas_counter[v.get("value", "")] += 1
            summary["gas_species"] = {
                "label": "가스 종류 (Gas Species)", "category": "condition",
                "unit": "", "count": sum(gas_counter.values()), "doc_count": dc,
                "distribution": dict(gas_counter.most_common(20))
            }
            continue

        all_vals = []
        dc = 0
        for doc_id, doc_info in param_db.get("documents", {}).items():
            if pk in doc_info.get("params", {}):
                dc += 1
                for v in doc_info["params"][pk].get("values", []):
                    if isinstance(v.get("value"), (int, float)):
                        all_vals.append(v["value"])
        if all_vals:
            arr = np.array(all_vals)
            pinfo = PARAM_PATTERNS.get(pk, {})
            summary[pk] = {
                "label": pinfo.get("label", pk),
                "category": pinfo.get("category", ""),
                "unit": pinfo.get("base_unit", ""),
                "count": len(all_vals),
                "doc_count": dc,
                "min": round(float(arr.min()), 4),
                "max": round(float(arr.max()), 4),
                "mean": round(float(arr.mean()), 4),
                "std": round(float(arr.std()), 4),
                "median": round(float(np.median(arr)), 4),
            }
    return summary

def _calc_condition_similarity(input_conditions, doc_params):
    """입력 조건과 문서 조건 간 유사도 (0~1)"""
    if not input_conditions:
        return 0
    total_sim = 0.0
    matched = 0
    for key, inp_val in input_conditions.items():
        if key in doc_params:
            doc_vals = [v["value"] for v in doc_params[key].get("values", [])
                        if isinstance(v.get("value"), (int, float))]
            if doc_vals:
                closest = min(doc_vals, key=lambda x: abs(x - inp_val))
                diff = abs(closest - inp_val)
                scale = max(abs(inp_val), abs(closest), 1.0)
                sim = max(0.0, 1.0 - diff / scale)
                total_sim += sim
                matched += 1
    if matched == 0:
        return 0
    return total_sim / len(input_conditions)

def _build_feature_matrix(param_db, target_param):
    """파라미터 DB → 회귀용 특징 행렬 구축"""
    cond_keys = [k for k, v in PARAM_PATTERNS.items()
                 if v.get("category") == "condition" and k != "gas_species"]
    X_rows, y_vals, doc_ids = [], [], []

    for doc_id, doc_info in param_db.get("documents", {}).items():
        params = doc_info.get("params", {})
        if target_param not in params:
            continue
        tvs = [v["value"] for v in params[target_param].get("values", [])
               if isinstance(v.get("value"), (int, float))]
        if not tvs:
            continue
        feat = []
        has_cond = False
        for ck in cond_keys:
            if ck in params:
                cvs = [v["value"] for v in params[ck].get("values", [])
                       if isinstance(v.get("value"), (int, float))]
                if cvs:
                    feat.append(float(np.mean(cvs)))
                    has_cond = True
                    continue
            feat.append(np.nan)
        if has_cond:
            for tv in tvs:
                X_rows.append(feat.copy())
                y_vals.append(tv)
                doc_ids.append(doc_id)

    if not X_rows:
        return np.array([]), np.array([]), cond_keys, []

    X = np.array(X_rows)
    y = np.array(y_vals)
    col_means = np.nanmean(X, axis=0)
    for i in range(X.shape[1]):
        mask = np.isnan(X[:, i])
        X[mask, i] = col_means[i] if not np.isnan(col_means[i]) else 0.0
    return X, y, cond_keys, doc_ids

# ==============================================================================
# 기존 엔드포인트
# ==============================================================================
def collections():
    """사용 가능한 컬렉션 목록"""
    try:
        client = _get_client()
        col_names = client.list_collections()
        meta = _load_collection_meta()
        result = []
        for name in col_names:
            info = meta.get(name, {})
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
                    dim_to_model = {}
                    for mname, minfo in MODEL_REGISTRY.items():
                        d = minfo["dim"]
                        if d not in dim_to_model:
                            dim_to_model[d] = mname
                    inferred = dim_to_model.get(dim, DEFAULT_MODEL)
                    inferred_info = MODEL_REGISTRY.get(inferred, {})
                    info = {"model": inferred, "dim": dim,
                            "short_name": inferred_info.get("short_name", inferred)}
                except Exception:
                    pass
            result.append({
                "name": name,
                "model": info.get("model", DEFAULT_MODEL),
                "short_name": info.get("short_name", "Unknown"),
                "dim": info.get("dim", 768)
            })
        wiz.response.status(200, collections=result)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        wiz.response.status(200, collections=[])


def predict():
    """공정 조건 입력 → 유사 문헌에서 결과 예측/추천"""
    try:
        process_type = wiz.request.query("process_type", "")
        gas_type = wiz.request.query("gas_type", "")
        pressure = wiz.request.query("pressure", "")
        power = wiz.request.query("power", "")
        temperature = wiz.request.query("temperature", "")
        substrate = wiz.request.query("substrate", "")
        target_property = wiz.request.query("target_property", "")

        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, predictions=[], message="컬렉션이 없습니다.")
            return

        query_parts = []
        if process_type:
            query_parts.append(f"{process_type} 공정")
        if gas_type:
            query_parts.append(f"{gas_type} 가스")
        if pressure:
            query_parts.append(f"압력 {pressure}")
        if power:
            query_parts.append(f"전력 {power}")
        if temperature:
            query_parts.append(f"온도 {temperature}")
        if substrate:
            query_parts.append(f"{substrate} 기판")
        if target_property:
            query_parts.append(f"{target_property}")

        if not query_parts:
            wiz.response.status(400, message="최소 하나의 공정 조건을 입력하세요.")
            return

        query_text = " ".join(query_parts)
        model = _get_model(model_name)
        query_vec = model.encode([query_text], normalize_embeddings=True)[0].tolist()

        search_results = client.search(
            collection_name=collection_name,
            data=[query_vec], limit=30,
            output_fields=["doc_id", "filename", "chunk_index", "text"],
            search_params={"metric_type": "COSINE"}
        )

        predictions = []
        seen_docs = set()
        for hit in search_results[0]:
            entity = hit.get("entity", {})
            doc_id = entity.get("doc_id", "")
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)
            text = entity.get("text", "")
            params = _extract_parameters_from_text(text)
            extracted_values = []
            for pk, pdata in params.items():
                if pk == "gas_species":
                    continue
                for v in pdata.get("values", [])[:3]:
                    extracted_values.append(f"{v['raw_value']} {v['raw_unit']}")

            predictions.append({
                "doc_id": doc_id,
                "filename": entity.get("filename", ""),
                "chunk_index": entity.get("chunk_index", 0),
                "relevance": round(hit.get("distance", 0), 4),
                "text": text[:400],
                "extracted_values": extracted_values[:8],
                "params": {k: v for k, v in params.items() if k != "gas_species"}
            })
            if len(predictions) >= 10:
                break

        wiz.response.status(200,
            query=query_text,
            predictions=predictions,
            total_searched=len(search_results[0]))
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def analyze_params():
    """특정 공정 파라미터에 대한 문헌 기반 분석"""
    try:
        param_name = wiz.request.query("param_name", "")
        if not param_name:
            wiz.response.status(400, message="파라미터명을 입력하세요.")
            return

        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        model = _get_model(model_name)
        if not client.has_collection(collection_name):
            wiz.response.status(200, analysis=[], message="컬렉션이 없습니다.")
            return

        queries = [
            f"{param_name} effect",
            f"{param_name} increase",
            f"{param_name} decrease",
            f"{param_name} optimal"
        ]

        all_results = []
        for q in queries:
            qvec = model.encode([q], normalize_embeddings=True)[0].tolist()
            results = client.search(
                collection_name=collection_name,
                data=[qvec], limit=10,
                output_fields=["doc_id", "filename", "text"],
                search_params={"metric_type": "COSINE"}
            )
            for hit in results[0]:
                entity = hit.get("entity", {})
                all_results.append({
                    "query": q,
                    "doc_id": entity.get("doc_id", ""),
                    "filename": entity.get("filename", ""),
                    "text": entity.get("text", "")[:300],
                    "score": round(hit.get("distance", 0), 4)
                })

        seen = set()
        unique = []
        for r in sorted(all_results, key=lambda x: x["score"], reverse=True):
            k = f"{r['doc_id']}_{r['text'][:50]}"
            if k not in seen:
                seen.add(k)
                unique.append(r)
            if len(unique) >= 15:
                break

        wiz.response.status(200, param_name=param_name, analysis=unique)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def stats():
    """컬렉션 통계"""
    try:
        collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip()
        if not collection_name:
            collection_name = DEFAULT_COLLECTION
        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, total_docs=0, total_chunks=0, has_param_db=False)
            return

        stats_info = client.get_collection_stats(collection_name)
        total_chunks = stats_info.get("row_count", 0)
        total_docs = 0
        if total_chunks > 0:
            try:
                results = client.query(
                    collection_name=collection_name,
                    filter="chunk_index == 0",
                    output_fields=["doc_id"]
                )
                total_docs = len(results)
            except Exception:
                pass

        has_param_db = _load_param_db(collection_name) is not None

        wiz.response.status(200,
            total_docs=total_docs,
            total_chunks=total_chunks,
            has_param_db=has_param_db)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        wiz.response.status(200, total_docs=0, total_chunks=0, has_param_db=False, error=str(e))


# ==============================================================================
# FN-0001: Parameter Extraction Pipeline
# ==============================================================================
def extract_params():
    """컬렉션 내 문서에서 공정 파라미터 자동 추출 → Structured DB 구축"""
    try:
        collection_name, model_name = _resolve_collection_and_model()
        force = wiz.request.query("force", "false").lower() == "true"

        if not force:
            cached = _load_param_db(collection_name)
            if cached:
                summary = _compute_param_summary(cached)
                wiz.response.status(200,
                    param_db=cached, summary=summary,
                    cached=True, total_docs=len(cached.get("documents", {})))
                return

        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, param_db={}, summary={},
                message="컬렉션이 없습니다. 먼저 PDF를 임베딩하세요.")
            return

        # 전체 청크 조회
        all_chunks = client.query(
            collection_name=collection_name,
            filter="chunk_index >= 0",
            output_fields=["doc_id", "filename", "chunk_index", "text"],
            limit=10000
        )

        # 문서별 파라미터 추출
        doc_data = {}
        for chunk in all_chunks:
            doc_id = chunk.get("doc_id", "")
            if doc_id not in doc_data:
                doc_data[doc_id] = {"filename": "", "chunks": 0, "params": {}}
            doc_data[doc_id]["filename"] = chunk.get("filename", "")
            doc_data[doc_id]["chunks"] += 1

            extracted = _extract_parameters_from_text(chunk.get("text", ""))
            for pk, pinfo in extracted.items():
                if pk not in doc_data[doc_id]["params"]:
                    doc_data[doc_id]["params"][pk] = {
                        "label": pinfo["label"],
                        "category": pinfo["category"],
                        "values": []
                    }
                doc_data[doc_id]["params"][pk]["values"].extend(pinfo["values"])

        # 중복 제거
        documents = {}
        for doc_id, dinfo in doc_data.items():
            params = {}
            for pk, pdata in dinfo["params"].items():
                seen = set()
                unique_vals = []
                for v in pdata["values"]:
                    if pk == "gas_species":
                        k = v.get("value", "")
                    else:
                        k = f"{v.get('value', '')}_{v.get('unit', '')}"
                    if k not in seen:
                        seen.add(k)
                        unique_vals.append(v)
                params[pk] = {
                    "label": pdata["label"],
                    "category": pdata["category"],
                    "values": unique_vals
                }
            documents[doc_id] = {
                "filename": dinfo["filename"],
                "chunks": dinfo["chunks"],
                "params": params
            }

        param_db = {
            "collection": collection_name,
            "model": model_name,
            "total_docs": len(documents),
            "total_chunks": len(all_chunks),
            "documents": documents
        }

        _save_param_db(collection_name, param_db)
        summary = _compute_param_summary(param_db)
        wiz.response.status(200,
            param_db=param_db, summary=summary,
            cached=False, total_docs=len(documents))
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def param_database():
    """추출된 파라미터 DB 조회 (필터/정렬 지원)"""
    try:
        collection_name, _ = _resolve_collection_and_model()
        param_filter = wiz.request.query("param_filter", "")
        sort_by = wiz.request.query("sort_by", "")

        cached = _load_param_db(collection_name)
        if not cached:
            wiz.response.status(200,
                documents=[], summary={},
                message="먼저 파라미터 추출을 실행하세요.")
            return

        documents = cached.get("documents", {})

        if param_filter:
            filtered = {}
            for doc_id, doc_info in documents.items():
                if param_filter in doc_info.get("params", {}):
                    filtered[doc_id] = doc_info
            documents = filtered

        doc_list = []
        for doc_id, doc_info in documents.items():
            entry = {"doc_id": doc_id, **doc_info}
            if sort_by and sort_by in doc_info.get("params", {}):
                vals = [v["value"] for v in doc_info["params"][sort_by].get("values", [])
                        if isinstance(v.get("value"), (int, float))]
                entry["sort_value"] = float(np.mean(vals)) if vals else 0
            else:
                entry["sort_value"] = 0
            doc_list.append(entry)

        if sort_by:
            doc_list.sort(key=lambda x: x["sort_value"], reverse=True)

        summary = _compute_param_summary(cached)
        wiz.response.status(200,
            documents=doc_list, summary=summary,
            total=len(doc_list))
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# FN-0003: Inverse Condition Finder
# ==============================================================================
def inverse_search():
    """목표 결과 텍스트 → 유사 벡터 탐색 → 공정 조건 범위 제안"""
    try:
        target_text = wiz.request.query("target_text", "")
        if not target_text:
            wiz.response.status(400, message="목표 결과를 입력하세요.")
            return

        collection_name, model_name = _resolve_collection_and_model()
        top_k = int(wiz.request.query("top_k", "30"))

        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, suggested_conditions={}, evidence=[],
                message="컬렉션이 없습니다.")
            return

        model = _get_model(model_name)
        query_vec = model.encode([target_text], normalize_embeddings=True)[0].tolist()

        search_results = client.search(
            collection_name=collection_name,
            data=[query_vec], limit=top_k,
            output_fields=["doc_id", "filename", "chunk_index", "text"],
            search_params={"metric_type": "COSINE"}
        )

        condition_data = defaultdict(list)
        evidence = []
        seen_docs = set()
        all_scores = []

        for hit in search_results[0]:
            entity = hit.get("entity", {})
            doc_id = entity.get("doc_id", "")
            score = hit.get("distance", 0)
            text = entity.get("text", "")
            all_scores.append(score)

            params = _extract_parameters_from_text(text)

            for pk, pinfo in params.items():
                if pinfo["category"] == "condition" and pk != "gas_species":
                    for v in pinfo["values"]:
                        condition_data[pk].append({
                            "value": v["value"], "unit": v["unit"],
                            "score": score, "doc_id": doc_id
                        })
                elif pk == "gas_species":
                    for v in pinfo["values"]:
                        condition_data["gas_species"].append({
                            "value": v["value"], "score": score, "doc_id": doc_id
                        })

            if doc_id not in seen_docs:
                seen_docs.add(doc_id)
                evidence.append({
                    "doc_id": doc_id,
                    "filename": entity.get("filename", ""),
                    "chunk_index": entity.get("chunk_index", 0),
                    "relevance": round(score, 4),
                    "text": text[:300],
                })

        # 조건 범위 계산
        suggested_conditions = {}
        for pk, entries in condition_data.items():
            if pk == "gas_species":
                gas_counter = Counter()
                for e in entries:
                    gas_counter[e["value"]] += 1
                suggested_conditions["gas_species"] = {
                    "label": "가스 종류 (Gas Species)",
                    "recommended": [g for g, _ in gas_counter.most_common(5)],
                    "distribution": dict(gas_counter),
                    "sample_count": len(entries)
                }
                continue

            values = [e["value"] for e in entries]
            scores = [e["score"] for e in entries]
            arr = np.array(values)
            warr = np.array(scores)

            if len(arr) == 0:
                continue

            w_mean = float(np.average(arr, weights=warr)) if warr.sum() > 0 else float(arr.mean())
            w_std = float(np.sqrt(np.average((arr - w_mean)**2, weights=warr))) if len(arr) > 1 else 0.0

            pinfo = PARAM_PATTERNS.get(pk, {})
            suggested_conditions[pk] = {
                "label": pinfo.get("label", pk),
                "unit": pinfo.get("base_unit", ""),
                "min": round(float(arr.min()), 4),
                "max": round(float(arr.max()), 4),
                "mean": round(w_mean, 4),
                "std": round(w_std, 4),
                "recommended_range": [
                    round(float(max(arr.min(), w_mean - w_std)), 4),
                    round(float(min(arr.max(), w_mean + w_std)), 4)
                ],
                "sample_count": len(values),
                "n_docs": len(set(e["doc_id"] for e in entries))
            }

        # 신뢰도 점수
        n_docs = len(seen_docs)
        n_params = len(suggested_conditions)
        avg_score = float(np.mean(all_scores)) if all_scores else 0
        confidence = round(
            min(1.0, n_docs / 5) * 0.4 +
            min(1.0, n_params / 4) * 0.3 +
            avg_score * 0.3
        , 3)

        wiz.response.status(200,
            target_text=target_text,
            suggested_conditions=suggested_conditions,
            evidence=evidence[:10],
            confidence=confidence,
            n_evidence_docs=n_docs)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# FN-0004: Uncertainty Estimator
# ==============================================================================
def estimate_uncertainty():
    """공정 조건 입력 → 유사 실험 그룹 → 결과 분산/신뢰구간"""
    try:
        collection_name, _ = _resolve_collection_and_model()

        input_conditions = {}
        for key in ["pressure", "rf_power", "gas_flow", "temperature", "frequency", "bias_voltage"]:
            val = wiz.request.query(key, "")
            if val:
                try:
                    input_conditions[key] = float(val)
                except ValueError:
                    pass

        if not input_conditions:
            wiz.response.status(400, message="최소 하나의 공정 조건을 입력하세요.")
            return

        param_db = _load_param_db(collection_name)
        if not param_db:
            wiz.response.status(200, message="먼저 파라미터 추출을 실행하세요.",
                uncertainties={}, similar_docs=[])
            return

        # 각 문서와의 조건 유사도 계산
        similarities = []
        for doc_id, doc_info in param_db.get("documents", {}).items():
            doc_params = doc_info.get("params", {})
            sim = _calc_condition_similarity(input_conditions, doc_params)
            if sim > 0.1:
                similarities.append({
                    "doc_id": doc_id,
                    "filename": doc_info.get("filename", ""),
                    "similarity": round(sim, 4),
                    "params": doc_params
                })

        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        similar_docs = similarities[:20]

        # 결과 파라미터 분포 계산
        result_keys = [k for k, v in PARAM_PATTERNS.items() if v.get("category") == "result"]
        uncertainties = {}

        for rk in result_keys:
            weighted_values = []
            for doc in similar_docs:
                if rk in doc["params"]:
                    for v in doc["params"][rk].get("values", []):
                        if isinstance(v.get("value"), (int, float)):
                            weighted_values.append((v["value"], doc["similarity"]))

            if len(weighted_values) < 2:
                continue

            vals = np.array([wv[0] for wv in weighted_values])
            weights = np.array([wv[1] for wv in weighted_values])

            w_mean = float(np.average(vals, weights=weights))
            w_var = float(np.average((vals - w_mean)**2, weights=weights))
            w_std = float(np.sqrt(w_var))

            cv = w_std / (abs(w_mean) + 1e-8)
            reliability = round(
                min(1.0, len(weighted_values) / 5) * 0.5 +
                max(0, 1 - cv) * 0.5
            , 3)

            pinfo = PARAM_PATTERNS.get(rk, {})
            uncertainties[rk] = {
                "label": pinfo.get("label", rk),
                "unit": pinfo.get("base_unit", ""),
                "mean": round(w_mean, 4),
                "std": round(w_std, 4),
                "ci_lower": round(w_mean - 1.96 * w_std, 4),
                "ci_upper": round(w_mean + 1.96 * w_std, 4),
                "min": round(float(vals.min()), 4),
                "max": round(float(vals.max()), 4),
                "n_samples": len(weighted_values),
                "reliability": reliability,
                "values": [round(float(v), 4) for v in vals.tolist()]
            }

        doc_summary = [{
            "doc_id": d["doc_id"],
            "filename": d["filename"],
            "similarity": d["similarity"]
        } for d in similar_docs[:10]]

        wiz.response.status(200,
            uncertainties=uncertainties,
            similar_docs=doc_summary,
            input_conditions=input_conditions,
            n_similar=len(similar_docs))
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# FN-0005: Surrogate Predict (Hybrid Modeling)
# ==============================================================================
def surrogate_predict():
    """공정 조건 → regression 기반 수치 예측 + 불확실성"""
    try:
        collection_name, _ = _resolve_collection_and_model()
        target_param = wiz.request.query("target_param", "etch_rate")

        if target_param not in PARAM_PATTERNS:
            wiz.response.status(400, message=f"알 수 없는 대상 파라미터: {target_param}")
            return

        input_conditions = {}
        for key in ["pressure", "rf_power", "gas_flow", "temperature", "frequency", "bias_voltage"]:
            val = wiz.request.query(key, "")
            if val:
                try:
                    input_conditions[key] = float(val)
                except ValueError:
                    pass

        if not input_conditions:
            wiz.response.status(400, message="최소 하나의 공정 조건을 입력하세요.")
            return

        param_db = _load_param_db(collection_name)
        if not param_db:
            wiz.response.status(200, message="먼저 파라미터 추출을 실행하세요.")
            return

        X, y, feature_names, doc_ids = _build_feature_matrix(param_db, target_param)

        if len(X) < 3:
            available = [k for k, v in PARAM_PATTERNS.items() if v.get("category") == "result"]
            wiz.response.status(200,
                message=f"훈련 데이터 부족 (현재 {len(X)}개, 최소 3개 필요)",
                n_training=len(X),
                available_targets=available)
            return

        from sklearn.linear_model import Ridge
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import cross_val_predict, LeaveOneOut

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        ridge = Ridge(alpha=1.0)
        ridge.fit(X_scaled, y)

        # 입력 벡터 구성 (누락 조건은 훈련 평균값 사용)
        input_vec = np.zeros(len(feature_names))
        for i, fn in enumerate(feature_names):
            if fn in input_conditions:
                input_vec[i] = input_conditions[fn]
            else:
                input_vec[i] = float(np.mean(X[:, i]))

        input_scaled = scaler.transform([input_vec])
        prediction = float(ridge.predict(input_scaled)[0])

        # Cross-validation RMSE
        cv = LeaveOneOut() if len(X) <= 20 else 5
        try:
            cv_preds = cross_val_predict(Ridge(alpha=1.0), X_scaled, y, cv=cv)
            residuals = y - cv_preds
            rmse = float(np.sqrt(np.mean(residuals**2)))
            ss_res = float(np.sum(residuals**2))
            ss_tot = float(np.sum((y - y.mean())**2))
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        except Exception:
            rmse = float(np.std(y))
            r2 = 0

        pinfo = PARAM_PATTERNS.get(target_param, {})

        importance = {}
        for i, fn in enumerate(feature_names):
            importance[fn] = {
                "label": PARAM_PATTERNS.get(fn, {}).get("label", fn),
                "coefficient": round(float(ridge.coef_[i]), 4)
            }

        wiz.response.status(200,
            prediction=round(prediction, 4),
            target_param=target_param,
            target_label=pinfo.get("label", target_param),
            unit=pinfo.get("base_unit", ""),
            confidence_interval=[
                round(prediction - 1.96 * rmse, 4),
                round(prediction + 1.96 * rmse, 4)
            ],
            rmse=round(rmse, 4),
            r2_score=round(r2, 4),
            n_training=len(X),
            feature_importance=importance,
            training_range={
                "min": round(float(y.min()), 4),
                "max": round(float(y.max()), 4),
                "mean": round(float(y.mean()), 4)
            },
            input_conditions=input_conditions)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))
