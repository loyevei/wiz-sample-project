import os
import sys
import json
import traceback
import re
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations

from sentence_transformers import SentenceTransformer
from pymilvus import MilvusClient
import season.lib.exception

# ==============================================================================
# 설정 (page.research와 공유)
# ==============================================================================
MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
COLLECTION_META_PATH = "/opt/app/data/collection_meta.json"
DEFAULT_COLLECTION = "plasma_papers"
THEORY_GRAPH_DIR = "/opt/app/data/theory_graphs"

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
# 플라즈마 도메인 수식 사전
# ==============================================================================
PLASMA_EQUATIONS = {
    "boltzmann": {
        "name": "Boltzmann 방정식",
        "patterns": [r"\\frac\{\\partial\s*f\}", r"Boltzmann\s+equation", r"distribution\s+function.*collision"],
        "category": "governing",
        "description": "입자 분포 함수의 시간 진화를 기술하는 운동론적 방정식"
    },
    "poisson": {
        "name": "Poisson 방정식",
        "patterns": [r"\\nabla\^2\s*\\phi", r"\\nabla\^2\s*V", r"Poisson.*equation", r"\\varepsilon.*\\nabla\^2"],
        "category": "governing",
        "description": "전기장과 전하 밀도의 관계를 기술하는 방정식"
    },
    "continuity": {
        "name": "연속 방정식",
        "patterns": [r"\\frac\{\\partial\s*n\}", r"continuity\s+equation", r"\\nabla\s*\\cdot.*n.*v"],
        "category": "governing",
        "description": "입자 수 보존을 기술하는 수송 방정식"
    },
    "energy_balance": {
        "name": "에너지 보존식",
        "patterns": [r"energy\s+balance", r"\\frac\{\\partial.*T\}", r"energy\s+conservation"],
        "category": "governing",
        "description": "에너지 보존 법칙을 기술하는 방정식"
    },
    "maxwellian": {
        "name": "Maxwellian 분포",
        "patterns": [r"Maxwellian", r"f.*exp.*-.*kT", r"Maxwell.*distribution"],
        "category": "constitutive",
        "description": "열평형 상태의 입자 속도 분포 함수"
    },
    "drude": {
        "name": "Drude 모델",
        "patterns": [r"Drude\s+model", r"\\sigma.*=.*ne\^2.*\\tau", r"Drude"],
        "category": "empirical",
        "description": "금속의 전기 전도도를 설명하는 고전자 모델"
    },
    "debye_length": {
        "name": "Debye 길이",
        "patterns": [r"Debye\s+length", r"\\lambda_D", r"Debye\s+shielding"],
        "category": "constitutive",
        "description": "플라즈마의 차폐 거리를 나타내는 특성 길이"
    },
    "langmuir_probe": {
        "name": "Langmuir 프로브 이론",
        "patterns": [r"Langmuir\s+probe", r"I-V\s+characteristic", r"electron\s+saturation\s+current"],
        "category": "empirical",
        "description": "프로브 전류-전압 특성을 이용한 플라즈마 진단 이론"
    },
    "child_langmuir": {
        "name": "Child-Langmuir 법칙",
        "patterns": [r"Child.*Langmuir", r"space.*charge.*limited", r"J.*V\^\{3/2\}"],
        "category": "empirical",
        "description": "공간 전하 제한 전류를 기술하는 법칙"
    },
    "paschen": {
        "name": "Paschen 법칙",
        "patterns": [r"Paschen", r"breakdown\s+voltage.*pd", r"V_b.*=.*f\(pd\)"],
        "category": "empirical",
        "description": "방전 개시 전압과 기체 압력-전극 간격 곱의 관계"
    },
    "saha": {
        "name": "Saha 방정식",
        "patterns": [r"Saha.*equation", r"ionization\s+equilibrium", r"n_e.*n_i.*n_n"],
        "category": "constitutive",
        "description": "열평형 상태의 이온화 정도를 기술하는 방정식"
    },
    "arrhenius": {
        "name": "Arrhenius 식",
        "patterns": [r"Arrhenius", r"k.*=.*A.*exp.*-E_a", r"activation\s+energy"],
        "category": "empirical",
        "description": "온도에 따른 반응 속도 상수의 변화를 기술하는 식"
    }
}

# 수식 유형 분류
EQUATION_CATEGORIES = {
    "governing": {"label": "지배 방정식", "color": "indigo", "description": "물리계의 기본 법칙을 기술하는 방정식"},
    "boundary": {"label": "경계 조건", "color": "emerald", "description": "경계에서의 물리량 조건을 규정하는 식"},
    "constitutive": {"label": "구성 관계", "color": "violet", "description": "물질의 특성을 기술하는 관계식"},
    "empirical": {"label": "경험식", "color": "amber", "description": "실험 데이터로부터 도출된 경험적 관계식"},
    "other": {"label": "기타", "color": "gray", "description": "분류되지 않은 수식"}
}

