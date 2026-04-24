# =============================================================================
# OrchestratorAgent — 최상위 조율 에이전트
# =============================================================================
# 역할: 사용자 질문을 받아 하위 에이전트를 순차 호출하고,
#        전체 실행 흐름을 조율하며, SSE 이벤트를 생성
#
# 흐름:
#   1. KeywordAgent  → 키워드 추출 / 의도 분류 / 파라미터 매핑
#   2. RouterAgent   → 실행 계획(plan) 수립, 도구 순서 결정
#   3. PatentAgent   → 특허 검색 필요 시 KIPRIS API 호출
#   4. CollectorAgent → OpenAI tool-calling 루프로 페이지 결과/문헌 수집
#   5. SynthesizerAgent → LLM이 모든 근거를 읽고 최종 답변 생성
# =============================================================================

import json

try:
    from .base_agent import BaseAgent
    from .keyword_agent import KeywordAgent
    from .router_agent import RouterAgent
    from .collector_agent import CollectorAgent
    from .patent_agent import PatentAgent
    from .synthesizer_agent import SynthesizerAgent
except ImportError:
    from base_agent import BaseAgent
    from keyword_agent import KeywordAgent
    from router_agent import RouterAgent
    from collector_agent import CollectorAgent
    from patent_agent import PatentAgent
    from synthesizer_agent import SynthesizerAgent


