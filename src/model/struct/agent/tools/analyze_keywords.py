# =============================================================================
# analyze_keywords Tool — 검색 결과 기반 키워드/주제 분석
# =============================================================================
import os
import sys
import json
import re
from collections import Counter

from base_tool import BaseTool

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "into", "about", "between", "through", "during", "before", "after",
    "above", "below", "and", "or", "but", "not", "no", "nor",
    "this", "that", "these", "those", "it", "its", "they", "them",
    "we", "our", "you", "your", "he", "she", "his", "her",
    "which", "who", "whom", "what", "where", "when", "how", "than", "then",
    "also", "very", "just", "only", "still", "even", "more", "most",
    "such", "each", "every", "both", "all", "any", "some", "other",
    "up", "out", "if", "so", "like", "over", "one", "two",
    "fig", "figure", "table", "ref", "et", "al", "pp", "vol",
    "의", "은", "는", "이", "가", "을", "를", "에", "에서", "로", "으로",
    "와", "과", "도", "만", "까지", "부터", "한", "된", "하는", "있는",
    "등", "및", "또는", "그", "이", "저", "것", "수", "중",
    "using", "used", "based", "show", "shown", "shows", "results",
    "however", "therefore", "thus", "hence", "respectively",
}


class AnalyzeKeywordsTool(BaseTool):
    name = "analyze_keywords"
    description = "Analyze research papers on a topic and extract key terms, themes, and trends. Searches the database and performs keyword frequency analysis to identify important concepts and research directions."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Research topic to analyze (e.g., 'plasma etching selectivity', 'OES diagnostics')"
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

        # 모델
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

        # 검색
        query_vec = model.encode(query).tolist()
        results = client.search(
            collection_name=collection,
            data=[query_vec],
            limit=30,
            output_fields=["doc_id", "filename", "text"],
            search_params={"metric_type": "COSINE"}
        )

        if not results or not results[0]:
            return f"No results found for '{query}'."

        # 텍스트 수집
        all_text = ""
        filenames = set()
        for hit in results[0]:
            entity = hit.get("entity", {})
            all_text += " " + entity.get("text", "")
            filenames.add(entity.get("filename", "unknown"))

        # 키워드 추출
        words = re.findall(r'[a-zA-Z가-힣]{2,}', all_text.lower())
        counter = Counter(w for w in words if w not in STOPWORDS and len(w) > 2)
        top_keywords = counter.most_common(30)

        # 결과 포맷팅
        lines = [f"Keyword Analysis for '{query}' ({len(results[0])} documents analyzed from '{collection}'):\n"]

        lines.append("## Top Keywords (by frequency)")
        for kw, cnt in top_keywords:
            lines.append(f"  - {kw}: {cnt}")

        lines.append(f"\n## Source Documents ({len(filenames)} unique files)")
        for fn in sorted(filenames):
            lines.append(f"  - {fn}")

        return "\n".join(lines)


Tool = AnalyzeKeywordsTool
