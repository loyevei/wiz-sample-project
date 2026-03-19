# =============================================================================
# failure_reasoning Tool — 고장 원인 추론 및 해결 방법 분류
# =============================================================================
import os
import sys
import json
import re

from base_tool import BaseTool

FAILURE_KEYWORDS = {
    "원인분석": [
        r"cause[ds]?", r"reason", r"origin", r"root\s*cause", r"due\s+to",
        r"because", r"attributed", r"resulting\s+from", r"원인", r"이유",
        r"발생.*원인", r"기인"
    ],
    "해결방법": [
        r"solution", r"resolve[ds]?", r"fix(?:ed)?", r"remedy", r"mitigation",
        r"prevent", r"eliminat", r"reduc(?:e|ing|tion)", r"해결", r"방지",
        r"개선", r"대책", r"조치"
    ],
    "관련자료": [
        r"similar", r"related", r"reference", r"review", r"literature",
        r"reported", r"observed", r"참고", r"문헌", r"보고"
    ]
}


class FailureReasoningTool(BaseTool):
    name = "failure_reasoning"
    description = "Analyze plasma process failure by searching literature and classifying results into: cause analysis (원인분석), solution (해결방법), and related references (관련자료). Uses pattern matching to tag each result."
    input_schema = {
        "type": "object",
        "properties": {
            "failure_description": {
                "type": "string",
                "description": "Description of the failure or problem (e.g., 'chamber particle contamination after 1000 wafers', 'RF impedance mismatch causing plasma flickering')"
            },
            "collection": {
                "type": "string",
                "description": "Collection name. Default: plasma_papers"
            }
        },
        "required": ["failure_description"]
    }

    def _classify_text(self, text):
        """Classify text into failure categories using pattern matching"""
        text_lower = text.lower()
        scores = {}
        for category, patterns in FAILURE_KEYWORDS.items():
            score = 0
            for p in patterns:
                matches = re.findall(p, text_lower, re.IGNORECASE)
                score += len(matches)
            scores[category] = score

        if max(scores.values()) == 0:
            return "관련자료"
        return max(scores, key=scores.get)

    def execute(self, failure_description="", collection="", **kwargs):
        from sentence_transformers import SentenceTransformer
        from pymilvus import MilvusClient

        MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        META_PATH = "/opt/app/data/collection_meta.json"
        DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

        if not failure_description.strip():
            return "Error: failure_description is required."
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

        # Multi-query search
        queries = [
            f"{failure_description} cause analysis root cause",
            f"{failure_description} solution fix remedy prevention",
            f"{failure_description} failure mechanism",
            f"plasma process {failure_description} troubleshooting"
        ]

        all_results = []
        for q in queries:
            vec = model.encode([q], normalize_embeddings=True)[0].tolist()
            sr = client.search(collection_name=collection, data=[vec], limit=10,
                               output_fields=["doc_id", "filename", "text"],
                               search_params={"metric_type": "COSINE"})
            for h in sr[0]:
                e = h.get("entity", {})
                all_results.append({
                    "doc_id": e.get("doc_id", ""), "filename": e.get("filename", ""),
                    "text": e.get("text", ""), "score": round(h.get("distance", 0), 4)
                })

        # Deduplicate
        seen, unique = set(), []
        for r in sorted(all_results, key=lambda x: x["score"], reverse=True):
            key = f"{r['doc_id']}_{r['text'][:50]}"
            if key not in seen:
                seen.add(key)
                r["tag"] = self._classify_text(r["text"])
                unique.append(r)
            if len(unique) >= 15:
                break

        if not unique:
            return f"No failure analysis results found for: '{failure_description}'"

        # Group by tag
        tagged = {"원인분석": [], "해결방법": [], "관련자료": []}
        for r in unique:
            tagged[r["tag"]].append(r)

        lines = [f"고장 원인 추론: '{failure_description[:50]}'\n"]

        tag_labels = {"원인분석": "🔍 원인 분석", "해결방법": "🔧 해결 방법", "관련자료": "📚 관련 자료"}
        for tag, label in tag_labels.items():
            items = tagged[tag]
            if not items:
                continue
            lines.append(f"## {label} ({len(items)}건)")
            for i, r in enumerate(items[:4]):
                lines.append(f"  [{i+1}] {r['filename']} (유사도: {r['score']})")
                lines.append(f"      {r['text'][:200]}...")
            lines.append("")

        lines.append(f"총 {len(unique)}건 분석 (원인: {len(tagged['원인분석'])}건, 해결: {len(tagged['해결방법'])}건, 참고: {len(tagged['관련자료'])}건)")

        return "\n".join(lines)

Tool = FailureReasoningTool
