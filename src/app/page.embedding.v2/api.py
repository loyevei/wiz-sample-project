import season.lib.exception


def _load_embedding_api_module():
    hotload = wiz.model("hotload")
    return hotload.load_scope("app/page.embedding/api.py", name_prefix="wiz_hot_embedding")


def upload():
    scope = _load_embedding_api_module()
    handler = scope.get("upload")
    if handler is None:
        raise RuntimeError("upload function not found after exec")
    return handler()
