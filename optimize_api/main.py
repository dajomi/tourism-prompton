import math
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="관광지 동선 최적화 API",
    description="K-Means 지역 클러스터링 + Nearest Neighbor 방문 순서 최적화",
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# 파싱 / 거리
# ─────────────────────────────────────────────

def haversine(x1: float, y1: float, x2: float, y2: float) -> float:
    R = 6371.0
    dlat = math.radians(y2 - y1)
    dlon = math.radians(x2 - x1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(y1)) * math.cos(math.radians(y2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def parse_places(raw: str, field_name: str = "spots") -> list[dict]:
    """
    '이름,경도,위도|이름,경도,위도|...' → [{"name", "x", "y"}, ...]
    spots / hotels 공용으로 사용.
    """
    try:
        result = []
        for part in raw.strip().split("|"):
            tokens = part.strip().split(",")
            if len(tokens) != 3:
                raise ValueError
            result.append({
                "name": tokens[0].strip(),
                "x": float(tokens[1].strip()),
                "y": float(tokens[2].strip()),
            })
        if not result:
            raise ValueError
        return result
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} 형식 오류. 올바른 형식: '이름1,경도1,위도1|이름2,경도2,위도2'",
        )


def get_hotel_for_night(hotels: list[dict], night_index: int) -> dict:
    """
    night_index 번째 밤의 숙소.
    호텔이 일수보다 적으면 마지막 호텔을 반복 사용.
    """
    return hotels[min(night_index, len(hotels) - 1)]


# ─────────────────────────────────────────────
# K-Means 클러스터링
# ─────────────────────────────────────────────

def kmeans_geo(spots: list[dict], k: int, max_iter: int = 200) -> tuple[list[int], list[dict]]:
    """
    지리 좌표 기반 K-Means (최원점 우선 탐색, farthest-first traversal 초기화).
    반환: (레이블 리스트, 중심점 리스트)
    """
    n = len(spots)

    # 초기 중심점: 첫 spot에서 시작해, 기존 중심점들과의 최소 거리가 가장 큰 spot을 차례로 추가
    # (k-means++와 달리 무작위 추출이 없어 같은 입력이면 항상 같은 결과)
    centroids = [{"x": spots[0]["x"], "y": spots[0]["y"]}]
    for _ in range(k - 1):
        farthest = max(
            spots,
            key=lambda s: min(haversine(s["x"], s["y"], c["x"], c["y"]) for c in centroids),
        )
        centroids.append({"x": farthest["x"], "y": farthest["y"]})

    labels = [0] * n
    for _ in range(max_iter):
        new_labels = [
            min(range(k), key=lambda j: haversine(s["x"], s["y"], centroids[j]["x"], centroids[j]["y"]))
            for s in spots
        ]
        if new_labels == labels:
            break
        labels = new_labels
        for j in range(k):
            members = [spots[i] for i in range(n) if labels[i] == j]
            if members:
                centroids[j] = {
                    "x": sum(s["x"] for s in members) / len(members),
                    "y": sum(s["y"] for s in members) / len(members),
                }

    return labels, centroids


def order_clusters(
    centroids: list[dict],
    start_x: Optional[float],
    start_y: Optional[float],
) -> list[int]:
    """클러스터 중심점에 NN을 적용해 방문 날짜 순서 결정."""
    k = len(centroids)
    curr_x = start_x if start_x is not None else centroids[0]["x"]
    curr_y = start_y if start_y is not None else centroids[0]["y"]

    remaining = list(range(k))
    ordered: list[int] = []
    while remaining:
        nearest = min(remaining, key=lambda j: haversine(curr_x, curr_y, centroids[j]["x"], centroids[j]["y"]))
        ordered.append(nearest)
        remaining.remove(nearest)
        curr_x, curr_y = centroids[nearest]["x"], centroids[nearest]["y"]
    return ordered


