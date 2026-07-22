"""
의심건물 스크리닝 리포트 (2단계) - 불법 증축·무단 용도변경 의심 건물 우선순위화

verification_scan.py -> verification_log.csv(303개 건물 실측 원본 로그)를
다시 읽어서, "등록전유부수 대비 실제영업중수 격차가 큰 건물"부터 순위를 매김.
1단계(안전등급 진단)에서 이미 확보된 데이터를 그대로 재활용,
새로운 데이터 수집 없이 2단계 스크리닝 리포트를 만들 수 있음.

의심도 판단 기준을 두 가지:
  - 격차(gap) = 실제영업중수 - 등록전유부수 → 절대적 규모(관리 사각지대 크기)
  - 배율(ratio) = 실제영업중수 / 등록전유부수 → 상대적 심각도(등록 대비 몇 배나 쪼개졌는지)
큰 건물은 격차가 크게 나오고, 작은 건물이라도 배율은 크게 나올 수 있어서
(예: 등록 1건인데 실제 20건이면 격차는 작아도 배율은 20배) 둘 다 참고해야
"규모는 작지만 등록 자체가 무의미해진 건물"도 놓치지 않도록 한다.

의심도 점수(0~100)는 격차 순위와 배율 순위를 정규화해서 결합한다(각 0.5 가중치,
risk_grade_model.py의 절대기준 점수화 방식과 동일한 사고방식).

필요한 파일: verification_log.csv 
"""

import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def analyze():
    """
    verification_log.csv를 읽어 집합건축물 중 불일치(등록<실제) 건만 추려서
    격차·배율·의심도 점수를 계산하고 순위를 매기기.
    """
    path = os.path.join(BASE_DIR, "cvs", "verification_log.csv")
    df = pd.read_csv(path, encoding="utf-8-sig")

    mismatched = df[df["비고"] == "불일치(등록<실제)"].copy()
    mismatched["등록전유부수"] = mismatched["등록전유부수"].astype(int)
    mismatched["실제영업중수"] = mismatched["실제영업중수"].astype(int)

    mismatched["격차"] = mismatched["실제영업중수"] - mismatched["등록전유부수"]
    mismatched["배율"] = (mismatched["실제영업중수"] / mismatched["등록전유부수"]).round(1)

    # 격차·배율 각각 0~100으로 정규화(최소=0점, 최대=100점) 후 결합
    def normalize(s):
        return (s - s.min()) / (s.max() - s.min()) * 100

    mismatched["격차점수"] = normalize(mismatched["격차"])
    mismatched["배율점수"] = normalize(mismatched["배율"])
    mismatched["의심도점수"] = (0.5 * mismatched["격차점수"] + 0.5 * mismatched["배율점수"]).round(1)

    mismatched = mismatched.sort_values("의심도점수", ascending=False).reset_index(drop=True)

    n_total_scanned = len(df)
    n_collective = len(df[df["건물유형"] == "집합"])
    n_mismatched = len(mismatched)

    return {
        "n_total_scanned": n_total_scanned,
        "n_collective": n_collective,
        "n_mismatched": n_mismatched,
        "mismatch_rate": round(n_mismatched / n_collective * 100, 1) if n_collective else 0,
        "ranked": mismatched,
    }


if __name__ == "__main__":
    result = analyze()
    print(f"전체 스캔 {result['n_total_scanned']}개 / 집합건축물 {result['n_collective']}개 / "
          f"불일치 {result['n_mismatched']}개 ({result['mismatch_rate']}%)")
    print()
    print("=== 의심도 점수 상위 15건 ===")
    top15 = result["ranked"].head(15)
    for _, r in top15.iterrows():
        print(f"[{r['의심도점수']:5.1f}점] {r['시군구']:5s} {r['상가명']:20s} "
              f"등록 {r['등록전유부수']:3d} → 실제 {r['실제영업중수']:4d} "
              f"(격차 +{r['격차']}, {r['배율']}배)")


# HTML (analyze() 결과로 역산공실탐지기반_의심건물스크리닝.html 뽑음)
import json


