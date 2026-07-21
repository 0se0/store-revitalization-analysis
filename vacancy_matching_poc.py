"""
공실 자동탐지 알고리즘 PoC

아래 building_registry / biz_registry는 진짜 API 응답 아니고 로직 검증하려고
내가 직접 만든 샘플 데이터임. 실서비스 가면 여기에
  - 국토교통부 건축HUB 건축물대장정보 API (전체 상가 호수)
  - 소상공인시장진흥공단 상가정보 API (영업중인 상가)
실제 응답이 들어가고, 아래 매칭 로직은 그대로 재사용하면 됨

핵심 아이디어:
  건축물대장에 있는 (주소,층,호) - 상가정보에 있는 (주소,층,호)
  = 건물엔 있는데 영업중으로 등록 안 된 호수 -> 공실로 추정

이 PoC로 확인하고 싶었던 거:
  1. 주소 표기가 기관마다 다름 (도로명 축약, 층수 표기, 지하/B1 등등)
     -> 정규화 안 하면 매칭이 거의 안 됨을 재현해봄
  2. 정규화 함수 적용하면 정상적으로 매칭되는지 확인
  3. 두 목록 차집합으로 공실 후보 뽑아내는 전체 파이프라인 한번 돌려봄
"""

import re
from dataclasses import dataclass



# 1. 샘플 데이터 (실제 API 응답을 흉내낸 가상 데이터 — 표기 불일치를 의도적으로 포함)

# 건축물대장: "이 건물엔 이런 호수들이 존재한다" (전체 목록, 영업 여부와 무관)
building_registry = [
    {"raw_addr": "서울특별시 종로구 종로3가 15-2번지", "floor": "1층", "unit": "101호"},
    {"raw_addr": "서울특별시 종로구 종로3가 15-2번지", "floor": "1층", "unit": "102호"},
    {"raw_addr": "서울특별시 종로구 종로3가 15-2번지", "floor": "2층", "unit": "201호"},
    {"raw_addr": "서울 중구 을지로 120",                "floor": "지하1층", "unit": "B101호"},
    {"raw_addr": "서울 중구 을지로 120",                "floor": "2층",   "unit": "203호"},
    {"raw_addr": "서울 마포구 어울마당로 65",            "floor": "1층",   "unit": "B동 1호"},
]

# 상가정보: "이 호수엔 지금 영업 중인 사업자가 있다" (영업 중 목록만)
biz_registry = [
    {"raw_addr": "종로구 종로3가 15-2",   "floor": "1F",  "unit": "101",  "biz_name": "종로커피"},
    {"raw_addr": "중구 을지로 120번지",   "floor": "B1",  "unit": "101",  "biz_name": "을지분식"},
    {"raw_addr": "마포구 어울마당로 65",  "floor": "1",   "unit": "B동1호", "biz_name": "홍대꽃집"},
]


# 2. 주소 정규화 — 서로 다른 표기 체계를 하나의 key로 통일

def normalize_addr(raw: str) -> str:
    s = raw
    s = re.sub(r"^서울특별시\s*", "", s)
    s = re.sub(r"^서울\s*", "", s)
    s = re.sub(r"번지$", "", s)   # 말미 "번지"만 제거 (지번 숫자는 그대로 둠)
    s = re.sub(r"\s+", "", s)     # 공백 제거
    s = s.replace("-", "")        # 지번 하이픈 빼기 ("15-2" -> "152", 이렇게 해야 양쪽 표기가 같은 형태로 맞춰짐)
    return s


def normalize_floor(raw: str) -> str:
    s = raw.strip()
    s = s.replace("층", "").replace("F", "").replace("f", "")
    if "지하" in s or s.upper().startswith("B"):
        num = re.sub(r"[^0-9]", "", s) or "1"
        return f"B{num}"
    return re.sub(r"[^0-9]", "", s)


def normalize_unit(raw: str) -> str:
    s = raw.strip()
    s = re.sub(r"\s+", "", s)          # 내부 공백 제거 ("B동 1호" -> "B동1호")
    s = s.replace("호", "")
    s = re.sub(r"^[Bb](?=\d)", "", s)  # 'B101' -> '101' (층에서 이미 지하 처리했으니까 숫자 앞 B는 중복이라 뺌)
    return s.strip()


def make_key(addr: str, floor: str, unit: str) -> str:
    return f"{normalize_addr(addr)}|{normalize_floor(floor)}|{normalize_unit(unit)}"



def detect_vacancies(building_list, biz_list):
    biz_keys = {make_key(b["raw_addr"], b["floor"], b["unit"]) for b in biz_list}

    matched, vacant = [], []
    for unit in building_list:
        key = make_key(unit["raw_addr"], unit["floor"], unit["unit"])
        if key in biz_keys:
            matched.append(unit)
        else:
            vacant.append(unit)
    return matched, vacant, biz_keys


def run_without_normalization():
    """정규화 없이 원문 그대로 비교하면 매칭이 거의 실패함을 보여준다."""
    biz_keys_raw = {f"{b['raw_addr']}|{b['floor']}|{b['unit']}" for b in biz_registry}
    matched = 0
    for unit in building_registry:
        raw_key = f"{unit['raw_addr']}|{unit['floor']}|{unit['unit']}"
        if raw_key in biz_keys_raw:
            matched += 1
    return matched


if __name__ == "__main__":
    print("=" * 60)
    print("[0] 정규화 없이 원문 그대로 매칭 시도")
    print("=" * 60)
    raw_matched = run_without_normalization()
    print(f"전체 {len(building_registry)}개 호수 중 원문 매칭 성공: {raw_matched}개")
    print("→ 기관별 주소·층·호수 표기 방식이 달라 정규화 없이는 매칭이 거의 불가능함을 확인.\n")

    print("=" * 60)
    print("[1] 정규화 적용 후 매칭")
    print("=" * 60)
    matched, vacant, biz_keys = detect_vacancies(building_registry, biz_registry)

    print(f"건축물대장 전체 호수: {len(building_registry)}개")
    print(f"상가정보 영업중 호수: {len(biz_registry)}개")
    print(f"매칭(영업중으로 확인): {len(matched)}개")
    print(f"공실 추정: {len(vacant)}개\n")

    print("--- 영업중으로 매칭된 호수 ---")
    for m in matched:
        print(f"  {m['raw_addr']} {m['floor']} {m['unit']}  (key={make_key(m['raw_addr'], m['floor'], m['unit'])})")

    print("\n--- 공실 추정 호수 ---")
    for v in vacant:
        print(f"  🏠 {v['raw_addr']} {v['floor']} {v['unit']}  (key={make_key(v['raw_addr'], v['floor'], v['unit'])})")