import os
import sys
import json
import re
import uuid
import datetime
import tempfile
import traceback
import shutil

import fitz  # PyMuPDF
import numpy as np
from sentence_transformers import SentenceTransformer
from pymilvus import MilvusClient, DataType, CollectionSchema, FieldSchema
import season.lib.exception

# OCR 지원
try:
    import pytesseract
    from PIL import Image
    import io
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

# ==============================================================================
# 설정
# ==============================================================================
MILVUS_URI = os.environ.get("MILVUS_URI", "/opt/app/data/milvus.db")
COLLECTION_META_PATH = "/opt/app/data/collection_meta.json"
DATA_DIR = "/opt/app/data"
PAGES_DIR = os.path.join(DATA_DIR, "pages")  # /data/pages/{collection}/{doc_id}/page_NNNN.png
DEFAULT_COLLECTION = "plasma_papers"
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100

# 페이지 PNG 렌더링 DPI
PAGE_RENDER_DPI = 150     # 본문 (모달용)
THUMB_RENDER_DPI = 75     # 썸네일 (목록용)

# ==============================================================================
# 모델 레지스트리
# ==============================================================================
MODEL_REGISTRY = wiz.model("modelregistry").full()
DEFAULT_MODEL = wiz.model("modelregistry").default_model()

# ==============================================================================
# 청킹 전략 레지스트리
# ==============================================================================
CHUNK_STRATEGIES = {
    "semantic_section": {
        "name": "semantic_section",
        "label": "시맨틱 (섹션 기반)",
        "description": "섹션 헤더 → 문단 → 문장 경계 기반 의미 단위 분할. 기본 추천 전략.",
        "params": ["chunk_size", "chunk_overlap", "respect_sentences"],
        "default": True
    },
    "fixed": {
        "name": "fixed",
        "label": "고정 크기 (Fixed-size)",
        "description": "지정한 문자 수로 기계적 분할. 오버랩으로 문맥 보존. 가장 단순하고 빠름.",
        "params": ["chunk_size", "chunk_overlap"]
    },
    "sentence": {
        "name": "sentence",
        "label": "문장 기반 (Sentence)",
        "description": "문장 단위로 분리 후 chunk_size 내에서 그룹핑. 문장 경계가 항상 보존됨.",
        "params": ["chunk_size"]
    },
    "paragraph": {
        "name": "paragraph",
        "label": "문단 기반 (Paragraph)",
        "description": "빈 줄(\\n\\n) 기준 문단 분할. 짧은 문단은 병합. 논문 구조에 적합.",
        "params": ["chunk_size"]
    },
    "recursive": {
        "name": "recursive",
        "label": "재귀 분할 (Recursive)",
        "description": "구분자 계층(\\n\\n → \\n → 문장 → 공백) 순차 적용. LangChain 스타일.",
        "params": ["chunk_size", "chunk_overlap"]
    },
    "semantic_embedding": {
        "name": "semantic_embedding",
        "label": "시맨틱 (임베딩 유사도)",
        "description": "인접 문장 간 임베딩 코사인 유사도로 분할점 결정. 가장 정밀하나 느림.",
        "params": ["chunk_size", "similarity_threshold"]
    }
}

# ==============================================================================
# 유니코드 → LaTeX 매핑 (수식 변환용)
# ==============================================================================
UNICODE_TO_LATEX = {
    # 그리스 소문자
    'α': r'\alpha', 'β': r'\beta', 'γ': r'\gamma', 'δ': r'\delta',
    'ε': r'\epsilon', 'ζ': r'\zeta', 'η': r'\eta', 'θ': r'\theta',
    'ι': r'\iota', 'κ': r'\kappa', 'λ': r'\lambda', 'μ': r'\mu',
    'ν': r'\nu', 'ξ': r'\xi', 'π': r'\pi', 'ρ': r'\rho',
    'σ': r'\sigma', 'τ': r'\tau', 'υ': r'\upsilon', 'φ': r'\varphi',
    'χ': r'\chi', 'ψ': r'\psi', 'ω': r'\omega',
    'ϵ': r'\varepsilon', 'ϑ': r'\vartheta', 'ϕ': r'\phi', 'ϱ': r'\varrho',
    'ϖ': r'\varpi', 'ϰ': r'\varkappa', 'ϝ': r'\digamma',
    # 그리스 대문자
    'Γ': r'\Gamma', 'Δ': r'\Delta', 'Θ': r'\Theta', 'Λ': r'\Lambda',
    'Ξ': r'\Xi', 'Π': r'\Pi', 'Σ': r'\Sigma', 'Υ': r'\Upsilon',
    'Φ': r'\Phi', 'Ψ': r'\Psi', 'Ω': r'\Omega',
    # 연산자/기호
    '∫': r'\int', '∬': r'\iint', '∭': r'\iiint', '∮': r'\oint',
    '∑': r'\sum', '∏': r'\prod', '∐': r'\coprod',
    '∂': r'\partial', '√': r'\sqrt', '∛': r'\sqrt[3]', '∜': r'\sqrt[4]',
    '∞': r'\infty', '±': r'\pm', '∓': r'\mp',
    '×': r'\times', '÷': r'\div', '⋅': r'\cdot', '∗': r'\ast',
    '≈': r'\approx', '≠': r'\neq', '≤': r'\leq', '≥': r'\geq',
    '≪': r'\ll', '≫': r'\gg', '≲': r'\lesssim', '≳': r'\gtrsim',
    '∈': r'\in', '∉': r'\notin', '∋': r'\ni',
    '⊂': r'\subset', '⊃': r'\supset', '⊆': r'\subseteq', '⊇': r'\supseteq',
    '∪': r'\cup', '∩': r'\cap', '∀': r'\forall', '∃': r'\exists', '∄': r'\nexists',
    '∅': r'\emptyset', '∇': r'\nabla', '∆': r'\Delta',
    '∝': r'\propto', '∼': r'\sim', '≡': r'\equiv', '≅': r'\cong', '≃': r'\simeq',
    '⊥': r'\perp', '∧': r'\wedge', '∨': r'\vee', '¬': r'\neg',
    '→': r'\rightarrow', '←': r'\leftarrow', '↔': r'\leftrightarrow',
    '⇒': r'\Rightarrow', '⇐': r'\Leftarrow', '⇔': r'\Leftrightarrow',
    '↦': r'\mapsto', '↗': r'\nearrow', '↘': r'\searrow',
    '↑': r'\uparrow', '↓': r'\downarrow', '⇑': r'\Uparrow', '⇓': r'\Downarrow',
    '∘': r'\circ', '·': r'\cdot', '†': r'\dagger', '‡': r'\ddagger',
    '⊗': r'\otimes', '⊕': r'\oplus', '⊖': r'\ominus', '⊘': r'\oslash',
    '⊙': r'\odot', '⊞': r'\boxplus', '⊠': r'\boxtimes',
    '⟨': r'\langle', '⟩': r'\rangle', '⌊': r'\lfloor', '⌋': r'\rfloor',
    '⌈': r'\lceil', '⌉': r'\rceil', '‖': r'\|',
    # 위/아래 첨자 숫자
    '⁰': '^{0}', '¹': '^{1}', '²': '^{2}', '³': '^{3}', '⁴': '^{4}',
    '⁵': '^{5}', '⁶': '^{6}', '⁷': '^{7}', '⁸': '^{8}', '⁹': '^{9}',
    '₀': '_{0}', '₁': '_{1}', '₂': '_{2}', '₃': '_{3}', '₄': '_{4}',
    '₅': '_{5}', '₆': '_{6}', '₇': '_{7}', '₈': '_{8}', '₉': '_{9}',
    # 위/아래 첨자 문자
    'ⁱ': '^{i}', 'ⁿ': '^{n}', 'ⁿ': '^{n}', 'ˡ': '^{l}',
    'ₐ': '_{a}', 'ₑ': '_{e}', 'ₒ': '_{o}', 'ₓ': '_{x}',
    'ₕ': '_{h}', 'ₖ': '_{k}', 'ₗ': '_{l}', 'ₘ': '_{m}',
    'ₙ': '_{n}', 'ₚ': '_{p}', 'ₛ': '_{s}', 'ₜ': '_{t}',
    '⁺': '^{+}', '⁻': '^{-}', '⁼': '^{=}', '⁽': '^{(}', '⁾': '^{)}',
    '₊': '_{+}', '₋': '_{-}', '₌': '_{=}', '₍': '_{(}', '₎': '_{)}',
    # 수학 문자 (Mathematical Alphanumeric Symbols)
    'ℏ': r'\hbar', 'ℓ': r'\ell', 'ℝ': r'\mathbb{R}', 'ℂ': r'\mathbb{C}',
    'ℤ': r'\mathbb{Z}', 'ℕ': r'\mathbb{N}', 'ℚ': r'\mathbb{Q}',
    'ℋ': r'\mathcal{H}', 'ℒ': r'\mathcal{L}', 'ℱ': r'\mathcal{F}',
    '℘': r'\wp', 'ℑ': r'\Im', 'ℜ': r'\Re', 'ℵ': r'\aleph',
    '⅓': r'\frac{1}{3}', '⅔': r'\frac{2}{3}', '¼': r'\frac{1}{4}',
    '½': r'\frac{1}{2}', '¾': r'\frac{3}{4}', '⅕': r'\frac{1}{5}',
    # 그 밖의 수학 심볼
    '′': "'", '″': "''", '‴': "'''",
    '°': r'^\circ', '∠': r'\angle', '⊿': r'\triangle',
    '∥': r'\parallel', 'ℓ': r'\ell',
    '⋯': r'\cdots', '⋮': r'\vdots', '⋱': r'\ddots', '…': r'\ldots',
}

# ==============================================================================
# 수식/그림/표 감지용 상수
# ==============================================================================
MATH_FONTS = {
    "symbol", "cmmi", "cmsy", "cmr", "cmex", "mathjax", "stix", "cambria math", "math",
    "mathitalic", "mt extra", "euclid",
    "mathematica", "lucida math", "asana math", "dejavu math", "xits math",
    "latin modern math", "libertinus math", "fira math", "garamond-math",
}
MATH_CHARS = set(
    "∫∬∭∮∑∏∂√∛∜∞±∓×÷≈≠≤≥≪≫∈∉∋⊂⊃⊆⊇∪∩∀∃∄∅∇∆"
    "αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΥΦΨΩ"
    "ϵϑϕϱϖϰ"
    "∝∼≡≅≃⊥∧∨¬→←↔⇒⇐⇔↦↑↓⇑⇓"
    "∘·†‡⊗⊕⊖⊘⊙⟨⟩⌊⌋⌈⌉‖"
    "ℏℓℝℂℤℕℚℋℒℱ℘ℑℜℵ"
    "⋯⋮⋱′″‴°∠⊿∥"
)
# 수식 번호 패턴 (예: "(1)", "(2.3)", "(A.1)")
EQUATION_NUMBER_PATTERN = re.compile(r'^\s*\((?:\d+\.?\d*|[A-Z]\.?\d*)\)\s*$')
# 수반 텍스트 없이 수식만 있는 라인 패턴
EQUATION_LINE_PATTERNS = [
    re.compile(r'^[^a-zA-Z가-힣]*[=<>≈≡∝∼≤≥≪≫]+[^a-zA-Z가-힣]*$'),  # 등호/부등호만 있는 줄
    re.compile(r'^\s*[A-Za-z]\s*[=]\s*.+$'),  # "x = ..." 형태
    re.compile(r'^\s*\\?(?:frac|int|sum|prod|lim|max|min|log|exp|sin|cos|tan)\b'),  # LaTeX 명령
]
FIGURE_PATTERNS = re.compile(r'^\s*(Fig\.?|Figure|그림|FIGURE|fig\.?)\s*\.?\s*\d', re.IGNORECASE)
TABLE_CAPTION_PATTERNS = re.compile(r'^\s*(Table|표|TABLE)\s*\.?\s*\d', re.IGNORECASE)
SPECIAL_MARKER = re.compile(r'\[(FIGURE|EQUATION|TABLE):\s')
TEMPORAL_SIGNAL_PATTERNS = {
    "online_year": [
        r'available\s+online[\s\S]{0,80}?((?:19|20)\d{2})',
        r'online[\s\S]{0,40}?((?:19|20)\d{2})',
    ],
    "publication_year": [
        r'published[\s\S]{0,80}?((?:19|20)\d{2})',
        r'\b(?:applied|journal|vacuum|thin solid films|materials science|micromachines|physics)\b[^\n]{0,60}\(((?:19|20)\d{2})\)',
        r'\(((?:19|20)\d{2})\)',
    ],
    "accepted_year": [
        r'accepted[\s\S]{0,80}?((?:19|20)\d{2})',
    ],
    "received_year": [
        r'received[\s\S]{0,80}?((?:19|20)\d{2})',
    ],
}

# ==============================================================================
# sys 모듈 캐시
# ==============================================================================
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
    """Milvus Lite 클라이언트 (싱글톤 캐시)
    Milvus Lite는 SQLite 기반이므로 동일 프로세스에서 여러 MilvusClient를
    생성하면 데드락이 발생한다. 반드시 단일 인스턴스를 재사용해야 한다.
    """
    if not hasattr(sys, '_milvus_client') or sys._milvus_client is None:
        db_path = MILVUS_URI
        if not db_path.startswith("http"):
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        sys._milvus_client = MilvusClient(uri=db_path)
    return sys._milvus_client

# ==============================================================================
# 컬렉션 메타데이터 관리
# ==============================================================================
def _load_collection_meta():
    meta_helper = wiz.model("collectionmeta")
    return meta_helper.load(COLLECTION_META_PATH)

