# =============================================================================
# compare_diagnostics Tool — 두 진단 방법 비교 분석
# =============================================================================
import os
import sys
import json
import re
from collections import Counter

from base_tool import BaseTool


class CompareDiagnosticsTool(BaseTool):
    name = "compare_diagnostics"
    description = "Compare two plasma diagnostic methods (e.g., OES vs Langmuir probe, SEM vs AFM). Searches literature for each method, extracts unique/common keywords using TF analysis, and provides a structured comparison with differences, commonalities, and relevant papers."
    input_schema = {
        "type": "object",
        "properties": {
            "method_a": {
                "type": "string",
                "description": "First diagnostic method (e.g., 'OES', 'Langmuir probe', 'mass spectrometry')"
            },
            "method_b": {
                "type": "string",
                "description": "Second diagnostic method (e.g., 'ellipsometry', 'SEM', 'XPS')"
            },
            "collection": {
                "type": "string",
                "description": "Collection name. Default: plasma_papers"
            }
        },
        "required": ["method_a", "method_b"]
    }

    STOPWORDS = {
        "the","a","an","is","are","was","were","be","been","being","have","has","had",
        "do","does","did","will","would","shall","should","may","might","must","can","could",
        "of","in","to","for","with","on","at","from","by","as","into","through","during",
        "before","after","above","below","between","out","off","over","under","again",
        "further","then","once","here","there","when","where","why","how","all","both",
        "each","few","more","most","other","some","such","no","nor","not","only","own",
        "same","so","than","too","very","just","about","also","and","but","or","if","that",
        "this","these","those","it","its","which","what","who","whom","their","them","they",
        "we","our","us","you","your","he","she","his","her","him","my","me",
        "플라즈마","plasma","진단","diagnostics","diagnostic","측정","분석","analysis",
        "사용","이용","방법","결과","연구","통해","위해","대한","것으로","있다","수",
        "및","등","또한","따라","있는","하는","된다","이","그","저","것","data","using",
        "used","based","results","study","method","shown","figure","table","et","al",
    }

    def _extract_keywords(self, text, top_n=30):
        words = re.findall(r'[a-zA-Z\u3131-\u318E\uAC00-\uD7A3]{2,}', text.lower())
        tf = Counter(w for w in words if w not in self.STOPWORDS and len(w) > 2)
        return tf.most_common(top_n)

    def execute(self, method_a="", method_b="", collection="", **kwargs):
        from sentence_transformers import SentenceTransformer
        from pymilvus import MilvusClient

        MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        META_PATH = "/opt/app/data/collection_meta.json"
        DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

        if not method_a.strip() or not method_b.strip():
            return "Error: Both method_a and method_b are required."
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

        # Search for each method
        full_texts = {}
        results = {}
        for method in [method_a, method_b]:
            queries = [
                f"plasma diagnostics {method} measurement analysis",
                f"플라즈마 진단 {method} 측정 분석",
                f"{method} principle technique application"
            ]
            all_hits = []
            seen_keys = set()
            for q in queries:
                vec = model.encode([q], normalize_embeddings=True)[0].tolist()
                sr = client.search(collection_name=collection, data=[vec], limit=10,
                                   output_fields=["doc_id", "filename", "text"],
                                   search_params={"metric_type": "COSINE"})
                for h in sr[0]:
                    key = h["entity"].get("doc_id", "") + "_" + str(h.get("id", ""))
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_hits.append(h)
            all_hits.sort(key=lambda h: h.get("distance", 0), reverse=True)
            top_hits = all_hits[:15]
            results[method] = [{"filename": h["entity"].get("filename",""),
                                "score": round(h.get("distance",0), 4)} for h in top_hits]
            full_texts[method] = " ".join(h["entity"].get("text","") for h in top_hits)

        # Keyword analysis
        kw_a = self._extract_keywords(full_texts[method_a], 40)
        kw_b = self._extract_keywords(full_texts[method_b], 40)

        set_a = set(w for w, _ in kw_a)
        set_b = set(w for w, _ in kw_b)
        common_kw = set_a & set_b
        unique_a = [w for w, _ in kw_a if w in (set_a - set_b)][:10]
        unique_b = [w for w, _ in kw_b if w in (set_b - set_a)][:10]
        top_common = [w for w, _ in kw_a if w in common_kw][:8]

        avg_a = sum(r["score"] for r in results[method_a]) / max(len(results[method_a]), 1)
        avg_b = sum(r["score"] for r in results[method_b]) / max(len(results[method_b]), 1)

        lines = [f"'{method_a}' vs '{method_b}' 비교 분석\n"]

        lines.append(f"## {method_a}")
        lines.append(f"  문헌 수: {len(results[method_a])}건, 평균 유사도: {avg_a:.3f}")
        lines.append(f"  고유 키워드: {', '.join(unique_a[:8])}")
        files_a = list(set(r["filename"] for r in results[method_a][:5]))
        lines.append(f"  대표 논문: {', '.join(files_a[:3])}\n")

        lines.append(f"## {method_b}")
        lines.append(f"  문헌 수: {len(results[method_b])}건, 평균 유사도: {avg_b:.3f}")
        lines.append(f"  고유 키워드: {', '.join(unique_b[:8])}")
        files_b = list(set(r["filename"] for r in results[method_b][:5]))
        lines.append(f"  대표 논문: {', '.join(files_b[:3])}\n")

        lines.append("## 공통점")
        if top_common:
            lines.append(f"  공유 키워드: {', '.join(top_common)}")
        docs_a = set(r["filename"] for r in results[method_a])
        docs_b = set(r["filename"] for r in results[method_b])
        common_docs = docs_a & docs_b
        if common_docs:
            lines.append(f"  두 방법을 함께 다루는 논문: {len(common_docs)}건")

        lines.append("\n## 차이점")
        if unique_a:
            lines.append(f"  {method_a} 특화: {', '.join(unique_a[:6])}")
        if unique_b:
            lines.append(f"  {method_b} 특화: {', '.join(unique_b[:6])}")
        if abs(avg_a - avg_b) > 0.05:
            stronger = method_a if avg_a > avg_b else method_b
            lines.append(f"  현재 컬렉션에서 {stronger}의 문헌이 더 풍부합니다.")

        return "\n".join(lines)

Tool = CompareDiagnosticsTool
