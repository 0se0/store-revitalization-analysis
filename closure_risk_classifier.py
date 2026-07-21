"""
상권x업종 폐업위험 조기경보 모델
서울시 우리마을가게 상권분석서비스 CSV 5개(2021~2025) 읽어서 Random Forest로
다음 분기에 폐업위험이 통계적으로 유의하게 늘어날 상권x업종 예측함.
결과물은 역산공실탐지기반_폐업예측모델_수정본.html

라벨 정하는 방식 계속 바꿔가면서 시행착오 좀 있었음..

1차: 그냥 다음분기 폐업률(%) 자체를 회귀로 예측해봄
    -> R2 0.11밖에 안 나옴. 업종 평균 빼고 순수 잔차만 보면 R2 0.001, 거의 못 맞춤

2차: "폐업률 5%p 이상 급증"으로 이진분류 라벨 만듦
    -> 근데 이거 하니까 점포수 20~25개인 작은 상권은 매장 하나만 닫아도 5%p 넘어버림.
       원래 폐업률 0%였던 곳들이 이상하게 다 위험군으로 잡혀버리는 문제 발견

3차: 그래서 "폐업 매장수 절대 개수 2개 이상 증가"로 바꿔봄
    -> 2차 문제는 해결됐는데 이번엔 반대로 대형 상권(점포수 많은 곳)이 절대 개수
       기준을 그냥 규모빨로 쉽게 넘겨버리는 편향 생김. 확인해보니 20~50개 상권은
       위험비율 4.3%인데 200개 이상 상권은 10.4%나 됨. 규모별로 공평하지가 않음

4차(이걸로 최종): 당분기 폐업률이랑 다음분기 폐업률 두 비율 차이를 표본크기
    기준 표준오차로 나눠서 z-검정으로 판정하는 걸로 바꿈. 이러면 상권 크기랑
    상관없이 "통계적으로 진짜 유의미하게 늘었나"만 봄. 규모 편향도 많이 줄고
    (남은 편향 2.4배 정도) AUC도 오히려 0.79에서 0.88로 올라감

정리하면:
  - 라벨: z >= 1.64 (한쪽 방향 90% 신뢰수준)면 위험신호 1
  - 점포수 20개 미만인 조합은 비율 자체가 너무 튀어서 그냥 뺌
  - 피처는 당분기 지표들(점포수/개업율/폐업률 등) + lag/추세(전분기 대비, 3분기 이평,
    최근 기울기) + 계절성(분기번호)
  - 2024 4분기까지 학습, 2025 1~3분기로 검증 (시계열이라 섞으면 안 되니까 순서대로 split)
  - class_weight=balanced 쓰면 확률값이 부풀려져서 isotonic으로 다시 보정함
"""
import glob
import json
import os
import unicodedata

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CVS_DIR = os.path.join(BASE_DIR, "cvs")
HTML_DIR = os.path.join(BASE_DIR, "html")
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.preprocessing import LabelEncoder

MIN_STOR = 20
Z_THRESHOLD = 1.64  # 두 비율 z-검정 기준(약 90% 단측 신뢰수준) — 표본크기(점포수) 편향 없는 "통계적으로 유의한 폐업률 증가" 판정
DECISION_THRESHOLD = 0.10  # 보정된 확률 기준. 재현율 우선 설계(조기경보는 놓치는 것보다 과잉경보가 나음)
TRAIN_MAX_Q = 20244
TEST_MIN_Q = 20251

COLMAP = {
    '기준_년분기_코드': 'stdr_yyqu_cd', '상권_구분_코드': 'trdar_se_cd', '상권_구분_코드_명': 'trdar_se_cd_nm',
    '상권_코드': 'trdar_cd', '상권_코드_명': 'trdar_cd_nm', '서비스_업종_코드': 'svc_induty_cd',
    '서비스_업종_코드_명': 'svc_induty_cd_nm', '점포_수': 'stor_co', '유사_업종_점포_수': 'similr_induty_stor_co',
    '개업_율': 'opbiz_rt', '개업_점포_수': 'opbiz_stor_co', '폐업_률': 'clsbiz_rt',
    '폐업_점포_수': 'clsbiz_stor_co', '프랜차이즈_점포_수': 'frc_stor_co',
}