def rebalance_last_day(
    clusters: dict[int, list[int]],
    cluster_order: list[int],
    all_spots: list[dict],
    max_last: int = 2,
) -> dict[int, list[int]]:
    """
    마지막 날 클러스터가 max_last개 초과이면
    직전 날 클러스터로 초과분(가장 가까운 spot)을 이동.
    """
    if len(cluster_order) < 2:
        return clusters

    last_c = cluster_order[-1]
    prev_c = cluster_order[-2]
    excess = len(clusters[last_c]) - max_last
    if excess <= 0:
        return clusters

    prev_cx = sum(all_spots[i]["x"] for i in clusters[prev_c]) / len(clusters[prev_c])
    prev_cy = sum(all_spots[i]["y"] for i in clusters[prev_c]) / len(clusters[prev_c])

    sorted_last = sorted(
        clusters[last_c],
        key=lambda i: haversine(all_spots[i]["x"], all_spots[i]["y"], prev_cx, prev_cy),
    )
    for idx in sorted_last[:excess]:
        clusters[last_c].remove(idx)
        clusters[prev_c].append(idx)

    return clusters


# ─────────────────────────────────────────────
# Nearest Neighbor (클러스터 내부)
# ─────────────────────────────────────────────

def nn_within_cluster(
    spot_indices: list[int],
    all_spots: list[dict],
    start_x: Optional[float],
    start_y: Optional[float],
) -> tuple[list[int], float]:
    if not spot_indices:
        return [], 0.0

    pool = [(idx, all_spots[idx]) for idx in spot_indices]
    visited = [False] * len(pool)
    order: list[int] = []
    total_dist = 0.0

    curr_x = start_x if start_x is not None else pool[0][1]["x"]
    curr_y = start_y if start_y is not None else pool[0][1]["y"]

    for _ in range(len(pool)):
        nxt = min(
            (i for i in range(len(pool)) if not visited[i]),
            key=lambda i: haversine(curr_x, curr_y, pool[i][1]["x"], pool[i][1]["y"]),
        )
        total_dist += haversine(curr_x, curr_y, pool[nxt][1]["x"], pool[nxt][1]["y"])
        visited[nxt] = True
        order.append(pool[nxt][0])
        curr_x, curr_y = pool[nxt][1]["x"], pool[nxt][1]["y"]

    return order, total_dist


# ─────────────────────────────────────────────
# 응답 헬퍼
# ─────────────────────────────────────────────

def spot_entry(spot: dict, original_idx: int) -> dict:
    return {"original_idx": original_idx, "name": spot["name"], "x": spot["x"], "y": spot["y"]}


def hotel_entry(hotel: dict) -> dict:
    return {"name": hotel["name"], "x": hotel["x"], "y": hotel["y"], "type": "숙소"}


# ─────────────────────────────────────────────
# 엔드포인트
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "4.0.0"}


@app.get("/optimize", summary="단순 순서 최적화 (NN)")
def optimize(
    spots: str = Query(..., description="이름1,경도1,위도1|이름2,경도2,위도2|..."),
    start_x: Optional[float] = Query(None),
    start_y: Optional[float] = Query(None),
):
    spot_list = parse_places(spots, "spots")
    if len(spot_list) < 2:
        raise HTTPException(status_code=400, detail="spots에 최소 2개 이상 필요합니다.")

    order, dist = nn_within_cluster(list(range(len(spot_list))), spot_list, start_x, start_y)
    return {
        "optimized_order": order,
        "optimized_spots": [spot_entry(spot_list[i], i) for i in order],
        "total_distance_km": round(dist, 2),
    }


