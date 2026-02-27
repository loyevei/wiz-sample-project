# Diagnosis 파이프라인 6-탭 대시보드 구현

- **ID**: 003
- **날짜**: 2026-02-26
- **유형**: 기능 추가

## 작업 요약
진단(Diagnosis) 페이지를 기존 3탭(검색/비교/이상검색)에서 6탭 대시보드로 확장. OES Spectrum Embedding, Multimodal Retrieval, Anomaly Detection, Failure Case Reasoning 4개 핵심 기능을 새로 구현하고 기존 기능을 재편성함.

## 변경 파일 목록

### Backend (api.py)
- `src/app/page.diagnosis/api.py` — 전면 재작성 (~600줄)
  - **스펙트럼 처리 엔진**: `_parse_spectrum_text()`, `_resample_spectrum()` (512-bin 리샘플링), `_detect_peaks()` (scipy.signal.find_peaks), `_identify_species()` (~40개 발광선 매칭)
  - **OES Spectrum Embedding**: `upload_spectrum`, `search_similar_spectrum`, `spectrum_list`, `delete_spectrum`
  - **Multimodal Retrieval**: `multimodal_search` (텍스트+스펙트럼 가중 결합)
  - **Anomaly Detection**: `set_baseline`, `get_baseline`, `check_anomaly`, `anomaly_history_list`, `update_threshold`, `clear_history`
  - **Failure Case Reasoning**: `failure_reasoning`, `register_failure_pattern`, `list_failure_patterns`, `delete_failure_pattern`
  - **기존 보존**: `collections`, `search_diagnostic`, `compare_diagnostics`, `anomaly_search`, `overview` (통계 확장)

### Frontend (view.ts)
- `src/app/page.diagnosis/view.ts` — 전면 재작성 (~300줄)
  - 6탭 관리 시스템 (search/spectrum/multimodal/detection/failure/compare)
  - 탭별 상태 변수 및 로직 (파일 업로드, API 호출, 결과 표시)
  - Helper 메서드: `severityColor()`, `severityBg()`, `severityLabel()`, `objectKeys()`

### Template (view.pug)
- `src/app/page.diagnosis/view.pug` — 전면 재작성 (~350줄)
  - 상단: 컬렉션 선택 + 4-column 통계 카드
  - 6개 탭 UI (스크롤 가능 네비게이션)
  - 각 탭별 입력 폼 + 결과 표시 영역

### 데이터 파일 (JSON, /opt/app/data/)
- `spectrum_db.json` — 스펙트럼 DB (임베딩 포함)
- `anomaly_baseline.json` — 정상 공정 베이스라인 (centroid)
- `anomaly_history.json` — 이상 탐지 이력
- `failure_patterns.json` — 등록된 고장 패턴

## 기술 상세
- 스펙트럼 → 512차원 벡터 리샘플링 (200~1100nm 선형 보간)
- 피크 감지: scipy.signal.find_peaks (height/prominence/distance)
- 화학종 식별: 40개 발광선 DB (Ar I, O I, N2, H-alpha/beta, C, CF, F, Cl, Si, He)
- 이상 탐지: 코사인 거리 기반 (centroid 대비), severity 스케일링
- 멀티모달: 텍스트 score × text_weight + 스펙트럼 score × spectrum_weight → combined_score
