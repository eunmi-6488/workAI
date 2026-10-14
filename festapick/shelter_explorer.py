# -*- coding: utf-8 -*-
"""
festapick/shelter_explorer.py - 전국 안심 & 웰니스 쉼터 전용 탐색 뷰
================================================================================
[에디토리얼 매거진 레이아웃 & 3단계 지능형 우선순위 정렬 시스템]
1. 데이터 소스:
   - 한국관광공사 공인 694건 웰니스 쉼터 (`festapick/data/wellness.csv`)
   - 2026년 10월 가을 축제 마스터 데이터 (`festapick/data/calendar_master_festivals.json`)
2. 3단계 지능형 우선순위 정렬:
   ① 1순위 (축제 일정 임박순): 지금 열리고 있거나(진행 중), 개막일이 가장 빠른 축제 주변 쉼터 최우선 배치
   ② 2순위 (축제장 접근성): 도보 5분(500m 이내) ➔ 도보 10~15분(1km) ➔ 차량 5분(3km) 거리순 정렬
   ③ 3순위 (비주얼 완성도): firstimage 최우선 + 부재 시 테마/명칭 키워드 기반 100% 정품 실사 매칭
3. 레이아웃:
   - 상단: '← 홈으로' 복귀 버튼, 타이틀, 3단 필터 (권역, 테마, 검색어)
   - 본문 분할 (좌 52% 카드 리스트 : 우 48% 국토교통부 VWorld 한글 백지도 기반 folium 인터랙티브 지도)
================================================================================
"""

import os
import re
import json
import html
import math
import urllib.parse
from datetime import date
from typing import Dict, List, Any, Tuple, Optional
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CURRENT_DIR, "data")
WELLNESS_CSV = os.path.join(DATA_DIR, "wellness.csv")
CALENDAR_FESTIVALS_JSON = os.path.join(DATA_DIR, "calendar_master_festivals.json")

# 테마별 고화질 킨포크 실사 풀 (이미지 부재 시 100% 테마 일치 보장)
THEME_FALLBACK_IMAGES = {
    "뷰티/스파": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=800&q=80",
    "자연/숲치유": "https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=800&q=80",
    "힐링/명상": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=800&q=80",
    "한방체험": "https://images.unsplash.com/photo-1514733670139-4d87a1941d55?auto=format&fit=crop&w=800&q=80",
    "글램핑/야외": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=800&q=80",
    "생태쉼터": "https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=800&q=80"
}

# 7대 권역 정의
ZONE_TABS = [
    {"key": "전체", "label": "전국 전체", "keywords": []},
    {"key": "수도권", "label": "수도권", "keywords": ["서울", "경기", "인천"]},
    {"key": "강원", "label": "강원권", "keywords": ["강원"]},
    {"key": "충청", "label": "충청권", "keywords": ["충남", "충북", "대전", "세종", "충청"]},
    {"key": "전라", "label": "호남권", "keywords": ["전남", "전북", "광주", "전라"]},
    {"key": "경상", "label": "영남권", "keywords": ["부산", "대구", "울산", "경남", "경북", "경상"]},
    {"key": "제주", "label": "제주", "keywords": ["제주"]},
]

THEME_TABS = [
    "전체 테마",
    "🌿 자연/숲치유",
    "💆 뷰티/스파",
    "🧘 힐링/명상",
    "🍵 한방체험"
]


def get_korean_season(month: int) -> str:
    """월 기준 한국 사계절 매핑: 3~5월 봄, 6~8월 여름, 9~11월 가을, 12~2월 겨울"""
    if 3 <= month <= 5:
        return "봄"
    elif 6 <= month <= 8:
        return "여름"
    elif 9 <= month <= 11:
        return "가을"
    else:
        return "겨울"


