import os
import sys
import json

MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
COLLECTION_META_PATH = "/opt/app/data/collection_meta.json"

MODEL_REGISTRY = wiz.model("modelregistry").compact()


def _collection_meta_helper():
    return wiz.model("collectionmeta")

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

        meta_helper = _collection_meta_helper()
        result = []
        for name in col_names:
            info = meta_helper.normalize_info(meta.get(name, {}))
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
