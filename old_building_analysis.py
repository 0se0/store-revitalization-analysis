# ==============================================================================
# [국토교통부] 건물 에너지(전기/가스) & 건축물대장 기반 노후 건물 에너지 효율 분석
# File Name: old_building_analysis.py
# ==============================================================================

import pandas as pd
import numpy as np
import glob
import os
import unicodedata
from datetime import datetime

def read_csv_with_encoding(filepath, **kwargs):
    """
    한글 CSV 파일의 다양한 인코딩(cp949, euc-kr, utf-8)을 순서대로 시도하여 로드하는 함수
    """
    for enc in ['cp949', 'euc-kr', 'utf-8-sig', 'utf-8']:
        try:
            return pd.read_csv(filepath, encoding=enc, **kwargs)
        except Exception:
            continue
    raise ValueError(f"파일을 읽을 수 없습니다: {filepath}")

def load_and_merge_energy_data(folder_path, energy_type="elec"):
    """
    하위 폴더(전기에너지 / 가스에너지) 내의 월별 CSV 파일들을 읽어 통합하는 함수
    """
    print(f"🔍 [{energy_type.upper()}] 에너지 데이터 폴더 탐색 중: {folder_path}")
    if not os.path.exists(folder_path):
        print(f"⚠️ 경고: '{folder_path}' 폴더가 존재하지 않습니다.\n")
        return None
        
    files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith('.csv')]
    files = sorted(files)
    if not files:
        print(f"⚠️ 경고: '{folder_path}' 경로에 CSV 파일이 없습니다.\n")
        return None
    
    df_list = []
    # 메모리 절약을 위한 필수 분석 컬럼 지정
    use_cols = ['crtr_ym', 'signgu_cd', 'lgldong_cd', 'plot_div_cd', 'hsno_1', 'hsno_2', 
                'nadres_rd_cd', 'nadres_bbno', 'nadres_buno', 'use_qy']
    
    for f in files:
        print(f"  └─ 읽는 중: {os.path.basename(f)}")
        try:
            df = read_csv_with_encoding(f, usecols=lambda c: c in use_cols, dtype=str)
            df['use_qy'] = pd.to_numeric(df['use_qy'], errors='coerce').fillna(0)
            df_list.append(df)
        except Exception as e:
            print(f"    ❌ 오류 발생 ({os.path.basename(f)}): {e}")
            
    if not df_list:
        return None

    merged_df = pd.concat(df_list, ignore_index=True)
    print(f"✅ [{energy_type.upper()}] 총 {len(merged_df):,}건 로드 완료.\n")
    return merged_df

def aggregate_energy_by_pnu(df, prefix="elec"):
    """
    월별 에너지 데이터를 지번 PNU(필지고유번호 19자리) 키로 변환 후 연간/계절별 사용량 집계
    """
    print(f"⚙️ [{prefix.upper()}] PNU 키 생성 및 건물별 에너지 사용량 집계 중...")
    
    # PNU 지번 조합 키 (시군구5 + 법정동5 + 대지구분1 + 본번4 + 부번4)
    df['pnu_key'] = (
        df['signgu_cd'].fillna('').astype(str).str.zfill(5) + 
        df['lgldong_cd'].fillna('').astype(str).str.zfill(5) + 
        df['plot_div_cd'].fillna('0').astype(str) + 
        df['hsno_1'].fillna('0').astype(str).str.zfill(4) + 
        df['hsno_2'].fillna('0').astype(str).str.zfill(4)
    )
    
    # 월별 구분 (겨울철: 12, 1, 2, 3월)
    df['month'] = df['crtr_ym'].astype(str).str[-2:]
    df['is_winter'] = df['month'].isin(['12', '01', '02', '03'])
    
    # 건물별 사용량 합계 계산
    agg = df.groupby('pnu_key').agg(
        **{
            f'{prefix}_annual_use': ('use_qy', 'sum'),
            f'{prefix}_winter_use': ('use_qy', lambda x: x[df.loc[x.index, 'is_winter']].sum()),
            f'{prefix}_non_winter_use': ('use_qy', lambda x: x[~df.loc[x.index, 'is_winter']].sum())
        }
    ).reset_index()
    
    return agg

def load_building_register(filepath):
    """
    건축물대장 표제부 데이터 로드 및 노후도 계산
    """
    print(f"🏢 [건축물대장] 표제부 로드 중: {os.path.basename(filepath)}")
    try:
        df = read_csv_with_encoding(filepath, skiprows=[1], low_memory=False)
    except Exception:
        df = read_csv_with_encoding(filepath, low_memory=False)
        
    print(f"  └─ 원본 레코드 수: {len(df):,}건")
    
    # 지번 PNU 키 조합
    df['pnu_key'] = (
        df['시군구코드'].fillna('').astype(str).str.split('.').str[0].str.zfill(5) + 
        df['법정동코드'].fillna('').astype(str).str.split('.').str[0].str.zfill(5) + 
        df['대지구분코드'].fillna('0').astype(str).str.split('.').str[0] + 
        df['번'].fillna('0').astype(str).str.split('.').str[0].str.zfill(4) + 
        df['지'].fillna('0').astype(str).str.split('.').str[0].str.zfill(4)
    )
    
    # 수치형 컬럼 변환
    df['totflar'] = pd.to_numeric(df['연면적(㎡)'], errors='coerce').fillna(0)
    
    # 사용승인일로부터 건물 연식 계산
    current_year = datetime.now().year
    use_aprv = df['사용승인일'].astype(str).str.replace('-', '').str[:4]
    df['approval_year'] = pd.to_numeric(use_aprv, errors='coerce')
    df['building_age'] = current_year - df['approval_year']
    
    # 30년 이상 노후 여부 판단
    df['is_old_30y'] = df['building_age'] >= 30
    
    selected_cols = ['pnu_key', '대지위치', '건물명', '주용도코드명', 'totflar', 'approval_year', 'building_age', 'is_old_30y']
    return df[selected_cols]

