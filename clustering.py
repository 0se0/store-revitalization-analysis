"""
지역별 공실 위험도 K-Means 클러스터링 (변수 6개)
입력: 중대형/소규모/오피스 공실률 + 임대료 (2026 1분기, 17개 시도)
출력: 역산공실탐지기반_클러스터링.html

pandas/sklearn이 여기 numpy 2.x랑 안 맞아서 임포트가 계속 깨짐.
그래서 그냥 csv 표준라이브러리 + numpy만으로 읽기/정규화/K-Means 직접 구현함
"""
import csv
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CVS_DIR = os.path.join(BASE_DIR, "cvs")
HTML_DIR = os.path.join(BASE_DIR, "html")

REGIONS = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
           "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]

# 시도 중심 좌표 (지도 그릴 때 쓸 거)
COORDS = {
    "서울": (37.566, 126.978), "부산": (35.179, 129.075), "대구": (35.871, 128.601),
    "인천": (37.456, 126.705), "광주": (35.160, 126.851), "대전": (36.351, 127.385),
    "울산": (35.538, 129.311), "세종": (36.480, 127.289), "경기": (37.275, 127.009),
    "강원": (37.885, 127.730), "충북": (36.635, 127.491), "충남": (36.658, 126.673),
    "전북": (35.820, 127.108), "전남": (34.816, 126.463), "경북": (36.576, 128.506),
    "경남": (35.238, 128.692), "제주": (33.489, 126.498),
}

FILES = {
    "vac_large":  "임대동향_지역별_공실률_2024년3분기___중대형_상가.csv",
    "vac_small":  "임대동향_지역별_공실률_2024년3분기___소규모_상가.csv",
    "vac_office": "임대동향_지역별_공실률_2024년3분기___오피스.csv",
    "rent_large":  "임대동향_지역별_임대료_2024년3분기___중대형_상가.csv",
    "rent_small":  "임대동향_지역별_임대료_2024년3분기___소규모_상가.csv",
    "rent_office": "임대동향_지역별_임대료_2024년3분기___오피스.csv",
}


def read_latest(filename):
    """CSV에서 시도 단위 행(지역,지역,지역이 모두 같은 행)의 2026년 1분기(마지막 열) 값을 읽는다."""
    path = os.path.join(CVS_DIR, filename)
    with open(path, encoding="cp949") as f:
        rows = list(csv.reader(f))
    out = {}
    for row in rows[3:]:  # 앞 3줄은 헤더(연도/지표명/단위)
        if len(row) < 11:
            continue
        _, a, b, c = row[0], row[1], row[2], row[3]
        if a == b == c and a != "전국":
            out[a] = float(row[10])
    return out


