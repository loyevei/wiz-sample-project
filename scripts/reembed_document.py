import argparse
import importlib.util
import os
import sys
import tempfile


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMBEDDING_API_PATH = os.path.join(PROJECT_ROOT, "src", "app", "page.embedding", "api.py")


def _load_embedding_module():
    spec = importlib.util.spec_from_file_location("page_embedding_api", EMBEDDING_API_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Re-embed one document in a Milvus collection using the current embedding pipeline."
    )
    parser.add_argument("--collection", required=True, help="Target Milvus collection name")
    parser.add_argument("--doc-id", dest="doc_id", help="Document id to update")
    parser.add_argument("--filename", help="Filename to locate when doc_id is unknown")
    parser.add_argument("--pdf", help="Original PDF path. If omitted, existing stored chunks are re-embedded in place")
    parser.add_argument("--model", help="Embedding model name override")
    parser.add_argument("--chunk-strategy", default="semantic_section", help="Chunk strategy when --pdf is provided")
    parser.add_argument("--chunk-size", type=int, default=500, help="Chunk size when --pdf is provided")
    parser.add_argument("--chunk-overlap", type=int, default=100, help="Chunk overlap when --pdf is provided")
    parser.add_argument("--similarity-threshold", type=float, default=0.5, help="Similarity threshold for semantic_embedding strategy")
    parser.add_argument("--respect-sentences", action="store_true", default=True, help="Respect sentence boundaries when chunking PDF input")
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without deleting/inserting records")
    return parser.parse_args()


def _require_identifier(args):
    if args.doc_id or args.filename:
        return
    raise SystemExit("Either --doc-id or --filename is required.")


def _query_existing_rows(module, client, collection, doc_id=None, filename=None):
    output_fields = [
        "id", "doc_id", "filename", "chunk_index", "chunk_type", "page_num",
        "section_title", "text", "content_elements", "structured_content"
    ]

    if doc_id:
        filter_expr = f'doc_id == "{doc_id}"'
    else:
        filter_expr = f'filename == "{filename}"'

    rows = client.query(
        collection_name=collection,
        filter=filter_expr,
        output_fields=output_fields,
        limit=16384,
    )
    rows = sorted(rows, key=lambda item: int(item.get("chunk_index", 0)))
    return rows


def _resolve_doc_identity(rows, args):
    if not rows:
        target = args.doc_id or args.filename
        raise SystemExit(f"Document not found: {target}")

    doc_ids = {row.get("doc_id", "") for row in rows if row.get("doc_id", "")}
    if len(doc_ids) > 1:
        raise SystemExit(f"Multiple doc_ids matched. Please use --doc-id explicitly: {sorted(doc_ids)}")

    doc_id = rows[0].get("doc_id", "")
    filename = rows[0].get("filename", "")
    return doc_id, filename


def _build_chunks_from_pdf(module, pdf_path, args):
    extract_result = module._extract_text_from_pdf(pdf_path)
    full_text = extract_result.get("full_text", "")
    if not full_text.strip():
        raise SystemExit("Could not extract text from PDF.")

    chunks = module._chunk_text(
        full_text,
        strategy=args.chunk_strategy,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        respect_sentences=args.respect_sentences,
        similarity_threshold=args.similarity_threshold,
        model_name=args.model,
        pages_data=extract_result.get("pages", []),
    )
    return chunks


def _build_chunks_from_existing(module, rows):
    chunks = []
    for row in rows:
        chunks.append({
            "text": row.get("text", "") or "",
            "chunk_type": row.get("chunk_type", "text") or "text",
            "page_num": int(row.get("page_num", 0) or 0),
            "section_title": row.get("section_title", "") or "",
            "content_elements": row.get("content_elements", "") or "",
            "structured_content": row.get("structured_content", "") or "",
        })

    source_text = "\n\n".join(chunk.get("text", "") for chunk in chunks if chunk.get("text", "").strip())
    return module._enrich_chunks_with_temporal_metadata(chunks, source_text, pages_data=None)


def _detect_extended_fields(module, client, collection):
    try:
        fields = module._get_collection_fields(client, collection)
        return "content_elements" in fields
    except Exception:
        return False


def _encode_chunks(module, chunks, model_name):
    model = module._get_model(model_name)
    texts = [chunk.get("text", "") for chunk in chunks]
    return model.encode(texts, show_progress_bar=False, normalize_embeddings=True)


def _build_records(module, chunks, embeddings, doc_id, filename, has_extended_fields):
    records = []
    for index, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        text = (chunk.get("text", "") or "")[:8000]
        record = {
            "id": f"{doc_id}_{index:04d}",
            "doc_id": doc_id,
            "filename": filename,
            "chunk_index": index,
            "chunk_type": chunk.get("chunk_type", "text") or "text",
            "page_num": int(chunk.get("page_num", 0) or 0),
            "section_title": (chunk.get("section_title", "") or "")[:500],
            "text": text,
            "embedding": emb.tolist(),
        }
        if has_extended_fields:
            if chunk.get("content_elements"):
                record["content_elements"] = (chunk.get("content_elements", "") or "")[:1000]
            else:
                elements = module._detect_content_elements(text)
                record["content_elements"] = module.json.dumps(elements, ensure_ascii=False)[:1000]
            if chunk.get("structured_content"):
                record["structured_content"] = (chunk.get("structured_content", "") or "")[:8000]
            else:
                record["structured_content"] = module._extract_structured_content(text)[:8000]
        records.append(record)
    return records


def _delete_existing_rows(client, collection, doc_id):
    return client.delete(collection_name=collection, filter=f'doc_id == "{doc_id}"')


def main():
    args = _parse_args()
    _require_identifier(args)

    module = _load_embedding_module()
    client = module._get_client()

    if not client.has_collection(args.collection):
        raise SystemExit(f"Collection not found: {args.collection}")

    existing_rows = _query_existing_rows(module, client, args.collection, doc_id=args.doc_id, filename=args.filename)
    doc_id, current_filename = _resolve_doc_identity(existing_rows, args)

    model_name = args.model or module._get_collection_model(args.collection)
    if model_name not in module.MODEL_REGISTRY:
        model_name = module.DEFAULT_MODEL

    if args.pdf:
        pdf_path = os.path.abspath(args.pdf)
        if not os.path.exists(pdf_path):
            raise SystemExit(f"PDF not found: {pdf_path}")
        filename = os.path.basename(pdf_path)
        chunks = _build_chunks_from_pdf(module, pdf_path, args)
    else:
        filename = current_filename
        chunks = _build_chunks_from_existing(module, existing_rows)

    if not chunks:
        raise SystemExit("No chunks generated.")

    has_extended_fields = _detect_extended_fields(module, client, args.collection)
    embeddings = _encode_chunks(module, chunks, model_name)
    records = _build_records(module, chunks, embeddings, doc_id, filename, has_extended_fields)

    preview = records[0].get("text", "")[:240].replace("\n", " | ") if records else ""
    print(f"collection={args.collection}")
    print(f"doc_id={doc_id}")
    print(f"filename={filename}")
    print(f"model={model_name}")
    print(f"existing_chunks={len(existing_rows)}")
    print(f"new_chunks={len(records)}")
    print(f"preview={preview}")

    if args.dry_run:
        print("dry_run=true")
        return

    _delete_existing_rows(client, args.collection, doc_id)
    client.insert(collection_name=args.collection, data=records)
    print("status=reembedded")


if __name__ == "__main__":
    main()