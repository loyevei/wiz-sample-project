# =============================================================================
# Agent Struct — Tool-Use 기반 AI Agent (OpenAI GPT)
# =============================================================================
# 호출 예시:
#   struct = wiz.model("struct")
#   agent = struct.agent()
#   for event in agent.run("플라즈마 에칭 관련 논문 찾아줘"):
#       print(event)
# =============================================================================

import os
import sys
import json
import importlib
import importlib.util
import traceback

class Agent:
    MAX_ITERATIONS = 20

    def __init__(self, struct):
        self.struct = struct
        self.config = wiz.config("season")

        # LLM 설정 (OpenAI)
        self.api_key = getattr(self.config, "openai_api_key", "")
        self.model = getattr(self.config, "openai_model", "gpt-4o")

        # Tool Context — 모든 Tool에 주입되는 공유 컨텍스트
        self._tool_context = {
            "config": self.config,
            "struct": struct,
        }

        self._tools = {}
        self._messages = []
        self._load_tools()

    # =========================================================================
    # Tool Auto-Discovery
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
                spec.loader.exec_module(mod)

                if hasattr(mod, "Tool"):
                    instance = mod.Tool(self._tool_context)
                    if instance.name:
                        self._tools[instance.name] = instance
            except Exception:
                pass

    # =========================================================================
    # System Prompt
    # =========================================================================
    def _build_system_prompt(self):
        tool_descs = []
        for t in self._tools.values():
            tool_descs.append(f"- **{t.name}**: {t.description}")
        tool_list = "\n".join(tool_descs) if tool_descs else "none"

        return f"""You are an expert AI research assistant specialized in plasma science and engineering.
You have access to a vector database of plasma research papers and powerful analysis tools.

## CRITICAL: Language Rule
**You MUST detect the language of the user's message and respond in EXACTLY the same language.**
- If the user writes in Korean → respond entirely in Korean
- If the user writes in English → respond entirely in English
- If the user mixes languages → respond in the dominant language
- This rule applies to ALL responses including tool result summaries

## Available Tools
{tool_list}

## 4대 핵심 기능 영역 & 도구 조합 가이드

### 1. 주제 발굴 (Research Discovery) → Page: /research
사용자가 새로운 연구 주제, 트렌드, 공백을 탐색할 때:
- 기본 검색: `search_papers` → 관련 논문 탐색
- 주제 추천: `recommend_topics` → 교차 주제 / 연구 공백 / 확장 방향 추천
- 공백 탐지: `detect_research_gaps` → 키워드 밀도 분석으로 미개척 영역 발견
- 가설 생성: `generate_hypothesis` → 템플릿 기반 연구 가설 자동 생성
- 키워드 분석: `analyze_keywords` → 주요 용어 빈도 분석
- 조합 예시: search_papers → recommend_topics → generate_hypothesis

### 2. 공정 예측 (Process Prediction) → Page: /prediction
사용자가 공정 조건/결과를 예측하거나 파라미터를 분석할 때:
- 조건 기반 검색: `predict_process` → 공정 조건으로 유사 문헌 + 파라미터 추출
- 파라미터 효과: `analyze_parameter_effect` → 특정 파라미터의 효과 분석
- 역탐색: `inverse_search` → 목표 결과에서 조건 범위 역추적
- 수치 예측: `surrogate_predict` → Ridge 회귀 기반 결과 예측 + 신뢰구간
- 조합 예시: predict_process → surrogate_predict

### 3. 진단 분석 (Diagnostics Analysis) → Page: /diagnosis
사용자가 플라즈마 진단 방법, 이상 현상, 고장을 분석할 때:
- 진단 비교: `compare_diagnostics` → 두 진단 방법의 키워드/문헌 비교
- 이상 검색: `search_anomaly` → 이상 현상/고장 증상 관련 문헌 검색
- 고장 추론: `failure_reasoning` → 증상 기반 원인-해결 추론
- 조합 예시: compare_diagnostics → search_papers

### 4. 이론 연구 (Theory Analysis) → Page: /theory
사용자가 수식, 가정, 이론적 관계를 분석할 때:
- 수식 추출: `extract_equations` → 전체 문서에서 수식 추출 + 도메인 분류
- 수식 검색: `search_equations` → 특정 수식/공식 관련 문서 검색
- 가정 분석: `extract_assumptions` → 이론적 가정 추출 + 상충 검사
- 이론 그래프: `build_theory_graph` → Knowledge Graph + 영향 추적
- 조합 예시: extract_equations → extract_assumptions → build_theory_graph

## Page Navigation (IMPORTANT)
After completing your analysis using tools, you MUST call the `navigate_to_page` tool to direct the user to the relevant research page where they can explore results interactively. This is mandatory for any domain-specific question.

**Page mapping:**
- Research Discovery questions → `navigate_to_page` with page="research"
- Process Prediction questions → `navigate_to_page` with page="prediction"
- Diagnostics Analysis questions → `navigate_to_page` with page="diagnosis"
- Theory Analysis questions → `navigate_to_page` with page="theory"

Always call `navigate_to_page` as the LAST tool call in your workflow, after all analysis tools have completed.

## Workflow
1. **Understand** the user's research question — determine which of the 4 domains it falls into
2. **Select tools** based on the domain and specific need
3. **Execute** tools in logical order (search first, then analyze)
4. **Synthesize** results into a clear, actionable answer (in the user's language)
5. **Navigate** — call `navigate_to_page` to direct the user to the relevant page

## Guidelines
- Always search the database first before answering domain-specific questions
- When presenting search results, summarize key findings rather than just listing documents
- Include relevant paper titles and key details when referencing specific documents
- For equation queries, present equations in LaTeX format when available
- If the user asks about a topic not in the database, clearly state that and provide general knowledge
- **ALWAYS respond in the same language as the user's message**
- Be concise but thorough — provide actionable research insights
- When comparing topics, use multiple searches to gather comprehensive data
- For process prediction, extract and present numerical parameters clearly
- For diagnostics, clearly distinguish between different methods and their characteristics

## Domain Knowledge
You specialize in: plasma etching, deposition (CVD, PVD, ALD, PECVD), sputtering, OES diagnostics, Langmuir probes, plasma modeling/simulation, semiconductor processing, thin films, surface treatment, atmospheric/vacuum plasma, fusion plasma, and related fields.
"""

    # =========================================================================
    # Agent Run Loop (OpenAI Function Calling)
    # =========================================================================
    def run(self, message, history=None):
        """Generator 기반 Agent 실행 루프 — SSE 이벤트를 yield"""
        if not self.api_key:
            yield {"type": "error", "message": "OpenAI API key가 설정되지 않았습니다. config/season.py에 openai_api_key를 설정하세요."}
            return

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
        except Exception as e:
            yield {"type": "error", "message": f"OpenAI 클라이언트 생성 실패: {str(e)}"}
            return

        system_prompt = self._build_system_prompt()
        tool_schemas = self._get_openai_tools()

        # History 복원
        if history and isinstance(history, list):
            self._messages = list(history)
        else:
            self._messages = []

        # System message가 없으면 추가
        if not self._messages or self._messages[0].get("role") != "system":
            self._messages.insert(0, {"role": "system", "content": system_prompt})

        # 새 user message 추가
        self._messages.append({"role": "user", "content": message})

        iteration = 0
        while iteration < self.MAX_ITERATIONS:
            iteration += 1

            # LLM API 호출
            try:
                api_kwargs = {
                    "model": self.model,
                    "messages": self._messages,
                    "max_tokens": 8192,
                }
                if tool_schemas:
                    api_kwargs["tools"] = tool_schemas
                    api_kwargs["tool_choice"] = "auto"

                response = client.chat.completions.create(**api_kwargs)
            except Exception as e:
                yield {"type": "error", "message": f"LLM API 호출 실패: {str(e)}"}
                return

            choice = response.choices[0]
            msg = choice.message

            # assistant message를 히스토리에 저장
            assistant_msg = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ]
            self._messages.append(assistant_msg)

            # 텍스트 응답이 있으면 yield
            if msg.content:
                yield {"type": "text", "content": msg.content}

            # Tool Call 처리
            if not msg.tool_calls:
                yield {"type": "done", "content": ""}
                return

            # Tool 순차 실행
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_input = json.loads(tc.function.arguments)
                except Exception:
                    tool_input = {}

                yield {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tool_name,
                    "input": tool_input
                }

                result = self._execute_tool(tool_name, tool_input)

                # Tool 결과를 히스토리에 추가 (OpenAI format)
                self._messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                })

                yield {
                    "type": "tool_result",
                    "id": tc.id,
                    "name": tool_name,
                    "result": result
                }

            # finish_reason 확인
            if choice.finish_reason == "stop":
                yield {"type": "done", "content": ""}
                return

        # 최대 반복 초과
        yield {"type": "error", "message": "Agent가 최대 반복 횟수에 도달했습니다."}

    # =========================================================================
    # Tool 실행
    # =========================================================================
    def _execute_tool(self, name, tool_input):
        if name not in self._tools:
            return f"Error: Unknown tool '{name}'"
        try:
            return self._tools[name].execute(**tool_input)
        except Exception as e:
            return f"Error executing {name}: {str(e)}"

    # =========================================================================
    # Helpers
    # =========================================================================
    def _get_openai_tools(self):
        return [t.to_openai_tool() for t in self._tools.values()]

    def get_tools(self):
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]

    def get_history(self):
        return list(self._messages)

    def clear_history(self):
        self._messages = []

Model = Agent
