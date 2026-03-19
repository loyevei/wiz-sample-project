"""
navigate_to_page — 사용자를 4대 연구 기능 페이지로 안내하는 도구
Agent가 분석 완료 후 관련 페이지로 이동하도록 프론트엔드에 지시한다.
"""
import json
from urllib.parse import quote
from base_tool import BaseTool


class NavigateToPage(BaseTool):
    name = "navigate_to_page"
    description = (
        "Direct the user to a specific research/tool page for interactive exploration. "
        "Call this AFTER completing analysis with other tools. "
        "Maps to 8 categories: research (주제 발굴), prediction (공정 예측), "
        "diagnosis (진단 분석), theory (이론 연구), calculator (플라즈마 계산기), "
        "experiment (실험 관리), analysis (데이터 분석), collaboration (협업). "
        "The page will open with pre-filled search parameters."
    )
    parameters = {
        "type": "object",
        "properties": {
            "page": {
                "type": "string",
                "enum": ["research", "prediction", "diagnosis", "theory",
                         "calculator", "experiment", "analysis", "collaboration"],
                "description": (
                    "Target page: 'research' (주제 발굴), 'prediction' (공정 예측), "
                    "'diagnosis' (진단 분석), 'theory' (이론 연구), "
                    "'calculator' (플라즈마 계산기), 'experiment' (실험 관리), "
                    "'analysis' (데이터 분석), 'collaboration' (협업)"
                )
            },
            "tab": {
                "type": "string",
                "description": (
                    "Tab to activate on the target page. "
                    "research: discover|topicmap|gap|hypothesis|keywords|recommend|proposal|patent. "
                    "prediction: predict|paramdb|inverse|uncertainty|analysis. "
                    "diagnosis: search|spectrum|multimodal|detection|failure|compare. "
                    "theory: equation|assumption|graph. "
                    "calculator: plasma|units|constants|equations|paschen|gasdb|equipment. "
                    "experiment: doe|notebook|recipe. "
                    "analysis: plotter|statistics|fitting|dashboard. "
                    "collaboration: projects|discussions|activity."
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
                    "theory: {equationQuery, graphSearchQuery}. "
                    "calculator: {Te (eV), ne (m^-3), gas, pressure (mTorr), B (T)}. "
                    "analysis: {chart_type, csv_data}. "
                    "experiment: {gas, pressure, power, temperature, time}."
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
            "tabs": ["discover", "topicmap", "gap", "hypothesis", "keywords", "recommend", "proposal", "patent"]
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
        },
        "calculator": {
            "url": "/calculator",
            "default_tab": "plasma",
            "title_ko": "플라즈마 계산기",
            "title_en": "Plasma Calculator",
            "tabs": ["plasma", "units", "constants", "equations", "paschen", "gasdb", "equipment"]
        },
        "experiment": {
            "url": "/experiment",
            "default_tab": "doe",
            "title_ko": "실험 관리",
            "title_en": "Experiment Management",
            "tabs": ["doe", "notebook", "recipe"]
        },
        "analysis": {
            "url": "/analysis",
            "default_tab": "plotter",
            "title_ko": "데이터 분석",
            "title_en": "Data Analysis",
            "tabs": ["plotter", "statistics", "fitting", "dashboard"]
        },
        "collaboration": {
            "url": "/collaboration",
            "default_tab": "projects",
            "title_ko": "협업",
            "title_en": "Collaboration",
            "tabs": ["projects", "discussions", "activity"]
        }
    }

    def execute(self, page: str, tab: str = "", query: str = "", params: dict = None) -> str:
        if page not in self.PAGE_CONFIG:
            return json.dumps({
                "error": f"Unknown page: {page}. Must be one of: research, prediction, diagnosis, theory"
            }, ensure_ascii=False)

        config = self.PAGE_CONFIG[page]
        effective_tab = tab if tab and tab in config["tabs"] else config["default_tab"]
        ctx_collection = self.ctx.get("collection", "")
        merged_params = dict(params or {})
        if ctx_collection and not merged_params.get("collection"):
            merged_params["collection"] = ctx_collection

        # URL 쿼리 파라미터 구성
        query_params = {}
        if effective_tab:
            query_params["tab"] = effective_tab
        if query:
            query_params["q"] = query

        if merged_params:
            for k, v in merged_params.items():
                if v is not None and str(v).strip():
                    query_params[k] = str(v)

        # URL 구성 (값에 URL 인코딩 적용)
        url = config["url"]
        if query_params:
            qs = "&".join(f"{k}={quote(str(v), safe='')}" for k, v in query_params.items())
            url = f"{url}?{qs}"

        result = {
            "action": "navigate",
            "page": page,
            "url": url,
            "tab": effective_tab,
            "query": query,
            "params": merged_params,
            "collection": merged_params.get("collection", ""),
            "title_ko": config["title_ko"],
            "title_en": config["title_en"]
        }

        return json.dumps(result, ensure_ascii=False)


Tool = NavigateToPage