# ==============================================================================
# 가정(Assumption) 사전
# ==============================================================================
ASSUMPTION_DICT = {
    "quasi_neutrality": {
        "name": "준중성 (Quasi-neutrality)",
        "patterns": [r"quasi.?neutral", r"n_e\s*[≈=~]\s*n_i", r"charge\s+neutrality"],
        "category": "plasma_property",
        "contradicts": ["non_neutral"]
    },
    "non_neutral": {
        "name": "비중성 (Non-neutral)",
        "patterns": [r"non.?neutral", r"space\s+charge", r"sheath\s+region"],
        "category": "plasma_property",
        "contradicts": ["quasi_neutrality"]
    },
    "maxwellian_eedf": {
        "name": "Maxwellian EEDF",
        "patterns": [r"Maxwellian\s+EEDF", r"Maxwellian\s+distribution", r"thermal\s+equilibrium.*electron"],
        "category": "distribution",
        "contradicts": ["non_maxwellian"]
    },
    "non_maxwellian": {
        "name": "Non-Maxwellian EEDF",
        "patterns": [r"non.?Maxwellian", r"bi.?Maxwellian", r"Druyvesteyn", r"EEDF.*deviates?"],
        "category": "distribution",
        "contradicts": ["maxwellian_eedf"]
    },
    "lte": {
        "name": "LTE (국소 열평형)",
        "patterns": [r"local\s+thermodynamic\s+equilibrium", r"\bLTE\b", r"thermal\s+equilibrium"],
        "category": "equilibrium",
        "contradicts": ["non_lte"]
    },
    "non_lte": {
        "name": "Non-LTE",
        "patterns": [r"non.?LTE", r"non.?equilibrium", r"out\s+of\s+equilibrium"],
        "category": "equilibrium",
        "contradicts": ["lte"]
    },
    "collisionless": {
        "name": "무충돌 (Collisionless)",
        "patterns": [r"collisionless", r"mean\s+free\s+path.*>>", r"Knudsen.*>>"],
        "category": "transport",
        "contradicts": ["collisional"]
    },
    "collisional": {
        "name": "충돌성 (Collisional)",
        "patterns": [r"collision.?dominated", r"collisional\s+plasma", r"mean\s+free\s+path.*<<"],
        "category": "transport",
        "contradicts": ["collisionless"]
    },
    "fluid_model": {
        "name": "유체 모델 (Fluid Model)",
        "patterns": [r"fluid\s+model", r"fluid\s+approximation", r"drift.?diffusion"],
        "category": "model_type",
        "contradicts": ["kinetic_model"]
    },
    "kinetic_model": {
        "name": "운동론 모델 (Kinetic Model)",
        "patterns": [r"kinetic\s+model", r"kinetic\s+theory", r"PIC.*simulation", r"particle.?in.?cell"],
        "category": "model_type",
        "contradicts": ["fluid_model"]
    },
    "steady_state": {
        "name": "정상 상태 (Steady-state)",
        "patterns": [r"steady.?state", r"time.?independent", r"stationary\s+solution"],
        "category": "temporal",
        "contradicts": ["time_dependent"]
    },
    "time_dependent": {
        "name": "시간 의존 (Time-dependent)",
        "patterns": [r"time.?dependent", r"transient", r"pulsed\s+plasma", r"temporal\s+evolution"],
        "category": "temporal",
        "contradicts": ["steady_state"]
    },
    "ambipolar_diffusion": {
        "name": "양극성 확산 (Ambipolar Diffusion)",
        "patterns": [r"ambipolar\s+diffusion", r"ambipolar\s+transport"],
        "category": "transport",
        "contradicts": []
    },
    "optically_thin": {
        "name": "광학적 얇은 (Optically Thin)",
        "patterns": [r"optically\s+thin", r"optical\s+depth.*<<"],
        "category": "radiation",
        "contradicts": ["optically_thick"]
    },
    "optically_thick": {
        "name": "광학적 두꺼운 (Optically Thick)",
        "patterns": [r"optically\s+thick", r"optical\s+depth.*>>", r"radiation\s+trapping"],
        "category": "radiation",
        "contradicts": ["optically_thin"]
    }
}

ASSUMPTION_CATEGORIES = {
    "plasma_property": "플라즈마 특성",
    "distribution": "분포 함수",
    "equilibrium": "평형 상태",
    "transport": "수송 현상",
    "model_type": "모델 유형",
    "temporal": "시간 의존성",
    "radiation": "복사"
}

ASSUMPTION_TRIGGER_PATTERNS = [
    r"(?:we\s+)?assum(?:e|ing|ed|ption)",
    r"under\s+the\s+(?:assumption|condition)",
    r"it\s+is\s+assumed",
    r"(?:we\s+)?consider(?:ing)?.*(?:to\s+be|as)",
    r"supposed\s+to\s+be",
    r"approximat(?:e|ion|ed)",
    r"neglect(?:ing|ed)?",
    r"가정",
    r"근사",
]

