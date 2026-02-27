# =============================================================================
# build_theory_graph Tool — 인과 관계 그래프 구축 (BFS 탐색)
# =============================================================================
import os
import sys
import json
import re
from collections import defaultdict

from base_tool import BaseTool

PLASMA_CONCEPTS = [
    "electron density", "electron temperature", "ion density", "ion energy",
    "plasma potential", "floating potential", "sheath", "bulk plasma",
    "ionization", "recombination", "dissociation", "excitation",
    "mean free path", "collision frequency", "cross section",
    "Debye length", "plasma frequency", "gyro radius",
    "RF power", "DC bias", "impedance", "matching network",
    "etch rate", "deposition rate", "selectivity", "uniformity",
    "reactive species", "radical", "ion flux", "neutral flux",
    "gas pressure", "gas flow", "residence time",
    "전자 밀도", "전자 온도", "이온 에너지", "플라즈마 전위",
    "시스 영역", "벌크 플라즈마", "이온화", "재결합", "해리",
    "평균 자유 경로", "충돌 주파수", "반응 단면적",
    "식각 속도", "증착 속도", "선택비", "균일도",
    "RF 전력", "DC 바이어스", "가스 압력", "가스 유량",
]

CAUSAL_PATTERNS = [
    (r"(\w[\w\s]{2,30})\s+(?:leads?\s+to|results?\s+in|causes?|induces?)\s+(\w[\w\s]{2,30})", "causes"),
    (r"(?:due\s+to|because\s+of|owing\s+to)\s+(\w[\w\s]{2,30}),?\s*(\w[\w\s]{2,30})", "causes"),
    (r"(\w[\w\s]{2,30})\s+(?:depends?\s+on|is\s+determined\s+by)\s+(\w[\w\s]{2,30})", "depends_on"),
    (r"(?:increasing|decreasing|higher|lower)\s+(\w[\w\s]{2,30})\s+(?:increases?|decreases?|enhances?|reduces?)\s+(\w[\w\s]{2,30})", "affects"),
    (r"(\w[\w\s]{2,30})\s+(?:is\s+proportional\s+to|∝|\\propto)\s+(\w[\w\s]{2,30})", "proportional"),
]


def _match_concept(text_fragment):
    """Match text fragment to known plasma concept"""
    fragment_lower = text_fragment.strip().lower()
    for concept in PLASMA_CONCEPTS:
        if concept.lower() in fragment_lower or fragment_lower in concept.lower():
            return concept
    return text_fragment.strip()[:30]


class BuildTheoryGraphTool(BaseTool):
    name = "build_theory_graph"
    description = "Build a causal relationship graph from plasma physics literature. Extracts cause-effect, dependency, and proportional relationships between plasma concepts (electron density, etch rate, RF power, etc.) using NLP patterns. Returns nodes, edges, and BFS traversal from a seed concept."
    input_schema = {
        "type": "object",
        "properties": {
            "seed_concept": {
                "type": "string",
                "description": "Starting concept for graph exploration (e.g., 'electron density', 'etch rate', 'RF power')"
            },
            "collection": {
                "type": "string",
                "description": "Collection name. Default: plasma_papers"
            },
            "depth": {
                "type": "integer",
                "description": "BFS traversal depth from seed (default: 2, max: 3)"
            }
        },
        "required": ["seed_concept"]
    }

    def execute(self, seed_concept="", collection="", depth=2, **kwargs):
        from sentence_transformers import SentenceTransformer
        from pymilvus import MilvusClient

        MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
        META_PATH = "/opt/app/data/collection_meta.json"
        DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

        if not seed_concept.strip():
            return "Error: seed_concept is required."
        if not collection:
            collection = "plasma_papers"
        depth = min(int(depth) if depth else 2, 3)

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

        # BFS traversal
        edges = []
        nodes = set()
        visited = set()
        queue = [seed_concept]
        edge_set = set()

        for d in range(depth):
            next_queue = []
            for concept in queue:
                if concept in visited:
                    continue
                visited.add(concept)
                nodes.add(concept)

                # Search for concept
                search_queries = [
                    f"{concept} effect relationship cause",
                    f"{concept} depends on influence factor",
                    f"{concept} increases decreases plasma"
                ]

                for sq in search_queries:
                    vec = model.encode([sq], normalize_embeddings=True)[0].tolist()
                    results = client.search(collection_name=collection, data=[vec], limit=10,
                                            output_fields=["text"],
                                            search_params={"metric_type": "COSINE"})

                    for hit in results[0]:
                        text = hit["entity"].get("text", "")
                        # Extract causal relations
                        for pattern, rel_type in CAUSAL_PATTERNS:
                            for m in re.finditer(pattern, text, re.IGNORECASE):
                                src = _match_concept(m.group(1))
                                tgt = _match_concept(m.group(2))

                                # Only keep edges involving known concepts or seed
                                src_lower = src.lower()
                                tgt_lower = tgt.lower()
                                concept_lower = concept.lower()

                                relevant = (concept_lower in src_lower or concept_lower in tgt_lower or
                                           src_lower in concept_lower or tgt_lower in concept_lower)
                                if not relevant:
                                    continue

                                edge_key = f"{src}|{tgt}|{rel_type}"
                                if edge_key not in edge_set:
                                    edge_set.add(edge_key)
                                    edges.append({"source": src, "target": tgt, "type": rel_type})
                                    nodes.add(src)
                                    nodes.add(tgt)

                                    # Add to next BFS level
                                    if src != concept and src not in visited:
                                        next_queue.append(src)
                                    if tgt != concept and tgt not in visited:
                                        next_queue.append(tgt)

            queue = list(set(next_queue))[:5]  # Limit breadth

        if not edges:
            return f"No causal relationships found for '{seed_concept}'."

        # Format output
        rel_labels = {"causes": "→ (원인)", "depends_on": "← (의존)", "affects": "⇄ (영향)", "proportional": "∝ (비례)"}

        lines = [f"이론 인과 그래프: '{seed_concept}' (깊이 {depth})\n"]
        lines.append(f"노드: {len(nodes)}개, 엣지: {len(edges)}개\n")

        # Group edges by type
        by_type = defaultdict(list)
        for e in edges:
            by_type[e["type"]].append(e)

        for rel_type, label in rel_labels.items():
            type_edges = by_type.get(rel_type, [])
            if not type_edges:
                continue
            lines.append(f"## {label} ({len(type_edges)}건)")
            for e in type_edges[:8]:
                lines.append(f"  {e['source']} → {e['target']}")
            lines.append("")

        # Connected concepts
        connected = set()
        for e in edges:
            if seed_concept.lower() in e["source"].lower():
                connected.add(e["target"])
            elif seed_concept.lower() in e["target"].lower():
                connected.add(e["source"])

        if connected:
            lines.append(f"## '{seed_concept}'와 직접 연결된 개념")
            for c in list(connected)[:10]:
                lines.append(f"  - {c}")

        return "\n".join(lines)

Tool = BuildTheoryGraphTool
