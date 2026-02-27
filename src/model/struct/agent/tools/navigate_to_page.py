"""
navigate_to_page — 사용자를 4대 연구 기능 페이지로 안내하는 도구
Agent가 분석 완료 후 관련 페이지로 이동하도록 프론트엔드에 지시한다.
"""
import json
from base_tool import BaseTool


class NavigateToPage(BaseTool):
    name = "navigate_to_page"
    description = (
        "Direct the user to a specific research page for interactive exploration. "
        "Call this AFTER completing analysis with other tools. "
        "Maps to: research (주제 발굴), prediction (공정 예측), "
        "diagnosis (진단 분석), theory (이론 연구). "
        "The page will open with pre-filled search parameters."
    )
    parameters = {
        "type": "object",
        "properties": {
            "page": {
                "type": "string",
                "enum": ["research", "prediction", "diagnosis", "theory"],
                "description": "Target page: 'research' (주제 발굴), 'prediction' (공정 예측), 'diagnosis' (진단 분석), 'theory' (이론 연구)"
            },
            "tab": {
                "type": "string",
                "description": (
                    "Tab to activate on the target page. "
                    "research: discover|topicmap|gap|hypothesis|keywords. "
                    "prediction: predict|paramdb|inverse|uncertainty|analysis. "
                    "diagnosis: search|spectrum|multimodal|detection|failure|compare. "
                    "theory: equation|assumption|graph."
                )
            },
            "query": {
                "type": "string",
                "description": "Search keyword or query to pre-fill on the target page"
            },
            "params": {
                "type": "object",
                "description": (
                    "Additional parameters for the target page. Examples: "
                    "prediction: {process_type, gas_type, pressure, power}. "
                    "diagnosis: {diagType, symptom, methodA, methodB}. "
                    "theory: {equationQuery, graphSearchQuery}."
                ),
                "additionalProperties": True
            }
        },
        "required": ["page"]
    }

    # 페이지별 기본 탭 및 URL 매핑
    PAGE_CONFIG = {
        "research": {
            "url": "/research",
            "default_tab": "discover",
            "title_ko": "주제 발굴",
            "title_en": "Research Discovery",
            "tabs": ["discover", "topicmap", "gap", "hypothesis", "keywords"]
        },
        "prediction": {
            "url": "/prediction",
            "default_tab": "predict",
            "title_ko": "공정 예측",
            "title_en": "Process Prediction",
            "tabs": ["predict", "paramdb", "inverse", "uncertainty", "analysis"]
        },
        "diagnosis": {
            "url": "/diagnosis",
            "default_tab": "search",
            "title_ko": "진단 분석",
            "title_en": "Diagnostics Analysis",
            "tabs": ["search", "spectrum", "multimodal", "detection", "failure", "compare"]
        },
        "theory": {
            "url": "/theory",
            "default_tab": "equation",
            "title_ko": "이론 연구",
            "title_en": "Theory Analysis",
            "tabs": ["equation", "assumption", "graph"]
        }
    }

    def execute(self, page: str, tab: str = "", query: str = "", params: dict = None) -> str:
        if page not in self.PAGE_CONFIG:
            return json.dumps({
                "error": f"Unknown page: {page}. Must be one of: research, prediction, diagnosis, theory"
            }, ensure_ascii=False)

        config = self.PAGE_CONFIG[page]
        effective_tab = tab if tab and tab in config["tabs"] else config["default_tab"]

        # URL 쿼리 파라미터 구성
        query_params = {}
        if effective_tab:
            query_params["tab"] = effective_tab
        if query:
            query_params["q"] = query
        if params:
            for k, v in params.items():
                if v is not None and str(v).strip():
                    query_params[k] = str(v)

        # URL 구성
        url = config["url"]
        if query_params:
            qs = "&".join(f"{k}={v}" for k, v in query_params.items())
            url = f"{url}?{qs}"

        result = {
            "action": "navigate",
            "page": page,
            "url": url,
            "tab": effective_tab,
            "query": query,
            "params": params or {},
            "title_ko": config["title_ko"],
            "title_en": config["title_en"]
        }

        return json.dumps(result, ensure_ascii=False)


Tool = NavigateToPage
