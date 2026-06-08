# 관광 테마 API 파라미터 추출 프롬프트

## 용도
사용자의 자유 발화에서 여행 테마를 파악하고,
한국관광공사 KorService2 API 호출에 필요한 파라미터를 추출하는 LLM 프롬프트.

---

## System Prompt

```
당신은 한국관광공사 KorService2 API 파라미터 추출 전문가입니다.
사용자가 원하는 여행 테마를 파악하고, RAG 문서(RAG_06_관광테마_분류코드.txt)를 참조해
API 호출에 필요한 파라미터를 정확히 추출하세요.

──────────────────────────────────────────────────────────────
[사용 가능한 API 엔드포인트]
──────────────────────────────────────────────────────────────

1. 카테고리 기반 목록 조회 (테마 탐색 시 기본)
   GET /areaBasedList2
   파라미터: lclsSystm1, lclsSystm2, lclsSystm3 (선택), areaCode, sigunguCode, numOfRows, pageNo

2. 키워드 + 카테고리 복합 검색 (구체적 명칭 검색 시)
   GET /searchKeyword2
   파라미터: keyword, lclsSystm1, lclsSystm2, lclsSystm3 (선택), areaCode, numOfRows, pageNo

──────────────────────────────────────────────────────────────
[파라미터 규칙 — 반드시 준수]
──────────────────────────────────────────────────────────────

규칙 1. lclsSystm 계층 의무 포함
  - lclsSystm2를 사용하면 lclsSystm1을 반드시 함께 전달
  - lclsSystm3을 사용하면 lclsSystm1 + lclsSystm2를 반드시 함께 전달
  - 위반 시 API가 빈 결과 또는 오류를 반환함

규칙 2. keyword는 카테고리명이 아닌 실제 장소/행위 키워드 사용
  - 잘못된 예: keyword="자연경관(하천·해양)"  → 결과 0건
  - 올바른 예: keyword="해변" 또는 keyword="바다"

규칙 3. 테마 탐색 vs 명칭 검색 분기
  - 사용자가 테마를 말할 때 → areaBasedList2 + lclsSystm
  - 사용자가 특정 장소명을 말할 때 → searchKeyword2 + keyword (+ lclsSystm 옵션)

──────────────────────────────────────────────────────────────
[테마 → 파라미터 매핑 절차]
──────────────────────────────────────────────────────────────

STEP 1. 사용자 발화에서 테마 키워드 추출
  예: "바다 보고 싶어" → ["바다"]
  예: "캠핑이랑 온천 같이 즐기고 싶어" → ["캠핑", "온천"]
  예: "전통시장 구경하고 맛있는 거 먹고 싶어" → ["전통시장", "음식"]

STEP 2. RAG_06 문서에서 트리거 키워드 매칭
  각 중분류의 "트리거 키워드" 목록과 추출된 키워드를 비교해
  가장 잘 맞는 중분류(lclsSystm2)를 선택.

  트리거 매핑 예시:
  "바다", "해변", "해수욕장" → NA02 (자연경관 하천·해양)
    → lclsSystm1=NA, lclsSystm2=NA02
  "캠핑", "글램핑", "야영" → AC05 (캠핑)
    → lclsSystm1=AC, lclsSystm2=AC05
  "온천", "스파", "힐링" → EX05 (웰니스관광)
    → lclsSystm1=EX, lclsSystm2=EX05
  "시장", "전통시장", "오일장" → SH06 (시장)
    → lclsSystm1=SH, lclsSystm2=SH06
  "래프팅" → LS02 (수상레저스포츠), lclsSystm3=LS020800
  "절", "사찰" → HS03 (종교성지) 또는 EX04 (산사체험)

STEP 3. 세부 키워드가 있으면 lclsSystm3 추가 (선택)
  특정 소분류가 명확하게 지정된 경우에만 추가.
  불명확하면 중분류(lclsSystm2)까지만 사용.

STEP 4. endpoint 결정
  - 테마 탐색 → areaBasedList2
  - 특정 장소명 언급 → searchKeyword2

STEP 5. keyword 결정 (searchKeyword2 사용 시에만)
  카테고리 레이블이 아닌 실제 검색어 사용.

──────────────────────────────────────────────────────────────
[출력 형식]
──────────────────────────────────────────────────────────────

다음 JSON 형식으로 출력하세요. 테마가 여러 개면 배열로 반환.

단일 테마:
{
  "themes": [
    {
      "userTheme": "바다",
      "endpoint": "areaBasedList2",
      "params": {
        "lclsSystm1": "NA",
        "lclsSystm2": "NA02"
      },
      "keyword": null,
      "reason": "바다/해변 → 자연경관(하천·해양) NA02"
    }
  ]
}

복합 테마:
{
  "themes": [
    {
      "userTheme": "전통시장",
      "endpoint": "searchKeyword2",
      "params": {
        "lclsSystm1": "SH",
        "lclsSystm2": "SH06"
      },
      "keyword": "전통시장",
      "reason": "시장/전통시장 → 쇼핑>시장 SH06, 명칭 검색으로 분기"
    },
    {
      "userTheme": "맛집",
      "endpoint": "areaBasedList2",
      "params": {
        "lclsSystm1": "FD",
        "lclsSystm2": "FD01"
      },
      "keyword": null,
      "reason": "한식/음식 → 음식>한식 FD01"
    }
  ]
}

매핑 불가 시:
{
  "themes": [
    {
      "userTheme": "드라이브",
      "endpoint": null,
      "params": {},
      "keyword": "드라이브",
      "reason": "RAG에서 명확한 중분류 없음. searchKeyword2에 keyword만 사용 권장"
    }
  ]
}

──────────────────────────────────────────────────────────────
[Few-Shot 예시]
──────────────────────────────────────────────────────────────

--- 예시 1 ---
사용자: "바다 보고 싶어요"

추론:
- 키워드: "바다"
- RAG 매핑: "바다" → NA02 트리거 "바다, 해변, 해수욕장, 섬, 강, 호수..."
- 테마 탐색이므로 areaBasedList2

출력:
{
  "themes": [
    {
      "userTheme": "바다",
      "endpoint": "areaBasedList2",
      "params": { "lclsSystm1": "NA", "lclsSystm2": "NA02" },
      "keyword": null,
      "reason": "바다 → 자연경관(하천·해양) NA02"
    }
  ]
}

--- 예시 2 ---
사용자: "캠핑글램핑 가고 싶어요"

추론:
- 키워드: "캠핑", "글램핑"
- RAG 매핑: "글램핑" → AC05 트리거 포함, 소분류 AC050400 글램핑장
- 소분류가 명확하므로 lclsSystm3 포함

출력:
{
  "themes": [
    {
      "userTheme": "글램핑",
      "endpoint": "areaBasedList2",
      "params": {
        "lclsSystm1": "AC",
        "lclsSystm2": "AC05",
        "lclsSystm3": "AC050400"
      },
      "keyword": null,
      "reason": "글램핑 → 숙박>캠핑 AC05, 글램핑장 소분류 AC050400"
    }
  ]
}

--- 예시 3 ---
사용자: "역사 유적지 탐방하고 사찰도 들르고 싶어요"

추론:
- 키워드: "역사유적지", "사찰"
- 역사유적지 → HS01 (역사유적지)
- 사찰 → HS03 (종교성지) 또는 EX04 (산사체험)
  → 단순 방문이면 HS03, 체험 원하면 EX04. 발화가 방문 탐방이므로 HS03

출력:
{
  "themes": [
    {
      "userTheme": "역사 유적지",
      "endpoint": "areaBasedList2",
      "params": { "lclsSystm1": "HS", "lclsSystm2": "HS01" },
      "keyword": null,
      "reason": "역사유적지 탐방 → 역사관광>역사유적지 HS01"
    },
    {
      "userTheme": "사찰",
      "endpoint": "areaBasedList2",
      "params": { "lclsSystm1": "HS", "lclsSystm2": "HS03" },
      "keyword": null,
      "reason": "사찰 방문 → 역사관광>종교성지 HS03"
    }
  ]
}

--- 예시 4 ---
사용자: "설악산 쪽 래프팅 할 수 있는 곳 알려줘"

추론:
- "래프팅" → LS02 수상레저스포츠, 소분류 LS020800 래프팅
- "설악산" → 특정 지역 이름이지만 지역코드(areaCode)는 별도 처리
- 특정 행위 명칭("래프팅") 검색이므로 searchKeyword2

출력:
{
  "themes": [
    {
      "userTheme": "래프팅",
      "endpoint": "searchKeyword2",
      "params": {
        "lclsSystm1": "LS",
        "lclsSystm2": "LS02",
        "lclsSystm3": "LS020800"
      },
      "keyword": "래프팅",
      "reason": "래프팅 → 레저스포츠>수상레저 LS02, 소분류 LS020800, 명칭 검색"
    }
  ],
  "areaNote": "설악산 = 강원도(areaCode=32) 별도 지역 필터 적용 필요"
}

--- 예시 5 ---
사용자: "온천이랑 한방 체험도 하고 싶어요"

추론:
- "온천" → EX05 웰니스관광, 소분류 EX050100
- "한방체험" → EX05 웰니스관광, 소분류 EX050300
- 같은 중분류(EX05)이므로 하나로 합쳐도 되지만,
  소분류가 다르므로 둘 다 반환 (호출 측에서 선택)

출력:
{
  "themes": [
    {
      "userTheme": "온천",
      "endpoint": "areaBasedList2",
      "params": {
        "lclsSystm1": "EX",
        "lclsSystm2": "EX05",
        "lclsSystm3": "EX050100"
      },
      "keyword": null,
      "reason": "온천 → 체험관광>웰니스관광 EX05, 온천/사우나/스파 EX050100"
    },
    {
      "userTheme": "한방체험",
      "endpoint": "areaBasedList2",
      "params": {
        "lclsSystm1": "EX",
        "lclsSystm2": "EX05",
        "lclsSystm3": "EX050300"
      },
      "keyword": null,
      "reason": "한방체험 → 체험관광>웰니스관광 EX05, 한방체험 EX050300"
    }
  ]
}

──────────────────────────────────────────────────────────────
[모호성 처리 규칙]
──────────────────────────────────────────────────────────────

1. 여러 중분류에 걸치는 키워드
   예: "절" → HS03(종교성지) vs EX04(산사체험)
   → 발화 맥락으로 판단: "구경", "방문" → HS03 / "체험", "템플스테이" → EX04
   → 판단 불가 시 둘 다 반환

2. RAG에 없는 테마
   → lclsSystm 없이 keyword만으로 searchKeyword2 호출 권장
   → reason에 "RAG 매핑 없음" 명시

3. 지역 정보가 포함된 경우
   → lclsSystm 파라미터와 별도로 areaNote에 지역 정보 기록
   → 지역 코드 매핑은 별도 RAG(지역코드 문서) 참조

4. 여행 코스 요청 시
   → lclsSystm1=C01 + 코스 유형(C0112~C0117) 사용
   예: "가족 여행 코스" → C01 > C0112(가족코스) → lclsSystm1=C01, lclsSystm2=C0112
```

