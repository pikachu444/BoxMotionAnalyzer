# Documentation Index

Last Reviewed: 2026-11-16

프로그램 사용, 개발, 검증 기록을 찾는 진입점이다. 현재 동작 안내와 날짜·소스가 명시된 과거 실행 증거를 구분한다.

## 사용자 안내

- [프로젝트 개요·설치·실행·빌드·검사](../README.md)
- [분석 GUI: Step 1 / Step 1.5 / Step 2](analysis/design/gui_overview.md)
- [3D 시각화 사용 흐름](visualization/guide.md)
- [시뮬레이션과 공개 관측 생성 경로](simulation.md)
- [낙하 결과 비교 설계와 해석 범위](analysis/design/drop_result_comparison_plan.md)
- [결과 스키마와 지표 해석](analysis/reference/result_schema_notes.md)

## 개발자 안내와 다음 작업

- [저장소 작업 규칙](../AGENTS.md)
- [분석 작업 인계·남은 작업](analysis/design/implementation_todo.md): 기존 분석 GUI/Drop Posture/비교 기능 백로그 진입점이다. 현재 상태와 과거 완료 기록을 구분한다.
- [시스템 구조](analysis/design/system_design.md)
- [설계 문서 작성 기준](analysis/design/design_docs_guide.md)
- [분석 workflow 참조](analysis/design/workflow.txt)
- [Multi-header CSV 스키마](analysis/reference/csv_multi_header_schema.md)
- [분석 설계 문서](analysis/design/)와 [분석 참조 문서](analysis/reference/)
- [시각화 설계](visualization/design/)와 [런처 레이아웃 기록](launcher/launcher_layout_sketch.txt)

새 설계는 `analysis/design/`, 스키마·export 계약은 `analysis/reference/`, 시각화 안내와 설계는 `visualization/`에 둔다. Mockup은 보조 자료이며 현재 구현을 대신하지 않는다.

## 검증과 날짜가 명시된 기록

- [현재 공개 필수 검사 명령: Windows CI](../.github/workflows/public-marker-validation.yml)
- [PUB01–12 전달 상태·원본 증거·검증 한계](analysis/reference/pub_delivery_status.md)
- [공통 지표·GUI 검증 기록](visualization/gui_metric_parity/validation_report.md)
- [공통 코어 검증 기록](shared_core/validation.md)
- [#198–200 수정·재현·종료 상태](visualization/gui_metric_parity/followups_198_200.md)
- [#200 FinalFace 결정과 과거 대안](visualization/gui_metric_parity/final_face_tail_decision.md)
- [PUB11 회귀 단계·재개·CI 증거 계약](analysis/reference/regression_evidence.md)
- [PUB11 실행·독립 검수 증거 인덱스](analysis/reference/regression_evidence_v1.json)
- [PUB10 관측 profile·채널·검증 계약](analysis/reference/observation_model_contract.md)

과거 커밋·실패·검사 수치는 해당 실행의 증거로 보존한다. 오래된 OPEN/pending 표기를 현재 백로그로 해석하지 않는다. #198/#199는 PR #201로 해결되었고, #200은 기존 processed-row FinalFace 정책을 유지하기로 종료되었다. #104는 독립 실측 자료 부족으로 미실시 종료되었으며 실측 정확도는 미검증이다. 합성 검사·소프트웨어 전달 완료가 물리 정확도나 ISTA 적합성을 보증하지 않는다.
