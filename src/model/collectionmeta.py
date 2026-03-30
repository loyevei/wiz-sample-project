import json
import os


class CollectionMeta:
    def normalize_info(self, info):
        if isinstance(info, dict):
            return info
        if isinstance(info, str) and info:
            return {"model": info}
        return {}

    def normalize_meta(self, meta):
        if not isinstance(meta, dict):
            return {}
        return {
            name: self.normalize_info(info)
            for name, info in meta.items()
        }

    def load(self, path):
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            return self.normalize_meta(meta)
        except Exception:
            return {}

    def get_model(self, path, collection_name, default_model):
        meta = self.load(path)
        info = self.normalize_info(meta.get(collection_name, {}))
        return info.get("model", default_model)


Model = CollectionMeta()