# =============================================================================
# extract_assumptions Tool — 문헌에서 가정(Assumption) 추출 및 충돌 감지
# =============================================================================
import os
import sys
import json
import re
from collections import Counter

from base_tool import BaseTool

ASSUMPTION_DICT = {
    "quasi_neutrality": {
        "name": "준중성 (Quasi-neutrality)",
        "patterns": [r"quasi.?neutral", r"n_e\s*[≈=~]\s*n_i", r"charge\s+neutrality"],
        "category": "plasma_property", "contradicts": ["non_neutral"]
    },
    "non_neutral": {
        "name": "비중성 (Non-neutral)",
        "patterns": [r"non.?neutral", r"space\s+charge", r"sheath\s+region"],
        "category": "plasma_property", "contradicts": ["quasi_neutrality"]
    },
    "maxwellian_eedf": {
        "name": "Maxwellian EEDF",
        "patterns": [r"Maxwellian\s+EEDF", r"Maxwellian\s+distribution", r"thermal\s+equilibrium.*electron"],
        "category": "distribution", "contradicts": ["non_maxwellian"]
    },
    "non_maxwellian": {
        "name": "Non-Maxwellian EEDF",
        "patterns": [r"non.?Maxwellian", r"bi.?Maxwellian", r"Druyvesteyn", r"EEDF.*deviates?"],
        "category": "distribution", "contradicts": ["maxwellian_eedf"]
    },
    "lte": {
        "name": "LTE (국소 열평형)",
        "patterns": [r"local\s+thermodynamic\s+equilibrium", r"\bLTE\b", r"thermal\s+equilibrium"],
        "category": "equilibrium", "contradicts": ["non_lte"]
    },
    "non_lte": {
        "name": "Non-LTE",
        "patterns": [r"non.?LTE", r"non.?equilibrium", r"out\s+of\s+equilibrium"],
        "category": "equilibrium", "contradicts": ["lte"]
    },
    "collisionless": {
        "name": "무충돌 (Collisionless)",
        "patterns": [r"collisionless", r"mean\s+free\s+path.*>>"],
        "category": "transport", "contradicts": ["collisional"]
    },
    "collisional": {
        "name": "충돌성 (Collisional)",
        "patterns": [r"collision.?dominated", r"collisional\s+plasma", r"mean\s+free\s+path.*<<"],
        "category": "transport", "contradicts": ["collisionless"]
    },
    "fluid_model": {
        "name": "유체 모델 (Fluid Model)",
        "patterns": [r"fluid\s+model", r"fluid\s+approximation", r"drift.?diffusion"],
        "category": "model_type", "contradicts": ["kinetic_model"]
    },
    "kinetic_model": {
        "name": "운동론 모델 (Kinetic Model)",
        "patterns": [r"kinetic\s+model", r"kinetic\s+theory", r"PIC.*simulation", r"particle.?in.?cell"],
        "category": "model_type", "contradicts": ["fluid_model"]
    },
    "steady_state": {
        "name": "정상 상태 (Steady-state)",
        "patterns": [r"steady.?state", r"time.?independent"],
        "category": "temporal", "contradicts": ["time_dependent"]
    },
    "time_dependent": {
        "name": "시간 의존 (Time-dependent)",
        "patterns": [r"time.?dependent", r"transient", r"pulsed\s+plasma"],
        "category": "temporal", "contradicts": ["steady_state"]
    },
    "ambipolar_diffusion": {
        "name": "양극성 확산 (Ambipolar Diffusion)",
        "patterns": [r"ambipolar\s+diffusion", r"ambipolar\s+transport"],
        "category": "transport", "contradicts": []
    },
    "optically_thin": {
        "name": "광학적 얇은 (Optically Thin)",
        "patterns": [r"optically\s+thin", r"optical\s+depth.*<<"],
        "category": "radiation", "contradicts": ["optically_thick"]
    },
    "optically_thick": {
        "name": "광학적 두꺼운 (Optically Thick)",
        "patterns": [r"optically\s+thick", r"optical\s+depth.*>>", r"radiation\s+trapping"],
        "category": "radiation", "contradicts": ["optically_thin"]
    },
}

ASSUMPTION_CATEGORIES = {
    "plasma_property": "플라즈마 특성", "distribution": "분포 함수",
    "equilibrium": "평형 상태", "transport": "수송 현상",
    "model_type": "모델 유형", "temporal": "시간 의존성", "radiation": "복사"
}

TRIGGER_PATTERNS = [
    r"(?:we\s+)?assum(?:e|ing|ed|ption)", r"under\s+the\s+(?:assumption|condition)",
    r"it\s+is\s+assumed", r"approximat(?:e|ion|ed)", r"neglect(?:ing|ed)?",
    r"가정", r"근사",
]


