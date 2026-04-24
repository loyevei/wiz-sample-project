import os
import sys
import json
import re
import traceback

from sentence_transformers import SentenceTransformer
from pymilvus import MilvusClient
import season.lib.exception

# ==============================================================================
# 설정
# ==============================================================================
MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
COLLECTION_META_PATH = "/opt/app/data/collection_meta.json"

MODEL_REGISTRY = wiz.model("modelregistry").compact()
DEFAULT_MODEL = wiz.model("modelregistry").default_model()

LATEX_PATTERNS = [
    r'\\frac\b', r'\\int\b', r'\\sum\b', r'\\partial\b', r'\\nabla\b',
    r'\\alpha\b', r'\\beta\b', r'\\gamma\b', r'\\delta\b', r'\\epsilon\b',
    r'\\theta\b', r'\\lambda\b', r'\\mu\b', r'\\sigma\b', r'\\omega\b',
    r'\\infty\b', r'\\sqrt\b', r'\\vec\b', r'\\hat\b', r'\\dot\b',
    r'\\left\b', r'\\right\b', r'\$\$.*?\$\$', r'\\\[.*?\\\]',
]

# ==============================================================================
# 유틸리티
# ==============================================================================
def _get_milvus_client():
    if not hasattr(sys, '_milvus_client') or sys._milvus_client is None:
        sys._milvus_client = MilvusClient(uri=MILVUS_URI)
    return sys._milvus_client

def _get_embedding_model(model_name=None):
    if model_name is None:
        model_name = DEFAULT_MODEL
    cache_key = '_embedding_models'
    if not hasattr(sys, cache_key):
        setattr(sys, cache_key, {})
    models = getattr(sys, cache_key)
    if model_name not in models:
        models[model_name] = SentenceTransformer(model_name)
    return models[model_name]

def _load_collection_meta():
    if os.path.exists(COLLECTION_META_PATH):
        with open(COLLECTION_META_PATH, 'r') as f:
            return json.load(f)
    return {}

def _get_model_for_collection(collection_name):
    meta = _load_collection_meta()
    if collection_name in meta:
        return meta[collection_name].get("model", DEFAULT_MODEL)
    return DEFAULT_MODEL

def _has_equation(text):
    if not text:
        return False
    if '[EQUATION:' in text or '[EQUATION_BLOCK:' in text:
        return True
    for pat in LATEX_PATTERNS:
        if re.search(pat, text):
            return True
    return False

def _extract_latex_from_text(text):
    equations = []
    # [EQUATION: ...] 마커에서 LaTeX 추출
    marker_pattern = r'\[EQUATION:\s*(\w+)\s*\|\s*type=(\w+)\s*\|\s*\$\$(.*?)\$\$\s*(?:\|\s*ref=([^|]*?))?\s*(?:\|\s*context:\s*(.*?))?\s*\]'
    for m in re.finditer(marker_pattern, text, re.DOTALL):
        equations.append({
            'id': m.group(1),
            'type': m.group(2),
            'latex': m.group(3).strip(),
            'ref': (m.group(4) or '').strip(),
            'context': (m.group(5) or '').strip()
        })
    # $$...$$ 형식
    for m in re.finditer(r'\$\$(.*?)\$\$', text, re.DOTALL):
        latex = m.group(1).strip()
        if latex and not any(eq['latex'] == latex for eq in equations):
            equations.append({
                'id': f'inline_{len(equations)}',
                'type': 'display',
                'latex': latex,
                'ref': '',
                'context': ''
            })
    return equations

# ==============================================================================
# API: 컬렉션 목록
# ==============================================================================
def collections():
    client = _get_milvus_client()
    collection_names = client.list_collections()
    meta = _load_collection_meta()
    result = []
    for name in sorted(collection_names):
        info = meta.get(name, {})
        model_name = info.get("model", DEFAULT_MODEL)
        short_name = MODEL_REGISTRY.get(model_name, {}).get("short_name", model_name.split("/")[-1])
        try:
            stats = client.get_collection_stats(name)
            total = stats.get("row_count", 0)
        except Exception:
            total = 0
        result.append({
            "name": name,
            "model": model_name,
            "short_name": short_name,
            "total_docs": total
        })
    wiz.response.status(200, collections=result)

