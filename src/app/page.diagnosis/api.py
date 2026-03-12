import os
import sys
import json
import traceback
import re
import time
import hashlib
import numpy as np
from collections import Counter

from sentence_transformers import SentenceTransformer
from pymilvus import MilvusClient
import season.lib.exception

try:
    from scipy.signal import find_peaks
    from scipy.interpolate import interp1d
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# ==============================================================================
# 설정
# ==============================================================================
MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
COLLECTION_META_PATH = "/opt/app/data/collection_meta.json"
DEFAULT_COLLECTION = "plasma_papers"
DATA_DIR = "/opt/app/data"
SPECTRUM_DB_PATH = os.path.join(DATA_DIR, "spectrum_db.json")
BASELINE_PATH = os.path.join(DATA_DIR, "anomaly_baseline.json")
ANOMALY_HISTORY_PATH = os.path.join(DATA_DIR, "anomaly_history.json")
FAILURE_PATTERNS_PATH = os.path.join(DATA_DIR, "failure_patterns.json")

SPECTRUM_GRID_MIN = 200
SPECTRUM_GRID_MAX = 1100
SPECTRUM_BINS = 512

# 플라즈마 주요 발광선 (파장 nm → 종)
EMISSION_LINES = {
    696.5: "Ar I", 706.7: "Ar I", 714.7: "Ar I", 727.3: "Ar I",
    738.4: "Ar I", 750.4: "Ar I", 763.5: "Ar I", 772.4: "Ar I",
    794.8: "Ar I", 811.5: "Ar I", 826.5: "Ar I", 842.5: "Ar I",
    852.1: "Ar I", 912.3: "Ar I",
    777.2: "O I", 844.6: "O I",
    337.1: "N2", 357.7: "N2", 380.5: "N2", 391.4: "N2+",
    486.1: "H-beta", 656.3: "H-alpha",
    247.9: "C I", 426.7: "C I", 516.5: "C2",
    257.5: "CF", 262.4: "CF",
    685.6: "F I", 703.7: "F I", 712.8: "F I", 739.9: "F I",
    725.7: "Cl I", 741.4: "Cl I", 754.7: "Cl I", 837.6: "Cl I",
    251.6: "Si I", 288.2: "Si I",
    388.9: "He I", 501.6: "He I", 587.6: "He I", 667.8: "He I",
}

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
# Common Helpers
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