# ==============================================================================
# 이론 그래프 개념 사전
# ==============================================================================
PLASMA_CONCEPTS = [
    "electron density", "electron temperature", "ion density", "ion energy",
    "plasma potential", "floating potential", "sheath", "bulk plasma",
    "ionization", "recombination", "dissociation", "excitation",
    "mean free path", "collision frequency", "cross section",
    "Debye length", "plasma frequency", "gyro radius", "Larmor radius",
    "RF power", "DC bias", "impedance", "matching network",
    "etch rate", "deposition rate", "selectivity", "uniformity",
    "reactive species", "radical", "ion flux", "neutral flux",
    "gas pressure", "gas flow", "residence time",
    "전자 밀도", "전자 온도", "이온 에너지", "플라즈마 전위",
    "시스 영역", "벌크 플라즈마", "이온화", "재결합", "해리",
    "평균 자유 경로", "충돌 주파수", "반응 단면적",
    "식각 속도", "증착 속도", "선택비", "균일도",
    "RF 전력", "DC 바이어스", "가스 압력", "가스 유량"
]

CAUSAL_PATTERNS = [
    (r"(\w[\w\s]{2,30})\s+(?:leads?\s+to|results?\s+in|causes?|induces?)\s+(\w[\w\s]{2,30})", "causes"),
    (r"(?:due\s+to|because\s+of|owing\s+to)\s+(\w[\w\s]{2,30}),?\s*(\w[\w\s]{2,30})", "causes"),
    (r"(\w[\w\s]{2,30})\s+(?:depends?\s+on|is\s+determined\s+by)\s+(\w[\w\s]{2,30})", "depends_on"),
    (r"(?:increasing|decreasing|higher|lower)\s+(\w[\w\s]{2,30})\s+(?:increases?|decreases?|enhances?|reduces?)\s+(\w[\w\s]{2,30})", "affects"),
    (r"(\w[\w\s]{2,30})\s+(?:is\s+proportional\s+to|∝|\\propto)\s+(\w[\w\s]{2,30})", "proportional"),
]

# ==============================================================================
# 공통 유틸리티
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
    info = meta.get(collection_name, {})
    return info.get("model", DEFAULT_MODEL)

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

def _get_collection_fields(client, collection_name):
    """컬렉션의 실제 스키마 필드명 목록을 반환"""
    try:
        col_info = client.describe_collection(collection_name)
        return set(f.get("name", "") for f in col_info.get("fields", []))
    except Exception:
        return set()

def _query_all_chunks(client, collection_name, filter_expr, output_fields, max_limit=16000):
    """Milvus limit 제한(16384) 대응 페이지네이션 조회"""
    all_results = []
    offset = 0
    while True:
        batch = client.query(
            collection_name=collection_name,
            filter=filter_expr,
            output_fields=output_fields,
            limit=max_limit,
            offset=offset
        )
        if not batch:
            break
        all_results.extend(batch)
        if len(batch) < max_limit:
            break
        offset += max_limit
    return all_results

def _resolve_collection_and_model():
    collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip()
    if not collection_name:
        collection_name = DEFAULT_COLLECTION
    model_name = _get_collection_model(collection_name)
    return collection_name, model_name


# ==============================================================================
# 컬렉션 목록
# ==============================================================================
def collections():
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
                    info = {"model": inferred, "dim": dim, "short_name": inferred_info.get("short_name", inferred)}
                except Exception:
                    pass
            total_chunks = 0
            total_docs = 0
            try:
                stats_info = client.get_collection_stats(name)
                total_chunks = stats_info.get("row_count", 0)
                if total_chunks > 0:
                    docs = client.query(collection_name=name, filter="chunk_index == 0",
                                       output_fields=["doc_id"], limit=10000)
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


# ==============================================================================
# Equation-aware Retrieval
# ==============================================================================
def _extract_latex_equations(text):
    """텍스트에서 LaTeX 수식 패턴 추출 (Embedding [EQUATION:] 마커 포함)"""
    equations = []
    seen_latex = set()

    # 0. [EQUATION: ...] / [FORMULA: ...] 마커에서 추출 (Embedding 저장 형식)
    #    형식: [EQUATION: eq_N | type=display | $$latex$$ | context: ...]
    for m in re.finditer(r'\[(?:EQUATION|FORMULA):\s*([^\]]+)\]', text):
        marker_content = m.group(1)
        # $$...$$ 추출 시도
        latex_m = re.search(r'\$\$(.+?)\$\$', marker_content)
        if latex_m:
            latex = latex_m.group(1).strip()
            eq_type = "display"
        else:
            # $...$ 추출 시도
            latex_m = re.search(r'\$([^\$]+)\$', marker_content)
            if latex_m:
                latex = latex_m.group(1).strip()
                eq_type = "inline"
            else:
                # context 부분에서 추출
                parts = marker_content.split("|")
                latex = parts[-1].strip() if len(parts) > 1 else marker_content.strip()
                latex = re.sub(r'^context:\s*', '', latex)
                eq_type = "formula"
        if latex and latex not in seen_latex:
            seen_latex.add(latex)
            equations.append({"latex": latex, "type": eq_type, "start": m.start(), "end": m.end()})

    # 1. $$...$$ (디스플레이) — 마커 밖의 독립 수식
    for m in re.finditer(r'\$\$(.+?)\$\$', text, re.DOTALL):
        latex = m.group(1).strip()
        if latex and latex not in seen_latex:
            seen_latex.add(latex)
            equations.append({"latex": latex, "type": "display", "start": m.start(), "end": m.end()})

    # 2. $...$ (인라인) — 마커 밖의 독립 수식
    for m in re.finditer(r'(?<!\$)\$([^\$]{3,200})\$(?!\$)', text):
        latex = m.group(1).strip()
        if latex and latex not in seen_latex:
            seen_latex.add(latex)
            equations.append({"latex": latex, "type": "inline", "start": m.start(), "end": m.end()})

    # 3. \begin{equation}...\end{equation}
    for m in re.finditer(r'\\begin\{equation\}(.+?)\\end\{equation\}', text, re.DOTALL):
        latex = m.group(1).strip()
        if latex and latex not in seen_latex:
            seen_latex.add(latex)
            equations.append({"latex": latex, "type": "display", "start": m.start(), "end": m.end()})

    # 4. 수식 기호 패턴 (=, ∝, ≈ 포함 행)
    for m in re.finditer(r'([A-Za-z_\\][^\n]{5,100}(?:=|∝|≈|\\approx|\\propto)[^\n]{3,100})', text):
        eq_text = m.group(1).strip()
        if len(eq_text) > 10 and eq_text not in seen_latex:
            seen_latex.add(eq_text)
            equations.append({"latex": eq_text, "type": "formula", "start": m.start(), "end": m.end()})

    return equations