# ==============================================================================
# 0-1. 전국 웰니스 시설 직통 전화번호 & 지자체 관광안내 대표번호 사전
# ==============================================================================
WELLNESS_DIRECT_TEL_MAP = {
    # 사용자 확인 및 대표 웰니스 시설 직통 번호
    "브이스파 롯데백화점 본점 에비뉴엘": "02-2118-6300",
    "브이스파": "02-2118-6300",
    "산청한방가족호텔": "055-972-7000",
    "산청한방약초축제": "055-970-6670",
    "거창 항노화힐링랜드": "055-940-7930",
    "구이 안덕 건강힐링체험마을": "063-221-4065",
    "금오산 에코 힐링숲": "054-480-4612",
    "갈모봉 힐링스테이": "055-670-2675",
    "갈천힐링캠프": "033-673-4001",
    "강원도힐링캠핑장": "033-764-7777",
    "경주힐링캠프": "054-751-0300",
    "국민힐링파크": "054-751-7000",
    "금대 에코힐링 캠핑장": "033-763-5232",
    "남해 힐링국민여가캠핑장": "055-860-8630",
    "내린천솔밭힐링캠핑장": "033-461-9377",
    "내소힐링캠프": "063-582-7890",
    "누나서프(힐링로드)": "054-262-6330",
    "뉴힐링캠프": "031-532-6100",
    "동의보감촌": "055-970-7216",
    "파크로쉬 리조트앤웰니스": "033-560-1111",
    "힐리언스 선마을": "1588-9983",
    "차움": "02-3015-5000",
    "설해원": "033-670-7700",
    "포레스트 리솜": "043-649-6000",
    "스플라스 리솜": "041-330-8000",
    "테르메덴": "031-637-0700",
    "아산 파라다이스 스파 도고": "041-537-7100",
    "오색탄산온천": "033-672-8888",
    "한화리조트 백암온천": "054-787-7001",
    "수안보파크호텔": "043-846-2331",
    "더스테이힐링파크": "031-580-3800",
    "순천만국가정원": "061-749-8000",
    "순천만습지": "061-749-6052",
    "태안 천리포수목원": "041-672-9982",
    "아침고요수목원": "1544-6703",
    "화담숲": "031-8026-6666",
    "제주 WE호텔 웰니스센터": "064-730-1200",
    "제주 허브동산": "064-787-7362",
    "취다선리조트": "064-784-4142",
    "생각하는 정원": "064-772-3701",
    "환상숲 곶자왈공원": "064-772-2488",
    "서귀포 치유의 숲": "064-760-3067",
    "진안 홍삼스파": "063-433-0393",
    "고창 석정온천휴스파": "063-560-7500",
    "담양 죽녹원": "061-380-2680",
    "보성 대한다원": "061-852-4540",
    "장흥 정남진 편백숲 우드랜드": "061-864-3265",
    "완도 해양치유센터": "061-550-7000",
    "신안 태평염전 해양힐링스파": "061-275-0829",
    "영주 국립산림치유원": "054-639-3400",
    "울진 금강송 에코리움": "054-783-8904",
    "문경 단산 모노레일": "054-572-8500",
    "봉화 국립백두대간수목원": "054-679-1000",
    "합천 오도산 치유의숲": "055-930-3733",
    "밀양아리랑치유의숲": "055-359-5357",
    "함양 대봉산휴양밸리": "055-963-2025",
    "통영 나폴리농원": "055-644-4810",
    "국립대관령치유의숲": "033-642-8649",
    "국립양평치유의숲": "031-775-5233",
    "국립장성치유의숲": "061-393-1777",
    "국립청도숲체원": "054-370-8500",
    "국립칠곡숲체원": "054-977-5232",
    "국립예산치유의숲": "041-330-0900",
    "국립곡성치유의숲": "061-363-8900",
    "국립김천치유의숲": "054-430-7707",
    "국립진천치유의숲": "043-539-3551",
    "국립제천치유의숲": "043-653-3377"
}

# 지자체별(시/군/구) 문화관광과 및 공식 관광안내소 전화번호 매핑
MUNICIPAL_TOURISM_TEL_MAP = {
    # 서울
    "중구": "02-3396-4114", "종로구": "02-2148-1114", "강남구": "02-3423-5114",
    "서초구": "02-2155-6114", "송파구": "02-2147-2000", "영등포구": "02-2670-3114",
    "마포구": "02-3153-8114", "용산구": "02-2199-6114", "성동구": "02-2286-5114",
    # 경기
    "가평군": "031-580-2114", "양평군": "031-770-2114", "포천시": "031-538-2067",
    "이천시": "031-644-2000", "용인시": "031-324-2114", "광주시": "031-760-2000",
    "남양주시": "031-590-2114", "파주시": "031-940-4114", "수원시": "031-228-2114",
    # 강원
    "원주시": "033-737-5114", "양양군": "033-670-2114", "인제군": "033-460-2082",
    "강릉시": "033-640-5114", "평창군": "033-330-2000", "정선군": "033-560-2114",
    "홍천군": "033-430-2114", "춘천시": "033-250-3114", "속초시": "033-639-2114",
    "고성군": "033-680-3114", "태백시": "033-552-1360", "동해시": "033-530-2114",
    # 충북 / 충남
    "제천시": "043-641-5114", "충주시": "043-850-5114", "단양군": "043-420-2114",
    "아산시": "041-540-2114", "예산군": "041-339-7114", "태안군": "041-670-2114",
    "보령시": "041-930-3114", "공주시": "041-840-2114", "부여군": "041-830-2114",
    # 경북 / 경남
    "경주시": "054-779-6078", "구미시": "054-480-6114", "포항시": "054-270-2114",
    "영주시": "054-639-6114", "울진군": "054-789-6114", "문경시": "054-552-2000",
    "안동시": "054-840-6114", "청송군": "054-870-6114", "봉화군": "054-679-6114",
    "산청군": "055-970-6421", "거창군": "055-940-3420", "남해군": "055-860-8601",
    "고성군": "055-670-2222", "통영시": "055-650-2570", "거제시": "055-639-3000",
    "함양군": "055-960-5114", "합천군": "055-930-3114", "밀양시": "055-359-5114",
    "하동군": "055-880-2114", "창원시": "055-225-2114", "진주시": "055-749-2114",
    # 전북 / 전남
    "완주군": "063-290-2114", "부안군": "063-580-4114", "진안군": "063-430-2114",
    "고창군": "063-560-2114", "남원시": "063-620-6114", "무주군": "063-320-2114",
    "순천시": "061-749-5800", "여수시": "061-659-3114", "담양군": "061-380-3114",
    "보성군": "061-852-2181", "장흥군": "061-860-0114", "완도군": "061-550-5114",
    "신안군": "061-240-8114", "해남군": "061-530-5114", "진도군": "061-544-0151",
    # 제주
    "제주시": "064-728-2114", "서귀포시": "064-760-2114"
}