def _load_json(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return list(default) if isinstance(default, list) else dict(default)

def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==============================================================================
# Spectrum Processing
# ==============================================================================

def _parse_spectrum_text(raw_text):
    """CSV/TSV 텍스트에서 (wavelength, intensity) 파싱"""
    wavelengths, intensities = [], []
    for line in raw_text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # 헤더 스킵
        if any(line.lower().startswith(h) for h in ['wavelength', 'wl', 'lambda', 'nm']):
            continue
        parts = re.split(r'[,\t;]+', line)
        if len(parts) >= 2:
            try:
                wavelengths.append(float(parts[0].strip()))
                intensities.append(float(parts[1].strip()))
            except ValueError:
                continue
    return np.array(wavelengths), np.array(intensities)

def _resample_spectrum(wavelengths, intensities):
    """고정 그리드(512 bins)로 리샘플링하여 임베딩 벡터 생성"""
    if len(wavelengths) < 2:
        return np.zeros(SPECTRUM_BINS)
    idx = np.argsort(wavelengths)
    wavelengths, intensities = wavelengths[idx], intensities[idx]
    grid = np.linspace(SPECTRUM_GRID_MIN, SPECTRUM_GRID_MAX, SPECTRUM_BINS)
    if HAS_SCIPY:
        f = interp1d(wavelengths, intensities, kind='linear', bounds_error=False, fill_value=0)
        resampled = f(grid)
    else:
        resampled = np.interp(grid, wavelengths, intensities)
    max_val = np.max(np.abs(resampled))
    if max_val > 0:
        resampled = resampled / max_val
    return resampled

def _detect_peaks(wavelengths, intensities, threshold=0.1):
    """스펙트럼에서 피크 검출"""
    if len(intensities) < 3:
        return [], []
    max_val = np.max(intensities)
    if max_val <= 0:
        return [], []
    norm = intensities / max_val
    if HAS_SCIPY:
        peaks, _ = find_peaks(norm, height=threshold, prominence=0.03, distance=3)
        return wavelengths[peaks].tolist(), norm[peaks].tolist()
    peak_wls, peak_ints = [], []
    for i in range(1, len(norm) - 1):
        if norm[i] > norm[i-1] and norm[i] > norm[i+1] and norm[i] > threshold:
            peak_wls.append(float(wavelengths[i]))
            peak_ints.append(float(norm[i]))
    return peak_wls, peak_ints

def _identify_species(peak_wavelengths, tolerance=2.0):
    """피크 파장으로부터 화학종 식별"""
    identified = []
    for pw in peak_wavelengths:
        best, best_d = None, tolerance
        for wl, sp in EMISSION_LINES.items():
            d = abs(pw - wl)
            if d < best_d:
                best_d = d
                best = {"line_wavelength": wl, "species": sp, "measured": round(pw, 1), "offset_nm": round(d, 2)}
        if best:
            identified.append(best)
    return identified

def _cosine_sim(a, b):
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

def _process_spectrum(raw_text):
    """스펙트럼 텍스트 → 임베딩 + 피크 + 화학종 전체 처리"""
    wls, ints = _parse_spectrum_text(raw_text)
    if len(wls) < 2:
        return None
    embedding = _resample_spectrum(wls, ints).tolist()
    peak_wls, peak_ints = _detect_peaks(wls, ints)
    species = _identify_species(peak_wls)
    species_list = sorted(set(s["species"] for s in species))
    return {
        "embedding": embedding,
        "n_points": len(wls),
        "wl_range": [float(np.min(wls)), float(np.max(wls))],
        "peaks": [{"wavelength": round(w, 1), "intensity": round(i, 4)} for w, i in zip(peak_wls, peak_ints)],
        "identified_species": species,
        "species_list": species_list
    }

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
                            if isinstance(dim, str): dim = int(dim)
                            break
                    dim_to_model = {}
                    for mname, minfo in MODEL_REGISTRY.items():
                        d = minfo["dim"]
                        if d not in dim_to_model: dim_to_model[d] = mname
                    inferred = dim_to_model.get(dim, DEFAULT_MODEL)
                    info = {"model": inferred, "dim": dim, "short_name": MODEL_REGISTRY.get(inferred, {}).get("short_name", inferred)}
                except Exception:
                    pass
            result.append({"name": name, "model": info.get("model", DEFAULT_MODEL),
                           "short_name": info.get("short_name", "Unknown"), "dim": info.get("dim", 768)})
        wiz.response.status(200, collections=result)
    except season.lib.exception.ResponseException:
        raise
    except Exception:
        wiz.response.status(200, collections=[])


def search_diagnostic():
    """진단 데이터 관련 문헌 검색"""
    try:
        query = wiz.request.query("query", "")
        diagnostic_type = wiz.request.query("diagnostic_type", "")
        top_k = int(wiz.request.query("top_k", "20"))
        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, results=[], message="컬렉션이 없습니다.")
            return
        enhanced_query = f"{diagnostic_type} {query}".strip() if diagnostic_type else query
        if not enhanced_query.strip():
            wiz.response.status(400, message="검색어를 입력하세요.")
            return
        model = _get_model(model_name)
        qvec = model.encode([enhanced_query], normalize_embeddings=True)[0].tolist()
        results = client.search(collection_name=collection_name, data=[qvec], limit=top_k,
                                output_fields=["doc_id", "filename", "chunk_index", "text"],
                                search_params={"metric_type": "COSINE"})
        items = [{"doc_id": h["entity"].get("doc_id",""), "filename": h["entity"].get("filename",""),
                  "chunk_index": h["entity"].get("chunk_index",0), "text": h["entity"].get("text","")[:400],
                  "score": round(h.get("distance",0), 4)} for h in results[0]]
        wiz.response.status(200, query=enhanced_query, results=items, total=len(items))
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def compare_diagnostics():
    """두 진단 방법 비교 분석 (키워드 기반 텍스트 비교 포함)"""
    try:
        method_a = wiz.request.query("method_a", "")
        method_b = wiz.request.query("method_b", "")
        if not method_a or not method_b:
            wiz.response.status(400, message="두 가지 진단 방법을 입력하세요.")
            return
        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        model = _get_model(model_name)
        if not client.has_collection(collection_name):
            wiz.response.status(200, comparison=[], message="컬렉션이 없습니다.")
            return

        # 각 방법별 관련 문서 검색 (텍스트 더 길게 가져옴)
        results = {}
        full_texts = {}
        for method in [method_a, method_b]:
            queries = [
                f"plasma diagnostics {method} measurement analysis",
                f"플라즈마 진단 {method} 측정 분석",
                f"{method} principle technique application"
            ]
            all_hits = []
            seen_keys = set()
            for q in queries:
                qvec = model.encode([q], normalize_embeddings=True)[0].tolist()
                sr = client.search(collection_name=collection_name, data=[qvec], limit=10,
                                   output_fields=["doc_id", "filename", "text"],
                                   search_params={"metric_type": "COSINE"})
                for h in sr[0]:
                    key = h["entity"].get("doc_id", "") + "_" + str(h.get("id", ""))
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_hits.append(h)
            all_hits.sort(key=lambda h: h.get("distance", 0), reverse=True)
            top_hits = all_hits[:15]
            results[method] = [{"doc_id": h["entity"].get("doc_id",""), "filename": h["entity"].get("filename",""),
                                "text": h["entity"].get("text","")[:300], "score": round(h.get("distance",0), 4)} for h in top_hits]
            full_texts[method] = " ".join(h["entity"].get("text","") for h in top_hits)

        docs_a = set(r["doc_id"] for r in results[method_a])
        docs_b = set(r["doc_id"] for r in results[method_b])
        common = docs_a & docs_b

        # ---- 비교 분석 텍스트 생성 ----
        analysis = _build_comparison_analysis(method_a, method_b, full_texts[method_a], full_texts[method_b], results[method_a], results[method_b])

        wiz.response.status(200, method_a=method_a, method_b=method_b,
                            results_a=results[method_a][:10], results_b=results[method_b][:10],
                            common_doc_count=len(common), common_docs=list(common),
                            analysis=analysis)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def _build_comparison_analysis(method_a, method_b, text_a, text_b, results_a, results_b):
    """두 진단 방법의 비교 분석 텍스트 생성"""
    import math
    # 불용어
    stopwords = {
        "the","a","an","is","are","was","were","be","been","being","have","has","had",
        "do","does","did","will","would","shall","should","may","might","must","can","could",
        "of","in","to","for","with","on","at","from","by","as","into","through","during",
        "before","after","above","below","between","out","off","over","under","again",
        "further","then","once","here","there","when","where","why","how","all","both",
        "each","few","more","most","other","some","such","no","nor","not","only","own",
        "same","so","than","too","very","just","about","also","and","but","or","if","that",
        "this","these","those","it","its","which","what","who","whom","their","them","they",
        "we","our","us","you","your","he","she","his","her","him","my","me",
        "플라즈마","plasma","진단","diagnostics","diagnostic","측정","분석","analysis",
        "사용","이용","방법","결과","연구","통해","위해","대한","것으로","있다","수",
        "및","등","또한","따라","있는","하는","된다","이","그","저","것","data","using",
        "used","based","results","study","method","shown","figure","table","et","al",
        "however","therefore","thus","respectively","obtained","observed","e.g.","i.e.",
    }

    def extract_keywords(text, top_n=30):
        """TF 기반 키워드 추출"""
        words = re.findall(r'[a-zA-Z\u3131-\u318E\uAC00-\uD7A3]{2,}', text.lower())
        tf = Counter(w for w in words if w not in stopwords and len(w) > 2)
        return tf.most_common(top_n)

    kw_a = extract_keywords(text_a, 40)
    kw_b = extract_keywords(text_b, 40)

    set_a = set(w for w, _ in kw_a)
    set_b = set(w for w, _ in kw_b)
    common_kw = set_a & set_b
    unique_a = set_a - set_b
    unique_b = set_b - set_a

    # 각 방법별 상위 키워드 (TF 순으로 정렬)
    top_unique_a = [w for w, c in kw_a if w in unique_a][:12]
    top_unique_b = [w for w, c in kw_b if w in unique_b][:12]
    top_common = [w for w, c in kw_a if w in common_kw][:10]

    # 문서 파일명에서 주제 추출
    files_a = list(set(r.get("filename", "") for r in results_a if r.get("filename")))[:5]
    files_b = list(set(r.get("filename", "") for r in results_b if r.get("filename")))[:5]

    # 평균 유사도
    avg_score_a = sum(r.get("score", 0) for r in results_a) / max(len(results_a), 1)
    avg_score_b = sum(r.get("score", 0) for r in results_b) / max(len(results_b), 1)

    # 비교 요약 텍스트 생성
    summary_lines = []
    summary_lines.append(f"{method_a}은(는) 주로 {', '.join(top_unique_a[:5])} 등의 키워드와 관련된 문헌에서 다루어지며, 평균 유사도 {avg_score_a*100:.1f}%로 컬렉션 내 {len(results_a)}건의 관련 문서가 검색되었습니다.")
    summary_lines.append(f"{method_b}은(는) 주로 {', '.join(top_unique_b[:5])} 등의 키워드와 관련된 문헌에서 다루어지며, 평균 유사도 {avg_score_b*100:.1f}%로 컬렉션 내 {len(results_b)}건의 관련 문서가 검색되었습니다.")

    if top_common:
        summary_lines.append(f"두 방법은 {', '.join(top_common[:5])} 등의 공통 키워드를 공유하며, 상호 보완적으로 사용될 가능성이 있습니다.")

    # 차이점 분석
    differences = []
    if top_unique_a:
        differences.append(f"{method_a}의 고유 특성: {', '.join(top_unique_a[:6])} 관련 분석에 특화되어 있습니다.")
    if top_unique_b:
        differences.append(f"{method_b}의 고유 특성: {', '.join(top_unique_b[:6])} 관련 분석에 특화되어 있습니다.")

    if abs(avg_score_a - avg_score_b) > 0.05:
        stronger = method_a if avg_score_a > avg_score_b else method_b
        differences.append(f"현재 컬렉션에서는 {stronger}에 대한 문헌이 더 풍부하게 수록되어 있습니다.")

    # 공통점 분석
    commonalities = []
    if top_common:
        commonalities.append(f"공유 키워드: {', '.join(top_common[:8])}")
    docs_a_set = set(r.get("doc_id","") for r in results_a)
    docs_b_set = set(r.get("doc_id","") for r in results_b)
    common_docs = docs_a_set & docs_b_set
    if common_docs:
        commonalities.append(f"두 방법을 함께 다루는 문서가 {len(common_docs)}건 발견되어, 해당 문서들에서 두 방법의 직접 비교 정보를 확인할 수 있습니다.")

    return {
        "summary": " ".join(summary_lines),
        "differences": differences,
        "commonalities": commonalities,
        "keywords_a": top_unique_a,
        "keywords_b": top_unique_b,
        "keywords_common": top_common,
        "avg_score_a": round(avg_score_a, 4),
        "avg_score_b": round(avg_score_b, 4),
        "files_a": files_a,
        "files_b": files_b
    }


