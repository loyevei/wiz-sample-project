# =============================================================================
# get_collections Tool — 사용 가능한 Milvus 컬렉션 목록 조회
# =============================================================================
import os
import sys
import json

from base_tool import BaseTool

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


class GetCollectionsTool(BaseTool):
    name = "get_collections"
    description = "List all available Milvus vector database collections with metadata (document count, embedding model, dimensions). Use this first to know which collections are available for searching."
    input_schema = {
        "type": "object",
        "properties": {},
        "required": []
    }

    def execute(self, **kwargs):
        from pymilvus import MilvusClient

        MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        META_PATH = "/opt/app/data/collection_meta.json"

        if not hasattr(sys, '_milvus_client') or sys._milvus_client is None:
            sys._milvus_client = MilvusClient(uri=MILVUS_URI)
        client = sys._milvus_client

        col_names = client.list_collections()
        if not col_names:
            return "No collections found. Please embed PDF documents first using the Embedding page."

        meta = {}
        try:
            if os.path.exists(META_PATH):
                with open(META_PATH, "r", encoding="utf-8") as f:
                    meta = json.load(f)
        except Exception:
            pass

        lines = [f"Available collections ({len(col_names)}):\n"]
        for name in sorted(col_names):
            info = meta.get(name, {})
            model_name = info.get("model", "unknown")
            short_name = info.get("short_name", MODEL_REGISTRY.get(model_name, {}).get("short_name", "Unknown"))
            dim = info.get("dim", "?")

            # 통계
            total_chunks = 0
            total_docs = 0
            try:
                stats = client.get_collection_stats(name)
                total_chunks = stats.get("row_count", 0)
                if total_chunks > 0:
                    docs = client.query(
                        collection_name=name,
                        filter="chunk_index == 0",
                        output_fields=["doc_id"],
                        limit=10000
                    )
                    total_docs = len(docs)
            except Exception:
                pass

            lines.append(f"- **{name}**: {total_docs} documents, {total_chunks} chunks | Model: {short_name} (dim={dim})")

        return "\n".join(lines)


Tool = GetCollectionsTool
