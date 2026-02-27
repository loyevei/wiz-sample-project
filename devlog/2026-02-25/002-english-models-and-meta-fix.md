# 영어 특화 임베딩 모델 추가 및 컬렉션 메타 정합성 보강

- **ID**: 002
- **날짜**: 2026-02-25
- **유형**: 기능 추가

## 작업 요약
MODEL_REGISTRY에 영어 특화 모델 3개(MiniLM-L6, MPNet, BGE-base)를 추가하여 총 8개 모델 지원. 4개 페이지(embedding, research, prediction, diagnosis)의 api.py에 동기화. 모델 드롭다운을 언어별(한국어/영어/다국어) optgroup 그룹핑으로 개선. 컬렉션 메타데이터 누락 시 Milvus 스키마 dim으로 모델을 추론하는 fallback 로직 추가. 빌드 후 워커 자동 재시작 스크립트 작성.

## 변경 파일 목록

### MODEL_REGISTRY 확장 (4개 파일)
- `src/app/page.embedding/api.py` — 영어 3개 모델 추가, _infer_model_from_dim() 함수 추가, collections() fallback 로직
- `src/app/page.research/api.py` — MODEL_REGISTRY 동기화, collections() fallback 로직
- `src/app/page.prediction/api.py` — MODEL_REGISTRY 동기화, collections() fallback 로직
- `src/app/page.diagnosis/api.py` — MODEL_REGISTRY 동기화, collections() fallback 로직

### 프론트엔드 언어별 그룹핑
- `src/app/page.embedding/view.ts` — modelGroups, groupModelsByLang(), getLangLabel(), getLangClass() 추가
- `src/app/page.embedding/view.pug` — select를 optgroup 기반으로 변경, 언어 배지 3색(ko/en/multi) 대응

### 워커 재시작 스크립트
- `.github/scripts/restart-worker.sh` — 빌드 후 forkserver 워커 kill 스크립트
