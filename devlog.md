| 날짜 | ID | 작업 내용 | 상세 |
|------|-----|----------|------|
| 2026-04-24 | 001 | PDF 임베딩 업로드 경로에 Nougat OCR 래퍼와 `extraction_mode` 옵션을 추가하고 무중단 검증 | [상세](devlog/2026-04-24/001-nougat-wrapper-and-extraction-mode.md) |
| 2026-04-24 | 002 | Hybrid 본문 추출 파이프라인을 3단계(레이아웃/Nougat/병합)로 분리 | [상세](devlog/2026-04-24/002-hybrid-pipeline-split.md) |
| 2026-04-24 | 003 | 수식 품질 게이트 및 Gemma 4 Vision rescue 단계 추가 | [상세](devlog/2026-04-24/003-equation-quality-gate-rescue.md) |
| 2026-04-24 | 004 | Provenance 메타데이터를 structured_content에 저장 | [상세](devlog/2026-04-24/004-provenance-metadata.md) |
| 2026-04-24 | 005 | 업로드 UI에 추출 모드/Nougat/Gemma rescue 설정 노출 | [상세](devlog/2026-04-24/005-upload-ui-pipeline-settings.md) |
| 2026-04-24 | 006 | E2E 검증 및 pages_data 미정의 버그 수정 | [상세](devlog/2026-04-24/006-e2e-verification-bugfix.md) |
| 2026-04-23 | 004 | PDF 임베딩 파이프라인 v2: 페이지 PNG 사전 렌더링·Surya OCR fallback·Vision LaTeX 강화·검색 결과 모달 뷰어 추가 | [상세](devlog/2026-04-23/004-pdf-embedding-pipeline-v2.md) |
| 2026-04-23 | 003 | 페이지 조회 결과에 LLM 자연어 요약(`✨ AI 요약`) 블록 추가 | [상세](devlog/2026-04-23/003-page-result-llm-synthesis.md) |
| 2026-04-23 | 002 | 에이전트 챗봇 페이지 조회 결과 요약을 모든 페이지/탭 데이터 구조에 맞게 강화 | [상세](devlog/2026-04-23/002-agent-page-result-summary.md) |
| 2026-04-23 | 001 | Gemma 4와 GPT-4.1 A/B 벤치마크 경로를 무중단으로 추가하고 실측 비교 수행 | [상세](devlog/2026-04-23/001-gemma-vs-gpt-benchmark-path.md) |
| 2026-04-14 | 001 | ROCm PyTorch 교체 + Gemma 4 E4B-IT Vision LLM 통합 (PDF 이미지 멀티모달 분석) | [상세](devlog/2026-04-14/001-rocm-gemma4-vision-integration.md) |
| 2026-04-13 | 001 | 챗봇 SSE가 done 이후 닫히지 않아 로딩이 남는 문제를 /agent, /agent/v2, 플로팅 AI Chat에서 공통 보강 | [상세](devlog/2026-04-13/001-chatbot-stream-done-timeout-fix.md) |
| 2026-04-10 | 008 | 실제 AI 어시스턴트 페이지(/agent)에서 즉시 페이지 이동을 제거하고 최종답변 SSE 완료 처리를 보강 | [상세](devlog/2026-04-10/008-agent-page-final-answer-retention.md) |
| 2026-04-10 | 007 | 챗봇 최종답변이 누락되던 SSE 종료 경로를 보강하고 플로팅 handoff 자동이동을 지연 | [상세](devlog/2026-04-10/007-chatbot-final-answer-stream-completion.md) |
| 2026-04-10 | 006 | 챗봇 최종답변 타자 효과를 제거해 최종 텍스트를 즉시 렌더링하도록 조정 | [상세](devlog/2026-04-10/006-chatbot-instant-final-answer-render.md) |
| 2026-04-10 | 005 | 챗봇 최종답변에서 임의 외부 링크를 제거하고 실제 handoff 경로만 남기도록 보정 | [상세](devlog/2026-04-10/005-chatbot-final-handoff-link-grounding.md) |
| 2026-04-08 | 002 | 플로팅 챗봇을 사이드바 패널로 전환 + Claude×Copilot 하이브리드 에이전트 UI | [상세](devlog/2026-04-08/002-sidebar-chat-claude-copilot-hybrid.md) |
| 2026-04-08 | 001 | 플로팅 챗봇 UI를 VS Code Copilot 스타일로 전면 개편 (Thinking 섹션, 인라인 도구 칩, 미니멀 디자인) | [상세](devlog/2026-04-08/001-copilot-style-chatbot-ui.md) |
| 2026-03-27 | 004 | 플로팅 챗봇의 카드/프리뷰 상태 갱신 경로를 공용 헬퍼로 정리해 결합도를 낮춤 | [상세](devlog/2026-03-27/004-floating-chat-state-update-helper-refactor.md) |
| 2026-03-27 | 003 | 에이전트 답변 대기 체감 개선을 위해 progressive card/preview UX 적용 | [상세](devlog/2026-03-27/003-agent-waiting-ux-progressive-cards.md) |
| 2026-03-27 | 002 | 변경 컬렉션 기준 에이전트 파이프라인 재적용 | [상세](devlog/2026-03-27/002-agent-pipeline-refresh-for-changed-collection.md) |
| 2026-02-21 | 001 | 기존 인프라 page 앱 전체 삭제 및 일반 서비스 샘플 page 앱 생성 | [상세](devlog/2026-02-21/001-sample-pages-rebuild.md) |
| 2026-02-25 | 001 | PDF 임베딩 파이프라인 전면 리팩토링: 스마트 추출 + 시맨틱 청킹 + 멀티모델 + 컬렉션 관리 | [상세](devlog/2026-02-25/001-embedding-pipeline-enhancement.md) |
| 2026-02-25 | 002 | 영어 특화 임베딩 모델 3개 추가 + 컬렉션 메타 정합성 보강 + 워커 재시작 스크립트 | [상세](devlog/2026-02-25/002-english-models-and-meta-fix.md) |
| 2026-02-25 | 003 | 컬렉션 관리 기능 검증 및 UI/UX 보완 (로딩 상태, 빈 컬렉션 안내, 유효성 사전 검사) | [상세](devlog/2026-02-25/003-collection-management-ux.md) |
| 2026-02-26 | 001 | Research Gap Detector + 가설 자동 생성기 + 5탭 대시보드 통합 | [상세](devlog/2026-02-26/001-research-gap-hypothesis-dashboard.md) |
| 2026-02-26 | 002 | Prediction 공정 예측 파이프라인: 파라미터 추출/역설계/불확실성/Surrogate + 5탭 UI | [상세](devlog/2026-02-26/002-prediction-pipeline-dashboard.md) |
| 2026-02-26 | 003 | Diagnosis 6탭 대시보드: OES Spectrum Embedding/Multimodal Retrieval/Anomaly Detection/Failure Case Reasoning | [상세](devlog/2026-02-26/003-diagnosis-pipeline-dashboard.md) |
| 2026-02-26 | 004 | Research 토픽맵 클러스터 해석: 관계 분석/브릿지 문서/대표 snippet/자연어 요약 | [상세](devlog/2026-02-26/004-research-topicmap-interpretation.md) |
| 2026-02-26 | 005 | Theory 이론 연구 지원 3탭 페이지: 수식 검색/가정 검증/이론 그래프 전체 구현 | [상세](devlog/2026-02-26/005-theory-page-full-implementation.md) |
| 2026-02-26 | 006 | Embedding 6개 청킹 전략 + 이미지 OCR + 표→Markdown + 수식→LaTeX + Milvus 스키마 확장 | [상세](devlog/2026-02-26/006-embedding-chunking-ocr-enhancement.md) |
| 2026-02-26 | 007 | Embedding 페이지 chunk_type 통계 (분류 분포 바/문서별 상세) | [상세](devlog/2026-02-26/007-embedding-chunk-type-stats.md) |
| 2026-02-26 | 008 | Theory 수식 추출 버그 수정: chunk_index==0 필터 제거 + [EQUATION:] 마커 인식 | [상세](devlog/2026-02-26/008-theory-equation-extraction-fix.md) |
| 2026-02-26 | 009 | Diagnosis 컬렉션 선택 연동 버그 수정 + 진단 비교 분석 텍스트 생성 기능 추가 | [상세](devlog/2026-02-26/009-diagnosis-collection-compare.md) |
| 2026-02-26 | 010 | AI Agent 챗봇 구현: Tool-Use + SSE 스트리밍 + 4개 연구 도구 (논문/수식/컬렉션/키워드) | [상세](devlog/2026-02-26/010-ai-agent-chatbot.md) |
| 2026-02-26 | 011 | AI Agent — Anthropic→OpenAI GPT-4o 전환 + 13개 신규 도구 추가 (총 17개: 주제발굴3/공정예측4/진단분석3/이론연구3/기존4) | [상세](devlog/2026-02-26/011-ai-agent-openai-17tools.md) |
| 2026-02-27 | 001 | AI Agent 챗봇 응답 미반환 버그 수정: config/season.py API 키 문자열 SyntaxError 해결 | [상세](devlog/2026-02-27/001-agent-chat-syntax-error-fix.md) |
| 2026-02-27 | 002 | AI Agent 다국어 응답 + 4대 연구 페이지 네비게이션 연동 (navigate_to_page 도구 + 쿼리 파라미터 자동 검색) | [상세](devlog/2026-02-27/002-agent-multilang-page-navigation.md) |
| 2026-02-27 | 003 | Embedding 프론트엔드 — 청킹 전략 선택 UI + 미리보기 패널 + 청크 타입 통계 (FN-0009/0010 검증, FN-0025~0032 보완) | [상세](devlog/2026-02-27/003-embedding-frontend-chunking-preview.md) |
| 2026-03-16 | 001 | AI Agent 키워드 분류→페이지 파라미터 자동 실행: navigate_to_page 탭ID 동기화 + calculator/experiment/analysis/collaboration 쿼리파라미터 연동 + 시스템 프롬프트 파라미터 매핑 강화 | [상세](devlog/2026-03-16/001-agent-keyword-param-enhancement.md) |
| 2026-03-16 | 002 | AI Agent 네비게이션 강화: URL 인코딩 버그 수정 + force fresh navigation + 네비게이션 카드 UI + 시스템 프롬프트 STRICT workflow | [상세](devlog/2026-03-16/002-agent-navigation-enhancement.md) |
| 2026-02-27 | 004 | Embedding chunk_type_stats 배치 페이지네이션 적용 (BATCH_SIZE=16000, 대용량 컬렉션 대응) | [상세](devlog/2026-02-27/004-embedding-chunk-type-stats-batch.md) |
| 2026-02-27 | 005 | Embedding 청킹 옵션 상시 표출 + 버튼 UI / AI Agent 의도 분류 뱃지 + 자동 페이지 이동 | [상세](devlog/2026-02-27/005-embedding-button-ui-agent-intent.md) |
| 2026-02-27 | 006 | Embedding 페이지 글자 안 보이는 오류 수정 (view.ts 누락 메서드 복원) + 청킹 전략 카드형 버튼 UI 개선 | [상세](devlog/2026-02-27/006-embedding-fix-text-invisible-card-buttons.md) |
| 2026-03-17 | 001 | 플로팅 챗봇 Milvus 컬렉션 선택 UI + 에이전트 collection 전달 + Research 논문추천/제안서/특허 기능 연동 | [상세](devlog/2026-03-17/001-chatbot-milvus-agent-research.md) |
| 2026-03-18 | 001 | 플로팅 챗봇 DB 버튼 UI 및 Research 3기능 런타임 검증 + 서버 재시작 없는 빌드 반영 | [상세](devlog/2026-03-18/001-chatbot-db-buttons-research-fixes.md) |
| 2026-03-18 | 002 | 플로팅 챗봇 컬렉션 로딩을 /embedding API로 연결해 DB 버튼 노출 복구 | [상세](devlog/2026-03-18/002-chatbot-embedding-collection-bridge.md) |
| 2026-03-18 | 003 | 플로팅 챗봇 에이전트 `Te` NameError 수정 및 Tool-Use SSE 응답 복구 | [상세](devlog/2026-03-18/003-floating-chat-agent-fstring-fix.md) |
| 2026-03-19 | 001 | 플로팅 챗봇 선택 컬렉션을 Research/Prediction/Diagnosis/Theory 페이지와 동기화 | [상세](devlog/2026-03-19/001-floating-chat-collection-sync.md) |
| 2026-03-19 | 002 | 플로팅 챗봇이 페이지 이동과 함께 에이전트형 handoff 답변을 남기도록 강화 | [상세](devlog/2026-03-19/002-floating-chat-agent-handoff.md) |
| 2026-03-19 | 003 | 연구자 워크플로우 확장: 근거 추적·실험 데이터셋·연구 노트 자동화·프로젝트 컬렉션·보고서 생성 | [상세](devlog/2026-03-19/003-researcher-workflow-suite.md) |
| 2026-03-20 | 001 | 플로팅 챗봇 14단계 사고과정 UI와 플라즈마 로봇 캐릭터 적용 및 무중단 배포 | [상세](devlog/2026-03-20/001-floating-chatbot-trace-robot-ui.md) |
| 2026-03-20 | 002 | 플로팅 챗봇 보라/핑크 플라즈마 테마 적용 및 로봇 SVG 아이콘 교체 | [상세](devlog/2026-03-20/002-floating-chatbot-theme-and-robot-icon.md) |
| 2026-03-20 | 003 | 플로팅 챗봇 최종 답변을 프롬프트·오케스트레이터·도구·메모리·스트리밍 UI 파이프라인으로 명시화 | [상세](devlog/2026-03-20/003-floating-chatbot-answer-pipeline.md) |
| 2026-03-20 | 004 | 플로팅 챗봇 5요소 답변 파이프라인 전용 QA 체크리스트와 샘플 검수본 정리 | [상세](devlog/2026-03-20/004-floating-chatbot-pipeline-qa-checklist.md) |
| 2026-03-20 | 005 | 플로팅 챗봇 5요소 파이프라인 실제 검수 기록용 실전 판정본 추가 | [상세](devlog/2026-03-20/005-floating-chatbot-pipeline-live-report.md) |
| 2026-03-20 | 006 | 플로팅 챗봇이 Milvus 근거를 조합·구조화·검증해 더 높은 품질의 최종 답변을 생성하도록 고도화 | [상세](devlog/2026-03-20/006-floating-chatbot-grounded-answer-quality.md) |
| 2026-03-23 | 001 | 플로팅 챗봇이 도구 결과·페이지 파라미터까지 읽어 한글 최종답변을 재정리하도록 개선 | [상세](devlog/2026-03-23/001-floating-chatbot-answer-quality-refinement.md) |
| 2026-03-23 | 002 | 플로팅 챗봇이 페이지 결과 JSON을 직접 읽어 최종답변을 재구축하도록 `read_page_results` Tool 추가 | [상세](devlog/2026-03-23/002-read-page-results-tool-for-floating-chatbot.md) |
| 2026-03-23 | 003 | `read_page_results`를 Research 추천과 Diagnosis 결과까지 확장해 페이지 기반 한글 답변 범위를 넓힘 | [상세](devlog/2026-03-23/003-read-page-results-recommend-diagnosis-extension.md) |
| 2026-03-23 | 004 | `diagnosis/failure` 결과를 `read_page_results`로 직접 읽어 고장 진단 답변까지 페이지 기반으로 확장 | [상세](devlog/2026-03-23/004-read-page-results-diagnosis-failure.md) |
| 2026-03-23 | 005 | 플로팅 챗봇을 백엔드 오케스트레이션 이벤트 기반으로 재구성하고 `플라즈마 에이전트 챗봇` 명칭으로 정리 | [상세](devlog/2026-03-23/005-floating-chat-orchestration-and-rename.md) |
| 2026-03-23 | 006 | 플로팅 챗봇에 키워드 매핑·페이지 결과 추출·핸드오프까지 포함한 실행 사고 로그를 전면 표시 | [상세](devlog/2026-03-23/006-floating-chat-reasoning-visibility.md) |
| 2026-03-23 | 007 | 플로팅 챗봇의 파이프라인 카드를 제거하고 실제 실행 계획 원문과 페이지 결과 우선 답변 흐름을 노출 | [상세](devlog/2026-03-23/007-floating-chat-execution-plan-and-page-result-grounding.md) |
| 2026-03-23 | 008 | 플로팅 챗봇의 분리된 실행 UI를 `답변 생성 과정` 단일 섹션으로 통합하고 페이지 결과 기반 한국어 fallback 답변을 추가 | [상세](devlog/2026-03-23/008-floating-chat-answer-journey-unification.md) |
| 2026-03-23 | 009 | 플로팅 챗봇 에이전트를 군집형 역할 분담과 목표 반복 관리 루프로 확장 | [상세](devlog/2026-03-23/009-clustered-agent-goal-loop.md) |
| 2026-03-23 | 010 | 군집형 에이전트에 cluster-specific prompt를 도입해 반복 루프마다 active cluster 지시를 동적으로 적용 | [상세](devlog/2026-03-23/010-cluster-specific-prompts-for-agent-clusters.md) |
| 2026-03-23 | 011 | 군집형 에이전트에 cluster별 허용 tool 정책을 분리해 active cluster마다 호출 가능한 도구를 제한 | [상세](devlog/2026-03-23/011-cluster-tool-policy-restrictions.md) |
| 2026-03-23 | 012 | 군집형 에이전트에 cluster별 성공/실패 평가기와 planner fallback self-correction 루프를 추가 | [상세](devlog/2026-03-23/012-cluster-self-correction-evaluator.md) |
| 2026-03-23 | 013 | 군집형 에이전트의 self-correction을 실패 사유별 recovery strategy 분기로 확장하고 플로팅 UI에 복구 전략을 노출 | [상세](devlog/2026-03-23/013-cluster-recovery-strategy-branching.md) |
| 2026-03-23 | 014 | recovery strategy가 다음 iteration의 planner 도구 우선순위를 직접 바꾸고 플로팅 UI에 우선 도구를 반영하도록 확장 | [상세](devlog/2026-03-23/014-recovery-strategy-tool-priority.md) |
| 2026-03-23 | 015 | 플로팅 챗봇 명칭을 KFE bot으로 변경하고 recovery strategy의 다음 query/params 입력 힌트를 UI에 노출 | [상세](devlog/2026-03-23/015-kfe-bot-and-recovery-query-params.md) |
| 2026-03-23 | 016 | recovery strategy의 다음 query/params 추출을 도메인별 규칙으로 고도화해 계산기·예측·진단·분석 입력 정확도를 개선 | [상세](devlog/2026-03-23/016-domain-recovery-param-extraction.md) |
| 2026-03-23 | 017 | 최종답변의 추가 정제 호출을 줄여 응답 속도를 높이고, 플로팅 챗봇 최종답변을 한국어로 고정 | [상세](devlog/2026-03-23/017-fast-korean-final-answer.md) |
| 2026-03-23 | 018 | 도구 실행 중 짧은 한국어 중간결론을 먼저 보여주고 최종 verification 답변으로 교체하는 preview UX를 추가 | [상세](devlog/2026-03-23/018-preview-first-final-replace.md) |
| 2026-03-23 | 019 | 영어 근거와 영어 초안이 있어도 플로팅 챗봇 preview/최종답변을 한국어로 강제하고 raw 영어 preview 노출을 제거 | [상세](devlog/2026-03-23/019-force-korean-final-and-preview.md) |
| 2026-03-23 | 020 | 최종 설명은 한국어로 유지하되 논문 제목·파일명·원문 인용은 영어 그대로 유지할 수 있도록 언어 정책을 명확화 | [상세](devlog/2026-03-23/020-korean-answer-english-paper-titles.md) |
| 2026-03-23 | 021 | `read_page_results`의 인자값이 반영된 실제 페이지 결과를 LLM이 읽어 한국어 최종답변으로 정리하도록 fast fallback 경로를 제거 | [상세](devlog/2026-03-23/021-page-results-llm-korean-summary.md) |
| 2026-03-23 | 022 | 최종답변의 영문 설명 문장을 한국어로 정규화하고, sandbox 링크/페이지 이동 CTA를 본문에서 제거 | [상세](devlog/2026-03-23/022-korean-final-answer-cleanup-and-remove-cta.md) |
| 2026-03-24 | 001 | 최종답변에서 PDF 논문 제목·파일명·원문 인용을 제거하고, 페이지 결과 기반 한국어-only 설명으로 정리 | [상세](devlog/2026-03-24/001-remove-pdf-paper-evidence-from-final-answer.md) |
| 2026-03-24 | 002 | 질문 키워드와 인자값이 반영된 페이지 결과를 카드로 표시하고, 최종답변을 `핵심 결론 + 근거 2~3줄` 한국어 형식으로 고정 | [상세](devlog/2026-03-24/002-page-results-keyword-param-summary-format.md) |
| 2026-03-24 | 003 | 질문 언어와 관계없이 플로팅 챗봇의 최종답변과 trace 언어를 항상 한국어로 고정 | [상세](devlog/2026-03-24/003-force-korean-final-answer-always.md) |
| 2026-03-24 | 004 | 스트리밍 preview/최종답변 전송 직전에 한국어 정규화를 강제하고, 실패 시 페이지 결과 기반 한국어 fallback으로 대체 | [상세](devlog/2026-03-24/004-force-korean-streaming-fallback.md) |
| 2026-03-24 | 005 | 최종답변에 영어가 남아 있으면 마지막 단계에서 한국어 번역을 다시 수행하고, 실패 시 한국어 fallback으로 대체 | [상세](devlog/2026-03-24/005-final-translation-step-for-korean-answer.md) |
| 2026-03-24 | 006 | 페이지 결과가 존재하면 최종답변이 그 결과값의 요약 버전으로 우선 나오도록 강화 | [상세](devlog/2026-03-24/006-force-final-answer-to-summarize-page-results.md) |
| 2026-03-24 | 007 | 플로팅 챗봇의 preview/최종답변을 표시 버퍼 기반 타자식 애니메이션으로 출력 | [상세](devlog/2026-03-24/007-floating-chat-typewriter-answer.md) |
| 2026-03-24 | 008 | 마지막 번역 단계 대신 사용자 언어 우선 프롬프트를 적용하고, 페이지 결과 요약이 최종답변으로 우선 노출되도록 정리 | [상세](devlog/2026-03-24/008-language-prompt-and-page-result-final-answer.md) |
| 2026-03-24 | 009 | 페이지 결과 요약 최종답변이 사용자 질문 언어로 반드시 나오도록 공통 정규화와 번역 단계를 보강 | [상세](devlog/2026-03-24/009-user-language-final-answer-from-page-results.md) |
| 2026-03-24 | 010 | OpenAI tool_call 히스토리 정합성을 보정해 끊긴 tool 응답 때문에 최종답변이 실패하던 오류를 복구 | [상세](devlog/2026-03-24/010-openai-tool-call-history-sanitizer.md) |
| 2026-03-24 | 011 | 플로팅 챗봇의 답변 생성 과정을 기존 핵심 단계 순서 중심으로 다시 표시하도록 복원 | [상세](devlog/2026-03-24/011-restore-floating-chat-answer-journey-sequence.md) |
| 2026-03-24 | 012 | 에이전트 도구 모듈 로드 시 `wiz` 전역을 주입해 `name 'wiz' is not defined` 런타임 오류를 수정 | [상세](devlog/2026-03-24/012-inject-wiz-into-agent-tools.md) |
| 2026-03-24 | 013 | `read_page_results`가 전역 `wiz` 없이도 동작하도록 수정해 retriever의 페이지 결과 추출 오류를 복구 | [상세](devlog/2026-03-24/013-read-page-results-without-global-wiz.md) |
| 2026-03-24 | 014 | `navigate_to_page`의 빈 인자 첫 호출을 무중단 fallback으로 흡수하고 handoff 실패를 제거 | [상세](devlog/2026-03-24/014-navigate-to-page-empty-input-fallback.md) |
| 2026-03-24 | 015 | 최종 답변에 질문별 페이지 결과 요약 문구를 강제하고 플로팅 UI 표시 단계에서도 함께 노출 | [상세](devlog/2026-03-24/015-final-answer-page-result-summary.md) |
| 2026-03-25 | 001 | 최종 답변 핵심 결론을 문단형 서술로 풍부화하고, 근거 문헌 상세를 아코디언 UI로 전부 노출 | [상세](devlog/2026-03-25/001-rich-conclusion-accordion-evidence.md) |
| 2026-03-25 | 002 | Research 페이지 전 탭에 PDF 원문 연결: 영구 저장 + serve_pdf API + page_num 전수 추가 + 클릭 핸들러 | [상세](devlog/2026-03-25/002-pdf-viewer-link.md) |
| 2026-03-26 | 001 | 페이지 결과가 있어도 조기 요약으로 끝나던 최종답변을 LLM 정제로 연결해 결론 문단을 풍부화 | [상세](devlog/2026-03-26/001-enrich-final-answer-from-page-results.md) |
| 2026-03-26 | 002 | 서버 재시작 없이 최신 agent.py 적용: page.agent.v2 추가 + 플로팅 챗봇 SSE 엔드포인트 전환 + fallback 보강 | [상세](devlog/2026-03-26/002-agent-chat-v2-cache-bypass.md) |
| 2026-03-26 | 003 | 최종답변 결론을 최소 4문단으로 보강하고 파일명/원문 스니펫 노출을 차단 | [상세](devlog/2026-03-26/003-rich-conclusion-4-paragraphs.md) |
| 2026-03-26 | 008 | 임베딩 파이프라인에서 publication timeline 메타를 초기 청크에 보강하고 날짜 포함 연도 추출을 확장 | [상세](devlog/2026-03-26/008-embedding-temporal-metadata-preservation.md) |
| 2026-03-26 | 009 | 운영 컬렉션 문서를 PDF 또는 기존 청크 기반으로 다시 임베딩하는 CLI 스크립트 추가 | [상세](devlog/2026-03-26/009-operational-document-reembedding-script.md) |
| 2026-03-26 | 010 | 추천 논문 연도 추출이 preview 잘림에 영향받지 않도록 원문 범위를 분리 | [상세](devlog/2026-03-26/010-recommend-year-extraction-source-range-fix.md) |
| 2026-03-26 | 011 | 추천 메타를 문서 헤더 청크 기반으로 추출하고 에이전트 최종 요약에 채택/접수 연도를 반영 | [상세](devlog/2026-03-26/011-recommend-metadata-head-chunk-and-agent-summary.md) |
| 2026-03-26 | 012 | 신규 컬렉션 메타가 문자열이어도 플로팅 챗봇/연구 페이지/에이전트 도구가 깨지지 않도록 정규화 및 fallback 보강 | [상세](devlog/2026-03-26/012-floating-chat-new-collection-meta-normalization.md) |
| 2026-03-26 | 013 | PDF 원본 저장 누락을 수정하고 v2 프록시 API로 업로드/추천/PDF 원문 연결을 무중단 복구 | [상세](devlog/2026-03-26/013-pdf-original-preservation-and-v2-proxy-linking.md) |
| 2026-03-26 | 004 | 플로팅 챗봇의 최신 논문 요청을 research/recommend로 정렬하고 파일명 연도 기반 최신성 정렬을 추가 | [상세](devlog/2026-03-26/004-latest-paper-recommend-routing-and-sorting.md) |
| 2026-03-26 | 005 | 최신 논문 추천의 연도 판정을 파일명뿐 아니라 본문/초록 날짜 문구까지 읽도록 확장 | [상세](devlog/2026-03-26/005-latest-paper-date-parser-from-abstract.md) |
| 2026-03-26 | 006 | 최신 논문 추천 결과의 출판연도와 온라인 공개연도를 분리하고 에이전트/카드 UI에 반영 | [상세](devlog/2026-03-26/006-split-publication-year-and-online-year.md) |
| 2026-03-26 | 007 | 최신 논문 추천 결과의 채택연도와 접수연도를 page result 및 Research 카드 UI까지 전파 | [상세](devlog/2026-03-26/007-expose-accepted-and-received-years.md) |
| 2026-03-26 | 014 | 공통 hot-load helper로 agent/v2 프록시 API의 중복 무중단 로딩 로직을 정리 | [상세](devlog/2026-03-26/014-hotload-helper-refactor.md) |
| 2026-03-26 | 015 | collection_meta 문자열 정규화 로직을 페이지/API와 agent tools 공통 helper로 통합 | [상세](devlog/2026-03-26/015-collection-meta-helper-refactor.md) |
| 2026-03-26 | 016 | collaboration/dataset API의 남은 collection_meta 조회 로직을 공통 helper로 정리 | [상세](devlog/2026-03-26/016-finish-collection-meta-helper-cleanup.md) |
| 2026-03-26 | 017 | Research 토픽맵을 토픽별 탐색 카드·분포 분석·개인화 가이드까지 확장 | [상세](devlog/2026-03-26/017-research-topicmap-researcher-customization.md) |
| 2026-03-26 | 018 | Research 특허 검색을 KIPRIS Plus API 기반으로 전환하고 설정형 외부 연동으로 정리 | [상세](devlog/2026-03-26/018-research-patent-kipris-plus-integration.md) |
| 2026-03-26 | 019 | 플로팅 챗봇 에이전트를 하이브리드/계층형 아키텍처(오케스트레이터 + 5개 서브 에이전트)로 리팩토링 | [상세](devlog/2026-03-26/019-agent-hierarchical-architecture-refactor.md) |
| 2026-03-27 | 001 | 플로팅 챗봇의 컬렉션 변경 후 페이지 handoff 동기화를 수정하고 상태/네비게이션 로직을 리팩토링 | [상세](devlog/2026-03-27/001-floating-chat-collection-sync-and-refactor.md) |
| 2026-04-10 | 001 | Angular 번들 빌드 실패 수정: marked 의존성 누락으로 esbuild 컴파일 실패 → 구버전 번들 제공 문제 해결 | [상세](devlog/2026-04-10/001-fix-angular-bundle-marked-dependency.md) |
| 2026-04-10 | 002 | 챗봇 최종답변 타이핑 애니메이션을 적응형으로 가속해 장문 답변 체감 지연 감소 | [상세](devlog/2026-04-10/002-chatbot-final-answer-speedup.md) |
| 2026-04-10 | 003 | 챗봇 백엔드를 Claude 분석서형 단일 Tool-Use loop로 재구성하고 페이지 결과·핸드오프를 유지 | [상세](devlog/2026-04-10/003-chatbot-claude-style-single-loop.md) |
| 2026-04-10 | 004 | 챗봇 프론트 SSE 핸들러를 Claude형 이벤트 흐름으로 단순화하고 다중 text 누적 처리 보정 | [상세](devlog/2026-04-10/004-chatbot-frontend-claude-event-flow.md) |
