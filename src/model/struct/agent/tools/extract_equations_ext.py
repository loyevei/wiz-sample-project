# =============================================================================
# extract_equations Tool — 문헌에서 수식 추출 + 도메인 분류
# =============================================================================
import os
import sys
import json
import re
from collections import Counter

from base_tool import BaseTool

PLASMA_EQUATIONS = {
    "boltzmann": {"name": "Boltzmann 방정식", "category": "governing",
        "patterns": [r"\\frac\{\\partial\s*f\}", r"Boltzmann\s+equation", r"distribution\s+function.*collision"]},
    "poisson": {"name": "Poisson 방정식", "category": "governing",
        "patterns": [r"\\nabla\^2\s*\\phi", r"\\nabla\^2\s*V", r"Poisson.*equation"]},
    "continuity": {"name": "연속 방정식", "category": "governing",
        "patterns": [r"\\frac\{\\partial\s*n\}", r"continuity\s+equation", r"\\nabla\s*\\cdot.*n.*v"]},
    "energy_balance": {"name": "에너지 보존식", "category": "governing",
        "patterns": [r"energy\s+balance", r"\\frac\{\\partial.*T\}", r"energy\s+conservation"]},
    "maxwellian": {"name": "Maxwellian 분포", "category": "constitutive",
        "patterns": [r"Maxwellian", r"f.*exp.*-.*kT", r"Maxwell.*distribution"]},
    "drude": {"name": "Drude 모델", "category": "empirical",
        "patterns": [r"Drude\s+model", r"\\sigma.*=.*ne\^2.*\\tau"]},
    "debye_length": {"name": "Debye 길이", "category": "constitutive",
        "patterns": [r"Debye\s+length", r"\\lambda_D", r"Debye\s+shielding"]},
    "langmuir_probe": {"name": "Langmuir 프로브 이론", "category": "empirical",
        "patterns": [r"Langmuir\s+probe", r"I-V\s+characteristic"]},
    "child_langmuir": {"name": "Child-Langmuir 법칙", "category": "empirical",
        "patterns": [r"Child.*Langmuir", r"space.*charge.*limited"]},
    "paschen": {"name": "Paschen 법칙", "category": "empirical",
        "patterns": [r"Paschen", r"breakdown\s+voltage.*pd"]},
    "saha": {"name": "Saha 방정식", "category": "constitutive",
        "patterns": [r"Saha.*equation", r"ionization\s+equilibrium"]},
    "arrhenius": {"name": "Arrhenius 식", "category": "empirical",
        "patterns": [r"Arrhenius", r"k.*=.*A.*exp.*-E_a", r"activation\s+energy"]},
}

EQUATION_CATEGORIES = {
    "governing": "지배 방정식", "boundary": "경계 조건",
    "constitutive": "구성 관계", "empirical": "경험식", "other": "기타"
}


def _extract_latex_equations(text):
    equations = []
    seen = set()
    # [EQUATION: ...] markers
    for m in re.finditer(r'\[(?:EQUATION|FORMULA):\s*([^\]]+)\]', text):
        content = m.group(1)
        latex_m = re.search(r'\$\$(.+?)\$\$', content) or re.search(r'\$([^\$]+)\$', content)
        if latex_m:
            latex = latex_m.group(1).strip()
        else:
            parts = content.split("|")
            latex = parts[-1].strip() if len(parts) > 1 else content.strip()
            latex = re.sub(r'^context:\s*', '', latex)
        if latex and latex not in seen:
            seen.add(latex)
            equations.append({"latex": latex, "start": m.start(), "end": m.end()})
    # $$...$$ display
    for m in re.finditer(r'\$\$(.+?)\$\$', text, re.DOTALL):
        latex = m.group(1).strip()
        if latex and latex not in seen:
            seen.add(latex)
            equations.append({"latex": latex, "start": m.start(), "end": m.end()})
    # $...$ inline
    for m in re.finditer(r'(?<!\$)\$([^\$]{3,200})\$(?!\$)', text):
        latex = m.group(1).strip()
        if latex and latex not in seen:
            seen.add(latex)
            equations.append({"latex": latex, "start": m.start(), "end": m.end()})
    # formula patterns (=, ∝, ≈)
    for m in re.finditer(r'([A-Za-z_\\][^\n]{5,100}(?:=|∝|≈|\\approx|\\propto)[^\n]{3,100})', text):
        eq = m.group(1).strip()
        if len(eq) > 10 and eq not in seen:
            seen.add(eq)
            equations.append({"latex": eq, "start": m.start(), "end": m.end()})
    return equations


