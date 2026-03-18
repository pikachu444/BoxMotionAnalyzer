# Design Docs Guide

Last Reviewed: 2026-03-18

이 문서는 `docs/analysis/design/` 아래 분석 기능 설계 문서를 정리하거나 갱신할 때 참고하는 가이드다.

## 적용 범위
- 저장소 전체가 아니라 `docs/analysis/design/` 문서에 적용한다.
- 실제 동작 기준은 항상 현재 코드이며, 설계 문서는 그 구현을 설명하도록 유지한다.

## 먼저 확인할 기준 파일
1. `src/analysis/app/main_window.py`
2. `src/analysis/ui/widget_raw_data_processing.py`
3. `src/analysis/ui/widget_slice_processing.py`
4. `src/analysis/ui/widget_results_analyzer.py`
5. `src/analysis/ui/plot_popup_dialog.py`
6. `src/config/data_columns.py`
7. 루트 `README.md`

코드와 설계 문서가 충돌하면 코드를 기준으로 문서를 수정한다.

## 설계 문서 작성 원칙
- 현재 구현된 Step 1 / Step 1.5 / Step 2 흐름을 기준으로 쓴다.
- 과거 prototype이나 폐기된 UI 흐름을 현재 기능처럼 서술하지 않는다.
- 기능 설명과 구조 설명을 분리하고, reference 성격 문서는 `../reference/`에 둔다.

## 이 폴더의 문서 역할
- `system_design.md`
  - 분석 기능 전체 설계 개요
- `gui_overview.md`
  - 현재 분석 GUI 구조와 사용자 흐름 설명
- `component_specs.txt`
  - 주요 컴포넌트 책임 정리
- `workflow.txt`
  - 현재 작업 흐름 요약
- `gui_sketch.txt`
  - 현재 레이아웃 개요
- `gui_mockups/`
  - historical/reference mockup 이미지와 생성 스크립트
  - 현재 구현을 설명하는 기준 문서는 아니므로, 코드와 현재 구조 문서보다 우선하지 않는다

## 함께 확인할 reference 문서
- `../reference/pipeline_data_structures.txt`
- `../reference/scenario_export_format.md`
- `../reference/csv_multi_header_schema.md`
- `../reference/result_schema_notes.md`

## 수정 후 체크 항목
- Step 1 / Step 1.5 / Step 2 역할 분리가 현재 코드와 맞는가
- `.csv / .slice / .proc` 파일 흐름 설명이 현재 코드와 맞는가
- Step 1.5가 `.proc` 저장을 중심으로 설명돼 있는가
- timeline metadata와 multi-header 구조 설명이 현재 코드와 맞는가
- popup plot 흐름이 현재 구현과 맞는가
- 결과 컬럼 naming이 `src/config/data_columns.py`와 맞는가
