# main.py (최종 수정본 - 버그 수정 완료, CFS/CIS 동시 조회)

import os
import requests
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import List

# .env 파일에서 환경 변수 불러오기
load_dotenv()

# FastAPI 앱 생성
app = FastAPI()

# ======== CORS 설정 (중요) ========
origins = [
    "*"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ==================================


def fetch_dart_api_by_div(corp_code: str, year: str, fs_div: str):
    """
    DART API로부터 *특정 연도, 특정 재무제표*의 정보를 가져오는 헬퍼 함수
    fs_div: 'CFS' (연결재무상태표) 또는 'CIS' (연결손익계산서)
    """
    API_KEY = os.getenv("OPEN_DART_API_KEY")
    BASE_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    
    params = {
        'crtfc_key': API_KEY,
        'corp_code': corp_code,
        'bsns_year': year,
        'reprt_code': '11011',  # 사업보고서
        'fs_div': fs_div         # 'CFS' 또는 'CIS'
    }
    
    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == '000':
            raw_data_list = data.get('list', [])
            processed_list = []
            
            # for 루프를 돌며 모든 항목을 정제
            for item in raw_data_list:
                if not item.get('account_nm'):
                    continue
                account_name = item['account_nm'].strip()
                if '(손실)' in account_name:
                    account_name = account_name.replace('(손실)', '')

                item['account_nm'] = account_name
                processed_list.append(item)
            
            # [버그 수정] 루프가 *모두 끝난 뒤*에 정제된 리스트를 반환
            return processed_list 
        
        else:
            print(f"DART API Error for {year} ({fs_div}): {data.get('message')}")
            return None
            
    except Exception as e:
        print(f"HTTP/Parsing Error for {year} ({fs_div}): {str(e)}")
        return None
    
    
# 2. API 엔드포인트(라우터)
@app.get("/api/financials/{corp_code}")
async def get_financial_statements_range(
    corp_code: str, 
    start_year: str,
    end_year: str
):
    """
    Next.js가 호출할 API 엔드포인트입니다.
    매년 2회(CFS, CIS) API를 호출하고 결과를 합칩니다.
    """
    print(f"Received request for {corp_code} from {start_year} to {end_year}")
    
    all_financial_data = []
    
    for year in range(int(start_year), int(end_year) + 1):
        year_str = str(year)
        print(f"Fetching data for year: {year_str}...")
        
        # 1. 재무상태표(CFS) 호출
        print(f"  ... fetching CFS (Balance Sheet) for {year_str}")
        data_list_cfs = fetch_dart_api_by_div(corp_code, year_str, 'CFS')
        time.sleep(0.5) # DART API 딜레이

        # 2. 손익계산서(CIS) 호출
        print(f"  ... fetching CIS (Income Statement) for {year_str}")
        data_list_cis = fetch_dart_api_by_div(corp_code, year_str, 'CIS')
        time.sleep(0.5) # DART API 딜레이

        # 두 리스트를 하나로 합침
        if data_list_cfs:
            all_financial_data.extend(data_list_cfs)
        if data_list_cis:
            all_financial_data.extend(data_list_cis)

    if not all_financial_data:
        return {"data": {"error": "선택한 기간에 조회된 데이터가 없습니다."}}

    # 모든 연도의 (CFS + CIS) 데이터를 취합하여 반환
    return {"data": all_financial_data}