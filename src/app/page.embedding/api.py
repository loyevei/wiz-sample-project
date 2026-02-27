import os
import sys
import json
import re
import uuid
import datetime
import tempfile
import traceback

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
DEFAULT_COLLECTION = "plasma_papers"
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100

# ==============================================================================
# 모델 레지스트리
# ==============================================================================
MODEL_REGISTRY = {
    "snunlp/KR-SBERT-V40K-klueNLI-augSTS": {
        "name": "snunlp/KR-SBERT-V40K-klueNLI-augSTS",
        "dim": 768, "description": "한국어 최적화 SBERT (KlueNLI + augSTS)",
        "lang": "ko", "short_name": "KR-SBERT", "max_seq_length": 128
    },
    "BM-K/KoSimCSE-roberta-multitask": {
        "name": "BM-K/KoSimCSE-roberta-multitask",
        "dim": 768, "description": "한국어 SimCSE RoBERTa 멀티태스크",
        "lang": "ko", "short_name": "KoSimCSE", "max_seq_length": 512
    },
    "jhgan/ko-sroberta-multitask": {
        "name": "jhgan/ko-sroberta-multitask",
        "dim": 768, "description": "한국어 SRoBERTa 멀티태스크",
        "lang": "ko", "short_name": "ko-sroberta", "max_seq_length": 512
    },
    "sentence-transformers/all-MiniLM-L6-v2": {
        "name": "sentence-transformers/all-MiniLM-L6-v2",
        "dim": 384, "description": "영어 경량 MiniLM (고속 추론)",
        "lang": "en", "short_name": "MiniLM-L6", "max_seq_length": 256
    },
    "sentence-transformers/all-mpnet-base-v2": {
        "name": "sentence-transformers/all-mpnet-base-v2",
        "dim": 768, "description": "영어 고성능 MPNet",
        "lang": "en", "short_name": "MPNet", "max_seq_length": 384
    },
    "BAAI/bge-base-en-v1.5": {
        "name": "BAAI/bge-base-en-v1.5",
        "dim": 768, "description": "영어 BGE base (BAAI)",
        "lang": "en", "short_name": "BGE-base", "max_seq_length": 512
    },
    "intfloat/multilingual-e5-large": {
        "name": "intfloat/multilingual-e5-large",
        "dim": 1024, "description": "다국어 E5 Large (한국어 지원)",
        "lang": "multi", "short_name": "mE5-Large", "max_seq_length": 512
    },
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": {
        "name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "dim": 384, "description": "경량 다국어 MiniLM (빠른 추론)",
        "lang": "multi", "short_name": "MiniLM-L12", "max_seq_length": 128
    }
}
DEFAULT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

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
    # 그리스 대문자
    'Γ': r'\Gamma', 'Δ': r'\Delta', 'Θ': r'\Theta', 'Λ': r'\Lambda',
    'Ξ': r'\Xi', 'Π': r'\Pi', 'Σ': r'\Sigma', 'Υ': r'\Upsilon',
    'Φ': r'\Phi', 'Ψ': r'\Psi', 'Ω': r'\Omega',
    # 연산자/기호
    '∫': r'\int', '∑': r'\sum', '∂': r'\partial', '√': r'\sqrt',
    '∞': r'\infty', '±': r'\pm', '×': r'\times', '÷': r'\div',
    '≈': r'\approx', '≠': r'\neq', '≤': r'\leq', '≥': r'\geq',
    '∈': r'\in', '∉': r'\notin', '⊂': r'\subset', '⊃': r'\supset',
    '∪': r'\cup', '∩': r'\cap', '∀': r'\forall', '∃': r'\exists',
    '∅': r'\emptyset', '∇': r'\nabla', '∆': r'\Delta',
    '∝': r'\propto', '∼': r'\sim', '≡': r'\equiv', '≅': r'\cong',
    '⊥': r'\perp', '∧': r'\wedge', '∨': r'\vee', '¬': r'\neg',
    '→': r'\rightarrow', '←': r'\leftarrow', '↔': r'\leftrightarrow',
    '⇒': r'\Rightarrow', '⇐': r'\Leftarrow', '⇔': r'\Leftrightarrow',
    '∘': r'\circ', '·': r'\cdot',
    # 위/아래 첨자 숫자
    '⁰': '^{0}', '¹': '^{1}', '²': '^{2}', '³': '^{3}', '⁴': '^{4}',
    '⁵': '^{5}', '⁶': '^{6}', '⁷': '^{7}', '⁸': '^{8}', '⁹': '^{9}',
    '₀': '_{0}', '₁': '_{1}', '₂': '_{2}', '₃': '_{3}', '₄': '_{4}',
    '₅': '_{5}', '₆': '_{6}', '₇': '_{7}', '₈': '_{8}', '₉': '_{9}',
}