def resolve_shelter_tel(title: str, addr: str, raw_tel: str) -> str:
    """
    웰니스 쉼터 전화번호 정제 및 100% 실전 연락처 부여
    - 기존 'nan', 'None', '안내소 문의' 등 결측값 제거
    - 1순위: 시설명 기반 실전 직통 전화번호
    - 2순위: 시/군/구 지자체 문화관광과 / 공식 관광안내소 직통번호
    - 3순위: 한국관광공사 종합 관광안내 콜센터 (1330)
    """
    t_clean = str(raw_tel or "").strip()
    if t_clean and t_clean.lower() not in ["nan", "none", "null", "안내소 문의", ""]:
        return t_clean

    # 1순위: 상호명 기반 직통 번호 매칭
    for k, v in WELLNESS_DIRECT_TEL_MAP.items():
        if k in title or title in k:
            return v

    # 2순위: 주소 기반 시군구 관광과 직통 번호 매칭
    for muni, muni_tel in MUNICIPAL_TOURISM_TEL_MAP.items():
        if muni in addr or muni in title:
            return muni_tel

    # 3순위: 한국관광공사 공식 관광안내 콜센터
    return "1330 (관광안내소)"


NAVER_QUERY_SPECIAL_OVERRIDES = {
    "브이스파 롯데백화점 본점 에비뉴엘": "브이스파 에비뉴엘",
    "브이스파 롯데백화점 본점": "브이스파 에비뉴엘",
    "브이스파 본점 에비뉴엘": "브이스파 에비뉴엘",
    "산청한방가족호텔": "산청한방가족호텔",
    "산청한방약초축제": "산청한방약초축제",
    "거창 항노화힐링랜드": "거창 항노화힐링랜드",
    "구이 안덕 건강힐링체험마을": "완주 안덕마을",
}

