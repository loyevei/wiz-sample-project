# =============================================================================
# Agent Struct — 하이브리드/계층형 에이전트 아키텍처 (OpenAI GPT)
# =============================================================================
# 호출 예시:
#   struct = wiz.model("struct")
#   agent = struct.agent()
#   for event in agent.run("플라즈마 에칭 관련 논문 찾아줘"):
#       print(event)
#
# 아키텍처:
#   Agent (진입점)
#     └─ OrchestratorAgent (최상위 조율)
#          ├─ KeywordAgent     (키워드 추출 + 의도 분류)
#          ├─ RouterAgent      (실행 계획 수립 + 도구 순서 결정)
#          ├─ PatentAgent      (KIPRIS 특허 검색)
#          ├─ CollectorAgent   (페이지 결과 수집 + 문헌 검색)
#          └─ SynthesizerAgent (LLM 기반 최종 답변 생성)
# =============================================================================

import os
import sys
import json
import importlib
import importlib.util


class Agent:
    """에이전트 진입점 — OrchestratorAgent에 위임하는 슬림 래퍼.

    기존 인터페이스(run, get_tools, get_history)를 유지하면서
    내부적으로는 계층형 에이전트 구조로 동작한다.
    """

    MAX_ITERATIONS = 20

    def __init__(self, struct, collection=""):
        self.struct = struct
        self.config = wiz.config("season")
        self.collection = collection or ""

        # LLM 설정 (OpenAI)
        self.api_key = getattr(self.config, "openai_api_key", "")
        self.model = getattr(self.config, "openai_model", "gpt-4o")

        # Tool Context — 모든 Tool/Agent에 주입되는 공유 컨텍스트
        self._tool_context = {
            "wiz": wiz,
            "config": self.config,
            "struct": struct,
            "collection": self.collection,
        }

        self._tools = {}
        self._messages = []
        self._load_tools()

    # =========================================================================
    # Tool Auto-Discovery (기존 도구 로딩 유지)
    # =========================================================================
    def _load_tools(self):
        project_root = wiz.project.fs().abspath()
        tools_dir = None
        for candidate in ["src", "build", "bundle"]:
            path = os.path.join(project_root, candidate,
                                "model", "struct", "agent", "tools")
            if os.path.isdir(path):
                tools_dir = path
                break

        if tools_dir is None:
            return

        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)

        for fname in sorted(os.listdir(tools_dir)):
            if not fname.endswith(".py"):
                continue
            if fname.startswith("_") or fname == "base_tool.py":
                continue

            filepath = os.path.join(tools_dir, fname)
            module_name = fname[:-3]

            try:
                spec = importlib.util.spec_from_file_location(
                    f"agent_tool_{module_name}", filepath)
                mod = importlib.util.module_from_spec(spec)
                mod.wiz = wiz
                spec.loader.exec_module(mod)

                if hasattr(mod, "Tool"):
                    instance = mod.Tool(self._tool_context)
                    if instance.name:
                        self._tools[instance.name] = instance
            except Exception:
                pass

    # =========================================================================
    # OrchestratorAgent 로드 (agents/ 디렉토리에서 동적 로드)
    # =========================================================================
    def _load_orchestrator(self, client):
        """OrchestratorAgent를 동적 로드하여 인스턴스를 반환."""
        project_root = wiz.project.fs().abspath()
        agents_dir = None
        candidate_paths = [
            os.path.join(project_root, "bundle", "src", "model", "struct", "agent", "agents"),
            os.path.join(project_root, "build", "src", "model", "struct", "agent", "agents"),
            os.path.join(project_root, "src", "model", "struct", "agent", "agents"),
            os.path.join(project_root, "bundle", "model", "struct", "agent", "agents"),
            os.path.join(project_root, "build", "model", "struct", "agent", "agents"),
        ]
        for path in candidate_paths:
            if os.path.isdir(path):
                agents_dir = path
                break

        if agents_dir is None:
            return None

        # agents 디렉토리와 상위 디렉토리를 sys.path에 추가
        parent_dir = os.path.dirname(agents_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        if agents_dir not in sys.path:
            sys.path.insert(0, agents_dir)

        try:
            orchestrator_path = os.path.join(agents_dir, "orchestrator_agent.py")
            if not os.path.isfile(orchestrator_path):
                return None

            # 매 요청마다 최신 파일을 다시 읽도록 표준 import 캐시 제거
            for module_name in [
                "base_agent",
                "keyword_agent",
                "router_agent",
                "collector_agent",
                "patent_agent",
                "synthesizer_agent",
                "orchestrator_agent",
            ]:
                if module_name in sys.modules:
                    del sys.modules[module_name]

            # 의존 모듈을 순서대로 로드
            dep_modules = [
                ("base_agent", "base_agent.py"),
                ("keyword_agent", "keyword_agent.py"),
                ("router_agent", "router_agent.py"),
                ("collector_agent", "collector_agent.py"),
                ("patent_agent", "patent_agent.py"),
                ("synthesizer_agent", "synthesizer_agent.py"),
            ]

            loaded_modules = {}
            for mod_name, filename in dep_modules:
                fpath = os.path.join(agents_dir, filename)
                if not os.path.isfile(fpath):
                    return None
                spec = importlib.util.spec_from_file_location(mod_name, fpath)
                mod = importlib.util.module_from_spec(spec)
                mod.wiz = wiz
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)
                loaded_modules[mod_name] = mod

            # orchestrator_agent 로드
            spec = importlib.util.spec_from_file_location(
                "orchestrator_agent", orchestrator_path)
            orch_mod = importlib.util.module_from_spec(spec)
            orch_mod.wiz = wiz
            sys.modules["orchestrator_agent"] = orch_mod
            spec.loader.exec_module(orch_mod)

            OrchestratorAgent = getattr(orch_mod, "OrchestratorAgent", None)
            if OrchestratorAgent is None:
                return None

            # 오케스트레이터 컨텍스트 구성
            ctx = dict(self._tool_context)
            ctx["client"] = client
            ctx["model"] = self.model
            ctx["max_iterations"] = self.MAX_ITERATIONS

            return OrchestratorAgent(ctx)

        except Exception:
            import traceback
            traceback.print_exc()
            return None

    # =========================================================================
    # Agent Run — OrchestratorAgent에 위임
    # =========================================================================
    def run(self, message, history=None):
        """Generator 기반 Agent 실행 루프 — SSE 이벤트를 yield.

        OrchestratorAgent가 전체 흐름을 조율한다:
        1. KeywordAgent  → 키워드 추출 / 의도 분류
        2. RouterAgent   → 실행 계획 수립
        3. PatentAgent   → 특허 검색 (필요 시)
        4. CollectorAgent → 페이지 결과/문헌 수집
        5. SynthesizerAgent → LLM 최종 답변 생성
        """
        if not self.api_key:
            yield {
                "type": "error",
                "message": "OpenAI API key가 설정되지 않았습니다. config/season.py에 openai_api_key를 설정하세요."
            }
            return

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
        except Exception as e:
            yield {"type": "error", "message": f"OpenAI 클라이언트 생성 실패: {str(e)}"}
            return

        # OrchestratorAgent 로드
        orchestrator = self._load_orchestrator(client)
        if orchestrator is None:
            yield {"type": "error", "message": "OrchestratorAgent 로드 실패. agents/ 디렉토리를 확인하세요."}
            return

        # 히스토리 복원
        if history and isinstance(history, list):
            self._messages = list(history)
        else:
            self._messages = []

        # 실행을 OrchestratorAgent에 위임
        try:
            for event in orchestrator.run(
                message=message,
                history=self._messages,
                tools=self._tools,
            ):
                yield event

                # history 이벤트 캡처
                if event.get("type") == "history":
                    self._messages = event.get("messages", self._messages)

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield {
                "type": "error",
                "message": f"Agent 실행 중 오류: {str(e)}"
            }

    # =========================================================================
    # Public API (기존 인터페이스 유지)
    # =========================================================================
    def get_tools(self):
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]

    def get_history(self):
        return list(self._messages)

    def clear_history(self):
        self._messages = []


Model = Agent