# ==============================================================================
# 수식/그림/표 감지용 상수
# ==============================================================================
MATH_FONTS = {"symbol", "cmmi", "cmsy", "cmr", "cmex", "mathjax", "stix", "cambria math", "math"}
MATH_CHARS = set("∫∑∂√∞±×÷≈≠≤≥∈∉⊂⊃∪∩∀∃∅∇∆αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΥΦΨΩ∝∼≡≅⊥∧∨¬→←↔⇒⇐⇔∘·")
FIGURE_PATTERNS = re.compile(r'^\s*(Fig\.?|Figure|그림|FIGURE|fig\.?)\s*\.?\s*\d', re.IGNORECASE)
TABLE_CAPTION_PATTERNS = re.compile(r'^\s*(Table|표|TABLE)\s*\.?\s*\d', re.IGNORECASE)
SPECIAL_MARKER = re.compile(r'\[(FIGURE|EQUATION|TABLE):\s')

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
    if os.path.exists(COLLECTION_META_PATH):
        try:
            with open(COLLECTION_META_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_collection_meta(meta):
    os.makedirs(os.path.dirname(COLLECTION_META_PATH), exist_ok=True)
    with open(COLLECTION_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def _get_collection_model(collection_name):
    meta = _load_collection_meta()
    info = meta.get(collection_name, {})
    return info.get("model", DEFAULT_MODEL)

def _infer_model_from_dim(dim):
    dim_to_models = {}
    for name, info in MODEL_REGISTRY.items():
        d = info["dim"]
        if d not in dim_to_models:
            dim_to_models[d] = name
    return dim_to_models.get(dim, DEFAULT_MODEL)


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
def _ensure_collection(collection_name, model_name=None):
    client = _get_client()
    if not client.has_collection(collection_name):
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
            FieldSchema(name="section_title", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="content_elements", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="structured_content", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        ]
        schema = CollectionSchema(fields=fields, description=f"Embeddings ({model_name})")
        index_params = client.prepare_index_params()
        index_params.add_index(field_name="embedding", index_type="FLAT", metric_type="COSINE")
        client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)

        meta = _load_collection_meta()
        meta[collection_name] = {
            "model": model_name, "dim": dim,
            "created_at": datetime.datetime.now().isoformat(),
            "short_name": MODEL_REGISTRY.get(model_name, {}).get("short_name", model_name)
        }
        _save_collection_meta(meta)

    return client

# ==============================================================================
# 유니코드 → LaTeX 변환
# ==============================================================================
def _unicode_to_latex(text):
    """유니코드 수학 기호를 LaTeX 명령어로 근사 변환"""
    result = []
    for ch in text:
        if ch in UNICODE_TO_LATEX:
            result.append(UNICODE_TO_LATEX[ch])
        else:
            result.append(ch)
    return ''.join(result)

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
    """span이 수식인지 판별"""
    font = span.get("font", "").lower()
    text = span.get("text", "")
    for mf in MATH_FONTS:
        if mf in font:
            return True
    if len(text) > 0:
        math_ratio = sum(1 for c in text if c in MATH_CHARS) / len(text)
        if math_ratio > 0.3:
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
def _extract_text_from_pdf(pdf_path):
    """PyMuPDF dict 모드로 구조화 추출 — 이미지 OCR, 표 마크다운, 수식 LaTeX"""
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

    # 2패스: 구조화 추출
    current_section = ""
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        page_blocks = []
        blocks = page_dict.get("blocks", [])

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

            # 이미지 블록 → OCR + 캡션
            if block.get("type", 0) == 1:
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                caption = _find_figure_caption(blocks, bbox)

                # OCR로 이미지 내 텍스트 추출
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
            context_before = ""
            context_after = ""
            lines = block.get("lines", [])

            for line_idx, line in enumerate(lines):
                line_text = ""
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if _is_math_span(span):
                        has_math = True
                        math_spans_text.append(span_text)
                    line_text += span_text
                block_text += line_text

            block_text = block_text.strip()
            if not block_text:
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
                # 수식 강화: LaTeX 변환 + 인라인/디스플레이 구분
                equation_counter[0] += 1
                eq_idx = equation_counter[0]
                eq_type = _classify_equation_type(block, lines)
                latex_text = _unicode_to_latex(block_text)
                raw_math = "".join(math_spans_text)
                latex_math = _unicode_to_latex(raw_math) if raw_math else latex_text

                if eq_type == "display":
                    marker = f"[EQUATION: eq_{eq_idx} | type=display | $${latex_math}$$ | context: {block_text}]"
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
            "section": current_section
        })

    doc.close()
    full_text = "\n\n".join(all_text_parts)
    return {
        "full_text": full_text,
        "pages": pages_data,
        "stats": {
            "figures": figure_count,
            "formulas": formula_count,
            "tables": table_count,
            "ocr_extractions": ocr_count,
            "total_equations": equation_counter[0]
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
    """청크 텍스트를 pages_data와 매칭하여 page_num 할당"""
    # 각 페이지의 텍스트 조각과 페이지 번호 매핑
    text_page_map = []
    for page in pages_data:
        for block in page.get("blocks", []):
            content = block.get("content", "")
            if content and len(content) > 10:
                text_page_map.append((content[:100], block.get("page_num", 0)))

    for chunk in chunks:
        chunk_text = chunk.get("text", "")
        best_page = 0
        for snippet, pnum in text_page_map:
            if snippet[:50] in chunk_text:
                best_page = pnum
                break
        chunk["page_num"] = best_page

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
            "lang": info["lang"], "max_seq_length": info["max_seq_length"]
        })
    wiz.response.status(200, models=model_list, default=DEFAULT_MODEL)


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
        meta_updated = False

        result = []
        for name in col_names:
            info = meta.get(name, {})
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

            total_chunks = 0
            total_docs = 0
            try:
                stats_info = client.get_collection_stats(name)
                total_chunks = stats_info.get("row_count", 0)
                if total_chunks > 0:
                    docs = client.query(
                        collection_name=name, filter="chunk_index == 0",
                        output_fields=["doc_id"], limit=10000
                    )
                    total_docs = len(docs)
            except Exception:
                pass

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
        if client.has_collection(collection_name):
            wiz.response.status(400, message=f"'{collection_name}' 컬렉션이 이미 존재합니다.")

        _ensure_collection(collection_name, model_name)
        wiz.response.status(200,
            collection_name=collection_name, model=model_name,
            dim=MODEL_REGISTRY[model_name]["dim"],
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
        if not client.has_collection(collection_name):
            wiz.response.status(404, message=f"'{collection_name}' 컬렉션을 찾을 수 없습니다.")

        client.drop_collection(collection_name)
        meta = _load_collection_meta()
        meta.pop(collection_name, None)
        _save_collection_meta(meta)
        wiz.response.status(200, message=f"'{collection_name}' 컬렉션이 삭제되었습니다.")

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

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        # 추출
        extract_result = _extract_text_from_pdf(tmp_path)
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

        if not model_name:
            model_name = _get_collection_model(collection_name)
        if model_name not in MODEL_REGISTRY:
            model_name = DEFAULT_MODEL

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        # 1. 스마트 텍스트 추출
        extract_result = _extract_text_from_pdf(tmp_path)
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

        # 3. 임베딩
        model = _get_model(model_name)
        texts_to_embed = [c["text"] for c in chunks]
        embeddings = model.encode(texts_to_embed, show_progress_bar=False, normalize_embeddings=True)

        # 4. Milvus 저장
        client = _ensure_collection(collection_name, model_name)
        doc_id = str(uuid.uuid4())[:8]

        # 스키마 필드 존재 여부 확인 (하위 호환)
        has_extended_fields = True
        try:
            col_info = client.describe_collection(collection_name)
            field_names = [f.get("name", "") for f in col_info.get("fields", [])]
            if "content_elements" not in field_names:
                has_extended_fields = False
        except Exception:
            has_extended_fields = False

        data = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            record = {
                "id": f"{doc_id}_{i:04d}",
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": i,
                "chunk_type": chunk.get("chunk_type", "text"),
                "page_num": chunk.get("page_num", 0),
                "section_title": chunk.get("section_title", "")[:500],
                "text": chunk["text"][:8000],
                "embedding": emb.tolist()
            }
            if has_extended_fields:
                elements = _detect_content_elements(chunk["text"])
                record["content_elements"] = json.dumps(elements, ensure_ascii=False)[:1000]
                record["structured_content"] = _extract_structured_content(chunk["text"])[:8000]

            data.append(record)

        client.insert(collection_name=collection_name, data=data)

        # 청크 타입 분포
        chunk_types = {}
        for c in chunks:
            ct = c.get("chunk_type", "text")
            chunk_types[ct] = chunk_types.get(ct, 0) + 1

        wiz.response.status(200,
            filename=filename, doc_id=doc_id,
            total_pages=page_count,
            chunks_count=len(chunks),
            vectors_stored=len(data),
            figures_detected=ext_stats["figures"],
            formulas_detected=ext_stats["formulas"],
            tables_detected=ext_stats["tables"],
            ocr_extractions=ext_stats["ocr_extractions"],
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

        stats_info = client.get_collection_stats(collection_name)
        total_chunks = stats_info.get("row_count", 0)
        total_docs = 0
        if total_chunks > 0:
            try:
                results = client.query(
                    collection_name=collection_name,
                    filter="chunk_index == 0",
                    output_fields=["doc_id"]
                )
                total_docs = len(results)
            except Exception:
                total_docs = 0

        col_meta = meta.get(collection_name, {})
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
