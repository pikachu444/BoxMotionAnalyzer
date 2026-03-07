# Documentation Index

Last Reviewed: 2026-03-08

이 문서는 `docs/` 폴더 안내용 인덱스다. 루트 `README.md`와 달리 프로젝트 전체 소개나 실행 방법을 반복하지 않고, 어떤 문서를 언제 보면 되는지만 정리한다.

## 먼저 어디를 보면 되나
- 프로젝트를 처음 이해할 때
  - 루트 `README.md`
- 현재 GUI 설계와 작업 흐름을 보고 싶을 때
  - `design_proposal/`
- 결과 CSV 구조나 시각화 내부 동작 같은 세부 참고자료가 필요할 때
  - `docs/`

## 이 폴더의 문서 역할
- `documentation_index.md`
  - 이 폴더의 안내문
- `visualization_guide.md`
  - 3D visualization 기능의 구조와 사용 흐름 설명
- `changeheader.txt`
  - 결과 CSV multi-header 규칙 정리
- `code_structure_analysis.md`
  - 결과 컬럼 스키마와 구현 연결 구조 메모
- `launcher_layout_sketch.txt`
  - 런처 창 레이아웃 스케치

## 문서 분리 원칙
- 루트 `README.md`
  - 프로젝트 소개, 실행 방법, 빌드/테스트 안내
- `design_proposal/`
  - 현재 설계와 워크플로우 설명
- `docs/`
  - 구현 참고 문서와 기능별 보조 설명

## 정리 기준
- 같은 이름의 `README.md`가 여러 개 보이면 역할이 헷갈릴 수 있으므로, `docs/` 안 안내문은 `documentation_index.md`로 분리했다.
- 내부 구현 메모 성격이 강한 문서는 가능한 한 사용자 안내문과 이름부터 구분한다.