def _classify_equation(latex_str):
    """수식을 도메인 사전과 매칭하여 분류"""
    latex_lower = latex_str.lower()
    for eq_id, eq_info in PLASMA_EQUATIONS.items():
        for pattern in eq_info["patterns"]:
            if re.search(pattern, latex_str, re.IGNORECASE):
                return {
                    "id": eq_id,
                    "name": eq_info["name"],
                    "category": eq_info["category"],
                    "category_label": EQUATION_CATEGORIES.get(eq_info["category"], {}).get("label", "기타"),
                    "description": eq_info["description"]
                }
    return {"id": "unknown", "name": None, "category": "other",
            "category_label": EQUATION_CATEGORIES["other"]["label"], "description": None}


def extract_equations():
    """컬렉션 문서에서 수식 추출 (전체 청크 대상, chunk_type 활용)"""
    try:
        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, equations=[], stats={})
            return

        # 스키마 확인: chunk_type 필드가 있으면 formula 타입만 효율적 조회
        schema_fields = _get_collection_fields(client, collection_name)
        has_chunk_type = "chunk_type" in schema_fields

        if has_chunk_type:
            # 신 스키마: formula 타입 청크 직접 조회
            formula_chunks = _query_all_chunks(
                client, collection_name,
                filter_expr='chunk_type == "formula"',
                output_fields=["doc_id", "filename", "text"]
            )
            # 추가: 나머지 청크에서도 수식 마커가 포함된 텍스트 조회
            other_chunks = _query_all_chunks(
                client, collection_name,
                filter_expr='chunk_type != "formula"',
                output_fields=["doc_id", "filename", "text"]
            )
            doc_chunks = formula_chunks + [c for c in other_chunks if "[EQUATION:" in c.get("text", "") or "$$" in c.get("text", "")]
        else:
            # 구 스키마: 전체 청크 조회 후 수식 포함 여부 확인
            doc_chunks = _query_all_chunks(
                client, collection_name,
                filter_expr="chunk_index >= 0",
                output_fields=["doc_id", "filename", "text"]
            )

        # 총 문서 수 (통계용)
        try:
            all_doc0 = client.query(collection_name=collection_name,
                                    filter="chunk_index == 0",
                                    output_fields=["doc_id"], limit=16000)
            total_docs = len(all_doc0)
        except Exception:
            total_docs = 0

        all_equations = []
        doc_eq_count = Counter()
        category_count = Counter()

        for chunk in doc_chunks:
            text = chunk.get("text", "")
            filename = chunk.get("filename", "")
            doc_id = chunk.get("doc_id", "")
            eqs = _extract_latex_equations(text)
            for eq in eqs:
                classification = _classify_equation(eq["latex"])
                context_start = max(0, eq["start"] - 200)
                context_end = min(len(text), eq["end"] + 200)
                context = text[context_start:context_end]
                all_equations.append({
                    "latex": eq["latex"],
                    "type": eq["type"],
                    "filename": filename,
                    "doc_id": doc_id,
                    "context": context,
                    "classification": classification
                })
                doc_eq_count[filename] += 1
                category_count[classification["category"]] += 1

        stats = {
            "total_equations": len(all_equations),
            "total_docs_with_eq": len(doc_eq_count),
            "total_docs": total_docs,
            "by_category": {cat: {"count": cnt, "label": EQUATION_CATEGORIES.get(cat, {}).get("label", cat)}
                          for cat, cnt in category_count.most_common()},
            "top_docs": [{"filename": fn, "count": cnt} for fn, cnt in doc_eq_count.most_common(10)]
        }

        wiz.response.status(200, equations=all_equations[:200], stats=stats)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def search_equations():
    """수식 기반 유사 문서 검색"""
    try:
        query_eq = wiz.request.query("equation", "").strip()
        if not query_eq:
            wiz.response.status(400, message="검색할 수식을 입력하세요.")
            return

        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        model = _get_model(model_name)

        # 수식 문자열 + 컨텍스트 임베딩 검색
        search_text = f"equation formula {query_eq}"
        query_vec = model.encode([search_text], normalize_embeddings=True)[0].tolist()

        results = client.search(
            collection_name=collection_name,
            data=[query_vec],
            limit=30,
            output_fields=["doc_id", "filename", "chunk_index", "text"],
            search_params={"metric_type": "COSINE"}
        )

        # 수식 분류
        query_classification = _classify_equation(query_eq)

        # 결과에서 수식 포함 여부 필터링 + 정렬
        matched_docs = {}
        for hit in results[0]:
            entity = hit.get("entity", {})
            text = entity.get("text", "")
            doc_id = entity.get("doc_id", "")
            filename = entity.get("filename", "")
            score = hit.get("distance", 0)

            # 문서 내 수식 추출
            doc_eqs = _extract_latex_equations(text)
            has_equation = len(doc_eqs) > 0

            if doc_id not in matched_docs:
                matched_docs[doc_id] = {
                    "doc_id": doc_id,
                    "filename": filename,
                    "score": round(score, 4),
                    "has_equation": has_equation,
                    "equations": [],
                    "snippet": text[:250]
                }

            for eq in doc_eqs:
                cls = _classify_equation(eq["latex"])
                matched_docs[doc_id]["equations"].append({
                    "latex": eq["latex"][:200],
                    "classification": cls
                })

        # 수식 있는 문서 우선 정렬
        result_list = sorted(matched_docs.values(),
                           key=lambda x: (-int(x["has_equation"]), -x["score"]))

        wiz.response.status(200,
            results=result_list[:20],
            query_classification=query_classification,
            total=len(result_list))
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def equation_stats():
    """컬렉션 수식 통계 (전체 청크 대상)"""
    try:
        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, stats={})
            return

        # 스키마 확인
        schema_fields = _get_collection_fields(client, collection_name)
        has_chunk_type = "chunk_type" in schema_fields

        if has_chunk_type:
            formula_chunks = _query_all_chunks(
                client, collection_name,
                filter_expr='chunk_type == "formula"',
                output_fields=["doc_id", "filename", "text"]
            )
            other_chunks = _query_all_chunks(
                client, collection_name,
                filter_expr='chunk_type != "formula"',
                output_fields=["doc_id", "filename", "text"]
            )
            doc_chunks = formula_chunks + [c for c in other_chunks if "[EQUATION:" in c.get("text", "") or "$$" in c.get("text", "")]
        else:
            doc_chunks = _query_all_chunks(
                client, collection_name,
                filter_expr="chunk_index >= 0",
                output_fields=["doc_id", "filename", "text"]
            )

        category_count = Counter()
        known_eq_count = Counter()
        docs_with_eq = set()
        total_eqs = 0

        for chunk in doc_chunks:
            text = chunk.get("text", "")
            eqs = _extract_latex_equations(text)
            if eqs:
                docs_with_eq.add(chunk.get("doc_id", ""))
            total_eqs += len(eqs)
            for eq in eqs:
                cls = _classify_equation(eq["latex"])
                category_count[cls["category"]] += 1
                if cls["id"] != "unknown":
                    known_eq_count[cls["name"]] += 1

        stats = {
            "total_docs": len(doc_chunks),
            "docs_with_equations": len(docs_with_eq),
            "total_equations": total_eqs,
            "by_category": [{
                "category": cat,
                "label": EQUATION_CATEGORIES.get(cat, {}).get("label", cat),
                "color": EQUATION_CATEGORIES.get(cat, {}).get("color", "gray"),
                "count": cnt
            } for cat, cnt in category_count.most_common()],
            "known_equations": [{"name": name, "count": cnt}
                              for name, cnt in known_eq_count.most_common(15)]
        }
        wiz.response.status(200, stats=stats)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# Assumption Consistency Checker
