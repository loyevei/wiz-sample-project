import os
import sys
import json
import traceback

import season.lib.exception

MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
COLLECTION_META_PATH = "/opt/app/data/collection_meta.json"
DATA_DIR = "/opt/app/data"

MODEL_REGISTRY = wiz.model("modelregistry").compact()
DEFAULT_MODEL = wiz.model("modelregistry").default_model()


def _get_client():
    from pymilvus import MilvusClient
    if not hasattr(sys, '_milvus_client') or sys._milvus_client is None:
        db_path = MILVUS_URI
        if not db_path.startswith("http"):
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        sys._milvus_client = MilvusClient(uri=db_path)
    return sys._milvus_client


def _load_collection_meta():
    meta_helper = wiz.model("collectionmeta")
    return meta_helper.load(COLLECTION_META_PATH)


def _save_collection_meta(meta):
    os.makedirs(os.path.dirname(COLLECTION_META_PATH), exist_ok=True)
    with open(COLLECTION_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _count_collection_pdfs(collection_name):
    pdf_dir = os.path.join(DATA_DIR, "pdfs", collection_name)
    if not os.path.isdir(pdf_dir):
        return 0
    try:
        return sum(1 for name in os.listdir(pdf_dir) if name.lower().endswith('.pdf'))
    except Exception:
        return 0


def _infer_model_from_dim(dim):
    registry = wiz.model("modelregistry")
    return registry.infer_model_from_dim(dim, DEFAULT_MODEL)


def collections():
    """전체 컬렉션 목록 + 메타데이터"""
    try:
        client = _get_client()
        col_names = client.list_collections()
        meta = _load_collection_meta()
        meta_helper = wiz.model("collectionmeta")
        meta_updated = False

        result = []
        for name in col_names:
            info = meta_helper.normalize_info(meta.get(name, {}))
            if not info or info.get("short_name") == "Unknown":
                try:
                    col_info = client.describe_collection(name)
                    dim = 768
                    for field in col_info.get("fields", []):
                        if field.get("name") == "embedding":
                            params = field.get("params", {})
                            dim = params.get("dim", field.get("dim", 768))
                            if isinstance(dim, str):
                                dim = int(dim)
                            break
                    inferred_model = _infer_model_from_dim(dim)
                    model_info = MODEL_REGISTRY.get(inferred_model, {})
                    info = {
                        "model": inferred_model,
                        "dim": dim,
                        "created_at": info.get("created_at", ""),
                        "short_name": model_info.get("short_name", inferred_model)
                    }
                    meta[name] = info
                    meta_updated = True
                except Exception:
                    pass

            total_docs = info.get("total_docs")
            if total_docs is None:
                total_docs = _count_collection_pdfs(name)
                info["total_docs"] = total_docs
                meta[name] = info
                meta_updated = True

            total_chunks = info.get("total_chunks")
            if total_chunks is None:
                total_chunks = 0
                try:
                    stats_info = client.get_collection_stats(name)
                    total_chunks = stats_info.get("row_count", 0)
                except Exception:
                    pass
                info["total_chunks"] = total_chunks
                meta[name] = info
                meta_updated = True

            result.append({
                "name": name,
                "model": info.get("model", DEFAULT_MODEL),
                "short_name": info.get("short_name", "Unknown"),
                "dim": info.get("dim", 768),
                "created_at": info.get("created_at", ""),
                "total_chunks": total_chunks,
                "total_docs": total_docs
            })

        if meta_updated:
            _save_collection_meta(meta)
        wiz.response.status(200, collections=result)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))