class ExtractAssumptionsTool(BaseTool):
    name = "extract_assumptions"
    description = "Extract physical assumptions used in plasma physics literature and detect contradicting assumptions across papers. Identifies 15 types of assumptions (quasi-neutrality, Maxwellian EEDF, LTE, fluid/kinetic model, etc.) and flags contradictions."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query to focus assumption extraction (e.g., 'ICP etching simulation'). If empty, scans broadly."
            },
            "collection": {
                "type": "string",
                "description": "Collection name. Default: plasma_papers"
            }
        },
        "required": []
    }

    def execute(self, query="", collection="", **kwargs):
        from sentence_transformers import SentenceTransformer
        from pymilvus import MilvusClient

        MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        META_PATH = "/opt/app/data/collection_meta.json"
        DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

        if not collection:
            collection = "plasma_papers"

        model_name = DEFAULT_MODEL
        try:
            if os.path.exists(META_PATH):
                with open(META_PATH, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get(collection, {}).get("model"):
                    model_name = meta[collection]["model"]
        except Exception:
            pass

        if not hasattr(sys, '_embedding_models') or sys._embedding_models is None:
            sys._embedding_models = {}
        if model_name not in sys._embedding_models:
            sys._embedding_models[model_name] = SentenceTransformer(model_name)
        model = sys._embedding_models[model_name]

        if not hasattr(sys, '_milvus_client') or sys._milvus_client is None:
            sys._milvus_client = MilvusClient(uri=MILVUS_URI)
        client = sys._milvus_client

        if not client.has_collection(collection):
            return f"Error: Collection '{collection}' does not exist."

        # Search
        if query.strip():
            search_text = f"{query} assumption approximation model"
            vec = model.encode([search_text], normalize_embeddings=True)[0].tolist()
            results = client.search(collection_name=collection, data=[vec], limit=40,
                                    output_fields=["doc_id", "filename", "text"],
                                    search_params={"metric_type": "COSINE"})
            chunks = [{"text": h["entity"].get("text",""), "filename": h["entity"].get("filename",""),
                       "doc_id": h["entity"].get("doc_id","")} for h in results[0]]
        else:
            chunks = client.query(collection_name=collection, filter="chunk_index >= 0",
                                  output_fields=["doc_id", "filename", "text"], limit=300)

        # Extract assumptions
        doc_assumptions = {}  # doc_id -> set of assumption_ids
        assumption_docs = {}  # assumption_id -> set of doc_ids
        assumption_details = []
        total_triggers = 0

        for chunk in chunks:
            text = chunk.get("text", "")
            doc_id = chunk.get("doc_id", "")
            filename = chunk.get("filename", "")

            # Check trigger patterns
            has_trigger = any(re.search(tp, text, re.IGNORECASE) for tp in TRIGGER_PATTERNS)
            if has_trigger:
                total_triggers += 1

            # Match assumptions
            for a_id, a_info in ASSUMPTION_DICT.items():
                for p in a_info["patterns"]:
                    if re.search(p, text, re.IGNORECASE):
                        if doc_id not in doc_assumptions:
                            doc_assumptions[doc_id] = set()
                        doc_assumptions[doc_id].add(a_id)

                        if a_id not in assumption_docs:
                            assumption_docs[a_id] = set()
                        assumption_docs[a_id].add(doc_id)

                        # Context extraction
                        m = re.search(p, text, re.IGNORECASE)
                        if m:
                            ctx_s = max(0, m.start() - 100)
                            ctx_e = min(len(text), m.end() + 100)
                            assumption_details.append({
                                "id": a_id, "name": a_info["name"],
                                "category": ASSUMPTION_CATEGORIES.get(a_info["category"], a_info["category"]),
                                "filename": filename, "context": text[ctx_s:ctx_e]
                            })
                        break  # One match per assumption per chunk

        if not assumption_docs:
            return f"No assumptions detected" + (f" for '{query}'" if query else "") + "."

        # Detect contradictions
        contradictions = []
        for doc_id, assumptions in doc_assumptions.items():
            for a_id in assumptions:
                for contra_id in ASSUMPTION_DICT[a_id].get("contradicts", []):
                    if contra_id in assumptions:
                        contradictions.append({
                            "doc_id": doc_id,
                            "assumption_1": ASSUMPTION_DICT[a_id]["name"],
                            "assumption_2": ASSUMPTION_DICT[contra_id]["name"]
                        })

        lines = [f"가정(Assumption) 추출 결과\n"]
        lines.append(f"분석 문서: {len(doc_assumptions)}개, 가정 출현 트리거: {total_triggers}건\n")

        lines.append("## 발견된 가정")
        for a_id, doc_ids in sorted(assumption_docs.items(), key=lambda x: len(x[1]), reverse=True):
            info = ASSUMPTION_DICT[a_id]
            cat = ASSUMPTION_CATEGORIES.get(info["category"], info["category"])
            lines.append(f"  - {info['name']} [{cat}]: {len(doc_ids)}개 문서")

        if contradictions:
            lines.append(f"\n## ⚠️ 가정 충돌 감지 ({len(contradictions)}건)")
            seen_pairs = set()
            for c in contradictions:
                pair = (c["assumption_1"], c["assumption_2"])
                rpair = (c["assumption_2"], c["assumption_1"])
                if pair not in seen_pairs and rpair not in seen_pairs:
                    seen_pairs.add(pair)
                    lines.append(f"  충돌: {c['assumption_1']} ↔ {c['assumption_2']}")

        # Sample contexts
        lines.append(f"\n## 샘플 컨텍스트")
        shown = set()
        for d in assumption_details[:8]:
            if d["id"] not in shown:
                shown.add(d["id"])
                lines.append(f"  [{d['name']}] {d['filename']}")
                lines.append(f"    ...{d['context'][:150]}...")

        return "\n".join(lines)

Tool = ExtractAssumptionsTool