FEATURES = ['stor_co', 'similr_induty_stor_co', 'opbiz_rt', 'opbiz_stor_co',
            'clsbiz_rt', 'clsbiz_stor_co', 'frc_stor_co',
            'prev_clsbiz_rt', 'prev_opbiz_rt', 'stor_co_chg',
            'clsbiz_rt_ma3', 'opbiz_rt_ma3', 'clsbiz_rt_trend', 'clsbiz_rt_slope3', 'quarter_num',
            'trdar_se_enc', 'induty_enc']

FEATURE_LABELS = {
    'stor_co': '점포수', 'similr_induty_stor_co': '유사업종 점포수', 'opbiz_rt': '개업율',
    'opbiz_stor_co': '개업점포수', 'clsbiz_rt': '당분기 폐업률', 'clsbiz_stor_co': '폐업점포수',
    'frc_stor_co': '프랜차이즈점포수', 'prev_clsbiz_rt': '전분기 폐업률', 'prev_opbiz_rt': '전분기 개업율',
    'stor_co_chg': '점포수 증감', 'clsbiz_rt_ma3': '폐업률 3분기 이동평균', 'opbiz_rt_ma3': '개업율 3분기 이동평균',
    'clsbiz_rt_trend': '폐업률 직전변화', 'clsbiz_rt_slope3': '폐업률 최근기울기', 'quarter_num': '분기(계절성)',
    'trdar_se_enc': '상권구분', 'induty_enc': '업종',
}


def _find_year_csvs():
    out = {}
    for f in glob.glob(os.path.join(CVS_DIR, "*.csv")):
        fn = unicodedata.normalize("NFC", f)
        if "상권분석서비스" in fn and "점포" in fn:
            for y in ["2021", "2022", "2023", "2024", "2025"]:
                if y in fn:
                    out[y] = f
    missing = [y for y in ["2021", "2022", "2023", "2024", "2025"] if y not in out]
    if missing:
        raise FileNotFoundError(f"CSV 없음: {missing}")
    return out


def load_panel():
    files = _find_year_csvs()
    dfs = []
    for y in sorted(files):
        df = pd.read_csv(files[y], encoding='cp949').rename(columns=COLMAP)
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def build_features(full):
    full = full.sort_values(['trdar_cd', 'svc_induty_cd', 'stdr_yyqu_cd']).reset_index(drop=True)
    g = full.groupby(['trdar_cd', 'svc_induty_cd'])
    full['target_next_clsbiz_rt'] = g['clsbiz_rt'].shift(-1)
    full['target_next_clsbiz_stor_co'] = g['clsbiz_stor_co'].shift(-1)
    full['target_next_stor_co'] = g['stor_co'].shift(-1)
    full['prev_clsbiz_rt'] = g['clsbiz_rt'].shift(1)
    full['prev_opbiz_rt'] = g['opbiz_rt'].shift(1)
    full['stor_co_chg'] = full['stor_co'] - g['stor_co'].shift(1)
    full['clsbiz_rt_ma3'] = g['clsbiz_rt'].transform(lambda s: s.rolling(3, min_periods=2).mean())
    full['opbiz_rt_ma3'] = g['opbiz_rt'].transform(lambda s: s.rolling(3, min_periods=2).mean())
    full['clsbiz_rt_trend'] = full['clsbiz_rt'] - full['prev_clsbiz_rt']
    full['clsbiz_rt_2ago'] = g['clsbiz_rt'].shift(2)
    full['clsbiz_rt_slope3'] = (full['clsbiz_rt'] - full['clsbiz_rt_2ago']) / 2
    full['quarter_num'] = (full['stdr_yyqu_cd'] % 10).astype(int)
    return full


