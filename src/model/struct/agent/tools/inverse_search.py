# =============================================================================
# inverse_search Tool — 목표 결과 → 공정 조건 역추적
# =============================================================================
import os
import sys
import json
import re
import numpy as np
from collections import Counter, defaultdict

from base_tool import BaseTool

PARAM_PATTERNS = {
    "pressure": {"label": "압력 (Pressure)", "category": "condition", "base_unit": "mTorr",
        "patterns": [(r'(\d+\.?\d*)\s*mTorr', "mTorr"), (r'(\d+\.?\d*)\s*Torr\b', "Torr"),
                     (r'(\d+\.?\d*)\s*Pa\b', "Pa"), (r'(\d+\.?\d*)\s*kPa\b', "kPa")]},
    "rf_power": {"label": "RF 전력 (Power)", "category": "condition", "base_unit": "W",
        "patterns": [(r'(\d+\.?\d*)\s*kW\b', "kW"), (r'(\d+\.?\d*)\s*W\b', "W")]},
    "gas_flow": {"label": "가스 유량 (Gas Flow)", "category": "condition", "base_unit": "sccm",
        "patterns": [(r'(\d+\.?\d*)\s*sccm\b', "sccm"), (r'(\d+\.?\d*)\s*slm\b', "slm")]},
    "temperature": {"label": "온도 (Temperature)", "category": "condition", "base_unit": "°C",
        "patterns": [(r'(\d+\.?\d*)\s*°C', "°C"), (r'(\d+\.?\d*)\s*℃', "°C"), (r'(\d+\.?\d*)\s*K\b', "K")]},
    "frequency": {"label": "주파수 (Frequency)", "category": "condition", "base_unit": "MHz",
        "patterns": [(r'(\d+\.?\d*)\s*MHz\b', "MHz"), (r'(\d+\.?\d*)\s*kHz\b', "kHz")]},
    "bias_voltage": {"label": "바이어스 전압 (Bias)", "category": "condition", "base_unit": "V",
        "patterns": [(r'(?:bias|Vdc|Vpp)\s*(?:voltage)?\s*(?:of|=|:|\s)*[-]?\s*(\d+\.?\d*)\s*V\b', "V")]},
}

UNIT_CONVERSIONS = {
    ("Torr", "mTorr"): ("multiply", 1000.0), ("Pa", "mTorr"): ("multiply", 7.50062),
    ("kPa", "mTorr"): ("multiply", 7500.62), ("kW", "W"): ("multiply", 1000.0),
    ("slm", "sccm"): ("multiply", 1000.0), ("K", "°C"): ("add", -273.15),
    ("kHz", "MHz"): ("multiply", 0.001),
}

GAS_SPECIES = [
    "Ar", "O2", "N2", "H2", "He", "CF4", "C4F8", "C4F6", "CHF3", "CH2F2",
    "SF6", "Cl2", "BCl3", "HBr", "SiH4", "NH3", "N2O", "CO2",
]


def _convert(value, unit, base_unit):
    if unit == base_unit:
        return value
    key = (unit, base_unit)
    if key in UNIT_CONVERSIONS:
        op, factor = UNIT_CONVERSIONS[key]
        return value + factor if op == "add" else value * factor
    return value


def _extract_conditions(text):
    extracted = {}
    for pk, pinfo in PARAM_PATTERNS.items():
        vals = []
        for pattern, norm_unit in pinfo["patterns"]:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    val = float(m.group(1))
                    if val <= 0 or val >= 1e8:
                        continue
                    unit = norm_unit if norm_unit else pinfo["base_unit"]
                    base_val = _convert(val, unit, pinfo["base_unit"])
                    vals.append({"value": round(base_val, 4), "unit": pinfo["base_unit"],
                                 "raw": f"{val} {unit}"})
                except (ValueError, IndexError):
                    pass
        if vals:
            seen = set()
            unique = [v for v in vals if (k := f"{v['value']}") not in seen and not seen.add(k)]
            extracted[pk] = unique
    found_gases = [g for g in GAS_SPECIES if re.search(r'\b' + re.escape(g) + r'\b', text)]
    if found_gases:
        extracted["gas_species"] = found_gases
    return extracted


