"""
Vision LLM 모듈 — Gemma 4 E4B-IT 기반 이미지 분석
PDF 내 이미지에서 수식(LaTeX), 그래프, 표, 다이어그램 등을 분석합니다.
"""
import json
import torch
import gc
import re

MODEL_ID = "google/gemma-4-E4B-it"
MODEL_CACHE_DIR = "/opt/app/data/models"

# 싱글톤 인스턴스
_model = None
_processor = None
_device = None


def _load_model():
    """모델과 프로세서를 로드 (최초 1회)"""
    global _model, _processor, _device
    if _model is not None:
        return

    from transformers import AutoProcessor, AutoModelForCausalLM

    _processor = AutoProcessor.from_pretrained(
        MODEL_ID, cache_dir=MODEL_CACHE_DIR
    )
    _model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        dtype=torch.bfloat16,
        device_map="auto",
        cache_dir=MODEL_CACHE_DIR,
    )
    _model.eval()
    _device = next(_model.parameters()).device


def _unload_model():
    """모델 메모리 해제"""
    global _model, _processor, _device
    if _model is not None:
        del _model
        _model = None
    if _processor is not None:
        del _processor
        _processor = None
    _device = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _run_inference(image, prompt, max_tokens=1024, token_budget=560):
    """단일 이미지에 대해 추론 실행"""
    _load_model()

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    inputs = _processor.apply_chat_template(
        messages,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
        add_generation_prompt=True,
        enable_thinking=False,
    ).to(_model.device)

    with torch.no_grad():
        output_ids = _model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=1.0,
            top_p=0.95,
            top_k=64,
            do_sample=True,
        )

    # 입력 토큰 이후의 생성된 부분만 디코딩
    input_len = inputs["input_ids"].shape[1]
    generated = output_ids[0][input_len:]
    text = _processor.tokenizer.decode(generated, skip_special_tokens=True)
    return text.strip()


# ==========================================================================
# 공개 API
# ==========================================================================

