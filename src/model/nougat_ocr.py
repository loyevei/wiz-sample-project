import gc
import os
import re
import sys
import types

import fitz

MODEL_ID = os.environ.get("NOUGAT_MODEL_ID", "facebook/nougat-small")
MODEL_CACHE_DIR = "/opt/app/data/models"

# WIZ exec() 환경에서 요청 간 모델 상태를 유지하기 위해 sys.modules에 영속 캐시 사용
_CACHE_KEY = '_nougat_ocr_state'
if _CACHE_KEY not in sys.modules:
    _ns = types.ModuleType(_CACHE_KEY)
    _ns.model = None
    _ns.processor = None
    _ns.device = None
    sys.modules[_CACHE_KEY] = _ns
_state = sys.modules[_CACHE_KEY]


def _resolve_dtype(torch):
    if not torch.cuda.is_available():
        return torch.float32
    try:
        if torch.cuda.is_bf16_supported():
            return torch.bfloat16
    except Exception:
        pass
    return torch.float16


def _load_model():
    if _state.model is not None and _state.processor is not None:
        return

    import torch
    from transformers import NougatProcessor, VisionEncoderDecoderModel

    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

    _state.processor = NougatProcessor.from_pretrained(
        MODEL_ID,
        cache_dir=MODEL_CACHE_DIR,
    )
    _state.model = VisionEncoderDecoderModel.from_pretrained(
        MODEL_ID,
        cache_dir=MODEL_CACHE_DIR,
        torch_dtype=_resolve_dtype(torch),
    )
    _state.device = "cuda:0" if torch.cuda.is_available() else "cpu"
    _state.model = _state.model.to(_state.device)
    _state.model.eval()


def _unload_model():
    if _state.model is not None:
        del _state.model
        _state.model = None
    if _state.processor is not None:
        del _state.processor
        _state.processor = None
    _state.device = None

    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    gc.collect()


def _pixmap_to_image(pix):
    from PIL import Image

    mode = "RGB"
    if getattr(pix, "alpha", 0):
        mode = "RGBA"
    return Image.frombytes(mode, [pix.width, pix.height], pix.samples)


def _page_to_image(page, dpi=150):
    zoom = max(float(dpi or 150) / 72.0, 1.0)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return _pixmap_to_image(pix)


def _normalize_text(text):
    text = (text or "").replace("<pad>", " ").replace("</s>", " ").strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def _post_process_text(text):
    if _state.processor is None:
        return _normalize_text(text)

    processed = text
    try:
        processed = _state.processor.post_process_generation(text, fix_markdown=False)
    except TypeError:
        try:
            processed = _state.processor.post_process_generation(text)
        except Exception:
            processed = text
    except Exception:
        processed = text

    if isinstance(processed, dict):
        processed = processed.get("text") or processed.get("predictions") or text
    if isinstance(processed, (list, tuple)):
        processed = processed[0] if len(processed) > 0 else text

    return _normalize_text(str(processed or ""))


def _decode_images(images, max_new_tokens=2048):
    if not images:
        return []

    import torch

    _load_model()
    inputs = _state.processor(images=images, return_tensors="pt")
    pixel_values = inputs.pixel_values.to(_state.device)

    bad_words_ids = None
    unk_id = getattr(_state.processor.tokenizer, "unk_token_id", None)
    if unk_id is not None:
        bad_words_ids = [[unk_id]]

    with torch.no_grad():
        outputs = _state.model.generate(
            pixel_values,
            min_length=1,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            bad_words_ids=bad_words_ids,
            early_stopping=True,
        )

    decoded = _state.processor.batch_decode(outputs, skip_special_tokens=True)
    return [_post_process_text(text) for text in decoded]


def extract_document(pdf_path, dpi=150, batch_size=2, max_pages=0):
    doc = fitz.open(pdf_path)
    try:
        total_pages = len(doc)
        if max_pages and int(max_pages) > 0:
            total_pages = min(total_pages, int(max_pages))

        batch_size = max(int(batch_size or 1), 1)
        pages = []
        for start in range(0, total_pages, batch_size):
            batch_images = []
            batch_page_nums = []
            end = min(start + batch_size, total_pages)

            for index in range(start, end):
                page = doc.load_page(index)
                batch_images.append(_page_to_image(page, dpi=dpi))
                batch_page_nums.append(index + 1)

            texts = _decode_images(batch_images)
            for page_num, text in zip(batch_page_nums, texts):
                pages.append({
                    "page_num": page_num,
                    "text": text,
                })

        full_text = "\n\n".join(
            page.get("text", "") for page in pages if page.get("text", "").strip()
        )
        return {
            "model": MODEL_ID,
            "page_count": len(pages),
            "pages": pages,
            "full_text": full_text,
        }
    finally:
        doc.close()


def is_available():
    try:
        import torch  # noqa: F401
        from transformers import NougatProcessor, VisionEncoderDecoderModel  # noqa: F401
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        return False


class NougatOCR:
    def available(self):
        return is_available()

    def load(self):
        _load_model()

    def unload(self):
        _unload_model()

    def status(self):
        return {
            "available": is_available(),
            "loaded": _state.model is not None,
            "model": MODEL_ID,
            "runtime": "transformers",
        }

    def extract_document(self, pdf_path, dpi=150, batch_size=2, max_pages=0):
        return extract_document(pdf_path, dpi=dpi, batch_size=batch_size, max_pages=max_pages)


Model = NougatOCR()