# ISTA 6-Amazon.com SIOC 규격 참조 정보 (Type G & Type H)

본 문서는 Box Motion Analyzer 시뮬레이션 모듈에 구현된 ISTA 6-Amazon.com SIOC 규격 중 **TV/Monitor**에 특화된 Type G와 Type H의 핵심 낙하 테스트(Drop Test) 규격을 정리한 레퍼런스 문서입니다.

이 문서를 정리할 때 직접 참고한 외부 URL:

- ANSI storefront: https://webstore.ansi.org/standards/ansi/istaprojectamazonsioc2018
- Public excerpt used for Type G sequence / orientation cross-checks:
  https://d39w7f4ix9f5s9.cloudfront.net/32/98/c52dd6b841f18bcb8af679b1f1ac/9.TESTING_thumbnail_ISTA%20Project%206-Amazon.com-SIOC%2018-18.pdf

관련 로컬 경로:

- [simulation.md](/root/BoxMotionAnalyzer/docs/simulation.md)
- [simulation_external_reference_notes.md](/root/BoxMotionAnalyzer/docs/simulation_external_reference_notes.md)
- [scenarios.py](/root/BoxMotionAnalyzer/src/simulation/scenarios.py)

## 1. 개요
TV 및 모니터 제품군은 일반적인 택배 상자(Parcel)와 달리 화면(Screen)의 보호가 가장 중요합니다. 따라서 ISTA 규격에서는 이들을 일반 화물과 구분하여 **Type G (Parcel, 68kg 미만)** 와 **Type H (LTL, 68kg 이상)** 로 분류하고, 고유의 면 번호(Face Numbering) 규칙과 낙하 시퀀스를 적용합니다.

## 2. Face Numbering (면 번호 부여 규칙) 차이점
가장 큰 특징은 "TV의 스크린 방향"을 기준으로 면 번호가 다르다는 점입니다.

*   **Type G (Parcel Delivery, < 68kg)**
    *   Face 1: Rear (후면)
    *   Face 2: Bottom (바닥면)
    *   Face 3: Screen (전면)
    *   Face 4: Top (상면)
    *   Face 5: Right (우측면)
    *   Face 6: Left (좌측면)

*   **Type H (LTL Delivery, >= 68kg)**
    *   Face 1: Top (상면)
    *   Face 2: Rear (후면)
    *   Face 3: Bottom (바닥면)
    *   Face 4: Screen (전면)
    *   Face 5: Right (우측면)
    *   Face 6: Left (좌측면)

> **프로그램 내 로컬 축 매핑:**
> Box Motion Analyzer 시뮬레이션은 `[Width(X), Height(Y), Thickness/Depth(Z)]`를 사용합니다.
> 따라서 **X=Right(+)/Left(-), Y=Top(+)/Bottom(-), Z=Screen(+)/Rear(-)** 로 매핑됩니다.

## 3. Drop Test Sequence (낙하 시퀀스)
### 3.1 Type G (총 17회 낙하)
중량(Weight)에 따라 낙하 높이가 달라지며, 특정 Edge와 Corner를 포함한 17회의 가혹한 연속 낙하를 수행합니다.
*   **중량 기준 낙하 높이:**
    *   32kg 미만: 일반 460mm, 특정 시퀀스(High) 910mm
    *   32kg 이상: 일반 300mm, 특정 시퀀스(High) 610mm
*   **17회 시퀀스 구성:** (번호는 위 Type G의 Face 번호를 따름)

| Drop # | < 32 kg | 32-68 kg | Orientation |
|---|---:|---:|---|
| 1 | 460 mm | 300 mm | Edge 3-4 |
| 2 | 460 mm | 300 mm | Edge 3-6 |
| 3 | 460 mm | 300 mm | Edge 4-6 |
| 4 | 460 mm | 300 mm | Corner 3-4-6 |
| 5 | 460 mm | 300 mm | Corner 2-3-5 |
| 6 | 460 mm | 300 mm | Edge 2-3 |
| 7 | 460 mm | 300 mm | Edge 1-2 |
| 8 | 910 mm | 610 mm | Face 3 |
| 9 | 460 mm | 300 mm | Face 3 |
| 10 | 460 mm | 300 mm | Edge 3-4 |
| 11 | 460 mm | 300 mm | Edge 3-6 |
| 12 | 460 mm | 300 mm | Edge 1-5 |
| 13 | 460 mm | 300 mm | Corner 3-4-6 |
| 14 | 460 mm | 300 mm | Corner 1-2-6 |
| 15 | 460 mm | 300 mm | Corner 1-4-5 |
| 16 | 910 mm | 610 mm | Most critical or damage-prone flat orientation (unknown이면 Face 6) |
| 17 | 460 mm | 300 mm | Standard: Face 3 on hazard / Elongated or Flat: Face 2 on hazard |

> 위 표는 공개된 ISTA 6-Amazon.com-SIOC 2018 원문 일부(Test Block 2, Test Block 15)에서 확인되는 Type G TV/Monitor sequence를 기준으로 정리했습니다.

