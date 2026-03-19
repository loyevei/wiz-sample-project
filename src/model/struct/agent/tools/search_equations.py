# =============================================================================
# search_equations Tool — 수식 검색 (chunk_type=='equation' 또는 [EQUATION:] 마커)
# =============================================================================
import os
import sys
import json
import re

from base_tool import BaseTool


class SearchEquationsTool(BaseTool):
    name = "search_equations"
    description = "Search for mathematical equations and formulas in the plasma research database. Returns LaTeX equations with context. Use this when the user asks about specific formulas, mathematical relationships, or theoretical equations."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query related to equations (e.g., 'Boltzmann equation', 'electron density formula', 'Debye length')"
            },
            "collection": {
                "type": "string",
                "description": "Collection name. Default: plasma_papers"
            },
            "limit": {
                "type": "integer",
                "description": "Max equations to return (1-20). Default: 10"
            }
        },
        "required": ["query"]
    }

    def execute(self, query="", collection="", limit=10, **kwargs):
        from sentence_transformers import SentenceTransformer
        from pymilvus import MilvusClient

        MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        META_PATH = "/opt/app/data/collection_meta.json"
        DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

        if not query.strip():
            return "Error: query is required"
        if not collection:
            collection = self.ctx.get("collection", "") or "plasma_papers"
        limit = max(1, min(20, int(limit)))

        # 모델
        model_name = DEFAULT_MODEL
        try:
            if os.path.exists(META_PATH):
                with open(META_PATH, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                info = meta.get(collection, {})
                if info.get("model"):
                    model_name = info["model"]
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

        # 수식 관련 쿼리로 검색
        eq_queries = [
            f"{query} equation formula",
            f"{query} 수식 공식 방정식"
        ]

        all_equations = []
        seen = set()

        for eq_q in eq_queries:
            query_vec = model.encode(eq_q).tolist()
            results = client.search(
                collection_name=collection,
                data=[query_vec],
                limit=min(limit * 3, 50),
                output_fields=["doc_id", "filename", "text", "chunk_index", "chunk_type"],
                search_params={"metric_type": "COSINE"}
            )

            if not results or not results[0]:
                continue

            for hit in results[0]:
                entity = hit.get("entity", {})
                text = entity.get("text", "")
                chunk_type = entity.get("chunk_type", "")
                doc_id = entity.get("doc_id", "")
                chunk_idx = entity.get("chunk_index", 0)
                key = f"{doc_id}_{chunk_idx}"
                if key in seen:
                    continue

                # 수식 포함 여부 확인
                has_equation = False
                if chunk_type == "equation":
                    has_equation = True
                elif "[EQUATION:" in text:
                    has_equation = True
                elif re.search(r'(?:\\frac|\\int|\\sum|\\partial|\\nabla|\\alpha|\\beta|\\gamma|=.*[a-zA-Z])', text):
                    has_equation = True

                if has_equation:
                    seen.add(key)
                    all_equations.append({
                        "filename": entity.get("filename", "unknown"),
                        "text": text[:600],
                        "score": hit.get("distance", 0),
                        "chunk_type": chunk_type
                    })

        # 정렬 & 제한
        all_equations.sort(key=lambda x: x["score"], reverse=True)
        all_equations = all_equations[:limit]

        if not all_equations:
            return f"No equations found for '{query}' in collection '{collection}'. Try a broader search term."

        lines = [f"Found {len(all_equations)} equation(s) related to '{query}':\n"]
        for i, eq in enumerate(all_equations, 1):
            lines.append(f"--- Equation {i} (score: {eq['score']:.4f}) ---")
            lines.append(f"File: {eq['filename']}")
            lines.append(f"Text: {eq['text']}\n")

        return "\n".join(lines)


Tool = SearchEquationsTool