def main():
    print("1) CSV 5개 로드 중...")
    full = load_panel()
    print(f"   전체 패널: {len(full):,}행, {full['stdr_yyqu_cd'].nunique()}개 분기")

    print("2) lag/추세 피처 생성 중...")
    full = build_features(full)

    le_se = LabelEncoder()
    le_induty = LabelEncoder()
    full['trdar_se_enc'] = le_se.fit_transform(full['trdar_se_cd'])
    full['induty_enc'] = le_induty.fit_transform(full['svc_induty_cd'])

    needed = ['target_next_clsbiz_stor_co', 'target_next_stor_co', 'prev_clsbiz_rt', 'prev_opbiz_rt',
              'clsbiz_rt_ma3', 'clsbiz_rt_slope3']
    model_df = full.dropna(subset=needed)
    sub = model_df[model_df['stor_co'] >= MIN_STOR].copy()

    # 당분기 폐업률 vs 다음분기 폐업률 차이를 표본크기 기준 표준오차로 나눈 z-score
    # (%p 절대치나 폐업매장수 그대로 쓰면 작은/큰 상권 쪽으로 편향되는 거 확인했어서
    # 이렇게 표본크기 통제해서 계산함)
    p1 = sub['clsbiz_stor_co'] / sub['stor_co']
    n1 = sub['stor_co']
    p2 = sub['target_next_clsbiz_stor_co'] / sub['target_next_stor_co']
    n2 = sub['target_next_stor_co']
    p_pool = (sub['clsbiz_stor_co'] + sub['target_next_clsbiz_stor_co']) / (n1 + n2)
    se = np.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    sub['z_score'] = (p2 - p1) / se
    sub = sub[sub['z_score'].notna() & np.isfinite(sub['z_score'])]
    sub['risk_label'] = (sub['z_score'] >= Z_THRESHOLD).astype(int)
    print(f"   점포수 {MIN_STOR}개 이상 필터: {len(sub):,}행, 위험(통계적 유의 증가) 비율 {sub['risk_label'].mean()*100:.1f}%")

    train = sub[sub['stdr_yyqu_cd'] <= TRAIN_MAX_Q]
    test = sub[sub['stdr_yyqu_cd'] >= TEST_MIN_Q]
    print(f"3) 학습: {len(train):,}행(~{TRAIN_MAX_Q}) / 검증: {len(test):,}행({TEST_MIN_Q}~), "
          f"검증셋 위험비율 {test['risk_label'].mean()*100:.1f}%")

    base_clf = RandomForestClassifier(n_estimators=300, max_depth=8, min_samples_leaf=15,
                                       class_weight='balanced', n_jobs=-1, random_state=42)
    # class_weight='balanced' 쓰면 AUC(순위판별)엔 도움되는데 predict_proba 값 자체는
    # 실제보다 부풀려짐(확인해보니 평균 39% 나오는데 실제 위험비율은 13%였음)
    # isotonic 보정으로 표시되는 확률을 실제 빈도에 맞게 다시 조정함 (AUC는 그대로)
    clf = CalibratedClassifierCV(base_clf, method='isotonic', cv=3)
    clf.fit(train[FEATURES], train['risk_label'])
    proba = clf.predict_proba(test[FEATURES])[:, 1]
    pred = (proba >= DECISION_THRESHOLD).astype(int)

    auc = roc_auc_score(test['risk_label'], proba)
    prec = precision_score(test['risk_label'], pred)
    rec = recall_score(test['risk_label'], pred)
    f1 = f1_score(test['risk_label'], pred)
    cm = confusion_matrix(test['risk_label'], pred)
    print(f"4) 결과 — AUC {auc:.3f}  Precision {prec:.3f}  Recall {rec:.3f}  F1 {f1:.3f}")

    naive_proba = test['clsbiz_rt'] / test['clsbiz_rt'].max()
    naive_auc = roc_auc_score(test['risk_label'], naive_proba)
    print(f"   [대조군] 단순규칙(현재 폐업률 기준) AUC {naive_auc:.3f}")

    importances = pd.Series(
        np.mean([c.estimator.feature_importances_ for c in clf.calibrated_classifiers_], axis=0),
        index=FEATURES
    ).sort_values(ascending=False)

    latest = full[full['stdr_yyqu_cd'] == full['stdr_yyqu_cd'].max()].dropna(subset=needed[2:]).copy()
    latest = latest[latest['stor_co'] >= MIN_STOR]
    latest['risk_proba'] = clf.predict_proba(latest[FEATURES])[:, 1]
    top10 = latest.sort_values('risk_proba', ascending=False).head(10)
    by_induty = latest.groupby('svc_induty_cd_nm')['risk_proba'].mean().sort_values(ascending=False).head(8)

    result = {
        "min_stor": MIN_STOR, "z_threshold": Z_THRESHOLD,
        "n_train": len(train), "n_test": len(test),
        "positive_rate": round(float(sub['risk_label'].mean()) * 100, 1),
        "auc": round(float(auc), 3), "naive_auc": round(float(naive_auc), 3),
        "precision": round(float(prec), 3), "recall": round(float(rec), 3), "f1": round(float(f1), 3),
        "cm": cm.tolist(),
        "importances": [{"name": FEATURE_LABELS.get(k, k), "value": round(float(v), 3)}
                         for k, v in importances.head(8).items()],
        "top10": top10[['trdar_cd_nm', 'trdar_se_cd_nm', 'svc_induty_cd_nm', 'stor_co',
                         'clsbiz_rt', 'risk_proba']].assign(
            risk_proba=lambda d: (d['risk_proba'] * 100).round(1)).round(1).to_dict('records'),
        "by_induty": [{"name": k, "value": round(float(v) * 100, 1)} for k, v in by_induty.items()],
        "latest_quarter": int(full['stdr_yyqu_cd'].max()),
    }
    write_html(result)
    return result


