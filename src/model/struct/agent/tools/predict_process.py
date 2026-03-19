# =============================================================================
# predict_process Tool — 공정 조건 → 유사 문헌 기반 결과 예측
# =============================================================================
import os
import sys
import json
import re
import numpy as np

from base_tool import BaseTool

PARAM_PATTERNS = {
    "pressure": {
        "label": "압력 (Pressure)", "category": "condition", "base_unit": "mTorr",
        "patterns": [
            (r'(\d+\.?\d*)\s*mTorr', "mTorr"), (r'(\d+\.?\d*)\s*Torr\b', "Torr"),
            (r'(\d+\.?\d*)\s*Pa\b', "Pa"), (r'(\d+\.?\d*)\s*kPa\b', "kPa"),
            (r'(\d+\.?\d*)\s*mbar\b', "mbar"),
        ]
    },
    "rf_power": {
        "label": "RF 전력 (Power)", "category": "condition", "base_unit": "W",
        "patterns": [(r'(\d+\.?\d*)\s*kW\b', "kW"), (r'(\d+\.?\d*)\s*W\b', "W")]
    },
    "gas_flow": {
        "label": "가스 유량 (Gas Flow)", "category": "condition", "base_unit": "sccm",
        "patterns": [(r'(\d+\.?\d*)\s*sccm\b', "sccm"), (r'(\d+\.?\d*)\s*slm\b', "slm")]
    },
    "temperature": {
        "label": "온도 (Temperature)", "category": "condition", "base_unit": "°C",
        "patterns": [(r'(\d+\.?\d*)\s*°C', "°C"), (r'(\d+\.?\d*)\s*℃', "°C"), (r'(\d+\.?\d*)\s*K\b', "K")]
    },
    "frequency": {
        "label": "주파수 (Frequency)", "category": "condition", "base_unit": "MHz",
        "patterns": [(r'(\d+\.?\d*)\s*MHz\b', "MHz"), (r'(\d+\.?\d*)\s*kHz\b', "kHz"), (r'(\d+\.?\d*)\s*GHz\b', "GHz")]
    },
    "bias_voltage": {
        "label": "바이어스 전압 (Bias)", "category": "condition", "base_unit": "V",
        "patterns": [
            (r'(?:bias|Vdc|Vpp|self[- ]bias)\s*(?:voltage)?\s*(?:of|=|:|\s)*[-\u2212]?\s*(\d+\.?\d*)\s*V\b', "V"),
            (r'[-\u2212](\d+\.?\d*)\s*V\b', "V"),
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
        "patterns": [(r'(?:selectivity)\s*(?:of|=|:|\s)*(?:about|approximately|~)?\s*(\d+\.?\d*)', ":1")]
    },
}

UNIT_CONVERSIONS = {
    ("Torr", "mTorr"): ("multiply", 1000.0), ("Pa", "mTorr"): ("multiply", 7.50062),
    ("kPa", "mTorr"): ("multiply", 7500.62), ("mbar", "mTorr"): ("multiply", 750.062),
    ("kW", "W"): ("multiply", 1000.0), ("slm", "sccm"): ("multiply", 1000.0),
    ("K", "°C"): ("add", -273.15), ("GHz", "MHz"): ("multiply", 1000.0),
    ("kHz", "MHz"): ("multiply", 0.001), ("Å/min", "nm/min"): ("multiply", 0.1),
    ("μm/min", "nm/min"): ("multiply", 1000.0), ("nm/s", "nm/min"): ("multiply", 60.0),
    ("Å/s", "nm/min"): ("multiply", 6.0), ("cm", "mm"): ("multiply", 10.0),
}

GAS_SPECIES = [
    "Ar", "O2", "N2", "H2", "He", "Ne", "Kr", "Xe",
    "CF4", "C4F8", "C4F6", "CHF3", "CH2F2", "C2F6", "NF3",
    "SF6", "Cl2", "BCl3", "HBr", "SiH4", "SiCl4",
    "NH3", "N2O", "CO2", "CO", "CH4", "C2H2",
    "TiCl4", "WF6", "TEOS", "TMA", "TMGa",
]


def _convert_to_base(value, unit, base_unit):
    if unit == base_unit:
        return value
    key = (unit, base_unit)
    if key in UNIT_CONVERSIONS:
        op, factor = UNIT_CONVERSIONS[key]
        return value + factor if op == "add" else value * factor
    return value


def _extract_parameters_from_text(text):
    extracted = {}
    for param_key, pinfo in PARAM_PATTERNS.items():
        values = []
        for pattern, norm_unit in pinfo["patterns"]:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    val = float(m.group(1))
                    if val <= 0 or val >= 1e8:
                        continue
                    unit = norm_unit if norm_unit else (m.group(2) if m.lastindex >= 2 else pinfo["base_unit"])
                    base_val = _convert_to_base(val, unit, pinfo["base_unit"])
                    values.append({"raw_value": val, "raw_unit": unit, "value": round(base_val, 4), "unit": pinfo["base_unit"]})
                except (ValueError, IndexError):
                    pass
        if values:
            seen = set()
            unique = [v for v in values if (k := f"{v['value']}_{v['unit']}") not in seen and not seen.add(k)]
            extracted[param_key] = {"label": pinfo["label"], "category": pinfo["category"], "values": unique}
    found_gases = [g for g in GAS_SPECIES if re.search(r'\b' + re.escape(g) + r'\b', text)]
    if found_gases:
        extracted["gas_species"] = {"label": "가스 종류", "category": "condition",
                                     "values": [{"value": g, "unit": ""} for g in found_gases]}
    return extracted


class PredictProcessTool(BaseTool):
    name = "predict_process"
    description = "Predict plasma process outcomes by searching for similar literature based on given process conditions. Input process type, gas, pressure, power, temperature, substrate, etc. Returns relevant papers with extracted parameters (etch rate, deposition rate, uniformity, selectivity)."
    input_schema = {
        "type": "object",
        "properties": {
            "process_type": {"type": "string", "description": "Process type (e.g., etching, deposition, CVD, PVD, sputtering)"},
            "gas_type": {"type": "string", "description": "Gas species (e.g., CF4, Ar, O2)"},
            "pressure": {"type": "string", "description": "Pressure (e.g., '10 mTorr', '100 Pa')"},
            "power": {"type": "string", "description": "RF power (e.g., '500 W', '1 kW')"},
            "temperature": {"type": "string", "description": "Temperature (e.g., '300 °C')"},
            "substrate": {"type": "string", "description": "Substrate material (e.g., Si, SiO2, GaN)"},
            "target_property": {"type": "string", "description": "Target property to predict (e.g., etch rate, uniformity)"},
            "collection": {"type": "string", "description": "Collection name. Default: plasma_papers"}
        },
        "required": []
    }

    def execute(self, process_type="", gas_type="", pressure="", power="",
                temperature="", substrate="", target_property="", collection="", **kwargs):
        from sentence_transformers import SentenceTransformer
        from pymilvus import MilvusClient

        MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        META_PATH = "/opt/app/data/collection_meta.json"
        DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

        if not collection:
            collection = self.ctx.get("collection", "") or "plasma_papers"

        # Build query
        parts = []
        if process_type: parts.append(f"{process_type} 공정")
        if gas_type: parts.append(f"{gas_type} 가스")
        if pressure: parts.append(f"압력 {pressure}")
        if power: parts.append(f"전력 {power}")
        if temperature: parts.append(f"온도 {temperature}")
        if substrate: parts.append(f"{substrate} 기판")
        if target_property: parts.append(target_property)

        if not parts:
            return "Error: At least one process condition is required."

        query_text = " ".join(parts)

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

        vec = model.encode([query_text], normalize_embeddings=True)[0].tolist()
        results = client.search(collection_name=collection, data=[vec], limit=30,
                                output_fields=["doc_id", "filename", "text"],
                                search_params={"metric_type": "COSINE"})

        if not results or not results[0]:
            return f"No results found for query: {query_text}"

        lines = [f"공정 예측 결과 (쿼리: {query_text})\n"]
        seen_docs = set()
        count = 0

        for hit in results[0]:
            entity = hit.get("entity", {})
            doc_id = entity.get("doc_id", "")
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)

            text = entity.get("text", "")
            params = _extract_parameters_from_text(text)
            score = round(hit.get("distance", 0), 4)

            param_strs = []
            for pk, pdata in params.items():
                if pk == "gas_species":
                    gases = [v["value"] for v in pdata["values"]]
                    param_strs.append(f"가스: {', '.join(gases)}")
                else:
                    for v in pdata["values"][:2]:
                        param_strs.append(f"{pdata['label']}: {v['raw_value']} {v['raw_unit']}")

            lines.append(f"### [{count+1}] {entity.get('filename', 'Unknown')} (유사도: {score})")
            if param_strs:
                lines.append(f"  추출 파라미터: {' | '.join(param_strs)}")
            lines.append(f"  내용: {text[:250]}...\n")

            count += 1
            if count >= 8:
                break

        if count == 0:
            return f"No documents with extractable parameters found for: {query_text}"

        return "\n".join(lines)

Tool = PredictProcessTool