def generate(result: dict) -> str:
    ranked = result["ranked"]
    top30 = ranked.head(30)

    rows_html = ""
    for i, r in top30.iterrows():
        rank = i + 1
        rows_html += f"""<tr>
            <td>{rank}</td>
            <td>{r['시군구']}</td>
            <td>{r['상가명']}</td>
            <td>{r['건물명'] if pd.notna(r['건물명']) and str(r['건물명']).strip() else '-'}</td>
            <td>{r['등록전유부수']}</td>
            <td>{r['실제영업중수']}</td>
            <td style="color:#e34948;font-weight:600;">+{r['격차']}</td>
            <td style="color:#e34948;font-weight:600;">{r['배율']}배</td>
            <td><span class="score-badge">{r['의심도점수']}</span></td>
        </tr>"""

    bar_labels = json.dumps([f"{r['시군구']} {r['상가명']}" for _, r in top30.head(15).iterrows()], ensure_ascii=False)
    bar_values = json.dumps([r["의심도점수"] for _, r in top30.head(15).iterrows()])

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>역산공실탐지기반 — 의심건물 스크리닝 리포트 (2단계)</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8f8f7; color: #0b0b0b; padding: 2rem; }}
  h1 {{ font-size: 18px; font-weight: 500; margin-bottom: 4px; }}
  .subtitle {{ font-size: 12px; color: #898781; margin-bottom: 1.5rem; }}
  .scope {{ background: #eff6ff; border-left: 3px solid #2a78d6; padding: 0.875rem 1.1rem; font-size: 12px; color: #52514e; margin-bottom: 1.5rem; line-height: 1.7; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 1.5rem; }}
  .kpi-card {{ background: #f1f0eb; border-radius: 8px; padding: 1rem; text-align: center; }}
  .kpi-label {{ font-size: 12px; color: #898781; margin-bottom: 6px; }}
  .kpi-value {{ font-size: 24px; font-weight: 600; }}
  .chart-box {{ background: #fff; border-radius: 12px; border: 0.5px solid rgba(11,11,11,0.1); padding: 1.25rem; margin-bottom: 1.5rem; }}
  .chart-title {{ font-size: 13px; font-weight: 500; color: #52514e; margin-bottom: 12px; }}
  .chart-wrap {{ position: relative; height: 380px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th {{ text-align: left; color: #898781; font-weight: 500; padding: 6px 8px; border-bottom: 1px solid #e8e7e2; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #f1f0eb; }}
  .score-badge {{ display: inline-block; background: #fef2f2; color: #e34948; font-weight: 700; padding: 2px 10px; border-radius: 20px; }}
  .note {{ font-size: 11px; color: #898781; margin-top: 1.5rem; line-height: 1.6; }}
</style>
</head>
<body>
<h1>역산공실탐지기반 — 의심건물 스크리닝 리포트 (2단계)</h1>
<div class="subtitle">등록전유부수 대비 실제영업중수 격차 기반 우선 확인 대상 우선순위 — verification_log.csv(303개 건물 실측) 재활용</div>

<div class="scope">
📍 <b>이 리포트의 성격:</b> "등록전유부수 &lt; 실제영업중수" 불일치는 그 자체로 불법 증축·무단 용도변경을 확정하는 증거가 아니라,
<b>건축안전센터·국토안전관리원 등이 현장에서 확인해봐야 할 우선순위</b>를 데이터로 제시하는 것이다. 최종 판단은 관할 행정기관의
현장 확인을 거쳐야 한다. 본 리포트는 1단계(안전등급 진단)에서 이미 수집한 실측 데이터를 재사용해 산출했으며, 별도의
추가 데이터 수집 없이 즉시 생성 가능하다.
</div>

<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-label">전체 스캔 건물</div>
    <div class="kpi-value" style="color:#52514e;">{result['n_total_scanned']}개</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">집합건축물</div>
    <div class="kpi-value" style="color:#2a78d6;">{result['n_collective']}개</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">등록-실제 불일치</div>
    <div class="kpi-value" style="color:#e34948;">{result['n_mismatched']}개</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">불일치 비율</div>
    <div class="kpi-value" style="color:#e34948;">{result['mismatch_rate']}%</div>
  </div>
</div>

<div class="chart-box">
  <div class="chart-title">의심도 점수 상위 15건 (격차·배율 결합 점수)</div>
  <div class="chart-wrap"><canvas id="barChart"></canvas></div>
</div>

<div class="chart-box">
  <div class="chart-title">의심도 점수 상위 30건 상세 — 확인 우선순위 리스트</div>
  <table>
    <thead><tr><th>순위</th><th>시군구</th><th>상가명(기준)</th><th>건물명</th><th>등록전유부</th><th>실제영업중</th><th>격차</th><th>배율</th><th>의심도점수</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>

<div class="note">
※ 방법론: verification_log.csv에서 "등록전유부수 &lt; 실제영업중수" 불일치가 확인된 {result['n_mismatched']}개 건물을 대상으로,
격차(실제영업중수 − 등록전유부수)와 배율(실제영업중수 ÷ 등록전유부수)을 각각 0~100으로 정규화한 뒤 동일 가중치(0.5:0.5)로
결합해 의심도 점수를 산출했다. 격차는 관리 사각지대의 절대적 규모를, 배율은 등록 대비 실제 운영이 얼마나 벗어났는지를
나타낸다. 데이터: 소상공인시장진흥공단 상가(상권)정보 API, 국토교통부 건축HUB 건축물대장정보 API(2026년 실측).
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
new Chart(document.getElementById('barChart'), {{
  type: 'bar',
  data: {{
    labels: {bar_labels},
    datasets: [{{ data: {bar_values}, backgroundColor: '#e34948', borderRadius: 3 }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ color: '#e1e0d9' }}, min: 0, max: 100 }},
      y: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 10 }} }} }}
    }}
  }}
}});
</script>
</body>
</html>"""


if __name__ == "__main__":
    result = analyze()
    html = generate(result)
    os.makedirs(os.path.join(BASE_DIR, "html"), exist_ok=True)
    output_path = os.path.join(BASE_DIR, "html", "역산공실탐지기반_의심건물스크리닝.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nHTML 생성 완료: {output_path}")
