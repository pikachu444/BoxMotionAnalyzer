# Design Docs Guide

Last Reviewed: 2026-03-08

이 문서는 `design_proposal/` 폴더 안의 설계 문서를 정리하거나 갱신할 때 참고하는 가이드다.

## 적용 범위
- 이 문서는 저장소 전체가 아니라 `design_proposal/` 문서에만 적용한다.
- 실제 동작의 기준은 항상 현재 코드이며, 설계 문서는 그 구현을 설명하도록 유지한다.

## 먼저 확인할 기준 파일
설계 문서를 수정할 때는 아래 파일을 먼저 확인한다.

1. `src/analysis/main_window.py`
2. `src/analysis/ui/widget_raw_data_processing.py`
3. `src/analysis/ui/widget_results_analyzer.py`
4. `src/analysis/ui/plot_popup_dialog.py`
5. `src/config/data_columns.py`
6. 루트 `README.md`

코드와 설계 문서가 충돌하면 코드 기준으로 문서를 수정한다.

## 문서 작성 원칙
- 현재 구현된 Step 1 / Step 2 흐름을 기준으로 작성한다.
- 제거된 기능, 임시 prototype, 과거 UI 흐름을 현재 기능처럼 서술하지 않는다.
- 사용자가 현재 기능과 흐름을 이해할 수 있게 설명하되, 구현되지 않은 추측은 넣지 않는다.
- 문서끼리 역할이 겹치면 하나의 문서에 몰아넣지 말고 목적에 따라 나눈다.

## 현재 문서 역할
- `software_design_document.md`
  - 전체 설계 개요
- `gui_description.md`
  - 현재 GUI 구조와 사용자 흐름 설명
- `component_specs.txt`
  - 주요 컴포넌트 책임 정리
- `data_structures.txt`
  - 핵심 데이터 구조와 DataFrame 흐름 정리
- `scenario_export_format.md`
  - Step 2 scenario export 형식 설명
- `flow_chart.txt`
  - 현재 작업 흐름 요약
- `gui_sketch.txt`
  - 현재 레이아웃 개요

## 수정 후 확인할 항목
- Step 1 export 후 Step 2 자동 로드/자동 전환 흐름이 반영돼 있는가
- timeline metadata와 multi-header 결과 구조 설명이 현재 코드와 맞는가
- popup plot 흐름이 현재 구현과 맞는가
- 결과 컬럼 naming이 `src/config/data_columns.py`와 맞는가