# ==============================================================================
def _extract_assumptions_from_text(text):
    """텍스트에서 가정 추출"""
    found = []
    text_lower = text.lower()

    # 1. 도메인 사전 매칭
    for ass_id, ass_info in ASSUMPTION_DICT.items():
        for pattern in ass_info["patterns"]:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for m in matches:
                # 주변 문장 추출
                start = text.rfind('.', 0, max(0, m.start() - 10))
                start = start + 1 if start >= 0 else max(0, m.start() - 100)
                end = text.find('.', m.end())
                end = end + 1 if end >= 0 else min(len(text), m.end() + 100)
                sentence = text[start:end].strip()

                found.append({
                    "id": ass_id,
                    "name": ass_info["name"],
                    "category": ass_info["category"],
                    "category_label": ASSUMPTION_CATEGORIES.get(ass_info["category"], ass_info["category"]),
                    "sentence": sentence[:300],
                    "contradicts": ass_info["contradicts"]
                })
                break  # 같은 가정은 한 번만

    # 2. 트리거 패턴으로 추가 가정 탐지
    for trigger in ASSUMPTION_TRIGGER_PATTERNS:
        for m in re.finditer(trigger, text, re.IGNORECASE):
            start = text.rfind('.', 0, max(0, m.start() - 10))
            start = start + 1 if start >= 0 else max(0, m.start() - 100)
            end = text.find('.', m.end())
            end = end + 1 if end >= 0 else min(len(text), m.end() + 100)
            sentence = text[start:end].strip()
            if len(sentence) > 15 and not any(sentence == f["sentence"] for f in found):
                found.append({
                    "id": "custom",
                    "name": sentence[:60] + ("..." if len(sentence) > 60 else ""),
                    "category": "custom",
                    "category_label": "기타 가정",
                    "sentence": sentence[:300],
                    "contradicts": []
                })

    return found


