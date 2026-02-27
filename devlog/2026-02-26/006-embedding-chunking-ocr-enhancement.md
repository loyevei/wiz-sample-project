# 임베딩 페이지 청킹 전략 + OCR/수식/표 추출 강화

- **ID**: 006
- **날짜**: 2026-02-26
- **유형**: 기능 추가

## 작업 요약
임베딩 페이지에 6가지 청킹 전략 선택 기능을 추가하고, PDF에서 이미지 OCR(Tesseract), 표→마크다운 변환, 유니코드→LaTeX 수식 변환을 자동 수행하도록 강화. Milvus 스키마에 content_elements/structured_content 필드를 추가하고, 임베딩 전 미리보기 기능을 구현함.

## 변경 파일 목록

### 시스템 패키지 설치
- `tesseract-ocr` + `tesseract-ocr-kor` apt 패키지 설치
- `pytesseract` pip 패키지 설치

### 백엔드 (api.py 전면 재작성 ~850줄)
- **CHUNK_STRATEGIES 레지스트리**: semantic_section, fixed, sentence, paragraph, recursive, semantic_embedding 6개 전략 정의
- **UNICODE_TO_LATEX 매핑**: 60+ 유니코드 수학 기호 → LaTeX 명령어 변환 테이블
- **_extract_image_ocr()**: 이미지 블록 → Tesseract OCR (kor+eng, --psm 6). 50px 미만 필터링
- **_table_to_markdown()**: PyMuPDF 표 → 마크다운 테이블 형식 변환 (헤더/구분자/데이터)
- **_unicode_to_latex()**: 문자별 유니코드→LaTeX 변환
- **_classify_equation_type()**: display/inline 수식 판별 (math span 비율 > 60% = display)
- **_find_table_caption()**: 표 상하 80px 내 Table 캡션 탐색
- **_extract_text_from_pdf()**: 강화 추출 — OCR, 마크다운 표, LaTeX 수식, 수식 인덱싱 (eq_1, eq_2...)
- **6개 청킹 전략 함수**: 각각의 분할 알고리즘 구현
- **_detect_content_elements()**: 청크 내 요소 목록 (text, figure:N, equation:N, table:N)
- **_extract_structured_content()**: 청크에서 LaTeX 수식, 마크다운 표 JSON 추출
- **_assign_page_numbers()**: 청크→페이지 번호 매핑
- **preview_extract()**: 임베딩 전 추출+청킹 미리보기 API
- **upload()**: chunk_strategy, similarity_threshold 파라미터 추가, 확장 필드 하위 호환
- **chunk_strategies()**: 전략 목록 + OCR 사용 가능 여부 반환 API

### 프론트엔드 (view.ts 전면 재작성 ~320줄)
- **strategies, selectedStrategy**: 청킹 전략 선택 상태
- **ocrAvailable**: OCR 사용 가능 여부 표시
- **showAdvanced, chunkSize, chunkOverlap, respectSentences, similarityThreshold**: 고급 파라미터
- **previewExtract()**: PDF 분석 미리보기 요청
- **getChunkTypeColor/Label()**: 청크 타입 뱃지 UI 헬퍼
- **loadStrategies()**: 전략 목록 로드 + OCR 상태 확인

### 프론트엔드 (view.pug 전면 재작성 ~292줄)
- 안내 가이드 4단계 (모델→전략→스마트 추출→임베딩)
- 청킹 전략 6개 라디오 카드 UI
- OCR 상태 인디케이터 (초록/회색 점)
- 고급 파라미터 접이식 패널 (전략별 동적 표시)
- 미리보기 버튼 + 결과 패널 (요약 카드, 섹션 구조, 청크 타입 분포, 샘플 청크)
- 업로드 로그에 전략명/OCR 건수 포함

### 마커 형식 변경
- `[FORMULA:]` → `[EQUATION:]`로 통일 (이론 페이지와 일관성)
- `_detect_chunk_type()`에서 양쪽 패턴 모두 인식 (하위 호환)
- `_detect_content_elements()`, `_extract_structured_content()`에서도 하위 호환