def classify_image(image):
    """
    이미지 타입 분류: equation, graph, diagram, table, photo, other
    Returns: {"type": str, "confidence": str}
    """
    prompt = """Classify this image into exactly one category.
Categories: equation, graph, diagram, table, photo, other

Respond with ONLY a JSON object:
{"type": "<category>", "confidence": "high|medium|low"}"""

    result = _run_inference(image, prompt, max_tokens=50)
    try:
        # JSON 추출
        start = result.find("{")
        end = result.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(result[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return {"type": "other", "confidence": "low"}


def extract_equation_latex(image):
    """
    수식 이미지에서 LaTeX 추출 (영문/한글 부연 설명 일절 금지)
    Returns: {"latex": str, "description": str}
    """
    prompt = """You are a strict LaTeX transcriber for mathematical equations.

RULES (must follow exactly):
1. Output ONLY a JSON object. No prose, no markdown fences, no preamble.
2. Field "latex": LaTeX source ONLY. NO words, NO English/Korean explanations.
3. Use $ ... $ for inline math; use $$ ... $$ for displayed equations.
4. If multiple equations, separate by a newline; preserve original numbering "(1)", "(2.3)".
5. Preserve subscripts (T_e), superscripts (x^2), fractions (\\frac{a}{b}), integrals (\\int), summations (\\sum), Greek letters (\\alpha, \\Omega), vectors (\\vec{E}), gradients (\\nabla), partials (\\partial).
6. If the image is unreadable or contains no equation, set "latex" to "" (empty string). Do NOT hallucinate.
7. Field "description": at most 8 words naming the equation type (e.g. "Gauss's law", "ODE", "linear system"). Empty if unsure.

Respond with ONLY this JSON:
{"latex": "<LaTeX or empty>", "description": "<<=8 words or empty>"}"""

    result = _run_inference(image, prompt, max_tokens=512, token_budget=1120)
    try:
        start = result.find("{")
        end = result.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(result[start:end])
            # 환각 방지: latex가 사실상 자연어면 비움
            latex = parsed.get("latex", "") or ""
            stripped = latex.strip().strip("`")
            # latex 같지 않은 패턴 (수학 기호 전혀 없음) 차단
            if stripped and not re.search(r"[\\$\^_{}=+\-*/\d]", stripped):
                parsed["latex"] = ""
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    return {"latex": "", "description": ""}


def analyze_graph(image):
    """
    그래프/차트 이미지 분석
    Returns: {"chart_type": str, "axes": str, "trends": str, "key_values": str, "description": str}
    """
    prompt = """Analyze this scientific graph/chart image in detail.

Identify:
1. Chart type (line, bar, scatter, contour, etc.)
2. Axis labels and units
3. Key trends or patterns
4. Notable data points or values
5. Overall description

Respond with ONLY a JSON object:
{"chart_type": "<type>", "axes": "<x-axis and y-axis labels>", "trends": "<key trends>", "key_values": "<notable values>", "description": "<overall description>"}"""

    result = _run_inference(image, prompt, max_tokens=512, token_budget=1120)
    try:
        start = result.find("{")
        end = result.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(result[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return {"chart_type": "", "axes": "", "trends": "", "key_values": "", "description": result}


def analyze_table(image):
    """
    표 이미지를 마크다운 테이블로 변환
    Returns: {"markdown": str, "description": str}
    """
    prompt = """Convert this table image to a Markdown table format.
Preserve all cell values exactly as shown. Use | for column separators.

Respond with ONLY a JSON object:
{"markdown": "<markdown table>", "description": "<brief description of the table>"}"""

    result = _run_inference(image, prompt, max_tokens=1024, token_budget=1120)
    try:
        start = result.find("{")
        end = result.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(result[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return {"markdown": "", "description": result}


def analyze_diagram(image):
    """
    다이어그램/개략도 분석
    Returns: {"description": str, "components": str, "relationships": str}
    """
    prompt = """Analyze this scientific diagram or schematic.

Identify:
1. What the diagram represents
2. Key components or elements
3. Relationships or flows between components

Respond with ONLY a JSON object:
{"description": "<overall description>", "components": "<key components>", "relationships": "<relationships between components>"}"""

    result = _run_inference(image, prompt, max_tokens=512, token_budget=560)
    try:
        start = result.find("{")
        end = result.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(result[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return {"description": result, "components": "", "relationships": ""}


def analyze_image(image):
    """
    이미지를 자동 분류 후 타입에 맞는 분석 수행
    Returns: {"type": str, "marker": str, "detail": dict}
    """
    classification = classify_image(image)
    img_type = classification.get("type", "other")

    if img_type == "equation":
        detail = extract_equation_latex(image)
        latex = (detail.get("latex", "") or "").strip()
        desc = (detail.get("description", "") or "").strip()
        # 인라인($)/디스플레이($$) 자동 판별 — 디스플레이 우선
        if latex:
            if "$$" in latex:
                body = latex
            elif latex.startswith("$") and latex.endswith("$"):
                body = "$$" + latex.strip("$") + "$$"
            else:
                body = "$$" + latex + "$$"
            ctx_part = f" | context: {desc}" if desc else ""
            marker = f"[EQUATION: type=display | {body}{ctx_part}]"
        else:
            marker = f"[EQUATION: {desc}]" if desc else "[EQUATION: (수식)]"
        return {"type": "equation", "marker": marker, "detail": detail}

    elif img_type == "graph":
        detail = analyze_graph(image)
        desc = detail.get("description", "")
        axes = detail.get("axes", "")
        trends = detail.get("trends", "")
        parts = [p for p in [desc, f"Axes: {axes}" if axes else "", f"Trends: {trends}" if trends else ""] if p]
        marker = f"[FIGURE: {' | '.join(parts)}]"
        return {"type": "graph", "marker": marker, "detail": detail}

    elif img_type == "table":
        detail = analyze_table(image)
        md = detail.get("markdown", "")
        if md:
            marker = f"[TABLE:\n{md}\n]"
        else:
            marker = f"[TABLE: {detail.get('description', '(표)')}]"
        return {"type": "table", "marker": marker, "detail": detail}

    elif img_type == "diagram":
        detail = analyze_diagram(image)
        desc = detail.get("description", "")
        marker = f"[DIAGRAM: {desc}]"
        return {"type": "diagram", "marker": marker, "detail": detail}

    else:
        # photo 또는 기타 → 간단한 설명
        prompt = "Describe this image briefly in one or two sentences for a scientific paper context."
        desc = _run_inference(image, prompt, max_tokens=128, token_budget=280)
        marker = f"[FIGURE: {desc}]"
        return {"type": img_type, "marker": marker, "detail": {"description": desc}}


def is_available():
    """Vision LLM 모델 사용 가능 여부 확인"""
    try:
        import os
        # 모델 캐시 존재 확인
        cache_path = os.path.join(MODEL_CACHE_DIR, "models--google--gemma-4-E4B-it")
        if not os.path.exists(cache_path):
            return False
        # GPU 사용 가능 여부
        if not torch.cuda.is_available():
            return False
        return True
    except Exception:
        return False


class VisionLLM:
    """WIZ model 패턴 준수를 위한 래퍼 클래스"""

    def analyze(self, image):
        return analyze_image(image)

    def classify(self, image):
        return classify_image(image)

    def equation(self, image):
        return extract_equation_latex(image)

    def graph(self, image):
        return analyze_graph(image)

    def table(self, image):
        return analyze_table(image)

    def diagram(self, image):
        return analyze_diagram(image)

    def available(self):
        return is_available()

    def load(self):
        _load_model()

    def unload(self):
        _unload_model()


Model = VisionLLM()