def extract_assumptions():
    """문서에서 가정 추출"""
    try:
        collection_name, model_name = _resolve_collection_and_model()
        doc_ids_input = wiz.request.query("doc_ids", "")
        client = _get_client()

        if not client.has_collection(collection_name):
            wiz.response.status(200, documents=[], stats={})
            return

        # 선택된 문서 또는 전체 문서
        if doc_ids_input:
            doc_id_list = [d.strip() for d in doc_ids_input.split(",") if d.strip()]
            filter_expr = " or ".join([f'doc_id == "{did}"' for did in doc_id_list])
        else:
            filter_expr = "chunk_index >= 0"

        chunks = _query_all_chunks(
            client, collection_name,
            filter_expr=filter_expr,
            output_fields=["doc_id", "filename", "text", "chunk_index"]
        )

        # 문서별 가정 추출
        doc_assumptions = defaultdict(lambda: {"filename": "", "assumptions": []})
        all_assumption_counts = Counter()

        for chunk in chunks:
            doc_id = chunk.get("doc_id", "")
            filename = chunk.get("filename", "")
            text = chunk.get("text", "")
            doc_assumptions[doc_id]["filename"] = filename

            assumptions = _extract_assumptions_from_text(text)
            # 중복 제거
            existing_ids = set(a["id"] for a in doc_assumptions[doc_id]["assumptions"])
            for ass in assumptions:
                if ass["id"] not in existing_ids or ass["id"] == "custom":
                    doc_assumptions[doc_id]["assumptions"].append(ass)
                    existing_ids.add(ass["id"])
                    all_assumption_counts[ass["name"]] += 1

        documents = []
        for doc_id, info in doc_assumptions.items():
            documents.append({
                "doc_id": doc_id,
                "filename": info["filename"],
                "assumptions": info["assumptions"],
                "count": len(info["assumptions"])
            })
        documents.sort(key=lambda x: -x["count"])

        stats = {
            "total_docs": len(documents),
            "total_assumptions": sum(d["count"] for d in documents),
            "frequency": [{"name": name, "count": cnt}
                         for name, cnt in all_assumption_counts.most_common(20)]
        }

        wiz.response.status(200, documents=documents, stats=stats)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def check_consistency():
    """선택된 문서들의 가정 간 상충 검사"""
    try:
        collection_name, model_name = _resolve_collection_and_model()
        doc_ids_input = wiz.request.query("doc_ids", "")
        if not doc_ids_input:
            wiz.response.status(400, message="비교할 문서 ID를 입력하세요.")
            return

        client = _get_client()
        doc_id_list = [d.strip() for d in doc_ids_input.split(",") if d.strip()]

        # 문서별 가정 추출
        doc_assumptions = {}
        for did in doc_id_list:
            chunks = client.query(
                collection_name=collection_name,
                filter=f'doc_id == "{did}"',
                output_fields=["doc_id", "filename", "text"],
                limit=20
            )
            combined_text = " ".join(c.get("text", "") for c in chunks)
            filename = chunks[0].get("filename", "") if chunks else ""
            assumptions = _extract_assumptions_from_text(combined_text)
            # 중복 제거
            seen = set()
            unique_ass = []
            for a in assumptions:
                if a["id"] not in seen:
                    seen.add(a["id"])
                    unique_ass.append(a)
            doc_assumptions[did] = {"filename": filename, "assumptions": unique_ass}

        # 상충 검사
        conflicts = []
        doc_pairs = list(combinations(doc_id_list, 2))
        for did1, did2 in doc_pairs:
            ass1 = doc_assumptions.get(did1, {}).get("assumptions", [])
            ass2 = doc_assumptions.get(did2, {}).get("assumptions", [])
            fn1 = doc_assumptions.get(did1, {}).get("filename", "")
            fn2 = doc_assumptions.get(did2, {}).get("filename", "")

            for a1 in ass1:
                for a2 in ass2:
                    if a2["id"] in a1.get("contradicts", []):
                        severity = "critical" if a1["category"] == a2["category"] else "warning"
                        conflicts.append({
                            "doc_a": {"doc_id": did1, "filename": fn1, "assumption": a1},
                            "doc_b": {"doc_id": did2, "filename": fn2, "assumption": a2},
                            "severity": severity,
                            "description": f"'{a1['name']}'과(와) '{a2['name']}'은(는) "
                                         f"동일 조건에서 양립할 수 없는 가정입니다."
                        })

        # 호환성 매트릭스
        all_assumption_ids = set()
        for did, info in doc_assumptions.items():
            for a in info["assumptions"]:
                if a["id"] != "custom":
                    all_assumption_ids.add(a["id"])

        matrix = []
        ass_list = sorted(all_assumption_ids)
        for a_id in ass_list:
            row = {"id": a_id, "name": ASSUMPTION_DICT.get(a_id, {}).get("name", a_id), "cells": []}
            for b_id in ass_list:
                if a_id == b_id:
                    row["cells"].append({"id": b_id, "relation": "self"})
                elif b_id in ASSUMPTION_DICT.get(a_id, {}).get("contradicts", []):
                    row["cells"].append({"id": b_id, "relation": "conflict"})
                elif ASSUMPTION_DICT.get(a_id, {}).get("category") == ASSUMPTION_DICT.get(b_id, {}).get("category"):
                    row["cells"].append({"id": b_id, "relation": "same_category"})
                else:
                    row["cells"].append({"id": b_id, "relation": "neutral"})
            matrix.append(row)

        wiz.response.status(200,
            documents=doc_assumptions,
            conflicts=conflicts,
            matrix=matrix,
            matrix_labels=ass_list,
            total_conflicts=len(conflicts))
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def assumption_stats():
    """컬렉션 전체 가정 통계 (전체 청크 대상)"""
    try:
        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, stats={})
            return

        chunks = _query_all_chunks(
            client, collection_name,
            filter_expr="chunk_index >= 0",
            output_fields=["doc_id", "filename", "text"]
        )

        assumption_count = Counter()
        category_count = Counter()
        docs_with_assumptions = set()

        for chunk in chunks:
            text = chunk.get("text", "")
            assumptions = _extract_assumptions_from_text(text)
            if assumptions:
                docs_with_assumptions.add(chunk.get("doc_id", ""))
            for a in assumptions:
                assumption_count[a["name"]] += 1
                category_count[a["category_label"]] += 1

        stats = {
            "total_docs": len(chunks),
            "docs_with_assumptions": len(docs_with_assumptions),
            "total_assumptions": sum(assumption_count.values()),
            "by_name": [{"name": n, "count": c} for n, c in assumption_count.most_common(20)],
            "by_category": [{"category": cat, "count": cnt} for cat, cnt in category_count.most_common()]
        }
        wiz.response.status(200, stats=stats)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# Theory Knowledge Graph