def _classify_equation(latex):
    for eq_id, info in PLASMA_EQUATIONS.items():
        for p in info["patterns"]:
            if re.search(p, latex, re.IGNORECASE):
                return {"id": eq_id, "name": info["name"], "category": info["category"],
                        "category_label": EQUATION_CATEGORIES.get(info["category"], "기타")}
    return {"id": "unknown", "name": None, "category": "other", "category_label": "기타"}


class ExtractEquationsTool(BaseTool):
    name = "extract_equations"
    description = "Extract and classify mathematical equations from plasma physics literature in a vector collection. Identifies 12 types of plasma equations (Boltzmann, Poisson, continuity, etc.) with category classification (governing, constitutive, empirical). Can search by keyword or scan entire collection."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Optional search query to focus on specific equations (e.g., 'Boltzmann equation', 'Debye length'). If empty, scans all documents."
            },
            "collection": {
                "type": "string",
                "description": "Collection name. Default: plasma_papers"
            }
        },
        "required": []
    }

    def execute(self, query="", collection="", **kwargs):
        from sentence_transformers import SentenceTransformer
        from pymilvus import MilvusClient

        MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        META_PATH = "/opt/app/data/collection_meta.json"
        DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

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

        if query.strip():
            # Targeted search
            search_text = f"equation formula {query}"
            vec = model.encode([search_text], normalize_embeddings=True)[0].tolist()
            results = client.search(collection_name=collection, data=[vec], limit=30,
                                    output_fields=["doc_id", "filename", "text"],
                                    search_params={"metric_type": "COSINE"})
            chunks = [{"text": h["entity"].get("text",""), "filename": h["entity"].get("filename",""),
                       "doc_id": h["entity"].get("doc_id","")} for h in results[0]]
        else:
            # Scan all (limited)
            chunks = client.query(collection_name=collection, filter="chunk_index >= 0",
                                  output_fields=["doc_id", "filename", "text"], limit=500)

        all_equations = []
        category_count = Counter()
        doc_count = Counter()

        for chunk in chunks:
            text = chunk.get("text", "")
            eqs = _extract_latex_equations(text)
            for eq in eqs:
                cls = _classify_equation(eq["latex"])
                ctx_s = max(0, eq["start"] - 100)
                ctx_e = min(len(text), eq["end"] + 100)
                all_equations.append({
                    "latex": eq["latex"][:200],
                    "classification": cls,
                    "filename": chunk.get("filename", ""),
                    "context": text[ctx_s:ctx_e][:200]
                })
                category_count[cls["category"]] += 1
                doc_count[chunk.get("filename", "")] += 1

        if not all_equations:
            return f"No equations found" + (f" for '{query}'" if query else "") + "."

        lines = [f"수식 추출 결과 (총 {len(all_equations)}개)\n"]

        # Stats
        lines.append("## 카테고리별 분포")
        for cat, cnt in category_count.most_common():
            label = EQUATION_CATEGORIES.get(cat, cat)
            lines.append(f"  {label}: {cnt}개")

        # Known equations
        known = [e for e in all_equations if e["classification"]["id"] != "unknown"]
        if known:
            lines.append(f"\n## 식별된 수식 ({len(known)}개)")
            seen_names = set()
            for e in known:
                name = e["classification"]["name"]
                if name and name not in seen_names:
                    seen_names.add(name)
                    lines.append(f"  - {name} [{e['classification']['category_label']}] ({e['filename']})")
                    lines.append(f"    수식: {e['latex'][:80]}...")

        # Top documents
        lines.append(f"\n## 수식 포함 상위 문서")
        for fn, cnt in doc_count.most_common(5):
            lines.append(f"  {fn}: {cnt}개")

        return "\n".join(lines)

Tool = ExtractEquationsTool