def _fmt_q(q):
    q = int(q)
    return f"{q // 10}년 {q % 10}분기"


def write_html(r):
    html = HTML_TEMPLATE.format(
        auc=r['auc'], naive_auc=r['naive_auc'], recall=r['recall'], precision=r['precision'], f1=r['f1'],
        n_train=f"{r['n_train']:,}", n_test=f"{r['n_test']:,}", min_stor=r['min_stor'],
        z_threshold=r['z_threshold'], pos_rate=r['positive_rate'], latest_q=_fmt_q(r['latest_quarter']),
        tp=r['cm'][1][1], fn=r['cm'][1][0], fp=r['cm'][0][1], tn=r['cm'][0][0],
        imp_json=json.dumps(r['importances'], ensure_ascii=False),
        induty_json=json.dumps(r['by_induty'], ensure_ascii=False),
        top10_json=json.dumps(r['top10'], ensure_ascii=False),
    )
    with open(os.path.join(HTML_DIR, "역산공실탐지기반_폐업예측모델_수정본.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"생성 완료: {os.path.join(HTML_DIR, '역산공실탐지기반_폐업예측모델_수정본.html')}")


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>역산공실탐지기반 — 상권 폐업위험 조기경보 모델</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8f8f7; color: #0b0b0b; padding: 2rem; }}
  h1 {{ font-size: 18px; font-weight: 500; margin-bottom: 4px; }}
  .subtitle {{ font-size: 12px; color: #898781; margin-bottom: 1.5rem; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 1.5rem; }}
  .kpi-card {{ background: #f1f0eb; border-radius: 8px; padding: 1rem; text-align: center; }}
  .kpi-label {{ font-size: 12px; color: #898781; margin-bottom: 6px; }}
  .kpi-value {{ font-size: 24px; font-weight: 500; }}
  .kpi-sub {{ font-size: 11px; color: #898781; margin-top: 4px; }}
  .green {{ color: #3b6d11; }} .gray {{ color: #52514e; }} .red {{ color: #e34948; }}
  .chart-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 1.5rem; }}
  .chart-box {{ background: #fff; border-radius: 12px; border: 0.5px solid rgba(11,11,11,0.1); padding: 1.25rem; }}
  .chart-title {{ font-size: 13px; font-weight: 500; color: #52514e; margin-bottom: 12px; }}
  .chart-wrap {{ position: relative; height: 260px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th {{ text-align: left; color: #898781; font-weight: 500; padding: 6px 8px; border-bottom: 1px solid #e8e7e2; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #f1f0eb; }}
  .risk-high {{ color: #e34948; font-weight: 600; }}
  .note {{ font-size: 11px; color: #898781; margin-top: 1.5rem; line-height: 1.6; }}
  .caveat {{ background: #fef2f2; border-left: 3px solid #e34948; padding: 0.75rem 1rem; font-size: 12px; color: #52514e; margin-bottom: 1.5rem; line-height: 1.6; }}
  .scope {{ background: #eff6ff; border-left: 3px solid #2a78d6; padding: 0.75rem 1rem; font-size: 12px; color: #52514e; margin-bottom: 1.5rem; line-height: 1.6; }}
  .cm-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 8px; }}
  .cm-cell {{ background: #f8f8f7; border-radius: 6px; padding: 10px; text-align: center; }}
  .cm-cell .n {{ font-size: 18px; font-weight: 600; }}
  .cm-cell .lbl {{ font-size: 10px; color: #898781; margin-top: 2px; }}
</style>
</head>
<body>
<h1>역산공실탐지기반 — 상권×업종 폐업위험 조기경보 모델</h1>
<div class="subtitle">Random Forest Classifier | 라벨: 두 비율 z-검정(z≥{z_threshold})으로 판정한 "다음 분기 폐업률의 통계적으로 유의한 증가" 여부 | 데이터: 서울시 우리마을가게 상권분석서비스(2021~2025, 20개 분기)</div>

<div class="scope">
📍 <b>이 모델의 서비스 내 위치:</b> 이 모델은 "공실 탐지"(건축물대장×상가정보 교차매칭으로 개별 빈 호수를 찾는 것)와는
다른 데이터·다른 목적의 분석이다. 이 모델은 <b>영업 중인 상권×업종</b>이 다음 분기에 폐업 위험이 통계적으로
유의하게 증가할지를 예측하며, 서비스의 <b>③ 상권 리포트</b> 기능(창업자가 입주 전 해당 상권의 폐업 위험도를
미리 확인하는 기능)의 근거 데이터로 사용된다. 공실 탐지 알고리즘 자체의 근거로는 사용되지 않는다.
</div>

<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-label">AUC</div>
    <div class="kpi-value green">{auc}</div>
    <div class="kpi-sub">단순규칙 대조군 {naive_auc}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Recall (재현율)</div>
    <div class="kpi-value gray">{recall}</div>
    <div class="kpi-sub">실제 위험 급증 중 탐지 비율</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Precision (정밀도)</div>
    <div class="kpi-value gray">{precision}</div>
    <div class="kpi-sub">위험 예측 중 실제 적중 비율</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">검증 표본</div>
    <div class="kpi-value gray">{n_test}</div>
    <div class="kpi-sub">2025년 1~3분기 (학습 {n_train}행)</div>
  </div>
</div>

<div class="caveat">
⚠ <b>정직한 방법론 고지 (버전 히스토리):</b>
① 처음엔 "다음 분기 정확한 폐업률(%)"을 회귀로 예측 → R²=0.11로 약함, 업종 평균 제거 후 잔차 R²=0.001(사실상 0).
② "폐업률 5%p 이상 급증"을 이진분류 라벨로 사용 → 점포수 20~25개 상권은 매장 1개만 닫아도 5%p가 되어
당분기 폐업률 0%인 곳이 구조적으로 과대평가됨을 발견.
③ "폐업 매장 수 2개 이상 증가"(절대 개수 기준)로 수정 → ②의 왜곡은 해결됐지만, 이번엔 반대로 <b>점포수가
많은 대형 상권일수록 절대 개수 기준을 그냥 규모만으로 넘기기 쉬운 새로운 편향</b>을 발견(점포수 20~50 상권 위험비율
4.3% vs 200개 이상 상권 10.4%).
④(최종) 두 비율(당분기·다음분기 폐업률)의 차이를 표본크기 기반 표준오차로 나눈 <b>z-검정(z≥{z_threshold})</b>으로
재정의 — 상권 규모와 무관하게 "통계적으로 유의한 변화"만 위험으로 판정. 규모 편향이 대부분 해소됐고
(잔여 편향 2.4배 수준, ③의 3.8배·②의 그 이상보다 크게 개선) <b>AUC {auc}</b>로 오히려 성능도 향상됨.
클래스 불균형 보정(class_weight=balanced)이 표시 확률을 부풀리는 부작용이 있어 isotonic 보정으로 실제 빈도에
맞게 재조정했습니다(보정 후에도 AUC는 동일). 정밀도({precision})가 낮아 오탐이 있지만, 조기경보 시스템 특성상
재현율({recall})을 우선한 설계입니다. 점포수 {min_stor}개 미만 상권은 표본이 작아 분석에서 제외했습니다.
</div>

<div class="chart-grid">
  <div class="chart-box">
    <div class="chart-title">피처 중요도</div>
    <div class="chart-wrap"><canvas id="impChart"></canvas></div>
  </div>
  <div class="chart-box">
    <div class="chart-title">혼동행렬 (2025년 검증셋)</div>
    <div class="cm-grid">
      <div class="cm-cell"><div class="n" style="color:#3b6d11;">{tp}</div><div class="lbl">TP — 위험 급증을 맞게 예측</div></div>
      <div class="cm-cell"><div class="n" style="color:#e34948;">{fn}</div><div class="lbl">FN — 놓친 위험 급증</div></div>
      <div class="cm-cell"><div class="n" style="color:#898781;">{fp}</div><div class="lbl">FP — 오탐(과잉경보)</div></div>
      <div class="cm-cell"><div class="n" style="color:#898781;">{tn}</div><div class="lbl">TN — 정상 맞게 예측</div></div>
    </div>
  </div>
</div>

<div class="chart-box" style="margin-bottom:1.5rem;">
  <div class="chart-title">업종별 평균 폐업위험 확률 (다음 분기, 상위 8개)</div>
  <div class="chart-wrap"><canvas id="indutyChart"></canvas></div>
</div>

<div class="chart-box">
  <div class="chart-title">{latest_q} 기준 다음 분기 폐업위험 상위 10 상권×업종</div>
  <table>
    <thead><tr><th>상권</th><th>구분</th><th>업종</th><th>점포수</th><th>당분기 폐업률</th><th>위험 확률</th></tr></thead>
    <tbody id="top10Body"></tbody>
  </table>
</div>

<div class="note">
※ 방법론: 상권×업종 조합의 당분기 지표(점포수, 개업율, 폐업률, 프랜차이즈점포수)와 전분기 대비 변화·추세(3분기 이동평균, 최근 기울기)로
당분기 대비 다음분기 폐업률의 두 비율 z-검정(z≥{z_threshold}, 표본크기 기반 표준오차로 정규화 — 상권 규모와 무관한 판정)을
이진분류. 2024년 4분기까지 학습, 2025년 1~3분기로 검증(시계열 분할). class_weight=balanced로 소수 클래스(위험군 {pos_rate}%) 보정.
데이터: 서울시 우리마을가게 상권분석서비스(상권-점포), data.seoul.go.kr.
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const impData = {imp_json};
const indutyData = {induty_json};
const top10 = {top10_json};

new Chart(document.getElementById('impChart'), {{
  type: 'bar',
  data: {{ labels: impData.map(d=>d.name), datasets: [{{ data: impData.map(d=>d.value), backgroundColor: '#2a78d6', borderRadius: 3 }}] }},
  options: {{ indexAxis: 'y', responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ grid: {{ color: '#e1e0d9' }} }}, y: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 11 }} }} }} }} }}
}});

new Chart(document.getElementById('indutyChart'), {{
  type: 'bar',
  data: {{ labels: indutyData.map(d=>d.name), datasets: [{{ data: indutyData.map(d=>d.value), backgroundColor: '#e34948', borderRadius: 3 }}] }},
  options: {{ indexAxis: 'y', responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: ctx => ctx.parsed.x.toFixed(1) + '%' }} }} }},
    scales: {{ x: {{ grid: {{ color: '#e1e0d9' }}, ticks: {{ callback: v => v + '%' }} }}, y: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 11 }} }} }} }} }}
}});

const tbody = document.getElementById('top10Body');
top10.forEach(d => {{
  tbody.innerHTML += `<tr>
    <td>${{d.trdar_cd_nm}}</td><td>${{d.trdar_se_cd_nm}}</td><td>${{d.svc_induty_cd_nm}}</td>
    <td>${{d.stor_co}}</td><td>${{d.clsbiz_rt}}%</td><td class="risk-high">${{d.risk_proba}}%</td>
  </tr>`;
}});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()