# ==============================================================================
def _build_graph_from_texts(texts, filenames, doc_ids):
    """텍스트에서 Knowledge Graph 구축"""
    nodes = {}
    edges = []
    edge_set = set()

    def add_node(node_id, label, node_type, source_doc=""):
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id, "label": label, "type": node_type,
                "docs": set(), "degree": 0
            }
        if source_doc:
            nodes[node_id]["docs"].add(source_doc)

    def add_edge(source, target, relation, doc=""):
        key = (source, target, relation)
        if key not in edge_set:
            edge_set.add(key)
            edges.append({"source": source, "target": target, "relation": relation, "doc": doc})
            if source in nodes:
                nodes[source]["degree"] += 1
            if target in nodes:
                nodes[target]["degree"] += 1

    for idx, text in enumerate(texts):
        filename = filenames[idx] if idx < len(filenames) else ""
        text_lower = text.lower()

        # 1. 개념 노드 추출
        for concept in PLASMA_CONCEPTS:
            if concept.lower() in text_lower:
                cid = f"concept:{concept.lower().replace(' ', '_')}"
                add_node(cid, concept, "concept", filename)

        # 2. 수식 노드 추출
        eqs = _extract_latex_equations(text)
        for eq in eqs:
            cls = _classify_equation(eq["latex"])
            if cls["id"] != "unknown":
                eq_id = f"equation:{cls['id']}"
                add_node(eq_id, cls["name"], "equation", filename)

                # 수식 주변 개념과 연결
                context_start = max(0, eq["start"] - 300)
                context_end = min(len(text), eq["end"] + 300)
                context = text[context_start:context_end].lower()
                for concept in PLASMA_CONCEPTS:
                    if concept.lower() in context:
                        cid = f"concept:{concept.lower().replace(' ', '_')}"
                        add_node(cid, concept, "concept", filename)
                        add_edge(cid, eq_id, "uses", filename)

        # 3. 가정 노드 추출
        assumptions = _extract_assumptions_from_text(text)
        for ass in assumptions:
            if ass["id"] != "custom":
                aid = f"condition:{ass['id']}"
                add_node(aid, ass["name"], "condition", filename)
                # 가정 상충 관계
                for contra in ass.get("contradicts", []):
                    contra_id = f"condition:{contra}"
                    if contra_id in nodes:
                        add_edge(aid, contra_id, "contradicts", filename)

        # 4. 인과 관계 추출
        for pattern, rel_type in CAUSAL_PATTERNS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                groups = m.groups()
                if len(groups) >= 2:
                    src_text = groups[0].strip()[:40]
                    tgt_text = groups[1].strip()[:40]
                    if len(src_text) > 3 and len(tgt_text) > 3:
                        src_id = f"concept:{src_text.lower().replace(' ', '_')}"
                        tgt_id = f"concept:{tgt_text.lower().replace(' ', '_')}"
                        add_node(src_id, src_text, "concept", filename)
                        add_node(tgt_id, tgt_text, "concept", filename)
                        add_edge(src_id, tgt_id, rel_type, filename)

    # docs set -> list 변환
    for nid in nodes:
        nodes[nid]["docs"] = list(nodes[nid]["docs"])

    return list(nodes.values()), edges