### 3.1.1 Type G 자세(Angle) 정의 방식
Type G 규격은 일반적으로 `roll / pitch / yaw` 숫자를 직접 주지 않고, **어느 Face / Edge / Corner가 먼저 충돌해야 하는지**로 자세를 정의합니다.

- `Face n`: 해당 face가 바닥을 향하도록 둔다.
- `Edge a-b`: face `a`와 face `b`가 만나는 모서리 선이 먼저 닿도록 기울인다.
- `Corner a-b-c`: face `a`, `b`, `c`가 만나는 꼭짓점이 먼저 닿도록 기울인다.

중요한 점은 **기울기 크기(tilt magnitude)가 박스 치수에 따라 달라진다**는 것입니다.  
Box Motion Analyzer의 로컬 축을 `[Width(X), Height(Y), Depth(Z)]`라고 할 때:

- `Face`는 단일 축 방향만 맞추면 되므로 크기 비율 영향이 없다.
- `Edge`는 해당 edge 중심 벡터를 기준으로 기울여야 한다.
  - 예: `Edge 3-4`는 `Screen(+Z)`와 `Top(+Y)`가 동시에 낮아져야 하므로 목표 벡터는 `(0, +H, +D)`에 비례한다.
  - 예: `Edge 3-6`은 목표 벡터가 `(-W, 0, +D)`에 비례한다.
- `Corner`는 해당 corner 중심 벡터를 기준으로 기울여야 한다.
  - 예: `Corner 3-4-6`은 목표 벡터가 `(-W, +H, +D)`에 비례한다.

즉 Type G의 각도는 규격이 숫자로 직접 주는 것이 아니라, **규격이 정의한 접촉 자세와 박스의 실제 치수 비율로부터 계산**해야 합니다.

#### Type G 시퀀스별 접촉 의미와 목표 벡터

아래 표의 `목표 벡터`는 박스 중심에서 해당 접촉 면/선/점 방향으로 향하는 벡터를 뜻합니다.  
실제 각도는 이 벡터가 월드 아래 방향을 향하도록 계산됩니다.

| Drop # | Orientation | 접촉 의미 | 목표 벡터 |
|---|---|---|---|
| 1 | Edge 3-4 | Screen-Top edge | `(0, +H, +D)` |
| 2 | Edge 3-6 | Screen-Left edge | `(-W, 0, +D)` |
| 3 | Edge 4-6 | Top-Left edge | `(-W, +H, 0)` |
| 4 | Corner 3-4-6 | Screen-Top-Left corner | `(-W, +H, +D)` |
| 5 | Corner 2-3-5 | Bottom-Screen-Right corner | `(+W, -H, +D)` |
| 6 | Edge 2-3 | Bottom-Screen edge | `(0, -H, +D)` |
| 7 | Edge 1-2 | Rear-Bottom edge | `(0, -H, -D)` |
| 8 | Face 3 | Screen face, high drop | `(0, 0, +D)` |
| 9 | Face 3 | Screen face | `(0, 0, +D)` |
| 10 | Edge 3-4 | Screen-Top edge, second sequence | `(0, +H, +D)` |
| 11 | Edge 3-6 | Screen-Left edge, second sequence | `(-W, 0, +D)` |
| 12 | Edge 1-5 | Rear-Right edge | `(+W, 0, -D)` |
| 13 | Corner 3-4-6 | Screen-Top-Left corner, second sequence | `(-W, +H, +D)` |
| 14 | Corner 1-2-6 | Rear-Bottom-Left corner | `(-W, -H, -D)` |
| 15 | Corner 1-4-5 | Rear-Top-Right corner | `(+W, +H, -D)` |
| 16 | Most critical flat orientation | unknown이면 Face 6 | `(-W, 0, 0)` |
| 17 | Hazard orientation | default Face 2 | `(0, -H, 0)` |

### 3.2 Type H (총 12회 낙하/팁)
LTL(Less-Than-Truckload) 화물의 특성상 지게차 작업 및 팔레트 적재를 가정하여 Tip/Overturn(전도)과 Flat Drop(평면 낙하), Rotational Edge Drop(회전 모서리 낙하) 등 총 12회의 시퀀스로 구성됩니다.
*   **높이:** 300mm, 460mm, 810mm 등이 섞여서 적용됩니다.

> 참고: Type H는 공개 자료상 `Tip/Tip Over`의 `22 degree tip angle`, `Rotational Flat/Edge/Corner Drop`의 `9 in (230 mm)` lift/drop height 같은 절차 규정이 보입니다.  
> 현재 저장소 구현은 Type H를 단순화한 부분이 있으므로, 추후 원문 기준으로 별도 재정렬이 필요합니다.

---
*참고: 상세한 17개 및 12개 시퀀스의 목록 및 각도 매핑 로직은 `src/simulation/scenarios.py` 내부에 수학적으로 반영되어 있습니다.*

## 4. References & Sources
- **ISTA Project 6-AMAZON.COM-SIOC Test Protocol** (Type G: Packaged-Products for TV/Monitor less than 150 lbs, Type H: LTL Delivery). The drop sequences, heights, and specific Face Numbering rules mapping (where Face 1 is Rear for Type G, and Face 1 is Top for Type H) are derived directly from this official standard.
