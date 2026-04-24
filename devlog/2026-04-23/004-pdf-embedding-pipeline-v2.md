# PDF 임베딩 파이프라인 v2 (페이지 PNG / Surya OCR / Vision LaTeX 강화 / 검색 결과 모달)

- **ID**: 004
- **날짜**: 2026-04-23
- **유형**: 기능 추가

## 작업 요약

PDF 업로드 시 모든 페이지를 PNG로 사전 렌더링하여 검색 결과에서 원본 페이지를 즉시 표시할 수 있도록 했고, 텍스트 레이어가 부실한 페이지에는 Surya OCR fallback을 추가했다. Vision LLM의 수식 추출 프롬프트를 LaTeX 전용으로 엄격화하고 환각 방지 가드를 넣었다. 청크 메타에 bbox(원본 좌표)를 추가하여 검색 결과를 클릭하면 페이지 PNG 위에 빨간 테두리로 해당 영역을 하이라이트하는 모달 뷰어를 `page.research`에 통합했다. BGE-base 모델은 이미 `modelregistry`에 등록되어 있어 추가 조정 없이 사용 가능. 청크 크기 500자도 기본값.

## 변경 파일 목록

### 백엔드 — `page.embedding/api.py`
- 설정 상수 추가: `PAGES_DIR`, `PAGE_RENDER_DPI=150`, `THUMB_RENDER_DPI=75`
- 신규 헬퍼: `_page_dir`, `_render_pdf_pages` (PyMuPDF로 page_NNNN.png + thumb_NNNN.png + `_pages.json` 메타 생성, idempotent), `_get_surya`/`_surya_ocr_page` (surya-ocr 동적 로드, 신구 API 모두 대응)
- `_extract_text_from_pdf(use_ocr=True)`: 텍스트 50자 미만 페이지에 Surya OCR 결과를 텍스트 블록으로 주입, `ocr_pages_used` 통계 추가
- `_assign_page_numbers`: 청크에 `bbox` 함께 할당
- `_ensure_collection`: 신규 컬렉션 스키마에 `bbox VARCHAR(128)` 추가 (기존 컬렉션은 그대로 동작)
- `upload`: PDF 저장 직후 `_render_pdf_pages` 호출, 청크 record에 bbox JSON 포함, 응답에 `pages_rendered`/`ocr_pages_used`/`surya_available` 추가
- `delete_collection`/`delete_document`: 페이지 PNG 디렉토리도 함께 정리
- 신규 엔드포인트: `page_image()`, `thumb()`, `page_meta()`, `render_pages()` — 모두 lazy 렌더링 지원, `wiz.response` 예외 기반 종료 패턴 준수

### 백엔드 — `model/vision_llm.py`
- `extract_equation_latex` 프롬프트 전면 재작성: 출력은 JSON만, `latex` 필드는 LaTeX 소스 ONLY, `$..$`/`$$..$$` 구분, 모르면 빈 문자열, 8단어 이내 type label만 허용
- 환각 가드: 출력에 수학 기호(`\$^_{}=+-*/숫자`)가 전혀 없으면 latex를 빈 문자열로 비움
- `analyze_image`의 equation 분기를 새 마커 형식 `[EQUATION: type=display | $$...$$ | context: ...]`으로 정렬

### 백엔드 — `page.research/api.py`
- 신규 헬퍼: `_collection_field_names`, `_safe_output_fields` — 컬렉션 스키마에 없는 필드를 자동 제거 (bbox 미존재 컬렉션 호환)
- 메인 `_recommend_papers_data` 검색의 `output_fields`를 안전 처리 + 결과에 `bbox`(JSON 파싱), `collection` 추가

### 프론트엔드 — `page.research/view.ts`
- `pdfModal` 상태 객체 추가 (open/docId/pageNum/collection/filename/bbox/pageSize/renderDpi/totalPages/loading/error)
- `openPdf(docId, pageNum, paper)` 시그니처 확장: 새 탭 열기 대신 모달 표시
- 신규 메서드: `loadPdfPageMeta` (fetch로 `/wiz/api/page.embedding/page_meta` 호출), `pdfPageImageUrl`, `pdfThumbUrl`, `closePdfModal`, `pdfModalGoto(±1)`, `openPdfTab` (기존 새 탭 동작은 모달 헤더 버튼으로 보존), `bboxOverlayStyle` (PDF 좌표 → 백분율 좌표)

### 프론트엔드 — `page.research/view.pug`
- 검색 결과 카드(`recResults`)에 페이지 썸네일(`pdfThumbUrl`) 추가, 클릭 시 `openPdf(..., paper)` 호출
- 파일 끝에 PDF 페이지 모달 뷰어 추가: 헤더(파일명/페이지/이전·다음/원본 PDF/닫기) + 본문(페이지 PNG + bbox 빨간 오버레이) + 에러 메시지

## 코드 변경 패턴

### Before/After: vision_llm 수식 프롬프트
```python
# Before: 자연어 설명 섞임 가능
prompt = """This image contains a mathematical equation or formula.
1. Convert it to LaTeX notation exactly as shown.
2. Provide a brief description...
{"latex": "<LaTeX code>", "description": "<brief description>"}"""

# After: LaTeX 전용 + 환각 가드
prompt = """You are a strict LaTeX transcriber for mathematical equations.
RULES:
1. Output ONLY a JSON object. No prose, no markdown fences, no preamble.
2. Field "latex": LaTeX source ONLY. NO words, NO English/Korean explanations.
...
6. If unreadable or no equation, set "latex" to "" (empty). Do NOT hallucinate.
"""
# + 후처리: 수학 기호가 전혀 없으면 latex를 강제로 비움
if stripped and not re.search(r"[\\$\^_{}=+\-*/\d]", stripped):
    parsed["latex"] = ""
```

### Before/After: page.research 검색 결과 클릭
```typescript
// Before: 새 탭에서 PDF 원본 열기
public openPdf(docId, pageNum) {
    window.open(`/wiz/api/page.research.v2/serve_pdf?...#page=${pageNum}`, '_blank');
}

// After: 모달 뷰어 (페이지 PNG + bbox 하이라이트)
public openPdf(docId, pageNum, paper) {
    this.pdfModal = { open: true, docId, pageNum, collection: paper?.collection,
                      bbox: paper?.bbox, ... };
    this.loadPdfPageMeta();
}
```

## 검증

- `wiz project build --project=main` (normal 빌드, 서버 재시작 없음) 성공
- `page_meta` HTTP 200 JSON, 페이지 10장 사이즈/DPI 메타 정상 반환
- `thumb` / `page_image` HTTP 200 image/png, 매직바이트 `89 50 4E 47` PNG 검증
- `render_pages` 호출로 기존 문서 페이지 PNG 재생성 확인
- `/opt/app/data/pages/test/a021691b/`에 page_0001~0010.png + thumb_0001~0010.png + `_pages.json` 생성됨
- `page.research/recommend` 정상 응답 (bbox 추가가 기존 검색 흐름을 깨지 않음)
- Surya OCR은 `surya-ocr` 패키지가 설치되어 있을 때만 자동 활성 (현재 환경 미설치 → 텍스트 레이어 추출만 사용, fallback 코드 경로는 유효)