def anomaly_search():
    """이상 현상/고장 진단 검색 (기존)"""
    try:
        symptom = wiz.request.query("symptom", "")
        if not symptom:
            wiz.response.status(400, message="증상/이상 현상을 입력하세요.")
            return
        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        model = _get_model(model_name)
        if not client.has_collection(collection_name):
            wiz.response.status(200, results=[], message="컬렉션이 없습니다.")
            return
        queries = [f"{symptom} 원인 분석", f"{symptom} 해결 방법", f"{symptom} 진단 결과", f"플라즈마 {symptom} 이상"]
        all_results = []
        for q in queries:
            qvec = model.encode([q], normalize_embeddings=True)[0].tolist()
            sr = client.search(collection_name=collection_name, data=[qvec], limit=8,
                               output_fields=["doc_id", "filename", "chunk_index", "text"],
                               search_params={"metric_type": "COSINE"})
            for h in sr[0]:
                e = h.get("entity", {})
                all_results.append({"query_context": q, "doc_id": e.get("doc_id",""), "filename": e.get("filename",""),
                                    "chunk_index": e.get("chunk_index",0), "text": e.get("text","")[:350],
                                    "score": round(h.get("distance",0), 4)})
        seen, unique = set(), []
        for r in sorted(all_results, key=lambda x: x["score"], reverse=True):
            key = f"{r['doc_id']}_{r['chunk_index']}"
            if key not in seen:
                seen.add(key)
                unique.append(r)
            if len(unique) >= 15:
                break
        wiz.response.status(200, symptom=symptom, results=unique, total=len(unique))
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def overview():
    """진단 관련 문서 현황 개요"""
    try:
        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        model = _get_model(model_name)
        if not client.has_collection(collection_name):
            wiz.response.status(200, diagnostics={}, total_chunks=0)
            return
        stats_info = client.get_collection_stats(collection_name)
        total_chunks = stats_info.get("row_count", 0)
        methods = ["OES", "Langmuir probe", "mass spectrometry", "ellipsometry", "SEM", "XPS", "AFM",
                    "optical emission spectroscopy", "interferometry"]
        diagnostics = {}
        for method in methods:
            qvec = model.encode([f"플라즈마 진단 {method}"], normalize_embeddings=True)[0].tolist()
            sr = client.search(collection_name=collection_name, data=[qvec], limit=5,
                               output_fields=["doc_id"], search_params={"metric_type": "COSINE"})
            relevant = [h for h in sr[0] if h.get("distance", 0) > 0.5]
            if relevant:
                doc_ids = set(h.get("entity", {}).get("doc_id", "") for h in relevant)
                diagnostics[method] = {"count": len(relevant), "doc_count": len(doc_ids),
                                       "max_score": round(max(h.get("distance",0) for h in relevant), 4)}
        spec_db = _load_json(SPECTRUM_DB_PATH, {"spectra": []})
        baseline = _load_json(BASELINE_PATH, {})
        history = _load_json(ANOMALY_HISTORY_PATH, [])
        wiz.response.status(200, diagnostics=diagnostics, total_chunks=total_chunks,
                            spectrum_count=len(spec_db.get("spectra", [])),
                            has_baseline=bool(baseline.get("centroid")),
                            anomaly_count=len(history))
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# OES Spectrum Embedding
# ==============================================================================

