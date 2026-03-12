import os
import sys
import json
import traceback
import numpy as np
import re
from collections import Counter

from sentence_transformers import SentenceTransformer
from pymilvus import MilvusClient
import season.lib.exception

# ==============================================================================
# 설정
# ==============================================================================
MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
COLLECTION_META_PATH = "/opt/app/data/collection_meta.json"
DEFAULT_COLLECTION = "plasma_papers"

# 모델 레지스트리 (page.embedding과 동일)
MODEL_REGISTRY = {
    # 한국어
    "snunlp/KR-SBERT-V40K-klueNLI-augSTS": {"dim": 768, "short_name": "KR-SBERT"},
    "BM-K/KoSimCSE-roberta-multitask": {"dim": 768, "short_name": "KoSimCSE"},
    "jhgan/ko-sroberta-multitask": {"dim": 768, "short_name": "ko-sroberta"},
    # 영어
    "sentence-transformers/all-MiniLM-L6-v2": {"dim": 384, "short_name": "MiniLM-L6"},
    "sentence-transformers/all-mpnet-base-v2": {"dim": 768, "short_name": "MPNet"},
    "BAAI/bge-base-en-v1.5": {"dim": 768, "short_name": "BGE-base"},
    # 다국어
    "intfloat/multilingual-e5-large": {"dim": 1024, "short_name": "mE5-Large"},
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": {"dim": 384, "short_name": "MiniLM-L12"}
}
DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

# 플라즈마 도메인 용어 사전
PLASMA_TERMS = [
    "플라즈마", "plasma", "에칭", "etching", "증착", "deposition", "CVD", "PVD",
    "스퍼터링", "sputtering", "이온", "ion", "RF", "DC", "전자", "electron",
    "가스", "gas", "압력", "pressure", "온도", "temperature", "전력", "power",
    "기판", "substrate", "박막", "thin film", "반응", "reaction", "챔버", "chamber",
    "공정", "process", "반도체", "semiconductor", "실리콘", "silicon",
    "산화", "oxidation", "질화", "nitride", "식각", "etch", "균일도", "uniformity",
    "밀도", "density", "속도", "rate", "선택비", "selectivity",
    "OES", "optical emission", "Langmuir", "진단", "diagnostic",
    "토카막", "tokamak", "핵융합", "fusion", "자기장", "magnetic field",
    "전기장", "electric field", "방전", "discharge", "글로우", "glow",
    "아크", "arc", "대기압", "atmospheric", "진공", "vacuum",
    "나노", "nano", "표면", "surface", "계면", "interface",
    "전구체", "precursor", "세정", "cleaning", "패시베이션", "passivation",
    "ALD", "atomic layer", "PECVD", "ICP", "CCP", "마이크로파", "microwave",
    "수소", "hydrogen", "산소", "oxygen", "질소", "nitrogen", "아르곤", "argon",
    "불소", "fluorine", "CF4", "SF6", "Cl2", "HBr", "O2", "Ar", "N2", "H2",
    "시뮬레이션", "simulation", "모델링", "modeling", "머신러닝", "machine learning",
    "딥러닝", "deep learning", "인공지능", "AI", "센서", "sensor",
    "스펙트럼", "spectrum", "파장", "wavelength", "광학", "optical",
    "임피던스", "impedance", "주파수", "frequency", "파워", "power",
    "두께", "thickness", "거칠기", "roughness", "결함", "defect",
    "수율", "yield", "신뢰성", "reliability", "수명", "lifetime"
]

# ==============================================================================
# 컬렉션 메타데이터 & 모델 관리
# ==============================================================================
def _load_collection_meta():
    if os.path.exists(COLLECTION_META_PATH):
        try:
            with open(COLLECTION_META_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _get_collection_model(collection_name):
    meta = _load_collection_meta()
    info = meta.get(collection_name, {})
    return info.get("model", DEFAULT_MODEL)

def _get_model(model_name=None):
    if model_name is None:
        model_name = DEFAULT_MODEL
    if model_name not in MODEL_REGISTRY:
        model_name = DEFAULT_MODEL
    if not hasattr(sys, '_embedding_models') or sys._embedding_models is None:
        sys._embedding_models = {}
    if model_name not in sys._embedding_models or sys._embedding_models[model_name] is None:
        sys._embedding_models[model_name] = SentenceTransformer(model_name)
    return sys._embedding_models[model_name]

def _get_client():
    if not hasattr(sys, '_milvus_client') or sys._milvus_client is None:
        db_path = MILVUS_URI
        if not db_path.startswith("http"):
            db_dir = os.path.dirname(db_path)
            os.makedirs(db_dir, exist_ok=True)
        sys._milvus_client = MilvusClient(uri=db_path)
    return sys._milvus_client

def _resolve_collection_and_model():
    """요청에서 컬렉션 결정 → 해당 컬렉션의 모델 로드"""
    collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip()
    if not collection_name:
        collection_name = DEFAULT_COLLECTION
    model_name = _get_collection_model(collection_name)
    return collection_name, model_name


def _extract_terms_from_text(text):
    text_lower = text.lower()
    counter = Counter()
    for term in PLASMA_TERMS:
        tl = term.lower()
        cnt = text_lower.count(tl)
        if cnt > 0:
            counter[term] += cnt
    return counter


def collections():
    """사용 가능한 컬렉션 목록 반환 (문서 수, 청크 수 포함)"""
    try:
        client = _get_client()
        col_names = client.list_collections()
        meta = _load_collection_meta()

        result = []
        for name in col_names:
            info = meta.get(name, {})

            # 메타가 없거나 short_name이 Unknown인 경우 dim으로 모델 추론
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
                    # dim으로 모델 추론
                    dim_to_model = {}
                    for mname, minfo in MODEL_REGISTRY.items():
                        d = minfo["dim"]
                        if d not in dim_to_model:
                            dim_to_model[d] = mname
                    inferred = dim_to_model.get(dim, DEFAULT_MODEL)
                    inferred_info = MODEL_REGISTRY.get(inferred, {})
                    info = {
                        "model": inferred,
                        "dim": dim,
                        "short_name": inferred_info.get("short_name", inferred)
                    }
                except Exception:
                    pass

            # 통계 조회 (문서 수, 청크 수)
            total_chunks = 0
            total_docs = 0
            try:
                stats_info = client.get_collection_stats(name)
                total_chunks = stats_info.get("row_count", 0)
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
                "model": info.get("model", DEFAULT_MODEL),
                "short_name": info.get("short_name", "Unknown"),
                "dim": info.get("dim", 768),
                "total_docs": total_docs,
                "total_chunks": total_chunks
            })
        wiz.response.status(200, collections=result)
    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        wiz.response.status(200, collections=[])