# ==============================================================================
# API: 유사 논문 검색
# ==============================================================================
def search_papers():
    hypothesis_title = wiz.request.query("title", "")
    hypothesis_content = wiz.request.query("content", "")
    collection = wiz.request.query("collection", "")
    limit = int(wiz.request.query("limit", 20))

    if not collection:
        wiz.response.status(400, message="컬렉션을 선택하세요.")
    if not hypothesis_content and not hypothesis_title:
        wiz.response.status(400, message="가설을 입력하세요.")

    query_text = f"{hypothesis_title} {hypothesis_content}".strip()

    model_name = _get_model_for_collection(collection)
    model = _get_embedding_model(model_name)
    client = _get_milvus_client()

    query_embedding = model.encode(query_text).tolist()

    results = client.search(
        collection_name=collection,
        data=[query_embedding],
        limit=limit,
        output_fields=["text", "doc_id", "filename", "chunk_type", "page_num", "section_title", "content_elements"],
        search_params={"metric_type": "COSINE", "params": {"nprobe": 10}}
    )

    papers = []
    seen_docs = {}
    for hits in results:
        for hit in hits:
            entity = hit.get("entity", {})
            doc_id = entity.get("doc_id", "")
            filename = entity.get("filename", "unknown")
            text = entity.get("text", "")
            score = hit.get("distance", 0)
            chunk_type = entity.get("chunk_type", "text")
            has_eq = _has_equation(text) or chunk_type in ("equation", "formula", "mixed")

            if doc_id not in seen_docs:
                seen_docs[doc_id] = {
                    "doc_id": doc_id,
                    "filename": filename,
                    "score": score,
                    "snippets": [],
                    "has_equation": has_eq,
                    "equation_count": 0,
                    "pages": set()
                }

            doc = seen_docs[doc_id]
            doc["score"] = max(doc["score"], score)
            if has_eq:
                doc["has_equation"] = True
                doc["equation_count"] += 1

            page = entity.get("page_num", 0)
            if page:
                doc["pages"].add(page)

            snippet = text[:300] if text else ""
            if len(doc["snippets"]) < 3:
                doc["snippets"].append({
                    "text": snippet,
                    "score": score,
                    "page": page,
                    "section": entity.get("section_title", ""),
                    "chunk_type": chunk_type
                })

    paper_list = sorted(seen_docs.values(), key=lambda x: x["score"], reverse=True)
    for p in paper_list:
        p["pages"] = sorted(list(p["pages"]))

    wiz.response.status(200, papers=paper_list)

# ==============================================================================
# API: 논문 내 수식 추출
# ==============================================================================
def extract_equations():
    collection = wiz.request.query("collection", "")
    doc_ids_str = wiz.request.query("doc_ids", "")

    if not collection:
        wiz.response.status(400, message="컬렉션을 선택하세요.")
    if not doc_ids_str:
        wiz.response.status(400, message="논문 doc_id를 지정하세요.")

    doc_ids = [d.strip() for d in doc_ids_str.split(",") if d.strip()]

    client = _get_milvus_client()

    all_equations = []
    for doc_id in doc_ids:
        filter_expr = f'doc_id == "{doc_id}"'
        try:
            chunks = client.query(
                collection_name=collection,
                filter=filter_expr,
                output_fields=["text", "filename", "chunk_type", "page_num", "section_title", "content_elements"],
                limit=500
            )
        except Exception:
            continue

        for chunk in chunks:
            text = chunk.get("text", "")
            chunk_type = chunk.get("chunk_type", "text")
            filename = chunk.get("filename", "unknown")

            is_eq_chunk = chunk_type in ("equation", "formula", "mixed") or _has_equation(text)
            if not is_eq_chunk:
                continue

            extracted = _extract_latex_from_text(text)
            if not extracted and _has_equation(text):
                extracted = [{
                    'id': f'raw_{len(all_equations)}',
                    'type': 'unknown',
                    'latex': '',
                    'ref': '',
                    'context': text[:200]
                }]

            for eq in extracted:
                eq["source_doc_id"] = doc_id
                eq["source_filename"] = filename
                eq["page_num"] = chunk.get("page_num", 0)
                eq["section_title"] = chunk.get("section_title", "")
                eq["surrounding_text"] = text[:300]
                all_equations.append(eq)

    wiz.response.status(200, equations=all_equations, total=len(all_equations))

