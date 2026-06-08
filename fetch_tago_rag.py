"""
TAGO API 데이터 수집 및 RAG 문서 생성 스크립트
- RAG_04: 열차 도시코드 (GetCtyCodeList)
- RAG_05: 고속버스 터미널 ID (GetExpBusTrminlList)
"""

import urllib.request
import urllib.parse
import json
import os
from datetime import date

# 공공데이터포털 서비스 키(인코딩된 값)를 환경변수로 전달
SERVICE_KEY = os.environ.get("DATA_GO_KR_SERVICE_KEY", "")
if not SERVICE_KEY:
    raise SystemExit("환경변수 DATA_GO_KR_SERVICE_KEY 를 설정하세요.")


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all_pages(base_url: str, num_of_rows: int = 300) -> list:
    """totalCount를 확인하고 전체 페이지를 수집해 item 리스트 반환."""
    items = []
    page = 1
    total = None

    while True:
        url = f"{base_url}&numOfRows={num_of_rows}&pageNo={page}"
        data = fetch_json(url)
        body = data["response"]["body"]

        if total is None:
            total = body["totalCount"]
            print(f"  총 {total}건, {num_of_rows}건씩 수집 중...")

        raw = body["items"]["item"]
        chunk = raw if isinstance(raw, list) else [raw]
        items.extend(chunk)
        print(f"  page {page}: {len(chunk)}건 수집 (누적 {len(items)}건)")

        if len(items) >= total:
            break
        page += 1

    return items


# ─────────────────────────────────────────────────────────────
# RAG 04 : 열차 도시코드
# ─────────────────────────────────────────────────────────────

def fetch_train_city_codes() -> list:
    print("[1/2] 열차 도시코드 조회 (GetCtyCodeList)")
    base = (
        "https://apis.data.go.kr/1613000/TrainInfo/GetCtyCodeList"
        f"?serviceKey={SERVICE_KEY}&_type=json"
    )
    return fetch_all_pages(base, num_of_rows=100)


def write_rag04(items: list, today: str) -> None:
    lines = [
        "TAGO 열차 도시코드 (cityCode 기반 도시 검색용)",
        "출처: 국토교통부 TAGO 열차정보 API - GetCtyCodeList",
        "URL: https://apis.data.go.kr/1613000/TrainInfo/GetCtyCodeList",
        "한국관광공사 모여행 프로젝트 RAG 문서",
        f"수집일: {today} | 총 {len(items)}개 도시/광역시·도",
        "",
        "─" * 60,
        "[도시명] = [도시코드(cityCode)]",
        "─" * 60,
    ]

    for item in items:
        lines.append(f"{item['cityname']:<12} = {item['citycode']}")

    lines += [
        "",
        "─" * 60,
        "API 파라미터 안내",
        "─" * 60,
        "- 이 코드는 GetCtyCodeList API에서 반환하는 열차 도시 분류 코드입니다.",
        "- 열차 출발/도착 역 검색 시 도시 필터링에 사용합니다.",
        "- 실제 역 코드(depPlaceId / arrPlaceId)는 GetSttnAcctoTrainSttnList API로",
        "  cityCode를 넘겨 역 목록을 조회한 뒤 각 역의 stationCode를 사용합니다.",
        "",
        "─" * 60,
        "사용 예시 (도시 코드로 역 목록 조회 흐름)",
        "─" * 60,
        "1단계: 도시코드 확인",
        "  서울 = 11, 대전 = 25, 부산 = 21",
        "",
        "2단계: 역 목록 조회 (GetSttnAcctoTrainSttnList)",
        "  cityCode=11 → 서울역, 용산역, 청량리역 등 역 코드 획득",
        "",
        "3단계: 열차 시간표 조회 (GetSttnAcctoTrainInfo2)",
        "  depPlaceId=[출발역코드], arrPlaceId=[도착역코드], depPlandTime=[날짜]",
    ]

    path = "RAG_04_TAGO_열차_도시코드.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  → 저장: {path}")


# ─────────────────────────────────────────────────────────────
# RAG 05 : 고속버스 터미널 ID
# ─────────────────────────────────────────────────────────────

