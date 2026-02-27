# =============================================================================
# search_papers Tool — Milvus 벡터 검색으로 관련 논문 찾기
# =============================================================================
import os
import sys
import json

from base_tool import BaseTool


class SearchPapersTool(BaseTool):
    name = "search_papers"
    description = "Search the plasma research paper database using semantic similarity. Returns relevant paper chunks with titles, text content, and similarity scores. Use this to find papers related to a specific topic, technique, or research question."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query in natural language (Korean or English). Be specific about the plasma topic."
            },
            "collection": {
                "type": "string",
                "description": "Collection name to search in. Use get_collections tool first to see available collections. Default: plasma_papers"
            },
            "limit": {
                "type": "integer",
                "description": "Number of results to return (1-20). Default: 10"
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
            collection = "plasma_papers"
        limit = max(1, min(20, int(limit)))

        # 컬렉션 모델 결정
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

        # 모델 로드 (캐싱)
        if not hasattr(sys, '_embedding_models') or sys._embedding_models is None:
            sys._embedding_models = {}
        if model_name not in sys._embedding_models:
            sys._embedding_models[model_name] = SentenceTransformer(model_name)
        model = sys._embedding_models[model_name]

        # 클라이언트
        if not hasattr(sys, '_milvus_client') or sys._milvus_client is None:
            sys._milvus_client = MilvusClient(uri=MILVUS_URI)
        client = sys._milvus_client

        if not client.has_collection(collection):
            return f"Error: Collection '{collection}' does not exist. Use get_collections to see available ones."

        # 임베딩 & 검색
        query_vec = model.encode(query).tolist()
        results = client.search(
            collection_name=collection,
            data=[query_vec],
            limit=limit,
            output_fields=["doc_id", "filename", "text", "chunk_index"],
            search_params={"metric_type": "COSINE"}
        )

        if not results or not results[0]:
            return "No results found for the given query."

        # 결과 포맷팅
        output_lines = [f"Found {len(results[0])} results for query: '{query}' in collection '{collection}'\n"]
        for i, hit in enumerate(results[0], 1):
            entity = hit.get("entity", {})
            score = hit.get("distance", 0)
            filename = entity.get("filename", "unknown")
            text = entity.get("text", "")
            chunk_idx = entity.get("chunk_index", 0)
            # 텍스트 축약
            if len(text) > 500:
                text = text[:500] + "..."
            output_lines.append(f"--- Result {i} (score: {score:.4f}) ---")
            output_lines.append(f"File: {filename} | Chunk: {chunk_idx}")
            output_lines.append(f"Text: {text}\n")

        return "\n".join(output_lines)


Tool = SearchPapersTool
