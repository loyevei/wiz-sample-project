# =============================================================================
# analyze_parameter_effect Tool — 파라미터 영향 다각도 분석
# =============================================================================
import os
import sys
import json

from base_tool import BaseTool


class AnalyzeParameterEffectTool(BaseTool):
    name = "analyze_parameter_effect"
    description = "Analyze the effect of a specific plasma process parameter by searching literature from 4 directions: effect, increase, decrease, and optimal conditions. Input a parameter name like 'RF power', 'pressure', 'gas flow', etc."
    input_schema = {
        "type": "object",
        "properties": {
            "param_name": {
                "type": "string",
                "description": "Parameter name to analyze (e.g., 'RF power', 'pressure', 'bias voltage', 'gas flow rate', 'substrate temperature')"
            },
            "collection": {
                "type": "string",
                "description": "Collection name. Default: plasma_papers"
            }
        },
        "required": ["param_name"]
    }

    def execute(self, param_name="", collection="", **kwargs):
        from sentence_transformers import SentenceTransformer
        from pymilvus import MilvusClient

        MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        META_PATH = "/opt/app/data/collection_meta.json"
        DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

        if not param_name.strip():
            return "Error: param_name is required."
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

        # 4-direction queries
        queries = {
            "effect": f"{param_name} effect on plasma process",
            "increase": f"{param_name} increase influence result",
            "decrease": f"{param_name} decrease reduction impact",
            "optimal": f"{param_name} optimal condition optimization"
        }

        all_results = []
        for direction, q in queries.items():
            vec = model.encode([q], normalize_embeddings=True)[0].tolist()
            results = client.search(collection_name=collection, data=[vec], limit=8,
                                    output_fields=["doc_id", "filename", "text"],
                                    search_params={"metric_type": "COSINE"})
            for hit in results[0]:
                entity = hit.get("entity", {})
                all_results.append({
                    "direction": direction,
                    "doc_id": entity.get("doc_id", ""),
                    "filename": entity.get("filename", ""),
                    "text": entity.get("text", ""),
                    "score": round(hit.get("distance", 0), 4)
                })

        # Deduplicate and sort
        seen = set()
        unique = []
        for r in sorted(all_results, key=lambda x: x["score"], reverse=True):
            k = f"{r['doc_id']}_{r['text'][:50]}"
            if k not in seen:
                seen.add(k)
                unique.append(r)
            if len(unique) >= 15:
                break

        if not unique:
            return f"No literature found about '{param_name}' effects."

        dir_labels = {"effect": "일반 효과", "increase": "증가 시 영향",
                       "decrease": "감소 시 영향", "optimal": "최적 조건"}

        lines = [f"'{param_name}' 파라미터 영향 분석 (문헌 {len(unique)}건):\n"]

        # Group by direction
        for direction, label in dir_labels.items():
            dir_items = [r for r in unique if r["direction"] == direction]
            if not dir_items:
                continue
            lines.append(f"## {label}")
            for i, r in enumerate(dir_items[:3]):
                lines.append(f"  [{i+1}] {r['filename']} (유사도: {r['score']})")
                lines.append(f"      {r['text'][:200]}...")
            lines.append("")

        return "\n".join(lines)

Tool = AnalyzeParameterEffectTool