def build_theory_graph():
    """이론 그래프 구축 (전체 청크 대상)"""
    try:
        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, nodes=[], edges=[], message="컬렉션이 없습니다.")
            return

        # 전체 청크 조회 (수식·가정·개념이 어디에든 있을 수 있음)
        chunks = _query_all_chunks(
            client, collection_name,
            filter_expr="chunk_index >= 0",
            output_fields=["doc_id", "filename", "text"]
        )

        texts = [c.get("text", "") for c in chunks]
        filenames = [c.get("filename", "") for c in chunks]
        doc_ids = [c.get("doc_id", "") for c in chunks]

        nodes, edges = _build_graph_from_texts(texts, filenames, doc_ids)

        # degree가 0인 고립 노드 제거
        connected_ids = set()
        for e in edges:
            connected_ids.add(e["source"])
            connected_ids.add(e["target"])
        nodes = [n for n in nodes if n["id"] in connected_ids]

        # 캐시 저장
        os.makedirs(THEORY_GRAPH_DIR, exist_ok=True)
        cache_path = os.path.join(THEORY_GRAPH_DIR, f"{collection_name}.json")
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"nodes": nodes, "edges": edges}, f, ensure_ascii=False)

        wiz.response.status(200,
            nodes=nodes, edges=edges,
            stats={"total_nodes": len(nodes), "total_edges": len(edges),
                   "node_types": dict(Counter(n["type"] for n in nodes)),
                   "edge_types": dict(Counter(e["relation"] for e in edges))})
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def get_theory_graph():
    """캐시된 이론 그래프 조회"""
    try:
        collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip()
        cache_path = os.path.join(THEORY_GRAPH_DIR, f"{collection_name}.json")

        if not os.path.exists(cache_path):
            wiz.response.status(200, nodes=[], edges=[], cached=False)
            return

        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        wiz.response.status(200,
            nodes=data.get("nodes", []),
            edges=data.get("edges", []),
            cached=True,
            stats={"total_nodes": len(data.get("nodes", [])),
                   "total_edges": len(data.get("edges", []))})
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def trace_impact():
    """특정 노드의 하류 영향 추적"""
    try:
        node_id = wiz.request.query("node_id", "").strip()
        collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip()

        if not node_id:
            wiz.response.status(400, message="추적할 노드 ID를 입력하세요.")
            return

        cache_path = os.path.join(THEORY_GRAPH_DIR, f"{collection_name}.json")
        if not os.path.exists(cache_path):
            wiz.response.status(200, impacted=[], message="그래프가 없습니다. 먼저 그래프를 구축하세요.")
            return

        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # BFS로 하류 노드 추적
        adjacency = defaultdict(list)
        for e in data.get("edges", []):
            adjacency[e["source"]].append({"target": e["target"], "relation": e["relation"]})

        visited = set()
        queue = [node_id]
        impacted = []
        depth = 0
        max_depth = 5

        while queue and depth < max_depth:
            next_queue = []
            for current in queue:
                if current in visited:
                    continue
                visited.add(current)
                for neighbor in adjacency.get(current, []):
                    tgt = neighbor["target"]
                    if tgt not in visited:
                        # 노드 정보 찾기
                        node_info = next((n for n in data["nodes"] if n["id"] == tgt), None)
                        impacted.append({
                            "id": tgt,
                            "label": node_info["label"] if node_info else tgt,
                            "type": node_info["type"] if node_info else "unknown",
                            "relation": neighbor["relation"],
                            "depth": depth + 1,
                            "from": current
                        })
                        next_queue.append(tgt)
            queue = next_queue
            depth += 1

        wiz.response.status(200, source=node_id, impacted=impacted, total=len(impacted))
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def search_graph():
    """그래프 내 노드 검색"""
    try:
        query = wiz.request.query("query", "").strip()
        collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip()

        if not query:
            wiz.response.status(400, message="검색어를 입력하세요.")
            return

        cache_path = os.path.join(THEORY_GRAPH_DIR, f"{collection_name}.json")
        if not os.path.exists(cache_path):
            wiz.response.status(200, results=[], message="그래프가 없습니다.")
            return

        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        query_lower = query.lower()
        matched = []
        for node in data.get("nodes", []):
            if query_lower in node.get("label", "").lower() or query_lower in node.get("id", "").lower():
                # 연결된 엣지 찾기
                connected = [e for e in data.get("edges", [])
                           if e["source"] == node["id"] or e["target"] == node["id"]]
                matched.append({**node, "connected_edges": len(connected)})

        matched.sort(key=lambda x: -x.get("degree", 0))
        wiz.response.status(200, results=matched[:20], total=len(matched))
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))
