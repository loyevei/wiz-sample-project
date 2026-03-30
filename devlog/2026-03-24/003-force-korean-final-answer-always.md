# 최종답변 한국어 고정

- **ID**: 003
- **날짜**: 2026-03-24
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇의 최종답변이 질문 언어와 관계없이 항상 한국어로 출력되도록 언어 지시를 정리했다.
백엔드 프롬프트, 군집형 에이전트 synthesizer 지시, 실행 trace의 언어 표시를 모두 한국어 고정 기준으로 통일했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - 시스템 프롬프트의 `same language` 지시를 제거하고 항상 한국어 응답으로 고정
  - synthesizer cluster 지시를 한국어 최종답변 생성 기준으로 변경
  - trace의 언어 판별 설명을 한국어 고정 문구로 수정
- `src/app/component.chat.floating/view.ts`
  - 초기 trace 언어 표시가 항상 `ko`를 사용하도록 수정
