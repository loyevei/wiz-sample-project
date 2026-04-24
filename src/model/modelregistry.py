import os
import json

CUSTOM_MODELS_PATH = "/opt/app/data/custom_models.json"

class ModelRegistry:
    def __init__(self):
        self._builtin = {
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
        self._default_model = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"
        self._custom = self._load_custom()

    # =========================================================================
    # 커스텀 모델 영속화
    # =========================================================================
    def _load_custom(self):
        if os.path.exists(CUSTOM_MODELS_PATH):
            try:
                with open(CUSTOM_MODELS_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_custom(self):
        os.makedirs(os.path.dirname(CUSTOM_MODELS_PATH), exist_ok=True)
        with open(CUSTOM_MODELS_PATH, "w", encoding="utf-8") as f:
            json.dump(self._custom, f, ensure_ascii=False, indent=2)

    # =========================================================================
    # 공개 API
    # =========================================================================
    def default_model(self):
        return self._default_model

    def full(self):
        merged = dict(self._builtin)
        merged.update(self._custom)
        return merged

    def compact(self):
        return {
            name: {
                "dim": info.get("dim"),
                "short_name": info.get("short_name"),
            }
            for name, info in self.full().items()
        }

    def infer_model_from_dim(self, dim, default_model=None):
        if default_model is None:
            default_model = self._default_model
        dim_to_model = {}
        for name, info in self.full().items():
            model_dim = info.get("dim")
            if model_dim not in dim_to_model:
                dim_to_model[model_dim] = name
        return dim_to_model.get(dim, default_model)

    def add_model(self, name, dim, description="", lang="multi", short_name="", max_seq_length=512):
        """커스텀 모델 등록 (영속 저장)"""
        if not short_name:
            short_name = name.split("/")[-1] if "/" in name else name
        info = {
            "name": name,
            "dim": dim,
            "description": description,
            "lang": lang,
            "short_name": short_name,
            "max_seq_length": max_seq_length,
            "custom": True
        }
        self._custom[name] = info
        self._save_custom()
        return info

    def remove_model(self, name):
        """커스텀 모델 삭제 (빌트인은 삭제 불가)"""
        if name in self._builtin:
            raise ValueError(f"빌트인 모델 '{name}'은 삭제할 수 없습니다.")
        if name not in self._custom:
            raise ValueError(f"모델 '{name}'을 찾을 수 없습니다.")
        del self._custom[name]
        self._save_custom()

    def is_custom(self, name):
        return name in self._custom


Model = ModelRegistry()