def main():
    values = {k: read_latest(fn) for k, fn in FILES.items()}

    feature_keys = ["vac_large", "vac_small", "vac_office",
                     "rent_large", "rent_small", "rent_office"]
    shop_idx = [0, 1, 3, 4]  # vac_large, vac_small, rent_large, rent_small (세종도 관측치 있음)

    import numpy as np

    # 세종은 오피스 임대동향 조사를 아예 안 해서 오피스 관련 변수 2개가 없음.
    # 값을 임의로 만들어내기는 싫어서, K-means 학습 자체는 오피스 데이터 있는 16개 시도로만 함
    fit_regions = [r for r in REGIONS if r != "세종"]
    X = np.array([[values[k][r] for k in feature_keys] for r in fit_regions])

    # StandardScaler랑 똑같은 방식으로 표준화 (ddof=0, sklearn 기본값이랑 동일하게 맞춤)
    mean = X.mean(axis=0)
    std = X.std(axis=0, ddof=0)
    Xs = (X - mean) / std

    # k-means++ 초기화 + Lloyd's 알고리즘, random_state=42로 재현되게
    rng = np.random.default_rng(42)
    k = 3

    def kmeans_plusplus_init(data, k, rng):
        n = data.shape[0]
        centers = [data[rng.integers(n)]]
        for _ in range(1, k):
            d2 = np.min([((data - c) ** 2).sum(axis=1) for c in centers], axis=0)
            probs = d2 / d2.sum()
            centers.append(data[rng.choice(n, p=probs)])
        return np.array(centers)

    best_inertia, best_labels, best_centers = None, None, None
    for _ in range(20):  # 여러 번 초기화해 최적해 탐색 (sklearn n_init 흉내)
        centers = kmeans_plusplus_init(Xs, k, rng)
        for _ in range(100):
            dists = np.linalg.norm(Xs[:, None, :] - centers[None, :, :], axis=2)
            labels = dists.argmin(axis=1)
            new_centers = np.array([
                Xs[labels == c].mean(axis=0) if (labels == c).any() else centers[c]
                for c in range(k)
            ])
            if np.allclose(new_centers, centers):
                break
            centers = new_centers
        inertia = ((Xs - centers[labels]) ** 2).sum()
        if best_inertia is None or inertia < best_inertia:
            best_inertia, best_labels, best_centers = inertia, labels, centers

    labels = best_labels
    centers = best_centers

    # 세종은 갖고 있는 4개 변수(상가 공실률/임대료)만으로 표준화해서 부분거리로
    # 제일 가까운 중심점 찾음 - 오피스 값 지어내지 않고 그냥 있는 데이터로만 군집 배정
    shop_keys = [feature_keys[i] for i in shop_idx]
    sejong_x = np.array([values[k]["세종"] for k in shop_keys])
    sejong_xs = (sejong_x - mean[shop_idx]) / std[shop_idx]
    sejong_dists = np.linalg.norm(centers[:, shop_idx] - sejong_xs, axis=1)
    sejong_label = int(sejong_dists.argmin())

    all_labels = {r: int(labels[i]) for i, r in enumerate(fit_regions)}
    all_labels["세종"] = sejong_label

    # 클러스터 위험도 순위 매기기: 공실률 평균 높고 임대료 평균 낮을수록 고위험으로 봄
    vac_idx = [0, 1, 2]
    rent_idx = [3, 4, 5]
    risk_score = {}
    for c in range(k):
        idx = np.where(labels == c)[0]
        risk_score[c] = Xs[idx][:, vac_idx].mean() - Xs[idx][:, rent_idx].mean()
    order = sorted(range(k), key=lambda c: -risk_score[c])  # 위험도 높은 순
    cluster_rank = {cluster: rank for rank, cluster in enumerate(order)}

    palette = [
        ("고위험", "#e34948", "#fef2f2"),
        ("중위험", "#f59e0b", "#fefce8"),
        ("저위험", "#2a78d6", "#eff6ff"),
    ]

    data_out = []
    for r in REGIONS:
        rank = cluster_rank[all_labels[r]]
        label, color, bg = palette[rank]
        lat, lng = COORDS[r]
        has_office = r != "세종"
        data_out.append({
            "name": r, "cluster": rank, "label": label, "color": color, "bg": bg,
            "lat": lat, "lng": lng,
            "vac_large": values["vac_large"][r], "vac_small": values["vac_small"][r],
            "vac_office": round(values["vac_office"][r], 1) if has_office else None,
            "rent_large": values["rent_large"][r], "rent_small": values["rent_small"][r],
            "rent_office": round(values["rent_office"][r], 1) if has_office else None,
        })

    counts = {0: 0, 1: 0, 2: 0}
    for d in data_out:
        counts[d["cluster"]] += 1
    print("고위험", counts[0], "중위험", counts[1], "저위험", counts[2])

    write_html(data_out, counts)
    return data_out


