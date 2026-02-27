# PDF 임베딩 파이프라인 전면 리팩토링

- **ID**: 001
- **날짜**: 2026-02-25
- **유형**: 기능 추가 / 리팩토링

## 작업 요약
PDF 임베딩 파이프라인을 전면 리팩토링하여 (1) PyMuPDF dict 기반 스마트 텍스트 추출(그림/수식/표/헤더 감지), (2) 섹션→문단→문장 기반 시맨틱 청킹, (3) 5개 한글 특화 임베딩 모델 레지스트리, (4) Milvus 컬렉션 CRUD 관리, (5) 전체 4개 페이지 동적 컬렉션/모델 지원을 구현했다.

## 변경 파일 목록

### page.embedding (핵심 파이프라인)
| 파일 | 변경 | 내용 |
|------|------|------|
| `src/app/page.embedding/api.py` | 전면 재작성 | 스마트 추출(_extract_text_from_pdf), 시맨틱 청킹(_chunk_text), MODEL_REGISTRY(5종), 컬렉션 CRUD(models/collections/create_collection/delete_collection), upload/stats 리팩토링 |
| `src/app/page.embedding/view.ts` | 전면 재작성 | 모델/컬렉션 선택 상태, loadModels/loadCollections/createCollection/deleteCollection, 청킹 옵션(chunkSize, chunkOverlap, respectSentences) |
| `src/app/page.embedding/view.pug` | 전면 재작성 | 모델 드롭다운, 컬렉션 관리 테이블, 고급 청킹 옵션, 4단계 안내 |

### page.research (동적 컬렉션 지원)
| 파일 | 변경 | 내용 |
|------|------|------|
| `src/app/page.research/api.py` | 전면 재작성 | _resolve_collection_and_model(), collections() API, 모든 함수에 동적 컬렉션/모델 |
| `src/app/page.research/view.ts` | 수정 | collections[], selectedCollection, loadCollections(), 모든 API 호출에 collection 파라미터 |
| `src/app/page.research/view.pug` | 수정 | nav 우측에 컬렉션 선택 드롭다운 추가 |

### page.prediction (동적 컬렉션 지원)
| 파일 | 변경 | 내용 |
|------|------|------|
| `src/app/page.prediction/api.py` | 전면 재작성 | 동일 패턴 적용 |
| `src/app/page.prediction/view.ts` | 수정 | 컬렉션 선택 + onCollectionChange로 stats 리로드 |
| `src/app/page.prediction/view.pug` | 수정 | nav 우측 컬렉션 드롭다운, 모델 정보 동적 표시 |

### page.diagnosis (동적 컬렉션 지원)
| 파일 | 변경 | 내용 |
|------|------|------|
| `src/app/page.diagnosis/api.py` | 전면 재작성 | 동일 패턴 적용 |
| `src/app/page.diagnosis/view.ts` | 수정 | 컬렉션 선택 + 모든 API에 collection 전달 |
| `src/app/page.diagnosis/view.pug` | 수정 | nav 우측 컬렉션 드롭다운 |

## 핵심 아키텍처 변경

### 모델 레지스트리 패턴
```python
MODEL_REGISTRY = {
    "snunlp/KR-SBERT-V40K-klueNLI-augSTS": {"dim": 768, "short_name": "KR-SBERT"},
    "BM-K/KoSimCSE-roberta-multitask": {"dim": 768, "short_name": "KoSimCSE"},
    "intfloat/multilingual-e5-large": {"dim": 1024, "short_name": "mE5-Large"},
    "jhgan/ko-sroberta-multitask": {"dim": 768, "short_name": "ko-sroberta"},
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": {"dim": 384, "short_name": "MiniLM-L12"}
}
```

### 컬렉션 메타데이터
- `/opt/app/data/collection_meta.json`에 각 컬렉션별 model, dim, created_at 저장
- 다른 페이지에서 컬렉션 선택 시 자동으로 해당 모델을 로드

### 동적 컬렉션/모델 해석 공통 함수
```python
def _resolve_collection_and_model():
    collection_name = wiz.request.query("collection", DEFAULT_COLLECTION)
    model_name = _get_collection_model(collection_name)  # meta.json에서 조회
    return collection_name, model_name
```