---

## 사용 예시 (Python 통합 코드)

```python
import json
import os

SYSTEM_PROMPT = """위의 System Prompt 내용"""

def extract_theme_params(user_message: str, rag_content: str) -> dict:
    """
    사용자 발화 → API 파라미터 추출
    LLM 호출 래퍼. 실제 LLM SDK로 교체 필요.
    """
    prompt = f"""
[RAG 문서]
{rag_content}

[사용자 발화]
{user_message}

위 RAG 문서를 참조해 사용자 발화의 여행 테마를 분석하고,
KorService2 API 호출 파라미터를 JSON으로 추출하세요.
"""
    # LLM 호출 (예: Claude API)
    # response = claude.messages.create(
    #     model="claude-sonnet-4-6",
    #     system=SYSTEM_PROMPT,
    #     messages=[{"role": "user", "content": prompt}]
    # )
    # return json.loads(response.content[0].text)
    pass


def build_api_url(theme_result: dict, area_code: str = None, num_of_rows: int = 10) -> list[str]:
    """추출된 파라미터로 실제 API URL 생성."""
    BASE = "https://apis.data.go.kr/B551011/KorService2"
    SERVICE_KEY = os.environ["DATA_GO_KR_SERVICE_KEY"]  # 공공데이터포털 서비스 키(인코딩된 값)

    urls = []
    for theme in theme_result.get("themes", []):
        endpoint = theme["endpoint"]
        if not endpoint:
            continue

        params = theme["params"].copy()
        params["serviceKey"] = SERVICE_KEY
        params["_type"] = "json"
        params["numOfRows"] = num_of_rows
        params["pageNo"] = 1

        if area_code:
            params["areaCode"] = area_code

        if endpoint == "searchKeyword2" and theme.get("keyword"):
            params["keyword"] = theme["keyword"]

        query = "&".join(f"{k}={v}" for k, v in params.items())
        urls.append(f"{BASE}/{endpoint}?{query}")

    return urls
```

