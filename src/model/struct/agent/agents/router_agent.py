# =============================================================================
# RouterAgent — 도구 실행 계획 및 페이지 라우팅
# =============================================================================
# 역할: KeywordAgent 결과를 받아 실행 계획(plan)을 수립하고,
#        목표 페이지/탭에 맞는 도구 실행 순서를 결정
# =============================================================================

try:
    from .base_agent import BaseAgent
except ImportError:
    from base_agent import BaseAgent


class RouterAgent(BaseAgent):
    name = "router"
    description = "키워드 분류 결과를 기반으로 실행 계획(plan)을 수립하고 도구 실행 순서를 결정합니다."

    # 클러스터 정의 (기존 5-Cluster 체계 유지)
    AGENT_CLUSTERS = [
        {"name": "planner", "role": "질문 분류, 목표 정의, 다음 액션 결정"},
        {"name": "retriever", "role": "페이지 결과와 검색 근거 수집"},
        {"name": "analyst", "role": "비교·예측·추론 등 후속 분석"},
        {"name": "synthesizer", "role": "근거를 최종 한국어 답변으로 재구성"},
        {"name": "navigator", "role": "페이지 handoff와 후속 실행 연결"},
    ]

    def run(self, classification=None, **kwargs):
        """실행 계획을 수립한다.

        Args:
            classification: KeywordAgent가 반환한 분류 결과 dict.

        Returns:
            orchestrator_plan dict (기존 _build_orchestrator_plan 호환).
        """
        classification = classification or {}
        category = classification.get("category", "주제 발굴")
        page = classification.get("page", "research")
        tab = classification.get("tab", "discover")
        keywords = classification.get("keywords", [])
        recommended_tools = classification.get("recommended_tools", [])

        goal = f"{page}/{tab} 결과를 근거로 최종답변과 handoff를 완성"
        plan = [
            "Planner가 질문을 분류하고 응답 언어와 최종 목표를 고정합니다.",
            "Retriever가 선택 컬렉션과 페이지 파라미터를 맞춰 실제 페이지 결과를 먼저 읽습니다.",
            "필요하면 Analyst가 검색·비교·예측·추론 도구로 부족한 근거를 보강합니다.",
            "Synthesizer가 페이지 결과와 근거를 합쳐 최종 답변을 재구성합니다.",
            "Navigator가 목표 페이지 handoff를 준비하고 목표 달성 여부를 다시 점검합니다.",
        ]

        return {
            "category": category,
            "page": page,
            "tab": tab,
            "keywords": keywords,
            "goal": goal,
            "agent_clusters": list(self.AGENT_CLUSTERS),
            "recommended_tools": recommended_tools,
            "plan": plan,
            "params": classification.get("params", {}),
            "query": classification.get("query", ""),
            "language": classification.get("language", "ko"),
            "difficulty": classification.get("difficulty", "빠른 응답"),
        }