def discover():
    """키워드 기반 연구 주제 발굴 - 유사 문서 클러스터링"""
    try:
        keyword = wiz.request.query("keyword", "")
        top_k = int(wiz.request.query("top_k", "20"))
        collection_name, model_name = _resolve_collection_and_model()

        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, clusters=[], message="컬렉션이 없습니다. 먼저 PDF를 임베딩하세요.")
            return

        if not keyword.strip():
            results = client.query(
                collection_name=collection_name,
                filter="chunk_index == 0",
                output_fields=["doc_id", "filename", "text"],
                limit=50
            )
            docs = []
            for r in results:
                docs.append({
                    "doc_id": r.get("doc_id", ""),
                    "filename": r.get("filename", ""),
                    "snippet": r.get("text", "")[:200]
                })
            wiz.response.status(200, mode="overview", docs=docs, total=len(docs))
            return

        model = _get_model(model_name)
        query_vec = model.encode([keyword], normalize_embeddings=True)[0].tolist()

        search_results = client.search(
            collection_name=collection_name,
            data=[query_vec],
            limit=top_k,
            output_fields=["doc_id", "filename", "chunk_index", "text"],
            search_params={"metric_type": "COSINE"}
        )

        doc_groups = {}
        for hit in search_results[0]:
            entity = hit.get("entity", {})
            doc_id = entity.get("doc_id", "unknown")
            if doc_id not in doc_groups:
                doc_groups[doc_id] = {
                    "doc_id": doc_id,
                    "filename": entity.get("filename", ""),
                    "chunks": [],
                    "max_score": 0
                }
            score = hit.get("distance", 0)
            doc_groups[doc_id]["chunks"].append({
                "chunk_index": entity.get("chunk_index", 0),
                "text": entity.get("text", "")[:300],
                "score": round(score, 4)
            })
            if score > doc_groups[doc_id]["max_score"]:
                doc_groups[doc_id]["max_score"] = round(score, 4)

        clusters = sorted(doc_groups.values(), key=lambda x: x["max_score"], reverse=True)

        wiz.response.status(200,
            mode="search",
            keyword=keyword,
            clusters=clusters,
            total_hits=len(search_results[0]))

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def recommend():
    """키워드 기반 탐색 후 새로운 연구 주제 추천"""
    try:
        keyword = wiz.request.query("keyword", "")
        if not keyword.strip():
            wiz.response.status(400, message="추천을 위한 키워드를 입력하세요.")
            return

        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, recommendations=[], message="컬렉션이 없습니다. 먼저 PDF를 임베딩하세요.")
            return

        model = _get_model(model_name)
        recommendations = []

        # 1단계: 키워드 직접 검색 → 핵심 문서 + 공출현 용어 추출
        query_vec = model.encode([keyword], normalize_embeddings=True)[0].tolist()
        direct_results = client.search(
            collection_name=collection_name,
            data=[query_vec],
            limit=30,
            output_fields=["doc_id", "filename", "chunk_index", "text"],
            search_params={"metric_type": "COSINE"}
        )

        all_texts = []
        direct_doc_ids = set()
        for hit in direct_results[0]:
            entity = hit.get("entity", {})
            all_texts.append(entity.get("text", ""))
            direct_doc_ids.add(entity.get("doc_id", ""))

        combined_text = " ".join(all_texts)
        cooccurring = _extract_terms_from_text(combined_text)

        keyword_lower = keyword.lower()
        filtered_terms = []
        for term, freq in cooccurring.most_common(50):
            if term.lower() in keyword_lower or keyword_lower in term.lower():
                continue
            if len(term) <= 1:
                continue
            filtered_terms.append((term, freq))

        # 2단계: 교차 주제 조합
        cross_queries = []
        for term, freq in filtered_terms[:8]:
            cross_query = f"{keyword} {term}"
            cross_queries.append((cross_query, term, freq))

        for cross_query, co_term, freq in cross_queries[:6]:
            cross_vec = model.encode([cross_query], normalize_embeddings=True)[0].tolist()
            cross_results = client.search(
                collection_name=collection_name,
                data=[cross_vec],
                limit=5,
                output_fields=["doc_id", "filename", "text"],
                search_params={"metric_type": "COSINE"}
            )

            if not cross_results[0]:
                continue

            top_hit = cross_results[0][0]
            score = top_hit.get("distance", 0)

            evidence_snippets = []
            for h in cross_results[0][:3]:
                e = h.get("entity", {})
                evidence_snippets.append({
                    "filename": e.get("filename", ""),
                    "text": e.get("text", "")[:200],
                    "score": round(h.get("distance", 0), 4)
                })

            recommendations.append({
                "type": "cross_topic",
                "title": f"{keyword} × {co_term}",
                "description": f"'{keyword}'와 '{co_term}'의 교차 영역을 탐구하는 연구 주제입니다. 기존 문헌에서 두 개념이 {freq}회 함께 출현하여 연관성이 확인되었습니다.",
                "relevance": round(score, 4),
                "co_term": co_term,
                "co_frequency": freq,
                "evidence": evidence_snippets
            })

        # 3단계: 연구 공백 탐색
        gap_results = client.search(
            collection_name=collection_name,
            data=[query_vec],
            limit=50,
            output_fields=["doc_id", "filename", "chunk_index", "text"],
            search_params={"metric_type": "COSINE"}
        )

        gap_candidates = []
        for hit in gap_results[0]:
            score = hit.get("distance", 0)
            if 0.25 <= score <= 0.65:
                entity = hit.get("entity", {})
                gap_candidates.append({
                    "doc_id": entity.get("doc_id", ""),
                    "filename": entity.get("filename", ""),
                    "text": entity.get("text", ""),
                    "score": score
                })

        gap_unique_terms = Counter()
        for gc in gap_candidates:
            terms = _extract_terms_from_text(gc["text"])
            for t, c in terms.items():
                if t.lower() not in keyword_lower and keyword_lower not in t.lower():
                    gap_unique_terms[t] += c

        for term, gap_freq in gap_unique_terms.most_common(15):
            direct_freq = cooccurring.get(term, 0)
            if gap_freq > direct_freq * 0.5 and len(term) > 1:
                gap_query = f"{keyword} {term} 연구"
                gap_vec = model.encode([gap_query], normalize_embeddings=True)[0].tolist()
                gap_search = client.search(
                    collection_name=collection_name,
                    data=[gap_vec],
                    limit=3,
                    output_fields=["doc_id", "filename", "text"],
                    search_params={"metric_type": "COSINE"}
                )

                evidence_snippets = []
                for h in gap_search[0]:
                    e = h.get("entity", {})
                    evidence_snippets.append({
                        "filename": e.get("filename", ""),
                        "text": e.get("text", "")[:200],
                        "score": round(h.get("distance", 0), 4)
                    })

                recommendations.append({
                    "type": "research_gap",
                    "title": f"{keyword}에서의 {term} 연구",
                    "description": f"'{keyword}' 관련 핵심 문헌에서 '{term}'에 대한 연구가 상대적으로 부족합니다.",
                    "relevance": round(gap_search[0][0].get("distance", 0) if gap_search[0] else 0, 4),
                    "gap_term": term,
                    "gap_frequency": gap_freq,
                    "direct_frequency": direct_freq,
                    "evidence": evidence_snippets
                })

                if len([r for r in recommendations if r["type"] == "research_gap"]) >= 4:
                    break

        # 4단계: 확장 탐색
        expansion_templates = [
            ("{keyword} 최적화 방법", "방법론 확장", "기존 '{keyword}' 연구에 새로운 최적화 방법론을 적용하는 연구 주제입니다."),
            ("{keyword} 실시간 모니터링", "응용 확장", "'{keyword}'의 실시간 모니터링 및 제어 기술로의 확장 가능성을 탐구합니다."),
            ("{keyword} 머신러닝 예측", "AI 융합", "'{keyword}' 데이터에 머신러닝/AI 기법을 적용한 예측 모델 연구입니다."),
            ("{keyword} 시뮬레이션 모델링", "계산 과학", "'{keyword}'의 물리적 현상을 시뮬레이션하고 모델링하는 계산 과학 연구입니다."),
            ("{keyword} 신소재 적용", "소재 확장", "'{keyword}' 기술을 신소재/차세대 소재에 적용하는 연구 방향입니다."),
        ]

        for template_query, category, desc_template in expansion_templates:
            expanded_query = template_query.format(keyword=keyword)
            expanded_desc = desc_template.format(keyword=keyword)

            exp_vec = model.encode([expanded_query], normalize_embeddings=True)[0].tolist()
            exp_results = client.search(
                collection_name=collection_name,
                data=[exp_vec],
                limit=3,
                output_fields=["doc_id", "filename", "text"],
                search_params={"metric_type": "COSINE"}
            )

            if not exp_results[0]:
                continue

            top_score = exp_results[0][0].get("distance", 0)

            evidence_snippets = []
            for h in exp_results[0]:
                e = h.get("entity", {})
                evidence_snippets.append({
                    "filename": e.get("filename", ""),
                    "text": e.get("text", "")[:200],
                    "score": round(h.get("distance", 0), 4)
                })

            recommendations.append({
                "type": "expansion",
                "title": expanded_query,
                "description": expanded_desc,
                "category": category,
                "relevance": round(top_score, 4),
                "evidence": evidence_snippets
            })

        # 중복 제거 + 정렬
        seen_titles = set()
        unique_recs = []
        for r in recommendations:
            if r["title"] not in seen_titles:
                seen_titles.add(r["title"])
                unique_recs.append(r)

        type_order = {"cross_topic": 0, "research_gap": 1, "expansion": 2}
        unique_recs.sort(key=lambda x: (type_order.get(x["type"], 9), -x["relevance"]))

        wiz.response.status(200,
            keyword=keyword,
            recommendations=unique_recs,
            total=len(unique_recs),
            stats={
                "cross_topic": len([r for r in unique_recs if r["type"] == "cross_topic"]),
                "research_gap": len([r for r in unique_recs if r["type"] == "research_gap"]),
                "expansion": len([r for r in unique_recs if r["type"] == "expansion"]),
                "docs_analyzed": len(direct_doc_ids),
                "terms_found": len(filtered_terms)
            })

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def related():
    """특정 문서의 관련 연구 주제 찾기"""
    try:
        doc_id = wiz.request.query("doc_id", "")
        if not doc_id:
            wiz.response.status(400, message="doc_id가 필요합니다.")

        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        model = _get_model(model_name)

        source_chunks = client.query(
            collection_name=collection_name,
            filter=f'doc_id == "{doc_id}" and chunk_index == 0',
            output_fields=["text", "filename"]
        )

        if not source_chunks:
            wiz.response.status(404, message="문서를 찾을 수 없습니다.")

        source_text = source_chunks[0].get("text", "")
        source_filename = source_chunks[0].get("filename", "")

        query_vec = model.encode([source_text], normalize_embeddings=True)[0].tolist()

        search_results = client.search(
            collection_name=collection_name,
            data=[query_vec],
            limit=30,
            output_fields=["doc_id", "filename", "chunk_index", "text"],
            search_params={"metric_type": "COSINE"}
        )

        related_docs = {}
        for hit in search_results[0]:
            entity = hit.get("entity", {})
            hit_doc_id = entity.get("doc_id", "")
            if hit_doc_id == doc_id:
                continue
            if hit_doc_id not in related_docs:
                related_docs[hit_doc_id] = {
                    "doc_id": hit_doc_id,
                    "filename": entity.get("filename", ""),
                    "score": round(hit.get("distance", 0), 4),
                    "snippet": entity.get("text", "")[:200]
                }

        related_list = sorted(related_docs.values(), key=lambda x: x["score"], reverse=True)[:10]

        wiz.response.status(200,
            source_doc_id=doc_id,
            source_filename=source_filename,
            related=related_list)

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def keywords():
    """저장된 문서들에서 핵심 키워드/주제어 추출"""
    try:
        collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip()
        if not collection_name:
            collection_name = DEFAULT_COLLECTION

        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, keywords=[], message="컬렉션이 없습니다.")
            return

        results = client.query(
            collection_name=collection_name,
            filter="chunk_index == 0",
            output_fields=["text", "filename", "doc_id"],
            limit=100
        )

        term_counter = Counter()
        doc_term_map = {}

        for r in results:
            text = r.get("text", "").lower()
            doc_id = r.get("doc_id", "")
            filename = r.get("filename", "")
            for term in PLASMA_TERMS:
                tl = term.lower()
                count = text.count(tl)
                if count > 0:
                    term_counter[term] += count
                    if term not in doc_term_map:
                        doc_term_map[term] = []
                    doc_term_map[term].append({"doc_id": doc_id, "filename": filename})

        keywords_list = []
        for term, count in term_counter.most_common(30):
            keywords_list.append({
                "term": term,
                "frequency": count,
                "doc_count": len(doc_term_map.get(term, [])),
                "docs": doc_term_map.get(term, [])[:5]
            })

        wiz.response.status(200, keywords=keywords_list, total_docs=len(results))

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def topic_map():
    """토픽 클러스터링 & 2D 토픽 맵 생성"""
    try:
        collection_name, model_name = _resolve_collection_and_model()
        max_chunks = int(wiz.request.query("max_chunks", "500"))

        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, clusters=[], points=[], message="컬렉션이 없습니다.")
            return

        # 1. 청크 데이터 + 벡터 추출 (chunk_index==0: 문서 대표 청크)
        doc_chunks = client.query(
            collection_name=collection_name,
            filter="chunk_index == 0",
            output_fields=["doc_id", "filename", "text", "embedding"],
            limit=max_chunks
        )

        if len(doc_chunks) < 3:
            wiz.response.status(200, clusters=[], points=[],
                message=f"클러스터링에 최소 3개 문서가 필요합니다. (현재 {len(doc_chunks)}개)")
            return

        # 벡터 & 메타데이터 분리
        embeddings = []
        doc_ids = []
        filenames = []
        texts = []
        for chunk in doc_chunks:
            emb = chunk.get("embedding", [])
            if emb and len(emb) > 0:
                embeddings.append(emb)
                doc_ids.append(chunk.get("doc_id", ""))
                filenames.append(chunk.get("filename", ""))
                texts.append(chunk.get("text", ""))

        if len(embeddings) < 3:
            wiz.response.status(200, clusters=[], points=[],
                message="유효한 임베딩 벡터가 부족합니다.")
            return

        X = np.array(embeddings, dtype=np.float32)
        n_samples = X.shape[0]

        # 2. UMAP 2D 투영
        coords_2d = None
        try:
            import umap
            n_neighbors = min(15, n_samples - 1)
            if n_neighbors < 2:
                n_neighbors = 2
            reducer = umap.UMAP(
                n_components=2,
                n_neighbors=n_neighbors,
                min_dist=0.1,
                metric='cosine',
                random_state=42
            )
            coords_2d = reducer.fit_transform(X)
        except Exception:
            # Fallback: PCA
            from sklearn.decomposition import PCA
            pca = PCA(n_components=2, random_state=42)
            coords_2d = pca.fit_transform(X)

        # 좌표 정규화 (0~100 범위)
        if coords_2d is not None:
            for dim in range(2):
                mn = coords_2d[:, dim].min()
                mx = coords_2d[:, dim].max()
                rng = mx - mn if mx - mn > 0 else 1.0
                coords_2d[:, dim] = (coords_2d[:, dim] - mn) / rng * 100

        # 3. HDBSCAN 클러스터링
        labels = None
        try:
            import hdbscan
            min_cluster = max(2, n_samples // 10)
            min_cluster = min(min_cluster, 5)
            min_samples_val = max(1, min(3, n_samples // 10))
            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=min_cluster,
                min_samples=min_samples_val,
                metric='euclidean',
                cluster_selection_epsilon=0.0,
                cluster_selection_method='eom'
            )
            labels = clusterer.fit_predict(X)
        except Exception:
            pass

        if labels is None or len(set(labels)) <= 1:
            # Fallback: KMeans
            from sklearn.cluster import KMeans
            n_clusters = max(2, min(n_samples // 3, 8))
            km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = km.fit_predict(X)

        # 4. 클러스터별 키워드 추출 (PLASMA_TERMS 기반 TF-IDF 스타일)
        cluster_ids = sorted(set(labels))
        # 노이즈 레이블(-1) 처리: "기타" 클러스터로 통합
        cluster_map = {}  # cluster_id -> list of indices
        for idx, label in enumerate(labels):
            cid = int(label) if label >= 0 else -1
            if cid not in cluster_map:
                cluster_map[cid] = []
            cluster_map[cid].append(idx)

        # 전체 문서 term frequency (DF 계산용)
        global_df = Counter()
        doc_terms_list = []
        for text in texts:
            doc_terms = _extract_terms_from_text(text)
            doc_terms_list.append(doc_terms)
            for term in doc_terms:
                global_df[term] += 1

        total_docs_count = len(texts)

        # 클러스터 정보 구성
        clusters_result = []
        color_palette = [
            "#8b5cf6", "#f59e0b", "#10b981", "#3b82f6",
            "#ef4444", "#06b6d4", "#ec4899", "#84cc16",
            "#f97316", "#6366f1", "#14b8a6", "#a855f7"
        ]

        for cid in sorted(cluster_map.keys()):
            indices = cluster_map[cid]
            cluster_texts = [texts[i] for i in indices]
            cluster_filenames = [filenames[i] for i in indices]
            cluster_doc_ids = [doc_ids[i] for i in indices]

            # TF-IDF 스타일 키워드 추출
            cluster_tf = Counter()
            for i in indices:
                for term, cnt in doc_terms_list[i].items():
                    cluster_tf[term] += cnt

            # TF-IDF 점수 계산
            tfidf_scores = {}
            for term, tf in cluster_tf.items():
                df = global_df.get(term, 1)
                idf = np.log(total_docs_count / df + 1)
                tfidf_scores[term] = tf * idf

            top_keywords = sorted(tfidf_scores.items(), key=lambda x: -x[1])[:8]

            # 클러스터 중심 좌표
            cluster_coords = coords_2d[indices]
            center_x = float(np.mean(cluster_coords[:, 0]))
            center_y = float(np.mean(cluster_coords[:, 1]))

            # 클러스터 밀도 (평균 내부 거리의 역수)
            if len(indices) > 1:
                cluster_vecs = X[indices]
                center_vec = np.mean(cluster_vecs, axis=0)
                dists = np.linalg.norm(cluster_vecs - center_vec, axis=1)
                avg_dist = float(np.mean(dists))
                density = round(1.0 / (avg_dist + 0.001), 4)
            else:
                density = 0.0

            cluster_label = "기타 (미분류)" if cid == -1 else f"토픽 {cid + 1}"
            color_idx = (cid + 1) % len(color_palette) if cid >= 0 else 0
            color = "#9ca3af" if cid == -1 else color_palette[color_idx]

            # 유니크 문서 목록
            unique_docs = {}
            for di, fn in zip(cluster_doc_ids, cluster_filenames):
                if di not in unique_docs:
                    unique_docs[di] = fn

            clusters_result.append({
                "id": int(cid),
                "label": cluster_label,
                "color": color,
                "doc_count": len(unique_docs),
                "chunk_count": len(indices),
                "keywords": [{"term": t, "score": round(s, 2)} for t, s in top_keywords],
                "center": {"x": round(center_x, 2), "y": round(center_y, 2)},
                "density": density,
                "docs": [{"doc_id": did, "filename": fn} for did, fn in unique_docs.items()]
            })

        # 5. 포인트 데이터 (2D 좌표 + 클러스터 레이블)
        points = []
        for idx in range(n_samples):
            cid = int(labels[idx]) if labels[idx] >= 0 else -1
            # 해당 클러스터의 색상
            color_idx = (cid + 1) % len(color_palette) if cid >= 0 else 0
            color = "#9ca3af" if cid == -1 else color_palette[color_idx]

            points.append({
                "x": round(float(coords_2d[idx, 0]), 2),
                "y": round(float(coords_2d[idx, 1]), 2),
                "cluster_id": cid,
                "doc_id": doc_ids[idx],
                "filename": filenames[idx],
                "color": color
            })

        # 클러스터를 문서 수 역순 정렬 (기타는 마지막)
        clusters_result.sort(key=lambda c: (c["id"] == -1, -c["doc_count"]))

        # 6. 클러스터 간 관계 분석
        relationships = []
        valid_clusters = [c for c in clusters_result if c["id"] != -1]
        if len(valid_clusters) >= 2:
            for i in range(len(valid_clusters)):
                for j in range(i + 1, len(valid_clusters)):
                    c1 = valid_clusters[i]
                    c2 = valid_clusters[j]
                    dx = c1["center"]["x"] - c2["center"]["x"]
                    dy = c1["center"]["y"] - c2["center"]["y"]
                    dist_2d = (dx**2 + dy**2) ** 0.5
                    indices_1 = cluster_map[c1["id"]]
                    indices_2 = cluster_map[c2["id"]]
                    center_vec_1 = np.mean(X[indices_1], axis=0)
                    center_vec_2 = np.mean(X[indices_2], axis=0)
                    cos_sim = float(np.dot(center_vec_1, center_vec_2) /
                                   (np.linalg.norm(center_vec_1) * np.linalg.norm(center_vec_2) + 1e-8))
                    kw1 = set(k["term"] for k in c1["keywords"])
                    kw2 = set(k["term"] for k in c2["keywords"])
                    shared = kw1 & kw2
                    if cos_sim > 0.7:
                        relation = "similar"
                    elif cos_sim > 0.4:
                        relation = "related"
                    else:
                        relation = "distinct"
                    relationships.append({
                        "cluster_a": c1["id"], "cluster_b": c2["id"],
                        "label_a": c1["label"], "label_b": c2["label"],
                        "color_a": c1["color"], "color_b": c2["color"],
                        "center_a": c1["center"], "center_b": c2["center"],
                        "distance_2d": round(dist_2d, 2),
                        "cosine_similarity": round(cos_sim, 4),
                        "shared_keywords": list(shared),
                        "relation": relation
                    })
            relationships.sort(key=lambda x: -x["cosine_similarity"])

        # 7. 브릿지 문서 탐지
        bridge_docs = []
        if len(valid_clusters) >= 2:
            for idx in range(n_samples):
                doc_cluster = int(labels[idx]) if labels[idx] >= 0 else -1
                if doc_cluster == -1:
                    continue
                cluster_sims = []
                for c in valid_clusters:
                    c_indices = cluster_map[c["id"]]
                    center_vec = np.mean(X[c_indices], axis=0)
                    sim = float(np.dot(X[idx], center_vec) /
                               (np.linalg.norm(X[idx]) * np.linalg.norm(center_vec) + 1e-8))
                    cluster_sims.append({"cluster_id": c["id"], "label": c["label"],
                                        "color": c["color"], "similarity": round(sim, 4)})
                cluster_sims.sort(key=lambda x: -x["similarity"])
                if len(cluster_sims) >= 2:
                    primary = cluster_sims[0]
                    secondary = cluster_sims[1]
                    if secondary["similarity"] > 0.5 and secondary["cluster_id"] != doc_cluster:
                        bridge_docs.append({
                            "doc_id": doc_ids[idx],
                            "filename": filenames[idx],
                            "primary_cluster": primary,
                            "secondary_cluster": secondary,
                            "bridge_score": round(secondary["similarity"], 4)
                        })
            bridge_docs.sort(key=lambda x: -x["bridge_score"])
            bridge_docs = bridge_docs[:10]

        # 8. 클러스터별 대표 문장 추출
        for c in clusters_result:
            if c["id"] == -1:
                c["representative_snippet"] = ""
                c["representative_doc"] = ""
                continue
            c_indices = cluster_map.get(c["id"], [])
            if not c_indices:
                c["representative_snippet"] = ""
                c["representative_doc"] = ""
                continue
            center_vec = np.mean(X[c_indices], axis=0)
            best_idx = c_indices[0]
            best_sim = -1
            for ci in c_indices:
                sim = float(np.dot(X[ci], center_vec) /
                           (np.linalg.norm(X[ci]) * np.linalg.norm(center_vec) + 1e-8))
                if sim > best_sim:
                    best_sim = sim
                    best_idx = ci
            c["representative_snippet"] = texts[best_idx][:300]
            c["representative_doc"] = filenames[best_idx]

        # 9. 전체 맵 해석 요약
        summary_parts = []
        n_valid = len(valid_clusters)
        summary_parts.append(f"총 {n_samples}개 문서가 {n_valid}개의 토픽 클러스터로 분류되었습니다.")
        if valid_clusters:
            densest = max(valid_clusters, key=lambda c: c["density"])
            largest = max(valid_clusters, key=lambda c: c["doc_count"])
            summary_parts.append(
                f"가장 큰 토픽은 '{largest['label']}'({largest['doc_count']}문서)이며, "
                f"가장 밀집된 토픽은 '{densest['label']}'(밀도 {densest['density']:.1f})입니다."
            )
        if relationships:
            closest = relationships[0]
            summary_parts.append(
                f"'{closest['label_a']}'와 '{closest['label_b']}'은 "
                f"유사도 {closest['cosine_similarity']:.2f}로 가장 밀접하게 연관되어 있습니다."
            )
            if len(relationships) > 1:
                most_distinct = relationships[-1]
                if most_distinct["cosine_similarity"] < 0.4:
                    summary_parts.append(
                        f"반면 '{most_distinct['label_a']}'와 '{most_distinct['label_b']}'은 "
                        f"유사도 {most_distinct['cosine_similarity']:.2f}로 가장 독립적인 연구 영역입니다."
                    )
        if bridge_docs:
            summary_parts.append(
                f"클러스터 간 교차 영역에 위치한 브릿지 문서가 {len(bridge_docs)}건 탐지되었습니다. "
                f"이 문서들은 서로 다른 연구 주제를 연결하는 역할을 합니다."
            )
        noise_count = len(cluster_map.get(-1, []))
        if noise_count > 0:
            summary_parts.append(f"미분류 문서는 {noise_count}건으로, 독립적이거나 새로운 연구 방향일 수 있습니다.")

        interpretation = {
            "summary": " ".join(summary_parts),
            "relationships": relationships[:15],
            "bridge_docs": bridge_docs
        }

        wiz.response.status(200,
            clusters=clusters_result,
            points=points,
            total_docs=n_samples,
            n_clusters=len([c for c in clusters_result if c["id"] != -1]),
            method="HDBSCAN+UMAP",
            interpretation=interpretation
        )

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def gap_detector():
    """Research Gap Detector - 벡터 공간 밀도 분석으로 연구 공백 탐지"""
    try:
        keywords_input = wiz.request.query("keywords", "")
        if not keywords_input.strip():
            wiz.response.status(400, message="분석할 키워드를 입력하세요.")
            return

        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, gaps=[], keyword_densities=[], message="컬렉션이 없습니다.")
            return

        model = _get_model(model_name)

        # 키워드 파싱 (쉼표 구분)
        kw_list = [k.strip() for k in keywords_input.split(",") if k.strip()]
        if len(kw_list) == 0:
            wiz.response.status(400, message="유효한 키워드를 입력하세요.")
            return

        # 각 키워드별 밀도 분석
        keyword_densities = []
        keyword_vecs = {}
        for kw in kw_list:
            vec = model.encode([kw], normalize_embeddings=True)[0].tolist()
            keyword_vecs[kw] = vec

            results = client.search(
                collection_name=collection_name,
                data=[vec],
                limit=20,
                output_fields=["doc_id", "filename", "chunk_index", "text"],
                search_params={"metric_type": "COSINE"}
            )

            if not results[0]:
                keyword_densities.append({
                    "keyword": kw,
                    "density": 0,
                    "avg_similarity": 0,
                    "doc_count": 0,
                    "top_docs": []
                })
                continue

            # 밀도 계산: 상위 K개 결과의 평균 유사도 (COSINE이므로 높을수록 밀접)
            scores = [hit.get("distance", 0) for hit in results[0]]
            avg_score = sum(scores) / len(scores)

            # KNN 밀도: 가까운 K개의 평균 거리의 역수
            top5_scores = sorted(scores, reverse=True)[:5]
            knn_density = sum(top5_scores) / len(top5_scores) if top5_scores else 0

            # 유니크 문서
            unique_docs = {}
            for hit in results[0]:
                entity = hit.get("entity", {})
                doc_id = entity.get("doc_id", "")
                if doc_id not in unique_docs:
                    unique_docs[doc_id] = {
                        "doc_id": doc_id,
                        "filename": entity.get("filename", ""),
                        "score": round(hit.get("distance", 0), 4),
                        "snippet": entity.get("text", "")[:150]
                    }

            keyword_densities.append({
                "keyword": kw,
                "density": round(knn_density, 4),
                "avg_similarity": round(avg_score, 4),
                "doc_count": len(unique_docs),
                "top_docs": list(unique_docs.values())[:5]
            })

        # 교차 키워드 조합 밀도 분석
        gaps = []
        from itertools import combinations

        if len(kw_list) >= 2:
            for kw_combo in combinations(kw_list, 2):
                combined_query = f"{kw_combo[0]} {kw_combo[1]}"
                combo_vec = model.encode([combined_query], normalize_embeddings=True)[0].tolist()
                combo_results = client.search(
                    collection_name=collection_name,
                    data=[combo_vec],
                    limit=20,
                    output_fields=["doc_id", "filename", "text"],
                    search_params={"metric_type": "COSINE"}
                )

                if combo_results[0]:
                    combo_scores = [h.get("distance", 0) for h in combo_results[0]]
                    combo_density = sum(combo_scores[:5]) / min(5, len(combo_scores))

                    # 개별 키워드 밀도의 평균과 비교
                    individual_densities = []
                    for kd in keyword_densities:
                        if kd["keyword"] in kw_combo:
                            individual_densities.append(kd["density"])
                    avg_individual = sum(individual_densities) / len(individual_densities) if individual_densities else 0

                    # gap_score: 개별 밀도 대비 조합 밀도가 낮을수록 연구 공백
                    gap_score = max(0, avg_individual - combo_density)

                    # 관련 문서
                    unique_combo_docs = {}
                    for hit in combo_results[0]:
                        entity = hit.get("entity", {})
                        doc_id = entity.get("doc_id", "")
                        if doc_id not in unique_combo_docs:
                            unique_combo_docs[doc_id] = {
                                "doc_id": doc_id,
                                "filename": entity.get("filename", ""),
                                "score": round(hit.get("distance", 0), 4),
                                "snippet": entity.get("text", "")[:150]
                            }

                    # 잠재력 판단
                    if gap_score > 0.1:
                        potential = "높음"
                    elif gap_score > 0.05:
                        potential = "보통"
                    else:
                        potential = "낮음"

                    gaps.append({
                        "keywords": list(kw_combo),
                        "combined_query": combined_query,
                        "combo_density": round(combo_density, 4),
                        "avg_individual_density": round(avg_individual, 4),
                        "gap_score": round(gap_score, 4),
                        "potential": potential,
                        "doc_count": len(unique_combo_docs),
                        "related_docs": list(unique_combo_docs.values())[:5],
                        "description": f"'{kw_combo[0]}'와 '{kw_combo[1]}'의 교차 영역은 개별 주제(밀도 {avg_individual:.2f}) 대비 조합 밀도({combo_density:.2f})가 {'낮아' if gap_score > 0.05 else '유사하여'} {'잠재적 연구 공백' if gap_score > 0.05 else '충분히 연구된 영역'}으로 판단됩니다."
                    })
                else:
                    gaps.append({
                        "keywords": list(kw_combo),
                        "combined_query": combined_query,
                        "combo_density": 0,
                        "avg_individual_density": 0,
                        "gap_score": 1.0,
                        "potential": "높음",
                        "doc_count": 0,
                        "related_docs": [],
                        "description": f"'{kw_combo[0]}'와 '{kw_combo[1]}'의 교차 영역에 관련 문서가 전혀 없습니다. 미개척 연구 영역입니다."
                    })

        # 단일 키워드 중 밀도가 낮은 것도 gap으로 추가
        for kd in keyword_densities:
            if kd["density"] < 0.35:
                gaps.append({
                    "keywords": [kd["keyword"]],
                    "combined_query": kd["keyword"],
                    "combo_density": kd["density"],
                    "avg_individual_density": kd["density"],
                    "gap_score": round(max(0, 0.5 - kd["density"]), 4),
                    "potential": "높음" if kd["density"] < 0.2 else "보통",
                    "doc_count": kd["doc_count"],
                    "related_docs": kd["top_docs"],
                    "description": f"'{kd['keyword']}' 주제는 벡터 공간에서 밀도({kd['density']:.2f})가 낮아 관련 연구가 부족한 영역입니다."
                })

        # gap_score 역순 정렬
        gaps.sort(key=lambda x: -x["gap_score"])

        wiz.response.status(200,
            gaps=gaps,
            keyword_densities=keyword_densities,
            total_keywords=len(kw_list),
            total_gaps=len(gaps)
        )

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def generate_hypothesis():
    """가설 자동 생성 - 연구 조건 입력 → 관련 논문 검색 → 패턴 기반 가설 생성"""
    try:
        condition = wiz.request.query("condition", "")
        if not condition.strip():
            wiz.response.status(400, message="연구 조건을 입력하세요.")
            return

        collection_name, model_name = _resolve_collection_and_model()
        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, hypotheses=[], message="컬렉션이 없습니다.")
            return

        model = _get_model(model_name)

        # Step 1: 조건 벡터화 → Milvus 검색
        condition_vec = model.encode([condition], normalize_embeddings=True)[0].tolist()
        results = client.search(
            collection_name=collection_name,
            data=[condition_vec],
            limit=30,
            output_fields=["doc_id", "filename", "chunk_index", "text"],
            search_params={"metric_type": "COSINE"}
        )

        if not results[0]:
            wiz.response.status(200, hypotheses=[], evidence_docs=[], novel_terms=[],
                message="관련 문헌을 찾을 수 없습니다.")
            return

        # Step 2: 검색된 논문에서 공통 용어/패턴 추출
        all_texts = []
        evidence_docs = {}
        for hit in results[0]:
            entity = hit.get("entity", {})
            text = entity.get("text", "")
            all_texts.append(text)
            doc_id = entity.get("doc_id", "")
            if doc_id not in evidence_docs:
                evidence_docs[doc_id] = {
                    "doc_id": doc_id,
                    "filename": entity.get("filename", ""),
                    "score": round(hit.get("distance", 0), 4),
                    "snippet": text[:200]
                }

        # 공통 용어 추출
        combined_text = " ".join(all_texts)
        terms = _extract_terms_from_text(combined_text)
        condition_terms = _extract_terms_from_text(condition)

        # 조건에 없는 관련 용어 (새로운 변수 후보)
        novel_terms = []
        for term, freq in terms.most_common(30):
            if term.lower() not in condition.lower():
                novel_terms.append((term, freq))

        # Step 3: 템플릿 기반 가설 생성
        hypotheses = []

        # 조건에서 핵심 키워드 추출
        condition_keywords = [t for t, f in condition_terms.most_common(5)]
        if not condition_keywords:
            # 조건 텍스트에서 PLASMA_TERMS가 없으면 원문 사용
            condition_keywords = [condition[:30]]

        main_kw = condition_keywords[0] if condition_keywords else condition[:20]

        # 가설 템플릿들
        templates = [
            {
                "type": "parameter_optimization",
                "type_label": "파라미터 최적화",
                "title_template": "{main_kw}에서 {novel_term}의 최적 조건 탐색",
                "desc_template": "기존 문헌 분석 결과, {main_kw} 공정에서 {novel_term}이(가) 중요한 변수로 확인되었으나, 최적 조건에 대한 체계적 연구가 부족합니다. {novel_term}을(를) 변수로 설정한 파라미터 최적화 실험이 필요합니다.",
                "experiment": "{novel_term}을(를) 다단계로 변화시키며 {main_kw} 성능 지표를 측정하는 DOE(실험 설계) 기반 연구를 제안합니다.",
                "min_terms": 1
            },
            {
                "type": "mechanism_study",
                "type_label": "메커니즘 규명",
                "title_template": "{main_kw} 과정에서 {novel_term}의 메커니즘 규명",
                "desc_template": "관련 문헌에서 {novel_term}이(가) {main_kw}에 영향을 미치는 것으로 보고되었으나, 정확한 물리적/화학적 메커니즘은 아직 명확하지 않습니다. 분광학적 진단과 시뮬레이션을 통한 메커니즘 연구가 제안됩니다.",
                "experiment": "OES, Langmuir probe 등 진단 장비를 활용한 {novel_term} 기반 {main_kw} 메커니즘 분석을 제안합니다.",
                "min_terms": 1
            },
            {
                "type": "cross_domain",
                "type_label": "교차 도메인",
                "title_template": "{novel_term1}과 {novel_term2}의 상호작용이 {main_kw}에 미치는 영향",
                "desc_template": "{novel_term1}과(와) {novel_term2}은(는) 각각 {main_kw}와 관련된 중요한 변수이지만, 두 변수의 상호작용 효과에 대한 연구는 제한적입니다. 복합 효과 분석이 새로운 연구 방향이 될 수 있습니다.",
                "experiment": "2-factor factorial design으로 {novel_term1}과 {novel_term2}의 상호작용 효과를 분석하는 실험을 제안합니다.",
                "min_terms": 2
            },
            {
                "type": "novel_application",
                "type_label": "신규 응용",
                "title_template": "{main_kw} 기술의 {novel_term} 분야 적용 가능성",
                "desc_template": "기존 {main_kw} 연구는 특정 분야에 집중되어 있으나, {novel_term} 분야로의 확장 적용이 유망합니다. 관련 문헌에서 간접적 연관성이 확인되었으며, 직접적인 적용 연구가 필요합니다.",
                "experiment": "{main_kw} 기반 공정을 {novel_term} 소재/응용에 적용한 pilot 실험을 제안합니다.",
                "min_terms": 1
            },
            {
                "type": "prediction_model",
                "type_label": "예측 모델",
                "title_template": "{main_kw} 결과 예측을 위한 {novel_term} 기반 모델링",
                "desc_template": "{main_kw} 공정의 결과를 {novel_term} 데이터를 활용하여 예측하는 모델을 구축할 수 있습니다. 관련 문헌의 실험 데이터를 기반으로 머신러닝/통계적 모델 개발이 가능합니다.",
                "experiment": "기존 실험 데이터 수집 → {novel_term} 기반 feature engineering → ML 모델 훈련 및 검증 파이프라인을 제안합니다.",
                "min_terms": 1
            }
        ]

        evidence_list = list(evidence_docs.values())[:10]

        for i, template in enumerate(templates):
            if template["min_terms"] > len(novel_terms):
                continue

            if template["min_terms"] == 2 and len(novel_terms) >= 2:
                nt1 = novel_terms[0][0]
                nt2 = novel_terms[1][0]
                title = template["title_template"].format(main_kw=main_kw, novel_term1=nt1, novel_term2=nt2)
                desc = template["desc_template"].format(main_kw=main_kw, novel_term1=nt1, novel_term2=nt2)
                exp = template["experiment"].format(main_kw=main_kw, novel_term1=nt1, novel_term2=nt2)
            else:
                idx = min(i, len(novel_terms) - 1)
                nt = novel_terms[idx][0]
                title = template["title_template"].format(main_kw=main_kw, novel_term=nt)
                desc = template["desc_template"].format(main_kw=main_kw, novel_term=nt)
                exp = template["experiment"].format(main_kw=main_kw, novel_term=nt)

            # 가설 벡터 → 관련도 계산
            hyp_vec = model.encode([title], normalize_embeddings=True)[0].tolist()
            hyp_results = client.search(
                collection_name=collection_name,
                data=[hyp_vec],
                limit=3,
                output_fields=["doc_id", "filename", "text"],
                search_params={"metric_type": "COSINE"}
            )

            hyp_evidence = []
            confidence = 0
            if hyp_results[0]:
                confidence = hyp_results[0][0].get("distance", 0)
                for h in hyp_results[0]:
                    e = h.get("entity", {})
                    hyp_evidence.append({
                        "filename": e.get("filename", ""),
                        "text": e.get("text", "")[:200],
                        "score": round(h.get("distance", 0), 4)
                    })

            hypotheses.append({
                "type": template["type"],
                "type_label": template["type_label"],
                "title": title,
                "description": desc,
                "experiment_design": exp,
                "confidence": round(confidence, 4),
                "evidence": hyp_evidence,
                "novel_terms": [nt for nt, _ in novel_terms[:3]]
            })

        # 신뢰도 역순 정렬
        hypotheses.sort(key=lambda x: -x["confidence"])

        wiz.response.status(200,
            condition=condition,
            hypotheses=hypotheses,
            total=len(hypotheses),
            evidence_docs=evidence_list,
            novel_terms=[{"term": t, "frequency": f} for t, f in novel_terms[:10]]
        )

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# 논문 추천 (recommend)
# ==============================================================================
def recommend_papers():
    """관심 분야 기반 논문 추천"""
    try:
        interests = wiz.request.query("interests", "")
        collection_name = wiz.request.query("collection", "")

        if not interests.strip():
            wiz.response.status(400, message="관심 분야를 입력하세요.")

        if not collection_name:
            collection_name = _get_default_collection()

        client = MilvusClient(uri=MILVUS_URI)
        meta = _load_collection_meta()
        col_meta = meta.get(collection_name, {})
        model_name = col_meta.get("model_name", list(MODEL_REGISTRY.keys())[0])
        model = SentenceTransformer(model_name)

        query_vec = model.encode(interests).tolist()
        results = client.search(
            collection_name=collection_name,
            data=[query_vec],
            limit=10,
            output_fields=["title", "text", "metadata"]
        )

        papers = []
        for hit in results[0]:
            entity = hit.get("entity", {})
            papers.append({
                "title": entity.get("title", "제목 없음"),
                "text": (entity.get("text", "") or "")[:300],
                "score": round(hit.get("distance", 0), 4),
                "authors": (entity.get("metadata", {}) or {}).get("authors", "")
            })

        wiz.response.status(200, papers)

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# 제안서 생성 (proposal)
# ==============================================================================
def generate_proposal():
    """연구 제안서 초안 생성"""
    try:
        title = wiz.request.query("title", "")
        objective = wiz.request.query("objective", "")
        keywords = wiz.request.query("keywords", "")
        collection_name = wiz.request.query("collection", "")

        if not title.strip():
            wiz.response.status(400, message="연구 제목을 입력하세요.")

        if not collection_name:
            collection_name = _get_default_collection()

        # 키워드 기반으로 관련 문헌 검색
        search_text = f"{title} {objective} {keywords}"
        client = MilvusClient(uri=MILVUS_URI)
        meta = _load_collection_meta()
        col_meta = meta.get(collection_name, {})
        model_name = col_meta.get("model_name", list(MODEL_REGISTRY.keys())[0])
        model = SentenceTransformer(model_name)

        query_vec = model.encode(search_text).tolist()
        results = client.search(
            collection_name=collection_name,
            data=[query_vec],
            limit=5,
            output_fields=["title", "text", "metadata"]
        )

        references = []
        context_texts = []
        for hit in results[0]:
            entity = hit.get("entity", {})
            ref_title = entity.get("title", "제목 없음")
            references.append(ref_title)
            context_texts.append(entity.get("text", "")[:200])

        # 제안서 초안 구성
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        kw_str = ", ".join(kw_list) if kw_list else "플라즈마 공정"

        proposal = {
            "background": f"본 연구는 '{title}'에 관한 것으로, {kw_str} 분야의 최근 연구 동향을 기반으로 합니다. "
                         f"관련 문헌 {len(references)}편을 분석한 결과, 해당 분야에서 추가적인 연구가 필요한 것으로 판단됩니다. "
                         f"{objective}" if objective else f"본 연구는 '{title}'에 관한 것입니다.",
            "methodology": f"1) {kw_str} 관련 실험 설계 및 파라미터 최적화\n"
                          f"2) 관련 문헌 기반 비교 분석\n"
                          f"3) 실험 결과 검증 및 통계적 유의성 분석\n"
                          f"4) 결과 해석 및 모델링",
            "expected_results": f"본 연구를 통해 {kw_str} 분야에서의 새로운 지견을 확보하고, "
                               f"관련 공정의 효율성 향상에 기여할 것으로 기대됩니다.",
            "references": references
        }

        wiz.response.status(200, proposal)

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# 특허 검색 (patent)
# ==============================================================================
def search_patents():
    """특허 관련 기술 검색"""
    try:
        query = wiz.request.query("query", "")
        collection_name = wiz.request.query("collection", "")

        if not query.strip():
            wiz.response.status(400, message="검색어를 입력하세요.")

        if not collection_name:
            collection_name = _get_default_collection()

        client = MilvusClient(uri=MILVUS_URI)
        meta = _load_collection_meta()
        col_meta = meta.get(collection_name, {})
        model_name = col_meta.get("model_name", list(MODEL_REGISTRY.keys())[0])
        model = SentenceTransformer(model_name)

        # 특허 관련 키워드 추가하여 검색
        patent_query = f"{query} patent method apparatus system process"
        query_vec = model.encode(patent_query).tolist()
        results = client.search(
            collection_name=collection_name,
            data=[query_vec],
            limit=10,
            output_fields=["title", "text", "metadata"]
        )

        patents = []
        for hit in results[0]:
            entity = hit.get("entity", {})
            meta_data = entity.get("metadata", {}) or {}
            patents.append({
                "title": entity.get("title", "제목 없음"),
                "text": (entity.get("text", "") or "")[:300],
                "score": round(hit.get("distance", 0), 4),
                "year": meta_data.get("year", ""),
                "authors": meta_data.get("authors", "")
            })

        wiz.response.status(200, patents)

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))
