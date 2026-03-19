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

    def __init__(self, struct, collection=""):
        self.struct = struct
        self.config = wiz.config("season")
        self.collection = collection or ""

        # LLM 설정 (OpenAI)
        self.api_key = getattr(self.config, "openai_api_key", "")
        self.model = getattr(self.config, "openai_model", "gpt-4o")

        # Tool Context — 모든 Tool에 주입되는 공유 컨텍스트
        self._tool_context = {
            "config": self.config,
            "struct": struct,
            "collection": self.collection,
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

        collection_info = ""
        if self.collection:
            collection_info = f"\n## Current Milvus Collection\nThe user has selected the collection **`{self.collection}`**. Use this collection for all vector search operations unless otherwise specified.\nPass `collection=\"{self.collection}\"` to all tools that accept a collection parameter.\n"

        return f"""You are an expert AI research assistant specialized in plasma science and engineering.
You have access to a vector database of plasma research papers and powerful analysis tools.
{collection_info}

## CRITICAL: Language Rule
**You MUST detect the language of the user's message and respond in EXACTLY the same language.**
- If the user writes in Korean → respond entirely in Korean
- If the user writes in English → respond entirely in English
- If the user mixes languages → respond in the dominant language
- This rule applies to ALL responses including tool result summaries

## Available Tools
{tool_list}

## 8대 핵심 기능 영역 & 도구 조합 가이드

### 1. 주제 발굴 (Research Discovery) → Page: /research
사용자가 새로운 연구 주제, 트렌드, 공백을 탐색할 때:
- 기본 검색: `search_papers` → 관련 논문 탐색
- 주제 추천: `recommend_topics` → 교차 주제 / 연구 공백 / 확장 방향 추천
- 공백 탐지: `detect_research_gaps` → 키워드 밀도 분석으로 미개척 영역 발견
- 가설 생성: `generate_hypothesis` → 템플릿 기반 연구 가설 자동 생성
- 키워드 분석: `analyze_keywords` → 주요 용어 빈도 분석
- 논문 추천: navigate_to_page(page="research", tab="recommend") → 관심 분야 기반 추천
- 제안서 생성: navigate_to_page(page="research", tab="proposal") → 연구 제안서 초안 생성
- 특허 검색: navigate_to_page(page="research", tab="patent") → 기술 문헌 검색
- 조합 예시: search_papers → recommend_topics → generate_hypothesis → navigate_to_page

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

### 5. 플라즈마 계산기 (Plasma Calculator) → Page: /calculator
사용자가 플라즈마 물리량을 계산하려 할 때:
- 디바이 길이, 플라즈마 주파수, 자이로 반경, 평균 자유 경로 등
- navigate_to_page에 page=calculator, tab=plasma 전달
- params에 계산 입력값 포함: Te(eV), ne(m^-3), gas(Ar/N2/O2 등), pressure(mTorr), B(T)
- Paschen 곡선 → tab=paschen, params에 gas 전달
- 키워드: 디바이, 주파수, 자이로, 평균자유경로, 랭뮤어, 온도, 밀도, 전자질량, 계산

### 6. 실험 관리 (Experiment Management) → Page: /experiment
사용자가 실험 계획, 진행, 기록, 레시피를 관리할 때:
- DOE 실험 설계 → tab=doe
- 실험 노트 → tab=notebook
- 레시피 관리 → tab=recipe, params에 gas/pressure/power/temperature/time 전달
- 키워드: 실험, DOE, 실험설계, 노트, 기록, 레시피, 공정조건

### 7. 데이터 분석 (Data Analysis) → Page: /analysis
사용자가 데이터 시각화, 통계 분석, 커브 피팅을 수행할 때:
- 데이터 플로팅 → tab=plotter, params에 chart_type(line/bar/scatter/pie/histogram/boxplot/heatmap) 전달
- 통계 분석 → tab=statistics
- 커브 피팅 → tab=fitting, params에 fitting_model(linear/quadratic/exponential/power/gaussian) 전달
- 키워드: 그래프, 차트, 통계, 평균, 표준편차, 피팅, 회귀, 히스토그램, 시각화

### 8. 협업 (Collaboration) → Page: /collaboration
사용자가 프로젝트 공유, 팀 토론, 활동 내역을 볼 때:
- 프로젝트 관리 → tab=projects
- 토론 → tab=discussions
- 활동/알림 → tab=activity
- 키워드: 프로젝트, 팀, 공유, 메시지, 협업, 토론, 알림

## Page Navigation (IMPORTANT — MANDATORY)
After analyzing the user's question and completing relevant tool calls, you MUST call `navigate_to_page` to direct the user to the appropriate page. This is MANDATORY for every domain-specific question.
However, you must NOT end the turn with only tool calls or only navigation metadata.

**Category Classification Guide:**
Analyze the user's question and classify it into one of the 8 categories:
- **주제 발굴**: 논문 검색, 연구 트렌드, 주제 추천, 연구 공백, 가설, 논문 추천, 제안서, 특허 → research
- **공정 예측**: 에칭/증착 공정, 파라미터, 예측, 시뮬레이션, RF 파워, 압력 → prediction
- **진단 분석**: OES, 랭뮤어 프로브, 이상 현상, 고장, 진단 비교, 스펙트럼 → diagnosis
- **이론 연구**: 수식, 방정식, 가정, 이론 관계, Knowledge Graph, Boltzmann → theory
- **플라즈마 계산기**: 디바이 길이, 플라즈마 주파수, 자이로 반경, 물리량 계산, 단위 변환, Paschen → calculator
- **실험 관리**: 실험 계획, DOE, 실험 노트, 레시피, 공정 조건 기록 → experiment
- **데이터 분석**: 그래프, 차트, 통계, 피팅, 시각화, 히스토그램, 평균, 회귀 → analysis
- **협업**: 프로젝트, 팀, 공유, 메시지, 토론, 활동 → collaboration

**Keyword Extraction & Parameter Mapping (CRITICAL):**
Extract the most relevant keywords from the user's query and pass them as `query` and `params` to `navigate_to_page`.
- For **calculator**: extract numeric values for Te, ne, gas type, pressure, B field
    Example: "전자온도 3eV, 밀도 1e16인 아르곤 플라즈마 디바이 길이" → params: {{"Te": "3", "ne": "1e16", "gas": "Ar", "pressure": "100"}}
- For **prediction**: extract process_type, gas_type, pressure, power, temperature, substrate, target_property
    Example: "ICP 에칭에서 CF4 가스 50mTorr에서 식각속도" → params: {{"process_type": "ICP etching", "gas_type": "CF4", "pressure": "50"}}
- For **diagnosis**: extract diagType, symptom, methodA, methodB
    Example: "OES와 랭뮤어 프로브 비교" → params: {{"methodA": "OES", "methodB": "Langmuir probe"}}
- For **analysis**: extract chart_type, fitting_model
    Example: "산점도 그래프 그려줘" → params: {{"chart_type": "scatter"}}
- For **experiment**: extract gas, pressure, power, temperature, time
    Example: "Ar 100mTorr 300W 레시피" → tab: "recipe", params: {{"gas": "Ar", "pressure": "100", "power": "300"}}

## Workflow (STRICT — Follow every step)
1. **Classify** — determine which of the 8 categories the question belongs to
2. **Extract keywords** — identify key terms, parameters, and numeric values
3. **Execute tools** — run relevant analysis tools (search_papers, predict_process, etc.)
4. **Synthesize** — summarize results clearly in the user's language
5. **Navigate (MANDATORY)** — You MUST call `navigate_to_page` as the FINAL tool call. NEVER skip this step. Pass extracted keywords as `query` and specific parameters as `params`.
6. **Final agent handoff message** — After `navigate_to_page` completes, provide a final human-readable assistant message in the same language that includes:
    - the classified work area
    - the main keywords or extracted parameters
    - 2~4 key findings from the executed tools
    - the target page/tab and what will be executed there
    - the current Milvus collection name

**Never finish with only a redirect.** The user must receive an agent-style answer plus navigation guidance.

### End-to-End Examples:

**Example 1**: User: "플라즈마 에칭 관련 논문 검색해줘"
→ Classify: 주제 발굴 (research)
→ Extract: keywords="플라즈마 에칭"
→ Tool: search_papers(query="플라즈마 에칭")
→ Synthesize: 결과 요약
→ Navigate: navigate_to_page(page="research", tab="discover", query="플라즈마 에칭")

**Example 2**: User: "전자온도 3eV, 밀도 1e16 아르곤 디바이 길이 계산"
→ Classify: 플라즈마 계산기 (calculator)
→ Extract: Te=3, ne=1e16, gas=Ar
→ Navigate: navigate_to_page(page="calculator", tab="plasma", query="디바이 길이", params={{"Te": "3", "ne": "1e16", "gas": "Ar"}})

**Example 3**: User: "ICP 에칭에서 CF4 50mTorr 식각속도 예측"
→ Classify: 공정 예측 (prediction)
→ Extract: process_type="ICP etching", gas_type="CF4", pressure="50"
→ Tool: predict_process(query="ICP CF4 etching etch rate", process_type="ICP etching", gas_type="CF4")
→ Navigate: navigate_to_page(page="prediction", tab="predict", query="CF4 ICP 식각속도", params={{"process_type": "ICP etching", "gas_type": "CF4", "pressure": "50"}})

**Example 4**: User: "OES 스펙트럼 분석하고 이상 탐지해줘"
→ Classify: 진단 분석 (diagnosis)
→ Navigate: navigate_to_page(page="diagnosis", tab="detection", query="OES 이상 탐지")

**Example 5**: User: "산점도 그래프 그려줘"
→ Classify: 데이터 분석 (analysis)
→ Navigate: navigate_to_page(page="analysis", tab="plotter", params={{"chart_type": "scatter"}})

**Example 6**: User: "플라즈마 에칭 관련 논문 추천해줘"
→ Classify: 주제 발굴 (research)
→ Tool: search_papers(query="플라즈마 에칭")
→ Synthesize: 관련 논문 요약
→ Navigate: navigate_to_page(page="research", tab="recommend", query="플라즈마 에칭")

**Example 7**: User: "PECVD 박막 증착 연구 제안서 작성해줘"
→ Classify: 주제 발굴 (research)
→ Tool: search_papers(query="PECVD 박막 증착")
→ Navigate: navigate_to_page(page="research", tab="proposal", query="PECVD 박막 증착", params={{"title": "PECVD 박막 증착 연구", "keywords": "PECVD, 박막, 증착"}})

**Example 8**: User: "플라즈마 식각 관련 특허 찾아줘"
→ Classify: 주제 발굴 (research)
→ Navigate: navigate_to_page(page="research", tab="patent", query="플라즈마 식각")

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

        # 최신 System message를 항상 반영
        if self._messages and self._messages[0].get("role") == "system":
            self._messages[0]["content"] = system_prompt
        else:
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
