class ModelRegistry:
    def __init__(self):
        self._full = {
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

    def default_model(self):
        return self._default_model

    def full(self):
        return dict(self._full)

    def compact(self):
        return {
            name: {
                "dim": info.get("dim"),
                "short_name": info.get("short_name"),
            }
            for name, info in self._full.items()
        }

    def infer_model_from_dim(self, dim, default_model=None):
        if default_model is None:
            default_model = self._default_model
        dim_to_model = {}
        for name, info in self._full.items():
            model_dim = info.get("dim")
            if model_dim not in dim_to_model:
                dim_to_model[model_dim] = name
        return dim_to_model.get(dim, default_model)


Model = ModelRegistry()