# =============================================================================
# search_anomaly Tool — 이상 현상 / 고장 진단 검색
# =============================================================================
import os
import sys
import json

from base_tool import BaseTool


class SearchAnomalyTool(BaseTool):
    name = "search_anomaly"
    description = "Search for plasma process anomalies, failures, or troubleshooting information. Given a symptom or abnormal phenomenon, searches from 4 directions: cause analysis, solution, diagnostic result, and anomaly type. Returns categorized results with relevance scores."
    input_schema = {
        "type": "object",
        "properties": {
            "symptom": {
                "type": "string",
                "description": "Symptom or anomaly description (e.g., 'arcing in chamber', 'non-uniform etch', 'unexpected particle generation', 'plasma instability')"
            },
            "collection": {
                "type": "string",
                "description": "Collection name. Default: plasma_papers"
            }
        },
        "required": ["symptom"]
    }

    def execute(self, symptom="", collection="", **kwargs):
        from sentence_transformers import SentenceTransformer
        from pymilvus import MilvusClient

        MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        META_PATH = "/opt/app/data/collection_meta.json"
        DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

        if not symptom.strip():
            return "Error: symptom is required."
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
        query_map = {
            "원인 분석": f"{symptom} 원인 분석",
            "해결 방법": f"{symptom} 해결 방법",
            "진단 결과": f"{symptom} 진단 결과",
            "이상 현상": f"플라즈마 {symptom} 이상"
        }

        all_results = []
        for direction, q in query_map.items():
            vec = model.encode([q], normalize_embeddings=True)[0].tolist()
            sr = client.search(collection_name=collection, data=[vec], limit=8,
                               output_fields=["doc_id", "filename", "chunk_index", "text"],
                               search_params={"metric_type": "COSINE"})
            for h in sr[0]:
                e = h.get("entity", {})
                all_results.append({
                    "direction": direction, "doc_id": e.get("doc_id", ""),
                    "filename": e.get("filename", ""), "chunk_index": e.get("chunk_index", 0),
                    "text": e.get("text", ""), "score": round(h.get("distance", 0), 4)
                })

        # Deduplicate
        seen, unique = set(), []
        for r in sorted(all_results, key=lambda x: x["score"], reverse=True):
            key = f"{r['doc_id']}_{r['chunk_index']}"
            if key not in seen:
                seen.add(key)
                unique.append(r)
            if len(unique) >= 15:
                break

        if not unique:
            return f"No results found for anomaly: '{symptom}'"

        lines = [f"이상 현상 진단: '{symptom}' (문헌 {len(unique)}건)\n"]

        dir_labels = {"원인 분석": "🔍 원인 분석", "해결 방법": "🔧 해결 방법",
                       "진단 결과": "📊 진단 결과", "이상 현상": "⚠️ 이상 현상"}

        for direction, label in dir_labels.items():
            items = [r for r in unique if r["direction"] == direction]
            if not items:
                continue
            lines.append(f"## {label}")
            for i, r in enumerate(items[:3]):
                lines.append(f"  [{i+1}] {r['filename']} (유사도: {r['score']})")
                lines.append(f"      {r['text'][:200]}...")
            lines.append("")

        return "\n".join(lines)

Tool = SearchAnomalyTool