# ==============================================================================
# API: SSE 가설 검증 파이프라인
# ==============================================================================
def verify():
    flask = wiz.response._flask

    # Request context 안에서 미리 추출
    hypothesis_title = wiz.request.query("title", "")
    hypothesis_content = wiz.request.query("content", "")
    collection = wiz.request.query("collection", "")
    selected_eq_ids = wiz.request.query("selected_equations", "")
    paper_limit = int(wiz.request.query("paper_limit", 20))

    config = wiz.config("season")

    if not hypothesis_content and not hypothesis_title:
        wiz.response.status(400, message="가설을 입력하세요.")
    if not collection:
        wiz.response.status(400, message="컬렉션을 선택하세요.")

    # 로컬 LLM 클라이언트 로딩 (sys.modules 캐싱 + 버전 체크)
    import sys as _sys
    _mod_key = "_wiz_local_llm"
    _REQUIRED_VER = 15
    if _mod_key in _sys.modules:
        _cached = _sys.modules[_mod_key]
        if getattr(_cached, '_VERSION', 0) < _REQUIRED_VER:
            if hasattr(_cached, '_cleanup'):
                _cached._cleanup()
            del _sys.modules[_mod_key]
            del _cached
            import os as _os
            _os._exit(0)
    if _mod_key in _sys.modules and hasattr(_sys.modules[_mod_key], "get_client"):
        _llm_mod = _sys.modules[_mod_key]
    else:
        import importlib.util as _ilu
        _llm_path = os.path.join(wiz.project.fs().abspath(), "src", "model", "local_llm.py")
        if not os.path.isfile(_llm_path):
            for _c in ["build", "bundle"]:
                _p = os.path.join(wiz.project.fs().abspath(), _c, "model", "local_llm.py")
                if os.path.isfile(_p):
                    _llm_path = _p
                    break
        _spec = _ilu.spec_from_file_location(_mod_key, _llm_path)
        _llm_mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_llm_mod)
        _sys.modules[_mod_key] = _llm_mod
    llm_client = _llm_mod.get_client(config)
    llm_model_name = getattr(config, "local_model_name", "google/gemma-4-26B-A4B-it")

    model_name = _get_model_for_collection(collection)

    def generate():
        try:
            # ── Step 1: 유사 논문 검색 ──
            yield f"data: {json.dumps({'type': 'step', 'step': 'searching', 'message': '유사 논문을 검색하고 있습니다...'}, ensure_ascii=False)}\n\n"

            query_text = f"{hypothesis_title} {hypothesis_content}".strip()
            emb_model = _get_embedding_model(model_name)
            client = _get_milvus_client()
            query_embedding = emb_model.encode(query_text).tolist()

            results = client.search(
                collection_name=collection,
                data=[query_embedding],
                limit=paper_limit,
                output_fields=["text", "doc_id", "filename", "chunk_type", "page_num", "section_title"],
                search_params={"metric_type": "COSINE", "params": {"nprobe": 10}}
            )

            papers = {}
            all_snippets = []
            for hits in results:
                for hit in hits:
                    entity = hit.get("entity", {})
                    doc_id = entity.get("doc_id", "")
                    filename = entity.get("filename", "unknown")
                    text = entity.get("text", "")
                    score = hit.get("distance", 0)

                    if doc_id not in papers:
                        papers[doc_id] = {
                            "doc_id": doc_id,
                            "filename": filename,
                            "score": score,
                            "has_equation": False
                        }
                    papers[doc_id]["score"] = max(papers[doc_id]["score"], score)
                    if _has_equation(text):
                        papers[doc_id]["has_equation"] = True
                    all_snippets.append({
                        "doc_id": doc_id,
                        "filename": filename,
                        "text": text[:400],
                        "score": score
                    })

            paper_list = sorted(papers.values(), key=lambda x: x["score"], reverse=True)

            yield f"data: {json.dumps({'type': 'papers', 'papers': paper_list, 'total': len(paper_list)}, ensure_ascii=False)}\n\n"

            # ── Step 2: 수식 추출 ──
            yield f"data: {json.dumps({'type': 'step', 'step': 'extracting', 'message': '관련 수식을 추출하고 있습니다...'}, ensure_ascii=False)}\n\n"

            doc_ids = [p["doc_id"] for p in paper_list[:10]]
            all_equations = []

            for doc_id in doc_ids:
                filter_expr = f'doc_id == "{doc_id}"'
                try:
                    chunks = client.query(
                        collection_name=collection,
                        filter=filter_expr,
                        output_fields=["text", "filename", "chunk_type", "page_num"],
                        limit=200
                    )
                except Exception:
                    continue

                for chunk in chunks:
                    text = chunk.get("text", "")
                    chunk_type = chunk.get("chunk_type", "text")
                    if not (chunk_type in ("equation", "formula", "mixed") or _has_equation(text)):
                        continue

                    extracted = _extract_latex_from_text(text)
                    for eq in extracted:
                        eq["source_filename"] = chunk.get("filename", "unknown")
                        eq["surrounding_text"] = text[:200]
                        all_equations.append(eq)

            # 선택된 수식 필터
            if selected_eq_ids:
                sel_ids = set(selected_eq_ids.split(","))
                all_equations = [eq for eq in all_equations if eq.get("id") in sel_ids] or all_equations

            yield f"data: {json.dumps({'type': 'equations', 'equations': all_equations[:30], 'total': len(all_equations)}, ensure_ascii=False)}\n\n"

            # ── Step 3: LLM 가설 검증 ──
            yield f"data: {json.dumps({'type': 'step', 'step': 'verifying', 'message': 'AI가 가설을 검증하고 있습니다...'}, ensure_ascii=False)}\n\n"

            # 컨텍스트 구성
            paper_context = ""
            for i, snippet in enumerate(all_snippets[:15]):
                paper_context += f"\n[논문 {i+1}] {snippet['filename']} (유사도: {snippet['score']:.3f})\n{snippet['text']}\n"

            equation_context = ""
            for i, eq in enumerate(all_equations[:20]):
                latex = eq.get("latex", "")
                ctx = eq.get("context", "") or eq.get("surrounding_text", "")
                src = eq.get("source_filename", "")
                equation_context += f"\n[수식 {i+1}] 출처: {src}\nLaTeX: $${latex}$$\n맥락: {ctx[:150]}\n"

            prompt = f"""당신은 플라즈마 물리학 및 핵융합 연구 분야의 전문가입니다.
아래 가설을 관련 논문과 수식을 기반으로 검증해주세요.

## 가설
- **제목**: {hypothesis_title}
- **내용**: {hypothesis_content}

## 관련 논문 (유사도 순)
{paper_context}

## 관련 수식
{equation_context}

## 검증 요청
다음 구조로 답변해주세요:

### 1. 가설 분석
가설의 핵심 주장과 검증 가능한 명제를 정리하세요.

### 2. 관련 논문 근거
유사 논문들이 이 가설을 어떻게 지지하거나 반박하는지 분석하세요.
각 근거는 출처 논문을 명시하세요.

### 3. 수식적 검증
관련 수식들이 이 가설의 타당성을 어떻게 뒷받침하거나 반박하는지 분석하세요.
수식의 변수와 가설의 물리량 간 대응 관계를 설명하세요.

### 4. 검증 결론
**[결론: 지지/반박/불충분]** 중 하나를 선택하고, 
종합적인 판단 근거를 2-3문장으로 요약하세요.

### 5. 추가 실험 제안
가설을 더 확실히 검증하기 위한 실험이나 추가 분석을 제안하세요.
"""

            stream = llm_client.chat.completions.create(
                model=llm_model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.3,
                stream=True
            )

            full_text = ""
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    text_chunk = delta.content
                    full_text += text_chunk
                    yield f"data: {json.dumps({'type': 'text', 'content': text_chunk}, ensure_ascii=False)}\n\n"

            # 결론 추출
            conclusion = "insufficient"
            conclusion_label = "불충분"
            lower_text = full_text.lower()
            if "결론: 지지" in full_text or "supported" in lower_text:
                conclusion = "supported"
                conclusion_label = "지지"
            elif "결론: 반박" in full_text or "contradicted" in lower_text:
                conclusion = "contradicted"
                conclusion_label = "반박"

            yield f"data: {json.dumps({'type': 'result', 'conclusion': conclusion, 'conclusion_label': conclusion_label, 'full_text': full_text, 'papers_count': len(paper_list), 'equations_count': len(all_equations)}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    resp = flask.Response(generate(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    wiz.response.response(resp)

# ==============================================================================
# API: 검증 이력 관리
# ==============================================================================
HISTORY_PATH = "/opt/app/data/hypothesis_history.json"

def save_history():
    data = wiz.request.query("data", True)
    if not data:
        wiz.response.status(400, message="데이터가 없습니다.")

    history = []
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, 'r') as f:
            history = json.load(f)

    import datetime
    entry = {
        "id": f"hyp_{len(history)+1}",
        "timestamp": datetime.datetime.now().isoformat(),
        "title": data.get("title", ""),
        "content": data.get("content", ""),
        "collection": data.get("collection", ""),
        "conclusion": data.get("conclusion", ""),
        "conclusion_label": data.get("conclusion_label", ""),
        "papers_count": data.get("papers_count", 0),
        "equations_count": data.get("equations_count", 0)
    }
    history.insert(0, entry)
    history = history[:50]

    with open(HISTORY_PATH, 'w') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    wiz.response.status(200, entry=entry)

def load_history():
    history = []
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, 'r') as f:
            history = json.load(f)
    wiz.response.status(200, history=history)
