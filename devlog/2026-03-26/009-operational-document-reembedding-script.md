# 운영 컬렉션 문서 재임베딩 스크립트 추가

- **ID**: 009
- **날짜**: 2026-03-26
- **유형**: 기능 추가

## 작업 요약
운영 Milvus 컬렉션에서 특정 문서를 다시 임베딩할 수 있도록 독립 실행형 스크립트를 추가했다.
원본 PDF가 있으면 현재 임베딩 파이프라인으로 재추출/재청킹 후 재삽입하고, 원본 PDF가 없어도 기존 저장 청크를 읽어 publication timeline 메타를 보강한 뒤 제자리 재임베딩할 수 있게 구성했다.

## 변경 파일 목록
- `scripts/reembed_document.py`
  - `--collection`, `--doc-id`, `--filename`, `--pdf` 인자를 받는 CLI 스크립트 추가
  - PDF 입력 시 `page.embedding`의 최신 추출/청킹/임베딩 로직 재사용
  - PDF가 없을 때는 기존 Milvus 청크를 읽어 temporal metadata를 보강하고 재임베딩
  - `--dry-run` 지원으로 삭제/삽입 없이 preview 가능
- `devlog.md`
  - 작업 인덱스 추가

## 검증
- `python3 -m py_compile /opt/app/project/main/scripts/reembed_document.py`
- `python3 /opt/app/project/main/scripts/reembed_document.py --help`
- `python3 /opt/app/project/main/scripts/reembed_document.py --collection plasma_papers_eng --doc-id 01408398 --dry-run`

## 사용 예시
- 기존 청크 기반 재임베딩
  - `python3 scripts/reembed_document.py --collection plasma_papers_eng --doc-id 01408398 --dry-run`
- 원본 PDF 기반 재임베딩
  - `python3 scripts/reembed_document.py --collection plasma_papers_eng --doc-id 01408398 --pdf /path/to/file.pdf`
