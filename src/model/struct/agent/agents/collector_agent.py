# =============================================================================
# CollectorAgent — 페이지 결과 수집 + 문헌 검색 (기존 tools 활용)
# =============================================================================
# 역할: RouterAgent의 계획에 따라 read_page_results, search_papers 등
#        기존 도구를 실행하여 데이터를 수집하고, 근거 은행을 구축
# =============================================================================

import json
import re

try:
    from .base_agent import BaseAgent
except ImportError:
    from base_agent import BaseAgent


class CollectorAgent(BaseAgent):
    name = "collector"
    description = "페이지 결과 수집, 문헌 검색, 도구 실행을 통해 근거 데이터를 수집합니다."

    def __init__(self, ctx):
        super().__init__(ctx)
        self.evidence_bank = []
        self.tool_result_bank = []
        self.page_result_bank = []
        self.last_navigation = None
        self.synthetic_tool_counter = 0

    def run(self, plan=None, message="", tools=None, client=None, messages=None, **kwargs):
        """OpenAI tool-calling 루프로 도구를 실행하여 결과를 수집.

        이 에이전트는 OpenAI API의 tool_choice=auto를 사용하여
        LLM이 적절한 도구를 선택하고 실행하는 방식을 유지한다.
        기존 clustered agent loop의 retriever+analyst+navigator 역할을 수행한다.

        Args:
            plan: RouterAgent가 반환한 orchestrator_plan dict
            message: 사용자 원본 메시지
            tools: 사용 가능한 도구 dict (name -> tool instance)
            client: OpenAI client
            messages: 현재 대화 히스토리 (system + user + ...)

        Yields:
            SSE 이벤트 dict (tool_use, tool_result, pipeline, goal_manager 등)
        """
        plan = plan or {}
        tools = tools or {}
        recommended = plan.get("recommended_tools", [])
        max_iterations = self.ctx.get("max_iterations", 15)

        # 허용 도구 스키마 구성
        tool_schemas = []
        for name in recommended:
            if name in tools:
                tool_schemas.append(tools[name].to_openai_tool())
        # recommended에 없는 도구도 추가 (retriever/analyst 영역)
        retrieval_tools = {"read_page_results", "search_papers", "get_collections",
                           "search_equations", "search_anomaly", "compare_diagnostics",
                           "failure_reasoning", "predict_process", "analyze_parameter_effect",
                           "inverse_search", "surrogate_predict", "build_theory_graph",
                           "extract_assumptions", "extract_equations", "recommend_topics",
                           "generate_hypothesis", "detect_research_gaps", "analyze_keywords",
                           "navigate_to_page"}
        for name in retrieval_tools:
            if name in tools and name not in recommended:
                tool_schemas.append(tools[name].to_openai_tool())

        iteration = 0
        tool_counter = 0

        for event in self._prefetch_page_results(plan, tools, messages):
            if event.get("type") == "_tool_counter":
                tool_counter = event.get("value", tool_counter)
                continue
            yield event

        while iteration < max_iterations:
            iteration += 1

            # LLM 호출
            model = self.ctx.get("model", "gpt-4o")
            try:
                api_kwargs = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": 2400,
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
            messages.append(assistant_msg)

            # tool 호출이 없으면 수집 완료 → 최종 텍스트를 반환
            if not msg.tool_calls:
                for event in self._ensure_navigation(plan, tools, messages, tool_counter):
                    if event.get("type") == "_tool_counter":
                        tool_counter = event.get("value", tool_counter)
                        continue
                    yield event
                yield {
                    "type": "_collector_done",
                    "content": msg.content or "",
                    "iteration": iteration,
                }
                return

            # 도구 순차 실행
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_input = json.loads(tc.function.arguments)
                except Exception:
                    tool_input = {}

                # 도구 입력 전처리 (collection, query 보강)
                tool_input = self._prepare_tool_input(tool_name, tool_input, plan)
                tool_counter += 1

                yield {
                    "type": "pipeline",
                    "component": "tools",
                    "status": "running",
                    "detail": f"{tool_name} 도구를 실행해 근거와 후속 액션을 수집하고 있습니다.",
                    "meta": {"tool_name": tool_name, "tool_count": tool_counter},
                    "metaBadges": [f"{tool_counter}개 실행", tool_name],
                }

                yield {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tool_name,
                    "input": tool_input,
                }

                # 도구 실행
                result = self._execute_tool(tool_name, tool_input, tools)

                # 결과 수집
                self._collect_tool_output(tool_name, tool_input, result)
                evidence_rows = self._collect_evidence(tool_name, tool_input, result)

                # 히스토리에 tool result 추가
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result if isinstance(result, str) else json.dumps(result, ensure_ascii=False),
                })

                yield {
                    "type": "tool_result",
                    "id": tc.id,
                    "name": tool_name,
                    "result": result,
                }

                yield {
                    "type": "pipeline",
                    "component": "tools",
                    "status": "running",
                    "detail": f"{tool_name} 결과를 메모리와 최종 답변 컨텍스트에 반영했습니다.",
                    "meta": {"tool_name": tool_name, "tool_count": tool_counter},
                    "metaBadges": [f"{tool_counter}개 완료", tool_name],
                }

            # finish_reason 확인
            if choice.finish_reason == "stop":
                for event in self._ensure_navigation(plan, tools, messages, tool_counter):
                    if event.get("type") == "_tool_counter":
                        tool_counter = event.get("value", tool_counter)
                        continue
                    yield event
                yield {
                    "type": "_collector_done",
                    "content": msg.content or "",
                    "iteration": iteration,
                }
                return

        # 최대 반복 초과
        yield {
            "type": "_collector_done",
            "content": "",
            "iteration": iteration,
            "max_reached": True,
        }

    def _next_synthetic_tool_id(self, tool_name):
        self.synthetic_tool_counter += 1
        return f"synthetic_{tool_name}_{self.synthetic_tool_counter}"

    def _supports_page_prefetch(self, page):
        return page in ("research", "prediction", "diagnosis", "theory")

    def _append_synthetic_tool_messages(self, messages, tool_name, tool_input, tool_call_id, result):
        if not isinstance(messages, list):
            return
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(tool_input, ensure_ascii=False),
                }
            }]
        })
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result if isinstance(result, str) else json.dumps(result, ensure_ascii=False),
        })

    def _execute_tool_with_events(self, tool_name, tool_input, tools, messages, tool_counter, detail_prefix=""):
        tool_counter += 1
        yield {
            "type": "pipeline",
            "component": "tools",
            "status": "running",
            "detail": detail_prefix or f"{tool_name} 도구를 실행해 최신 컬렉션 기준 결과를 수집하고 있습니다.",
            "meta": {"tool_name": tool_name, "tool_count": tool_counter},
            "metaBadges": [f"{tool_counter}개 실행", tool_name],
        }

        tool_call_id = self._next_synthetic_tool_id(tool_name)
        yield {
            "type": "tool_use",
            "id": tool_call_id,
            "name": tool_name,
            "input": tool_input,
        }

        result = self._execute_tool(tool_name, tool_input, tools)
        self._collect_tool_output(tool_name, tool_input, result)
        self._collect_evidence(tool_name, tool_input, result)
        self._append_synthetic_tool_messages(messages, tool_name, tool_input, tool_call_id, result)

        yield {
            "type": "tool_result",
            "id": tool_call_id,
            "name": tool_name,
            "result": result,
        }

        yield {
            "type": "pipeline",
            "component": "tools",
            "status": "running",
            "detail": f"{tool_name} 결과를 최신 컬렉션 메모리와 최종 답변 컨텍스트에 반영했습니다.",
            "meta": {"tool_name": tool_name, "tool_count": tool_counter},
            "metaBadges": [f"{tool_counter}개 완료", tool_name],
        }

        yield {"type": "_tool_counter", "value": tool_counter}

    def _prefetch_page_results(self, plan, tools, messages):
        page = plan.get("page", "")
        if "read_page_results" not in tools or not self._supports_page_prefetch(page):
            return

        prepared = self._prepare_tool_input("read_page_results", {
            "page": page,
            "tab": plan.get("tab", ""),
            "query": plan.get("query", ""),
            "params": plan.get("params", {}),
        }, plan)

        if not prepared.get("page"):
            return

        for event in self._execute_tool_with_events(
            "read_page_results",
            prepared,
            tools,
            messages,
            0,
            detail_prefix="read_page_results 도구를 먼저 실행해 최신 컬렉션 기준 페이지 검색 결과를 확보하고 있습니다."
        ):
            yield event

    def _ensure_navigation(self, plan, tools, messages, tool_counter):
        if self.last_navigation is not None:
            return
        if "navigate_to_page" not in tools:
            return

        prepared = self._prepare_tool_input("navigate_to_page", {
            "page": plan.get("page", ""),
            "tab": plan.get("tab", ""),
            "query": plan.get("query", ""),
            "params": plan.get("params", {}),
        }, plan)

        if not prepared.get("page"):
            return

        for event in self._execute_tool_with_events(
            "navigate_to_page",
            prepared,
            tools,
            messages,
            tool_counter,
            detail_prefix="navigate_to_page 도구를 실행해 최신 컬렉션 기준 페이지 handoff를 확정하고 있습니다."
        ):
            yield event

    # =========================================================================
    # 도구 실행
    # =========================================================================
    def _execute_tool(self, name, tool_input, tools):
        if name not in tools:
            return f"Error: Unknown tool '{name}'"
        try:
            return tools[name].execute(**tool_input)
        except Exception as e:
            return f"Error executing {name}: {str(e)}"

    def _prepare_tool_input(self, name, tool_input, plan):
        """도구 입력에 plan 정보를 보강."""
        prepared = dict(tool_input or {})
        collection = self.ctx.get("collection", "")

        if name in ("read_page_results", "navigate_to_page"):
            if not prepared.get("page") and plan.get("page"):
                prepared["page"] = plan["page"]
            if not prepared.get("tab") and plan.get("tab"):
                prepared["tab"] = plan["tab"]
            if not prepared.get("query") and plan.get("query"):
                prepared["query"] = plan["query"]
            if not prepared.get("params") and plan.get("params"):
                prepared["params"] = plan["params"]
            if collection:
                prepared["collection"] = collection
                if isinstance(prepared.get("params"), dict):
                    prepared["params"]["collection"] = collection
                else:
                    prepared["params"] = {"collection": collection}

        if name in ("search_papers",) and collection and not prepared.get("collection"):
            prepared["collection"] = collection

        return prepared

    # =========================================================================
    # 결과 수집
    # =========================================================================
    def _collect_tool_output(self, tool_name, tool_input, result):
        if tool_name == "navigate_to_page":
            try:
                parsed = json.loads(result) if isinstance(result, str) else result
                if isinstance(parsed, dict) and parsed.get("action") == "navigate":
                    self.last_navigation = parsed
            except Exception:
                pass
            return

        normalized = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        normalized = self._truncate(normalized, 900)
        if not normalized:
            return

        if tool_name == "read_page_results":
            try:
                parsed = json.loads(result) if isinstance(result, str) else result
                if isinstance(parsed, dict):
                    col = (parsed.get("collection") or "").strip()
                    if col:
                        self.ctx["collection"] = col
                    self.page_result_bank.append(parsed)
                    self.page_result_bank = self.page_result_bank[-4:]
            except Exception:
                pass

        self.tool_result_bank.append({
            "tool": tool_name,
            "input": tool_input if isinstance(tool_input, dict) else {},
            "result": normalized,
        })
        self.tool_result_bank = self.tool_result_bank[-8:]

    def _collect_evidence(self, tool_name, tool_input, result):
        if tool_name != "search_papers":
            return []

        query = tool_input.get("query", "") if isinstance(tool_input, dict) else ""
        existing_keys = set((e.get("filename"), e.get("chunk")) for e in self.evidence_bank)

        pattern = re.compile(
            r"--- Result (\d+) \(score: ([\d.]+)\) ---\nFile: (.+?) \| Chunk: (.+?)\nText: ([\s\S]*?)(?=\n--- Result|$)"
        )
        for match in pattern.finditer(result if isinstance(result, str) else ""):
            filename = (match.group(3) or "").strip()
            chunk = (match.group(4) or "").strip()
            key = (filename, chunk)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            self.evidence_bank.append({
                "rank": int(match.group(1)),
                "score": float(match.group(2)),
                "filename": filename,
                "chunk": chunk,
                "excerpt": self._truncate((match.group(5) or "").strip(), 240),
                "query": query,
            })

        self.evidence_bank = sorted(self.evidence_bank, key=lambda x: x.get("score", 0), reverse=True)[:8]
        return list(self.evidence_bank)

    def _truncate(self, text, limit=220):
        text = " ".join((text or "").split())
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    # =========================================================================
    # 수집 결과 조회
    # =========================================================================
    def get_collected_data(self):
        """수집된 모든 데이터를 반환."""
        return {
            "evidence_bank": list(self.evidence_bank),
            "tool_result_bank": list(self.tool_result_bank),
            "page_result_bank": list(self.page_result_bank),
            "last_navigation": self.last_navigation,
        }