def _save_collection_meta(meta):
    os.makedirs(os.path.dirname(COLLECTION_META_PATH), exist_ok=True)
    with open(COLLECTION_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _count_collection_pdfs(collection_name):
    pdf_dir = os.path.join(DATA_DIR, "pdfs", collection_name)
    if not os.path.isdir(pdf_dir):
        return 0
    try:
        return sum(1 for name in os.listdir(pdf_dir) if name.lower().endswith('.pdf'))
    except Exception:
        return 0

def _get_collection_model(collection_name):
    meta_helper = wiz.model("collectionmeta")
    return meta_helper.get_model(COLLECTION_META_PATH, collection_name, DEFAULT_MODEL)

def _infer_model_from_dim(dim):
    registry = wiz.model("modelregistry")
    return registry.infer_model_from_dim(dim, DEFAULT_MODEL)


def _get_collection_fields(client, collection_name):
    """컬렉션 스키마의 필드명 집합 반환"""
    try:
        col_info = client.describe_collection(collection_name)
        return {f["name"] for f in col_info.get("fields", [])}
    except Exception:
        return set()


# ==============================================================================
# 컬렉션 생성 (확장 스키마)
# ==============================================================================
def _ensure_collection(collection_name, model_name=None, client=None):
    if client is None:
        client = _get_client()
    if not client.has_collection(collection_name, timeout=10):
        if model_name is None:
            model_name = DEFAULT_MODEL
        dim = MODEL_REGISTRY.get(model_name, {}).get("dim", 768)

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="chunk_type", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="page_num", dtype=DataType.INT64),
            FieldSchema(name="bbox", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="section_title", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="content_elements", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="structured_content", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        ]
        schema = CollectionSchema(fields=fields, description=f"Embeddings ({model_name})")
        index_params = client.prepare_index_params()
        index_params.add_index(field_name="embedding", index_type="FLAT", metric_type="COSINE")
        client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params,
            timeout=15
        )

        meta = _load_collection_meta()
        meta[collection_name] = {
            "model": model_name, "dim": dim,
            "created_at": datetime.datetime.now().isoformat(),
            "short_name": MODEL_REGISTRY.get(model_name, {}).get("short_name", model_name),
            "total_docs": 0,
            "total_chunks": 0
        }
        _save_collection_meta(meta)

    return client

# ==============================================================================
# 유니코드 → LaTeX 변환 (구조적 재구성 포함)
# ==============================================================================
_SUPERSCRIPT_MAP = {
    '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
    '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
    '⁺': '+', '⁻': '-', '⁼': '=', '⁽': '(', '⁾': ')',
    'ⁱ': 'i', 'ⁿ': 'n', 'ˡ': 'l',
}
_SUBSCRIPT_MAP = {
    '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
    '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
    '₊': '+', '₋': '-', '₌': '=', '₍': '(', '₎': ')',
    'ₐ': 'a', 'ₑ': 'e', 'ₒ': 'o', 'ₓ': 'x',
    'ₕ': 'h', 'ₖ': 'k', 'ₗ': 'l', 'ₘ': 'm',
    'ₙ': 'n', 'ₚ': 'p', 'ₛ': 's', 'ₜ': 't',
}

def _unicode_to_latex(text):
    """유니코드 수학 기호를 LaTeX 명령어로 변환 — 구조적 위/아래 첨자 그룹핑 포함"""
    result = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]

        # 연속 위 첨자를 ^{...}로 그룹핑
        if ch in _SUPERSCRIPT_MAP:
            group = []
            while i < n and text[i] in _SUPERSCRIPT_MAP:
                group.append(_SUPERSCRIPT_MAP[text[i]])
                i += 1
            result.append('^{' + ''.join(group) + '}')
            continue

        # 연속 아래 첨자를 _{...}로 그룹핑
        if ch in _SUBSCRIPT_MAP:
            group = []
            while i < n and text[i] in _SUBSCRIPT_MAP:
                group.append(_SUBSCRIPT_MAP[text[i]])
                i += 1
            result.append('_{' + ''.join(group) + '}')
            continue

        # 일반 매핑
        if ch in UNICODE_TO_LATEX:
            result.append(UNICODE_TO_LATEX[ch])
        else:
            result.append(ch)
        i += 1

    latex = ''.join(result)

    # 후처리: 분수 패턴 인식 (a/b → \frac{a}{b} for simple cases)
    # 단, 이미 \frac가 있거나 URL 같은 패턴은 건드리지 않음
    if r'\frac' not in latex and '/' in latex:
        latex = re.sub(
            r'(?<![a-zA-Z/\\])([a-zA-Z0-9\\]+(?:\{[^}]*\})?)\s*/\s*([a-zA-Z0-9\\]+(?:\{[^}]*\})?)',
            r'\\frac{\1}{\2}',
            latex
        )

    return latex


def _build_structured_latex(lines):
    """블록 내 span들의 폰트 크기/위치 정보를 활용하여 구조적 LaTeX를 재구성한다.
    PyMuPDF의 span 위치(origin, bbox)에서 위/아래 첨자 관계를 추론한다."""
    if not lines:
        return ""

    # 전체 span에서 기준(base) 폰트 크기 결정
    all_spans = []
    for line in lines:
        for span in line.get("spans", []):
            text = span.get("text", "").strip()
            if text:
                all_spans.append(span)

    if not all_spans:
        return ""

    sizes = [s.get("size", 12) for s in all_spans]
    base_size = max(set(sizes), key=sizes.count)  # 최빈값

    latex_parts = []
    for line in lines:
        spans = line.get("spans", [])
        line_parts = []
        for span in spans:
            text = span.get("text", "").strip()
            if not text:
                continue
            size = span.get("size", 12)
            origin_y = span.get("origin", [0, 0])[1] if "origin" in span else None
            flags = span.get("flags", 0)

            # 유니코드→LaTeX 기본 변환
            latex_text = _unicode_to_latex(text)

            # 폰트 크기가 base보다 확연히 작으면 위/아래 첨자 후보
            if size < base_size * 0.75 and origin_y is not None and len(line_parts) > 0:
                # span의 origin.y와 이전 span 대비 위치로 위/아래 구분
                prev_span = None
                for s in reversed(all_spans):
                    if s is not span and "origin" in s and s.get("size", 12) >= base_size * 0.75:
                        prev_span = s
                        break
                if prev_span and "origin" in prev_span:
                    prev_y = prev_span["origin"][1]
                    if origin_y < prev_y - 2:  # 위쪽
                        latex_text = '^{' + latex_text + '}'
                    elif origin_y > prev_y + 2:  # 아래쪽
                        latex_text = '_{' + latex_text + '}'

            line_parts.append(latex_text)
        if line_parts:
            latex_parts.append(' '.join(line_parts))

    return ' '.join(latex_parts)

# ==============================================================================
# 이미지 OCR 추출
# ==============================================================================
def _extract_image_ocr(page, img_block):
    """이미지 블록에서 OCR로 텍스트 추출 (Tesseract 사용)"""
    if not HAS_TESSERACT:
        return ""
    try:
        bbox = img_block.get("bbox", [0, 0, 0, 0])
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        # 너무 작은 이미지 스킵 (아이콘/장식)
        if width < 50 or height < 50:
            return ""
        # 이미지 영역 렌더링 (해상도 2x)
        clip = fitz.Rect(bbox)
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat, clip=clip)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        # Tesseract OCR (한국어+영어)
        ocr_text = pytesseract.image_to_string(img, lang="kor+eng", config="--psm 6")
        ocr_text = ocr_text.strip()
        # 너무 짧거나 노이즈인 경우 무시
        if len(ocr_text) < 5:
            return ""
        return ocr_text
    except Exception:
        return ""

# ==============================================================================
# 표 → 마크다운 변환
# ==============================================================================
def _table_to_markdown(table):
    """PyMuPDF 테이블 → 마크다운 테이블 형식 변환"""
    try:
        rows = table.extract()
        if not rows:
            return "", 0, 0
        num_rows = len(rows)
        num_cols = max(len(r) for r in rows) if rows else 0
        if num_cols == 0:
            return "", 0, 0

        md_lines = []
        # 첫 행을 헤더로 사용
        header = rows[0]
        header_cells = [str(c).strip() if c else "" for c in header]
        md_lines.append("| " + " | ".join(header_cells) + " |")
        md_lines.append("| " + " | ".join(["---"] * len(header_cells)) + " |")
        # 나머지 행
        for row in rows[1:]:
            cells = [str(c).strip() if c else "" for c in row]
            # 열 수 맞추기
            while len(cells) < len(header_cells):
                cells.append("")
            md_lines.append("| " + " | ".join(cells[:len(header_cells)]) + " |")

        md_text = "\n".join(md_lines)
        return md_text, num_rows, num_cols
    except Exception:
        return "", 0, 0

# ==============================================================================
# 수식 감지 및 LaTeX 변환
# ==============================================================================
def _is_math_span(span):
    """span이 수식인지 판별 — 폰트명, 유니코드 문자 비율, 위/아래 첨자 문자 기반."""
    font = span.get("font", "").lower()
    text = span.get("text", "")
    # 1. 수식 전용 폰트
    for mf in MATH_FONTS:
        if mf in font:
            return True
    if len(text) == 0:
        return False
    # 2. 유니코드 수학 문자 비율
    math_count = sum(1 for c in text if c in MATH_CHARS)
    sub_sup_count = sum(1 for c in text if c in _SUPERSCRIPT_MAP or c in _SUBSCRIPT_MAP)
    special_count = math_count + sub_sup_count
    if special_count > 0 and special_count / len(text) > 0.25:
        return True
    # 3. 등호가 있고 짧은 텍스트 (변수 = 값 패턴)
    if '=' in text and len(text) < 50 and any(c in MATH_CHARS or c.isdigit() for c in text):
        alpha_count = sum(1 for c in text if c.isalpha() and c not in MATH_CHARS)
        if alpha_count < len(text) * 0.5:
            return True
    return False

def _classify_equation_type(block, lines):
    """수식이 인라인인지 디스플레이(독립 블록)인지 판별"""
    total_spans = 0
    math_spans = 0
    for line in lines:
        for span in line.get("spans", []):
            total_spans += 1
            if _is_math_span(span):
                math_spans += 1
    if total_spans == 0:
        return "inline"
    # 대부분 수식 span이면 display
    if math_spans / total_spans > 0.6:
        return "display"
    return "inline"

def _detect_section_header(block, median_font_size):
    """블록이 섹션 헤더인지 판별"""
    lines = block.get("lines", [])
    if not lines:
        return None
    spans = lines[0].get("spans", [])
    if not spans:
        return None
    span = spans[0]
    size = span.get("size", 0)
    flags = span.get("flags", 0)
    text = span.get("text", "").strip()
    if not text or len(text) > 200:
        return None
    is_bold = flags & 2 ** 4
    is_larger = size > median_font_size * 1.15
    section_pattern = re.match(r'^(\d+\.?\d*\.?\s+)', text)
    if (is_bold and is_larger) or (is_larger and section_pattern):
        full_text = ""
        for line in lines:
            for s in line.get("spans", []):
                full_text += s.get("text", "")
        return full_text.strip()
    return None

def _find_figure_caption(blocks, img_bbox):
    """이미지 블록 하단에서 Figure 캡션 탐색"""
    img_bottom = img_bbox[3]
    img_center_x = (img_bbox[0] + img_bbox[2]) / 2
    best_caption = None
    best_dist = 999999
    for block in blocks:
        if block.get("type", 0) != 0:
            continue
        bbox = block.get("bbox", [0, 0, 0, 0])
        block_top = bbox[1]
        dist = block_top - img_bottom
        if 0 < dist < 80:
            block_center_x = (bbox[0] + bbox[2]) / 2
            if abs(block_center_x - img_center_x) < 200:
                text = ""
                for line in block.get("lines", []):
                    for s in line.get("spans", []):
                        text += s.get("text", "")
                text = text.strip()
                if FIGURE_PATTERNS.match(text) and dist < best_dist:
                    best_caption = text
                    best_dist = dist
    return best_caption

def _find_table_caption(blocks, table_bbox):
    """표 상단/하단에서 Table 캡션 탐색"""
    t_top = table_bbox[1]
    t_bottom = table_bbox[3]
    t_center_x = (table_bbox[0] + table_bbox[2]) / 2
    best_caption = None
    best_dist = 999999
    for block in blocks:
        if block.get("type", 0) != 0:
            continue
        bbox = block.get("bbox", [0, 0, 0, 0])
        text = ""
        for line in block.get("lines", []):
            for s in line.get("spans", []):
                text += s.get("text", "")
        text = text.strip()
        if not TABLE_CAPTION_PATTERNS.match(text):
            continue
        block_center_x = (bbox[0] + bbox[2]) / 2
        if abs(block_center_x - t_center_x) > 250:
            continue
        # 표 위쪽 캡션
        dist_above = t_top - bbox[3]
        if 0 < dist_above < 60 and dist_above < best_dist:
            best_caption = text
            best_dist = dist_above
        # 표 아래쪽 캡션
        dist_below = bbox[1] - t_bottom
        if 0 < dist_below < 60 and dist_below < best_dist:
            best_caption = text
            best_dist = dist_below
    return best_caption

# ==============================================================================
# 스마트 PDF 텍스트 추출 (강화 버전)
# ==============================================================================
# ==============================================================================
# 페이지 PNG 사전 렌더링 (PyMuPDF) — 검색 결과 모달 뷰어용
# ==============================================================================
def _page_dir(collection_name, doc_id):
    return os.path.join(PAGES_DIR, collection_name, doc_id)


