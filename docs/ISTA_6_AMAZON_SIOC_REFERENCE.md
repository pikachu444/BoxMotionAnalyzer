# ISTA 6-Amazon.com SIOC 규격 참조 정보 (Type G & Type H)

본 문서는 Box Motion Analyzer 시뮬레이션 모듈에 구현된 ISTA 6-Amazon.com SIOC 규격 중 **TV/Monitor**에 특화된 Type G와 Type H의 핵심 낙하 테스트(Drop Test) 규격을 정리한 레퍼런스 문서입니다.

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
*   **17회 시퀀스 구성:** (예시: Edge 3-4, Edge 3-6, Corner 3-4-6 등. 여기서 번호는 위 Type G의 Face 번호를 따름)

### 3.2 Type H (총 12회 낙하/팁)
LTL(Less-Than-Truckload) 화물의 특성상 지게차 작업 및 팔레트 적재를 가정하여 Tip/Overturn(전도)과 Flat Drop(평면 낙하), Rotational Edge Drop(회전 모서리 낙하) 등 총 12회의 시퀀스로 구성됩니다.
*   **높이:** 300mm, 460mm, 810mm 등이 섞여서 적용됩니다.

---
*참고: 상세한 17개 및 12개 시퀀스의 목록 및 각도 매핑 로직은 `src/simulation/scenarios.py` 내부에 수학적으로 반영되어 있습니다.*

## 4. References & Sources
- **ISTA Project 6-AMAZON.COM-SIOC Test Protocol** (Type G: Packaged-Products for TV/Monitor less than 150 lbs, Type H: LTL Delivery). The drop sequences, heights, and specific Face Numbering rules mapping (where Face 1 is Rear for Type G, and Face 1 is Top for Type H) are derived directly from this official standard.