def write_html(data_out, counts):
    high = [d["name"] for d in data_out if d["cluster"] == 0]
    mid = [d["name"] for d in data_out if d["cluster"] == 1]
    low = [d["name"] for d in data_out if d["cluster"] == 2]

    html = HTML_TEMPLATE.format(
        data_json=json.dumps(data_out, ensure_ascii=False),
        high_count=counts[0], mid_count=counts[1], low_count=counts[2],
        high_regions="·".join(high), mid_regions="·".join(mid), low_regions="·".join(low),
    )
    out_path = os.path.join(HTML_DIR, "역산공실탐지기반_클러스터링.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"생성 완료: {out_path}")


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>역산공실탐지기반 — 지역별 공실 위험도 클러스터링 분석</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8f8f7; color: #0b0b0b; padding: 2rem; }}
  h1 {{ font-size: 18px; font-weight: 500; margin-bottom: 4px; }}
  .subtitle {{ font-size: 12px; color: #898781; margin-bottom: 1.5rem; }}
  .layout {{ display: grid; grid-template-columns: 1fr 380px; gap: 20px; margin-bottom: 1.5rem; }}
  .map-box {{ background: #fff; border-radius: 12px; border: 0.5px solid rgba(11,11,11,0.1); padding: 1.25rem; position: relative; }}
  .map-title {{ font-size: 13px; font-weight: 500; color: #52514e; margin-bottom: 12px; }}
  #mapArea {{ width: 100%; height: 420px; border-radius: 8px; overflow: hidden; }}
  .map-legend {{ position: absolute; z-index: 1000; bottom: 1.5rem; left: 1.5rem; background: rgba(255,255,255,0.95); border: 1px solid #e8e7e2; border-radius: 8px; padding: 10px 14px; }}
  .legend-title {{ font-size: 11px; font-weight: 600; color: #1a1a18; margin-bottom: 6px; }}
  .legend-row {{ display: flex; align-items: center; gap: 6px; font-size: 11px; color: #52514e; margin-bottom: 3px; }}
  .legend-dot {{ width: 12px; height: 12px; border-radius: 50%; border: 1.5px solid #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }}
  .cards-box {{ display: flex; flex-direction: column; gap: 12px; }}
  .cluster-card {{ background: #fff; border-radius: 10px; border: 0.5px solid rgba(11,11,11,0.1); padding: 1rem; border-left: 4px solid; }}
  .card-top {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
  .card-badge {{ font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; color: #fff; }}
  .card-regions {{ font-size: 12px; color: #52514e; margin-bottom: 10px; line-height: 1.5; }}
  .card-stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
  .stat-box {{ background: #f8f8f7; border-radius: 6px; padding: 6px 8px; }}
  .stat-label {{ font-size: 10px; color: #898781; margin-bottom: 2px; }}
  .stat-val {{ font-size: 14px; font-weight: 600; color: #0b0b0b; }}
  .insight-box {{ background: #fff; border-radius: 12px; border: 0.5px solid rgba(11,11,11,0.1); padding: 1.25rem; }}
  .insight-title {{ font-size: 13px; font-weight: 500; color: #52514e; margin-bottom: 12px; }}
  .insight-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
  .insight-card {{ background: #f8f8f7; border-radius: 8px; padding: 1rem; border-left: 3px solid; }}
  .insight-label {{ font-size: 11px; font-weight: 600; margin-bottom: 6px; }}
  .insight-body {{ font-size: 12px; color: #52514e; line-height: 1.6; }}
  .source {{ font-size: 11px; color: #898781; margin-top: 1.5rem; }}
</style>
</head>
<body>
<h1>역산공실탐지기반 — 지역별 공실 위험도 클러스터링 분석</h1>
<div class="subtitle">K-Means 클러스터링 (k=3, 6개 변수) | 입력 변수: 중대형·소규모·오피스 공실률, 중대형·소규모·오피스 임대료 (2026년 1분기) | 출처: 한국부동산원 상업용부동산 임대동향조사</div>

<div class="layout">
  <div class="map-box">
    <div class="map-title">시도별 공실 위험도 클러스터 분포</div>
    <div id="mapArea"></div>
    <div class="map-legend">
      <div class="legend-title">공실 위험도</div>
      <div class="legend-row"><div class="legend-dot" style="background:#e34948;"></div>고위험 — 공실↑ 임대료↓</div>
      <div class="legend-row"><div class="legend-dot" style="background:#f59e0b;"></div>중위험 — 공실 보통 임대료 중간</div>
      <div class="legend-row"><div class="legend-dot" style="background:#2a78d6;"></div>저위험 — 공실↓ 임대료↑</div>
    </div>
  </div>
  <div class="cards-box" id="cards"></div>
</div>

<div class="insight-box">
  <div class="insight-title">📌 클러스터 분석 인사이트 — 진단모델 활용 전략</div>
  <div class="insight-grid">
    <div class="insight-card" style="border-color:#e34948;">
      <div class="insight-label" style="color:#e34948;">🔴 고위험군 우선 타깃 ({high_count}개 시도)</div>
      <div class="insight-body">{high_regions} 등 상가·오피스 공실률이 함께 높고 임대료는 정체된 지역이다. 방치 공실이 집중되어 매칭 수요가 가장 높으며, 지자체 협력 창업 지원 프로그램과 연계 시 즉각적인 효과가 기대된다.</div>
    </div>
    <div class="insight-card" style="border-color:#f59e0b;">
      <div class="insight-label" style="color:#d97706;">🟡 중위험군 성장 거점 ({mid_count}개 시도)</div>
      <div class="insight-body">{mid_regions} 등 중위험군은 임대료가 어느 정도 형성되어 창업 성공 가능성이 상대적으로 높다. 서비스 확산 거점으로 활용 가능하다.</div>
    </div>
    <div class="insight-card" style="border-color:#2a78d6;">
      <div class="insight-label" style="color:#2a78d6;">🔵 저위험군 전략 ({low_count}개 시도)</div>
      <div class="insight-body">{low_regions}은 공실률이 낮고 임대료가 높아 청년 창업자 진입 장벽이 크다. 이면도로·골목 상권 틈새 공실에 집중하고 팝업·단기 임대 형태의 매칭 모델이 효과적이다.</div>
    </div>
  </div>
</div>

<div class="source">※ 분석 방법: K-Means 클러스터링 (k=3, 6개 변수 표준화, k-means++ 초기화, random_state=42)<br>
 데이터: 한국부동산원 상업용부동산 임대동향조사 (2026년 1분기 실제 공표 수치)<br>
세종은 오피스 임대동향 조사 미실시 지역으로 K-means 학습(16개 시도)에서는 제외했고, 실측된 상가 공실률·임대료 4개 변수만으로 최근접 중심점(부분거리 방식)을 찾아 군집을 배정했다. 
<br>오피스 값은 채우지 않았으며, 클러스터 평균에도 세종의 오피스 수치는 포함하지 않았다.</div>

<script>
const data = {data_json};

const map = L.map('mapArea').setView([36.2, 127.8], 6.7);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 18,
  attribution: '&copy; OpenStreetMap contributors'
}}).addTo(map);

data.forEach(d => {{
  const officeText = d.vac_office == null ? '오피스 데이터 없음' : `오피스공실 ${{d.vac_office}}%`;
  const circle = L.circleMarker([d.lat, d.lng], {{
    radius: 14,
    fillColor: d.color,
    color: '#fff',
    weight: 2,
    fillOpacity: 0.9,
  }}).addTo(map);
  circle.bindTooltip(`<b>${{d.name}}</b> (${{d.label}})<br>상가공실 ${{d.vac_large}}% | ${{officeText}}`);
}});

const cards = document.getElementById('cards');
[{{c:0,label:'고위험',desc:'공실 심각 + 저임대료',color:'#e34948'}},
 {{c:1,label:'중위험',desc:'공실 보통 + 중임대료',color:'#f59e0b'}},
 {{c:2,label:'저위험',desc:'공실 낮음 + 고임대료',color:'#2a78d6'}}].forEach(cl => {{
  const g = data.filter(d => d.cluster === cl.c);
  if (!g.length) return;
  const avg = k => {{
    const vals = g.map(d=>d[k]).filter(v => v != null);
    return vals.length ? (vals.reduce((s,v)=>s+v,0)/vals.length).toFixed(1) : 'N/A';
  }};
  cards.innerHTML += `<div class="cluster-card" style="border-left-color:${{cl.color}};">
    <div class="card-top"><span class="card-badge" style="background:${{cl.color}};">${{cl.label}}군</span><span style="font-size:12px;color:#52514e;">${{cl.desc}}</span></div>
    <div class="card-regions">${{g.map(d=>d.name).join(' · ')}}</div>
    <div class="card-stats">
      <div class="stat-box"><div class="stat-label">중대형상가 공실률</div><div class="stat-val" style="color:${{cl.color}};">${{avg('vac_large')}}%</div></div>
      <div class="stat-box"><div class="stat-label">소규모상가 공실률</div><div class="stat-val" style="color:${{cl.color}};">${{avg('vac_small')}}%</div></div>
      <div class="stat-box"><div class="stat-label">오피스 공실률 (세종 제외)</div><div class="stat-val" style="color:${{cl.color}};">${{avg('vac_office')}}%</div></div>
      <div class="stat-box"><div class="stat-label">중대형상가 임대료</div><div class="stat-val">${{avg('rent_large')}}천원/㎡</div></div>
      <div class="stat-box"><div class="stat-label">소규모상가 임대료</div><div class="stat-val">${{avg('rent_small')}}천원/㎡</div></div>
      <div class="stat-box"><div class="stat-label">오피스 임대료 (세종 제외)</div><div class="stat-val">${{avg('rent_office')}}천원/㎡</div></div>
    </div>
  </div>`;
}});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()