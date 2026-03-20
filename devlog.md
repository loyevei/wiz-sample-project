| 날짜 | ID | 작업 내용 | 상세 |
|------|-----|----------|------|
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
