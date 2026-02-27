# =============================================================================
# detect_research_gaps Tool — 벡터 밀도 기반 연구 공백 탐지
# =============================================================================
import os
import sys
import json
from itertools import combinations

from base_tool import BaseTool


class DetectResearchGapsTool(BaseTool):
    name = "detect_research_gaps"
    description = "Detect research gaps by analyzing vector space density for given keywords. Compares individual keyword density vs. cross-keyword combination density to find unexplored intersection areas."
    input_schema = {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "string",
                "description": "Comma-separated keywords to analyze (e.g., 'plasma etching, selectivity, machine learning')"
            },
            "collection": {
                "type": "string",
                "description": "Collection name. Default: plasma_papers"
            }
        },
        "required": ["keywords"]
    }

    def execute(self, keywords="", collection="", **kwargs):
        from sentence_transformers import SentenceTransformer
        from pymilvus import MilvusClient

        MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        META_PATH = "/opt/app/data/collection_meta.json"
        DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        if not kw_list:
            return "Error: keywords required (comma-separated)"
        if not collection:
            collection = "plasma_papers"

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

        # 각 키워드별 밀도 분석
        kw_densities = {}
        lines = [f"연구 공백 분석: {', '.join(kw_list)}\n"]
        lines.append("## 개별 키워드 밀도")

        for kw in kw_list:
            vec = model.encode(kw).tolist()
            results = client.search(collection_name=collection, data=[vec], limit=20,
                                    output_fields=["doc_id", "filename"],
                                    search_params={"metric_type": "COSINE"})
            if not results or not results[0]:
                kw_densities[kw] = 0
                lines.append(f"  - {kw}: 밀도=0 (문서 없음)")
                continue

            scores = [h.get("distance", 0) for h in results[0]]
            top5 = sorted(scores, reverse=True)[:5]
            density = sum(top5) / len(top5)
            doc_count = len(set(h["entity"].get("doc_id", "") for h in results[0]))
            kw_densities[kw] = density
            lines.append(f"  - {kw}: 밀도={density:.4f}, 문서={doc_count}건")

        # 교차 조합 분석
        gaps = []
        if len(kw_list) >= 2:
            lines.append("\n## 교차 조합 공백 분석")
            for combo in combinations(kw_list, 2):
                combined = f"{combo[0]} {combo[1]}"
                cv = model.encode(combined).tolist()
                cr = client.search(collection_name=collection, data=[cv], limit=20,
                                   output_fields=["doc_id", "filename"],
                                   search_params={"metric_type": "COSINE"})

                if cr and cr[0]:
                    combo_scores = [h.get("distance", 0) for h in cr[0]]
                    combo_density = sum(combo_scores[:5]) / min(5, len(combo_scores))
                    doc_count = len(set(h["entity"].get("doc_id", "") for h in cr[0]))
                else:
                    combo_density = 0
                    doc_count = 0

                avg_ind = (kw_densities.get(combo[0], 0) + kw_densities.get(combo[1], 0)) / 2
                gap_score = max(0, avg_ind - combo_density)

                if gap_score > 0.1:
                    potential = "높음 ⚠️"
                elif gap_score > 0.05:
                    potential = "보통"
                else:
                    potential = "낮음"

                lines.append(
                    f"  - {combo[0]} × {combo[1]}: 조합밀도={combo_density:.4f}, "
                    f"개별평균={avg_ind:.4f}, gap={gap_score:.4f} [{potential}], 문서={doc_count}건")
                gaps.append((combo, gap_score, potential))

        # 저밀도 단일 키워드
        for kw in kw_list:
            d = kw_densities.get(kw, 0)
            if d < 0.35:
                lines.append(f"\n⚠️ '{kw}' 단독 밀도({d:.4f})가 낮아 관련 연구가 부족합니다.")

        # 요약
        high_gaps = [g for g in gaps if g[1] > 0.05]
        if high_gaps:
            lines.append(f"\n## 요약: {len(high_gaps)}개 잠재적 연구 공백 발견")
            for combo, score, pot in sorted(high_gaps, key=lambda x: -x[1]):
                lines.append(f"  → {combo[0]} × {combo[1]} (gap_score: {score:.4f}, 잠재력: {pot})")

        return "\n".join(lines)

Tool = DetectResearchGapsTool
