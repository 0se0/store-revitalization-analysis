"""
노후상가/전통시장 위치(위도경도) 대충 매핑해둔 것
정확한 지번 주소는 아니고 그 상권 있는 동/구 중심좌표로 근사한 거임
(일단 프로토타입이라 이렇게 해둠, 나중에 실서비스 가면 상가정보 API의
실제 lon/lat 필드 그대로 쓰면 됨)
"""

MARKET_COORDS = {
    '세운상가가동': (37.5701, 126.9917),
    '낙원시장(낙원지하시장(대일상가))': (37.5730, 126.9870),
    '동대문상가A동': (37.5701, 126.9986),
    '동대문상가B동': (37.5701, 126.9986),
    '동대문상가C동': (37.5701, 126.9986),
    '동대문상가D동': (37.5701, 126.9986),
    '남대문시장(자유상가)': (37.5592, 126.9784),
    '용산전자상가(용산역)': (37.5296, 126.9648),
    '평화시장(남평화시장, 제일평화시장, 신평화패션타운)': (37.5705, 126.9995),
    '청계천공구상가': (37.5701, 126.9950),
    '테크노상가(엘리시움)': (37.5290, 126.9660),
    '방산종합시장(방산시장)': (37.5695, 126.9975),
    '광장시장(광장전통시장)': (37.5701, 127.0010),
    '경동시장': (37.5825, 127.0388),
    '청량리종합시장': (37.5803, 127.0466),
    '청량리전통시장': (37.5807, 127.0455),
    '황학동벼룩시장': (37.5720, 127.0160),
    '신림중앙시장(조원동 펭귄시장)': (37.4845, 126.9296),
    '영등포전통시장': (37.5163, 126.9068),
    '영등포유통상가': (37.5170, 126.9060),
    '영등포시장기계공구상가': (37.5158, 126.9075),
    '동묘시장(동묘벼룩시장)': (37.5730, 127.0165),
    '중부시장(신중부시장)': (37.5651, 126.9945),
    '통인시장': (37.5807, 126.9700),
    '자양골목전통시장(자양골목시장)': (37.5350, 127.0790),
    '길음시장': (37.6068, 127.0254),
    '정릉시장': (37.6094, 127.0080),
    '수유전통시장(수유시장, 수유골목시장)': (37.6376, 127.0257),
    '창동신창시장': (37.6534, 127.0473),
    '쌍문시장(쌍문역골목시장)': (37.6486, 127.0347),
    '신설종합시장': (37.5758, 127.0224),
    '상계중앙시장': (37.6600, 127.0730),
    '화곡중앙시장': (37.5417, 126.8402),
    '봉천중앙시장': (37.4823, 126.9522),
    '신림종합시장': (37.4845, 126.9296),
    '사당시장': (37.4766, 126.9816),
    '노량진중앙시장': (37.5135, 126.9427),
    '가락시장': (37.4924, 127.1185),
    '답십리 건축자재시장': (37.5713, 127.0450),
    '남성사계시장(남성시장)': (37.4870, 126.9750),
    '중랑동부시장(중랑교종합상가)': (37.6063, 127.0925),
    '성동용답상가시장': (37.5637, 127.0475),
    '삼익패션타운(남대문시장)': (37.5592, 126.9784),
    '숭례문수입상가(남대문시장)': (37.5592, 126.9784),
    '동대문종합시장(동대문종합시장 신관, 동대문종합시장D동상가)': (37.5701, 126.9986),
    '동대문패션타운 관광특구': (37.5701, 126.9986),
    '청평화시장': (37.5705, 126.9995),
    '동평화시장': (37.5705, 126.9995),
}