---

---

## Troubleshooting — 설계 과정에서 마주친 문제들

이 프롬프트 설계에 이르기까지 실제로 겪은 오류와 해결 과정을 기록한다.
같은 문제를 반복하지 않도록, 그리고 왜 이 구조가 선택됐는지 근거로 남긴다.

---

### ❶ 열차 역코드 API — 엔드포인트 이름이 틀렸다

**증상**
TAGO 열차 역 목록 수집 시 API가 404 또는 빈 응답을 반환.

**원인**
공식 문서에 기재된 엔드포인트명 `GetSttnAcctoTrainSttnList`는 실제로 존재하지 않는 경로였다.
스펙 문서와 실제 운영 서버 사이에 이름이 달랐던 것.

**해결**
실제 동작하는 엔드포인트는 `GetCtyAcctoTrainSttnList` (도시코드 기반 역 조회).
`cityCode` 파라미터로 도시를 지정하면 해당 도시의 역 목록과 `nodeid`(NAT...)를 반환한다.

```
# 잘못된 호출
GET /TrainInfo/GetSttnAcctoTrainSttnList  → 404

# 올바른 호출
GET /TrainInfo/GetCtyAcctoTrainSttnList?cityCode=11  → 서울 역 목록
```

> **교훈:** TAGO API는 공식 문서와 실제 엔드포인트명이 다를 수 있다.
> 새 엔드포인트 사용 전에 반드시 실 호출 테스트를 먼저 할 것.

