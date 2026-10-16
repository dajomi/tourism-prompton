# 관광지 동선 최적화 API

K-Means 지역 클러스터링 + Nearest Neighbor 기반 관광지 최적 방문 순서 API.
ennoia 멀티에이전트 플랫폼의 Tool로 등록해 사용합니다.

## 실행 방법

```bash
cd optimize_api
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

서버 확인:
```
GET http://localhost:8000/health
→ {"status": "ok", "version": "4.0.0"}
```

API 문서 (Swagger UI):
```
http://localhost:8000/docs
```

---

## 엔드포인트

### GET /health
서버 상태 확인.

---

### GET /optimize
단순 순서 최적화 (Nearest Neighbor).

| 파라미터 | 필수 | 설명 |
|---------|-----|------|
| `spots` | ✅ | `이름1,경도1,위도1\|이름2,경도2,위도2\|...` |
| `start_x` | ❌ | 출발지 경도 (없으면 첫 번째 spot 기준) |
| `start_y` | ❌ | 출발지 위도 |

```
GET /optimize?spots=해운대,129.1604,35.1587|광안리,129.1186,35.1531|태종대,129.0854,35.0490
```

응답:
```json
{
  "optimized_order": [0, 1, 2],
  "optimized_spots": [
    {"original_idx": 0, "name": "해운대", "x": 129.1604, "y": 35.1587},
    {"original_idx": 1, "name": "광안리", "x": 129.1186, "y": 35.1531},
    {"original_idx": 2, "name": "태종대", "x": 129.0854, "y": 35.0490}
  ],
  "total_distance_km": 12.3
}
```

---

### GET /optimize/days
날짜별 동선 최적화 (K-Means + Nearest Neighbor).

| 파라미터 | 필수 | 설명 |
|---------|-----|------|
| `spots` | ✅ | `이름1,경도1,위도1\|이름2,경도2,위도2\|...` |
| `days` | ✅ | 여행 일수 (정수, 1 이상) |
| `hotels` | ❌ | `이름1,경도1,위도1\|이름2,경도2,위도2\|...` (spots와 동일 형식) |

#### 숙소(hotels) 배정 규칙

| hotels 개수 | 동작 |
|------------|------|
| 생략 | 숙소 없이 순서만 반환 |
| 1개 | 전 일정 동일 숙소 사용 |
| 여러 개 | 순서대로 각 날 밤에 배정. 수가 부족하면 마지막 숙소 반복 |

```
hotels[0] → day1 밤 숙박 / day2 출발 기준
hotels[1] → day2 밤 숙박 / day3 출발 기준
...
마지막 날(dayN)은 숙소 없음
```

#### 요청 예시 — 숙소 1개

```
GET /optimize/days
  ?spots=해운대,129.1604,35.1587|광안리,129.1186,35.1531|동백섬,129.2003,35.1531|용두산공원,129.0307,35.1009|태종대,129.0854,35.0490
  &days=2
  &hotels=해운대그랜드호텔,129.1620,35.1600
```

#### 요청 예시 — 숙소 여러 개 (날짜별 다른 호텔)

```
GET /optimize/days
  ?spots=해운대,129.1604,35.1587|광안리,129.1186,35.1531|동백섬,129.2003,35.1531|용두산공원,129.0307,35.1009|자갈치시장,129.0247,35.0973|태종대,129.0854,35.0490
  &days=3
  &hotels=해운대그랜드호텔,129.1620,35.1600|서면롯데호텔,129.0590,35.1580
```

#### 응답 예시

```json
{
  "days": {
    "day1": [
      {"original_idx": 0, "name": "해운대", "x": 129.1604, "y": 35.1587},
      {"original_idx": 2, "name": "동백섬", "x": 129.2003, "y": 35.1531},
      {"original_idx": 1, "name": "광안리", "x": 129.1186, "y": 35.1531},
      {"name": "해운대그랜드호텔", "x": 129.162, "y": 35.16, "type": "숙소"}
    ],
    "day2": [
      {"original_idx": 3, "name": "용두산공원", "x": 129.0307, "y": 35.1009},
      {"original_idx": 4, "name": "자갈치시장", "x": 129.0247, "y": 35.0973},
      {"name": "서면롯데호텔", "x": 129.059, "y": 35.158, "type": "숙소"}
    ],
    "day3": [
      {"original_idx": 5, "name": "태종대", "x": 129.0854, "y": 35.049}
    ]
  },
  "spots_per_day": {"day1": 3, "day2": 2, "day3": 1},
  "total_distance_km": 45.2
}
```

---

## 알고리즘

| 단계 | 내용 |
|-----|------|
| 1. K-Means 클러스터링 | 관광지를 days개 지역 그룹으로 분류. 최원점 우선 탐색(farthest-first traversal)으로 초기 중심을 지리적으로 고르게 분산 (무작위 없음, 결과 재현 가능) |
| 2. 클러스터 순서 결정 | 첫 번째 숙소(또는 첫 관광지) 위치에서 NN으로 클러스터 방문 순서 결정 |
| 3. 마지막 날 조정 | 마지막 날 클러스터가 3개 이상이면 직전 클러스터로 초과분 이동 (최대 2개 유지) |
| 4. 클러스터 내 NN | 각 날짜 내에서 Nearest Neighbor로 방문 순서 최적화 |
| 5. 숙소 처리 | 마지막 날 제외 각 날 마지막에 해당 숙소 추가. 다음 날은 그 숙소에서 출발 |

- 거리 계산: Haversine 공식 (구면 거리, km 단위)
- 외부 의존성 없음 (Python 표준 라이브러리 `math`만 사용)

---

## ngrok으로 외부 노출

ennoia가 로컬 서버에 접근하려면 ngrok으로 퍼블릭 URL을 발급해야 합니다.

### 1. ngrok 설치
```bash
winget install ngrok
# 또는 https://ngrok.com/download 에서 다운로드
```

### 2. 인증 토큰 등록 (최초 1회)
```bash
ngrok config add-authtoken <YOUR_TOKEN>
# 토큰 확인: https://dashboard.ngrok.com/get-started/your-authtoken
```

### 3. 터널 실행 (uvicorn과 별도 터미널에서)
```bash
ngrok http 8000
```

출력 예시:
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:8000
```

---

## ennoia 커넥터 등록 방법

### 방법 1: OpenAPI 자동 등록 (권장)

```
https://abc123.ngrok-free.app/openapi.json
```

ennoia → **Connectors** → **Add Connector** → **OpenAPI** → 위 URL 입력
→ `/optimize`, `/optimize/days`, `/health` 자동 등록

### 방법 2: 수동 Tool 등록

**Tool: route_optimize_days**
- Method: `GET`
- URL: `https://abc123.ngrok-free.app/optimize/days`
- Parameters:
  - `spots` (string, required): `이름1,경도1,위도1|이름2,경도2,위도2|...`
  - `days` (integer, required): 여행 일수
  - `hotels` (string, optional): `이름1,경도1,위도1|이름2,경도2,위도2|...`

### ennoia 에이전트 프롬프트 예시

```
사용자가 여행지 목록과 숙소 정보를 제공하면:
1. 각 장소의 이름, 경도(x), 위도(y)를 수집한다.
2. route_optimize_days 툴을 호출한다.
   - spots: "이름1,경도1,위도1|이름2,경도2,위도2|..."
   - days: 여행 일수
   - hotels: "숙소이름1,경도1,위도1|숙소이름2,경도2,위도2|..." (선택)
3. 반환된 날짜별 동선을 사용자에게 안내한다.
```
