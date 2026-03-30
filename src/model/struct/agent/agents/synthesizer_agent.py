# =============================================================================
# SynthesizerAgent — LLM 기반 최종 답변 요약·생성
# =============================================================================
# 역할: 수집된 모든 근거(페이지 결과, 문헌, 도구 출력, 특허)를 LLM이 읽고
#        사용자 질문에 맞는 형태로 요약·정리하여 최종 답변을 생성
# =============================================================================

import json
import re
import os
from collections import Counter

try:
    from .base_agent import BaseAgent
except ImportError:
    from base_agent import BaseAgent


class SynthesizerAgent(BaseAgent):
    name = "synthesizer"
    description = "수집된 근거를 LLM이 읽고 해석하여 사용자 질문에 맞는 최종 답변을 생성합니다."

    def run(self, message="", plan=None, collected_data=None,
            patent_data=None, draft_answer="", language="ko", **kwargs):
        """LLM 기반 최종 답변 생성.

        Args:
            message: 사용자 원본 메시지
            plan: 오케스트레이터 계획 (category, page, tab 등)
            collected_data: CollectorAgent가 수집한 데이터
            patent_data: PatentAgent가 수집한 특허 데이터
            draft_answer: CollectorAgent가 생성한 초안 답변
            language: 응답 언어 ("ko" or "en")

        Returns:
            dict with 'answer', 'quality_report', 'evidence_items'
        """
        plan = plan or {}
        collected_data = collected_data or {}
        patent_data = patent_data or {}
        client = self.ctx.get("client")
        model = self.ctx.get("model", "gpt-4o")

        evidence_bank = collected_data.get("evidence_bank", [])
        tool_result_bank = collected_data.get("tool_result_bank", [])
        page_result_bank = collected_data.get("page_result_bank", [])
        navigation = collected_data.get("last_navigation")

        # 1. 페이지 결과 기반 1차 답변 구축
        page_answer = self._build_page_grounded_answer(
            message, page_result_bank, navigation, language
        )

        # 2. 특허 정보 통합
        patent_section = self._build_patent_section(patent_data, language)

        # 3. 페이지 결과에서 텍스트 스니펫 수집
        derived_snips = self._collect_text_snippets(page_result_bank)
        derived_terms = self._extract_top_keywords(derived_snips, limit=10)
        page_result_bundle = self._build_page_result_llm_bundle(page_result_bank)
        patent_bundle = self._serialize_patents_for_llm(patent_data)

        # 4. LLM으로 최종 답변 정제
        final_answer = page_answer or draft_answer or ""
        quality_report = self._build_base_quality_report(
            language, evidence_bank, tool_result_bank, page_result_bank
        )

        if client and (page_result_bank or evidence_bank or tool_result_bank or draft_answer or patent_bundle):
            refined = self._refine_with_llm(
                client, model, message, plan, language,
                draft_answer, page_answer, patent_section,
                evidence_bank, tool_result_bank, page_result_bank,
                navigation, derived_snips, derived_terms,
                page_result_bundle, patent_bundle,
            )
            if refined:
                final_answer = refined.get("answer", final_answer)
                if refined.get("quality_report"):
                    quality_report.update(refined["quality_report"])
                if refined.get("evidence_items"):
                    quality_report["evidence_items"] = refined["evidence_items"]

        if client and (not quality_report.get("llmUsed")) and (page_result_bank or evidence_bank or patent_bundle):
            plain_answer = self._synthesize_plaintext_with_llm(
                client, model, message, plan, language,
                draft_answer, page_answer, evidence_bank,
                tool_result_bank, page_result_bundle, patent_bundle,
            )
            if plain_answer:
                final_answer = plain_answer
                quality_report.update({
                    "detail": "LLM이 페이지별 결과 데이터와 검색 근거를 읽고 해석한 뒤 최종 답변을 생성했습니다." if language == "ko" else "The LLM interpreted page-level results and evidence before answering.",
                    "answerStyle": "페이지 결과 해석 기반 응답" if language == "ko" else "Page-result interpreted synthesis",
                    "llmUsed": True,
                })

        # 5. 한국어 최종 보강
        if language == "ko" and page_result_bank and not quality_report.get("llmUsed"):
            final_answer = self._ensure_rich_korean(final_answer, message, page_result_bank)

        # 6. 특허 섹션 병합
        if patent_section and not quality_report.get("llmUsed") and patent_section not in (final_answer or ""):
            final_answer = (final_answer or "").rstrip() + "\n\n" + patent_section

        # Evidence items
        evidence_items = quality_report.get("evidence_items") or self._build_evidence_items(page_result_bank)

        return {
            "answer": final_answer,
            "quality_report": quality_report,
            "evidence_items": evidence_items,
        }

    # =========================================================================
    # LLM 정제
    # =========================================================================
    def _refine_with_llm(self, client, model, message, plan, language,
                         draft_answer, page_answer, patent_section,
                         evidence_bank, tool_result_bank, page_result_bank,
                         navigation, derived_snips, derived_terms,
                         page_result_bundle, patent_bundle):
        """OpenAI LLM을 사용하여 최종 답변을 정제."""

        # 근거 줄
        evidence_lines = []
        for idx, item in enumerate(evidence_bank[:5], 1):
            evidence_lines.append(
                f"[{idx}] file={item.get('filename')} | score={item.get('score')} | excerpt={item.get('excerpt')}"
            )

        tool_lines = []
        for idx, item in enumerate(tool_result_bank[-5:], 1):
            tool_query = (item.get("input") or {}).get("query", "")
            tool_lines.append(
                f"[{idx}] tool={item.get('tool')} | query={tool_query} | result={item.get('result')}"
            )

        page_result_lines = []
        for idx, item in enumerate(page_result_bank[-3:], 1):
            page = item.get("page", "-")
            tab = item.get("tab", "-")
            total = item.get("total", item.get("total_hits", item.get("total_searched", 0)))
            page_result_lines.append(
                f"[{idx}] page={page} | tab={tab} | query={item.get('query', '')} | total={total} | data={json.dumps(item, ensure_ascii=False)[:2400]}"
            )

        navigation_line = ""
        if navigation and isinstance(navigation, dict):
            navigation_line = f"page={navigation.get('page')} | tab={navigation.get('tab')} | query={navigation.get('query')}"

        derived_block = "\n".join(
            [f"- top_terms: {', '.join(derived_terms)}" if derived_terms else "- top_terms: (none)"] +
            [f"- sample_snippets: {derived_snips[0][:180]}" if derived_snips else "- sample_snippets: (none)"]
        )

        system_prompt = (
            "너는 검색 근거를 조합해 최종 답변을 다듬는 품질 향상기다. "
            "Always answer in the user's language regardless of the context language. "
            "`read_page_results`로 확보한 페이지 결과는 해당 페이지가 실제로 보여줄 1차 근거이므로 가장 우선해서 사용하라. "
            "페이지 결과 JSON과 그 요약 번들을 충분히 읽고, 결과가 말해주는 주제/조건/수치/한계를 먼저 해석한 뒤 답변하라. "
            "원문 DB 결과를 그대로 나열하지 말고, 중복을 제거하고 핵심 주장·조건·수치·한계를 통합해 전문가형 답변으로 재작성하라. "
            "논문 제목·파일명·PDF 이름·원문 인용 조각은 최종답변에 직접 노출하지 마라. "
            "반드시 JSON만 반환하고, 키는 answer, evidence_items, synthesis_points, verification_checks, confidence, answer_style 를 사용하라. "
            "answer 구조: '핵심 결론' 헤딩 뒤에 여러 문단(1.개괄 2.상세분석 3.시사점), '근거' 헤딩 뒤에 2~3줄 요약. "
            "evidence_items: 페이지 결과의 개별 문헌을 {doc_id, filename, score, snippets} 배열로."
        )

        user_prompt = f"""
Question: {message}
Draft answer: {draft_answer or page_answer or '(empty)'}
Category: {plan.get('category', '-')}
Target: {plan.get('page', '-')}/{plan.get('tab', '-')}
Collection: {self.ctx.get('collection', '-')}

Evidence: {os.linesep.join(evidence_lines) or '(none)'}
Tool outputs: {os.linesep.join(tool_lines) or '(none)'}
Page result bundle: {json.dumps(page_result_bundle, ensure_ascii=False)[:9000] if page_result_bundle else '(none)'}
Page results: {os.linesep.join(page_result_lines) or '(none)'}
Derived signals: {derived_block}
Navigation: {navigation_line or '(none)'}
Patent info: {json.dumps(patent_bundle, ensure_ascii=False)[:4000] if patent_bundle else (patent_section or '(none)')}

Requirements:
- Structure: '핵심 결론' + multiple paragraphs + '근거' section
- Korean answer for Korean questions
- Do NOT expose raw filenames
- Include ALL documents in evidence_items
- Prioritize the page result bundle over the draft answer. The final answer must be grounded in interpreted page results, not in rule-based template text.
- Explain what the page results imply for the user's specific question, not just what was searched.
""".strip()

        attempts = [
            {
                "system": system_prompt,
                "user": user_prompt,
                "max_tokens": 2200,
            },
            {
                "system": system_prompt + " JSON 파싱 실패 시에도 반드시 단일 JSON 객체만 반환하라.",
                "user": user_prompt + "\nRetry instruction: 출력 시작과 끝은 반드시 { 와 } 여야 하며, 설명 문장은 JSON 밖에 두지 마라.",
                "max_tokens": 2200,
            },
        ]

        for attempt in attempts:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": attempt["system"]},
                        {"role": "user", "content": attempt["user"]},
                    ],
                    max_tokens=attempt["max_tokens"],
                )
                parsed = self._extract_json(response.choices[0].message.content or "")
                if not parsed:
                    continue

                answer = (parsed.get("answer") or "").strip()
                if language == "ko" and not re.search(r"[가-힣]", answer):
                    continue

                return {
                    "answer": answer,
                    "quality_report": {
                        "detail": "LLM이 페이지별 결과 데이터와 도구 결과를 직접 읽고 해석한 뒤 최종 답변을 재구성했습니다." if language == "ko" else "The LLM read and interpreted page-level results before generating the final answer.",
                        "answerStyle": parsed.get("answer_style", "페이지 결과 해석 기반 응답" if language == "ko" else "Page-result interpreted synthesis"),
                        "confidence": parsed.get("confidence", "중간"),
                        "synthesisPoints": parsed.get("synthesis_points", []),
                        "verificationChecks": parsed.get("verification_checks", []),
                        "llmUsed": True,
                    },
                    "evidence_items": parsed.get("evidence_items", []),
                }
            except Exception:
                continue

        return None

    # =========================================================================
    # 페이지 결과 기반 답변
    # =========================================================================
    def _build_page_grounded_answer(self, message, page_results, navigation, language):
        if not page_results or language != "ko":
            return None

        pr = page_results[-1] if isinstance(page_results[-1], dict) else None
        if not pr:
            return None

        page = pr.get("page", "-")
        tab = pr.get("tab", "-")
        query = pr.get("query", message)
        total = pr.get("total", pr.get("total_hits", pr.get("total_searched", 0)))

        count_text = f"{total}건" if total else "다수의 결과"
        p1 = f"'{query}' 키워드로 {page}/{tab} 페이지를 실행해 관련 결과 {count_text}을 확인했습니다."

        return f"핵심 결론\n\n{p1}"

    def _synthesize_plaintext_with_llm(self, client, model, message, plan, language,
                                       draft_answer, page_answer, evidence_bank,
                                       tool_result_bank, page_result_bundle, patent_bundle):
        evidence_text = "\n".join([
            f"- score={item.get('score')} excerpt={item.get('excerpt')}"
            for item in evidence_bank[:6]
        ]) or "(none)"
        tool_text = "\n".join([
            f"- tool={item.get('tool')} result={item.get('result')}"
            for item in tool_result_bank[-6:]
        ]) or "(none)"
        prompt = f"""
사용자 질문: {message}
카테고리: {plan.get('category', '-')}
대상 페이지: {plan.get('page', '-')}/{plan.get('tab', '-')}
초안 답변: {draft_answer or page_answer or '(empty)'}

페이지 결과 번들:
{json.dumps(page_result_bundle, ensure_ascii=False)[:10000] if page_result_bundle else '(none)'}

검색 근거:
{evidence_text}

도구 결과:
{tool_text}

특허 결과:
{json.dumps(patent_bundle, ensure_ascii=False)[:4000] if patent_bundle else '(none)'}

요구사항:
- 반드시 사용자의 언어로 답하라.
- 페이지 결과가 말해주는 주제, 조건, 수치, 시사점을 먼저 해석하라.
- 단순 링크 안내나 규칙형 템플릿 문장으로 끝내지 마라.
- 최종 답변은 사용자의 질문에 직접 답하는 형태여야 한다.
- raw filename, pdf 경로, 영어 문헌 목록을 그대로 나열하지 마라.
- 구조: '핵심 결론' 제목 + 2~4개 문단 + '근거' 제목 + 짧은 bullet 2~3개.
""".strip()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "너는 페이지 결과를 읽고 해석하여 최종 답변을 작성하는 AI 연구 어시스턴트다. 반드시 사용자의 언어로, 해석 중심으로 답하라."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1800,
            )
            answer = (response.choices[0].message.content or "").strip()
            if language == "ko" and not re.search(r"[가-힣]", answer):
                return None
            if self._looks_rule_based_answer(answer):
                return None
            return answer
        except Exception:
            return None

    def _looks_rule_based_answer(self, answer):
        text = (answer or "").strip()
        if len(text) < 120:
            return True
        markers = [
            "연구 페이지로 이동하기",
            "링크를 통해",
            "더욱 탐구하고",
            "말씀해 주세요",
            "sandbox:/",
        ]
        return any(marker in text for marker in markers)

    # =========================================================================
    # 특허 섹션
    # =========================================================================
    def _build_patent_section(self, patent_data, language):
        if not patent_data or not patent_data.get("has_patents"):
            return ""

        patents = patent_data.get("patents", [])[:5]
        if not patents:
            return ""

        lines = ["## 관련 특허" if language == "ko" else "## Related Patents"]
        for idx, p in enumerate(patents, 1):
            title = p.get("title", "제목 없음")
            applicant = p.get("applicant", "")
            app_num = p.get("applicationNumber", "")
            lines.append(f"{idx}. **{title}** (출원번호: {app_num}, 출원인: {applicant})")

        return "\n".join(lines)

    # =========================================================================
    # 한국어 보강
    # =========================================================================
    def _ensure_rich_korean(self, answer, message, page_results):
        """한국어 답변이 충분히 풍부한지 확인하고 보강."""
        if not page_results:
            return answer

        text = (answer or "").strip()
        # 이미 충분한 구조가 있으면 패스
        if "핵심 결론" in text and len(text) > 400:
            paras = [p.strip() for p in text.split("\n\n") if p.strip()]
            if len(paras) >= 4:
                return answer

        pr = page_results[-1] if isinstance(page_results[-1], dict) else {}
        page = pr.get("page", "-")
        tab = pr.get("tab", "-")
        query = pr.get("query", message)
        total = pr.get("total", pr.get("total_hits", pr.get("total_searched", 0)))

        derived_snips = self._collect_text_snippets(page_results)
        derived_terms = self._extract_top_keywords(derived_snips, limit=8)

        count_phrase = f"{total}건" if total else "다수의 결과"
        p1 = f"'{query}' 키워드로 {page}/{tab} 페이지를 실행해 관련 결과 {count_phrase}을 확인했습니다."

        p2 = "상위 유사도 분포는 검색어가 현재 컬렉션의 어떤 주제들과 가까운지를 보여줍니다."
        if derived_terms:
            p2 += f" 페이지 결과에서 함께 자주 등장한 용어는 {', '.join(derived_terms)} 입니다."

        p3 = "검색어를 '재료/가스/전력/압력/온도/공정 타입'처럼 조절 가능한 축으로 분해하면 더 정밀한 결과를 얻을 수 있습니다."
        if derived_terms:
            p3 = f"{', '.join(derived_terms[:6])} 같은 동반 용어를 중심으로 재검색하면 관련 문헌의 주제성이 더 뚜렷해집니다."

        p4 = "상위 결과에서 반복되는 핵심 용어를 선택해 AND 조합으로 재검색하면 메커니즘 후보를 더 빠르게 좁힐 수 있습니다."

        new_conclusion = "\n\n".join([p1, p2, p3, p4])

        return f"핵심 결론\n\n{new_conclusion}\n\n근거\n- 페이지 결과 요약: {page}/{tab} 페이지에서 '{query}' 검색 결과를 기준으로 정리했습니다."

    # =========================================================================
    # 텍스트 스니펫/키워드 추출
    # =========================================================================
    def _collect_text_snippets(self, page_results, max_items=40, max_chars=6000):
        snippets = []
        total_chars = 0

        def add(t):
            nonlocal total_chars
            if not t or not isinstance(t, str):
                return
            t = t.strip()[:400]
            if ".pdf" in t.lower() or not t or t in snippets:
                return
            if total_chars + len(t) > max_chars:
                return
            snippets.append(t)
            total_chars += len(t)

        def walk(node):
            if len(snippets) >= max_items or total_chars >= max_chars:
                return
            if isinstance(node, str):
                add(node)
            elif isinstance(node, dict):
                for k, v in node.items():
                    if k in ("filename", "file", "path", "doc_id", "id"):
                        continue
                    if k in ("text", "snippet", "excerpt", "abstract", "content", "description", "summary"):
                        if isinstance(v, str):
                            add(v)
                            continue
                    if k in ("title", "topic") and isinstance(v, str):
                        add(v)
                        continue
                    if k == "chunks" and isinstance(v, list):
                        for ch in v[:5]:
                            if isinstance(ch, dict):
                                add(ch.get("text"))
                        continue
                    if k == "snippets" and isinstance(v, list):
                        for s in v[:5]:
                            if isinstance(s, str):
                                add(s)
                        continue
                    walk(v)
            elif isinstance(node, list):
                for it in node[:30]:
                    walk(it)

        for pr in (page_results or [])[-3:]:
            if isinstance(pr, dict):
                walk(pr)

        return snippets

    def _extract_top_keywords(self, texts, limit=10):
        if not texts:
            return []
        stop = {"있습니다", "합니다", "됩니다", "확인", "기반", "관련", "결과", "문헌", "페이지",
                "the", "and", "for", "with", "from", "that", "this", "using", "results"}
        counter = Counter()
        for t in texts[:60]:
            for token in re.findall(r"[A-Za-z]{3,}|[가-힣]{2,}", t or ""):
                tok = token.strip().lower()
                if tok and tok not in stop and not tok.isdigit():
                    counter[tok] += 1
        return [w for w, _ in sorted(counter.items(), key=lambda x: (-x[1], -len(x[0])))[:limit]]

    # =========================================================================
    # 품질 보고서 / Evidence
    # =========================================================================
    def _build_base_quality_report(self, language, evidence_bank, tool_result_bank, page_result_bank):
        scores = [e.get("score", 0) for e in evidence_bank if isinstance(e.get("score"), (int, float))]
        return {
            "stage": "verification",
            "detail": "페이지 결과와 검색 근거를 바탕으로 최종 답변을 구성하고 있습니다." if language == "ko" else "Building the final answer from page results and evidence.",
            "answerStyle": "근거 통합 응답" if language == "ko" else "Grounded synthesis",
            "confidence": "중간" if language == "ko" else "Medium",
            "evidenceCount": len(evidence_bank),
            "avgScore": round(sum(scores) / len(scores), 4) if scores else None,
            "synthesisPoints": [],
            "verificationChecks": [],
            "sources": [e.get("filename") for e in evidence_bank[:3] if e.get("filename")],
            "llmUsed": False,
        }

    def _build_page_result_llm_bundle(self, page_results):
        bundle = []
        for pr in (page_results or [])[-3:]:
            if not isinstance(pr, dict):
                continue
            params = pr.get("params") if isinstance(pr.get("params"), dict) else {}
            snippets = self._collect_text_snippets([pr], max_items=12, max_chars=2500)
            bundle.append({
                "page": pr.get("page", "-"),
                "tab": pr.get("tab", "-"),
                "query": pr.get("query", ""),
                "params": params,
                "totals": {
                    "total": pr.get("total"),
                    "total_hits": pr.get("total_hits"),
                    "total_searched": pr.get("total_searched"),
                },
                "top_terms": self._extract_top_keywords(snippets, limit=8),
                "semantic_snippets": snippets[:10],
                "raw_excerpt": json.dumps(pr, ensure_ascii=False)[:3200],
            })
        return bundle

    def _serialize_patents_for_llm(self, patent_data):
        if not patent_data or not patent_data.get("has_patents"):
            return []
        patents = []
        for item in (patent_data.get("patents") or [])[:10]:
            if not isinstance(item, dict):
                continue
            patents.append({
                "title": item.get("title", ""),
                "applicant": item.get("applicant", ""),
                "applicationNumber": item.get("applicationNumber", ""),
                "applicationDate": item.get("applicationDate", ""),
                "publicationNumber": item.get("publicationNumber", ""),
                "registerNumber": item.get("registerNumber", ""),
                "abstract": (item.get("abstract") or "")[:600],
            })
        return patents

    def _build_evidence_items(self, page_results):
        items = []
        for pr in (page_results or []):
            if not isinstance(pr, dict):
                continue
            for key in ("results", "clusters", "predictions", "matched_patterns", "items", "data"):
                items_list = pr.get(key)
                if not isinstance(items_list, list):
                    continue
                for idx, item in enumerate(items_list):
                    if not isinstance(item, dict):
                        continue
                    doc_id = item.get("doc_id") or item.get("id") or str(idx + 1)
                    filename = item.get("filename") or item.get("title") or item.get("name") or f"문서 {idx + 1}"
                    score = item.get("score") or item.get("relevance") or item.get("match_score")
                    snippets = []
                    for skey in ("snippet", "text", "excerpt", "abstract", "content"):
                        val = item.get(skey)
                        if val and isinstance(val, str):
                            snippets.append(val[:300])
                            break
                    items.append({
                        "doc_id": str(doc_id),
                        "filename": str(filename),
                        "score": float(score) if score is not None else None,
                        "snippets": snippets,
                    })
        return items