# 안전등급 지도(risk_grade_model + alt_vacancy_indicator 결과 + 위 좌표 합쳐서)
"""
안전등급 지도 - 1단계 메인화면으로 쓸 프로토타입
risk_grade_model.py에서 나온 A~D 등급 + 위 MARKET_COORDS 위치 데이터 합쳐서
서울 지도 위에 노후상가들 안전관리 우선순위 등급 표시함
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
    for r in rows:
        coord = MARKET_COORDS.get(r["name"])
        if not coord:
            continue
        lat, lng = coord
        markers.append({
            "name": r["name"], "grade": r["grade"], "score": r["risk_score"],
            "net_change": r["net_change_pct"], "close_rate": r["recent_close_rate_avg"],
            "lat": lat, "lng": lng, "color": GRADE_COLOR[r["grade"]],
        })

    markers_json = json.dumps(markers, ensure_ascii=False)
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
  .legend-row {{ display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }}
  .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
  .side-panel {{ display: flex; flex-direction: column; gap: 10px; }}
  .kpi-card {{ background: #f1f0eb; border-radius: 8px; padding: 0.875rem; text-align: center; }}
  .kpi-label {{ font-size: 11px; color: #898781; margin-bottom: 4px; }}
  .kpi-value {{ font-size: 22px; font-weight: 600; }}
  .top-list {{ background: #fff; border-radius: 10px; border: 0.5px solid rgba(11,11,11,0.1); padding: 1rem; }}
  .top-list-title {{ font-size: 12px; font-weight: 600; color: #52514e; margin-bottom: 8px; }}
  .top-item {{ display: flex; justify-content: space-between; font-size: 11px; padding: 4px 0; border-bottom: 1px solid #f1f0eb; }}
  .note {{ font-size: 11px; color: #898781; margin-top: 1.5rem; line-height: 1.6; }}
  .leaflet-popup-content {{ font-size: 12px; line-height: 1.5; }}
</style>
</head>
<body>
<h1>역산공실탐지기반 — 안전등급 지도 (1단계 메인화면 프로토타입)</h1>
<div class="subtitle">서울시 노후 대형상가·전통시장 {len(rows)}곳 | 공실 순증감률 + 폐업률 결합 안전관리 우선순위 등급</div>

<div class="caveat">
⚠️ <b>프로토타입 목업 고지:</b> 마커 위치는 각 상권이 위치한 동/구 중심 좌표 기준 근사치이며,
실제 서비스에서는 상가정보 API의 정확한 위경도(lon/lat) 필드를 사용한다. 지도는 실제 OpenStreetMap
타일을 사용한다(Leaflet.js). 등급 산출 로직과 수치는 `risk_grade_model.py`의 실제 계산 결과를 그대로 사용했다.
</div>

<div class="layout">
  <div class="map-box">
    <div class="map-title">서울시 안전관리 우선순위 등급 분포 (실제 지도)</div>
    <div id="mapArea"></div>
    <div class="legend">
      <div style="font-weight:600;margin-bottom:6px;">안전등급</div>
      <div class="legend-row"><div class="legend-dot" style="background:#e34948;"></div>D — 최우선 점검</div>
      <div class="legend-row"><div class="legend-dot" style="background:#f59e0b;"></div>C — 우선 점검 권고</div>
      <div class="legend-row"><div class="legend-dot" style="background:#2a78d6;"></div>B — 정기 모니터링</div>
      <div class="legend-row"><div class="legend-dot" style="background:#3b6d11;"></div>A — 양호</div>
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
산출, 절대기준 고정 임계값(60점 이상 D, 40~60 C, 20~40 B, 20미만 A)으로 {len(rows)}곳을 등급 분류
(D {grade_counts['D']}곳·C {grade_counts['C']}곳·B {grade_counts['B']}곳·A {grade_counts['A']}곳). 상세 산출 근거는 `역산공실탐지기반_안전등급모델.html` 참고.
지도 타일: © OpenStreetMap contributors.
</div>

<script>
const markers = {markers_json};

const map = L.map('mapArea').setView([37.5665, 126.9780], 11);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 18,
  attribution: '&copy; OpenStreetMap contributors'
}}).addTo(map);

markers.forEach(m => {{
  const circle = L.circleMarker([m.lat, m.lng], {{
    radius: 8,
    fillColor: m.color,
    color: '#fff',
    weight: 1.5,
    fillOpacity: 0.9,
  }}).addTo(map);
  circle.bindPopup(`<b>[${{m.grade}}] ${{m.name}}</b><br>위험점수 ${{m.score}} · 순증감 ${{m.net_change}}%`);
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
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"생성 완료: {output_path}")
    print(f"마커 매칭: {sum(1 for r in rows if r['name'] in MARKET_COORDS)}/{len(rows)}")