class InverseSearchTool(BaseTool):
    name = "inverse_search"
    description = "Given a target result (e.g., 'etch rate 500 nm/min with high uniformity'), search similar literature and reverse-engineer the process conditions that achieve it. Returns recommended condition ranges with weighted statistics and confidence score."
    input_schema = {
        "type": "object",
        "properties": {
            "target_text": {
                "type": "string",
                "description": "Target result description (e.g., 'SiO2 etch rate above 300 nm/min with selectivity > 10:1')"
            },
            "collection": {
                "type": "string",
                "description": "Collection name. Default: plasma_papers"
            },
            "top_k": {
                "type": "integer",
                "description": "Number of chunks to search (default: 30)"
            }
        },
        "required": ["target_text"]
    }

    def execute(self, target_text="", collection="", top_k=30, **kwargs):
        from sentence_transformers import SentenceTransformer
        from pymilvus import MilvusClient

        MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        META_PATH = "/opt/app/data/collection_meta.json"
        DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

        if not target_text.strip():
            return "Error: target_text is required."
        if not collection:
            collection = self.ctx.get("collection", "") or "plasma_papers"
        top_k = int(top_k) if top_k else 30

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

        vec = model.encode([target_text], normalize_embeddings=True)[0].tolist()
        results = client.search(collection_name=collection, data=[vec], limit=top_k,
                                output_fields=["doc_id", "filename", "text"],
                                search_params={"metric_type": "COSINE"})

        if not results or not results[0]:
            return f"No results found for: {target_text}"

        condition_data = defaultdict(list)
        evidence_docs = []
        seen_docs = set()
        all_scores = []

        for hit in results[0]:
            entity = hit.get("entity", {})
            doc_id = entity.get("doc_id", "")
            score = hit.get("distance", 0)
            text = entity.get("text", "")
            all_scores.append(score)

            conditions = _extract_conditions(text)
            for pk, vals in conditions.items():
                if pk == "gas_species":
                    for g in vals:
                        condition_data["gas_species"].append({"value": g, "score": score})
                else:
                    for v in vals:
                        condition_data[pk].append({"value": v["value"], "unit": v["unit"],
                                                    "score": score, "doc_id": doc_id})

            if doc_id not in seen_docs:
                seen_docs.add(doc_id)
                evidence_docs.append({"filename": entity.get("filename", ""),
                                       "score": round(score, 4), "text": text[:200]})

        if not condition_data:
            return f"Found {len(results[0])} chunks but no extractable process conditions."

        lines = [f"역추적 결과 (목표: {target_text[:60]})\n"]

        # Condition ranges
        lines.append("## 추천 공정 조건 범위")
        n_params = 0
        for pk, entries in condition_data.items():
            if pk == "gas_species":
                gas_counter = Counter(e["value"] for e in entries)
                top_gases = [g for g, _ in gas_counter.most_common(5)]
                lines.append(f"  가스 종류: {', '.join(top_gases)} (총 {len(entries)}건)")
                n_params += 1
                continue

            values = np.array([e["value"] for e in entries])
            scores = np.array([e["score"] for e in entries])
            if len(values) == 0:
                continue

            w_mean = float(np.average(values, weights=scores)) if scores.sum() > 0 else float(values.mean())
            w_std = float(np.sqrt(np.average((values - w_mean)**2, weights=scores))) if len(values) > 1 else 0
            unit = entries[0]["unit"]
            label = PARAM_PATTERNS.get(pk, {}).get("label", pk)

            rec_low = round(max(float(values.min()), w_mean - w_std), 2)
            rec_high = round(min(float(values.max()), w_mean + w_std), 2)

            lines.append(f"  {label}: {rec_low} ~ {rec_high} {unit} (평균: {round(w_mean,2)}, 샘플: {len(values)}건)")
            n_params += 1

        # Confidence
        n_docs = len(seen_docs)
        avg_score = float(np.mean(all_scores)) if all_scores else 0
        confidence = round(min(1.0, n_docs / 5) * 0.4 + min(1.0, n_params / 4) * 0.3 + avg_score * 0.3, 3)
        lines.append(f"\n신뢰도: {confidence} (근거 문서 {n_docs}건, 추출 파라미터 {n_params}종)")

        # Evidence
        lines.append(f"\n## 근거 문헌 (상위 {min(5, len(evidence_docs))}건)")
        for i, doc in enumerate(evidence_docs[:5]):
            lines.append(f"  [{i+1}] {doc['filename']} (유사도: {doc['score']})")
            lines.append(f"      {doc['text'][:150]}...")

        return "\n".join(lines)

Tool = InverseSearchTool