class OrchestratorAgent(BaseAgent):
    name = "orchestrator"
    description = "사용자 질문을 분석하고 하위 에이전트를 순차 호출하여 전체 실행 흐름을 조율합니다."

    def __init__(self, ctx):
        super().__init__(ctx)
        # 하위 에이전트 인스턴스 생성
        self.keyword_agent = KeywordAgent(ctx)
        self.router_agent = RouterAgent(ctx)
        self.collector_agent = CollectorAgent(ctx)
        self.patent_agent = PatentAgent(ctx)
        self.synthesizer_agent = SynthesizerAgent(ctx)

    def run(self, message="", history=None, tools=None, **kwargs):
        """오케스트레이터 실행 루프 — SSE 이벤트를 yield.

        기존 Agent.run()과 동일한 SSE 이벤트 체계를 유지하여
        프론트엔드(component.chat.floating, page.agent.v2)와 완벽 호환.

        Args:
            message: 사용자 질문
            history: 대화 히스토리 (list of dicts)
            tools: 사용 가능한 도구 dict (name -> tool instance)

        Yields:
            SSE 이벤트 dict
        """
        client = self.ctx.get("client")
        model = self.ctx.get("model", "google/gemma-4-26B-A4B-it")
        collection = self._current_collection()

        if not client:
            yield {"type": "error", "message": "LLM 클라이언트가 초기화되지 않았습니다."}
            return

        tools = tools or {}

        # =====================================================================
        # Phase 1: KeywordAgent — 키워드 추출 + 의도 분류
        # =====================================================================
        classification = self.keyword_agent.run(message=message)
        classification["collection"] = collection
        language = classification.get("language", "ko")
        difficulty = classification.get("difficulty", "빠른 응답")

        # =====================================================================
        # Phase 2: RouterAgent — 실행 계획 수립
        # =====================================================================
        plan = self.router_agent.run(classification=classification)
        plan["collection"] = collection

        # =====================================================================
        # SSE: 오케스트레이션 스냅샷 (기존 프론트엔드 호환)
        # =====================================================================
        memory_context = self._build_memory_context(history, message)

        yield self._build_orchestration_snapshot(
            memory_context, plan, language, difficulty
        )

        yield self._pipeline_event(
            "prompt", "running",
            f"시스템 프롬프트와 사용자 질문을 결합해 {model} 실행 컨텍스트를 구성하고 있습니다.",
            language=language, model=model, collection=collection or "미선택",
            metaBadges=[language, model, collection or "컬렉션 미선택"],
        )

        yield self._pipeline_event(
            "memory", "running",
            "대화 이력, 최근 질문, 선택 컬렉션을 세션 메모리로 정리하고 있습니다.",
            history_turns=memory_context.get("history_turns", 0),
            collection=collection or "미선택",
            metaBadges=[f"이력 {memory_context.get('history_turns', 0)}턴", f"컬렉션 {collection or '미선택'}"],
        )

        yield self._pipeline_event(
            "orchestrator", "running",
            f"{plan.get('category')} 흐름으로 분류하고, {', '.join(plan.get('recommended_tools', []))} 순으로 실행을 계획하고 있습니다.",
            category=plan.get("category"), page=plan.get("page"), tab=plan.get("tab"),
            plan=plan.get("plan", []),
            metaBadges=[plan.get("category"), plan.get("page"), plan.get("tab")],
        )

        # =====================================================================
        # Phase 2.5: 시스템 프롬프트 & 메시지 히스토리 구성
        # =====================================================================
        system_prompt = self._build_system_prompt(plan, memory_context, collection, tools)

        messages = self._build_messages(system_prompt, history, message)

        yield self._pipeline_event(
            "prompt", "done",
            "프롬프트 레이어가 시스템 규칙, 메모리, 오케스트레이션 계획을 포함하도록 확정되었습니다.",
            language=language, model=model, collection=collection or "미선택",
            metaBadges=[language, model, collection or "컬렉션 미선택"],
        )

        yield self._pipeline_event(
            "memory", "done",
            f"세션 메모리에 최근 질문 {len(memory_context.get('recent_user_queries', []))}건과 컬렉션 정보를 반영했습니다.",
            history_turns=memory_context.get("history_turns", 0),
            collection=collection or "미선택",
            metaBadges=[f"이력 {memory_context.get('history_turns', 0)}턴", f"컬렉션 {collection or '미선택'}"],
        )

        yield self._pipeline_event(
            "orchestrator", "done",
            f"실행 경로를 {plan.get('page')} / {plan.get('tab')} 중심으로 확정했습니다.",
            category=plan.get("category"), page=plan.get("page"), tab=plan.get("tab"),
            plan=plan.get("plan", []),
            metaBadges=[plan.get("category"), plan.get("page"), plan.get("tab")],
        )

        yield self._pipeline_event(
            "tools", "pending",
            "필요한 검색/분석/이동 도구 실행을 대기하고 있습니다.",
            tool_count=0, metaBadges=["0개 실행"],
        )

        yield self._pipeline_event(
            "streaming", "running",
            "SSE 스트림을 열고 실행 상태를 프론트 UI에 전달하고 있습니다.",
            transport="SSE", mode="실시간 UI", metaBadges=["SSE", "실시간 UI"],
        )

        # =====================================================================
        # Phase 3: PatentAgent — 특허 검색 (병렬 가능, 여기서는 선행 실행)
        # =====================================================================
        patent_data = self.patent_agent.run(
            message=message, classification=classification
        )

        # =====================================================================
        # Phase 4: CollectorAgent — 도구 실행 + 결과 수집
        # =====================================================================
        draft_answer = ""
        for event in self.collector_agent.run(
            plan=plan, message=message, tools=tools,
            client=client, messages=messages,
        ):
            event_type = event.get("type", "")

            # 내부 완료 이벤트
            if event_type == "_collector_done":
                draft_answer = event.get("content", "")
                continue

            # 나머지 SSE 이벤트는 그대로 전달
            yield event

        # CollectorAgent 수집 데이터 가져오기
        collected_data = self.collector_agent.get_collected_data()
        collection = self._current_collection()

        used_tools = len(collected_data.get("tool_result_bank", [])) > 0

        if used_tools:
            yield self._pipeline_event(
                "tools", "done",
                f"수집된 근거 {len(collected_data.get('evidence_bank', []))}건과 도구 결과를 답변 구조에 반영했습니다.",
                tool_count=len(collected_data.get("tool_result_bank", [])),
                metaBadges=[f"근거 {len(collected_data.get('evidence_bank', []))}건"],
            )
        else:
            yield self._pipeline_event(
                "tools", "skipped",
                "추가 도구 없이 프롬프트와 메모리만으로 답변을 생성했습니다.",
                tool_count=0, metaBadges=["도구 미사용"],
            )

        # =====================================================================
        # Phase 5: 최종 답변 (Claude-style — draft_answer 직접 사용)
        # =====================================================================
        # CollectorAgent의 LLM이 도구 결과를 보고 생성한 텍스트를 최종 답변으로 사용
        # SynthesizerAgent를 거치지 않아 실패 없이 즉시 답변 전달
        final_answer = (draft_answer or "").strip()

        # draft가 비어있으면 수집된 결과에서 폴백 답변 구성
        if not final_answer:
            final_answer = self._build_fallback_answer(
                message, collected_data, patent_data, language
            )

        # 근거 데이터 추출
        evidence_bank = collected_data.get("evidence_bank", [])
        page_result_bank = collected_data.get("page_result_bank", [])
        evidence_count = len(evidence_bank)

        # 품질 보고서 (LLM 없이 직접 구성)
        quality_report = {
            "stage": "direct",
            "detail": f"수집된 근거 {evidence_count}건을 기반으로 답변을 생성했습니다." if language == "ko" else f"Answer generated from {evidence_count} evidence items.",
            "answerStyle": "도구 실행 결과 기반 응답" if language == "ko" else "Tool-result grounded response",
            "confidence": "high" if evidence_count > 3 else ("medium" if evidence_count > 0 else "low"),
            "evidenceCount": evidence_count,
            "llmUsed": False,
        }

        # evidence_items 구축
        evidence_items = []
        for item in evidence_bank[:10]:
            evidence_items.append({
                "doc_id": item.get("doc_id", ""),
                "filename": item.get("filename", ""),
                "score": item.get("score"),
                "snippets": [item.get("excerpt", "")][:2] if item.get("excerpt") else [],
            })

        yield self._pipeline_event(
            "orchestrator", "running",
            "수집된 도구 결과를 최종 답변으로 정리하고 있습니다.",
            category=plan.get("category"), page=plan.get("page"), tab=plan.get("tab"),
            metaBadges=[plan.get("category"), "답변 정리"],
        )

        # SSE: 품질 보고서
        yield {
            "type": "quality",
            "stage": quality_report.get("stage", "direct"),
            "detail": quality_report.get("detail", ""),
            "answerStyle": quality_report.get("answerStyle", ""),
            "confidence": quality_report.get("confidence", ""),
            "evidenceCount": quality_report.get("evidenceCount", 0),
            "llmUsed": False,
        }

        # SSE: evidence_items (아코디언 UI)
        if evidence_items:
            yield {
                "type": "evidence_items",
                "items": evidence_items,
            }

        # SSE: 최종 답변
        yield self._pipeline_event(
            "orchestrator", "done",
            quality_report.get("detail", "답변 정리를 완료했습니다."),
            category=plan.get("category"), page=plan.get("page"), tab=plan.get("tab"),
            metaBadges=[plan.get("category"), quality_report.get("answerStyle", "직접 응답")],
        )

        yield self._pipeline_event(
            "memory", "done",
            f"근거 {evidence_count}건 기반으로 답변을 완료했습니다.",
            history_turns=memory_context.get("history_turns", 0),
            collection=self._current_collection() or "미선택",
            metaBadges=[f"근거 {evidence_count}건"],
        )

        yield self._pipeline_event(
            "streaming", "running",
            "답변을 스트리밍 UI로 전달하고 있습니다.",
            transport="SSE", mode="답변 전달", metaBadges=["SSE", "답변 전달"],
        )

        yield {"type": "text", "content": final_answer}

        yield self._pipeline_event(
            "streaming", "done",
            "답변 전달을 완료했습니다.",
            transport="SSE", mode="완료", metaBadges=["SSE 완료"],
        )

        yield {"type": "done", "content": ""}

    # =========================================================================
    # 히스토리 구성
    # =========================================================================
    def _build_memory_context(self, history, message):
        history = history or []
        chat_turns = [h for h in history if h.get("role") in ("user", "assistant")]
        recent_user_queries = [h.get("content", "") for h in chat_turns if h.get("role") == "user"][-3:]
        current_message = (message or "").strip()
        return {
            "collection": self._current_collection(),
            "history_turns": len(chat_turns),
            "recent_user_queries": [q for q in recent_user_queries if q],
            "current_message": current_message,
            "last_topic": recent_user_queries[-1] if recent_user_queries else current_message,
        }

    def _current_collection(self):
        return (self.ctx.get("collection", "") or "").strip()

    def _build_fallback_answer(self, message, collected_data, patent_data, language):
        """draft_answer가 비어있을 때 수집된 결과에서 폴백 답변을 구성."""
        collected_data = collected_data or {}
        parts = []

        # 페이지 결과에서 요약 추출
        page_results = collected_data.get("page_result_bank", [])
        if page_results:
            for pr in page_results[:3]:
                page = pr.get("page", "")
                tab = pr.get("tab", "")
                query = pr.get("query", "")
                total = pr.get("total", pr.get("total_hits", pr.get("total_searched", 0)))
                if page and tab:
                    if language == "ko":
                        parts.append(f"**{page}/{tab}** 페이지에서 '{query}' 검색 결과 **{total}건**을 확인했습니다.")
                    else:
                        parts.append(f"Found **{total}** results for '{query}' on **{page}/{tab}**.")
                # 결과 데이터에서 핵심 정보 추출
                results = pr.get("results", pr.get("data", []))
                if isinstance(results, list):
                    for item in results[:5]:
                        if isinstance(item, dict):
                            title = item.get("title", item.get("name", item.get("doc_id", "")))
                            if title:
                                parts.append(f"- {title}")

        # 근거에서 정보 추출
        evidence = collected_data.get("evidence_bank", [])
        if evidence and not page_results:
            if language == "ko":
                parts.append(f"관련 문헌 **{len(evidence)}건**을 검색했습니다.")
            else:
                parts.append(f"Found **{len(evidence)}** relevant documents.")
            for ev in evidence[:5]:
                excerpt = ev.get("excerpt", "")
                if excerpt:
                    parts.append(f"- {excerpt[:200]}")

        # 도구 결과 요약
        tool_results = collected_data.get("tool_result_bank", [])
        if tool_results and not parts:
            for tr in tool_results[:3]:
                tool_name = tr.get("tool", "")
                result_text = str(tr.get("result", ""))[:300]
                if tool_name and result_text:
                    parts.append(f"**{tool_name}**: {result_text}")

        # 특허 정보
        if patent_data and isinstance(patent_data, dict):
            patents = patent_data.get("patents", [])
            if patents:
                if language == "ko":
                    parts.append(f"\n관련 특허 **{len(patents)}건**을 확인했습니다.")
                else:
                    parts.append(f"\nFound **{len(patents)}** related patents.")
                for p in patents[:3]:
                    title = p.get("title", "")
                    if title:
                        parts.append(f"- {title}")

        if parts:
            header = "질문에 대한 검색 결과를 정리했습니다." if language == "ko" else "Here are the search results for your query."
            return f"{header}\n\n" + "\n".join(parts)

        # 아무 결과도 없는 경우
        if language == "ko":
            return f"'{message}' 에 대해 검색을 수행했으나 충분한 결과를 확보하지 못했습니다. 다른 키워드로 다시 시도해 주세요."
        return f"The search for '{message}' did not return sufficient results. Please try with different keywords."

    def _sanitize_history(self, history):
        """OpenAI 호환 히스토리로 정리."""
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
                if role != "tool":
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
        """시스템 프롬프트 + 히스토리 + 신규 메시지로 messages 배열 구성."""
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            sanitized = self._sanitize_history(history)
            # 기존 시스템 메시지 제거
            for h in sanitized:
                if h.get("role") != "system":
                    messages.append(h)
        messages.append({"role": "user", "content": message})
        return messages

    # =========================================================================
    # 시스템 프롬프트
    # =========================================================================
    def _build_system_prompt(self, plan, memory_context, collection, tools):
        tool_descs = "\n".join([f"- **{t.name}**: {t.description}" for t in tools.values()])

        collection_info = ""
        if collection:
            collection_info = f"\n## Current Milvus Collection\nSelected: **`{collection}`**. Pass it to all tools that accept a collection parameter.\n"

        recent_queries = "\n".join([f"- {q}" for q in memory_context.get("recent_user_queries", [])]) or "- No previous turns"
        memory_section = f"""
## Session Memory
- Collection: {memory_context.get('collection', collection or 'none')}
- Turns: {memory_context.get('history_turns', 0)}
- Latest topic: {memory_context.get('last_topic', '')}
- Recent queries:
{recent_queries}
"""

        plan_lines = "\n".join([f"- {p}" for p in plan.get("plan", [])])
        tool_lines = ", ".join(plan.get("recommended_tools", []))
        orchestrator_section = f"""
## Orchestrator Plan
- Category: {plan.get('category', 'unknown')}
- Target: {plan.get('page', '-')}/{plan.get('tab', '-')}
- Goal: {plan.get('goal', 'produce a grounded answer')}
- Tools: {tool_lines}
- Keywords: {', '.join(plan.get('keywords', []))}
- Plan:
{plan_lines}
"""

        return f"""You are an expert AI research assistant specialized in plasma science and engineering.
You have access to a vector database of plasma research papers and powerful analysis tools.
{collection_info}
{memory_section}
{orchestrator_section}

## Available Tools
{tool_descs or 'none'}

## Workflow
1. Classify the question into one of 8 categories
2. Extract keywords and parameters
3. Execute tools (read_page_results, search, analysis, etc.)
4. Synthesize results in the user's language (Korean for Korean questions)
5. Call navigate_to_page as the final tool call (MANDATORY)
6. Provide a final human-readable answer

## CRITICAL: Language Rule
Always answer in the user's language. All summaries and final answers must be in the user's language.

## Evidence Rule
Never dump raw DB chunks. Synthesize evidence into structured findings.
"""

    # =========================================================================
    # SSE 이벤트 헬퍼
    # =========================================================================
    def _pipeline_event(self, component, status, detail, **meta):
        badges = meta.pop("metaBadges", None)
        event = {
            "type": "pipeline",
            "component": component,
            "status": status,
            "detail": detail,
            "meta": meta,
        }
        if badges is not None:
            event["metaBadges"] = badges
        return event

    def _build_orchestration_snapshot(self, memory_context, plan, language, difficulty):
        collection = self.ctx.get("collection", "") or "미선택"
        category = plan.get("category", "주제 발굴")
        page = plan.get("page", "research")
        tab = plan.get("tab", "discover")
        keywords = ", ".join(plan.get("keywords", [])[:5]) or "없음"

        trace_steps = [
            {"id": 1, "title": "질문 수신", "summary": "새로운 사용자 질문을 등록했습니다.", "status": "done"},
            {"id": 2, "title": "언어 판별", "summary": f"응답 언어를 {'한국어' if language == 'ko' else '영어'}로 결정했습니다.", "status": "done"},
            {"id": 3, "title": "도메인 분류", "summary": f"{category} 영역으로 분류했습니다.", "status": "done"},
            {"id": 4, "title": "질문 난이도 판정", "summary": f"{difficulty} 수준 응답을 준비합니다.", "status": "done"},
            {"id": 5, "title": "키워드 추출", "summary": f"추출 키워드: {keywords}", "status": "done"},
            {"id": 6, "title": "파라미터 매핑", "summary": "페이지 실행용 파라미터를 구성합니다.", "status": "running"},
            {"id": 7, "title": "목표 페이지 선정", "summary": f"대상: {page}/{tab}", "status": "pending"},
            {"id": 8, "title": "오케스트레이션 계획", "summary": ", ".join(plan.get("recommended_tools", [])) or "도구 계획 없음", "status": "pending"},
            {"id": 9, "title": "컬렉션 확인", "summary": f"선택 컬렉션: {collection}", "status": "done" if self.ctx.get("collection") else "running"},
            {"id": 10, "title": "페이지 결과 추출", "summary": "페이지가 실제로 보여줄 결과를 읽습니다.", "status": "pending"},
            {"id": 11, "title": "문헌·근거 수집", "summary": "문헌·도구 결과에서 핵심 근거를 모읍니다.", "status": "pending"},
            {"id": 12, "title": "메모리 반영", "summary": "수집된 근거를 세션 메모리에 반영합니다.", "status": "pending"},
            {"id": 13, "title": "추가 도구 실행", "summary": "후속 분석 도구를 실행합니다.", "status": "pending"},
            {"id": 14, "title": "답변 통합", "summary": "도구 결과를 읽기 쉬운 답변으로 통합합니다.", "status": "pending"},
            {"id": 15, "title": "품질 검증", "summary": "근거 정합성과 표현 품질을 점검합니다.", "status": "pending"},
            {"id": 16, "title": "페이지 핸드오프", "summary": f"대상 페이지는 {page}/{tab} 입니다.", "status": "pending"},
        ]

        pipeline_components = [
            {"key": "prompt", "title": "프롬프트", "icon": "🧠", "status": "running",
             "summary": "시스템 프롬프트와 사용자 질문을 결합합니다.",
             "metaBadges": [language, self.ctx.get("model", "google/gemma-4-26B-A4B-it"), collection]},
            {"key": "orchestrator", "title": "오케스트레이터", "icon": "🗺️", "status": "running",
             "summary": "실행 순서와 도구 계획을 수립합니다.",
             "metaBadges": [category, difficulty], "plan": plan.get("plan", [])},
            {"key": "tools", "title": "도구", "icon": "🧰", "status": "pending",
             "summary": "검색·분석·이동 도구를 실행합니다.", "metaBadges": ["0개 실행"]},
            {"key": "memory", "title": "메모리", "icon": "🗂️", "status": "pending",
             "summary": "대화 이력과 컬렉션을 컨텍스트에 반영합니다.",
             "metaBadges": [f"이력 {memory_context.get('history_turns', 0)}턴", f"컬렉션 {collection}"]},
            {"key": "streaming", "title": "스트리밍 UI", "icon": "📡", "status": "pending",
             "summary": "SSE 이벤트로 실행 과정을 표시합니다.", "metaBadges": ["SSE 대기"]},
        ]

        return {
            "type": "orchestration",
            "category": category,
            "page": page,
            "tab": tab,
            "keywords": plan.get("keywords", []),
            "recommended_tools": plan.get("recommended_tools", []),
            "plan": plan.get("plan", []),
            "execution_plan": {
                "category": category,
                "page": page,
                "tab": tab,
                "goal": plan.get("goal"),
                "keywords": plan.get("keywords", []),
                "agent_clusters": plan.get("agent_clusters", []),
                "recommended_tools": plan.get("recommended_tools", []),
                "plan_lines": plan.get("plan", []),
                "collection": self._current_collection(),
                "params": plan.get("params", {}),
                "goal_status": "running",
            },
            "language": language,
            "difficulty": difficulty,
            "collection": self._current_collection(),
            "trace_steps": trace_steps,
            "pipeline_components": pipeline_components,
            "currentLabel": "오케스트레이션 계획 수립",
            "currentDescription": f"{category} 흐름으로 질문을 분류하고 키워드·파라미터·페이지 이동·결과 추출 순서를 계획했습니다.",
        }