def fetch_bus_terminals() -> list:
    print("[2/2] 고속버스 터미널 목록 조회 (GetExpBusTrminlList)")
    base = (
        "http://apis.data.go.kr/1613000/ExpBusInfo/GetExpBusTrminlList"
        f"?serviceKey={SERVICE_KEY}&_type=json"
    )
    return fetch_all_pages(base, num_of_rows=300)


# 터미널 ID 앞 두 자리(숫자 부분)로 지역 분류
REGION_MAP = [
    (range(10,  100), "서울·수도권"),
    (range(200, 280), "강원권"),
    (range(300, 500), "충청권"),
    (range(500, 660), "전라권"),
    (range(700, 760), "경남권"),
    (range(800, 900), "경북·대구권"),
    (range(900, 1000), "기타·수수료·경유"),
]

def region_label(terminal_id: str) -> str:
    try:
        num = int(terminal_id.replace("NAEK", ""))
        for r, label in REGION_MAP:
            if num in r:
                return label
    except ValueError:
        pass
    return "기타"


def write_rag05(items: list, today: str) -> None:
    # 지역별로 그룹핑
    groups: dict[str, list] = {label: [] for _, label in REGION_MAP}
    for item in items:
        label = region_label(item["terminalId"])
        if label not in groups:
            groups[label] = []
        groups[label].append(item)

    lines = [
        "TAGO 고속버스 터미널 ID (depTerminalId / arrTerminalId)",
        "출처: 국토교통부 TAGO 고속버스정보 API - GetExpBusTrminlList",
        "URL: http://apis.data.go.kr/1613000/ExpBusInfo/GetExpBusTrminlList",
        "한국관광공사 모여행 프로젝트 RAG 문서",
        f"수집일: {today} | 총 {len(items)}개 터미널",
        "",
        "─" * 60,
        "[터미널명] = [터미널ID]",
        "─" * 60,
    ]

    for _, label in REGION_MAP:
        group = groups.get(label, [])
        if not group:
            continue
        lines.append(f"\n## {label}")
        for item in group:
            lines.append(f"{item['terminalNm']:<20} = {item['terminalId']}")

    lines += [
        "",
        "─" * 60,
        "주요 거점 터미널 빠른 참조",
        "─" * 60,
        "서울경부    = NAEK010  |  동서울     = NAEK030  |  서울남부   = NAEK050",
        "센트럴시티  = NAEK020  |  상봉       = NAEK040",
        "대전복합    = NAEK300  |  유성복합   = NAEK360",
        "광주유스퀘어= NAEK500  |  여수       = NAEK510  |  순천       = NAEK515",
        "전주        = NAEK600  |  군산       = NAEK610  |  익산       = NAEK615",
        "부산        = NAEK700  |  부산사상   = NAEK703",
        "울산        = NAEK715  |  창원       = NAEK710  |  진주       = NAEK720",
        "동대구      = NAEK800  |  서대구     = NAEK805  |  포항       = NAEK830",
        "강릉        = NAEK200  |  원주       = NAEK240  |  속초       = NAEK230",
        "",
        "─" * 60,
        "사용 예시",
        "─" * 60,
        "서울 출발 → 대전 도착: depTerminalId=NAEK010, arrTerminalId=NAEK300",
        "서울 출발 → 부산 도착: depTerminalId=NAEK010, arrTerminalId=NAEK700",
        "동서울 출발 → 강릉 도착: depTerminalId=NAEK030, arrTerminalId=NAEK200",
        "센트럴시티 출발 → 광주 도착: depTerminalId=NAEK020, arrTerminalId=NAEK500",
    ]

    path = "RAG_05_TAGO_고속버스_터미널ID.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  → 저장: {path}")


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

def main() -> None:
    today = date.today().isoformat()

    train_items = fetch_train_city_codes()
    write_rag04(train_items, today)

    bus_items = fetch_bus_terminals()
    write_rag05(bus_items, today)

    print("\n완료: RAG_04, RAG_05 파일이 생성되었습니다.")


if __name__ == "__main__":
    main()