def upload_spectrum():
    """OES 스펙트럼 업로드 및 임베딩 저장"""
    try:
        spectrum_data = wiz.request.query("spectrum_data", "")
        label = wiz.request.query("label", "")
        conditions = wiz.request.query("conditions", "{}")
        if not spectrum_data.strip():
            wiz.response.status(400, message="스펙트럼 데이터를 입력하세요.")
            return
        if isinstance(conditions, str):
            try:
                conditions = json.loads(conditions)
            except Exception:
                conditions = {}
        result = _process_spectrum(spectrum_data)
        if result is None:
            wiz.response.status(400, message="스펙트럼 파싱 실패. CSV 형식(wavelength,intensity)을 확인하세요.")
            return
        spec_id = hashlib.md5(f"{time.time()}_{label}".encode()).hexdigest()[:12]
        entry = {
            "id": spec_id,
            "label": label or f"spectrum_{spec_id}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "conditions": conditions,
            "embedding": result["embedding"],
            "n_points": result["n_points"],
            "wl_range": result["wl_range"],
            "peaks": result["peaks"],
            "identified_species": result["identified_species"],
            "species_list": result["species_list"]
        }
        db = _load_json(SPECTRUM_DB_PATH, {"spectra": []})
        db["spectra"].append(entry)
        _save_json(SPECTRUM_DB_PATH, db)
        resp = {k: v for k, v in entry.items() if k != "embedding"}
        wiz.response.status(200, spectrum=resp)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def search_similar_spectrum():
    """입력 스펙트럼과 유사한 저장 스펙트럼 + 관련 논문 검색"""
    try:
        spectrum_data = wiz.request.query("spectrum_data", "")
        top_k = int(wiz.request.query("top_k", "10"))
        if not spectrum_data.strip():
            wiz.response.status(400, message="스펙트럼 데이터를 입력하세요.")
            return
        result = _process_spectrum(spectrum_data)
        if result is None:
            wiz.response.status(400, message="스펙트럼 파싱 실패")
            return
        query_emb = result["embedding"]
        # 저장된 스펙트럼 비교
        db = _load_json(SPECTRUM_DB_PATH, {"spectra": []})
        similarities = []
        for spec in db.get("spectra", []):
            sim = _cosine_sim(query_emb, spec["embedding"])
            similarities.append({
                "id": spec["id"], "label": spec["label"], "similarity": round(sim, 4),
                "species_list": spec.get("species_list", []), "conditions": spec.get("conditions", {}),
                "timestamp": spec.get("timestamp", ""), "peaks": spec.get("peaks", [])[:10]
            })
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        # 검출된 종으로 논문 검색
        related_papers = []
        if result["species_list"]:
            collection_name, model_name = _resolve_collection_and_model()
            client = _get_client()
            if client.has_collection(collection_name):
                species_query = " ".join(result["species_list"]) + " plasma OES spectrum emission"
                model = _get_model(model_name)
                qvec = model.encode([species_query], normalize_embeddings=True)[0].tolist()
                sr = client.search(collection_name=collection_name, data=[qvec], limit=10,
                                   output_fields=["doc_id", "filename", "text"],
                                   search_params={"metric_type": "COSINE"})
                seen = set()
                for h in sr[0]:
                    e = h.get("entity", {})
                    did = e.get("doc_id", "")
                    if did not in seen:
                        seen.add(did)
                        related_papers.append({"doc_id": did, "filename": e.get("filename",""),
                                               "text": e.get("text","")[:300], "score": round(h.get("distance",0), 4)})
        wiz.response.status(200,
            query_info={"n_points": result["n_points"], "wl_range": result["wl_range"],
                        "n_peaks": len(result["peaks"]), "species_list": result["species_list"],
                        "peaks": result["peaks"][:20], "identified_species": result["identified_species"][:20]},
            similar_spectra=similarities[:top_k],
            related_papers=related_papers)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def spectrum_list():
    """저장된 스펙트럼 목록"""
    try:
        db = _load_json(SPECTRUM_DB_PATH, {"spectra": []})
        items = [{k: v for k, v in s.items() if k != "embedding"} for s in db.get("spectra", [])]
        wiz.response.status(200, spectra=items, total=len(items))
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        wiz.response.status(500, message=str(e))


