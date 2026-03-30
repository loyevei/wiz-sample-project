# =============================================================================
# KeywordAgent — 키워드 추출 + 의도 분류 + 파라미터 매핑
# =============================================================================
# 역할: 사용자 질문을 분석하여 카테고리, 대상 페이지/탭, 키워드, 파라미터를 결정
# =============================================================================

import re

try:
    from .base_agent import BaseAgent
except ImportError:
    from base_agent import BaseAgent


class KeywordAgent(BaseAgent):
    name = "keyword"
    description = "사용자 질문에서 키워드를 추출하고, 의도를 분류하며, 페이지 파라미터를 매핑합니다."

    # =========================================================================
    # 의도 분류 규칙
    # =========================================================================
    def _classify_intent(self, message):
        """규칙 기반 의도 분류 → (category, page, tab, recommended_tools)"""
        q = (message or "").strip().lower()

        # 논문 추천/검색 우선
        paper_intent = (
            any(k in q for k in ["논문", "paper", "papers", "publication", "journal", "arxiv"])
            and any(k in q for k in ["찾아", "검색", "추천", "리스트", "목록", "latest", "recent", "최신", "추천해"])
        )
        if paper_intent:
            return "논문 추천", "research", "recommend", ["read_page_results", "navigate_to_page"]

        # 특허 검색은 공정/식각 키워드가 함께 있어도 KIPRIS 우선 흐름으로 분류
        if any(kw in q for kw in ["특허", "patent", "kipris", "출원", "등록번호"]):
            return "특허 검색", "research", "patent", ["read_page_results", "navigate_to_page"]

        if any(kw in q for kw in ["그래프", "차트", "통계", "피팅", "scatter", "plot"]):
            return "데이터 분석", "analysis", "plotter", ["navigate_to_page"]
        if any(kw in q for kw in ["실험", "doe", "레시피", "노트"]):
            return "실험 관리", "experiment", "doe", ["navigate_to_page"]
        if any(kw in q for kw in ["디바이", "paschen", "자이로", "계산", "주파수"]):
            return "플라즈마 계산기", "calculator", "plasma", ["navigate_to_page"]
        if any(kw in q for kw in ["수식", "방정식", "가정", "theory", "이론", "boltzmann"]):
            return "이론 연구", "theory", "equation", ["read_page_results", "search_equations", "build_theory_graph", "navigate_to_page"]
        if any(kw in q for kw in ["비교", "compare"]) and any(kw in q for kw in ["oes", "랭뮤어", "probe", "진단"]):
            return "진단 분석", "diagnosis", "compare", ["read_page_results", "compare_diagnostics", "search_papers", "navigate_to_page"]
        if any(kw in q for kw in ["고장", "원인", "해결", "증상", "아킹", "불안정", "반사", "파티클"]):
            return "진단 분석", "diagnosis", "failure", ["read_page_results", "failure_reasoning", "search_anomaly", "navigate_to_page"]
        if any(kw in q for kw in ["oes", "랭뮤어", "진단", "스펙트럼", "이상"]):
            return "진단 분석", "diagnosis", "detection", ["read_page_results", "search_papers", "compare_diagnostics", "navigate_to_page"]
        if any(kw in q for kw in ["예측", "etch", "식각", "증착", "rf", "pressure", "power", "icp"]):
            return "공정 예측", "prediction", "predict", ["read_page_results", "search_papers", "predict_process", "navigate_to_page"]
        if any(kw in q for kw in ["프로젝트", "협업", "토론", "activity", "공유"]):
            return "협업", "collaboration", "projects", ["navigate_to_page"]

        return "주제 발굴", "research", "discover", ["read_page_results", "search_papers", "navigate_to_page"]

    # =========================================================================
    # 키워드 추출
    # =========================================================================
    def _extract_keywords(self, message):
        text = (message or "").strip()
        keywords = [w.strip() for w in text.replace(",", " ").split() if len(w.strip()) > 1][:5]
        if not keywords and text:
            keywords = [text[:24]]
        return keywords

    # =========================================================================
    # 파라미터 매핑
    # =========================================================================
    def _extract_params(self, message, page, tab):
        """질문에서 페이지별 파라미터를 추출."""
        text = (message or "").strip()
        q = text.lower()
        params = {}

        # 공통 추출기
        gas = self._extract_gas(q)
        pressure = self._find_number_unit(q, [r"(\d+(?:\.\d+)?)\s*mtorr", r"(\d+(?:\.\d+)?)\s*torr"])
        power = self._find_number_unit(q, [r"(\d+(?:\.\d+)?)\s*w\b", r"(\d+(?:\.\d+)?)\s*kw\b"])
        tev = self._find_number_unit(q, [r"(\d+(?:\.\d+)?)\s*ev", r"te\s*(\d+(?:\.\d+)?)"])
        density_match = re.search(r"(\d+(?:\.\d+)?e[+\-]?\d+)", q)
        temperature = self._find_number_unit(q, [r"(\d+(?:\.\d+)?)\s*°c", r"(\d+(?:\.\d+)?)\s*c\b", r"(\d+(?:\.\d+)?)\s*k\b"])
        time_value = self._find_number_unit(q, [r"(\d+(?:\.\d+)?)\s*min", r"(\d+(?:\.\d+)?)\s*s(ec)?\b"])
        bfield = self._find_number_unit(q, [r"(\d+(?:\.\d+)?)\s*t\b", r"b\s*=\s*(\d+(?:\.\d+)?)"])
        chart_type = self._extract_chart_type(q)
        fitting_model = self._extract_fitting_model(q)
        diag_methods = self._extract_diag_methods(q)

        if page == "diagnosis" and tab == "failure":
            params["symptom"] = text[:80]
        elif page == "diagnosis" and tab == "compare":
            if len(diag_methods) > 0:
                params["methodA"] = diag_methods[0]
            if len(diag_methods) > 1:
                params["methodB"] = diag_methods[1]
            elif "비교" in text and "methodA" in params:
                params["methodB"] = "Langmuir probe" if params["methodA"] != "Langmuir probe" else "OES"
        elif page == "diagnosis":
            if diag_methods:
                params["diagType"] = diag_methods[0]
        elif page == "prediction":
            if gas: params["gas_type"] = gas
            if pressure: params["pressure"] = pressure
            if power: params["power"] = power
            if temperature: params["temperature"] = temperature
            if "etch" in q or "식각" in text:
                params["process_type"] = "ICP etching" if "icp" in q else "etching"
            elif "증착" in text or "deposition" in q or "pecvd" in q:
                params["process_type"] = "PECVD deposition" if "pecvd" in q else "deposition"
            if "식각속도" in text or "etch rate" in q:
                params["target_property"] = "etch_rate"
        elif page == "calculator":
            if tev: params["Te"] = tev
            if density_match: params["ne"] = density_match.group(1)
            if gas: params["gas"] = gas
            if pressure: params["pressure"] = pressure
            if bfield: params["B"] = bfield
        elif page == "analysis":
            if chart_type: params["chart_type"] = chart_type
            if fitting_model: params["fitting_model"] = fitting_model
        elif page == "experiment":
            if gas: params["gas"] = gas
            if pressure: params["pressure"] = pressure
            if power: params["power"] = power
            if temperature: params["temperature"] = temperature
            if time_value: params["time"] = time_value
        elif page == "research" and tab == "proposal":
            keywords = self._extract_keywords(text)
            params["title"] = text[:32]
            params["keywords"] = ", ".join(keywords[:3])

        return params

    # =========================================================================
    # 유틸리티
    # =========================================================================
    def _find_number_unit(self, text, patterns):
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def _extract_gas(self, text):
        gas_map = {
            "argon": "Ar", "아르곤": "Ar", "ar": "Ar",
            "nitrogen": "N2", "질소": "N2", "n2": "N2",
            "oxygen": "O2", "산소": "O2", "o2": "O2",
            "cf4": "CF4", "sf6": "SF6", "cl2": "Cl2", "hbr": "HBr",
            "helium": "He", "헬륨": "He", "he": "He",
        }
        for key, value in gas_map.items():
            if key in text:
                return value
        return None

    def _extract_diag_methods(self, text):
        methods = []
        method_map = [
            ("oes", "OES"), ("랭뮤어", "Langmuir probe"), ("langmuir", "Langmuir probe"),
            ("vi probe", "VI probe"), ("mass", "Mass spectrometry"), ("xps", "XPS"), ("sem", "SEM"),
        ]
        for key, label in method_map:
            if key in text and label not in methods:
                methods.append(label)
        return methods[:2]

    def _extract_chart_type(self, text):
        chart_map = [
            (["scatter", "산점도"], "scatter"), (["heatmap", "히트맵"], "heatmap"),
            (["histogram", "히스토그램"], "histogram"), (["line", "선 그래프"], "line"),
            (["bar", "막대"], "bar"), (["pie", "파이차트"], "pie"),
        ]
        for keys, value in chart_map:
            if any(k in text for k in keys):
                return value
        return None

    def _extract_fitting_model(self, text):
        fitting_map = [
            (["linear", "선형"], "linear"), (["quadratic", "이차"], "quadratic"),
            (["exponential", "지수"], "exponential"), (["gaussian", "가우시안"], "gaussian"),
        ]
        for keys, value in fitting_map:
            if any(k in text for k in keys):
                return value
        return None

    def _detect_language(self, message):
        if re.search(r"[가-힣]", message or ""):
            return "ko"
        return "en"

    def _detect_difficulty(self, message):
        score = [
            any(ch.isdigit() for ch in (message or "")),
            len((message or "").strip()) > 30,
            bool(re.search(r"비교|예측|가설|분석|추론|recommend|predict", message or "", re.IGNORECASE)),
        ]
        count = len([s for s in score if s])
        if count >= 3: return "심층 분석"
        if count == 2: return "표준 분석"
        return "빠른 응답"

    # =========================================================================
    # run: 메인 실행
    # =========================================================================
    def run(self, message="", **kwargs):
        """키워드 추출 + 의도 분류 + 파라미터 매핑 → 통합 결과 dict 반환."""
        category, page, tab, recommended_tools = self._classify_intent(message)
        keywords = self._extract_keywords(message)
        params = self._extract_params(message, page, tab)
        language = self._detect_language(message)
        difficulty = self._detect_difficulty(message)

        return {
            "category": category,
            "page": page,
            "tab": tab,
            "keywords": keywords,
            "params": params,
            "recommended_tools": recommended_tools,
            "language": language,
            "difficulty": difficulty,
            "query": " ".join(keywords[:2]).strip() or (message or "").strip()[:48],
        }
