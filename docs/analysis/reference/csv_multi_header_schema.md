# CSV Multi-Header 스키마 (v3)

Last Reviewed: 2026-09-08

이 문서는 현재 코드 기준의 결과 CSV Multi-Header 규칙을 정리한다.

## 1. 헤더 계층
- Level 1 (L1): `Position`, `Velocity`, `Acceleration`, `Analysis`, `Analysis Scenario`, `Etc`, `Info`
- Level 2 (L2): `CoM`, `C1`~`C8`, 기타 객체/정보 그룹
- Level 3 (L3): 실제 측정 키

## 2. 핵심 네이밍 규칙
- Position: `P_T*`, `P_R*`
  - 예: `P_TX`, `P_RZ`
- Velocity:
  - Global: `Global_V_T*`, `Global_V_R*`
  - BoxLocal: `BoxLocal_V_T*`, `BoxLocal_V_R*`
- Acceleration:
  - Global: `Global_A_T*`, `Global_A_R*`
  - BoxLocal: `BoxLocal_A_T*`, `BoxLocal_A_R*`
- Norm 표기: 항상 `*_Norm`
  - 예: `Global_V_T_Norm`, `BoxLocal_A_R_Norm`

## 3. CoM 기준 주요 결과 키
- Position/CoM:
  - `P_TX`, `P_TY`, `P_TZ`, `P_RX`, `P_RY`, `P_RZ`
- Velocity/CoM:
  - BoxLocal 먼저: `BoxLocal_V_TX` ... `BoxLocal_V_R_Norm`
  - Global 나중: `Global_V_TX` ... `Global_V_R_Norm`
- Acceleration/CoM:
  - BoxLocal 먼저: `BoxLocal_A_TX` ... `BoxLocal_A_R_Norm`
  - Global 나중: `Global_A_TX` ... `Global_A_R_Norm`

## 4. Corner (C1~C8) 규칙
- Position: `P_TX`, `P_TY`, `P_TZ`
- Velocity: `Global_V_TX`, `Global_V_TY`, `Global_V_TZ`, `Global_V_T_Norm`
- Corner에는 Rotation 성분(`R*`)을 두지 않는다.

## 5. _Ana 정책
- 기존 `_Ana` 접미사 기반 키는 신규 스키마에서 사용하지 않는다.
- 로컬 좌표계 결과는 `BoxLocal_` 접두사로 표기한다.

## 6. 변환/저장 규칙 메모
- Export는 `src/utils/header_converter.py`의 규칙을 따른다.
- `RigidBody_Position_*`는 `(Position, RigidBody, P_T*)`로 유지한다.
  - CoM 포즈(`P_T*`, `P_R*`)와 중복 충돌을 피하기 위한 정책.

## 6-1. Marker correction provenance
- corrected source 기반 결과는 Level 1 `Info`, Level 2 `MarkerCorrection` 그룹을 사용한다.
- Level 3 키:
  - `SchemaVersion`
  - `AlgorithmVersion`
  - `OriginalSource`
  - `OriginalSourceSha256`
  - `ReviewedSource`
  - `EventCount`
  - `ApprovedEventCount`
  - `EventsJson`
  - `ContextJson`
- `EventCount`는 OFF 판단까지 포함한 전체 검토 이벤트 수이고, `ApprovedEventCount`는 실제 적용 이벤트 수다.
- `EventsJson`에는 recommendation과 operator decision/axis/permutation을 분리해 저장한다.

### v3 corrected raw / slice의 면 할당

결과의 3-level multi-header 버전과 corrected raw 버전은 별개다. Corrected raw v3는 기존 2줄 metadata + 6줄 raw header를 유지하며 각 Rigid Body Marker에 하나씩 annotation 열을 추가한다. `type=Marker Annotation`, `category=Assignment`, `component=Face`, name/id/parent는 해당 XYZ 열과 동일하다. 모든 마커를 덮는 완전한 annotation 집합과 알려진 면 값이 필요하다.

본문 annotation이 실제 분석 입력이며 EventsJson은 감사 이력이다. Parser는 이력을 재적용하지 않는다. 사건 이후부터 시작하는 slice도 행별 면을 그대로 가진다. ContextJson에는 원본 면, 박스 크기(mm), 좌표 정책, 원본 export metadata/헤더 두 줄, 원본 SHA와 알고리즘 버전을 보존한다. 승인 당시 크기와 다른 corrected slice는 거부한다. 일반 Motive CSV 또는 v2에 annotation을 붙여 새 보정처럼 읽지 않는다.

## 7. TestSets 폴더 정책
- `TestSets/Input/`: 버전관리 대상 입력 데이터
- `TestSets/Output/`: 로컬 산출물 전용, `.gitignore` 대상