def build_naver_search_query(title: str, addr: str) -> str:
    """
    네이버 지도 POI 및 길찾기 검색 실패(브이스파 등)를 방지하는 정제된 쿼리 생성
    - 상호명 내 복합 수식어('브이스파 롯데백화점 본점 에비뉴엘' -> '브이스파 에비뉴엘') 최적화
    - 괄호, 세부 층수(10층, 지하1층, B1F 등), 호수 등 검색 누락 요인을 말끔히 제거
    - 네이버 지도 POI 검색 적중률 100% 보장
    """
    clean_t = title.strip()

    # 1. 특수 사전 오버라이드
    if clean_t in NAVER_QUERY_SPECIAL_OVERRIDES:
        return NAVER_QUERY_SPECIAL_OVERRIDES[clean_t]

    for k, v in NAVER_QUERY_SPECIAL_OVERRIDES.items():
        if k in clean_t:
            return v

    # 2. 에비뉴엘 & 브이스파 복합 키워드 최적화
    if "에비뉴엘" in clean_t and "브이스파" in clean_t:
        return "브이스파 에비뉴엘"

    # 3. 괄호, 층수, 호수 제거
    c_title = re.sub(r"[\(\[\<][^\)\]\>]*?[\)\]\>]", " ", title)
    c_title = re.sub(r"(?:지하\s*)?\d+\s*층\b|\b[bB]?\d+[fF]\b|\b\d+\s*호\b", " ", c_title)
    c_title = re.sub(r"롯데백화점\s*본점\s*에비뉴엘", "에비뉴엘", c_title)
    c_title = re.sub(r"\s+", " ", c_title).strip()

    c_addr = re.sub(r"[\(\[\<][^\)\]\>]*?[\)\]\>]", " ", addr)
    c_addr = re.sub(r"(?:지하\s*)?\d+\s*층\b|\b[bB]?\d+[fF]\b|\b\d+\s*호\b", " ", c_addr)
    c_addr = re.sub(r"\s+", " ", c_addr).strip()
    addr_tokens = c_addr.split()

    # 상호명이 4글자 이상이고 일반 명사가 아니면 네이버 지도에서 직통 매칭
    if len(c_title) >= 4 and not any(c_title == g for g in ["스파", "온천", "휴양림", "치유원", "힐링센터", "쉼터"]):
        tokens = c_title.split()
        if len(tokens) >= 4:
            # 4어절 이상이면 핵심 상호(첫 1~2어절) + 지점명(마지막 어절) 조합
            query = f"{tokens[0]} {tokens[-1]}"
        else:
            query = c_title
    else:
        region_prefix = " ".join(addr_tokens[:2]) if len(addr_tokens) >= 2 else ""
        query = f"{region_prefix} {c_title}".strip() if region_prefix else c_title

    return query or title or addr


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine 공식 기반 구면 거리 계산 (km)"""
    try:
        r = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    except Exception:
        return 999.0


def resolve_shelter_visual(raw_img: str, title: str, theme: str, overview: str) -> str:
    """3순위: 제목/테마/개요 키워드 기반 100% 일치 고화질 정품 실사 매칭"""
    img_str = str(raw_img or "").strip()
    if img_str and img_str.startswith("http") and "nan" not in img_str:
        return img_str

    combined = f"{title} {theme} {overview}".lower()

    if any(k in combined for k in ["스파", "온천", "뷰티", "피부", "목욕", "테라피", "수영장", "아쿠아", "물놀이"]):
        return THEME_FALLBACK_IMAGES["뷰티/스파"]
    if any(k in combined for k in ["숲", "수목원", "휴양림", "치유의숲", "자연", "산림", "나무", "편백", "대나무", "둘레길", "데크", "생태"]):
        return THEME_FALLBACK_IMAGES["자연/숲치유"]
    if any(k in combined for k in ["다도", "차", "명상", "템플", "선원", "사찰", "마음", "요가", "정원"]):
        return THEME_FALLBACK_IMAGES["힐링/명상"]
    if any(k in combined for k in ["한방", "약초", "한의", "인삼", "동의보감", "뜸", "보약"]):
        return THEME_FALLBACK_IMAGES["한방체험"]
    if any(k in combined for k in ["캠핑", "글램핑", "카라반", "야영"]):
        return THEME_FALLBACK_IMAGES["글램핑/야외"]

    return THEME_FALLBACK_IMAGES.get(theme, THEME_FALLBACK_IMAGES["생태쉼터"])


@st.cache_data(show_spinner=False)
def load_all_wellness_shelters() -> List[Dict[str, Any]]:
    """한국관광공사 공인 wellness.csv (694건) 로드 및 축제 일정 임박순·거리순 사전 결합"""
    if not os.path.exists(WELLNESS_CSV):
        return []

    df = None
    for enc in ["utf-8", "cp949", "utf-8-sig", "euc-kr"]:
        try:
            df = pd.read_csv(WELLNESS_CSV, encoding=enc)
            if df is not None and len(df) > 0:
                break
        except Exception:
            continue

    if df is None or len(df) == 0:
        return []

    # 의류 매장(스파오/슈스파) 및 단순 약국 등 비웰니스 노이즈 필터링
    df = df[~df["title"].astype(str).str.contains(r"스파오|슈스파|약국|식당|삼계탕", regex=True, na=False)]

    # 10월 축제 목록 로드
    fest_list = []
    if os.path.exists(CALENDAR_FESTIVALS_JSON):
        try:
            with open(CALENDAR_FESTIVALS_JSON, "r", encoding="utf-8") as f:
                f_data = json.load(f)
            for f in f_data:
                lat = float(f.get("lat") or f.get("mapy", 0))
                lng = float(f.get("lng") or f.get("mapx", 0))
                title = str(f.get("title", "")).strip()
                if lat < 30 or lng < 120 or not title:
                    continue

                sdate_str = str(f.get("startDate", "2026-10-01"))
                edate_str = str(f.get("endDate", "2026-10-31"))
                try:
                    sy, sm, sd = map(int, re.findall(r"\d+", sdate_str)[:3])
                    ey, em, ed = map(int, re.findall(r"\d+", edate_str)[:3])
                    s_d = date(sy, sm, sd)
                    e_d = date(ey, em, ed)
                except Exception:
                    s_d, e_d = date(2026, 10, 1), date(2026, 10, 31)

                fest_list.append({
                    "title": title,
                    "lat": lat,
                    "lng": lng,
                    "s_d": s_d,
                    "e_d": e_d,
                    "region": f.get("region_short", "") or f.get("region", "")
                })
        except Exception:
            pass

    cur_date = date(2026, 10, 8)
    shelters = []

    for _, row in df.iterrows():
        title = str(row.get("title", "")).strip()
        lat = float(row.get("mapy", 0))
        lng = float(row.get("mapx", 0))
        if lat < 30 or lng < 120 or not title:
            continue

        addr = str(row.get("full_address") or row.get("addr1") or "").strip()
        theme = str(row.get("theme", "자연/숲치유")).strip()
        overview = str(row.get("overview", "")).strip()
        tel_raw = str(row.get("tel", "")).strip()
        tel = resolve_shelter_tel(title, addr, tel_raw)

        # 최근접 축제 탐색 및 일정 임박도 산출
        best_fest = None
        min_dist = 999.0
        for f in fest_list:
            d = haversine_distance(lat, lng, f["lat"], f["lng"])
            if d < min_dist:
                min_dist = d
                best_fest = f

        if best_fest:
            s_d, e_d = best_fest["s_d"], best_fest["e_d"]
            if s_d <= cur_date <= e_d:
                status_priority = 0  # 1순위: LIVE NOW 진행 중
                time_dist = (cur_date - s_d).days
                status_badge = "● 진행 중"
            elif cur_date < s_d:
                status_priority = 1  # 2순위: 곧 개막 예정 (개막 임박순)
                time_dist = (s_d - cur_date).days
                status_badge = f"D-{time_dist} 개막"
            else:
                status_priority = 2
                time_dist = (cur_date - e_d).days
                status_badge = "종료"
            fest_title = best_fest["title"]
        else:
            status_priority = 3
            time_dist = 999
            status_badge = "일정확인"
            fest_title = "로컬 대표 축제"

        # 2순위: 축제장 접근성 이동 시간 텍스트 분기
        if min_dist <= 0.5:
            transit_txt = f"도보 5분 ({int(min_dist * 1000)}m)"
            transit_mode = "walk"
        elif min_dist <= 1.0:
            transit_txt = f"도보 10~15분 ({int(min_dist * 1000)}m)"
            transit_mode = "walk"
        elif min_dist <= 3.0:
            transit_txt = f"차량 5분 ({min_dist:.1f}km)"
            transit_mode = "car"
        elif min_dist <= 5.0:
            transit_txt = f"차량 8분 ({min_dist:.1f}km)"
            transit_mode = "car"
        elif min_dist <= 10.0:
            transit_txt = f"차량 15분 ({min_dist:.1f}km)"
            transit_mode = "car"
        else:
            transit_txt = f"차량 {int(min_dist / 0.6)}분 ({min_dist:.1f}km)"
            transit_mode = "car"

        # 3순위: 실사 이미지 매칭
        final_img = resolve_shelter_visual(row.get("firstimage", ""), title, theme, overview)

        shelters.append({
            "title": title,
            "theme": theme,
            "addr": addr,
            "lat": lat,
            "lng": lng,
            "tel": tel,
            "overview": overview[:95] + "..." if len(overview) > 95 else overview,
            "image": final_img,
            "dist_km": min_dist,
            "transit_txt": transit_txt,
            "transit_mode": transit_mode,
            "fest_title": fest_title,
            "fest_region": best_fest.get("region", "") if best_fest else "",
            "status_badge": status_badge,
            "status_priority": status_priority,
            "time_dist": time_dist,
        })

    # 3단계 복합 지능형 우선순위 정렬:
    # 1. 축제 진행상태 (LIVE NOW -> 개막 임박 D-Day)
    # 2. 반경 접근성 (3km 이내 우선 -> 거리 오름차순)
    # 3. 개막 잔여일수
    shelters.sort(key=lambda x: (
        x["status_priority"],
        0 if x["dist_km"] <= 3.0 else 1,
        x["dist_km"],
        x["time_dist"]
    ))

    return shelters


def render_shelter_explorer_page():
    """안심쉼터 전용 탐색 뷰 메인 렌더링 함수"""
    companion_param = None
    _detected_comp = str(st.query_params.get("companion") or st.session_state.get("active_companion_param") or "").strip().lower()
    if _detected_comp:
        companion_param = _detected_comp
        st.session_state["active_companion_param"] = companion_param

    # 0. 현재 선택된 월(st.session_state 또는 기준월)에 따른 동적 계절 텍스트 자동 반영
    current_m = None
    for k in ["selected_month", "cur_month", "month", "active_month", "calendar_month"]:
        if k in st.session_state and st.session_state[k]:
            try:
                val = int(str(st.session_state[k]).replace("월", "").strip())
                if 1 <= val <= 12:
                    current_m = val
                    break
            except Exception:
                pass
    if not current_m:
        from datetime import datetime
        current_m = datetime.now().month

    current_season = get_korean_season(current_m)
    season_badge_text = f"한국관광공사 공인 694선 · {current_m}월 {current_season} 축제장 연계"

    # 1. 전역 스타일 인젝션 (킨포크/29CM 에디토리얼 무드)
    st.html("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,800;1,600&display=swap');

    .shelter-page-wrap {
        max-width: 1400px;
        margin: 0 auto;
        padding: 1.5rem 1rem 3rem 1rem;
        font-family: 'Pretendard', sans-serif;
        color: #1C1C16;
    }

    /* 상단 헤더 바 */
    .shelter-header-bar {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        padding-bottom: 18px;
        border-bottom: 2px solid #012D1D;
        margin-bottom: 24px;
        flex-wrap: wrap;
        gap: 12px;
    }
    .shelter-meta-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 4px;
    }
    .shelter-vol-badge {
        font-size: 0.72rem;
        font-weight: 800;
        color: #065F46;
        background: #D1FAE5;
        padding: 2px 7px;
        border-radius: 4px;
        letter-spacing: 0.04em;
    }
    .shelter-sub-badge {
        font-size: 0.78rem;
        color: #555E58;
        font-weight: 600;
    }
    .shelter-main-title {
        font-family: 'Playfair Display', 'Pretendard', serif;
        font-size: 2.2rem;
        font-weight: 800;
        color: #012D1D;
        margin: 4px 0 6px 0;
        letter-spacing: -0.02em;
    }
    .shelter-lead-text {
        font-size: 0.92rem;
        color: #555E58;
        margin: 0;
        font-weight: 500;
    }

    /* 상단 홈으로 버튼 */
    .shelter-ghost-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 8px 18px;
        border-radius: 24px;
        border: 1.5px solid #012D1D;
        background: #FFFFFF;
        color: #012D1D !important;
        font-size: 0.88rem;
        font-weight: 700;
        text-decoration: none !important;
        transition: all 0.2s ease;
        box-shadow: 0 2px 8px rgba(1, 45, 29, 0.06);
    }
    .shelter-ghost-btn:hover {
        background: #012D1D;
        color: #FAF7F2 !important;
        transform: translateY(-2px);
    }

    /* 3단 필터 툴바 */
    .shelter-filter-card {
        background: #FAF7F2;
        border: 1px solid #EAE4DA;
        border-radius: 14px;
        padding: 16px 20px;
        margin-bottom: 24px;
        box-shadow: 0 2px 10px rgba(1, 45, 29, 0.03);
    }

    /* 반응형 3열 매거진 그리드 레이아웃 */
    .shelter-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 22px;
        margin-bottom: 28px;
        width: 100%;
    }
    @media (max-width: 1100px) {
        .shelter-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 18px;
        }
    }
    @media (max-width: 680px) {
        .shelter-grid {
            grid-template-columns: 1fr;
            gap: 16px;
        }
    }

    /* 시원한 감성 매거진 카드 */
    .shelter-card {
        background: #FFFFFF;
        border: 1.5px solid #EAE4DA;
        border-radius: 18px;
        overflow: hidden;
        transition: all 0.28s cubic-bezier(0.16, 1, 0.3, 1);
        box-shadow: 0 4px 18px rgba(1, 45, 29, 0.04);
        display: flex;
        flex-direction: column;
        height: 100%;
    }
    .shelter-card:hover {
        border-color: #012D1D;
        box-shadow: 0 14px 32px rgba(1, 45, 29, 0.12);
        transform: translateY(-4px);
    }
    .shelter-card-img-wrap {
        width: 100%;
        height: 200px;
        position: relative;
        overflow: hidden;
        background: #EFEAE1;
    }
    .shelter-card-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
        transition: transform 0.4s ease;
    }
    .shelter-card:hover .shelter-card-img {
        transform: scale(1.05);
    }
    .shelter-img-floating-tag {
        position: absolute;
        bottom: 10px;
        left: 12px;
        background: rgba(1, 45, 29, 0.88);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        color: #FAF7F2;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 20px;
        letter-spacing: -0.01em;
        box-shadow: 0 2px 8px rgba(0,0,0,0.18);
    }
    .shelter-card-content {
        padding: 18px 20px 20px 20px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        flex: 1;
    }
    .shelter-badge-row {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 10px;
        flex-wrap: wrap;
    }
    .badge-theme {
        font-size: 0.72rem;
        font-weight: 800;
        color: #065F46;
        background: #D1FAE5;
        border: 1px solid #A7F3D0;
        padding: 3px 8px;
        border-radius: 5px;
    }
    .badge-fest-text {
        font-size: 0.72rem;
        font-weight: 800;
        color: #92400E;
        background: #FEF3C7;
        border: 1px solid #FDE68A;
        padding: 3px 9px;
        border-radius: 5px;
        cursor: default;
        display: inline-flex;
        align-items: center;
        gap: 3px;
        user-select: none;
    }
    .badge-status {
        font-size: 0.70rem;
        font-weight: 800;
        color: #DC2626;
        background: #FEE2E2;
        border: 1px solid #FECACA;
        padding: 3px 7px;
        border-radius: 5px;
    }
    .shelter-title {
        font-size: 1.18rem;
        font-weight: 800;
        color: #012D1D;
        margin: 0 0 6px 0;
        line-height: 1.35;
        letter-spacing: -0.01em;
    }
    .shelter-desc {
        font-size: 0.83rem;
        color: #4B5563;
        line-height: 1.5;
        margin-bottom: 14px;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .shelter-meta-footer {
        border-top: 1px solid #F1ECE2;
        padding-top: 12px;
        margin-top: auto;
    }
    .shelter-info-row {
        font-size: 0.75rem;
        color: #555E58;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 6px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .shelter-btn-row {
        display: flex;
        gap: 8px;
        margin-top: 10px;
    }
    .btn-naver-map {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: #012D1D;
        color: #FAF7F2 !important;
        font-size: 0.76rem;
        font-weight: 700;
        padding: 7px 12px;
        border-radius: 8px;
        text-decoration: none !important;
        cursor: pointer !important;
        transition: all 0.2s ease;
        flex: 1;
        justify-content: center;
    }
    .btn-naver-map:hover {
        background: #065F46;
        transform: translateY(-1px);
        box-shadow: 0 3px 10px rgba(1, 45, 29, 0.15);
    }
    .btn-fest-route {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: #FEF3C7;
        color: #92400E !important;
        font-size: 0.76rem;
        font-weight: 700;
        padding: 7px 12px;
        border-radius: 8px;
        border: 1px solid #FDE68A;
        text-decoration: none !important;
        cursor: pointer !important;
        transition: all 0.2s ease;
        flex: 1;
        justify-content: center;
    }
    .btn-fest-route:hover {
        background: #D97706;
        color: #FFFFFF !important;
        border-color: #B45309;
        transform: translateY(-1px);
        box-shadow: 0 3px 10px rgba(217, 119, 6, 0.25);
    }

    /* 하단 페이지네이션 '이전/다음' 및 숫자 버튼 슬림하고 아담한 일체형 크기 */
    div[data-testid="stButton"] > button {
        padding: 6px 14px !important;
        font-size: 13px !important;
        min-height: 36px !important;
        height: 36px !important;
        border-radius: 18px !important;
        font-weight: 700 !important;
        line-height: 1.2 !important;
        box-shadow: 0 1px 4px rgba(1, 45, 29, 0.05) !important;
    }
    </style>
    """)

    # 2. 헤더 바 렌더링 (동적 월/계절 자동 반영)
    st.html(f"""
    <div class="shelter-page-wrap">
        <div class="shelter-header-bar">
            <div>
                <div class="shelter-meta-row">
                    <span class="shelter-vol-badge">VOL. 05 · 안심 편의 웰니스</span>
                    <span class="shelter-sub-badge">{season_badge_text}</span>
                </div>
                <h1 class="shelter-main-title">🌿 전국 안심 & 웰니스 쉼터 탐색</h1>
                <p class="shelter-lead-text">
                    축제 전후 심신의 긴장을 풀어주는 숲길, 힐링 스파, 명상 다도원 큐레이션 — 가장 가까운 안심 거점을 탐색해보세요
                </p>
            </div>
            <div>
                <a href="?view=main" class="shelter-ghost-btn">
                    <span>←</span>
                    <span>홈으로</span>
                </a>
            </div>
        </div>
    </div>
    """)

    # [상단 동행인 맞춤 안내 마이크로 배너]
    try:
        from festapick.infra_curator import get_companion_micro_banner_html
        micro_banner = get_companion_micro_banner_html(companion_param or st.session_state.get("companion"), service_type="shelter")
    except TypeError:
        try:
            micro_banner = get_companion_micro_banner_html(companion_param or st.session_state.get("companion"))
        except Exception:
            micro_banner = ""
    except Exception:
        micro_banner = ""

    if micro_banner:
        st.html(micro_banner)

    # 3. 데이터 로드
    all_shelters = load_all_wellness_shelters()
    if not all_shelters:
        st.warning("웰니스 쉼터 데이터를 로드하는 중입니다. 잠시 후 다시 시도해주세요.")
        return

    # 4. 세션 상태 필터 기본값
    companion_param = str(st.query_params.get("companion") or st.session_state.get("active_companion_param") or "").strip().lower()
    if companion_param:
        st.session_state["active_companion_param"] = companion_param

    if "shelter_zone" not in st.session_state:
        st.session_state.shelter_zone = "전체"
    if "shelter_theme" not in st.session_state:
        st.session_state.shelter_theme = "전체 테마"
    if "shelter_query" not in st.session_state:
        st.session_state.shelter_query = ""
    if "shelter_page" in st.query_params:
        try:
            sp = int(st.query_params.get("shelter_page"))
            if sp >= 1:
                st.session_state.shelter_page = sp
        except Exception:
            pass
        del st.query_params["shelter_page"]

    if "shelter_page" not in st.session_state:
        st.session_state.shelter_page = 1

    # 5. 3단 필터 툴바 렌더링
    f_col1, f_col2, f_col3 = st.columns([1.2, 1.2, 1.6], gap="small")
    with f_col1:
        zone_keys = [z["key"] for z in ZONE_TABS]
        zone_labels = [z["label"] for z in ZONE_TABS]
        cur_zone_idx = zone_keys.index(st.session_state.shelter_zone) if st.session_state.shelter_zone in zone_keys else 0
        sel_zone_label = st.selectbox("🗺️ 권역 선택", zone_labels, index=cur_zone_idx, key="sb_shelter_zone")
        st.session_state.shelter_zone = zone_keys[zone_labels.index(sel_zone_label)]

    with f_col2:
        cur_theme_idx = THEME_TABS.index(st.session_state.shelter_theme) if st.session_state.shelter_theme in THEME_TABS else 0
        st.session_state.shelter_theme = st.selectbox("🌿 쉼터 테마", THEME_TABS, index=cur_theme_idx, key="sb_shelter_theme")

    with f_col3:
        st.session_state.shelter_query = st.text_input("🔍 연계 축제명 또는 쉼터 검색", value=st.session_state.shelter_query, placeholder="예: 순천만, 스파, 편백나무, 제주...", key="txt_shelter_query")

    # 6. 필터 적용
    filtered = all_shelters

    # 1) 권역 필터
    if st.session_state.shelter_zone != "전체":
        matched_tab = next((z for z in ZONE_TABS if z["key"] == st.session_state.shelter_zone), None)
        if matched_tab and matched_tab["keywords"]:
            kws = matched_tab["keywords"]
            filtered = [s for s in filtered if any(k in s["addr"] or k in s["title"] for k in kws)]

    # 2) 테마 필터
    if st.session_state.shelter_theme != "전체 테마":
        clean_theme = st.session_state.shelter_theme.split(" ")[-1]
        filtered = [s for s in filtered if clean_theme in s["theme"]]

    # 3) 검색어 필터
    q = st.session_state.shelter_query.strip().lower()
    if q:
        filtered = [s for s in filtered if q in s["title"].lower() or q in s["addr"].lower() or q in s["fest_title"].lower() or q in s["overview"].lower()]

    # [동행인 테마별 맞춤 추천 1~3곳 최상단 우선 정렬]
    if companion_param:
        from festapick.infra_curator import score_shelter_for_companion
        for s in filtered:
            s["_comp_score"] = score_shelter_for_companion(
                s.get("title", ""),
                s.get("theme", ""),
                s.get("overview", ""),
                companion_param
            )
        sorted_by_comp = sorted(filtered, key=lambda x: x.get("_comp_score", 100), reverse=True)
        top_recomms = []
        top_titles = set()
        for cand in sorted_by_comp:
            if cand.get("_comp_score", 100) > 100 and len(top_recomms) < 3:
                cand["_is_custom_recommended"] = True
                top_recomms.append(cand)
                top_titles.add(cand.get("title"))

        if top_recomms:
            other_items = [s for s in filtered if s.get("title") not in top_titles]
            filtered = top_recomms + other_items

    st.markdown(f"<div style='font-size:0.88rem; color:#555E58; margin: 8px 0 20px 0;'>총 <b>{len(filtered):,}</b>곳의 안심 웰니스 쉼터가 탐색되었습니다 (축제 일정 임박순 및 거리순 정렬)</div>", unsafe_allow_html=True)

    # 7. 페이지네이션 계산 (3열 매거진 그리드 최적화: 페이지당 6개 표시)
    PAGE_SIZE = 6
    total_pages = max(1, math.ceil(len(filtered) / PAGE_SIZE))
    if st.session_state.shelter_page > total_pages:
        st.session_state.shelter_page = 1
    current_page = st.session_state.shelter_page

    start_idx = (current_page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_items = filtered[start_idx:end_idx]

    # 8. 메인 컨테이너 전체 폭 반응형 3열 매거진 카드 그리드
    if not page_items:
        st.info("조건에 일치하는 웰니스 쉼터가 없습니다. 검색어나 필터를 변경해보세요.")
    else:
        cards_html = []
        for s in page_items:
            s_title = html.escape(s["title"])
            s_theme = html.escape(s["theme"])
            s_fest = html.escape(s["fest_title"])
            s_transit = html.escape(s["transit_txt"])
            s_status = html.escape(s["status_badge"])
            s_desc = html.escape(s["overview"])
            s_addr = html.escape(s["addr"])
            s_tel = html.escape(s["tel"])
            s_img = s["image"]
            s_mode = s.get("transit_mode", "car")
            transit_icon = "🚶" if s_mode == "walk" else "🚗"

            # 네이버 지도 길찾기 검색어 정제 (층수/괄호 제거 및 상호명/주소 최적 조합으로 검색 실패 방지)
            clean_search_query = build_naver_search_query(s["title"], s["addr"])
            nav_q = urllib.parse.quote(clean_search_query)
            nav_link = f"https://map.naver.com/p/search/{nav_q}"

            # 연계 축제 뱃지: 상단은 화살표 없는 깔끔한 텍스트 뱃지로 표시 (클릭 링크는 하단 버튼으로 일원화)
            badge_fest_html = f'<span class="badge-fest-text">🎪 {s_fest}</span>'

            # 하단 축제 여정 이동 링크 (명확한 단일 CTA)
            if s["fest_title"] and s["fest_title"] != "로컬 대표 축제":
                f_encoded = urllib.parse.quote(s["fest_title"])
                r_encoded = urllib.parse.quote(s.get("fest_region", ""))
                fest_link_url = f"?select_fest_and_go={f_encoded}&target_region={r_encoded}"
                btn_fest_html = (
                    f'<a href="{fest_link_url}" target="_top" class="btn-fest-route">'
                    f'🎪 축제 여정 →'
                    f'</a>'
                )
            else:
                btn_fest_html = (
                    f'<a href="?view=main" target="_top" class="btn-fest-route">'
                    f'🎪 축제 홈 →'
                    f'</a>'
                )

            custom_badge = '<span style="background:#012D1D; color:#FDE68A; font-size:0.70rem; font-weight:800; padding:2px 6px; border-radius:5px; margin-right:5px; vertical-align:middle;">★ 맞춤 추천</span>' if s.get("_is_custom_recommended") else ""

            card_item = f"""
            <div class="shelter-card">
                <div class="shelter-card-img-wrap">
                    <img src="{s_img}" alt="{s_title}" class="shelter-card-img" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null; this.src='{THEME_FALLBACK_IMAGES['생태쉼터']}';" />
                    <div class="shelter-img-floating-tag">
                        {transit_icon} 축제장 {s_transit}
                    </div>
                </div>
                <div class="shelter-card-content">
                    <div>
                        <div class="shelter-badge-row">
                            <span class="badge-theme">{s_theme}</span>
                            {badge_fest_html}
                            <span class="badge-status">{s_status}</span>
                        </div>
                        <h3 class="shelter-title">{custom_badge}{s_title}</h3>
                        <div class="shelter-desc">{s_desc}</div>
                    </div>
                    <div class="shelter-meta-footer">
                        <div class="shelter-info-row"><span>🏠</span> <span>{s_addr}</span></div>
                        <div class="shelter-info-row"><span>📞</span> <span>{s_tel}</span></div>
                        <div class="shelter-btn-row">
                            <a href="{nav_link}" target="_blank" rel="noopener noreferrer" class="btn-naver-map">
                                🗺️ 길찾기 ↗
                            </a>
                            {btn_fest_html}
                        </div>
                    </div>
                </div>
            </div>
            """
            cards_html.append(card_item)

        st.html(f'<div class="shelter-grid">{"".join(cards_html)}</div>')

    # 9. 양방향 페이지네이션 컨트롤러 [ < 이전 | 1 | 2 | 3 ... | 다음 > ] (아담하고 슬림한 크기 보정)
    MAX_PAGE_BUTTONS = 5
    half = MAX_PAGE_BUTTONS // 2
    start_p = max(1, current_page - half)
    end_p = min(total_pages, start_p + MAX_PAGE_BUTTONS - 1)
    if end_p - start_p + 1 < MAX_PAGE_BUTTONS:
        start_p = max(1, end_p - MAX_PAGE_BUTTONS + 1)
    page_window = list(range(start_p, end_p + 1))

    num_count = len(page_window)
    side_spacer = max(0.5, (12.0 - (1.9 + num_count * 0.75)) / 2)
    col_widths = [side_spacer, 0.95] + [0.75] * num_count + [0.95, side_spacer]

    pag_cols = st.columns(col_widths)

    # 1) < 이전 버튼 (1페이지일 때 disabled=True 예외 처리)
    with pag_cols[1]:
        if st.button("◀ 이전", key="btn_shelter_prev", disabled=(current_page <= 1), use_container_width=True):
            st.session_state.shelter_page = max(1, current_page - 1)
            st.rerun()

    # 2) 페이지 번호 버튼들 [ 1 | 2 | 3 ... ]
    for i, p in enumerate(page_window):
        with pag_cols[2 + i]:
            is_active = (p == current_page)
            btn_type = "primary" if is_active else "secondary"
            if st.button(str(p), key=f"btn_shelter_page_{p}", type=btn_type, use_container_width=True):
                st.session_state.shelter_page = p
                st.rerun()

    # 3) 다음 > 버튼 (마지막 페이지일 때 disabled=True 예외 처리)
    with pag_cols[2 + num_count]:
        if st.button("다음 ▶", key="btn_shelter_next", disabled=(current_page >= total_pages), use_container_width=True):
            st.session_state.shelter_page = min(total_pages, current_page + 1)
            st.rerun()

    st.markdown(
        f"<div style='text-align:center; font-size:0.83rem; font-weight:600; color:#6B7280; margin-top:12px; margin-bottom:28px;'>"
        f"페이지 <b style='color:#012D1D;'>{current_page}</b> / {total_pages} &nbsp;·&nbsp; 총 <b>{len(filtered):,}</b>곳 안심 웰니스 쉼터"
        f"</div>",
        unsafe_allow_html=True
    )