def delete_spectrum():
    """저장된 스펙트럼 삭제"""
    try:
        spec_id = wiz.request.query("id", "")
        if not spec_id:
            wiz.response.status(400, message="스펙트럼 ID를 지정하세요.")
            return
        db = _load_json(SPECTRUM_DB_PATH, {"spectra": []})
        before = len(db["spectra"])
        db["spectra"] = [s for s in db["spectra"] if s.get("id") != spec_id]
        _save_json(SPECTRUM_DB_PATH, db)
        if len(db["spectra"]) < before:
            wiz.response.status(200, message="삭제 완료")
        else:
            wiz.response.status(404, message="스펙트럼을 찾을 수 없습니다.")
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        wiz.response.status(500, message=str(e))


# ==============================================================================
# Multimodal Retrieval
# ==============================================================================

def multimodal_search():
    """텍스트 + 스펙트럼 통합 검색"""
    try:
        text_query = wiz.request.query("text_query", "")
        spectrum_data = wiz.request.query("spectrum_data", "")
        text_weight = float(wiz.request.query("text_weight", "0.6"))
        spectrum_weight = float(wiz.request.query("spectrum_weight", "0.4"))
        top_k = int(wiz.request.query("top_k", "15"))
        if not text_query.strip() and not spectrum_data.strip():
            wiz.response.status(400, message="텍스트 또는 스펙트럼 데이터를 입력하세요.")
            return
        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, results=[], message="컬렉션이 없습니다.")
            return
        doc_scores = {}
        # 텍스트 검색
        if text_query.strip():
            model = _get_model(model_name)
            qvec = model.encode([text_query], normalize_embeddings=True)[0].tolist()
            sr = client.search(collection_name=collection_name, data=[qvec], limit=top_k * 2,
                               output_fields=["doc_id", "filename", "text"],
                               search_params={"metric_type": "COSINE"})
            for h in sr[0]:
                e = h.get("entity", {})
                did = e.get("doc_id", "")
                score = h.get("distance", 0)
                if did not in doc_scores or score > doc_scores[did]["text_score"]:
                    doc_scores[did] = {"doc_id": did, "filename": e.get("filename",""),
                                       "text_snippet": e.get("text","")[:300],
                                       "text_score": score, "spectrum_score": 0}
        # 스펙트럼 기반 종 추출 → 텍스트 검색
        spectrum_info = None
        if spectrum_data.strip():
            result = _process_spectrum(spectrum_data)
            if result and result["species_list"]:
                spectrum_info = {"n_peaks": len(result["peaks"]), "species_list": result["species_list"],
                                 "peaks": result["peaks"][:15]}
                species_query = " ".join(result["species_list"]) + " emission spectrum plasma diagnostic"
                model = _get_model(model_name)
                qvec = model.encode([species_query], normalize_embeddings=True)[0].tolist()
                sr = client.search(collection_name=collection_name, data=[qvec], limit=top_k * 2,
                                   output_fields=["doc_id", "filename", "text"],
                                   search_params={"metric_type": "COSINE"})
                for h in sr[0]:
                    e = h.get("entity", {})
                    did = e.get("doc_id", "")
                    score = h.get("distance", 0)
                    if did in doc_scores:
                        if score > doc_scores[did]["spectrum_score"]:
                            doc_scores[did]["spectrum_score"] = score
                    else:
                        doc_scores[did] = {"doc_id": did, "filename": e.get("filename",""),
                                           "text_snippet": e.get("text","")[:300],
                                           "text_score": 0, "spectrum_score": score}
        # 가중 결합
        total_w = max(text_weight + spectrum_weight, 0.01)
        combined = []
        for did, info in doc_scores.items():
            info["combined_score"] = round((info["text_score"] * text_weight + info["spectrum_score"] * spectrum_weight) / total_w, 4)
            info["text_score"] = round(info["text_score"], 4)
            info["spectrum_score"] = round(info["spectrum_score"], 4)
            combined.append(info)
        combined.sort(key=lambda x: x["combined_score"], reverse=True)
        wiz.response.status(200, results=combined[:top_k], total=len(combined[:top_k]),
                            spectrum_info=spectrum_info, weights={"text": text_weight, "spectrum": spectrum_weight})
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# Anomaly Detection
# ==============================================================================