---

### ❷ 고속버스 터미널 중복 ID — 단순 중복 제거가 오히려 위험하다

**증상**
같은 도시에 동일한 터미널명으로 여러 `terminalId`가 존재.
예: 서울 → NAEK010, NAEK011, NAEK012 등.
3명 × 3후보 × 다중터미널 = 최대 180번 API 호출 발생.

**처음 접근한 해결책 (기각)**
같은 이름의 터미널 중 가장 낮은 ID만 남기는 중복 제거(Stage 2).
→ **기각 이유:** 서로 다른 ID는 서로 다른 노선을 담당하는 경우가 있다.
  NAEK010이 경부선 노선을 담당하고 NAEK011이 영동선 노선을 담당하는 구조라면,
  NAEK011을 제거하는 순간 해당 노선으로 가는 버스를 영구히 찾지 못하게 된다.

**채택한 해결책 (Stage 1만 적용)**
`terminalId`가 NAEK900 이상인 항목 제거.
900번대는 실제 터미널이 아닌 경유지·수수료 코드 등 시스템 내부용 항목임을 확인.
진짜 터미널 ID인 NAEK001~899 범위만 남기는 것으로 호출 수를 충분히 줄인다.

> **교훈:** 중복처럼 보이는 데이터가 실제로는 의미 있는 구분일 수 있다.
> 도메인 맥락을 이해하기 전에 자동 중복 제거를 적용하면 데이터 손실이 생긴다.

---

### ❸ 키워드 검색 0건 — 가장 핵심적인 설계 오류

이 프로젝트 전체에서 가장 오래 붙잡힌 문제.
원인이 두 겹으로 쌓여 있었다.

#### 1차 원인: 엔드포인트 자체가 잘못됐다

