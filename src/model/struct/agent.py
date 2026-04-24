# =============================================================================
# Agent Struct — Claude 분석서형 단일 Tool-Use 루프 (OpenAI GPT)
# =============================================================================

import os
import re
import sys
import json
import uuid
import importlib.util


class Agent:
    MAX_ITERATIONS = 20

    def __init__(self, struct, collection="", provider=None, model_name=None, api_key=None,
                 temperature=None, top_p=None, max_tokens=None):
        self.struct = struct
        self.config = wiz.config("season")
        self.collection = collection or ""
        self.provider = self._normalize_provider(provider or getattr(self.config, "llm_provider", "local"))
        if self.provider == "openai":
            self.model = model_name or getattr(self.config, "openai_model", "gpt-4.1")
        else:
            self.model = model_name or getattr(self.config, "local_model_name", "google/gemma-4-26B-A4B-it")
        self.api_key = api_key or getattr(self.config, "openai_api_key", "") or os.environ.get("OPENAI_API_KEY", "")
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens or 2400

        self._tool_context = {
            "wiz": wiz,
            "config": self.config,
            "struct": struct,
            "collection": self.collection,
        }

        self._tools = {}
        self._messages = []
        self._load_tools()

    def _normalize_provider(self, provider):
        value = str(provider or "local").strip().lower()
        if value in ("gpt", "gpt-4.1", "openai-chat"):
            return "openai"
        if value in ("local", "openai"):
            return value
        return "local"

    def _get_local_client(self):
        _mod_key = "_wiz_local_llm"
        _REQUIRED_VER = 15
        if _mod_key in sys.modules:
            _cached = sys.modules[_mod_key]
            if getattr(_cached, '_VERSION', 0) < _REQUIRED_VER:
                if hasattr(_cached, '_cleanup'):
                    _cached._cleanup()
                del sys.modules[_mod_key]
                del _cached
                import os as _os
                _os._exit(0)

        if _mod_key in sys.modules and hasattr(sys.modules[_mod_key], "get_client"):
            _mod = sys.modules[_mod_key]
        else:
            import importlib.util as _ilu
            _llm_path = os.path.join(wiz.project.fs().abspath(), "src", "model", "local_llm.py")
            if not os.path.isfile(_llm_path):
                for c in ["build", "bundle"]:
                    _p = os.path.join(wiz.project.fs().abspath(), c, "model", "local_llm.py")
                    if os.path.isfile(_p):
                        _llm_path = _p
                        break
            _spec = _ilu.spec_from_file_location(_mod_key, _llm_path)
            _mod = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            sys.modules[_mod_key] = _mod
        return _mod.get_client(self.config)

    def _get_openai_client(self):
        if not self.api_key:
            raise ValueError("OpenAI API key가 설정되지 않았습니다.")
        from openai import OpenAI
        return OpenAI(api_key=self.api_key)

    def _get_llm_client(self):
        if self.provider == "openai":
            return self._get_openai_client()
        return self._get_local_client()

    # =========================================================================
    # Tool Auto-Discovery
    # =========================================================================
    def _load_tools(self):
        project_root = wiz.project.fs().abspath()
        tools_dir = None
        for candidate in ["src", "build", "bundle"]:
            path = os.path.join(project_root, candidate, "model", "struct", "agent", "tools")
            if os.path.isdir(path):
                tools_dir = path
                break

        if tools_dir is None:
            return

        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)

        for fname in sorted(os.listdir(tools_dir)):
            if not fname.endswith(".py") or fname.startswith("_") or fname == "base_tool.py":
                continue

            filepath = os.path.join(tools_dir, fname)
            module_name = fname[:-3]
            try:
                spec = importlib.util.spec_from_file_location(f"agent_tool_{module_name}", filepath)
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
    # Support Agents (Keyword / Router)
    # =========================================================================
    def _get_agents_dir(self):
        project_root = wiz.project.fs().abspath()
        candidate_paths = [
            os.path.join(project_root, "bundle", "src", "model", "struct", "agent", "agents"),
            os.path.join(project_root, "build", "src", "model", "struct", "agent", "agents"),
            os.path.join(project_root, "src", "model", "struct", "agent", "agents"),
            os.path.join(project_root, "bundle", "model", "struct", "agent", "agents"),
            os.path.join(project_root, "build", "model", "struct", "agent", "agents"),
        ]
        for path in candidate_paths:
            if os.path.isdir(path):
                return path
        return None

    def _load_support_agent_classes(self):
        agents_dir = self._get_agents_dir()
        if agents_dir is None:
            return None, None

        parent_dir = os.path.dirname(agents_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        if agents_dir not in sys.path:
            sys.path.insert(0, agents_dir)

        modules = [
            ("base_agent", "base_agent.py"),
            ("keyword_agent", "keyword_agent.py"),
            ("router_agent", "router_agent.py"),
        ]

        try:
            for module_name in [name for name, _ in modules]:
                if module_name in sys.modules:
                    del sys.modules[module_name]

            loaded = {}
            for module_name, filename in modules:
                path = os.path.join(agents_dir, filename)
                if not os.path.isfile(path):
                    return None, None
                spec = importlib.util.spec_from_file_location(module_name, path)
                mod = importlib.util.module_from_spec(spec)
                mod.wiz = wiz
                sys.modules[module_name] = mod
                spec.loader.exec_module(mod)
                loaded[module_name] = mod

            return loaded["keyword_agent"].KeywordAgent, loaded["router_agent"].RouterAgent
        except Exception:
            import traceback
            traceback.print_exc()
            return None, None

    # =========================================================================
    # Main Run Loop (Claude-style)
    # =========================================================================
    def run(self, message, history=None):
        try:
            client = self._get_llm_client()
        except Exception as e:
            prefix = "OpenAI LLM 로딩 실패" if self.provider == "openai" else "로컬 LLM 로딩 실패"
            yield {"type": "error", "message": f"{prefix}: {str(e)}"}
            return

        ctx = dict(self._tool_context)
        ctx["client"] = client
        ctx["model"] = self.model
        ctx["provider"] = self.provider
        ctx["max_iterations"] = self.MAX_ITERATIONS

        KeywordAgent, RouterAgent = self._load_support_agent_classes()
        if KeywordAgent is None or RouterAgent is None:
            yield {"type": "error", "message": "Keyword/Router helper 로드 실패"}
            return

        keyword_agent = KeywordAgent(ctx)
        router_agent = RouterAgent(ctx)

        classification = keyword_agent.run(message=message)
        classification["collection"] = self._current_collection()
        plan = router_agent.run(classification=classification)
        plan["collection"] = self._current_collection()

        language = classification.get("language", "ko")
        difficulty = classification.get("difficulty", "빠른 응답")
        memory_context = self._build_memory_context(history, message)

        yield self._build_orchestration_snapshot(memory_context, plan, language, difficulty)

        tools = self._tools or {}
        system_prompt = self._build_system_prompt(plan, memory_context, self._current_collection(), tools)
        messages = self._build_messages(system_prompt, history, message)
        collected = {
            "evidence_bank": [],
            "tool_result_bank": [],
            "page_result_bank": [],
            "last_navigation": None,
        }
        synthetic_tool_counter = 0

        # 페이지 결과는 먼저 읽어 UI에 실제 결과를 보여준다.
        if plan.get("page") in ("research", "prediction", "diagnosis", "theory") and "read_page_results" in tools:
            prepared = self._prepare_tool_input("read_page_results", {
                "page": plan.get("page", ""),
                "tab": plan.get("tab", ""),
                "query": plan.get("query", ""),
                "params": plan.get("params", {}),
            }, plan)
            for event, synthetic_tool_counter in self._run_synthetic_tool(
                "read_page_results", prepared, tools, messages, collected, synthetic_tool_counter
            ):
                yield event

            # 페이지 결과를 LLM이 자연어로 요약 → collected에 저장 (실패해도 본 흐름은 계속)
            try:
                synthesis = self._generate_page_synthesis(
                    client, collected.get("page_result_bank", []), message, language
                )
                if synthesis:
                    collected["page_synthesis"] = synthesis
            except Exception:
                pass

        tool_schemas = self._build_tool_schemas(plan, tools)

        iteration = 0
        while iteration < self.MAX_ITERATIONS:
            iteration += 1
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": self.max_tokens,
                }
                if self.temperature is not None:
                    kwargs["temperature"] = self.temperature
                if self.top_p is not None:
                    kwargs["top_p"] = self.top_p
                if tool_schemas:
                    kwargs["tools"] = tool_schemas
                    kwargs["tool_choice"] = "auto"

                # ─── LOCAL: 스트리밍 경로 (토큰 즉시 전달) ───
                if self.provider == "local":
                    for ev in self._run_local_streaming_iteration(
                        client, kwargs, messages, plan, tools, tool_schemas,
                        collected, synthetic_tool_counter, message, language
                    ):
                        ev_type = ev.get("_type") if isinstance(ev, dict) else ""
                        if ev_type == "_continue":
                            synthetic_tool_counter = ev.get("counter", synthetic_tool_counter)
                            break  # break inner for → continue outer while
                        if ev_type == "_return":
                            return
                        yield ev
                    else:
                        # for loop completed without break → _return was issued inside
                        continue
                    # break was hit → continue outer while loop
                    continue

                # ─── OPENAI: 기존 non-streaming 경로 ───
                response = client.chat.completions.create(**kwargs)
            except Exception as e:
                yield {"type": "error", "message": f"LLM API 호출 실패: {str(e)}"}
                return

            choice = response.choices[0]
            msg = choice.message

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
            self._messages = self._history_without_system(messages)

            # Claude-style: tool_call이 없으면 종료. 단, handoff가 없으면 마지막 navigate를 보장.
            if not msg.tool_calls:
                if collected.get("last_navigation") is None and "navigate_to_page" in tools and plan.get("page"):
                    prepared = self._prepare_tool_input("navigate_to_page", {
                        "page": plan.get("page", ""),
                        "tab": plan.get("tab", ""),
                        "query": plan.get("query", ""),
                        "params": plan.get("params", {}),
                    }, plan)
                    for event, synthetic_tool_counter in self._run_synthetic_tool(
                        "navigate_to_page", prepared, tools, messages, collected, synthetic_tool_counter
                    ):
                        yield event
                    self._messages = self._history_without_system(messages)
                    continue

                text_content = self._finalize_answer_text(msg.content or "", collected, language)
                if text_content:
                    messages[-1]["content"] = text_content
                    self._messages = self._history_without_system(messages)
                    yield {"type": "text", "content": text_content}

                if not text_content:
                    fallback = self._build_fallback_answer(message, collected, language)
                    if fallback:
                        yield {"type": "text", "content": fallback}
                    else:
                        yield {"type": "error", "message": "최종 답변을 생성하지 못했습니다."}
                        return

                self._messages = self._history_without_system(messages)
                yield {"type": "done", "content": ""}
                return

            text_content = (msg.content or "").strip()
            if text_content:
                yield {"type": "text", "content": text_content}

            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_input = json.loads(tc.function.arguments)
                except Exception:
                    tool_input = {}

                prepared = self._prepare_tool_input(tool_name, tool_input, plan)
                yield {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tool_name,
                    "input": prepared,
                }

                result = self._execute_tool(tool_name, prepared, tools)
                self._collect_tool_output(tool_name, prepared, result, collected)
                self._collect_evidence(tool_name, prepared, result, collected)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result if isinstance(result, str) else json.dumps(result, ensure_ascii=False),
                })
                self._messages = self._history_without_system(messages)

                yield {
                    "type": "tool_result",
                    "id": tc.id,
                    "name": tool_name,
                    "result": result,
                }

        fallback = self._build_fallback_answer(message, collected, language)
        if fallback:
            yield {"type": "text", "content": fallback}
            yield {"type": "done", "content": ""}
            return
        yield {"type": "error", "message": "Agent reached maximum iteration limit."}

    # =========================================================================
    # Local Streaming (토큰 단위 실시간 전달)
    # =========================================================================
    _STREAM_BUFFER = 200  # tool_call 마커 감지 전까지 버퍼링할 문자 수

    def _run_local_streaming_iteration(self, client, kwargs, messages, plan,
                                        tools, tool_schemas, collected,
                                        synthetic_tool_counter, user_message, language):
        """로컬 모델 1회 LLM 호출을 스트리밍으로 수행.
        yield하는 이벤트 중 내부 제어용:
          {"_type": "_continue", "counter": N}  → 외부 while 루프 continue
          {"_type": "_return"}                  → 외부 함수 return
        """
        stream_kwargs = dict(kwargs)
        stream_kwargs["stream"] = True

        accumulated = ""
        text_delta_started = False
        tool_marker_found = False

        try:
            for chunk in client.chat.completions.create(**stream_kwargs):
                delta_text = ""
                if chunk.choices and chunk.choices[0].delta:
                    delta_text = chunk.choices[0].delta.content or ""
                if not delta_text:
                    if chunk.choices and chunk.choices[0].finish_reason == "stop":
                        break
                    continue

                accumulated += delta_text

                # tool_call 마커 감지
                if not tool_marker_found:
                    if "<tool_call>" in accumulated or "```json\n{" in accumulated:
                        tool_marker_found = True
                    elif len(accumulated) >= self._STREAM_BUFFER and not text_delta_started:
                        # 버퍼 임계치 도달, tool_call 아님 → 텍스트 스트리밍 시작
                        yield {"type": "text_delta", "content": accumulated}
                        text_delta_started = True
                    elif text_delta_started:
                        yield {"type": "text_delta", "content": delta_text}
                # tool_marker_found 이후에는 조용히 누적만
        except Exception as e:
            yield {"type": "error", "message": f"LLM 스트리밍 실패: {str(e)}"}
            yield {"_type": "_return"}
            return

        # 버퍼에 남은 짧은 텍스트 (BUFFER 미만이고 tool_call 아닌 경우)
        if not tool_marker_found and not text_delta_started and accumulated.strip():
            yield {"type": "text_delta", "content": accumulated}
            text_delta_started = True

        # tool_call 파싱
        parsed_tcs, remaining_text = self._parse_local_tool_calls(accumulated, tool_schemas)

        if parsed_tcs:
            # tool_call이 있었는데 이미 text_delta를 보냈다면 클리어
            if text_delta_started:
                yield {"type": "text_clear"}

            assistant_msg = {"role": "assistant", "content": remaining_text}
            assistant_msg["tool_calls"] = [
                {"id": tc["id"], "type": "function",
                 "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in parsed_tcs
            ]
            messages.append(assistant_msg)
            self._messages = self._history_without_system(messages)

            if remaining_text.strip():
                yield {"type": "text", "content": remaining_text.strip()}

            for tc in parsed_tcs:
                tool_name = tc["name"]
                try:
                    tool_input = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
                except Exception:
                    tool_input = {}

                prepared = self._prepare_tool_input(tool_name, tool_input, plan)
                yield {"type": "tool_use", "id": tc["id"], "name": tool_name, "input": prepared}

                result = self._execute_tool(tool_name, prepared, tools)
                self._collect_tool_output(tool_name, prepared, result, collected)
                self._collect_evidence(tool_name, prepared, result, collected)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result if isinstance(result, str) else json.dumps(result, ensure_ascii=False),
                })

                yield {"type": "tool_result", "id": tc["id"], "name": tool_name, "result": result}

            self._messages = self._history_without_system(messages)
            yield {"_type": "_continue", "counter": synthetic_tool_counter}
            return

        # ── tool_call 없음 = 최종 답변 ──
        final_text = accumulated.strip()
        assistant_msg = {"role": "assistant", "content": final_text}
        messages.append(assistant_msg)
        self._messages = self._history_without_system(messages)

        # navigate 보장
        if collected.get("last_navigation") is None and "navigate_to_page" in tools and plan.get("page"):
            prepared = self._prepare_tool_input("navigate_to_page", {
                "page": plan.get("page", ""),
                "tab": plan.get("tab", ""),
                "query": plan.get("query", ""),
                "params": plan.get("params", {}),
            }, plan)
            for event, synthetic_tool_counter in self._run_synthetic_tool(
                "navigate_to_page", prepared, tools, messages, collected, synthetic_tool_counter
            ):
                yield event
            self._messages = self._history_without_system(messages)
            yield {"_type": "_continue", "counter": synthetic_tool_counter}
            return

        text_content = self._finalize_answer_text(final_text, collected, language)
        if text_content:
            messages[-1]["content"] = text_content
            self._messages = self._history_without_system(messages)
            yield {"type": "text", "content": text_content}
        else:
            fallback = self._build_fallback_answer(user_message, collected, language)
            if fallback:
                yield {"type": "text", "content": fallback}
            else:
                yield {"type": "error", "message": "최종 답변을 생성하지 못했습니다."}
                yield {"_type": "_return"}
                return

        self._messages = self._history_without_system(messages)
        yield {"type": "done", "content": ""}
        yield {"_type": "_return"}

    @staticmethod
    def _parse_local_tool_calls(text, tool_schemas):
        """로컬 모델 스트리밍 출력에서 tool_call JSON을 파싱."""
        if not text or not tool_schemas:
            return [], text

        results = []
        remaining = text
        patterns = [
            r'<tool_call>\s*(\{.*?\})\s*</tool_call>',
            r'```json\s*(\{.*?\})\s*```',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.DOTALL):
                try:
                    data = json.loads(match.group(1))
                    if "name" in data and "arguments" in data:
                        tc_id = f"call_{uuid.uuid4().hex[:8]}"
                        args = data["arguments"]
                        if isinstance(args, dict):
                            args = json.dumps(args, ensure_ascii=False)
                        results.append({"id": tc_id, "name": data["name"], "arguments": args})
                        remaining = remaining.replace(match.group(0), "", 1)
                except (json.JSONDecodeError, KeyError):
                    pass
        return results, remaining.strip()

    # =========================================================================
    # Message / Prompt Helpers
    # =========================================================================
    def _current_collection(self):
        return (self._tool_context.get("collection", "") or "").strip()

    def _build_memory_context(self, history, message):
        history = history or []
        chat_turns = [h for h in history if isinstance(h, dict) and h.get("role") in ("user", "assistant")]
        recent_user_queries = [h.get("content", "") for h in chat_turns if h.get("role") == "user"][-3:]
        current_message = (message or "").strip()
        return {
            "collection": self._current_collection(),
            "history_turns": len(chat_turns),
            "recent_user_queries": [q for q in recent_user_queries if q],
            "current_message": current_message,
            "last_topic": recent_user_queries[-1] if recent_user_queries else current_message,
        }

    def _sanitize_history(self, history):
        sanitized = []
        items = list(history or [])
        idx = 0
        while idx < len(items):
            item = items[idx]
            if not isinstance(item, dict):
                idx += 1
                continue
            role = item.get("role")
            if role != "assistant":
                if role != "tool" and role != "system":
                    sanitized.append(dict(item))
                idx += 1
                continue
            tool_calls = item.get("tool_calls")
            if not isinstance(tool_calls, list) or len(tool_calls) == 0:
                sanitized.append(dict(item))
                idx += 1
                continue
            expected_ids = [tc.get("id") for tc in tool_calls if isinstance(tc, dict) and tc.get("id")]
            if not expected_ids:
                copy = dict(item)
                copy.pop("tool_calls", None)
                if copy.get("content"):
                    sanitized.append(copy)
                idx += 1
                continue
            matched = []
            seen = set()
            probe = idx + 1
            while probe < len(items):
                ni = items[probe]
                if not isinstance(ni, dict) or ni.get("role") != "tool":
                    break
                tcid = ni.get("tool_call_id")
                if tcid in expected_ids and tcid not in seen:
                    matched.append(dict(ni))
                    seen.add(tcid)
                probe += 1
            if len(seen) == len(expected_ids):
                sanitized.append(dict(item))
                sanitized.extend(matched)
            else:
                copy = dict(item)
                copy.pop("tool_calls", None)
                if copy.get("content"):
                    sanitized.append(copy)
            idx = probe if probe > idx else idx + 1
        return sanitized

    def _build_messages(self, system_prompt, history, message):
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for item in self._sanitize_history(history):
                messages.append(item)
        messages.append({"role": "user", "content": message})
        return messages

    def _history_without_system(self, messages):
        return [dict(item) for item in messages if isinstance(item, dict) and item.get("role") != "system"]

    def _build_system_prompt(self, plan, memory_context, collection, tools):
        tool_descs = "\n".join([f"- {t.name}: {t.description}" for t in tools.values()])
        recent_queries = "\n".join([f"- {q}" for q in memory_context.get("recent_user_queries", [])]) or "- No previous turns"
        tool_lines = ", ".join(plan.get("recommended_tools", [])) or "read_page_results, search_papers, navigate_to_page"
        plan_lines = "\n".join([f"- {p}" for p in plan.get("plan", [])]) or "- Read page results, gather evidence, handoff to destination page, answer briefly."

        return f"""You are an expert AI research assistant specialized in plasma science and engineering.

Use a simple tool-use loop:
1. Call read_page_results FIRST to get actual data from the target page.
2. Call additional tools (search_papers, etc.) if more evidence is needed.
3. Call navigate_to_page as the final handoff tool so the user's browser moves to the right page with the correct parameters.
4. Then provide a comprehensive final answer that MUST include:
   a) A summary of the page results (what was found, how many results, key items).
   b) Key insights or analysis based on the collected evidence.
   c) Mention that the page has been navigated with the given parameters for further exploration.

Current collection: {collection or 'none'}
Recent turns: {memory_context.get('history_turns', 0)}
Recent queries:
{recent_queries}

Planned destination: {plan.get('page', '-')}/{plan.get('tab', '-')}
Category: {plan.get('category', 'unknown')}
Recommended tools: {tool_lines}
Plan:
{plan_lines}

Critical requirements:
- ALWAYS summarize read_page_results data in the final answer. Include result count, top item titles/names, and any relevant scores or metrics.
- Keep page move, parameter insertion, and page result reading in the workflow.
- Prefer read_page_results before making claims about what a page would show.
- Pass collection to tools that accept it.
- Never dump raw chunks without explanation.
- Always answer in Korean for Korean user questions.
- Do not invent URLs, domains, placeholder links, or markdown links.
- If you mention navigation, only use the exact URL returned by navigate_to_page.
- Prefer plain Korean guidance over fabricated hyperlink text.
- Final answer must be detailed and grounded in tool results. Never give a vague or generic answer when you have concrete data from tools.

Available tools:
{tool_descs or '- none'}
"""

    def _build_orchestration_snapshot(self, memory_context, plan, language, difficulty):
        collection = self._current_collection() or "미선택"
        return {
            "type": "orchestration",
            "category": plan.get("category", "주제 발굴"),
            "page": plan.get("page", "research"),
            "tab": plan.get("tab", "discover"),
            "keywords": plan.get("keywords", []),
            "recommended_tools": plan.get("recommended_tools", []),
            "plan": plan.get("plan", []),
            "execution_plan": {
                "category": plan.get("category", "주제 발굴"),
                "page": plan.get("page", "research"),
                "tab": plan.get("tab", "discover"),
                "goal": plan.get("goal", "produce a grounded answer"),
                "keywords": plan.get("keywords", []),
                "recommended_tools": plan.get("recommended_tools", []),
                "plan_lines": plan.get("plan", []),
                "collection": self._current_collection(),
                "params": plan.get("params", {}),
                "query": plan.get("query", ""),
                "goal_status": "running",
            },
            "language": language,
            "difficulty": difficulty,
            "collection": self._current_collection(),
            "trace_steps": [
                {"id": 1, "title": "질문 수신", "summary": "새로운 질문을 분석합니다.", "status": "done"},
                {"id": 2, "title": "경로 결정", "summary": f"대상: {plan.get('page', 'research')}/{plan.get('tab', 'discover')}", "status": "running"},
                {"id": 3, "title": "도구 실행", "summary": "필요한 도구를 호출합니다.", "status": "pending"},
                {"id": 4, "title": "결과 수집", "summary": "페이지 결과와 근거를 수집합니다.", "status": "pending"},
                {"id": 5, "title": "답변 생성", "summary": "최종 답변을 생성합니다.", "status": "pending"},
            ],
            "pipeline_components": [],
            "currentLabel": "오케스트레이션 계획 수립",
            "currentDescription": f"{plan.get('category', '주제 발굴')} 흐름으로 질문을 분류하고, 페이지 이동과 결과 추출을 준비했습니다.",
        }

    # =========================================================================
    # Tool Helpers
    # =========================================================================
    def _build_tool_schemas(self, plan, tools):
        recommended = plan.get("recommended_tools", [])
        allowed = []
        seen = set()
        for name in recommended:
            if name in tools and name not in seen:
                allowed.append(tools[name].to_openai_tool())
                seen.add(name)
        extra = {
            "read_page_results", "search_papers", "get_collections", "search_equations",
            "search_anomaly", "compare_diagnostics", "failure_reasoning", "predict_process",
            "analyze_parameter_effect", "inverse_search", "surrogate_predict", "build_theory_graph",
            "extract_assumptions", "recommend_topics", "generate_hypothesis", "detect_research_gaps",
            "analyze_keywords", "navigate_to_page"
        }
        for name in extra:
            if name in tools and name not in seen:
                allowed.append(tools[name].to_openai_tool())
                seen.add(name)
        return allowed

    def _prepare_tool_input(self, name, tool_input, plan):
        prepared = dict(tool_input or {})
        collection = self._current_collection()

        if name in ("read_page_results", "navigate_to_page"):
            if not prepared.get("page") and plan.get("page"):
                prepared["page"] = plan["page"]
            if not prepared.get("tab") and plan.get("tab"):
                prepared["tab"] = plan["tab"]
            if not prepared.get("query") and plan.get("query"):
                prepared["query"] = plan["query"]
            if not prepared.get("params") and plan.get("params"):
                prepared["params"] = dict(plan.get("params", {}))
            if collection:
                prepared["collection"] = collection
                if isinstance(prepared.get("params"), dict):
                    prepared["params"]["collection"] = collection
                else:
                    prepared["params"] = {"collection": collection}

        if name in ("search_papers",) and collection and not prepared.get("collection"):
            prepared["collection"] = collection

        return prepared

    def _execute_tool(self, name, tool_input, tools):
        if name not in tools:
            return f"Error: Unknown tool '{name}'"
        try:
            return tools[name].execute(**tool_input)
        except Exception as e:
            return f"Error executing {name}: {str(e)}"

    def _append_synthetic_tool_messages(self, messages, tool_name, tool_input, tool_call_id, result):
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

    def _run_synthetic_tool(self, tool_name, tool_input, tools, messages, collected, synthetic_tool_counter):
        synthetic_tool_counter += 1
        tool_call_id = f"synthetic_{tool_name}_{synthetic_tool_counter}"
        yield {
            "type": "tool_use",
            "id": tool_call_id,
            "name": tool_name,
            "input": tool_input,
        }, synthetic_tool_counter

        result = self._execute_tool(tool_name, tool_input, tools)
        self._collect_tool_output(tool_name, tool_input, result, collected)
        self._collect_evidence(tool_name, tool_input, result, collected)
        self._append_synthetic_tool_messages(messages, tool_name, tool_input, tool_call_id, result)
        self._messages = self._history_without_system(messages)

        yield {
            "type": "tool_result",
            "id": tool_call_id,
            "name": tool_name,
            "result": result,
        }, synthetic_tool_counter

    # =========================================================================
    # Result Collection
    # =========================================================================
    def _collect_tool_output(self, tool_name, tool_input, result, collected):
        if tool_name == "navigate_to_page":
            try:
                parsed = json.loads(result) if isinstance(result, str) else result
                if isinstance(parsed, dict) and parsed.get("action") == "navigate":
                    collected["last_navigation"] = parsed
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
                        self._tool_context["collection"] = col
                    collected["page_result_bank"].append(parsed)
                    collected["page_result_bank"] = collected["page_result_bank"][-4:]
            except Exception:
                pass

        collected["tool_result_bank"].append({
            "tool": tool_name,
            "input": tool_input if isinstance(tool_input, dict) else {},
            "result": normalized,
        })
        collected["tool_result_bank"] = collected["tool_result_bank"][-8:]

    def _collect_evidence(self, tool_name, tool_input, result, collected):
        if tool_name != "search_papers":
            return

        import re
        query = tool_input.get("query", "") if isinstance(tool_input, dict) else ""
        existing_keys = set((e.get("filename"), e.get("chunk")) for e in collected["evidence_bank"])
        pattern = re.compile(r"--- Result (\d+) \(score: ([\d.]+)\) ---\nFile: (.+?) \| Chunk: (.+?)\nText: ([\s\S]*?)(?=\n--- Result|$)")
        result_text = result if isinstance(result, str) else ""
        for match in pattern.finditer(result_text):
            filename = (match.group(3) or "").strip()
            chunk = (match.group(4) or "").strip()
            key = (filename, chunk)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            collected["evidence_bank"].append({
                "rank": int(match.group(1)),
                "score": float(match.group(2)),
                "filename": filename,
                "chunk": chunk,
                "excerpt": self._truncate((match.group(5) or "").strip(), 240),
                "query": query,
            })

        collected["evidence_bank"] = sorted(
            collected["evidence_bank"],
            key=lambda item: item.get("score", 0),
            reverse=True
        )[:8]

    def _truncate(self, text, limit=220):
        text = " ".join((text or "").split())
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    def _format_score(self, score):
        if score is None:
            return ""
        try:
            value = float(score)
        except (TypeError, ValueError):
            return ""
        if 0 < value <= 1:
            return f" (유사도 {value:.1%})"
        return f" ({value:.3f})"

    def _summarize_page_result(self, pr, use_korean=True):
        """단일 페이지 결과(read_page_results 반환) → Markdown 요약 블록.

        페이지/탭별 데이터 구조 차이(clusters/papers/predictions/results/matched_patterns 등)를
        모두 처리하여 사용자가 챗봇 답변만 보고도 핵심 결과를 파악할 수 있도록 한다.
        """
        if not isinstance(pr, dict):
            return ""

        page = pr.get("page", "") or ""
        tab = pr.get("tab", "") or ""
        query = pr.get("query", "") or ""
        total = pr.get("total", pr.get("total_hits", pr.get("total_searched", 0))) or 0

        page_label = f"{page}/{tab}" if tab else page

        # 페이지별 항목 컬렉션 후보 (우선순위 순)
        items = []
        item_label = ""
        if page == "research" and tab == "discover":
            items = pr.get("clusters", []) or []
            item_label = "문서"
        elif page == "research" and tab == "recommend":
            items = pr.get("papers", []) or []
            item_label = "추천 논문"
        elif page == "prediction":
            items = pr.get("predictions", []) or []
            item_label = "예측 사례"
        elif page == "theory":
            items = pr.get("results", []) or []
            item_label = "수식 결과"
        elif page == "diagnosis" and tab == "compare":
            method_a = pr.get("method_a") or ""
            method_b = pr.get("method_b") or ""
            common = pr.get("common_doc_count", 0)
            items = (pr.get("results_a", []) or [])[:3] + (pr.get("results_b", []) or [])[:3]
            item_label = f"{method_a} vs {method_b}"
            if not query:
                query = item_label
        elif page == "diagnosis" and tab == "failure":
            items = pr.get("matched_patterns", []) or []
            item_label = "고장 패턴"
        elif page == "diagnosis" and tab == "detection":
            items = pr.get("history", []) or []
            item_label = "이상 이벤트"
        elif page == "diagnosis":
            items = pr.get("results", []) or []
            item_label = "진단 결과"
        else:
            for key in ("results", "data", "items"):
                if isinstance(pr.get(key), list) and pr.get(key):
                    items = pr[key]
                    break
            item_label = "결과"

        if not isinstance(items, list):
            items = []

        item_count = total or len(items)

        lines = []
        if use_korean:
            header = f"**{page_label}** 페이지에서"
            if query:
                header += f" `{query}` 관련"
            header += f" **{item_count}건**의 {item_label}을 확인했습니다."
        else:
            header = f"On **{page_label}** found **{item_count}** {item_label}"
            if query:
                header += f" for `{query}`"
            header += "."
        lines.append(header)

        for idx, item in enumerate(items[:5], 1):
            if not isinstance(item, dict):
                continue

            # 제목 후보
            title = (
                item.get("filename")
                or item.get("title")
                or item.get("name")
                or item.get("doc_id")
                or ""
            )
            if not title:
                continue

            score = item.get("score") or item.get("max_score") or item.get("relevance_score") or item.get("match_score")
            score_text = self._format_score(score)

            year = item.get("year") or item.get("publication_year") or ""
            year_text = f" · {year}" if year else ""

            # 스니펫/설명 후보
            snippet = ""
            if isinstance(item.get("snippets"), list) and item["snippets"]:
                snippet = item["snippets"][0] or ""
            elif item.get("snippet"):
                snippet = item.get("snippet") or ""
            elif item.get("text"):
                snippet = item.get("text") or ""
            elif item.get("excerpt"):
                snippet = item.get("excerpt") or ""

            line = f"{idx}. **{title}**{score_text}{year_text}"
            lines.append(line)
            if snippet:
                lines.append(f"   > {self._truncate(snippet, 180)}")

            # 추가 메타: 진단/예측 도메인
            if isinstance(item.get("causes"), list) and item["causes"]:
                causes = ", ".join(str(c) for c in item["causes"][:3])
                lines.append(f"   · 원인: {causes}")
            if isinstance(item.get("solutions"), list) and item["solutions"]:
                sols = ", ".join(str(s) for s in item["solutions"][:3])
                lines.append(f"   · 해결: {sols}")
            if isinstance(item.get("extracted_values"), list) and item["extracted_values"]:
                vals = ", ".join(str(v) for v in item["extracted_values"][:4])
                lines.append(f"   · 추출값: {vals}")
            if isinstance(item.get("equations"), list) and item["equations"]:
                eq_count = len(item["equations"])
                lines.append(f"   · 수식 {eq_count}개 포함")

        return "\n".join(lines)

    def _build_page_results_summary(self, page_results, use_korean=True, max_pages=3, synthesis=""):
        """page_result_bank를 받아 통합 Markdown 요약을 생성한다.

        synthesis가 주어지면 구조화 리스트 위에 `✨ AI 요약` 블록을 함께 출력한다.
        """
        if not page_results:
            return ""
        blocks = []
        for pr in page_results[:max_pages]:
            block = self._summarize_page_result(pr, use_korean=use_korean)
            if block:
                blocks.append(block)
        if not blocks and not synthesis:
            return ""
        title = "📊 **페이지 조회 결과**" if use_korean else "📊 **Page Results**"
        sections = [title]
        if synthesis:
            synth_label = "✨ **AI 요약**" if use_korean else "✨ **AI Summary**"
            sections.append(f"{synth_label}\n{synthesis.strip()}")
        if blocks:
            list_label = "📝 **상세 결과**" if use_korean else "📝 **Details**"
            sections.append(f"{list_label}\n\n" + "\n\n".join(blocks))
        return "\n\n".join(sections)

    def _build_synthesis_input(self, page_results, max_items_per_page=5):
        """LLM 요약용 입력 텍스트(plain) 생성: 각 페이지 결과의 핵심 메타 + 스니펫만 포함."""
        if not page_results:
            return ""
        lines = []
        for pr in page_results[:3]:
            if not isinstance(pr, dict):
                continue
            page = pr.get("page", "")
            tab = pr.get("tab", "")
            query = pr.get("query", "")
            total = pr.get("total", pr.get("total_hits", pr.get("total_searched", 0))) or 0
            lines.append(f"[페이지: {page}/{tab} | 질의: {query} | 총 {total}건]")

            items = []
            for key in ("clusters", "papers", "predictions", "results", "matched_patterns", "history", "data", "items"):
                val = pr.get(key)
                if isinstance(val, list) and val:
                    items = val
                    break

            for idx, item in enumerate(items[:max_items_per_page], 1):
                if not isinstance(item, dict):
                    continue
                title = item.get("filename") or item.get("title") or item.get("name") or item.get("doc_id") or ""
                year = item.get("year") or item.get("publication_year") or ""
                score = item.get("score") or item.get("max_score") or item.get("relevance_score") or item.get("match_score")
                snippet = ""
                if isinstance(item.get("snippets"), list) and item["snippets"]:
                    snippet = item["snippets"][0] or ""
                elif item.get("snippet"):
                    snippet = item.get("snippet") or ""
                elif item.get("text"):
                    snippet = item.get("text") or ""
                snippet = self._truncate(snippet, 240)
                meta_parts = []
                if year:
                    meta_parts.append(str(year))
                if isinstance(score, (int, float)):
                    meta_parts.append(f"score={score:.3f}")
                meta = (" · ".join(meta_parts))
                lines.append(f"  {idx}. {title}" + (f" ({meta})" if meta else ""))
                if snippet:
                    lines.append(f"     - {snippet}")
            lines.append("")
        return "\n".join(lines).strip()

    def _generate_page_synthesis(self, client, page_results, message, language):
        """페이지 결과를 LLM에게 보내 자연어 요약(3~5문장)을 생성한다.

        실패 시 빈 문자열을 반환하여 본 흐름에 영향을 주지 않는다.
        """
        if not client or not page_results:
            return ""
        synthesis_input = self._build_synthesis_input(page_results)
        if not synthesis_input:
            return ""

        use_korean = language == "ko"
        if use_korean:
            sys_prompt = (
                "당신은 플라즈마/반도체 연구 데이터를 해석하는 분석가입니다. "
                "사용자의 질문과 페이지 조회 결과를 받아, 결과의 핵심 주제·패턴·추천 포인트를 "
                "3~5문장(불릿 1~3개 허용)으로 한국어 요약합니다. "
                "결과에 없는 내용은 추정하지 말고, 결과 항목 자체를 단순 나열하지 마세요. "
                "구체적 인사이트(연도 분포, 공통 키워드, 가장 관련성 높은 항목과 그 이유 등)를 짧게 전달하세요."
            )
            user_prompt = f"사용자 질문: {message}\n\n페이지 조회 결과:\n{synthesis_input}\n\n위 결과를 한국어로 요약해 주세요."
        else:
            sys_prompt = (
                "You analyze plasma/semiconductor research results. "
                "Given the user query and the page results, write a 3-5 sentence English summary "
                "(1-3 bullets allowed) highlighting the main themes, patterns, and the most relevant items with brief reasons. "
                "Do not invent content. Do not just list items."
            )
            user_prompt = f"User query: {message}\n\nPage results:\n{synthesis_input}\n\nSummarize concisely."

        try:
            kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 400,
            }
            if self.temperature is not None:
                kwargs["temperature"] = min(0.3, float(self.temperature))
            if self.top_p is not None:
                kwargs["top_p"] = self.top_p
            response = client.chat.completions.create(**kwargs)
            text = response.choices[0].message.content or ""
            return text.strip()
        except Exception:
            return ""

    def _build_fallback_answer(self, message, collected, language):
        use_korean = language == "ko"
        parts = []
        page_results = collected.get("page_result_bank", [])
        if page_results:
            page_summary = self._build_page_results_summary(
                page_results,
                use_korean=use_korean,
                synthesis=collected.get("page_synthesis", ""),
            )
            if page_summary:
                parts.append(page_summary)

        evidence = collected.get("evidence_bank", [])
        if evidence:
            if use_korean:
                parts.append(f"\n📚 관련 문헌 **{len(evidence)}건**을 검색했습니다.")
            else:
                parts.append(f"\n📚 Found **{len(evidence)}** relevant documents.")
            for item in evidence[:5]:
                filename = item.get("filename", "")
                excerpt = item.get("excerpt", "")
                score = item.get("score", None)
                score_text = self._format_score(score)
                if filename:
                    parts.append(f"- **{filename}**{score_text}")
                if excerpt:
                    parts.append(f"  > {self._truncate(excerpt, 180)}")

        navigation = collected.get("last_navigation")
        if navigation and use_korean:
            parts.append(f"\n🧭 해당 조건으로 **{navigation.get('title_ko') or navigation.get('page')}** 페이지로 이동하여 더 자세한 결과를 확인할 수 있습니다.")
        elif navigation:
            parts.append(f"\n🧭 You can explore more details on the **{navigation.get('title_en') or navigation.get('page')}** page with the same parameters.")

        if parts:
            header = "질문에 대한 검색 결과를 정리했습니다." if use_korean else "Here are the grounded results for your query."
            return header + "\n\n" + "\n".join(parts)

        if use_korean:
            return f"'{message}' 에 대해 검색을 수행했지만 충분한 결과를 확보하지 못했습니다. 다른 키워드로 다시 시도해 주세요."
        return f"The search for '{message}' did not return sufficient results. Please try different keywords."

    def _finalize_answer_text(self, text, collected, language):
        import re

        answer = (text or "").strip()
        if not answer:
            return ""

        use_korean = language == "ko" or re.search(r"[가-힣]", answer) is not None

        answer = re.sub(r"\[([^\]]+)\]\(([^)]*(yourdomain|your-research-platform|유효한 한국어 URL)[^)]*)\)", r"\1", answer)

        # ── 페이지 결과 요약 주입 ──
        # 페이지 조회 결과는 LLM 답변 본문에서 누락되거나 일반화되는 경우가 많으므로,
        # 항상 답변 앞에 구조화된 요약을 명시적으로 삽입한다 (사용자가 이동하지 않고도 확인 가능하도록).
        page_results = collected.get("page_result_bank", [])
        if page_results:
            page_summary = self._build_page_results_summary(
                page_results,
                use_korean=use_korean,
                synthesis=collected.get("page_synthesis", ""),
            )
            if page_summary:
                # 이미 답변에 동일한 페이지 요약 헤더가 있으면 중복 삽입하지 않음
                if "페이지 조회 결과" not in answer and "Page Results" not in answer:
                    answer = f"{page_summary}\n\n---\n\n{answer}"

        navigation = collected.get("last_navigation") or {}
        nav_url = str(navigation.get("url") or "").strip()
        nav_title = str(
            navigation.get("title_ko") if use_korean else navigation.get("title_en")
            or navigation.get("title_ko")
            or navigation.get("title_en")
            or navigation.get("page")
            or ""
        ).strip()

        if not nav_url:
            return answer

        has_link_target = bool(re.search(r"\[[^\]]+\]\((https?://[^)]+|/[^)]*)\)", answer)) or bool(re.search(r"https?://\S+", answer))

        if has_link_target:
            answer = re.sub(r"\[([^\]]+)\]\((https?://[^)]+|/[^)]*)\)", r"\1", answer)
            answer = re.sub(r"https?://\S+", "", answer)
            answer = re.sub(r"\s{2,}", " ", answer).strip()
            answer = answer.replace("아래 링크를 클릭하면", "아래 경로로 이동하면")
            answer = answer.replace("링크를 클릭하세요", "경로로 이동하세요")

        if nav_url in answer and not has_link_target:
            return answer

        if use_korean:
            handoff = f"\n\n🧭 해당 조건으로 **{nav_title or '대상'}** 페이지로 이동하여 더 자세한 결과를 확인할 수 있습니다."
        else:
            handoff = f"\n\n🧭 You can explore more details on the **{nav_title or 'target'}** page with the same parameters."

        return answer + handoff

    # =========================================================================
    # Public API
    # =========================================================================
    def get_tools(self):
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]

    def get_history(self):
        return list(self._messages)

    def clear_history(self):
        self._messages = []


Model = Agent