def set_baseline():
    """정상 공정 스펙트럼으로 베이스라인 설정"""
    try:
        spectra_data = wiz.request.query("spectra_data", "")
        label = wiz.request.query("label", "default")
        threshold = float(wiz.request.query("threshold", "0.15"))
        if not spectra_data.strip():
            wiz.response.status(400, message="스펙트럼 데이터를 입력하세요. 여러 스펙트럼은 '---'로 구분합니다.")
            return
        raw_spectra = spectra_data.split('---')
        embeddings = []
        all_species = []
        for raw in raw_spectra:
            raw = raw.strip()
            if not raw:
                continue
            result = _process_spectrum(raw)
            if result:
                embeddings.append(result["embedding"])
                all_species.extend(result["species_list"])
        if len(embeddings) < 1:
            wiz.response.status(400, message="유효한 스펙트럼이 없습니다.")
            return
        centroid = np.mean(embeddings, axis=0).tolist()
        distances = [1 - _cosine_sim(centroid, e) for e in embeddings]
        mean_dist = float(np.mean(distances))
        std_dist = float(np.std(distances)) if len(distances) > 1 else 0.0
        baseline = {
            "label": label, "centroid": centroid, "n_samples": len(embeddings),
            "threshold": threshold,
            "mean_distance": round(mean_dist, 6), "std_distance": round(std_dist, 6),
            "auto_threshold": round(mean_dist + 3 * std_dist, 6) if std_dist > 0 else threshold,
            "species_distribution": dict(Counter(all_species)),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        _save_json(BASELINE_PATH, baseline)
        resp = {k: v for k, v in baseline.items() if k != "centroid"}
        wiz.response.status(200, baseline=resp)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def get_baseline():
    """현재 베이스라인 정보 조회"""
    try:
        baseline = _load_json(BASELINE_PATH, {})
        if not baseline.get("centroid"):
            wiz.response.status(200, has_baseline=False)
            return
        resp = {k: v for k, v in baseline.items() if k != "centroid"}
        resp["has_baseline"] = True
        wiz.response.status(200, **resp)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        wiz.response.status(500, message=str(e))


def check_anomaly():
    """스펙트럼 이상 탐지"""
    try:
        spectrum_data = wiz.request.query("spectrum_data", "")
        if not spectrum_data.strip():
            wiz.response.status(400, message="스펙트럼 데이터를 입력하세요.")
            return
        baseline = _load_json(BASELINE_PATH, {})
        if not baseline.get("centroid"):
            wiz.response.status(400, message="베이스라인이 설정되지 않았습니다.")
            return
        result = _process_spectrum(spectrum_data)
        if result is None:
            wiz.response.status(400, message="스펙트럼 파싱 실패")
            return
        cosine_dist = 1 - _cosine_sim(result["embedding"], baseline["centroid"])
        threshold = baseline.get("threshold", 0.15)
        is_anomaly = cosine_dist > threshold
        severity = min(1.0, cosine_dist / max(threshold * 2, 0.01))
        record = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "distance": round(cosine_dist, 6), "threshold": threshold,
            "is_anomaly": is_anomaly, "severity": round(severity, 4),
            "n_peaks": len(result["peaks"]), "species_list": result["species_list"]
        }
        history = _load_json(ANOMALY_HISTORY_PATH, [])
        history.append(record)
        if len(history) > 1000:
            history = history[-1000:]
        _save_json(ANOMALY_HISTORY_PATH, history)
        wiz.response.status(200, is_anomaly=is_anomaly, distance=round(cosine_dist, 6),
                            threshold=threshold, severity=round(severity, 4),
                            species_list=result["species_list"], peaks=result["peaks"][:15],
                            baseline_label=baseline.get("label", ""))
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def anomaly_history_list():
    """이상 탐지 이력 조회"""
    try:
        limit = int(wiz.request.query("limit", "100"))
        history = _load_json(ANOMALY_HISTORY_PATH, [])
        recent = list(reversed(history[-limit:]))
        anomaly_count = sum(1 for h in history if h.get("is_anomaly"))
        avg_distance = round(float(np.mean([h["distance"] for h in history])), 6) if history else 0
        wiz.response.status(200, history=recent, total=len(history),
                            anomaly_count=anomaly_count, avg_distance=avg_distance)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        wiz.response.status(500, message=str(e))


def update_threshold():
    """이상 탐지 임계값 변경"""
    try:
        threshold = float(wiz.request.query("threshold", "0.15"))
        baseline = _load_json(BASELINE_PATH, {})
        if not baseline.get("centroid"):
            wiz.response.status(400, message="베이스라인이 없습니다.")
            return
        baseline["threshold"] = threshold
        _save_json(BASELINE_PATH, baseline)
        wiz.response.status(200, threshold=threshold)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        wiz.response.status(500, message=str(e))


def clear_history():
    """이상 탐지 이력 초기화"""
    try:
        _save_json(ANOMALY_HISTORY_PATH, [])
        wiz.response.status(200, message="이력이 초기화되었습니다.")
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        wiz.response.status(500, message=str(e))


# ==============================================================================
# Failure Case Reasoning
# ==============================================================================