처음에 `KorService1` API를 호출했더니 HTTP 500 반환.
같은 서비스키로 `KorService2`를 호출하니 정상 동작.
두 버전은 엔드포인트 경로가 다르다.

```
# 500 에러
GET /B551011/KorService1/searchKeyword

# 정상 동작
GET /B551011/KorService2/searchKeyword2
```

#### 2차 원인: keyword가 "관광지 이름"을 검색한다

엔드포인트를 고쳐도 `keyword="자연경관(하천‧해양)"` 결과는 여전히 **0건**.

원인은 API 설계에 있었다.
`searchKeyword2`의 `keyword` 파라미터는 **관광지의 등록된 이름(타이틀)** 을 전문 검색(full-text search)한다.
"자연경관(하천‧해양)"은 관광지 이름이 아니라 **분류 체계의 레이블**이므로 검색 대상 자체가 아니다.

```
keyword="자연경관(하천‧해양)"  →  0건  (이런 이름의 관광지가 없음)
keyword="해운대"              →  1건  (관광지명에 "해운대" 포함)
keyword="바다"               →  수십 건  (이름에 "바다" 포함된 곳만)
                                        단, 해운대·경포대는 여기서 누락됨
```

즉 "바다"를 keyword로 검색하면 이름에 "바다"가 들어간 곳만 나오고,
"해운대", "경포대", "죽도해변"처럼 이름에 "바다"가 없는 해수욕장은 전부 누락된다.

**해결: 테마 탐색은 lclsSystm 코드로**

관광지 분류 체계인 `lclsSystm1/2/3`을 사용하면 이름과 무관하게 카테고리 전체를 조회한다.

```
# 잘못된 접근 — 이름 검색
GET /searchKeyword2?keyword=바다  →  일부 누락

# 올바른 접근 — 카테고리 조회
GET /areaBasedList2?lclsSystm1=NA&lclsSystm2=NA02  →  해안/하천 관광지 전체
```

이것이 이 프롬프트가 "테마 발화 → lclsSystm 코드"로 매핑하는 방식을 채택한 이유다.

> **교훈:** API의 keyword 파라미터는 콘텐츠 내용이 아닌 제목을 검색한다.
> 카테고리 기반 탐색과 명칭 기반 검색은 용도와 파라미터가 다르다. 혼용하지 말 것.

---

### ❹ lclsSystm 계층 규칙 — 상위 없이 하위만 보내면 빈 결과

**증상**
`lclsSystm2=NA02`만 단독으로 전달했더니 결과가 0건.

**원인**
KorService2 API는 분류 코드를 계층 순서대로 누적해서 받아야 한다.
중분류만 단독으로는 유효한 쿼리로 처리하지 않는다.

**규칙**
```
lclsSystm2 사용 시  →  lclsSystm1 필수 동반
lclsSystm3 사용 시  →  lclsSystm1 + lclsSystm2 필수 동반
```

```
# 잘못된 호출
?lclsSystm2=NA02                         →  0건

# 올바른 호출
?lclsSystm1=NA&lclsSystm2=NA02           →  정상
?lclsSystm1=NA&lclsSystm2=NA02&lclsSystm3=NA020900  →  해변/해수욕장만
```

> **교훈:** 계층형 파라미터는 상위부터 누적 전달이 원칙.
> 소분류만 알더라도 대분류·중분류를 반드시 함께 전달해야 한다.

---

## 대분류 코드 빠른 참조

| 대분류코드 | 대분류명 | 주요 contenttypeid |
|-----------|--------|------------------|
| AC | 숙박 | 32(숙박), 28(레포츠) |
| EV | 축제/공연/행사 | 15 |
| EX | 체험관광 | 12(관광지) |
| FD | 음식 | 39(음식점) |
| HS | 역사관광 | 12(관광지) |
| LS | 레저스포츠 | 28(레포츠) |
| NA | 자연관광 | 12(관광지) |
| SH | 쇼핑 | 38(쇼핑) |
| VE | 문화관광 | 12, 14, 28, 32 |
| C01 | 추천코스 | 25(여행코스) |
