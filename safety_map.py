"""
노후상가/전통시장 위치(위도경도) + 소속 자치구
정확한 지번 주소는 아니고 그 상권 있는 동/구 중심좌표로 근사한 거임
(일단 프로토타입이라 이렇게 해둠, 나중에 실서비스 가면 상가정보 API의
실제 lon/lat 필드 그대로 쓰면 됨)
자치구는 상권명이 위치한 일반적으로 알려진 행정구역 기준 (정밀 지번 대조는 아님)
"""

MARKET_COORDS = {
    '세운상가가동': (37.5701, 126.9917, '종로구'),
    '낙원시장(낙원지하시장(대일상가))': (37.5730, 126.9870, '종로구'),
    '동대문상가A동': (37.5701, 126.9986, '종로구'),
    '동대문상가B동': (37.5701, 126.9986, '종로구'),
    '동대문상가C동': (37.5701, 126.9986, '종로구'),
    '동대문상가D동': (37.5701, 126.9986, '종로구'),
    '남대문시장(자유상가)': (37.5592, 126.9784, '중구'),
    '용산전자상가(용산역)': (37.5296, 126.9648, '용산구'),
    '평화시장(남평화시장, 제일평화시장, 신평화패션타운)': (37.5705, 126.9995, '중구'),
    '청계천공구상가': (37.5701, 126.9950, '중구'),
    '테크노상가(엘리시움)': (37.5290, 126.9660, '용산구'),
    '방산종합시장(방산시장)': (37.5695, 126.9975, '중구'),
    '광장시장(광장전통시장)': (37.5701, 127.0010, '종로구'),
    '경동시장': (37.5825, 127.0388, '동대문구'),
    '청량리종합시장': (37.5803, 127.0466, '동대문구'),
    '청량리전통시장': (37.5807, 127.0455, '동대문구'),
    '황학동벼룩시장': (37.5720, 127.0160, '중구'),
    '신림중앙시장(조원동 펭귄시장)': (37.4845, 126.9296, '관악구'),
    '영등포전통시장': (37.5163, 126.9068, '영등포구'),
    '영등포유통상가': (37.5170, 126.9060, '영등포구'),
    '영등포시장기계공구상가': (37.5158, 126.9075, '영등포구'),
    '동묘시장(동묘벼룩시장)': (37.5730, 127.0165, '종로구'),
    '중부시장(신중부시장)': (37.5651, 126.9945, '중구'),
    '통인시장': (37.5807, 126.9700, '종로구'),
    '자양골목전통시장(자양골목시장)': (37.5350, 127.0790, '광진구'),
    '길음시장': (37.6068, 127.0254, '성북구'),
    '정릉시장': (37.6094, 127.0080, '성북구'),
    '수유전통시장(수유시장, 수유골목시장)': (37.6376, 127.0257, '강북구'),
    '창동신창시장': (37.6534, 127.0473, '도봉구'),
    '쌍문시장(쌍문역골목시장)': (37.6486, 127.0347, '도봉구'),
    '신설종합시장': (37.5758, 127.0224, '동대문구'),
    '상계중앙시장': (37.6600, 127.0730, '노원구'),
    '화곡중앙시장': (37.5417, 126.8402, '강서구'),
    '봉천중앙시장': (37.4823, 126.9522, '관악구'),
    '신림종합시장': (37.4845, 126.9296, '관악구'),
    '사당시장': (37.4766, 126.9816, '동작구'),
    '노량진중앙시장': (37.5135, 126.9427, '동작구'),
    '가락시장': (37.4924, 127.1185, '송파구'),
    '답십리 건축자재시장': (37.5713, 127.0450, '동대문구'),
    '남성사계시장(남성시장)': (37.4870, 126.9750, '동작구'),
    '중랑동부시장(중랑교종합상가)': (37.6063, 127.0925, '중랑구'),
    '성동용답상가시장': (37.5637, 127.0475, '성동구'),
    '삼익패션타운(남대문시장)': (37.5592, 126.9784, '중구'),
    '숭례문수입상가(남대문시장)': (37.5592, 126.9784, '중구'),
    '동대문종합시장(동대문종합시장 신관, 동대문종합시장D동상가)': (37.5701, 126.9986, '종로구'),
    '동대문패션타운 관광특구': (37.5701, 126.9986, '종로구'),
    '청평화시장': (37.5705, 126.9995, '중구'),
    '동평화시장': (37.5705, 126.9995, '중구'),
}


