# 질문 키워드·인자값 기반 페이지 결과 표시와 한국어 요약 형식 고정

- **ID**: 002
- **날짜**: 2026-03-24
- **유형**: 기능 추가

## 작업 요약
사용자 질문에서 추출한 키워드와 인자값이 실제 페이지 결과에 어떻게 반영됐는지 UI에서 바로 확인할 수 있도록 정리했다.
최종답변은 해당 페이지 결과를 기반으로 `핵심 결론` 1줄과 `근거` 2~3줄만 노출하도록 한국어 형식으로 고정했다.

## 변경 파일 목록
- `src/model/struct/agent/tools/read_page_results.py`
  - 페이지 결과 JSON에 `params`를 포함하도록 확장해 질문 인자값이 결과와 함께 전달되게 수정
- `src/model/struct/agent.py`
  - 페이지 결과 fallback/preview/정제 프롬프트를 `핵심 결론 + 근거 2~3줄` 형식으로 재구성
  - 문헌 제목/파일명 대신 페이지 결과 수치·파라미터 중심으로 근거를 설명하도록 조정
- `src/app/component.chat.floating/view.ts`
  - `read_page_results` 결과를 페이지 결과 카드로 저장하고, 답변이 비는 경우에도 같은 형식의 한국어 fallback 답변을 생성하도록 보강
  - 페이지 결과 요약에 query/params/count를 포함하도록 개선
- `src/app/component.chat.floating/view.pug`
  - 실행된 페이지, 질문 키워드, 적용 인자값, 결과 요약을 보여주는 카드 추가
