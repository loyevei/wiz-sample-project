import os
import sys
import json

MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
COLLECTION_META_PATH = "/opt/app/data/collection_meta.json"

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

def _get_client():
    from pymilvus import MilvusClient
    if not hasattr(sys, '_milvus_client') or sys._milvus_client is None:
        db_path = MILVUS_URI
        if not db_path.startswith("http"):
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        sys._milvus_client = MilvusClient(uri=db_path)
    return sys._milvus_client

def collections():
    """Milvus 컬렉션 목록 반환 (문서 수, 청크 수 포함)"""
    try:
        client = _get_client()
        col_names = client.list_collections()

        meta = {}
        try:
            if os.path.exists(COLLECTION_META_PATH):
                with open(COLLECTION_META_PATH, "r", encoding="utf-8") as f:
                    meta = json.load(f)
        except Exception:
            pass

        result = []
        for name in col_names:
            info = meta.get(name, {})
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

            result.append({
                "name": name,
                "model": info.get("model", "unknown"),
                "short_name": info.get("short_name", "Unknown"),
                "dim": info.get("dim", 768),
                "total_docs": total_docs,
                "total_chunks": total_chunks
            })
        wiz.response.status(200, collections=result)
    except Exception as e:
        wiz.response.status(200, collections=[])