@app.get("/optimize/days", summary="날짜별 동선 최적화 (K-Means + NN)")
def optimize_days(
    spots: str = Query(
        ...,
        description="관광지 목록. 형식: '이름1,경도1,위도1|이름2,경도2,위도2|...'",
        example="해운대,129.1604,35.1587|광안리,129.1186,35.1531|동백섬,129.2003,35.1531",
    ),
    days: int = Query(..., ge=1, description="여행 일수"),
    hotels: Optional[str] = Query(
        None,
        description=(
            "숙소 목록. spots와 동일한 형식: '이름1,경도1,위도1|이름2,경도2,위도2|...'\n"
            "- 1개: 전 일정 동일 숙소\n"
            "- 여러 개: 순서대로 각 날 밤 숙소 배정 (days-1개 권장)\n"
            "- 생략 가능"
        ),
        example="해운대그랜드호텔,129.1620,35.1600",
    ),
):
    """
    ## 알고리즘
    1. **K-Means** — 관광지를 days개 지역 클러스터로 분류
    2. **클러스터 순서** — 첫 번째 숙소(또는 첫 관광지)에서 가장 가까운 클러스터부터 시작
    3. **마지막 날 조정** — 마지막 날 클러스터 최대 2개 유지
    4. **NN** — 각 날짜 내 방문 순서 최적화
    5. **숙소 처리** — 마지막 날 제외 각 날 마지막에 해당 숙소 추가, 다음 날은 그 숙소에서 출발

    ## 숙소 배정 규칙
    - hotels[0] → day1 밤 / day2 출발
    - hotels[1] → day2 밤 / day3 출발
    - 숙소 수 < days-1 이면 마지막 숙소 반복 사용
    """
    spot_list = parse_places(spots, "spots")
    n = len(spot_list)

    if n < 1:
        raise HTTPException(status_code=400, detail="spots에 최소 1개 이상 필요합니다.")
    if days > n:
        raise HTTPException(status_code=400, detail=f"days({days}) ≤ spots 수({n}) 이어야 합니다.")

    hotel_list = parse_places(hotels, "hotels") if hotels else []
    has_hotels = len(hotel_list) > 0

    # Day 1 출발 기준: 첫 번째 숙소 위치 (없으면 None → NN이 첫 spot 기준으로 처리)
    first_start_x = hotel_list[0]["x"] if has_hotels else None
    first_start_y = hotel_list[0]["y"] if has_hotels else None

    # ── STEP 1: K-Means ──
    labels, centroids = kmeans_geo(spot_list, days)
    clusters: dict[int, list[int]] = {j: [] for j in range(days)}
    for i, label in enumerate(labels):
        clusters[label].append(i)

    # ── STEP 2: 클러스터 방문 순서 ──
    cluster_order = order_clusters(centroids, first_start_x, first_start_y)

    # ── STEP 3: 마지막 날 spot 수 조정 ──
    clusters = rebalance_last_day(clusters, cluster_order, spot_list, max_last=2)

    # ── STEP 4 & 5: 날별 NN + 숙소 ──
    day_groups: dict[str, list] = {}
    spots_per_day: dict[str, int] = {}
    total_dist = 0.0
    curr_x, curr_y = first_start_x, first_start_y

    for day_num, cluster_idx in enumerate(cluster_order, start=1):
        is_last_day = (day_num == days)
        spot_indices = clusters[cluster_idx]

        ordered_indices, day_dist = nn_within_cluster(spot_indices, spot_list, curr_x, curr_y)
        total_dist += day_dist

        day_spots = [spot_entry(spot_list[i], i) for i in ordered_indices]

        if not is_last_day and has_hotels:
            tonight = get_hotel_for_night(hotel_list, day_num - 1)  # night_index = day_num-1
            day_spots.append(hotel_entry(tonight))
            curr_x, curr_y = tonight["x"], tonight["y"]
        elif ordered_indices:
            last = spot_list[ordered_indices[-1]]
            curr_x, curr_y = last["x"], last["y"]

        day_groups[f"day{day_num}"] = day_spots
        spots_per_day[f"day{day_num}"] = len(spot_indices)

    return {
        "days": day_groups,
        "spots_per_day": spots_per_day,
        "total_distance_km": round(total_dist, 2),
    }
