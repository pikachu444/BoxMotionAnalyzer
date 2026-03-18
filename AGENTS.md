# Repository AGENTS Guide

Last Reviewed: 2026-03-18

이 문서는 저장소 전체에 공통으로 적용하는 작업 원칙을 정리한다.

## 적용 범위
- 이 파일은 저장소 루트 기준의 공통 가이드다.
- 하위 폴더에 별도 `AGENTS.md`가 없다면 이 지침을 기본으로 따른다.

## 기본 원칙
- 실제 코드와 현재 동작을 우선 기준으로 본다.
- 변경은 한 번에 한 주제씩 작게 나눈다.
- 파일 수정 후에는 변경 내용을 먼저 보여주고, 사용자가 확인한 뒤 커밋한다.
- push는 커밋과 별도로 다시 확인한다.

## 문서 작업 원칙
- 루트 `README.md`는 프로젝트 전체 개요와 실행/빌드/테스트 안내를 담당한다.
- `docs/`는 프로젝트 문서의 기준 폴더다.
- `docs/analysis/design/`에는 분석 기능 설계 문서를 둔다.
- `docs/analysis/reference/`에는 결과 스키마, export 형식, 구조 메모 같은 참조 문서를 둔다.
- `docs/visualization/`에는 visualization 가이드와 레이아웃 설계 문서를 둔다.
- 분석 설계 문서를 수정할 때는 `docs/analysis/design/design_docs_guide.md`도 함께 참고한다.
- 저장소에서 관리하는 모든 문서(`.md`, `.txt`)에는 문서 상단에 `Last Reviewed: YYYY-MM-DD`를 유지한다.
- 문서 내용을 검토하거나 의미 있게 수정했으면 `Last Reviewed` 날짜도 함께 갱신한다.

## 현재 Analysis Workflow 기준 문서
- 현재 구현된 `Step 1 / Step 1.5 / Step 2` 흐름은 먼저 `docs/analysis/design/gui_overview.md`에서 확인한다.
- 상위 구조와 설계 원칙은 `docs/analysis/design/system_design.md`를 기준으로 본다.
- batch processing 같은 후속 기능은 현재 구현 범위에 포함되지 않으므로, 문서와 코드에서 별도 확인 전에는 구현된 기능처럼 취급하지 않는다.
- 후속 개발을 다시 시작할 때는 `docs/analysis/design/analysis_followup_plan.md`를 먼저 확인한다.

## 코드 작업 원칙
- 현재 구현과 맞지 않는 구 버전 스크립트, 테스트, 문서는 유지 이유가 없으면 정리 대상이 될 수 있다.
- 컬럼 스키마나 export 형식 변경 시에는 관련 코드와 문서를 함께 확인한다.
- UI 변경 시 mockup, 설계 문서, 사용자 안내문 중 영향을 받는 항목이 있는지 같이 점검한다.

## 커밋/보고 방식
- 커밋 제목은 영어로 작성한다.
- 커밋 본문은 영어로 작성한다.
- 사용자에게 보고할 때는 영문 커밋 메시지를 먼저 보여주고, 이어서 한글 설명을 제공한다.
- PR 제목과 본문 초안을 작성할 때는 영어 버전을 먼저 쓰고, 바로 아래에 한글 버전을 함께 제공한다.
- PR 본문은 가능하면 아래 형식을 따른다.

```text
English
- Summary
- Changes
- Testing
- Risks / Notes

한국어
- 요약
- 변경 사항
- 테스트
- 리스크 / 참고사항
```
