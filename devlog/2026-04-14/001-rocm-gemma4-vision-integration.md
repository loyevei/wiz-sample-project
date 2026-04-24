# ROCm PyTorch 교체 및 Gemma 4 Vision LLM 통합

- **ID**: 001
- **날짜**: 2026-04-14
- **유형**: 기능 추가

## 작업 요약
AMD GPU(RX 7900, 24GB VRAM)를 활용하기 위해 PyTorch를 CUDA 빌드에서 ROCm 빌드로 교체하고,
Gemma 4 E4B-IT Vision LLM을 설치하여 PDF 임베딩 파이프라인에 멀티모달 이미지 분석 기능을 통합하였다.

## 변경 파일 목록

### 신규 파일
- `src/model/vision_llm.py` — Gemma 4 E4B-IT 기반 Vision LLM 모듈 (싱글톤 로드, 이미지 분류/수식 LaTeX 추출/그래프 분석/표 변환/다이어그램 분석)

### 수정 파일
- `src/app/page.embedding/api.py`
  - `_extract_text_from_pdf()`: `use_vision` 파라미터 추가, Vision LLM으로 이미지 블록 분석 (OCR 폴백 유지)
  - `upload()`, `preview_extract()`: `use_vision` 파라미터 수신 및 전달
  - `vision_status()`: Vision LLM 사용 가능 여부 확인 API 추가
- `src/app/page.embedding/view.ts`
  - `useVision`, `visionAvailable` 상태 변수 추가
  - `checkVisionStatus()` 함수 추가
  - upload/preview FormData에 `use_vision` 파라미터 전달
- `src/app/page.embedding/view.pug`
  - 청킹 옵션 하단에 "멀티모달 Vision 분석" 토글 UI 추가

### 환경 변경
- PyTorch: `2.10.0+cu128` → `2.9.1+rocm6.4` (ROCm HIP 6.4 활성화)
- accelerate 1.13.0 설치
- google/gemma-4-E4B-it 모델 다운로드 (~16GB, /opt/app/data/models/)
