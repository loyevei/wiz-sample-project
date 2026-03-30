import season.lib.exception


def _load_research_api_module():
    hotload = wiz.model("hotload")
    return hotload.load_scope("app/page.research/api.py", name_prefix="wiz_hot_research")


def recommend_papers():
    scope = _load_research_api_module()
    handler = scope.get("recommend_papers")
    if handler is None:
        raise RuntimeError("recommend_papers function not found after exec")
    return handler()


def serve_pdf():
    scope = _load_research_api_module()
    handler = scope.get("serve_pdf")
    if handler is None:
        raise RuntimeError("serve_pdf function not found after exec")
    return handler()
