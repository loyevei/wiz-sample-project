# =============================================================================
# generate_hypothesis Tool — 템플릿 기반 가설 자동 생성
# =============================================================================
import os
import sys
import json
from collections import Counter

from base_tool import BaseTool

PLASMA_TERMS = [
    "플라즈마", "plasma", "에칭", "etching", "증착", "deposition", "CVD", "PVD",
    "스퍼터링", "sputtering", "이온", "ion", "RF", "DC", "전자", "electron",
    "가스", "gas", "압력", "pressure", "온도", "temperature", "전력", "power",
    "기판", "substrate", "박막", "thin film", "OES", "Langmuir", "진단", "diagnostic",
    "시뮬레이션", "simulation", "모델링", "modeling", "머신러닝", "machine learning",
    "식각", "etch", "균일도", "uniformity", "선택비", "selectivity", "밀도", "density",
]


class GenerateHypothesisTool(BaseTool):
    name = "generate_hypothesis"
    description = "Generate research hypotheses based on a given condition/topic. Searches related papers, extracts novel co-occurring terms, and generates hypotheses using 5 templates: parameter optimization, mechanism study, cross-domain, novel application, prediction model."
    input_schema = {
        "type": "object",
        "properties": {
            "condition": {
                "type": "string",
                "description": "Research condition or topic (e.g., 'CF4 plasma etching of SiO2', 'ICP source power effect')"
            },
            "collection": {
                "type": "string",
                "description": "Collection name. Default: plasma_papers"
            }
        },
        "required": ["condition"]
    }

    def execute(self, condition="", collection="", **kwargs):
        from sentence_transformers import SentenceTransformer
        from pymilvus import MilvusClient

        MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        META_PATH = "/opt/app/data/collection_meta.json"
        DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

        if not condition.strip():
            return "Error: condition is required"
        if not collection:
            collection = self.ctx.get("collection", "") or "plasma_papers"

        model_name = DEFAULT_MODEL
        try:
            if os.path.exists(META_PATH):
                with open(META_PATH, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get(collection, {}).get("model"):
                    model_name = meta[collection]["model"]
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

        # Step 1: 검색
        vec = model.encode(condition).tolist()
        results = client.search(collection_name=collection, data=[vec], limit=30,
                                output_fields=["doc_id", "filename", "text"],
                                search_params={"metric_type": "COSINE"})

        if not results or not results[0]:
            return f"No related papers found for '{condition}'."

        # Step 2: 공출현 용어 추출
        all_text = " ".join(h["entity"].get("text", "") for h in results[0])
        terms = Counter()
        text_lower = all_text.lower()
        for term in PLASMA_TERMS:
            cnt = text_lower.count(term.lower())
            if cnt > 0:
                terms[term] += cnt

        condition_lower = condition.lower()
        novel_terms = [(t, f) for t, f in terms.most_common(30) if t.lower() not in condition_lower]

        if not novel_terms:
            return f"Could not extract novel terms from papers related to '{condition}'."

        main_kw = condition[:30]
        evidence_files = list(set(h["entity"].get("filename", "") for h in results[0][:5]))

        # Step 3: 가설 생성
        templates = [
            ("파라미터 최적화", "{main_kw}에서 {nt}의 최적 조건 탐색",
             "기존 문헌에서 {nt}이(가) 중요 변수로 확인되었으나 최적 조건 연구가 부족합니다.",
             "{nt}을(를) 다단계로 변화시키며 성능 지표를 측정하는 DOE 기반 실험 제안"),
            ("메커니즘 규명", "{main_kw} 과정에서 {nt}의 메커니즘 규명",
             "관련 문헌에서 {nt}의 영향이 보고되었으나 정확한 메커니즘은 미규명 상태입니다.",
             "OES/Langmuir probe 진단과 시뮬레이션을 통한 메커니즘 분석 제안"),
            ("교차 도메인", "{nt1}과 {nt2}의 상호작용이 {main_kw}에 미치는 영향",
             "각 변수는 개별 연구되었으나 상호작용 효과는 미탐구 영역입니다.",
             "2-factor factorial design으로 상호작용 효과 분석 제안"),
            ("신규 응용", "{main_kw} 기술의 {nt} 분야 적용",
             "기존 연구는 특정 분야에 집중되어 있으나 {nt} 분야로 확장 가능합니다.",
             "Pilot 실험을 통한 적용 가능성 검증 제안"),
            ("예측 모델", "{main_kw} 결과 예측을 위한 {nt} 기반 모델링",
             "실험 데이터를 활용한 {nt} 기반 ML/통계 예측 모델 구축이 가능합니다.",
             "Feature engineering → ML 모델 훈련 → 검증 파이프라인 제안"),
        ]

        lines = [f"'{condition}' 기반 연구 가설 ({len(templates)}건):\n"]
        lines.append(f"근거 논문: {', '.join(evidence_files[:3])}")
        lines.append(f"발견된 관련 변수: {', '.join(t for t, _ in novel_terms[:5])}\n")

        for i, (typ, title_t, desc_t, exp_t) in enumerate(templates):
            if i < len(novel_terms):
                nt = novel_terms[i][0]
            else:
                nt = novel_terms[0][0]

            if typ == "교차 도메인" and len(novel_terms) >= 2:
                title = title_t.format(main_kw=main_kw, nt1=novel_terms[0][0], nt2=novel_terms[1][0])
                desc = desc_t.format(main_kw=main_kw, nt1=novel_terms[0][0], nt2=novel_terms[1][0])
                exp = exp_t.format(main_kw=main_kw, nt1=novel_terms[0][0], nt2=novel_terms[1][0])
            else:
                title = title_t.format(main_kw=main_kw, nt=nt)
                desc = desc_t.format(main_kw=main_kw, nt=nt)
                exp = exp_t.format(main_kw=main_kw, nt=nt)

            lines.append(f"### 가설 {i+1}: [{typ}] {title}")
            lines.append(f"  배경: {desc}")
            lines.append(f"  실험 설계: {exp}\n")

        return "\n".join(lines)

Tool = GenerateHypothesisTool