def _render_pdf_pages(pdf_path, collection_name, doc_id):
    """PDF 모든 페이지를 PNG로 사전 렌더링.
    - {PAGES_DIR}/{collection}/{doc_id}/page_NNNN.png  (PAGE_RENDER_DPI)
    - {PAGES_DIR}/{collection}/{doc_id}/thumb_NNNN.png (THUMB_RENDER_DPI)
    이미 디렉토리가 존재하면 스킵 (idempotent).
    Returns: {"page_count": int, "page_size": {page_num: [w, h]}, "skipped": bool}
    """
    out_dir = _page_dir(collection_name, doc_id)
    page_size = {}

    # idempotent: 디렉토리에 page_*.png가 이미 있으면 스킵
    if os.path.isdir(out_dir):
        existing = [f for f in os.listdir(out_dir) if f.startswith("page_") and f.endswith(".png")]
        if existing:
            try:
                doc = fitz.open(pdf_path)
                for i in range(len(doc)):
                    page = doc.load_page(i)
                    rect = page.rect
                    page_size[i + 1] = [rect.width, rect.height]
                doc.close()
            except Exception:
                pass
            return {"page_count": len(existing), "page_size": page_size, "skipped": True}

    os.makedirs(out_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    page_count = len(doc)
    page_zoom = PAGE_RENDER_DPI / 72.0
    thumb_zoom = THUMB_RENDER_DPI / 72.0
    page_mat = fitz.Matrix(page_zoom, page_zoom)
    thumb_mat = fitz.Matrix(thumb_zoom, thumb_zoom)

    for i in range(page_count):
        page = doc.load_page(i)
        rect = page.rect
        page_size[i + 1] = [rect.width, rect.height]
        page_no = i + 1
        try:
            pix = page.get_pixmap(matrix=page_mat, alpha=False)
            pix.save(os.path.join(out_dir, f"page_{page_no:04d}.png"))
        except Exception:
            pass
        try:
            tpix = page.get_pixmap(matrix=thumb_mat, alpha=False)
            tpix.save(os.path.join(out_dir, f"thumb_{page_no:04d}.png"))
        except Exception:
            pass
    doc.close()

    # 페이지 크기 메타도 같이 저장 (bbox 좌표 변환용)
    try:
        with open(os.path.join(out_dir, "_pages.json"), "w", encoding="utf-8") as f:
            json.dump({
                "page_count": page_count,
                "page_size": page_size,
                "render_dpi": PAGE_RENDER_DPI,
                "thumb_dpi": THUMB_RENDER_DPI,
                "pdf_dpi": 72,
            }, f, ensure_ascii=False)
    except Exception:
        pass

    return {"page_count": page_count, "page_size": page_size, "skipped": False}


# ==============================================================================
# Surya OCR (텍스트 레이어 부실 페이지 fallback) — 동적 로드
# ==============================================================================
_SURYA_PREDICTOR = None
_SURYA_CHECKED = False
_SURYA_AVAILABLE = False


def _resolve_extraction_mode(extraction_mode="", use_nougat=False, use_ocr=True):
    mode = (extraction_mode or "").strip().lower()
    if mode not in ("native", "surya", "nougat_hybrid"):
        if use_nougat:
            mode = "nougat_hybrid"
        elif use_ocr:
            mode = "surya"
        else:
            mode = "native"
    return mode


def _page_text_from_blocks(page_blocks):
    parts = []
    for block in page_blocks:
        content = (block.get("content") or "").strip()
        if content:
            parts.append(content)
    return "\n\n".join(parts).strip()


def _preferred_page_text(page_data, nougat_text=""):
    nougat_text = (nougat_text or "").strip()
    if nougat_text:
        extras = []
        for block in page_data.get("blocks", []):
            if block.get("type") not in ("header", "figure", "table", "table_caption", "formula", "equation_number"):
                continue
            content = (block.get("content") or "").strip()
            if content and content not in nougat_text:
                extras.append(content)
        parts = [nougat_text] + extras
        return "\n\n".join(part for part in parts if part).strip(), "nougat"
    return _page_text_from_blocks(page_data.get("blocks", [])), page_data.get("text_source", "native")


def _get_surya():
    """surya-ocr이 설치되어 있으면 단일 predictor 인스턴스 반환, 아니면 None."""
    global _SURYA_PREDICTOR, _SURYA_CHECKED, _SURYA_AVAILABLE
    if _SURYA_CHECKED:
        return _SURYA_PREDICTOR if _SURYA_AVAILABLE else None
    _SURYA_CHECKED = True
    try:
        # surya-ocr v0.6+ 새 API
        from surya.foundation import FoundationPredictor  # noqa: F401
        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor
        rec = RecognitionPredictor()
        det = DetectionPredictor()
        _SURYA_PREDICTOR = {"rec": rec, "det": det}
        _SURYA_AVAILABLE = True
    except Exception:
        try:
            # 구 API
            from surya.ocr import run_ocr  # noqa: F401
            from surya.model.detection.model import load_model as load_det
            from surya.model.detection.model import load_processor as load_det_proc
            from surya.model.recognition.model import load_model as load_rec
            from surya.model.recognition.processor import load_processor as load_rec_proc
            _SURYA_PREDICTOR = {
                "legacy": True,
                "det_model": load_det(),
                "det_proc": load_det_proc(),
                "rec_model": load_rec(),
                "rec_proc": load_rec_proc(),
            }
            _SURYA_AVAILABLE = True
        except Exception:
            _SURYA_PREDICTOR = None
            _SURYA_AVAILABLE = False
    return _SURYA_PREDICTOR if _SURYA_AVAILABLE else None


def _surya_ocr_page(page, langs=None):
    """Surya OCR로 PDF 페이지 텍스트 추출. 실패 시 빈 문자열 반환."""
    pred = _get_surya()
    if pred is None:
        return ""
    if langs is None:
        langs = ["en", "ko"]
    try:
        # 페이지 → PIL 이미지 (200 DPI)
        from PIL import Image as PILImage
        mat = fitz.Matrix(200 / 72.0, 200 / 72.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = PILImage.open(io.BytesIO(pix.tobytes("png")))

        if "legacy" in pred:
            from surya.ocr import run_ocr
            preds = run_ocr(
                [img], [langs],
                pred["det_model"], pred["det_proc"],
                pred["rec_model"], pred["rec_proc"]
            )
        else:
            preds = pred["rec"]([img], [langs], det_predictor=pred["det"])

        if not preds:
            return ""
        page_pred = preds[0]
        lines = getattr(page_pred, "text_lines", None) or []
        return "\n".join(getattr(line, "text", "") for line in lines if getattr(line, "text", ""))
    except Exception:
        return ""


def _extract_layout_from_pdf(pdf_path, use_vision=False, use_ocr=True):
    """Phase 1: PyMuPDF 레이아웃 추출 — 블록/bbox/헤더/표/수식/이미지 감지.
    텍스트 소스 결정은 하지 않고, 구조 데이터만 반환한다.
    """
    doc = fitz.open(pdf_path)
    pages_data = []
    all_text_parts = []
    equation_counter = [0]  # mutable counter

    # 1패스: 전체 폰트 크기 중위값 계산
    all_sizes = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for block in page_dict.get("blocks", []):
            if block.get("type", 0) == 0:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            all_sizes.append(span.get("size", 12))
    median_size = sorted(all_sizes)[len(all_sizes) // 2] if all_sizes else 12

    # 통계 카운터
    figure_count = 0
    formula_count = 0
    table_count = 0
    ocr_count = 0

    # Vision LLM 로드 (use_vision=True일 때)
    vision_llm = None
    if use_vision:
        try:
            _vlm = wiz.model("vision_llm")
            if _vlm.available():
                vision_llm = _vlm
        except Exception:
            pass

    # 2패스: 구조화 추출
    current_section = ""
    ocr_pages_used = 0  # Surya OCR로 fallback된 페이지 수
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        page_rect = page.rect
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        page_blocks = []
        blocks = page_dict.get("blocks", [])
        page_used_surya = False

        # Surya OCR fallback: 텍스트 레이어가 부실(50자 미만)하면 OCR 결과를 단일 텍스트 블록으로 추가
        if use_ocr:
            plain_text = page.get_text("text") or ""
            if len(plain_text.strip()) < 50:
                ocr_text = _surya_ocr_page(page)
                if ocr_text and ocr_text.strip():
                    rect = page.rect
                    blocks.append({
                        "type": 0,
                        "bbox": [rect.x0, rect.y0, rect.x1, rect.y1],
                        "lines": [{
                            "spans": [{
                                "text": line, "size": 12, "flags": 0,
                                "bbox": [rect.x0, rect.y0 + i * 14, rect.x1, rect.y0 + (i + 1) * 14]
                            }]
                        } for i, line in enumerate(ocr_text.split("\n")) if line.strip()]
                    })
                    ocr_pages_used += 1
                    page_used_surya = True

        # 표 추출 (마크다운 변환)
        tables_on_page = []
        try:
            tables = page.find_tables()
            for table in tables:
                md_text, num_rows, num_cols = _table_to_markdown(table)
                if md_text.strip():
                    caption = _find_table_caption(blocks, list(table.bbox))
                    caption_str = caption if caption else "Table"
                    marker = f"[TABLE: {caption_str} | rows={num_rows}, cols={num_cols} | {md_text}]"
                    tables_on_page.append({
                        "bbox": list(table.bbox),
                        "text": marker,
                        "md_text": md_text,
                        "caption": caption_str,
                        "rows": num_rows,
                        "cols": num_cols
                    })
        except Exception:
            pass

        for block in blocks:
            bbox = block.get("bbox", [0, 0, 0, 0])

            # 이미지 블록 → Vision LLM 분석 또는 OCR + 캡션
            if block.get("type", 0) == 1:
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                caption = _find_figure_caption(blocks, bbox)

                marker = None

                # Vision LLM 분석 (use_vision=True이고 충분한 크기의 이미지)
                if vision_llm is not None and width >= 80 and height >= 80:
                    try:
                        clip = fitz.Rect(bbox)
                        mat = fitz.Matrix(2, 2)
                        pix = page.get_pixmap(matrix=mat, clip=clip)
                        img_bytes = pix.tobytes("png")
                        from PIL import Image as PILImage
                        pil_img = PILImage.open(io.BytesIO(img_bytes))

                        result = vision_llm.analyze(pil_img)
                        marker = result.get("marker", "")
                        if result.get("type") == "equation":
                            formula_count += 1
                        ocr_count += 1
                    except Exception:
                        marker = None

                # Vision LLM 실패 또는 미사용 시 기존 OCR 폴백
                if marker is None:
                    ocr_text = ""
                    if width >= 50 and height >= 50:
                        ocr_text = _extract_image_ocr(page, block)
                        if ocr_text:
                            ocr_count += 1

                    if caption and ocr_text:
                        marker = f"[FIGURE: {caption} | OCR: {ocr_text}]"
                    elif caption:
                        marker = f"[FIGURE: {caption}]"
                    elif ocr_text:
                        marker = f"[FIGURE: (이미지) | OCR: {ocr_text}]"
                    else:
                        if width < 30 or height < 30:
                            continue  # 너무 작은 이미지 스킵
                        marker = "[FIGURE: (이미지)]"

                figure_count += 1
                page_blocks.append({
                    "type": "figure", "content": marker,
                    "bbox": list(bbox), "page_num": page_num + 1
                })
                all_text_parts.append(marker)
                continue

            # 텍스트 블록 아닌 경우 스킵
            if block.get("type", 0) != 0:
                continue

            # 표 영역 안에 있는 블록 스킵
            in_table = False
            for tbl in tables_on_page:
                tb = tbl["bbox"]
                if (bbox[0] >= tb[0] - 5 and bbox[1] >= tb[1] - 5 and
                    bbox[2] <= tb[2] + 5 and bbox[3] <= tb[3] + 5):
                    in_table = True
                    break
            if in_table:
                continue

            # 섹션 헤더 감지
            header = _detect_section_header(block, median_size)
            if header:
                current_section = header
                marker = f"\n\n## {header}\n\n"
                page_blocks.append({
                    "type": "header", "content": header,
                    "bbox": list(bbox), "page_num": page_num + 1
                })
                all_text_parts.append(marker)
                continue

            # 일반 텍스트 + 수식 감지
            block_text = ""
            has_math = False
            math_spans_text = []
            math_spans_count = 0
            total_spans_count = 0
            context_before = ""
            context_after = ""
            lines = block.get("lines", [])

            for line_idx, line in enumerate(lines):
                line_text = ""
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    total_spans_count += 1
                    if _is_math_span(span):
                        has_math = True
                        math_spans_text.append(span_text)
                        math_spans_count += 1
                    line_text += span_text
                block_text += line_text

            block_text = block_text.strip()
            if not block_text:
                continue

            # 수식 번호만 있는 블록 감지 (예: "(1)", "(2.3)")
            if EQUATION_NUMBER_PATTERN.match(block_text):
                # 수식 번호는 이전 수식 블록에 연결 — 별도 블록으로 기록
                page_blocks.append({
                    "type": "equation_number", "content": block_text.strip(),
                    "bbox": list(bbox), "page_num": page_num + 1
                })
                continue

            # 캡션 패턴 감지
            if FIGURE_PATTERNS.match(block_text):
                marker = f"[FIGURE: {block_text}]"
                figure_count += 1
                page_blocks.append({
                    "type": "figure", "content": marker,
                    "bbox": list(bbox), "page_num": page_num + 1
                })
                all_text_parts.append(marker)
            elif TABLE_CAPTION_PATTERNS.match(block_text):
                # 표 캡션은 이미 표와 연결됨 — 별도로도 기록
                marker = f"[TABLE: {block_text}]"
                page_blocks.append({
                    "type": "table_caption", "content": marker,
                    "bbox": list(bbox), "page_num": page_num + 1
                })
                all_text_parts.append(marker)
            elif has_math:
                # 수식 강화: 구조적 LaTeX 재구성 + 인라인/디스플레이 구분
                equation_counter[0] += 1
                eq_idx = equation_counter[0]
                eq_type = _classify_equation_type(block, lines)

                # 구조적 LaTeX 재구성 시도 (span 위치 정보 활용)
                structured_latex = _build_structured_latex(lines)
                # 기본 유니코드 변환도 병행
                raw_math = "".join(math_spans_text)
                simple_latex = _unicode_to_latex(raw_math) if raw_math else _unicode_to_latex(block_text)
                # 구조적 결과가 더 풍부하면 우선 사용
                latex_math = structured_latex if len(structured_latex) >= len(simple_latex) else simple_latex

                # 수식 번호가 다음 블록에 있을 수 있으므로 eq_ref 추출
                eq_ref = ""
                eq_num_match = re.search(r'\((\d+\.?\d*|[A-Z]\.?\d*)\)\s*$', block_text)
                if eq_num_match:
                    eq_ref = eq_num_match.group(1)

                if eq_type == "display":
                    ref_part = f" | ref=({eq_ref})" if eq_ref else ""
                    marker = f"[EQUATION: eq_{eq_idx} | type=display{ref_part} | $${latex_math}$$ | context: {block_text}]"
                else:
                    marker = f"[EQUATION: eq_{eq_idx} | type=inline | ${latex_math}$ | context: {block_text}]"

                formula_count += 1
                page_blocks.append({
                    "type": "formula", "content": marker,
                    "bbox": list(bbox), "page_num": page_num + 1,
                    "eq_index": eq_idx, "eq_type": eq_type,
                    "latex": latex_math
                })
                all_text_parts.append(marker)
            else:
                page_blocks.append({
                    "type": "text", "content": block_text,
                    "bbox": list(bbox), "page_num": page_num + 1
                })
                all_text_parts.append(block_text)

        # 표 블록 추가
        for tbl in tables_on_page:
            table_count += 1
            page_blocks.append({
                "type": "table", "content": tbl["text"],
                "bbox": tbl["bbox"], "page_num": page_num + 1,
                "md_text": tbl["md_text"], "rows": tbl["rows"], "cols": tbl["cols"]
            })
            all_text_parts.append(tbl["text"])

        pages_data.append({
            "page_num": page_num + 1,
            "blocks": page_blocks,
            "section": current_section,
            "text_source": "surya" if page_used_surya else "native",
            "page_bbox": [page_rect.x0, page_rect.y0, page_rect.x1, page_rect.y1],
        })

    doc.close()

    return {
        "pages": pages_data,
        "all_text_parts": all_text_parts,
        "stats": {
            "figures": figure_count,
            "formulas": formula_count,
            "tables": table_count,
            "ocr_extractions": ocr_count,
            "ocr_pages_used": ocr_pages_used,
            "surya_available": _SURYA_AVAILABLE,
            "total_equations": equation_counter[0],
        }
    }


def _run_nougat_extraction(pdf_path):
    """Phase 2: Nougat OCR로 페이지별 텍스트 추출. 실패 시 빈 dict 반환."""
    nougat_map = {}
    nougat_available = False
    try:
        nougat_model = wiz.model("nougat_ocr")
        nougat_available = nougat_model.available()
        if nougat_available:
            nougat_result = nougat_model.extract_document(pdf_path, dpi=PAGE_RENDER_DPI, batch_size=2)
            for page_info in nougat_result.get("pages", []):
                page_no = int(page_info.get("page_num", 0) or 0)
                if page_no > 0:
                    nougat_map[page_no] = (page_info.get("text") or "").strip()
    except Exception:
        traceback.print_exc()
        nougat_available = False
    return nougat_map, nougat_available


def _merge_page_texts(pages_data, all_text_parts, nougat_map=None):
    """Phase 3: 소스 우선순위 병합 — Nougat → native/surya text.
    각 페이지에 preferred_text와 preferred_text_source를 기록하고
    full_text를 반환한다.
    """
    if nougat_map is None:
        nougat_map = {}

    nougat_pages_used = 0
    native_pages_used = 0
    failed_pages = []
    page_texts = []

    for page in pages_data:
        preferred_text, source = _preferred_page_text(
            page, nougat_map.get(page.get("page_num", 0), "")
        )
        if not preferred_text:
            failed_pages.append(page.get("page_num", 0))
            continue
        page["preferred_text"] = preferred_text
        page["preferred_text_source"] = source
        page_texts.append(preferred_text)
        if source == "nougat":
            nougat_pages_used += 1
        else:
            native_pages_used += 1

    full_text = "\n\n".join(page_texts if page_texts else all_text_parts)
    return {
        "full_text": full_text,
        "nougat_pages_used": nougat_pages_used,
        "native_pages_used": native_pages_used,
        "failed_pages": failed_pages,
    }


def _is_equation_quality_ok(latex):
    """수식 LaTeX 문자열의 품질을 판정한다. True면 양호, False면 rescue 대상."""
    latex = (latex or "").strip()
    if not latex:
        return False
    # 1. 달러/중괄호 짝 불일치
    if latex.count("{") != latex.count("}"):
        return False
    dollar_count = latex.count("$") - latex.count("\\$")
    if dollar_count % 2 != 0:
        return False
    # 2. 수학 기호가 전혀 없는 경우 (자연어만)
    if not re.search(r"[\\$\^_{}=+\-*/\d]", latex):
        return False
    # 3. 특수문자 노이즈 비율 과다 (제어문자·대체문자)
    noise = sum(1 for ch in latex if ord(ch) < 32 or ch == '\ufffd')
    if len(latex) > 5 and noise / len(latex) > 0.3:
        return False
    # 4. 너무 짧은 수식 (단일 문자)
    stripped = re.sub(r"[\s${}\\]", "", latex)
    if len(stripped) < 2:
        return False
    return True


def _run_gemma_equation_rescue(pdf_path, pages_data):
    """Phase 2.5: 품질 미달 수식 블록만 Gemma 4 Vision으로 재추출.
    pages_data의 formula 블록을 in-place로 갱신한다.
    """
    stats = {"gemma_rescues": 0, "rescue_skipped": 0, "rescue_failed": 0}
    # Gemma Vision LLM 로드
    vision_llm = None
    try:
        _vlm = wiz.model("vision_llm")
        if _vlm.available():
            vision_llm = _vlm
    except Exception:
        pass
    if vision_llm is None:
        return stats

    doc = None
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return stats

    try:
        for page_data in pages_data:
            page_num_1 = page_data.get("page_num", 0)
            if page_num_1 < 1 or page_num_1 > len(doc):
                continue
            page = doc.load_page(page_num_1 - 1)

            for block in page_data.get("blocks", []):
                if block.get("type") != "formula":
                    continue
                latex = block.get("latex", "")
                if _is_equation_quality_ok(latex):
                    stats["rescue_skipped"] += 1
                    continue

                # bbox crop → Gemma 재추출
                bbox = block.get("bbox")
                if not bbox or len(bbox) < 4:
                    stats["rescue_skipped"] += 1
                    continue

                try:
                    from PIL import Image as PILImage
                    clip = fitz.Rect(bbox)
                    # 약간의 패딩 추가
                    clip.x0 = max(0, clip.x0 - 5)
                    clip.y0 = max(0, clip.y0 - 5)
                    clip.x1 = min(page.rect.x1, clip.x1 + 5)
                    clip.y1 = min(page.rect.y1, clip.y1 + 5)
                    mat = fitz.Matrix(3, 3)  # 고해상도 crop
                    pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
                    pil_img = PILImage.open(io.BytesIO(pix.tobytes("png")))

                    result = vision_llm.equation(pil_img)
                    new_latex = (result.get("latex") or "").strip()
                    if new_latex and _is_equation_quality_ok(new_latex):
                        eq_idx = block.get("eq_index", 0)
                        eq_type = block.get("eq_type", "display")
                        desc = (result.get("description") or "").strip()
                        if eq_type == "display":
                            body = f"$${new_latex}$$"
                        else:
                            body = f"${new_latex}$"
                        ctx_part = f" | context: {desc}" if desc else ""
                        new_marker = f"[EQUATION: eq_{eq_idx} | type={eq_type} | {body}{ctx_part} | source=gemma_rescue]"
                        block["content"] = new_marker
                        block["latex"] = new_latex
                        block["rescue_source"] = "gemma"
                        stats["gemma_rescues"] += 1
                    else:
                        stats["rescue_failed"] += 1
                except Exception:
                    stats["rescue_failed"] += 1
    finally:
        doc.close()

    return stats


def _extract_text_from_pdf(pdf_path, use_vision=False, use_ocr=True, use_nougat=False,
                           gemma_rescue=False, extraction_mode="surya"):
    """오케스트레이터: 레이아웃 추출 → (선택) Nougat 추출 → 수식 rescue → 소스 병합."""
    # Phase 1: PyMuPDF 레이아웃
    layout = _extract_layout_from_pdf(pdf_path, use_vision=use_vision, use_ocr=use_ocr)
    pages_data = layout["pages"]
    all_text_parts = layout["all_text_parts"]
    layout_stats = layout["stats"]

    # Phase 2: Nougat (선택)
    nougat_map = {}
    nougat_available = False
    if use_nougat:
        nougat_map, nougat_available = _run_nougat_extraction(pdf_path)

    # Phase 2.5: 수식 품질 게이트 + Gemma rescue (선택)
    rescue_stats = {"gemma_rescues": 0, "rescue_skipped": 0, "rescue_failed": 0}
    if gemma_rescue:
        rescue_stats = _run_gemma_equation_rescue(pdf_path, pages_data)

    # Phase 3: 소스 병합
    merge = _merge_page_texts(pages_data, all_text_parts, nougat_map)

    return {
        "full_text": merge["full_text"],
        "pages": pages_data,
        "stats": {
            **layout_stats,
            "nougat_available": nougat_available,
            "nougat_pages_used": merge["nougat_pages_used"],
            "native_pages_used": merge["native_pages_used"],
            "failed_pages": merge["failed_pages"],
            "extraction_mode": _resolve_extraction_mode(extraction_mode, use_nougat=use_nougat, use_ocr=use_ocr),
            "gemma_rescue_requested": gemma_rescue,
            "gemma_rescues": rescue_stats.get("gemma_rescues", 0),
            "rescue_skipped": rescue_stats.get("rescue_skipped", 0),
            "rescue_failed": rescue_stats.get("rescue_failed", 0),
        }
    }

# ==============================================================================
# 문장 분리 유틸
# ==============================================================================
def _split_sentences(text):
    """한국어+영어 문장 경계로 분리"""
    sentences = []
    parts = re.split(r'(?<=[.!?。])\s+(?=[A-Z가-힣\[\(])', text)
    for part in parts:
        part = part.strip()
        if part:
            sentences.append(part)
    return sentences if sentences else [text]


def _extract_temporal_signals(text):
    text = (text or "").strip()
    signals = {
        "publication_year": "",
        "online_year": "",
        "accepted_year": "",
        "received_year": "",
    }
    if not text:
        return signals

    for key, patterns in TEMPORAL_SIGNAL_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            year = match.group(1)
            try:
                year_int = int(year)
                if 1900 <= year_int <= 2100:
                    signals[key] = str(year_int)
                    break
            except Exception:
                pass

    return signals


def _build_temporal_metadata_prefix(full_text, pages_data=None):
    candidate_parts = []

    if pages_data:
        first_page = pages_data[0] if len(pages_data) > 0 else None
        if first_page:
            first_page_texts = []
            for block in first_page.get("blocks", []):
                content = (block.get("content", "") or "").strip()
                if content:
                    first_page_texts.append(content)
            if first_page_texts:
                candidate_parts.append("\n".join(first_page_texts[:40]))

    head_text = (full_text or "")[:5000].strip()
    if head_text:
        candidate_parts.append(head_text)

    if not candidate_parts:
        return ""

    merged = "\n\n".join(candidate_parts)
    signals = _extract_temporal_signals(merged)
    parts = []

    publication_year = signals.get("publication_year", "")
    online_year = signals.get("online_year", "")
    accepted_year = signals.get("accepted_year", "")
    received_year = signals.get("received_year", "")

    if publication_year:
        parts.append(f"Published {publication_year}")
    if online_year:
        parts.append(f"Available online {online_year}")
    if accepted_year:
        parts.append(f"Accepted {accepted_year}")
    if received_year:
        parts.append(f"Received {received_year}")

    if not parts:
        return ""

    return "Publication timeline: " + ". ".join(parts) + "."


def _enrich_chunks_with_temporal_metadata(chunks, full_text, pages_data=None, max_chunks=5):
    prefix = _build_temporal_metadata_prefix(full_text, pages_data=pages_data)
    if not prefix:
        return chunks

    enriched = 0
    for chunk in chunks:
        if enriched >= max_chunks:
            break

        chunk_type = (chunk.get("chunk_type", "") or "text").strip()
        if chunk_type not in ("text", "mixed"):
            continue

        text = (chunk.get("text", "") or "").strip()
        if not text:
            continue

        lower = text.lower()
        if any(token in lower for token in [
            "publication timeline:",
            "available online",
            "accepted ",
            "received ",
            "published ",
        ]):
            continue

        chunk["text"] = f"{prefix}\n\n{text}".strip()
        enriched += 1

    return chunks

# ==============================================================================
# 청크 타입 감지
# ==============================================================================
def _detect_chunk_type(text):
    """청크 내용에 따라 타입 결정"""
    has_figure = "[FIGURE:" in text
    has_formula = "[EQUATION:" in text or "[FORMULA:" in text
    has_table = "[TABLE:" in text
    count = sum([has_figure, has_formula, has_table])
    if count > 1:
        return "mixed"
    if has_figure:
        return "figure"
    if has_formula:
        return "formula"
    if has_table:
        return "table"
    return "text"

def _detect_content_elements(text):
    """청크 내 포함된 요소 목록 반환"""
    elements = []
    fig_count = len(re.findall(r'\[FIGURE:', text))
    eq_count = len(re.findall(r'\[EQUATION:', text)) + len(re.findall(r'\[FORMULA:', text))
    tbl_count = len(re.findall(r'\[TABLE:', text))
    text_len = len(re.sub(r'\[(FIGURE|EQUATION|TABLE):[^\]]*\]', '', text).strip())

    if text_len > 20:
        elements.append("text")
    if fig_count > 0:
        elements.append(f"figure:{fig_count}")
    if eq_count > 0:
        elements.append(f"equation:{eq_count}")
    if tbl_count > 0:
        elements.append(f"table:{tbl_count}")
    return elements

def _extract_structured_content(text):
    """청크에서 구조화된 콘텐츠 추출 (LaTeX 수식, 마크다운 표)"""
    structured = []
    # 수식 추출 (EQUATION + FORMULA 하위 호환)
    for m in re.finditer(r'\[(?:EQUATION|FORMULA):\s*([^\]]+)\]', text):
        structured.append({"type": "equation", "content": m.group(1)})
    # 표 추출
    for m in re.finditer(r'\[TABLE:\s*([^\]]+)\]', text):
        content = m.group(1)
        if '|' in content:
            structured.append({"type": "table", "content": content[:500]})
    if not structured:
        return ""
    return json.dumps(structured, ensure_ascii=False)[:8000]

# ==============================================================================
# 수식 청크 임베딩 텍스트 보강
# ==============================================================================
def _enhance_equation_text_for_embedding(text):
    """수식 마커가 포함된 청크에서 검색 친화적 텍스트를 생성한다.
    LaTeX 수식은 벡터 임베딩에 잘 반영되지 않으므로,
    수식의 context 텍스트 + 섹션 제목 + 변수 명칭을 보강하여 검색 정확도를 높인다."""
    enhanced_parts = [text]

    # [EQUATION: ... | context: 원본텍스트] 에서 context 추출
    for m in re.finditer(r'\[EQUATION:\s*eq_\d+\s*\|[^|]*\|[^|]*\|\s*context:\s*([^\]]+)\]', text):
        context = m.group(1).strip()
        if context and context not in text[:text.find('[EQUATION:')]:
            enhanced_parts.append(context)

    # LaTeX 명령어에서 의미 있는 용어 추출 (그리스 문자를 자연어로)
    latex_terms = []
    latex_to_term = {
        r'\alpha': 'alpha', r'\beta': 'beta', r'\gamma': 'gamma',
        r'\delta': 'delta', r'\epsilon': 'epsilon', r'\theta': 'theta',
        r'\lambda': 'lambda', r'\mu': 'mu', r'\sigma': 'sigma',
        r'\omega': 'omega', r'\phi': 'phi', r'\psi': 'psi',
        r'\nabla': 'gradient', r'\partial': 'partial derivative',
        r'\int': 'integral', r'\sum': 'summation',
        r'\frac': 'fraction', r'\sqrt': 'square root',
    }
    for cmd, term in latex_to_term.items():
        if cmd in text:
            latex_terms.append(term)
    if latex_terms:
        enhanced_parts.append("Mathematical terms: " + ", ".join(set(latex_terms)))

    return "\n".join(enhanced_parts)

# ==============================================================================
# 청킹 전략 구현
# ==============================================================================

def _chunk_text(text, strategy="semantic_section", chunk_size=DEFAULT_CHUNK_SIZE,
                chunk_overlap=DEFAULT_CHUNK_OVERLAP, respect_sentences=True,
                similarity_threshold=0.5, model_name=None, pages_data=None):
    """청킹 디스패처 — 전략에 따라 적절한 함수 호출"""
    if not text or not text.strip():
        return []

    if strategy == "fixed":
        chunks = _chunk_text_fixed(text, chunk_size, chunk_overlap)
    elif strategy == "sentence":
        chunks = _chunk_text_sentence(text, chunk_size)
    elif strategy == "paragraph":
        chunks = _chunk_text_paragraph(text, chunk_size)
    elif strategy == "recursive":
        chunks = _chunk_text_recursive(text, chunk_size, chunk_overlap)
    elif strategy == "semantic_embedding":
        chunks = _chunk_text_semantic_embedding(text, chunk_size, similarity_threshold, model_name)
    else:  # semantic_section (기본값)
        chunks = _chunk_text_semantic_section(text, chunk_size, chunk_overlap, respect_sentences)

    # 페이지 번호 매핑
    if pages_data:
        _assign_page_numbers(chunks, pages_data)

    # 논문 접수/채택/온라인 공개 연도 메타를 초기 청크에 보강
    chunks = _enrich_chunks_with_temporal_metadata(chunks, text, pages_data=pages_data)

    # 빈 청크 제거
    chunks = [c for c in chunks if c.get("text", "").strip()]
    return chunks


# --- 전략 1: 고정 크기 (Fixed-size) ---
def _chunk_text_fixed(text, chunk_size, chunk_overlap):
    """단순 고정 크기 분할 + 오버랩"""
    chunks = []
    step = max(chunk_size - chunk_overlap, 1)
    for i in range(0, len(text), step):
        piece = text[i:i + chunk_size].strip()
        if piece:
            chunks.append({
                "text": piece,
                "chunk_type": _detect_chunk_type(piece),
                "section_title": ""
            })
    return chunks


# --- 전략 2: 문장 기반 (Sentence) ---
def _chunk_text_sentence(text, chunk_size):
    """문장 단위 분리 후 그룹핑"""
    sentences = _split_sentences(text)
    chunks = []
    current = ""
    current_section = ""

    for sent in sentences:
        # 섹션 헤더 감지
        header_match = re.match(r'^## (.+?)$', sent, re.MULTILINE)
        if header_match:
            if current.strip():
                chunks.append({
                    "text": current.strip(),
                    "chunk_type": _detect_chunk_type(current),
                    "section_title": current_section
                })
                current = ""
            current_section = header_match.group(1).strip()
            continue

        if len(current) + len(sent) + 1 > chunk_size:
            if current.strip():
                chunks.append({
                    "text": current.strip(),
                    "chunk_type": _detect_chunk_type(current),
                    "section_title": current_section
                })
            current = sent
        else:
            current = (current + " " + sent).strip() if current else sent

    if current.strip():
        chunks.append({
            "text": current.strip(),
            "chunk_type": _detect_chunk_type(current),
            "section_title": current_section
        })
    return chunks


# --- 전략 3: 문단 기반 (Paragraph) ---
def _chunk_text_paragraph(text, chunk_size):
    """문단 단위 분할 + 짧은 문단 병합"""
    paragraphs = re.split(r'\n\n+', text)
    chunks = []
    current = ""
    current_section = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 섹션 헤더
        header_match = re.match(r'^## (.+)', para)
        if header_match:
            if current.strip():
                chunks.append({
                    "text": current.strip(),
                    "chunk_type": _detect_chunk_type(current),
                    "section_title": current_section
                })
                current = ""
            current_section = header_match.group(1).strip()
            continue

        # 특수 마커(FIGURE/EQUATION/TABLE) → 독립 청크
        if SPECIAL_MARKER.search(para):
            if current.strip():
                chunks.append({
                    "text": current.strip(),
                    "chunk_type": _detect_chunk_type(current),
                    "section_title": current_section
                })
                current = ""
            chunks.append({
                "text": para,
                "chunk_type": _detect_chunk_type(para),
                "section_title": current_section
            })
            continue

        if len(current) + len(para) + 2 > chunk_size:
            if current.strip():
                chunks.append({
                    "text": current.strip(),
                    "chunk_type": _detect_chunk_type(current),
                    "section_title": current_section
                })
            # 문단 자체가 너무 크면 분할
            if len(para) > chunk_size:
                sents = _split_sentences(para)
                sub = ""
                for s in sents:
                    if len(sub) + len(s) + 1 > chunk_size:
                        if sub.strip():
                            chunks.append({
                                "text": sub.strip(),
                                "chunk_type": "text",
                                "section_title": current_section
                            })
                        sub = s
                    else:
                        sub = (sub + " " + s).strip() if sub else s
                current = sub
            else:
                current = para
        else:
            current = (current + "\n\n" + para).strip() if current else para

    if current.strip():
        chunks.append({
            "text": current.strip(),
            "chunk_type": _detect_chunk_type(current),
            "section_title": current_section
        })
    return chunks


# --- 전략 4: 재귀 분할 (Recursive) ---
def _chunk_text_recursive(text, chunk_size, chunk_overlap, separators=None):
    """구분자 계층 순차 적용 (LangChain 스타일)"""
    if separators is None:
        separators = ["\n\n", "\n", ". ", " ", ""]

    chunks = []
    _recursive_split(text, separators, 0, chunk_size, chunk_overlap, chunks, "")
    return chunks

def _recursive_split(text, separators, sep_idx, chunk_size, chunk_overlap, chunks, section_title):
    if len(text) <= chunk_size:
        if text.strip():
            # 섹션 헤더 추출
            hm = re.match(r'^## (.+?)(?:\n|$)', text)
            sec = hm.group(1).strip() if hm else section_title
            chunks.append({
                "text": text.strip(),
                "chunk_type": _detect_chunk_type(text),
                "section_title": sec
            })
        return

    if sep_idx >= len(separators):
        # 모든 구분자 소진 — 강제 분할
        step = max(chunk_size - chunk_overlap, 1)
        for i in range(0, len(text), step):
            piece = text[i:i + chunk_size].strip()
            if piece:
                chunks.append({
                    "text": piece,
                    "chunk_type": _detect_chunk_type(piece),
                    "section_title": section_title
                })
        return

    sep = separators[sep_idx]
    if sep == "":
        # 빈 구분자 = 문자 단위 분할
        step = max(chunk_size - chunk_overlap, 1)
        for i in range(0, len(text), step):
            piece = text[i:i + chunk_size].strip()
            if piece:
                chunks.append({
                    "text": piece,
                    "chunk_type": _detect_chunk_type(piece),
                    "section_title": section_title
                })
        return

    parts = text.split(sep)
    current = ""
    for part in parts:
        candidate = (current + sep + part) if current else part
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current.strip():
                if len(current) <= chunk_size:
                    hm = re.match(r'^## (.+?)(?:\n|$)', current)
                    sec = hm.group(1).strip() if hm else section_title
                    chunks.append({
                        "text": current.strip(),
                        "chunk_type": _detect_chunk_type(current),
                        "section_title": sec
                    })
                else:
                    _recursive_split(current, separators, sep_idx + 1, chunk_size, chunk_overlap, chunks, section_title)
            current = part

    if current.strip():
        if len(current) <= chunk_size:
            hm = re.match(r'^## (.+?)(?:\n|$)', current)
            sec = hm.group(1).strip() if hm else section_title
            chunks.append({
                "text": current.strip(),
                "chunk_type": _detect_chunk_type(current),
                "section_title": sec
            })
        else:
            _recursive_split(current, separators, sep_idx + 1, chunk_size, chunk_overlap, chunks, section_title)


# --- 전략 5: 시맨틱 섹션 기반 (기존 방식, 기본값) ---
def _chunk_text_semantic_section(text, chunk_size, chunk_overlap, respect_sentences):
    """섹션·문단·문장 경계 기반 의미 단위 분할 (기존 로직)"""
    # 1단계: 섹션 헤더(## )로 분할
    section_splits = re.split(r'\n\n(?=## )', text)
    sections = []
    current_section_title = ""

    for split in section_splits:
        split = split.strip()
        if not split:
            continue
        header_match = re.match(r'^## (.+?)(?:\n|$)', split)
        if header_match:
            current_section_title = header_match.group(1).strip()
            body = split[header_match.end():].strip()
        else:
            body = split
        if body:
            sections.append({"text": body, "section_title": current_section_title})

    if not sections:
        sections = [{"text": text.strip(), "section_title": ""}]

    # 2단계: 각 섹션을 청크 크기에 맞게 분할
    chunks = []
    for section in sections:
        sec_text = section["text"]
        sec_title = section["section_title"]

        if len(sec_text) <= chunk_size:
            chunks.append({
                "text": sec_text,
                "chunk_type": _detect_chunk_type(sec_text),
                "section_title": sec_title
            })
            continue

        paragraphs = re.split(r'\n\n+', sec_text)
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 특수 마커 → 독립 청크
            if SPECIAL_MARKER.search(para):
                if current_chunk:
                    chunks.append({
                        "text": current_chunk.strip(),
                        "chunk_type": _detect_chunk_type(current_chunk),
                        "section_title": sec_title
                    })
                    current_chunk = ""
                if len(para) <= 2000:
                    chunks.append({
                        "text": para,
                        "chunk_type": _detect_chunk_type(para),
                        "section_title": sec_title
                    })
                else:
                    _split_large_special(para, chunks, sec_title, chunk_size)
                continue

            if len(current_chunk) + len(para) + 2 > chunk_size:
                if current_chunk:
                    chunks.append({
                        "text": current_chunk.strip(),
                        "chunk_type": _detect_chunk_type(current_chunk),
                        "section_title": sec_title
                    })

                if len(para) > chunk_size and respect_sentences:
                    sentences = _split_sentences(para)
                    current_chunk = ""
                    for sent in sentences:
                        if len(current_chunk) + len(sent) + 1 > chunk_size:
                            if current_chunk:
                                chunks.append({
                                    "text": current_chunk.strip(),
                                    "chunk_type": "text",
                                    "section_title": sec_title
                                })
                            current_chunk = sent
                        else:
                            current_chunk = (current_chunk + " " + sent).strip() if current_chunk else sent
                elif len(para) > chunk_size:
                    for i in range(0, len(para), chunk_size - chunk_overlap):
                        piece = para[i:i + chunk_size]
                        if piece.strip():
                            chunks.append({
                                "text": piece.strip(),
                                "chunk_type": "text",
                                "section_title": sec_title
                            })
                    current_chunk = ""
                else:
                    current_chunk = para
            else:
                current_chunk = (current_chunk + "\n\n" + para).strip() if current_chunk else para

        if current_chunk.strip():
            chunks.append({
                "text": current_chunk.strip(),
                "chunk_type": _detect_chunk_type(current_chunk),
                "section_title": sec_title
            })

    # 오버랩 적용
    if chunk_overlap > 0 and len(chunks) > 1:
        for i in range(1, len(chunks)):
            prev_text = chunks[i - 1]["text"]
            if chunks[i]["chunk_type"] not in ("figure", "formula", "table"):
                overlap_text = prev_text[-chunk_overlap:] if len(prev_text) > chunk_overlap else ""
                if overlap_text and not SPECIAL_MARKER.search(overlap_text):
                    chunks[i]["text"] = overlap_text + " " + chunks[i]["text"]

    return chunks


# --- 전략 6: 시맨틱 임베딩 유사도 기반 ---
def _chunk_text_semantic_embedding(text, chunk_size, similarity_threshold, model_name):
    """인접 문장 간 임베딩 코사인 유사도로 분할점 결정"""
    sentences = _split_sentences(text)
    if len(sentences) <= 1:
        return [{"text": text.strip(), "chunk_type": _detect_chunk_type(text), "section_title": ""}]

    # 섹션 헤더 추출
    current_section = ""
    clean_sentences = []
    sentence_sections = []
    for s in sentences:
        hm = re.match(r'^## (.+)', s)
        if hm:
            current_section = hm.group(1).strip()
            continue
        clean_sentences.append(s)
        sentence_sections.append(current_section)

    if not clean_sentences:
        return [{"text": text.strip(), "chunk_type": _detect_chunk_type(text), "section_title": ""}]

    # 문장별 임베딩 계산
    model = _get_model(model_name)
    embeddings = model.encode(clean_sentences, normalize_embeddings=True, show_progress_bar=False)

    # 인접 문장 간 코사인 유사도 계산 → 분할점 결정
    split_points = []
    for i in range(1, len(embeddings)):
        sim = float(np.dot(embeddings[i-1], embeddings[i]))
        if sim < similarity_threshold:
            split_points.append(i)

    # 분할점 기반 그룹핑
    chunks = []
    start = 0
    for sp in split_points + [len(clean_sentences)]:
        group = clean_sentences[start:sp]
        sec = sentence_sections[start] if start < len(sentence_sections) else ""
        group_text = " ".join(group)

        # chunk_size 초과 시 추가 분할
        if len(group_text) > chunk_size:
            sub = ""
            for s in group:
                if len(sub) + len(s) + 1 > chunk_size:
                    if sub.strip():
                        chunks.append({
                            "text": sub.strip(),
                            "chunk_type": _detect_chunk_type(sub),
                            "section_title": sec
                        })
                    sub = s
                else:
                    sub = (sub + " " + s).strip() if sub else s
            if sub.strip():
                chunks.append({
                    "text": sub.strip(),
                    "chunk_type": _detect_chunk_type(sub),
                    "section_title": sec
                })
        else:
            if group_text.strip():
                chunks.append({
                    "text": group_text.strip(),
                    "chunk_type": _detect_chunk_type(group_text),
                    "section_title": sec
                })
        start = sp

    return chunks


def _split_large_special(text, chunks, sec_title, chunk_size):
    """2000자 초과 특수 마커 텍스트 분할"""
    parts = re.split(r'(\[(?:FIGURE|EQUATION|TABLE):[^\]]*\])', text)
    current = ""
    for part in parts:
        if SPECIAL_MARKER.match(part):
            if current.strip():
                chunks.append({
                    "text": current.strip(),
                    "chunk_type": _detect_chunk_type(current),
                    "section_title": sec_title
                })
                current = ""
            chunks.append({
                "text": part.strip(),
                "chunk_type": _detect_chunk_type(part),
                "section_title": sec_title
            })
        else:
            if len(current) + len(part) > chunk_size:
                if current.strip():
                    chunks.append({
                        "text": current.strip(),
                        "chunk_type": "text",
                        "section_title": sec_title
                    })
                current = part
            else:
                current += part
    if current.strip():
        chunks.append({
            "text": current.strip(),
            "chunk_type": _detect_chunk_type(current),
            "section_title": sec_title
        })


def _assign_page_numbers(chunks, pages_data):
    """청크 텍스트를 pages_data와 매칭하여 page_num + bbox 할당.
    bbox는 청크 내 첫 매칭 블록의 bbox를 사용 (검색 결과 → 페이지 PNG 위 하이라이트 오버레이용).
    """
    # 각 페이지의 텍스트 조각과 (페이지 번호, bbox) 매핑
    text_page_map = []
    for page in pages_data:
        for block in page.get("blocks", []):
            content = block.get("content", "")
            if content and len(content) > 10:
                text_page_map.append((
                    content[:100],
                    block.get("page_num", 0),
                    block.get("bbox", None),
                ))

    for chunk in chunks:
        chunk_text = chunk.get("text", "")
        best_page = 0
        best_bbox = None
        for snippet, pnum, bbox in text_page_map:
            if snippet[:50] in chunk_text:
                best_page = pnum
                best_bbox = bbox
                break
        chunk["page_num"] = best_page
        if best_bbox is not None:
            chunk["bbox"] = best_bbox

# ==============================================================================
# API 엔드포인트
# ==============================================================================

def models():
    """사용 가능한 임베딩 모델 목록"""
    model_list = []
    for key, info in MODEL_REGISTRY.items():
        model_list.append({
            "name": info["name"], "short_name": info["short_name"],
            "dim": info["dim"], "description": info["description"],
            "lang": info["lang"], "max_seq_length": info["max_seq_length"],
            "custom": info.get("custom", False)
        })
    wiz.response.status(200, models=model_list, default=DEFAULT_MODEL)


def vision_status():
    """Vision LLM (Gemma 4) 사용 가능 여부 확인"""
    available = False
    try:
        _vlm = wiz.model("vision_llm")
        available = _vlm.available()
    except Exception:
        pass
    wiz.response.status(200, available=available, model="google/gemma-4-E4B-it" if available else "")


def nougat_status():
    """Nougat OCR 사용 가능 여부 확인"""
    available = False
    status = {
        "model": "",
        "runtime": "",
        "loaded": False,
    }
    try:
        nougat = wiz.model("nougat_ocr")
        available = nougat.available()
        if hasattr(nougat, "status"):
            status = nougat.status()
    except Exception:
        pass
    wiz.response.status(
        200,
        available=available,
        model=status.get("model", "") if available else "",
        runtime=status.get("runtime", ""),
        loaded=bool(status.get("loaded", False)),
    )


def nougat_load():
    """Nougat 모델을 GPU 메모리에 로드"""
    nougat = wiz.model("nougat_ocr")
    if not nougat.available():
        wiz.response.status(400, message="Nougat 의존성이 설치되지 않았습니다.")
    nougat.load()
    status = nougat.status()
    wiz.response.status(200, loaded=status.get("loaded", False), model=status.get("model", ""))


def nougat_unload():
    """Nougat 모델을 GPU 메모리에서 해제"""
    nougat = wiz.model("nougat_ocr")
    nougat.unload()
    wiz.response.status(200, loaded=False)


def add_custom_model():
    """HuggingFace 등에서 SentenceTransformer 모델을 다운로드하여 레지스트리에 추가"""
    model_name = wiz.request.query("model_name", "").strip()
    if not model_name:
        wiz.response.status(400, message="모델 이름을 입력하세요.")

    # 이미 등록된 모델인지 확인
    registry = wiz.model("modelregistry")
    existing = registry.full()
    if model_name in existing:
        wiz.response.status(400, message=f"'{model_name}' 모델이 이미 등록되어 있습니다.")

    # SentenceTransformer로 모델 다운로드 및 로드 시도
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)

        # 모델 정보 추출
        dim = model.get_sentence_embedding_dimension()
        max_seq = getattr(model, 'max_seq_length', 512)

        # 언어 자동 감지 (이름 기반 휴리스틱)
        name_lower = model_name.lower()
        if any(kw in name_lower for kw in ['ko', 'korean', 'klue', 'kr-']):
            lang = "ko"
        elif any(kw in name_lower for kw in ['multilingual', 'multi', 'e5', 'labse', 'xlm']):
            lang = "multi"
        else:
            lang = "en"

        # 설명 자동 생성
        short_name = model_name.split("/")[-1] if "/" in model_name else model_name
        description = f"커스텀 모델 ({dim}D, max {max_seq} tokens)"

        # 레지스트리에 등록 (영속 저장)
        info = registry.add_model(
            name=model_name,
            dim=dim,
            description=description,
            lang=lang,
            short_name=short_name,
            max_seq_length=max_seq
        )

        # 모델 캐시에 등록 (다시 다운로드 방지)
        if not hasattr(sys, '_embedding_models') or sys._embedding_models is None:
            sys._embedding_models = {}
        sys._embedding_models[model_name] = model

        # MODEL_REGISTRY 갱신
        global MODEL_REGISTRY
        MODEL_REGISTRY = registry.full()

        wiz.response.status(200,
            model=info,
            message=f"'{short_name}' 모델이 성공적으로 추가되었습니다. ({dim}차원, max {max_seq} tokens)"
        )
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "not found" in error_msg.lower():
            wiz.response.status(400, message=f"모델 '{model_name}'을 찾을 수 없습니다. HuggingFace 모델 이름을 확인하세요.")
        elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            wiz.response.status(400, message=f"모델 다운로드 중 네트워크 오류가 발생했습니다: {error_msg}")
        else:
            wiz.response.status(400, message=f"모델 로드 실패: {error_msg}")


def remove_custom_model():
    """커스텀 모델을 레지스트리에서 삭제"""
    model_name = wiz.request.query("model_name", "").strip()
    if not model_name:
        wiz.response.status(400, message="모델 이름을 입력하세요.")

    registry = wiz.model("modelregistry")
    try:
        registry.remove_model(model_name)
    except ValueError as e:
        wiz.response.status(400, message=str(e))

    # 메모리 캐시에서도 제거
    if hasattr(sys, '_embedding_models') and sys._embedding_models and model_name in sys._embedding_models:
        del sys._embedding_models[model_name]

    # MODEL_REGISTRY 갱신
    global MODEL_REGISTRY
    MODEL_REGISTRY = registry.full()

    wiz.response.status(200, message=f"모델 '{model_name}'이 삭제되었습니다.")


def chunk_strategies():
    """사용 가능한 청킹 전략 목록"""
    strategies = []
    for key, info in CHUNK_STRATEGIES.items():
        strategies.append({
            "name": info["name"], "label": info["label"],
            "description": info["description"], "params": info["params"],
            "default": info.get("default", False)
        })
    wiz.response.status(200, strategies=strategies, ocr_available=HAS_TESSERACT)


def collections():
    """전체 컬렉션 목록 + 메타데이터"""
    try:
        client = _get_client()
        col_names = client.list_collections()
        meta = _load_collection_meta()
        meta_helper = wiz.model("collectionmeta")
        meta_updated = False

        result = []
        for name in col_names:
            info = meta_helper.normalize_info(meta.get(name, {}))
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
                    inferred_model = _infer_model_from_dim(dim)
                    model_info = MODEL_REGISTRY.get(inferred_model, {})
                    info = {
                        "model": inferred_model, "dim": dim,
                        "created_at": info.get("created_at", ""),
                        "short_name": model_info.get("short_name", inferred_model)
                    }
                    meta[name] = info
                    meta_updated = True
                except Exception:
                    pass

            total_docs = info.get("total_docs")
            if total_docs is None:
                total_docs = _count_collection_pdfs(name)
                info["total_docs"] = total_docs
                meta[name] = info
                meta_updated = True

            total_chunks = info.get("total_chunks")
            if total_chunks is None:
                total_chunks = 0
                try:
                    stats_info = client.get_collection_stats(name)
                    total_chunks = stats_info.get("row_count", 0)
                except Exception:
                    pass
                info["total_chunks"] = total_chunks
                meta[name] = info
                meta_updated = True

            result.append({
                "name": name, "model": info.get("model", DEFAULT_MODEL),
                "short_name": info.get("short_name", "Unknown"),
                "dim": info.get("dim", 768),
                "created_at": info.get("created_at", ""),
                "total_chunks": total_chunks, "total_docs": total_docs
            })

        if meta_updated:
            _save_collection_meta(meta)
        wiz.response.status(200, collections=result)

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def create_collection():
    """새 컬렉션 생성"""
    try:
        collection_name = wiz.request.query("collection_name", "").strip()
        model_name = wiz.request.query("model_name", DEFAULT_MODEL).strip()

        if not collection_name:
            wiz.response.status(400, message="컬렉션 이름을 입력하세요.")
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', collection_name):
            wiz.response.status(400, message="컬렉션 이름은 영문, 숫자, 밑줄만 사용하세요.")
        if model_name not in MODEL_REGISTRY:
            wiz.response.status(400, message=f"지원하지 않는 모델: {model_name}")

        client = _get_client()
        if client.has_collection(collection_name, timeout=10):
            wiz.response.status(400, message=f"'{collection_name}' 컬렉션이 이미 존재합니다.")

        _ensure_collection(collection_name, model_name, client=client)
        if not client.has_collection(collection_name, timeout=20):
            wiz.response.status(500, message=f"'{collection_name}' 컬렉션 생성 확인에 실패했습니다.")

        meta = _load_collection_meta()
        collection_meta = meta.get(collection_name, {})
        wiz.response.status(200,
            collection_name=collection_name, model=model_name,
            dim=MODEL_REGISTRY[model_name]["dim"],
            created_at=collection_meta.get("created_at", datetime.datetime.now().isoformat()),
            message=f"'{collection_name}' 컬렉션이 생성되었습니다.")

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def delete_collection():
    """컬렉션 삭제"""
    try:
        collection_name = wiz.request.query("collection_name", "").strip()
        if not collection_name:
            wiz.response.status(400, message="컬렉션 이름을 입력하세요.")

        client = _get_client()
        if not client.has_collection(collection_name, timeout=10):
            wiz.response.status(404, message=f"'{collection_name}' 컬렉션을 찾을 수 없습니다.")

        try:
            load_state = client.get_load_state(collection_name=collection_name, timeout=10)
            state = str(load_state.get("state", "")).lower()
            if state not in ("", "not_load", "not loaded"):
                client.release_collection(collection_name=collection_name, timeout=10)
        except Exception:
            try:
                client.release_collection(collection_name=collection_name, timeout=10)
            except Exception:
                pass

        client.drop_collection(collection_name=collection_name, timeout=20)
        if client.has_collection(collection_name, timeout=10):
            wiz.response.status(500, message=f"'{collection_name}' 컬렉션 삭제를 완료하지 못했습니다.")

        meta = _load_collection_meta()
        meta.pop(collection_name, None)
        _save_collection_meta(meta)

        pdf_dir = os.path.join(DATA_DIR, "pdfs", collection_name)
        if os.path.isdir(pdf_dir):
            shutil.rmtree(pdf_dir, ignore_errors=True)

        # 페이지 PNG 디렉토리도 함께 정리
        pages_dir = os.path.join(PAGES_DIR, collection_name)
        if os.path.isdir(pages_dir):
            shutil.rmtree(pages_dir, ignore_errors=True)

        wiz.response.status(200,
            collection_name=collection_name,
            message=f"'{collection_name}' 컬렉션이 삭제되었습니다.")

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def preview_extract():
    """PDF 추출 + 청킹 미리보기 (임베딩/저장 없이 결과만 반환)"""
    tmp_path = None
    try:
        file = wiz.request.file("file")
        if file is None:
            wiz.response.status(400, message="파일이 없습니다.")

        filename = file.filename
        if not filename.lower().endswith('.pdf'):
            wiz.response.status(400, message="PDF 파일만 지원합니다.")

        strategy = wiz.request.query("strategy", "semantic_section").strip()
        chunk_size = int(wiz.request.query("chunk_size", str(DEFAULT_CHUNK_SIZE)))
        chunk_overlap = int(wiz.request.query("chunk_overlap", str(DEFAULT_CHUNK_OVERLAP)))
        respect_sentences = wiz.request.query("respect_sentences", "true").lower() == "true"
        similarity_threshold = float(wiz.request.query("similarity_threshold", "0.5"))
        use_vision = wiz.request.query("use_vision", "false").lower() == "true"

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        # 추출
        extract_result = _extract_text_from_pdf(tmp_path, use_vision=use_vision)
        full_text = extract_result["full_text"]
        if not full_text.strip():
            wiz.response.status(400, message="PDF에서 텍스트를 추출할 수 없습니다.")

        page_count = len(extract_result["pages"])
        stats = extract_result["stats"]

        # 청킹
        chunks = _chunk_text(
            full_text, strategy=strategy, chunk_size=chunk_size,
            chunk_overlap=chunk_overlap, respect_sentences=respect_sentences,
            similarity_threshold=similarity_threshold,
            pages_data=extract_result["pages"]
        )

        # 섹션 구조 추출
        sections = []
        for page in extract_result["pages"]:
            for block in page["blocks"]:
                if block["type"] == "header":
                    sections.append({
                        "title": block["content"],
                        "page": block["page_num"]
                    })

        # 청크 타입 분포
        type_dist = {}
        for c in chunks:
            ct = c.get("chunk_type", "text")
            type_dist[ct] = type_dist.get(ct, 0) + 1

        # 샘플 청크 (최대 10개)
        sample_chunks = []
        for i, c in enumerate(chunks[:10]):
            sample_chunks.append({
                "index": i,
                "text": c["text"][:300] + ("..." if len(c["text"]) > 300 else ""),
                "chunk_type": c.get("chunk_type", "text"),
                "section_title": c.get("section_title", ""),
                "page_num": c.get("page_num", 0),
                "length": len(c["text"]),
                "content_elements": _detect_content_elements(c["text"])
            })

        wiz.response.status(200,
            filename=filename,
            total_pages=page_count,
            total_chunks=len(chunks),
            figures=stats["figures"],
            formulas=stats["formulas"],
            tables=stats["tables"],
            ocr_extractions=stats["ocr_extractions"],
            sections=sections,
            chunk_type_distribution=type_dist,
            sample_chunks=sample_chunks,
            strategy_used=strategy,
            avg_chunk_length=round(sum(len(c["text"]) for c in chunks) / max(len(chunks), 1))
        )

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def upload():
    """PDF 업로드 → 추출 → 청킹 → 임베딩 → Milvus 저장"""
    tmp_path = None
    try:
        file = wiz.request.file("file")
        if file is None:
            wiz.response.status(400, message="파일이 없습니다.")

        filename = file.filename
        if not filename.lower().endswith('.pdf'):
            wiz.response.status(400, message="PDF 파일만 지원합니다.")

        # 옵션
        collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip()
        model_name = wiz.request.query("model", "").strip()
        chunk_size = int(wiz.request.query("chunk_size", str(DEFAULT_CHUNK_SIZE)))
        chunk_overlap = int(wiz.request.query("chunk_overlap", str(DEFAULT_CHUNK_OVERLAP)))
        respect_sentences = wiz.request.query("respect_sentences", "true").lower() == "true"
        strategy = wiz.request.query("chunk_strategy", "semantic_section").strip()
        similarity_threshold = float(wiz.request.query("similarity_threshold", "0.5"))
        use_vision = wiz.request.query("use_vision", "false").lower() == "true"
        use_nougat = wiz.request.query("use_nougat", "false").lower() == "true"
        gemma_rescue = wiz.request.query("gemma_rescue", "false").lower() == "true"
        extraction_mode = _resolve_extraction_mode(
            wiz.request.query("extraction_mode", "surya"),
            use_nougat=use_nougat,
            use_ocr=True,
        )
        use_ocr = extraction_mode in ("surya", "nougat_hybrid")
        use_nougat = extraction_mode == "nougat_hybrid" or use_nougat

        if not model_name:
            model_name = _get_collection_model(collection_name)
        if model_name not in MODEL_REGISTRY:
            model_name = DEFAULT_MODEL

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        # 1. 스마트 텍스트 추출
        extract_result = _extract_text_from_pdf(
            tmp_path,
            use_vision=use_vision,
            use_ocr=use_ocr,
            use_nougat=use_nougat,
            gemma_rescue=gemma_rescue,
            extraction_mode=extraction_mode,
        )
        full_text = extract_result["full_text"]
        if not full_text.strip():
            wiz.response.status(400, message="PDF에서 텍스트를 추출할 수 없습니다.")

        page_count = len(extract_result["pages"])
        ext_stats = extract_result["stats"]

        # 2. 청킹
        chunks = _chunk_text(
            full_text, strategy=strategy, chunk_size=chunk_size,
            chunk_overlap=chunk_overlap, respect_sentences=respect_sentences,
            similarity_threshold=similarity_threshold, model_name=model_name,
            pages_data=extract_result["pages"]
        )
        if not chunks:
            wiz.response.status(400, message="유효한 텍스트 청크가 없습니다.")

        # 3. 임베딩 — 수식 청크에 검색 친화적 텍스트 보강
        model = _get_model(model_name)
        texts_to_embed = []
        for c in chunks:
            t = c["text"]
            ct = c.get("chunk_type", "text")
            if ct in ("formula", "mixed"):
                # 수식 마커에서 LaTeX와 context를 추출하여 검색용 텍스트 보강
                enhanced = _enhance_equation_text_for_embedding(t)
                texts_to_embed.append(enhanced)
            else:
                texts_to_embed.append(t)
        embeddings = model.encode(texts_to_embed, show_progress_bar=False, normalize_embeddings=True)

        # 4. Milvus 저장
        client = _get_client()
        client = _ensure_collection(collection_name, model_name, client=client)
        doc_id = str(uuid.uuid4())[:8]

        # 4-1. PDF 원본 영구 저장 (검색 결과에서 원문 조회용)
        pdf_dir = os.path.join(DATA_DIR, "pdfs", collection_name)
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_dest = os.path.join(pdf_dir, f"{doc_id}.pdf")
        import shutil
        shutil.copy2(tmp_path, pdf_dest)

        # 4-2. 페이지 PNG 사전 렌더링 (모달 뷰어 / 썸네일용)
        try:
            render_info = _render_pdf_pages(pdf_dest, collection_name, doc_id)
        except Exception:
            traceback.print_exc()
            render_info = {"page_count": 0, "skipped": False}

        # 스키마 필드 존재 여부 확인 (하위 호환)
        has_extended_fields = True
        has_bbox_field = False
        try:
            col_info = client.describe_collection(collection_name)
            field_names = [f.get("name", "") for f in col_info.get("fields", [])]
            if "content_elements" not in field_names:
                has_extended_fields = False
            has_bbox_field = "bbox" in field_names
        except Exception:
            has_extended_fields = False

        data = []
        # 페이지별 provenance 맵 구축
        page_source_map = {}
        for pg in extract_result["pages"]:
            pn = pg.get("page_num", 0)
            page_source_map[pn] = {
                "text_source": pg.get("preferred_text_source", pg.get("text_source", "native")),
                "has_rescue": any(
                    b.get("rescue_source") for b in pg.get("blocks", []) if b.get("type") == "formula"
                ),
            }

        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            page_num = chunk.get("page_num", 0)
            prov = page_source_map.get(page_num, {})

            record = {
                "id": f"{doc_id}_{i:04d}",
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": i,
                "chunk_type": chunk.get("chunk_type", "text"),
                "page_num": page_num,
                "section_title": chunk.get("section_title", "")[:500],
                "text": chunk["text"][:8000],
                "embedding": emb.tolist()
            }
            if has_extended_fields:
                elements = _detect_content_elements(chunk["text"])
                record["content_elements"] = json.dumps(elements, ensure_ascii=False)[:1000]
                base_sc = _extract_structured_content(chunk["text"])
                # provenance를 structured_content 끝에 JSON 블록으로 추가
                provenance = {
                    "source_text": prov.get("text_source", "native"),
                    "source_layout": "pymupdf",
                    "extraction_mode": extraction_mode,
                }
                if prov.get("has_rescue"):
                    provenance["rescue_applied"] = True
                prov_json = json.dumps({"_provenance": provenance}, ensure_ascii=False)
                record["structured_content"] = (base_sc + "\n" + prov_json)[:8000]
            if has_bbox_field:
                bbox = chunk.get("bbox")
                if bbox:
                    try:
                        record["bbox"] = json.dumps([round(float(v), 2) for v in bbox])[:128]
                    except Exception:
                        record["bbox"] = ""
                else:
                    record["bbox"] = ""

            data.append(record)

        client.insert(collection_name=collection_name, data=data)

        meta = _load_collection_meta()
        collection_meta = meta.get(collection_name, {})
        collection_meta["model"] = model_name
        collection_meta["dim"] = MODEL_REGISTRY.get(model_name, {}).get("dim", len(data[0].get("embedding", [])) if len(data) > 0 else 768)
        collection_meta["short_name"] = MODEL_REGISTRY.get(model_name, {}).get("short_name", model_name)
        collection_meta["created_at"] = collection_meta.get("created_at", datetime.datetime.now().isoformat())
        collection_meta["total_docs"] = int(collection_meta.get("total_docs", 0)) + 1
        collection_meta["total_chunks"] = int(collection_meta.get("total_chunks", 0)) + len(data)
        meta[collection_name] = collection_meta
        _save_collection_meta(meta)

        # 청크 타입 분포
        chunk_types = {}
        for c in chunks:
            ct = c.get("chunk_type", "text")
            chunk_types[ct] = chunk_types.get(ct, 0) + 1

        wiz.response.status(200,
            filename=filename, doc_id=doc_id,
            total_pages=page_count,
            extraction_mode=extraction_mode,
            use_nougat=use_nougat,
            gemma_rescue_requested=gemma_rescue,
            chunks_count=len(chunks),
            vectors_stored=len(data),
            figures_detected=ext_stats["figures"],
            formulas_detected=ext_stats["formulas"],
            tables_detected=ext_stats["tables"],
            ocr_extractions=ext_stats["ocr_extractions"],
            ocr_pages_used=ext_stats.get("ocr_pages_used", 0),
            surya_available=ext_stats.get("surya_available", False),
            nougat_available=ext_stats.get("nougat_available", False),
            nougat_pages_used=ext_stats.get("nougat_pages_used", 0),
            native_pages_used=ext_stats.get("native_pages_used", 0),
            failed_pages=ext_stats.get("failed_pages", []),
            gemma_rescues=ext_stats.get("gemma_rescues", 0),
            rescue_skipped=ext_stats.get("rescue_skipped", 0),
            rescue_failed=ext_stats.get("rescue_failed", 0),
            pages_rendered=render_info.get("page_count", 0),
            model_used=MODEL_REGISTRY.get(model_name, {}).get("short_name", model_name),
            collection=collection_name,
            strategy_used=strategy,
            chunk_types=chunk_types)

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def stats():
    """특정 컬렉션 통계"""
    try:
        collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip()
        client = _get_client()
        meta = _load_collection_meta()

        if not client.has_collection(collection_name):
            col_meta = meta.get(collection_name, {})
            wiz.response.status(200,
                total_docs=0, total_chunks=0,
                model_name=col_meta.get("model", DEFAULT_MODEL),
                collection=collection_name)
            return
        col_meta = meta.get(collection_name, {})
        total_docs = col_meta.get("total_docs")
        if total_docs is None:
            total_docs = _count_collection_pdfs(collection_name)
            col_meta["total_docs"] = total_docs

        total_chunks = col_meta.get("total_chunks")
        if total_chunks is None:
            total_chunks = 0
            try:
                stats_info = client.get_collection_stats(collection_name)
                total_chunks = stats_info.get("row_count", 0)
            except Exception:
                total_chunks = 0
            col_meta["total_chunks"] = total_chunks

        if meta.get(collection_name) != col_meta:
            meta[collection_name] = col_meta
            _save_collection_meta(meta)

        model_name = col_meta.get("model", DEFAULT_MODEL)
        model_info = MODEL_REGISTRY.get(model_name, {})

        wiz.response.status(200,
            total_docs=total_docs, total_chunks=total_chunks,
            model_name=model_name,
            model_short_name=model_info.get("short_name", model_name),
            model_dim=model_info.get("dim", 768),
            collection=collection_name,
            created_at=col_meta.get("created_at", ""))

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        wiz.response.status(200,
            total_docs=0, total_chunks=0,
            model_name=DEFAULT_MODEL,
            collection=collection_name if 'collection_name' in dir() else DEFAULT_COLLECTION,
            error=str(e))


def chunk_type_stats():
    """컬렉션 내 청크 타입별 통계 (배치 페이지네이션 적용)"""
    BATCH_SIZE = 16000  # Milvus Lite limit 16384 이내

    try:
        collection_name = wiz.request.query("collection", DEFAULT_COLLECTION).strip()
        client = _get_client()

        if not client.has_collection(collection_name):
            wiz.response.status(200, stats={}, total=0, collection=collection_name)

        stats_info = client.get_collection_stats(collection_name)
        total_chunks = stats_info.get("row_count", 0)

        if total_chunks == 0:
            wiz.response.status(200, stats={}, total=0, collection=collection_name)

        # 스키마 필드 확인
        schema_fields = _get_collection_fields(client, collection_name)
        has_chunk_type = "chunk_type" in schema_fields

        type_counts = {}
        offset = 0

        while True:
            if has_chunk_type:
                results = client.query(
                    collection_name=collection_name,
                    filter="chunk_index >= 0",
                    output_fields=["chunk_type"],
                    limit=BATCH_SIZE,
                    offset=offset
                )
                for r in results:
                    ct = r.get("chunk_type", "text") or "text"
                    type_counts[ct] = type_counts.get(ct, 0) + 1
            else:
                results = client.query(
                    collection_name=collection_name,
                    filter="chunk_index >= 0",
                    output_fields=["text"],
                    limit=BATCH_SIZE,
                    offset=offset
                )
                for r in results:
                    text = r.get("text", "")
                    ct = _detect_chunk_type(text)
                    type_counts[ct] = type_counts.get(ct, 0) + 1

            # 배치가 BATCH_SIZE 미만이면 마지막 배치
            if len(results) < BATCH_SIZE:
                break
            offset += len(results)

        wiz.response.status(200,
            stats=type_counts,
            total=sum(type_counts.values()),
            collection=collection_name,
            method="schema" if has_chunk_type else "content_analysis"
        )

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def documents():
    """컬렉션 내 문서 목록 조회 (doc_id 기준 그룹핑)"""
    BATCH_SIZE = 16000
    try:
        collection_name = wiz.request.query("collection", "").strip()
        if not collection_name:
            wiz.response.status(400, message="컬렉션 이름이 필요합니다.")

        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(200, documents=[], collection=collection_name)

        schema_fields = _get_collection_fields(client, collection_name)
        output_fields = ["doc_id", "filename", "chunk_index", "page_num"]
        has_chunk_type = "chunk_type" in schema_fields
        if has_chunk_type:
            output_fields.append("chunk_type")

        doc_map = {}
        offset = 0

        while True:
            results = client.query(
                collection_name=collection_name,
                filter="chunk_index >= 0",
                output_fields=output_fields,
                limit=BATCH_SIZE,
                offset=offset
            )

            for r in results:
                did = r.get("doc_id", "unknown")
                if did not in doc_map:
                    doc_map[did] = {
                        "doc_id": did,
                        "filename": r.get("filename", ""),
                        "chunk_count": 0,
                        "pages": set(),
                        "type_counts": {}
                    }
                doc = doc_map[did]
                doc["chunk_count"] += 1
                pn = r.get("page_num", 0)
                if pn > 0:
                    doc["pages"].add(pn)
                ct = r.get("chunk_type", "text") or "text"
                doc["type_counts"][ct] = doc["type_counts"].get(ct, 0) + 1

            if len(results) < BATCH_SIZE:
                break
            offset += len(results)

        doc_list = []
        for did, doc in doc_map.items():
            pdf_path = os.path.join(DATA_DIR, "pdfs", collection_name, f"{did}.pdf")
            doc_list.append({
                "doc_id": did,
                "filename": doc["filename"],
                "chunk_count": doc["chunk_count"],
                "page_count": len(doc["pages"]),
                "type_counts": doc["type_counts"],
                "has_pdf": os.path.isfile(pdf_path)
            })
        doc_list.sort(key=lambda x: x["filename"])

        wiz.response.status(200, documents=doc_list, collection=collection_name)

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def document_chunks():
    """특정 문서의 청크 목록 (페이징, 필터)"""
    try:
        collection_name = wiz.request.query("collection", "").strip()
        doc_id = wiz.request.query("doc_id", "").strip()
        page = int(wiz.request.query("page", 1))
        dump = int(wiz.request.query("dump", 20))
        chunk_type_filter = wiz.request.query("chunk_type", "").strip()

        if not collection_name or not doc_id:
            wiz.response.status(400, message="collection과 doc_id가 필요합니다.")

        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(404, message="컬렉션을 찾을 수 없습니다.")

        schema_fields = _get_collection_fields(client, collection_name)
        output_fields = ["id", "doc_id", "filename", "chunk_index", "page_num",
                         "section_title", "text"]
        if "chunk_type" in schema_fields:
            output_fields.append("chunk_type")
        if "content_elements" in schema_fields:
            output_fields.append("content_elements")
        if "structured_content" in schema_fields:
            output_fields.append("structured_content")

        filter_expr = f'doc_id == "{doc_id}"'
        if chunk_type_filter:
            filter_expr += f' and chunk_type == "{chunk_type_filter}"'

        # 전체 카운트 (필터 적용)
        count_results = client.query(
            collection_name=collection_name,
            filter=filter_expr,
            output_fields=["chunk_index"],
            limit=16000
        )
        total = len(count_results)

        # 페이징으로 가져오기 (chunk_index 정렬은 클라이언트 사이드)
        all_results = client.query(
            collection_name=collection_name,
            filter=filter_expr,
            output_fields=output_fields,
            limit=16000
        )
        all_results.sort(key=lambda x: x.get("chunk_index", 0))

        start = (page - 1) * dump
        end = start + dump
        page_results = all_results[start:end]

        chunks = []
        for r in page_results:
            chunk = {
                "id": r.get("id", ""),
                "chunk_index": r.get("chunk_index", 0),
                "chunk_type": r.get("chunk_type", "text") or "text",
                "page_num": r.get("page_num", 0),
                "section_title": r.get("section_title", ""),
                "text": r.get("text", ""),
                "text_length": len(r.get("text", "")),
                "content_elements": r.get("content_elements", ""),
                "structured_content": r.get("structured_content", "")
            }
            chunks.append(chunk)

        wiz.response.status(200,
            chunks=chunks,
            total=total,
            page=page,
            dump=dump,
            total_pages=(total + dump - 1) // dump if dump > 0 else 1,
            collection=collection_name,
            doc_id=doc_id
        )

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


def delete_document():
    """특정 문서의 모든 청크 삭제 + PDF 원본 삭제"""
    try:
        collection_name = wiz.request.query("collection", "").strip()
        doc_id = wiz.request.query("doc_id", "").strip()

        if not collection_name or not doc_id:
            wiz.response.status(400, message="collection과 doc_id가 필요합니다.")

        client = _get_client()
        if not client.has_collection(collection_name):
            wiz.response.status(404, message="컬렉션을 찾을 수 없습니다.")

        # 해당 doc_id의 청크 ID 조회
        results = client.query(
            collection_name=collection_name,
            filter=f'doc_id == "{doc_id}"',
            output_fields=["id"],
            limit=16000
        )
        chunk_ids = [r["id"] for r in results]
        deleted_count = len(chunk_ids)

        if chunk_ids:
            client.delete(
                collection_name=collection_name,
                filter=f'doc_id == "{doc_id}"'
            )

        # PDF 원본 삭제
        pdf_path = os.path.join(DATA_DIR, "pdfs", collection_name, f"{doc_id}.pdf")
        pdf_deleted = False
        if os.path.isfile(pdf_path):
            os.remove(pdf_path)
            pdf_deleted = True

        # 페이지 PNG 디렉토리 삭제
        pages_doc_dir = _page_dir(collection_name, doc_id)
        if os.path.isdir(pages_doc_dir):
            shutil.rmtree(pages_doc_dir, ignore_errors=True)

        # 메타데이터 갱신
        meta = _load_collection_meta()
        col_meta = meta.get(collection_name, {})
        if "total_chunks" in col_meta:
            col_meta["total_chunks"] = max(0, col_meta.get("total_chunks", 0) - deleted_count)
        if "total_docs" in col_meta:
            col_meta["total_docs"] = _count_collection_pdfs(collection_name)
        meta[collection_name] = col_meta
        _save_collection_meta(meta)

        wiz.response.status(200,
            doc_id=doc_id,
            deleted_chunks=deleted_count,
            pdf_deleted=pdf_deleted,
            collection=collection_name,
            message=f"문서 '{doc_id}' 삭제 완료 ({deleted_count}개 청크)"
        )

    except season.lib.exception.ResponseException:
        raise
    except Exception as e:
        traceback.print_exc()
        wiz.response.status(500, message=str(e))


# ==============================================================================
# 페이지 이미지 서빙 (모달 뷰어 / 썸네일)
# ==============================================================================
def _safe_collection_doc(collection, doc_id):
    if not collection or not doc_id:
        wiz.response.status(400, message="collection, doc_id가 필요합니다.")
    if "/" in collection or ".." in collection:
        wiz.response.status(400, message="잘못된 collection")
    if "/" in doc_id or ".." in doc_id:
        wiz.response.status(400, message="잘못된 doc_id")


def _ensure_page_rendered(collection, doc_id, page_no):
    """요청된 페이지가 PNG로 없으면 PDF에서 lazy 렌더링 (마이그레이션 케이스)."""
    out_dir = _page_dir(collection, doc_id)
    page_path = os.path.join(out_dir, f"page_{page_no:04d}.png")
    if os.path.isfile(page_path):
        return page_path
    pdf_path = os.path.join(DATA_DIR, "pdfs", collection, f"{doc_id}.pdf")
    if not os.path.isfile(pdf_path):
        return None
    try:
        _render_pdf_pages(pdf_path, collection, doc_id)
    except Exception:
        traceback.print_exc()
        return None
    return page_path if os.path.isfile(page_path) else None


def page_image():
    """페이지 PNG 본문 이미지 반환. ?collection=...&doc_id=...&page=N"""
    collection = wiz.request.query("collection", "").strip()
    doc_id = wiz.request.query("doc_id", "").strip()
    try:
        page_no = int(wiz.request.query("page", "1"))
    except Exception:
        page_no = 1
    _safe_collection_doc(collection, doc_id)
    if page_no < 1:
        wiz.response.status(400, message="잘못된 page")

    img_path = _ensure_page_rendered(collection, doc_id, page_no)
    if img_path is None:
        wiz.response.status(404, message="페이지 이미지를 찾을 수 없습니다.")

    flask = wiz.response._flask
    with open(img_path, "rb") as f:
        body = f.read()
    resp = flask.Response(body, mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    wiz.response.response(resp)


def thumb():
    """썸네일 PNG 반환. ?collection=...&doc_id=...&page=N"""
    collection = wiz.request.query("collection", "").strip()
    doc_id = wiz.request.query("doc_id", "").strip()
    try:
        page_no = int(wiz.request.query("page", "1"))
    except Exception:
        page_no = 1
    _safe_collection_doc(collection, doc_id)
    if page_no < 1:
        wiz.response.status(400, message="잘못된 page")

    out_dir = _page_dir(collection, doc_id)
    thumb_path = os.path.join(out_dir, f"thumb_{page_no:04d}.png")
    if not os.path.isfile(thumb_path):
        # 본문 PNG 렌더링 시 썸네일도 같이 생성됨 → trigger
        _ensure_page_rendered(collection, doc_id, page_no)
    if not os.path.isfile(thumb_path):
        # 페이지 PNG가 있으면 그걸 그대로 반환 (fallback)
        page_path = os.path.join(out_dir, f"page_{page_no:04d}.png")
        if os.path.isfile(page_path):
            thumb_path = page_path
        else:
            wiz.response.status(404, message="썸네일을 찾을 수 없습니다.")

    flask = wiz.response._flask
    with open(thumb_path, "rb") as f:
        body = f.read()
    resp = flask.Response(body, mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    wiz.response.response(resp)


def page_meta():
    """페이지 메타(크기, DPI) 반환 — bbox 좌표 변환에 사용. ?collection=...&doc_id=..."""
    collection = wiz.request.query("collection", "").strip()
    doc_id = wiz.request.query("doc_id", "").strip()
    _safe_collection_doc(collection, doc_id)

    meta_path = os.path.join(_page_dir(collection, doc_id), "_pages.json")
    if not os.path.isfile(meta_path):
        # PDF가 있으면 즉석 렌더링
        pdf_path = os.path.join(DATA_DIR, "pdfs", collection, f"{doc_id}.pdf")
        if os.path.isfile(pdf_path):
            try:
                _render_pdf_pages(pdf_path, collection, doc_id)
            except Exception:
                traceback.print_exc()
    if not os.path.isfile(meta_path):
        wiz.response.status(404, message="페이지 메타를 찾을 수 없습니다.")
    with open(meta_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    wiz.response.status(200, **data)


def render_pages():
    """기존 문서를 다시 렌더링 (마이그레이션용). ?collection=...&doc_id=..."""
    collection = wiz.request.query("collection", "").strip()
    doc_id = wiz.request.query("doc_id", "").strip()
    _safe_collection_doc(collection, doc_id)

    pdf_path = os.path.join(DATA_DIR, "pdfs", collection, f"{doc_id}.pdf")
    if not os.path.isfile(pdf_path):
        wiz.response.status(404, message="PDF 원본을 찾을 수 없습니다.")

    # 기존 디렉토리 비우고 재렌더링
    out_dir = _page_dir(collection, doc_id)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir, ignore_errors=True)
    info = _render_pdf_pages(pdf_path, collection, doc_id)
    wiz.response.status(200,
        collection=collection, doc_id=doc_id,
        pages_rendered=info.get("page_count", 0))