def main():
    # ==============================================================
    # 1. 파일 및 폴더 경로 자동 탐색
    # ==============================================================
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    
    # cvs2 폴더 탐색
    if os.path.basename(SCRIPT_DIR) == 'cvs2':
        CVS2_DIR = SCRIPT_DIR
    elif os.path.exists(os.path.join(SCRIPT_DIR, 'cvs2')):
        CVS2_DIR = os.path.join(SCRIPT_DIR, 'cvs2')
    else:
        CVS2_DIR = SCRIPT_DIR
        
    ELEC_DIR = os.path.join(CVS2_DIR, "전기에너지")
    GAS_DIR = os.path.join(CVS2_DIR, "가스에너지")
    
    # 맥 한글 NFD 인코딩 대응 표제부 파일 검색
    all_files = os.listdir(CVS2_DIR)
    bld_files = [
        os.path.join(CVS2_DIR, f) for f in all_files 
        if '표제부' in unicodedata.normalize('NFC', f) and f.endswith('.csv')
    ]
    
    if not bld_files:
        print(f"❌ 건축물대장 표제부 파일(*표제부*.csv)을 '{CVS2_DIR}' 경로에서 찾을 수 없습니다.")
        return
    bld_path = bld_files[0]

    # ==============================================================
    # 2. 데이터 로드 및 집계
    # ==============================================================
    df_bld = load_building_register(bld_path)
    
    df_elec = load_and_merge_energy_data(ELEC_DIR, "elec")
    elec_agg = aggregate_energy_by_pnu(df_elec, "elec") if df_elec is not None else None
    
    df_gas = load_and_merge_energy_data(GAS_DIR, "gas")
    gas_agg = aggregate_energy_by_pnu(df_gas, "gas") if df_gas is not None else None

    # ==============================================================
    # 3. 건축물대장 + 에너지 데이터 연결 (Join)
    # ==============================================================
    print("🔗 건축물대장 데이터와 에너지 사용량 데이터를 PNU 키로 결합 중...")
    merged = df_bld.copy()
    
    if elec_agg is not None:
        merged = pd.merge(merged, elec_agg, on='pnu_key', how='left')
    if gas_agg is not None:
        merged = pd.merge(merged, gas_agg, on='pnu_key', how='left')
        
    merged = merged[merged['totflar'] > 0].copy()

    # ==============================================================
    # 4. 에너지 효율 지표(EUI) 산출
    # ==============================================================
    print("📊 건물별 EUI(단위면적당 에너지 소비량) 계산 중...")
    
    if 'elec_annual_use' in merged.columns:
        merged['elec_eui'] = merged['elec_annual_use'] / merged['totflar']
        
    if 'gas_annual_use' in merged.columns:
        merged['gas_eui'] = merged['gas_annual_use'] / merged['totflar']
        merged['gas_winter_ratio'] = (merged['gas_winter_use'] / (merged['gas_annual_use'] + 1e-6)) * 100

    if 'elec_annual_use' in merged.columns and 'gas_annual_use' in merged.columns:
        merged['total_eui_kwh'] = (merged['elec_annual_use'] + merged['gas_annual_use'] * 10.55) / merged['totflar']

    # ==============================================================
    # 5. 그린 리모델링 최우선 대상 노후 건물 발굴
    # ==============================================================
    if 'total_eui_kwh' in merged.columns:
        eui_threshold = merged['total_eui_kwh'].quantile(0.90)
        merged['priority_target'] = (merged['is_old_30y'] == True) & (merged['total_eui_kwh'] >= eui_threshold)
    elif 'gas_eui' in merged.columns:
        eui_threshold = merged['gas_eui'].quantile(0.90)
        merged['priority_target'] = (merged['is_old_30y'] == True) & (merged['gas_eui'] >= eui_threshold)
    else:
        merged['priority_target'] = merged['is_old_30y'] == True

    # 요약 결과 출력
    total_bld = len(merged)
    old_bld = merged['is_old_30y'].sum()
    target_bld = merged['priority_target'].sum()
    
    print("\n==================================================")
    print(f"📌 [분석 요약 보고]")
    print(f" - 전체 분석 건물 수: {total_bld:,}개")
    print(f" - 30년 이상 노후 건물 수: {old_bld:,}개 ({old_bld/total_bld*100:.1f}%)")
    print(f" - ⭐ 그린리모델링 최우선 대상 건물: {target_bld:,}개")
    print("==================================================\n")

    # ==============================================================
    # 6. 최종 분석 결과 저장
    # ==============================================================
    output_filename = os.path.join(CVS2_DIR, "노후건물_에너지효율_분석결과.csv")
    merged.to_csv(output_filename, index=False, encoding='utf-8-sig')
    print(f"💾 최종 데이터셋 저장 완료: {output_filename}")

if __name__ == "__main__":
    main()