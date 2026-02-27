# =============================================================================
# recommend_topics Tool — 연구 주제 추천 (교차/공백/확장)
# =============================================================================
import os
import sys
import json
import re
from collections import Counter

from base_tool import BaseTool

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
    "시뮬레이션", "simulation", "모델링", "modeling", "머신러닝", "machine learning",
]

def _extract_terms(text):
    text_lower = text.lower()
    counter = Counter()
    for term in PLASMA_TERMS:
        cnt = text_lower.count(term.lower())
        if cnt > 0:
            counter[term] += cnt
    return counter


class RecommendTopicsTool(BaseTool):
    name = "recommend_topics"
    description = "Recommend new research topics based on a keyword. Analyzes co-occurring terms, research gaps, and expansion directions. Returns cross-topic combinations, gap areas, and methodological extensions."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Research interest keyword (e.g., 'plasma etching', 'OES diagnostics')"
            },
            "collection": {
                "type": "string",
                "description": "Collection name. Default: plasma_papers"
            }
        },
        "required": ["query"]
    }

    def execute(self, query="", collection="", **kwargs):
        from sentence_transformers import SentenceTransformer
        from pymilvus import MilvusClient

        MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        META_PATH = "/opt/app/data/collection_meta.json"
        DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

        if not query.strip():
            return "Error: query is required"
        if not collection:
            collection = "plasma_papers"

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

        recommendations = []

        # Step 1: 직접 검색 → 공출현 용어
        query_vec = model.encode(query).tolist()
        direct = client.search(collection_name=collection, data=[query_vec], limit=30,
                               output_fields=["doc_id", "filename", "text"],
                               search_params={"metric_type": "COSINE"})
        if not direct or not direct[0]:
            return f"No results found for '{query}'."

        all_text = " ".join(h["entity"].get("text", "") for h in direct[0])
        cooccurring = _extract_terms(all_text)
        query_lower = query.lower()
        filtered = [(t, f) for t, f in cooccurring.most_common(50)
                     if t.lower() not in query_lower and query_lower not in t.lower() and len(t) > 1]

        # Step 2: 교차 주제
        for term, freq in filtered[:5]:
            cross_q = f"{query} {term}"
            cv = model.encode(cross_q).tolist()
            cr = client.search(collection_name=collection, data=[cv], limit=3,
                               output_fields=["doc_id", "filename", "text"],
                               search_params={"metric_type": "COSINE"})
            if cr and cr[0]:
                score = cr[0][0].get("distance", 0)
                evidence = cr[0][0]["entity"].get("filename", "")
                recommendations.append(
                    f"[교차 주제] {query} × {term} (관련도: {score:.3f}, 공출현 {freq}회)\n"
                    f"  근거: {evidence}")

        # Step 3: 연구 공백
        gap_results = client.search(collection_name=collection, data=[query_vec], limit=50,
                                    output_fields=["doc_id", "text"],
                                    search_params={"metric_type": "COSINE"})
        gap_terms = Counter()
        for h in gap_results[0]:
            score = h.get("distance", 0)
            if 0.25 <= score <= 0.65:
                terms = _extract_terms(h["entity"].get("text", ""))
                for t, c in terms.items():
                    if t.lower() not in query_lower:
                        gap_terms[t] += c

        for term, gf in gap_terms.most_common(3):
            recommendations.append(
                f"[연구 공백] {query}에서의 {term} 연구 (빈도: {gf})\n"
                f"  설명: 핵심 문헌에서 '{term}' 관련 연구가 상대적으로 부족합니다.")

        # Step 4: 확장 탐색
        expansions = [
            (f"{query} 최적화 방법", "방법론 확장"),
            (f"{query} 실시간 모니터링", "응용 확장"),
            (f"{query} 머신러닝 예측", "AI 융합"),
            (f"{query} 시뮬레이션 모델링", "계산 과학"),
        ]
        for eq, cat in expansions:
            ev = model.encode(eq).tolist()
            er = client.search(collection_name=collection, data=[ev], limit=1,
                               output_fields=["filename"],
                               search_params={"metric_type": "COSINE"})
            if er and er[0]:
                score = er[0][0].get("distance", 0)
                recommendations.append(
                    f"[{cat}] {eq} (관련도: {score:.3f})")

        if not recommendations:
            return f"'{query}'에 대한 추천 주제를 생성하지 못했습니다."

        header = f"'{query}' 기반 연구 주제 추천 ({len(recommendations)}건):\n"
        return header + "\n".join(f"\n{i+1}. {r}" for i, r in enumerate(recommendations))

Tool = RecommendTopicsTool