# 안전등급 지도(risk_grade_model + alt_vacancy_indicator 결과 + 위 좌표 합쳐서)
"""
안전등급 지도 - 1단계 메인화면으로 쓸 프로토타입
risk_grade_model.py에서 나온 A~D 등급 + 위 MARKET_COORDS 위치 데이터 합쳐서
서울 지도 위에 노후상가들 안전관리 우선순위 등급 표시함

[수정] 폐업률을 팝업에 표시 + 등급 필터 버튼 추가
(이미 markers 데이터에 close_rate 값이 있었는데 팝업에서 안 보여주고 있던 걸 반영)
"""
import json
import os
from alt_vacancy_indicator import analyze
from risk_grade_model import compute_risk_grades

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

GRADE_COLOR = {"D": "#e34948", "C": "#f59e0b", "B": "#2a78d6", "A": "#3b6d11"}
GRADE_LABEL = {"D": "최우선 점검", "C": "우선 점검 권고", "B": "정기 모니터링", "A": "양호"}


def generate(rows: list) -> str:
    markers = []
    districts_used = set()
    for r in rows:
        coord = MARKET_COORDS.get(r["name"])
        if not coord:
            continue
        lat, lng, district = coord
        districts_used.add(district)
        markers.append({
            "name": r["name"], "grade": r["grade"], "score": r["risk_score"],
            "net_change": r["net_change_pct"], "close_rate": r["recent_close_rate_avg"],
            "lat": lat, "lng": lng, "district": district, "color": GRADE_COLOR[r["grade"]],
        })

    markers_json = json.dumps(markers, ensure_ascii=False)
    districts_sorted = sorted(districts_used)
    districts_json = json.dumps(districts_sorted, ensure_ascii=False)
    grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in rows:
        grade_counts[r["grade"]] += 1

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>역산공실탐지기반 — 안전등급 지도 (1단계 메인화면)</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8f8f7; color: #0b0b0b; padding: 2rem; }}
  h1 {{ font-size: 18px; font-weight: 500; margin-bottom: 4px; }}
  .subtitle {{ font-size: 12px; color: #898781; margin-bottom: 1.5rem; }}
  .caveat {{ background: #fff7ed; border-left: 3px solid #f59e0b; padding: 0.75rem 1rem; font-size: 12px; color: #52514e; margin-bottom: 1.5rem; line-height: 1.6; }}
  .layout {{ display: grid; grid-template-columns: 1fr 320px; gap: 20px; }}
  .map-box {{ background: #fff; border-radius: 12px; border: 0.5px solid rgba(11,11,11,0.1); padding: 1.25rem; position: relative; }}
  .map-title {{ font-size: 13px; font-weight: 500; color: #52514e; margin-bottom: 12px; }}
  #mapArea {{ width: 100%; height: 620px; border-radius: 8px; overflow: hidden; }}
  .legend {{ position: absolute; z-index: 1000; top: 4.2rem; right: 2.2rem; background: rgba(255,255,255,0.95); border: 1px solid #e8e7e2;
    border-radius: 8px; padding: 10px 14px; font-size: 11px; }}
  .legend-row {{ display: flex; align-items: center; gap: 6px; margin-bottom: 4px; cursor: pointer; user-select: none; }}
  .legend-row.off {{ opacity: 0.35; }}
  .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
  .filter-hint {{ font-size: 9px; color: #898781; margin-top: 6px; border-top: 1px solid #e8e7e2; padding-top: 6px; }}
  .side-panel {{ display: flex; flex-direction: column; gap: 10px; }}
  .kpi-card {{ background: #f1f0eb; border-radius: 8px; padding: 0.875rem; text-align: center; }}
  .kpi-label {{ font-size: 11px; color: #898781; margin-bottom: 4px; }}
  .kpi-value {{ font-size: 22px; font-weight: 600; }}
  .top-list {{ background: #fff; border-radius: 10px; border: 0.5px solid rgba(11,11,11,0.1); padding: 1rem; }}
  .top-list-title {{ font-size: 12px; font-weight: 600; color: #52514e; margin-bottom: 8px; }}
  .top-item {{ display: flex; justify-content: space-between; font-size: 11px; padding: 4px 0; border-bottom: 1px solid #f1f0eb; }}
  .note {{ font-size: 11px; color: #898781; margin-top: 1.5rem; line-height: 1.6; }}
  .leaflet-popup-content {{ font-size: 12px; line-height: 1.6; }}
</style>
</head>
<body>
<h1>역산공실탐지기반 — 안전등급 지도 (1단계 메인화면 프로토타입)</h1>
<div class="subtitle">서울시 노후 대형상가·전통시장 {len(rows)}곳 | 공실 순증감률 + 폐업률 결합 안전관리 우선순위 등급</div>

<div class="caveat">
📍 <b>위치 정확도 안내:</b> 지도에 표시된 안전등급(D~A)과 위험점수는 `risk_grade_model.py`가 48개 상권의 실측 데이터로 계산한 결과 그대로다.<br>
다만 마커의 정확한 좌표(위경도)는 각 상권이 위치한 동/구의 중심점으로 표시한 근사치이며, 실제 건물의 정밀 주소 좌표는 아니다. 자치구 표기도 상권명 기준으로 통상 알려진 행정구역이며, 정밀 지번 대조 결과는 아니다.<br>
(예: 동대문상가 A~D동은 실제로 같은 복합건물 내 동(wing) 구분이라 근사치로도 위치가 크게 다르지 않지만, 일부 인접 건물은 정밀도가 떨어질 수 있다.)<br>
지도 자체는 실제 OpenStreetMap 타일을 사용한다.(Leaflet.js) 실 서비스 단계에서는 상가정보 API의 정확한 위경도(lon/lat) 필드로 교체할 예정이다.<br>
건물 준공연도·공실 추정 현황은 상권 단위 데이터로는 산출이 어려워 이번 프로토타입에는 포함하지 않았다(향후 건물 단위 실측 데이터 확보 시 반영 예정).
</div>

<div class="layout">
  <div class="map-box">
    <div class="map-title">서울시 안전관리 우선순위 등급 분포 (실제 지도)</div>
    <div id="mapArea"></div>
    <div class="legend" id="legendBox">
      <div style="font-weight:600;margin-bottom:6px;">안전등급 (클릭해서 필터)</div>
      <div class="legend-row" data-grade="D"><div class="legend-dot" style="background:#e34948;"></div>D — 최우선 점검</div>
      <div class="legend-row" data-grade="C"><div class="legend-dot" style="background:#f59e0b;"></div>C — 우선 점검 권고</div>
      <div class="legend-row" data-grade="B"><div class="legend-dot" style="background:#2a78d6;"></div>B — 정기 모니터링</div>
      <div class="legend-row" data-grade="A"><div class="legend-dot" style="background:#3b6d11;"></div>A — 양호</div>
      <div class="filter-hint" style="border-top:none; border-bottom:1px solid #e8e7e2; padding-top:4px; padding-bottom:8px; margin-top:4px; margin-bottom:10px;">
        등급을 클릭하면 지도에서 켜고 끌 수 있습니다.
      </div>

        <div>
        <div style="font-weight:600; margin-bottom:6px;">지역(자치구)</div>
        <div class="filter-hint" style="border-top:none; margin-top:0; padding-top:0;">
          지역 필터는 종로구(11곳)·중구(10곳)가 가장 많습니다.<br> 
          일부 자치구는 상권이 1~3곳뿐이라, 등급 필터와 겹치면 마커가 안 보일 수 있습니다.
        </div><br> 
        <select id="districtFilter" style="width:100%; font-size:11px; padding:4px; border-radius:4px; border:1px solid #d3d1c7;">
          <option value="ALL">전체 보기</option>
        </select>
      </div>
    </div>
  </div>
  <div class="side-panel">
    <div class="kpi-card">
      <div class="kpi-label">분석 대상 상권</div>
      <div class="kpi-value" style="color:#52514e;">{len(rows)}곳</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">D등급 (최우선 점검)</div>
      <div class="kpi-value" style="color:#e34948;">{grade_counts['D']}곳</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">C등급 (우선 점검 권고)</div>
      <div class="kpi-value" style="color:#d97706;">{grade_counts['C']}곳</div>
    </div>
    <div class="top-list">
      <div class="top-list-title">🔴 D등급 상권 (위험점수 순)</div>
      <div id="dList"></div>
    </div>
  </div>
</div>

<div class="note">
※ 방법론: 점포수 순증감률(2021~2025, 서울시 상권분석서비스)과 최근4분기 평균폐업률을 결합해 위험점수(0~100)
산출,<br< 절대기준 고정 임계값(60점 이상 D, 40~60 C, 20~40 B, 20미만 A)으로 {len(rows)}곳을 등급 분류
(D {grade_counts['D']}곳·C {grade_counts['C']}곳·B {grade_counts['B']}곳·A {grade_counts['A']}곳).<br> 상세 산출 근거는 `역산공실탐지기반_안전등급모델.html` 참고.
지도 타일: © OpenStreetMap contributors.
</div>

<script>
const markers = {markers_json};
const districts = {districts_json};
const gradeColors = {{ D: '#e34948', C: '#f59e0b', B: '#2a78d6', A: '#3b6d11' }};
const activeGrades = new Set(['D','C','B','A']);
let activeDistrict = 'ALL';
const circleByMarker = [];

const map = L.map('mapArea').setView([37.5665, 126.9780], 11);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 18,
  attribution: '&copy; OpenStreetMap contributors'
}}).addTo(map);

const districtSelect = document.getElementById('districtFilter');
districts.forEach(d => {{
  const opt = document.createElement('option');
  opt.value = d; opt.textContent = d;
  districtSelect.appendChild(opt);
}});

function applyFilters() {{
  circleByMarker.forEach(({{ marker, circle }}) => {{
    const gradeOk = activeGrades.has(marker.grade);
    const districtOk = (activeDistrict === 'ALL') || (marker.district === activeDistrict);
    if (gradeOk && districtOk) {{
      if (!map.hasLayer(circle)) circle.addTo(map);
    }} else {{
      if (map.hasLayer(circle)) map.removeLayer(circle);
    }}
  }});
}}

markers.forEach(m => {{
  const circle = L.circleMarker([m.lat, m.lng], {{
    radius: 8,
    fillColor: m.color,
    color: '#fff',
    weight: 1.5,
    fillOpacity: 0.9,
  }}).addTo(map);
  // 폐업률(close_rate)·자치구(district)를 팝업에 추가 표시
  circle.bindPopup(`<b>[${{m.grade}}] ${{m.name}}</b><br>${{m.district}} · 위험점수 ${{m.score}} · 순증감 ${{m.net_change}}%<br>최근4분기 평균폐업률 ${{m.close_rate}}%`);
  circleByMarker.push({{ marker: m, circle }});
}});

// 범례 클릭 시 해당 등급 마커 켜고 끄기
document.querySelectorAll('.legend-row').forEach(row => {{
  row.addEventListener('click', () => {{
    const grade = row.dataset.grade;
    if (activeGrades.has(grade)) {{
      activeGrades.delete(grade);
      row.classList.add('off');
    }} else {{
      activeGrades.add(grade);
      row.classList.remove('off');
    }}
    applyFilters();
  }});
}});

// 자치구 드롭다운 필터
districtSelect.addEventListener('change', () => {{
  activeDistrict = districtSelect.value;
  applyFilters();
}});

const dList = document.getElementById('dList');
markers.filter(m => m.grade === 'D').sort((a,b) => b.score - a.score).forEach(m => {{
  dList.innerHTML += `<div class="top-item"><span>${{m.name}}</span><span style="color:#e34948;font-weight:600;">${{m.score}}</span></div>`;
}});
</script>
</body>
</html>"""


if __name__ == "__main__":
    result = analyze()
    rows = compute_risk_grades(result)
    html = generate(rows)
    output_path = os.path.join(BASE_DIR, "html", "역산공실탐지기반_안전등급지도.html")
    os.makedirs(os.path.join(BASE_DIR, "html"), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"생성 완료: {output_path}")
    print(f"마커 매칭: {sum(1 for r in rows if r['name'] in MARKET_COORDS)}/{len(rows)}")