def failure_reasoning():
    """고장 증상 분석 및 유사 failure case 검색"""
    try:
        symptom = wiz.request.query("symptom", "")
        spectrum_data = wiz.request.query("spectrum_data", "")
        if not symptom.strip() and not spectrum_data.strip():
            wiz.response.status(400, message="증상 또는 스펙트럼 데이터를 입력하세요.")
            return
        # 1. 알려진 패턴 매칭
        patterns = _load_json(FAILURE_PATTERNS_PATH, [])
        matched_patterns = []
        symptom_lower = symptom.lower()
        for pat in patterns:
            pat_symptoms = [s.lower() for s in pat.get("symptoms", [])]
            match_count = sum(1 for ps in pat_symptoms if ps in symptom_lower or symptom_lower in ps)
            if match_count > 0:
                matched_patterns.append({**pat, "match_score": round(match_count / max(len(pat_symptoms), 1), 2)})
        matched_patterns.sort(key=lambda x: x["match_score"], reverse=True)
        # 2. 스펙트럼 분석
        spectrum_info = None
        species_context = ""
        if spectrum_data.strip():
            result = _process_spectrum(spectrum_data)
            if result:
                spectrum_info = {"n_peaks": len(result["peaks"]), "species_list": result["species_list"],
                                 "peaks": result["peaks"][:15]}
                species_context = " ".join(result["species_list"])
        # 3. 벡터 검색
        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        evidence_docs = []
        if client.has_collection(collection_name):
            model = _get_model(model_name)
            queries = [
                f"{symptom} failure cause analysis {species_context}".strip(),
                f"{symptom} troubleshooting solution {species_context}".strip(),
                f"plasma process {symptom} abnormal diagnosis",
                f"{symptom} mechanism root cause"
            ]
            all_hits = []
            for q in queries:
                qvec = model.encode([q], normalize_embeddings=True)[0].tolist()
                sr = client.search(collection_name=collection_name, data=[qvec], limit=8,
                                   output_fields=["doc_id", "filename", "chunk_index", "text"],
                                   search_params={"metric_type": "COSINE"})
                for h in sr[0]:
                    e = h.get("entity", {})
                    all_hits.append({
                        "query_context": q.replace(species_context, "").strip() if species_context else q,
                        "doc_id": e.get("doc_id",""), "filename": e.get("filename",""),
                        "chunk_index": e.get("chunk_index",0), "text": e.get("text","")[:400],
                        "score": round(h.get("distance",0), 4)
                    })
            seen = set()
            for h in sorted(all_hits, key=lambda x: x["score"], reverse=True):
                key = f"{h['doc_id']}_{h['chunk_index']}"
                if key not in seen:
                    seen.add(key)
                    text_l = h["text"].lower()
                    tags = []
                    if any(kw in text_l for kw in ["cause", "due to", "because", "원인", "기인"]):
                        tags.append("원인분석")
                    if any(kw in text_l for kw in ["solution", "resolve", "fix", "prevent", "해결", "방지", "개선"]):
                        tags.append("해결방법")
                    if not tags:
                        tags.append("관련자료")
                    h["tags"] = tags
                    evidence_docs.append(h)
                if len(evidence_docs) >= 15:
                    break
        cause_docs = [d for d in evidence_docs if "원인분석" in d.get("tags",[])]
        solution_docs = [d for d in evidence_docs if "해결방법" in d.get("tags",[])]
        summary = {
            "symptom": symptom, "n_matched_patterns": len(matched_patterns),
            "n_evidence_docs": len(evidence_docs), "n_cause_docs": len(cause_docs),
            "n_solution_docs": len(solution_docs),
            "detected_species": spectrum_info["species_list"] if spectrum_info else []
        }
        wiz.response.status(200, summary=summary, matched_patterns=matched_patterns[:5],
                            evidence_docs=evidence_docs, spectrum_info=spectrum_info)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def register_failure_pattern():
    """알려진 고장 패턴 등록"""
    try:
        name = wiz.request.query("name", "")
        symptoms_raw = wiz.request.query("symptoms", "")
        causes_raw = wiz.request.query("causes", "")
        solutions_raw = wiz.request.query("solutions", "")
        related_peaks = wiz.request.query("related_peaks", "")
        if not name.strip():
            wiz.response.status(400, message="패턴 이름을 입력하세요.")
            return
        symptoms = [s.strip() for s in symptoms_raw.split(',') if s.strip()]
        causes = [s.strip() for s in causes_raw.split(',') if s.strip()]
        solutions = [s.strip() for s in solutions_raw.split(',') if s.strip()]
        peaks = [s.strip() for s in related_peaks.split(',') if s.strip()]
        if not symptoms:
            wiz.response.status(400, message="증상을 1개 이상 입력하세요.")
            return
        pattern_id = hashlib.md5(f"{time.time()}_{name}".encode()).hexdigest()[:10]
        pattern = {"id": pattern_id, "name": name, "symptoms": symptoms, "causes": causes,
                   "solutions": solutions, "related_peaks": peaks,
                   "created_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        patterns = _load_json(FAILURE_PATTERNS_PATH, [])
        patterns.append(pattern)
        _save_json(FAILURE_PATTERNS_PATH, patterns)
        wiz.response.status(200, pattern=pattern)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        wiz.response.status(500, message=str(e))


def list_failure_patterns():
    """등록된 고장 패턴 목록"""
    try:
        patterns = _load_json(FAILURE_PATTERNS_PATH, [])
        wiz.response.status(200, patterns=patterns, total=len(patterns))
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        wiz.response.status(500, message=str(e))


def delete_failure_pattern():
    """고장 패턴 삭제"""
    try:
        pattern_id = wiz.request.query("id", "")
        if not pattern_id:
            wiz.response.status(400, message="패턴 ID를 지정하세요.")
            return
        patterns = _load_json(FAILURE_PATTERNS_PATH, [])
        before = len(patterns)
        patterns = [p for p in patterns if p.get("id") != pattern_id]
        _save_json(FAILURE_PATTERNS_PATH, patterns)
        if len(patterns) < before:
            wiz.response.status(200, message="삭제 완료")
        else:
            wiz.response.status(404, message="패턴을 찾을 수 없습니다.")
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        wiz.response.status(500, message=str(e))


# ==============================================================================
# Boltzmann Plot 분석
# ==============================================================================
def boltzmann_plot():
    """OES 데이터로 Boltzmann plot → 전자 온도 추정"""
    try:
        spectrum_data = wiz.request.query("spectrum_data", "")
        if not spectrum_data.strip():
            wiz.response.status(400, message="스펙트럼 데이터를 입력하세요.")

        import math

        lines = [l.strip() for l in spectrum_data.strip().split('\n') if l.strip()]
        points = []
        for line in lines:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 5:
                continue
            wavelength = float(parts[0])
            intensity = float(parts[1])
            energy = float(parts[2])    # 상태 에너지 (eV)
            g = float(parts[3])         # 통계 가중치
            A = float(parts[4])         # 전이 확률 (s⁻¹)

            if intensity <= 0 or g <= 0 or A <= 0 or wavelength <= 0:
                continue
            ln_val = math.log(intensity * wavelength * 1e-9 / (g * A))
            points.append({
                "wavelength": wavelength,
                "energy": energy,
                "g": g,
                "A": A,
                "intensity": intensity,
                "ln_value": round(ln_val, 4)
            })

        if len(points) < 2:
            wiz.response.status(400, message="최소 2개 이상의 유효한 데이터 포인트가 필요합니다.")

        # 선형 회귀: ln(I*λ/(g*A)) = -E/(kT) + const
        x = np.array([p["energy"] for p in points])
        y = np.array([p["ln_value"] for p in points])

        n = len(x)
        sx = np.sum(x)
        sy = np.sum(y)
        sxy = np.sum(x * y)
        sxx = np.sum(x * x)
        syy = np.sum(y * y)

        slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
        intercept = (sy - slope * sx) / n

        # R²
        ss_res = np.sum((y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        # Te = -1/slope (eV) (since slope = -1/(kT) with k_B=1 when E in eV)
        Te_eV = round(-1.0 / slope, 3) if slope != 0 else 0
        Te_K = round(Te_eV * 11604.5, 1)

        wiz.response.status(200, {
            "Te_eV": Te_eV,
            "Te_K": Te_K,
            "slope": round(slope, 6),
            "intercept": round(intercept, 4),
            "r_squared": round(r_squared, 4),
            "n_points": n,
            "points": points
        })

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# Langmuir Probe I-V 분석
# ==============================================================================
def langmuir_analysis():
    """I-V 특성 데이터에서 플라즈마 파라미터 추출"""
    try:
        iv_data = wiz.request.query("iv_data", "")
        if not iv_data.strip():
            wiz.response.status(400, message="I-V 데이터를 입력하세요.")

        import math

        lines = [l.strip() for l in iv_data.strip().split('\n') if l.strip()]
        voltages = []
        currents = []
        for line in lines:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                voltages.append(float(parts[0]))
                currents.append(float(parts[1]))

        if len(voltages) < 4:
            wiz.response.status(400, message="최소 4개 이상의 데이터 포인트가 필요합니다.")

        V = np.array(voltages)
        I = np.array(currents)

        # 부유 전위 Vf: I=0 지점 근사
        Vf = 0
        for i in range(len(I) - 1):
            if I[i] <= 0 and I[i+1] > 0:
                Vf = V[i] + (V[i+1] - V[i]) * (-I[i]) / (I[i+1] - I[i])
                break

        # 이온 포화 전류 (가장 음의 전압 영역)
        i_ion_sat = np.mean(I[V < V.min() + (V.max() - V.min()) * 0.2])

        # 전자 전류: I_e = I - I_ion_sat
        I_e = I - i_ion_sat

        # 전이 영역에서 Te 추정 (ln(I_e) vs V의 기울기)
        mask = (I_e > 0) & (V < np.max(V) * 0.8) & (V > Vf - 5)
        if np.sum(mask) >= 2:
            V_trans = V[mask]
            ln_Ie = np.log(I_e[mask])
            coeffs = np.polyfit(V_trans, ln_Ie, 1)
            Te_eV = round(1.0 / coeffs[0], 3) if coeffs[0] > 0 else 1.0
        else:
            Te_eV = 1.0

        Te_K = round(Te_eV * 11604.5, 1)

        # 플라즈마 전위 Vp: dI/dV 최대 지점
        dI = np.gradient(I, V)
        Vp_idx = np.argmax(dI)
        Vp = round(float(V[Vp_idx]), 2)

        # 전자 포화 전류 → ne
        I_e_sat = float(np.max(I_e))
        e = 1.602e-19
        me = 9.109e-31
        kB = 1.381e-23
        Te_K_val = Te_eV * 11604.5
        probe_area = 1e-6  # 가정: 1 mm² 프로브 면적
        if Te_K_val > 0 and I_e_sat > 0:
            ne = I_e_sat / (e * probe_area * math.sqrt(e * Te_eV / (2 * math.pi * me)))
        else:
            ne = 0

        wiz.response.status(200, {
            "ne": f"{ne:.2e}",
            "Te_eV": round(Te_eV, 3),
            "Te_K": Te_K,
            "Vp": Vp,
            "Vf": round(Vf, 2),
            "I_ion_sat": f"{i_ion_sat:.4e}",
            "I_e_sat": f"{I_e_sat:.4e}",
            "n_points": len(voltages)
        })

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# Actinometry 분석
# ==============================================================================
def actinometry_analysis():
    """OES Actinometry를 통한 반응성 종 상대 밀도 추정"""
    try:
        spectrum_data = wiz.request.query("spectrum_data", "")
        ref_gas = wiz.request.query("ref_gas", "Ar")

        if not spectrum_data.strip():
            wiz.response.status(400, message="스펙트럼 데이터를 입력하세요.")

        # 기준 파장 매핑
        ref_wavelengths = {
            "Ar": 750.4,
            "He": 706.5,
            "Ne": 585.2
        }
        ref_wl = ref_wavelengths.get(ref_gas, 750.4)

        lines_input = [l.strip() for l in spectrum_data.strip().split('\n') if l.strip()]
        entries = []
        ref_entry = None

        for line in lines_input:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 3:
                wl = float(parts[0])
                intensity = float(parts[1])
                species = parts[2].strip()
                entry = {"wavelength": wl, "intensity": intensity, "name": species}
                entries.append(entry)
                if species.lower() == ref_gas.lower():
                    if ref_entry is None or abs(wl - ref_wl) < abs(ref_entry["wavelength"] - ref_wl):
                        ref_entry = entry

        if ref_entry is None:
            wiz.response.status(400, message=f"기준 가스({ref_gas}) 데이터가 없습니다.")

        ref_intensity = ref_entry["intensity"]
        if ref_intensity <= 0:
            wiz.response.status(400, message="기준 가스 강도가 0 이하입니다.")

        # 각 종별 상대 밀도 계산
        species_results = []
        for entry in entries:
            if entry["name"].lower() == ref_gas.lower():
                continue
            ratio = entry["intensity"] / ref_intensity
            species_results.append({
                "name": entry["name"],
                "wavelength": entry["wavelength"],
                "intensity": entry["intensity"],
                "ratio": round(ratio, 4),
                "relative_density": round(ratio, 4)
            })

        wiz.response.status(200, {
            "ref_gas": ref_gas,
            "ref_wavelength": ref_entry["wavelength"],
            "ref_intensity": ref_intensity,
            "species": species_results
        })

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))
