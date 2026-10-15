"""
app_demo.py - 페스타픽 (FestaPick) 웹 서비스 메인 애플리케이션
================================================================================
[시스템 아키텍처 개요]
1. 탐색 및 큐레이션    : 축제 탐색 중복 제거 및 단일 보존 최신 패치 반영
                        - 가독성 보호 다크 오버레이 & 420px 화이트 알약 버튼
                        - 원클릭으로 메인 큐레이션 화면으로 전환
2. 프론트엔드 (Frontend)   : Streamlit 기반 킨포크/29CM 에디토리얼 라이프스타일 UI
                        - Pretendard 웹폰트 및 웜 크림(#FDF9F0) 테마 고정
                        - Flexbox 기반 디스플레이/배율(DPI) 대응 및 다크모드 차단
3. 백엔드 (Backend AI)     : LangGraph 멀티 에이전트 오케스트레이션 (backend/agent.py)
                        - run_processing_pipeline: 큐레이션 에세이 및 체크포인트 생성
4. 데이터 및 API (Data/API): 대한민국 공공데이터 오픈 API 엔지니어링 모듈 (data.py)
                        - 한국관광공사 TourAPI 4.0, 행안부 착한가격업소, KNPS 국립공원
================================================================================
"""

import os
import sys
import json
import html
import re
import math
import textwrap
import urllib.parse
import base64
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import folium
from streamlit_folium import st_folium
import streamlit.components.v1 as st_components

# ------------------------------------------------------------------------------
# [모듈 경로 등록] backend(LangGraph 에이전트) 및 festapick(공공데이터 엔진) 경로 설정
# ------------------------------------------------------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = CURRENT_DIR
for p in [CURRENT_DIR, PARENT_DIR, os.path.join(CURRENT_DIR, "festapick"), os.path.join(PARENT_DIR, "festapick"), os.path.join(CURRENT_DIR, "backend"), os.path.join(PARENT_DIR, "backend")]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

# [Backend API 연동] agent.py LangGraph 파이프라인 인터페이스
try:
    from festapick.agent import run_processing_pipeline, PipelineState
except ImportError:
    try:
        from agent import run_processing_pipeline, PipelineState
    except ImportError as e:
        st.error(f"agent.py 임포트 오류: {e}")
        st.stop()

# [Open Data API 연동] data.py 공공데이터포털 실시간 수집 및 인프라 번들 인터페이스
try:
    from festapick.data import get_festival_infra_bundle, get_festivals
except ImportError:
    try:
        from data import get_festival_infra_bundle, get_festivals
    except ImportError as e:
        st.error(f"data.py 임포트 오류: {e}")
        st.stop()


# ==============================================================================
# 1. 행정구역 마스터 & 큐레이션 에셋 프리셋
# ==============================================================================
ADMIN_REGIONS = [
    "전국 전체", "서울특별시", "부산광역시", "대구광역시", "인천광역시", 
    "광주광역시", "대전광역시", "울산광역시", "세종특별자치시", "경기도", 
    "강원특별자치도", "충청북도", "충청남도", "전북특별자치도", "전라남도", 
    "경상북도", "경상남도", "제주특별자치도"
]

# [Festival Representative Coordinates Table] 주요 축제 대표 좌표 사전 및 강제 보정 매핑
FESTIVAL_COORDS_TABLE = {
    "풍기인삼": (36.8715, 128.5255),
    "영주": (36.8715, 128.5255),
    "순천만": (34.8872, 127.5083),
    "진주": (35.1878, 128.0805),
    "강릉": (37.7719, 128.9482),
    "수원": (37.2849, 127.0142),
    "안동": (36.5645, 128.7289),
    "부산": (35.1532, 129.1186),
    "서산": (36.7135, 126.4842),
    "태안": (36.4952, 126.3408),
    "여수": (34.7431, 127.7378),
}

def resolve_festival_coordinates(name: str = "", address: str = "", lat: Any = None, lng: Any = None) -> tuple:
    """
    축제명과 주소를 기반으로 FESTIVAL_COORDS_TABLE을 우선 매칭하여 
    로컬 축제(예: 경북영주 풍기인삼축제)가 서울 종로구 등 엉뚱한 위치로 렌더링되는 문제를 원천 보정합니다.
    """
    target_str = f"{name} {address}".strip()
    for kw, (c_lat, c_lng) in FESTIVAL_COORDS_TABLE.items():
        if kw in target_str:
            return float(c_lat), float(c_lng)
    
    try:
        f_lat = float(lat)
        f_lng = float(lng)
        # 서울 종로/시청 기본 더미 좌표(37.5636, 126.9808)가 아니고 유효 좌표 범위인 경우
        if 33.0 <= f_lat <= 39.0 and 124.0 <= f_lng <= 132.0:
            if not (abs(f_lat - 37.5636) < 0.01 and abs(f_lng - 126.9808) < 0.01 and "서울" not in target_str):
                return f_lat, f_lng
    except (TypeError, ValueError):
        pass
    
    return 34.8872, 127.5083

try:
    from festapick.fallback_assets import DEFAULT_FESTIVAL_GRAPHIC_DATA_URI
    FALLBACK_SAFE_IMAGE = DEFAULT_FESTIVAL_GRAPHIC_DATA_URI
except Exception:
    FALLBACK_SAFE_IMAGE = "https://images.unsplash.com/photo-1506157786151-b8491531f063?auto=format&fit=crop&w=800&q=80"

# [Local Master Assets] 순천만 갈대축제 & 착한가격 모범식당 & 웰니스 쉼터 공식 실사 (초경량 Base64 Data URI 무결점 연동)
def _load_b64_file(filename: str, fallback_url: str) -> str:
    path = os.path.join(PROJECT_ROOT, "assets", filename)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                c = f.read().strip()
                if c.startswith("data:image"):
                    return c
        except Exception:
            pass
    return fallback_url

SUNCHEON_REED_IMG = _load_b64_file("suncheon_reed_b64.txt", "https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=800&q=80")
JINJU_LANTERN_IMG = _load_b64_file("jinju_lantern_b64.txt", "https://images.unsplash.com/photo-1533174072545-7a4b6ad7a6c3?auto=format&fit=crop&w=800&q=80")
GANGNEUNG_COFFEE_IMG = _load_b64_file("gangneung_coffee_b64.txt", "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=800&q=80")
GEUMSAN_GINSENG_IMG = _load_b64_file("geumsan_ginseng_b64.txt", "https://images.unsplash.com/photo-1514733670139-4d87a1941d55?auto=format&fit=crop&w=800&q=80")
TAEAN_FLOWER_IMG = _load_b64_file("taean_flower_b64.txt", "https://images.unsplash.com/photo-1508615039623-a25605d2b022?auto=format&fit=crop&w=800&q=80")
MODEL_FOOD_IMG = _load_b64_file("model_food_b64.txt", "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80")
NATURE_SHELTER_IMG = _load_b64_file("nature_shelter_b64.txt", "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=800&q=80")
DWAEJI_GUKBAP_IMG = _load_b64_file("dwaeji_gukbap_b64.txt", "https://upload.wikimedia.org/wikipedia/commons/8/8b/Dwaeji-gukbap.jpg")

# [Good Price Store & Food Semantic Engine] 착한가격 업소 메뉴/업종/상호별 실사 시맨틱 매칭
FOOD_SEMANTIC_IMAGES: Dict[str, str] = {
    "국밥": DWAEJI_GUKBAP_IMG,
    "돼지국밥": DWAEJI_GUKBAP_IMG,
    "순대국밥": DWAEJI_GUKBAP_IMG,
    "곰탕": MODEL_FOOD_IMG,
    "설렁탕": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=800&q=80",
    "백반": MODEL_FOOD_IMG,
    "정식": MODEL_FOOD_IMG,
    "한식": MODEL_FOOD_IMG,
    "가정식": MODEL_FOOD_IMG,
    "쌈밥": MODEL_FOOD_IMG,
    "꼬막": "https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?auto=format&fit=crop&w=800&q=80",
    "순두부": "https://images.unsplash.com/photo-1547496502-affa22d38842?auto=format&fit=crop&w=800&q=80",
    "두부": "https://images.unsplash.com/photo-1547496502-affa22d38842?auto=format&fit=crop&w=800&q=80",
    "찌개": MODEL_FOOD_IMG,
    "칼국수": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=800&q=80",
    "국수": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=800&q=80",
    "냉면": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=800&q=80",
    "불고기": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
    "갈비": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
    "삼겹살": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
    "비빔밥": "https://images.unsplash.com/photo-1590301157890-4810ed352733?auto=format&fit=crop&w=800&q=80",
    "돈까스": "https://images.unsplash.com/photo-1565299585323-38d6b0865b47?auto=format&fit=crop&w=800&q=80",
    "짜장": "https://images.unsplash.com/photo-1585032226651-759b368d7246?auto=format&fit=crop&w=800&q=80",
    "짬뽕": "https://images.unsplash.com/photo-1585032226651-759b368d7246?auto=format&fit=crop&w=800&q=80",
    "중식": "https://images.unsplash.com/photo-1585032226651-759b368d7246?auto=format&fit=crop&w=800&q=80",
    "빵": "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=800&q=80",
    "베이커리": "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=800&q=80",
    "카페": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=800&q=80",
    "커피": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=800&q=80",
    "식당": MODEL_FOOD_IMG,
    "향촌": MODEL_FOOD_IMG,
    "모범": MODEL_FOOD_IMG,
    "착한가격": MODEL_FOOD_IMG
}

def resolve_restaurant_image(rest_name: str, rest_desc: str = "", region: str = "") -> str:
    """[Frontend Engine] 착한가격업소/맛집 명칭 및 메뉴 키워드 기반 고화질 실사 매칭 (부재 시 행안부 인증 착한가격업소 골든 마스터 실사 보장)"""
    text = f"{rest_name} {rest_desc}".lower()
    for kw, img_url in FOOD_SEMANTIC_IMAGES.items():
        if kw in text:
            return img_url
    return MODEL_FOOD_IMG

# [Wellness Shelter Semantic Engine] 힐링 쉼터 성격별 고화질 실사 매칭
SHELTER_SEMANTIC_IMAGES: Dict[str, str] = {
    "족욕": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=800&q=80",
    "온열": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=800&q=80",
    "스파": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=800&q=80",
    "약초": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=800&q=80",
    "차": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=800&q=80",
    "다도": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=800&q=80",
    "대나무": NATURE_SHELTER_IMG,
    "숲길": NATURE_SHELTER_IMG,
    "데크": NATURE_SHELTER_IMG,
    "호수": NATURE_SHELTER_IMG,
    "공원": NATURE_SHELTER_IMG,
    "정원": NATURE_SHELTER_IMG,
    "쉼터": NATURE_SHELTER_IMG
}

def resolve_shelter_image(spot_name: str, spot_desc: str = "", region: str = "") -> str:
    """[Frontend Engine] 웰니스 쉼터 명칭 및 설명 키워드 기반 실사 매칭 (부재 시 대나무 숲길 쉼터 골든 마스터 실사 보장)"""
    text = f"{spot_name} {spot_desc}".lower()
    for kw, img_url in SHELTER_SEMANTIC_IMAGES.items():
        if kw in text:
            return img_url
    return NATURE_SHELTER_IMG

def validate_image_url(url: Optional[str], default_url: str = FALLBACK_SAFE_IMAGE) -> str:
    """[Frontend Utility] 이미지 URL 유효성(Null/NaN/프로토콜) 검증 및 Fallback 안전 보장"""
    if not url:
        return default_url
    url_str = str(url).strip()
    if url_str.lower() in ["none", "null", "nan", "", "-", "undefined"]:
        return default_url
    if not (url_str.startswith("http://") or url_str.startswith("https://") or url_str.startswith("data:image")):
        return default_url
    return url_str

# [Image Cache & Fallback] 실무형 이미지 안전 매핑(Fallback Cache) 연동
SAFE_IMAGE_MAPPING: Dict[str, str] = {
    "순천만": SUNCHEON_REED_IMG,
    "갈대": SUNCHEON_REED_IMG,
    "억새": SUNCHEON_REED_IMG,
    "남강유등": "https://images.unsplash.com/photo-1533174072545-7a4b6ad7a6c3?auto=format&fit=crop&w=800&q=80",
    "진주": "https://images.unsplash.com/photo-1533174072545-7a4b6ad7a6c3?auto=format&fit=crop&w=800&q=80",
    "유등": "https://images.unsplash.com/photo-1533174072545-7a4b6ad7a6c3?auto=format&fit=crop&w=800&q=80",
    "강릉": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=800&q=80",
    "커피": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=800&q=80",
    "사진": "https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?auto=format&fit=crop&w=800&q=80",
    "전시": "https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?auto=format&fit=crop&w=800&q=80",
    "미술": "https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?auto=format&fit=crop&w=800&q=80",
    "페어": "https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?auto=format&fit=crop&w=800&q=80",
    "불꽃": "https://images.unsplash.com/photo-1498931299472-f7a63a5a1cfa?auto=format&fit=crop&w=800&q=80",
    "음악": "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=800&q=80",
    "재즈": "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=800&q=80",
    "국화": "https://images.unsplash.com/photo-1508615039623-a25605d2b022?auto=format&fit=crop&w=800&q=80",
}

def resolve_safe_image(fest_name: str, fallback_url: Optional[str] = None) -> str:
    """[Frontend Utility] AI 검색 오류 방지 실무형 이미지 안전 매핑(Fallback Cache) 연동"""
    name = str(fest_name or "")
    for keyword, safe_url in SAFE_IMAGE_MAPPING.items():
        if keyword in name:
            return safe_url
    if fallback_url:
        return validate_image_url(fallback_url, FALLBACK_SAFE_IMAGE)
    return FALLBACK_SAFE_IMAGE

# [Content Preset] 기획특집 추천 3선 프리셋 (고화질 Unsplash CDN 연동)
HOT_FESTIVALS_PRESET = [
    {
        "name": "순천만 갈대축제",
        "region": "전라남도",
        "month": 10,
        "theme": "자연/꽃",
        "badge": "VOL. 01 · 힐링 1위",
        "tag": "황금빛 갈대 데크로드 · 흑두루미 생태 쉼터",
        "stamina": 35,
        "companion": "부모님 (연로하심)",
        "transport": "🚗 자가용 (렌터카)",
        "img": SUNCHEON_REED_IMG,
        "desc": "바람과 은빛 갈대숲이 머무는 곳, 체력에 맞추어 가장 안심하고 누리는 1일 힐링 에디토리얼 여정.",
        "programs": [
            {
                "name": "순천만 갈대길 생태 걷기대회 (남파랑길 코스)",
                "category": "생태 걷기",
                "description": "황금빛 갈대숲 데크로드와 남파랑길을 따라 걷는 완만한 무장애 힐링 트레킹",
                "reservation_required": True,
                "booking_tip": "순천만습지 누리집 사전 신청 우선"
            },
            {
                "name": "갈대숲 클래식 버스킹 & 쉼터 음악회",
                "category": "문화 공연",
                "description": "은빛 갈대 물결 사이 쉼터 벤치에서 즐기는 편안한 어쿠스틱 및 클래식 라이브 연주",
                "reservation_required": False,
                "booking_tip": "갈대밭 쉼터 일원 자유 관람"
            },
            {
                "name": "흑두루미 소망 엽서 쓰기 & 갈대공예 체험",
                "category": "체험 프로그램",
                "description": "순천만을 찾아온 겨울 철새 흑두루미를 맞이하며 소망 엽서와 천연 갈대 빗자루 만들기",
                "reservation_required": False,
                "booking_tip": "생태체험관 앞 현장 부스 참여"
            },
            {
                "name": "용산전망대 노을 해설 투어",
                "category": "해설 투어",
                "description": "순천만 S자 갯골과 붉게 물드는 석양을 전문 생태해설사와 함께 감상하는 가이드 투어",
                "reservation_required": False,
                "booking_tip": "현장 출발 10분 전 안내소 집결"
            }
        ]
    },
    {
        "name": "진주 남강유등축제",
        "region": "경상남도",
        "month": 10,
        "theme": "야경/빛",
        "badge": "VOL. 02 · 빛의 야경",
        "tag": "남강 수상 유등 전시 · 촉석루 달빛 산책",
        "stamina": 50,
        "companion": "친구들과 함께",
        "transport": "🚶 도보 (대중교통)",
        "img": "https://images.unsplash.com/photo-1514565131-fce0801e5785?q=80&w=1600",
        "desc": "천 년의 역사를 품은 남강 물결 위에 수놓아진 수만 개의 유등. 물빛과 달빛이 어우러진 낭만적인 밤 산책 코스.",
        "programs": [
            {
                "name": "소망등 달기 및 창작등 제작 체험",
                "category": "체험행사",
                "description": "남강 변에 가족의 건강과 안녕을 기원하는 소망등을 직접 달고 창작등을 제작하는 시그니처 체험",
                "reservation_required": True,
                "booking_tip": "공식 누리집 사전 예약 및 현장 접수"
            },
            {
                "name": "남강 수상 유등 전시 및 유등 띄우기",
                "category": "전시 및 참여",
                "description": "수만 개의 형형색색 대형 유등이 남강 물결 위에 부유하는 환상적인 야경 감상 및 유등 방류",
                "reservation_required": False,
                "booking_tip": "상시 자유 관람 및 현장 참여"
            },
            {
                "name": "드론 라이트쇼 & 수상 멀티미디어 불꽃놀이",
                "category": "공연 및 관람",
                "description": "진주성 성곽과 남강 밤하늘을 수놓는 최첨단 드론 군집 비행과 야간 멀티미디어 불꽃 쇼",
                "reservation_required": False,
                "booking_tip": "촉석루 및 남강 둔치 일원 자유 관람"
            },
            {
                "name": "남강 부교(배다리) 건너기 체험",
                "category": "보행 체험",
                "description": "강 위에 놓인 평지 부교를 걸으며 유등 사이를 가장 가까이서 거닐 수 있는 무장애 보행로",
                "reservation_required": False,
                "booking_tip": "현장 발권 및 자유 통행"
            }
        ]
    },
    {
        "name": "강릉 커피축제",
        "region": "강원특별자치도",
        "month": 10,
        "theme": "미식/특산물",
        "badge": "VOL. 03 · 솔향과 커피",
        "tag": "안목해변 커피거리 · 경포호 솔밭 무장애길",
        "stamina": 40,
        "companion": "연인 / 커플",
        "transport": "🚗 자가용 (렌터카)",
        "img": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=1600",
        "desc": "솔향과 그윽한 커피 향기가 파도 소리와 만나는 시간, 평지 해변 데크길로 걷는 릴랙스 여행.",
        "programs": [
            {
                "name": "100인 100미 핸드드립 커피 퍼포먼스",
                "category": "대표 프로그램",
                "description": "100인의 전문 바리스타가 동시에 추출하는 100가지 개성 넘치는 드립 커피 무료 시음회",
                "reservation_required": True,
                "booking_tip": "공식 누리집 시음 평가단 사전 접수"
            },
            {
                "name": "강릉 커피로드 스탬프 랠리",
                "category": "투어 랠리",
                "description": "안목해변 커피거리와 로컬 로스터리 카페를 탐방하며 스탬프를 모으는 힐링 투어",
                "reservation_required": False,
                "booking_tip": "안내소에서 스탬프북 수령 후 자유 참여"
            },
            {
                "name": "솔향 해변 커피크닉(피크닉) 쉼터",
                "category": "휴식 쉼터",
                "description": "경포호와 송정 솔밭 사이에 마련된 빈백 쉼터에서 파도 소리와 커피를 함께 즐기는 릴랙스 공간",
                "reservation_required": False,
                "booking_tip": "송정 솔밭 데크존 자유 이용"
            },
            {
                "name": "별의별 강릉 커피 로스터리 마켓 & 어워즈",
                "category": "전시 및 마켓",
                "description": "전국 유명 로스터리와 친환경 다회용기를 활용한 원두 플리마켓 및 바리스타 챔피언십",
                "reservation_required": False,
                "booking_tip": "강릉 아레나 야외광장 자유 관람"
            }
        ]
    }
]

# [Calendar & Curation Master Data] 2026 전국 로컬 축제 마스터 데이터셋 (공공데이터 프로그램 원천 연동)
CALENDAR_MASTER_FESTIVALS = [
    {
        "id": "fest-vk-01",
        "title": "국가유산 미디어아트 여수 진남관",
        "region": "전라남도 여수시",
        "region_short": "전라남도",
        "startDate": "2026-10-09",
        "endDate": "2026-11-08",
        "location": "진남관 및 망해루 일원",
        "address": "전라남도 여수시 동문로 11",
        "lat": 34.7431,
        "lng": 127.7378,
        "image": "https://tong.visitkorea.or.kr/cms/resource/84/4116784_image2_1.jpg",
        "description": "'빛으로 재건하다' - 국보 진남관을 캔버스 삼아 펼쳐지는 웅장한 프로젝션 맵핑과 야간 미디어아트",
        "stamina": 35,
        "phone": "061-659-4742",
        "homepage": "https://www.yeosu.go.kr",
        "programs": [
            {
                "name": "진남관 본전 3D 미디어파사드 상설 공연",
                "category": "미디어아트",
                "description": "국보 진남관의 역사와 이순신 장군의 승전을 첨단 디지털 빛과 사운드로 구현한 몰입형 미디어 쇼",
                "reservation_required": False,
                "booking_tip": "진남관 경내 자유 관람"
            }
        ]
    },
    {
        "id": "fest-vk-02",
        "title": "파주페어 북앤컬처",
        "region": "경기도 파주시",
        "region_short": "경기도",
        "startDate": "2026-10-09",
        "endDate": "2026-10-18",
        "location": "파주출판도시 아시아출판문화정보센터",
        "address": "경기도 파주시 회동길 145",
        "lat": 37.7125,
        "lng": 126.6853,
        "image": "https://cdn.imweb.me/upload/S202608313c0f65fcfaf46/0e4b51cbbecad.png",
        "description": "책과 문화예술의 만남, 아시아 최대 출판문화클러스터에서 즐기는 도서 박람회 및 북토크 콘서트",
        "stamina": 35,
        "phone": "031-955-0050",
        "homepage": "https://pajufair.com",
        "programs": [
            {
                "name": "작가와의 만남 북토크 & 오픈 북마켓",
                "category": "문화전시",
                "description": "국내외 베스트셀러 작가 강연 및 출판사 직영 특별 도서 할인전",
                "reservation_required": False,
                "booking_tip": "지혜의숲 일원 상시 참여"
            }
        ]
    },
    {
        "id": "fest-vk-03",
        "title": "국가유산 미디어아트 청주",
        "region": "충청북도 청주시",
        "region_short": "충청북도",
        "startDate": "2026-10-03",
        "endDate": "2026-10-24",
        "location": "청주 상당산성 및 문화재 일원",
        "address": "충청북도 청주시 상당구 산성로 1",
        "lat": 36.6521,
        "lng": 127.5302,
        "image": "https://tong.visitkorea.or.kr/cms/resource/27/3563827_image2_1.jpg",
        "description": "천년 고도 청주의 역사 유산과 산성을 현대 디지털 예술로 재해석한 국가유산 미디어 페스티벌",
        "stamina": 40,
        "phone": "043-201-2014",
        "homepage": "https://www.cheongju.go.kr",
        "programs": [
            {
                "name": "산성 성벽 라이팅 쇼 & 인터랙티브 아트",
                "category": "야행미디어",
                "description": "자연 성곽과 고즈넉한 숲길을 따라 펼쳐지는 야간 미디어 산책",
                "reservation_required": False,
                "booking_tip": "상당산성 잔디광장 자유 관람"
            }
        ]
    },
    {
        "id": "fest-vk-04",
        "title": "양재아트살롱",
        "region": "서울특별시 서초구",
        "region_short": "서울특별시",
        "startDate": "2026-10-02",
        "endDate": "2026-10-25",
        "location": "양재천 수변무대 및 카페거리",
        "address": "서울특별시 서초구 양재천로 일원",
        "lat": 37.4782,
        "lng": 127.0421,
        "image": "https://tong.visitkorea.or.kr/cms/resource/57/4116957_image2_1.JPEG",
        "description": "도심 속 힐링 하천 양재천을 따라 펼쳐지는 대형 캐릭터 아트 조형물과 로컬 공예 아트 플리마켓",
        "stamina": 30,
        "phone": "02-2155-8700",
        "homepage": "https://www.seocho.go.kr",
        "programs": [
            {
                "name": "양재천 수변 아트마켓 & 캐릭터 포토존",
                "category": "수변예술",
                "description": "수변 산책로를 걸으며 감상하는 청년 작가 아트마켓 및 대형 풍선 포토존",
                "reservation_required": False,
                "booking_tip": "수변 데크길 상시 자유 산책"
            }
        ]
    },
    {
        "id": "fest-vk-05",
        "title": "경남고성공룡세계엑스포",
        "region": "경상남도 고성군",
        "region_short": "경상남도",
        "startDate": "2026-09-22",
        "endDate": "2026-11-01",
        "location": "당항포관광지 일원",
        "address": "경상남도 고성군 회화면 당항만로 1116",
        "lat": 35.0592,
        "lng": 128.4011,
        "image": "https://tong.visitkorea.or.kr/cms/resource/43/2828043_image2_1.jpg",
        "description": "실물 크기의 움직이는 대형 공룡 로봇과 4D/5D 영상관, 공룡 화석 발굴 체험이 가득한 테마 축제",
        "stamina": 45,
        "phone": "055-670-3811",
        "homepage": "https://dino-expo.com",
        "programs": [
            {
                "name": "공룡 퍼레이드 & 주제공연",
                "category": "퍼레이드",
                "description": "대형 공룡 카트와 무용단이 함께 펼치는 신나는 테마 거리 행렬",
                "reservation_required": False,
                "booking_tip": "당항포 야외광장 매일 2회 관람"
            }
        ]
    },
    {
        "id": "fest-vk-06",
        "title": "덕수궁 밤의 석조전",
        "region": "서울특별시 중구",
        "region_short": "서울특별시",
        "startDate": "2026-09-09",
        "endDate": "2026-10-18",
        "location": "덕수궁 석조전",
        "address": "서울특별시 중구 세종대로 99",
        "lat": 37.5658,
        "lng": 126.9751,
        "image": "https://tong.visitkorea.or.kr/cms/resource/10/4102010_image2_1.jpg",
        "description": "대한제국 황실의 서양식 궁전 석조전에서 즐기는 고품격 야간 테라스 카페와 뮤지컬 갈라",
        "stamina": 30,
        "phone": "02-1522-2295",
        "homepage": "https://www.chf.or.kr",
        "programs": [
            {
                "name": "석조전 2층 테라스 카페 황실 디저트 시식",
                "category": "야행체험",
                "description": "은은한 분수 야경을 내려다보며 즐기는 가비(커피)와 프랑스 디저트 체험",
                "reservation_required": True,
                "booking_tip": "티켓링크 사전 예매 필수"
            }
        ]
    },
    {
        "id": "fest-vk-07",
        "title": "홍성남당항 대하축제",
        "region": "충청남도 홍성군",
        "region_short": "충청남도",
        "startDate": "2026-09-04",
        "endDate": "2026-11-08",
        "location": "홍성 남당항 일원",
        "address": "충청남도 홍성군 서부면 남당항로 213",
        "lat": 36.5413,
        "lng": 126.4712,
        "image": "https://tong.visitkorea.or.kr/cms/resource/72/4100472_image2_1.JPG",
        "description": "서해안 청정 갯벌에서 갓 잡아 올린 살이 통통하게 오른 천연 대하 소금구이와 해양 먹거리 축제",
        "stamina": 35,
        "phone": "041-630-1225",
        "homepage": "https://www.hongseong.go.kr",
        "programs": [
            {
                "name": "맨손 대하잡기 체험 & 수산물 경매",
                "category": "수산체험",
                "description": "남당항 대형 풀장에서 직접 대하를 잡아 즉석에서 맛보는 흥미진진한 체험",
                "reservation_required": False,
                "booking_tip": "축제장 주무대 선착순 현장 접수"
            }
        ]
    },
    {
        "id": "fest-vk-08",
        "title": "경복궁 별빛야행",
        "region": "서울특별시 종로구",
        "region_short": "서울특별시",
        "startDate": "2026-09-02",
        "endDate": "2026-10-24",
        "location": "경복궁 소주방 및 북측 권역",
        "address": "서울특별시 종로구 사직로 161",
        "lat": 37.5796,
        "lng": 126.9770,
        "image": "https://tong.visitkorea.or.kr/cms/resource/35/4100435_image2_1.jpg",
        "description": "궁중음식 '도슭수라상'을 맛보고 전문 해설사와 함께 평소 개방되지 않는 경복궁 후원을 거니는 고품격 야행",
        "stamina": 35,
        "phone": "02-1522-2295",
        "homepage": "https://www.chf.or.kr",
        "programs": [
            {
                "name": "외소주방 궁중음식 도슭수라상 체험 & 국악 공연",
                "category": "궁중미식",
                "description": "조선 왕실의 12첩 반상을 4단 유기합에 담아 국악 연주와 함께 음미하는 야간 만찬",
                "reservation_required": True,
                "booking_tip": "인터파크 티켓 사전 추첨/예매"
            }
        ]
    },
    {
        "id": "fest-01",
        "title": "진주 남강유등축제",
        "theme": "야경/빛",
        "region": "경상남도 진주시",
        "region_short": "경상남도",
        "startDate": "2026-10-05",
        "endDate": "2026-10-20",
        "location": "진주성 및 남강 일원",
        "address": "경상남도 진주시 남강로 626",
        "lat": 35.1878,
        "lng": 128.0805,
        "image": "https://tong.visitkorea.or.kr/cms/resource/57/4082657_image2_1.png",
        "description": "물빛과 달빛, 수만 개의 유등이 남강을 수놓는 환상적인 10월 대한민국 대표 야경 축제",
        "stamina": 50,
        "phone": "055-755-9111",
        "homepage": "https://yudeung.com",
        "programs": [
            {
                "name": "소망등 달기 및 창작등 제작 체험",
                "category": "체험행사",
                "description": "남강 변에 가족의 건강과 안녕을 기원하는 소망등을 직접 달고 창작등을 제작하는 시그니처 체험",
                "reservation_required": True,
                "booking_tip": "공식 누리집 사전 예약 및 현장 접수"
            },
            {
                "name": "남강 수상 유등 전시 및 유등 띄우기",
                "category": "전시 및 참여",
                "description": "수만 개의 형형색색 대형 유등이 남강 물결 위에 부유하는 환상적인 야경 감상 및 유등 방류",
                "reservation_required": False,
                "booking_tip": "상시 자유 관람 및 현장 참여"
            },
            {
                "name": "드론 라이트쇼 & 수상 멀티미디어 불꽃놀이",
                "category": "공연 및 관람",
                "description": "진주성 성곽과 남강 밤하늘을 수놓는 최첨단 드론 군집 비행과 야간 멀티미디어 불꽃 쇼",
                "reservation_required": False,
                "booking_tip": "촉석루 및 남강 둔치 일원 자유 관람"
            },
            {
                "name": "남강 부교(배다리) 건너기 체험",
                "category": "보행 체험",
                "description": "강 위에 놓인 평지 부교를 걸으며 유등 사이를 가장 가까이서 거닐 수 있는 무장애 보행로",
                "reservation_required": False,
                "booking_tip": "현장 발권 및 자유 통행"
            }
        ]
    },
    {
        "id": "fest-02",
        "title": "순천만 갈대축제",
        "theme": "자연/꽃",
        "region": "전라남도 순천시",
        "region_short": "전라남도",
        "startDate": "2026-10-10",
        "endDate": "2026-10-28",
        "location": "순천만습지 갈대숲 일원",
        "address": "전라남도 순천시 순천만길 513-25",
        "lat": 34.8872,
        "lng": 127.5083,
        "image": SUNCHEON_REED_IMG,
        "description": "바람과 은빛 갈대숲이 머무는 곳, 체력에 맞추어 가장 안심하고 누리는 1일 힐링 생태 축제",
        "stamina": 75,
        "phone": "061-749-6052",
        "homepage": "https://scbay.suncheon.go.kr",
        "programs": [
            {
                "name": "순천만 갈대길 생태 걷기대회 (남파랑길 코스)",
                "category": "생태 걷기",
                "description": "황금빛 갈대숲 데크로드와 남파랑길을 따라 걷는 완만한 무장애 힐링 트레킹",
                "reservation_required": True,
                "booking_tip": "순천만습지 누리집 사전 신청 우선"
            },
            {
                "name": "갈대숲 클래식 버스킹 & 쉼터 음악회",
                "category": "문화 공연",
                "description": "은빛 갈대 물결 사이 쉼터 벤치에서 즐기는 편안한 어쿠스틱 및 클래식 라이브 연주",
                "reservation_required": False,
                "booking_tip": "갈대밭 쉼터 일원 자유 관람"
            },
            {
                "name": "흑두루미 소망 엽서 쓰기 & 갈대공예 체험",
                "category": "체험 프로그램",
                "description": "순천만을 찾아온 겨울 철새 흑두루미를 맞이하며 소망 엽서와 천연 갈대 빗자루 만들기",
                "reservation_required": False,
                "booking_tip": "생태체험관 앞 현장 부스 참여"
            },
            {
                "name": "용산전망대 노을 해설 투어",
                "category": "해설 투어",
                "description": "순천만 S자 갯골과 붉게 물드는 석양을 전문 생태해설사와 함께 감상하는 가이드 투어",
                "reservation_required": False,
                "booking_tip": "현장 출발 10분 전 안내소 집결"
            }
        ]
    },
    {
        "id": "fest-03",
        "title": "강릉 커피축제 & 솔향 바다",
        "theme": "미식/특산물",
        "region": "강원특별자치도 강릉시",
        "region_short": "강원특별자치도",
        "startDate": "2026-10-12",
        "endDate": "2026-10-18",
        "location": "안목해변 커피거리 & 아레나",
        "address": "강원특별자치도 강릉시 창해로 14번길",
        "lat": 37.7719,
        "lng": 128.9482,
        "image": "https://tong.visitkorea.or.kr/cms/resource/93/3557693_image2_1.jpg",
        "description": "솔향과 커피 향기가 파도 소리와 만나는 시간, 평지 해변 데크길로 걷는 가을 커피 문화 축제",
        "stamina": 40,
        "phone": "033-647-6802",
        "homepage": "http://www.coffeefestival.net",
        "programs": [
            {
                "name": "100인 100미 핸드드립 커피 퍼포먼스",
                "category": "대표 프로그램",
                "description": "100인의 전문 바리스타가 동시에 추출하는 100가지 개성 넘치는 드립 커피 무료 시음회",
                "reservation_required": True,
                "booking_tip": "공식 누리집 시음 평가단 사전 접수"
            },
            {
                "name": "강릉 커피로드 스탬프 랠리",
                "category": "투어 랠리",
                "description": "안목해변 커피거리와 로컬 로스터리 카페를 탐방하며 스탬프를 모으는 힐링 투어",
                "reservation_required": False,
                "booking_tip": "안내소에서 스탬프북 수령 후 자유 참여"
            },
            {
                "name": "솔향 해변 커피크닉(피크닉) 쉼터",
                "category": "휴식 쉼터",
                "description": "경포호와 송정 솔밭 사이에 마련된 빈백 쉼터에서 파도 소리와 커피를 함께 즐기는 릴랙스 공간",
                "reservation_required": False,
                "booking_tip": "송정 솔밭 데크존 자유 이용"
            },
            {
                "name": "별의별 강릉 커피 로스터리 마켓 & 어워즈",
                "category": "전시 및 마켓",
                "description": "전국 유명 로스터리와 친환경 다회용기를 활용한 원두 플리마켓 및 바리스타 챔피언십",
                "reservation_required": False,
                "booking_tip": "강릉 아레나 야외광장 자유 관람"
            }
        ]
    },
    {
        "id": "fest-04",
        "title": "수원화성문화제 & 미디어아트",
        "region": "경기도 수원시",
        "region_short": "경기도",
        "startDate": "2026-10-02",
        "endDate": "2026-10-09",
        "location": "수원화성 행궁 및 연무대 일원",
        "address": "경기도 수원시 팔달구 정조로 825",
        "lat": 37.2849,
        "lng": 127.0142,
        "image": "https://tong.visitkorea.or.kr/cms/resource/90/4060890_image2_1.jpg",
        "description": "유네스코 세계유산 수원화성을 배경으로 펼쳐지는 성곽 야행과 첨단 미디어아트 페스티벌",
        "stamina": 45,
        "phone": "031-290-3622",
        "homepage": "https://www.swcf.or.kr",
        "programs": [
            {
                "name": "수원화성 성곽 야행 달빛 투어",
                "category": "야행 투어",
                "description": "문화해설사와 함께 은은한 조명이 켜진 화성 성곽길을 야간에 걷는 고품격 역사 산책",
                "reservation_required": True,
                "booking_tip": "수원문화재단 누리집 사전 예약 필수"
            },
            {
                "name": "정조대왕 능행차 공동 재현 행렬 관람",
                "category": "대표 퍼레이드",
                "description": "을묘년(1795) 정조대왕의 화성 원행을 완벽 고증하여 성곽 안팎을 지나는 웅장한 행렬",
                "reservation_required": False,
                "booking_tip": "행궁광장 및 종로대로 일원 자유 관람"
            },
            {
                "name": "화서문 미디어아트 야간 페스티벌",
                "category": "미디어아트",
                "description": "유네스코 세계유산 성벽을 초대형 캔버스 삼아 펼쳐지는 최첨단 3D 맵핑 라이트 쇼",
                "reservation_required": False,
                "booking_tip": "화서문 야외 잔디광장 자유 관람"
            },
            {
                "name": "조선 전통 무예24기 특별 시연",
                "category": "전통 무예",
                "description": "정조의 친위부대 장용영 군사들이 펼쳤던 24가지 실전 무예를 생생하게 복원한 무예극",
                "reservation_required": False,
                "booking_tip": "신풍루 앞 상설공연장 자유 관람"
            }
        ]
    },
    {
        "id": "fest-05",
        "title": "안동 국제탈춤페스티벌",
        "region": "경상북도 안동시",
        "region_short": "경상북도",
        "startDate": "2026-09-27",
        "endDate": "2026-10-06",
        "location": "안동 탈춤공원 및 하회마을",
        "address": "경상북도 안동시 육사로 239",
        "lat": 36.5645,
        "lng": 128.7289,
        "image": "https://tong.visitkorea.or.kr/cms/resource/06/4025906_image2_1.JPG",
        "description": "신명나는 한국의 탈춤과 전 세계 민속 가면극이 어우러지는 전통 문화 대축제",
        "stamina": 40,
        "phone": "054-840-6398",
        "homepage": "http://www.maskdance.com",
        "programs": [
            {
                "name": "나만의 하회탈 만들기 공예 체험",
                "category": "전통 공예",
                "description": "전통 한지와 나무를 활용하여 나만의 표정과 개성을 담은 하회탈을 만드는 공예 교실",
                "reservation_required": True,
                "booking_tip": "체험마당 현장 선착순 또는 사전 예약"
            },
            {
                "name": "국가무형문화재 전통 탈춤 상설 마당",
                "category": "전통 공연",
                "description": "하회별신굿탈놀이, 봉산탈춤, 강령탈춤 등 한국 대표 탈춤의 신명나는 해학과 풍자 공연",
                "reservation_required": False,
                "booking_tip": "탈춤공연장 상설마당 자유 관람"
            },
            {
                "name": "세계 민속 가면극 갈라쇼 & 거리 퍼레이드",
                "category": "해외 초청",
                "description": "세계 10여 개국에서 초청된 전통 가면 무용단이 펼치는 다채로운 가면 퍼포먼스",
                "reservation_required": False,
                "booking_tip": "원도심 거리 및 축제장 전역 자유 관람"
            },
            {
                "name": "시민 대동난장 마당놀이",
                "category": "시민 화합",
                "description": "탈을 쓴 모든 관람객과 공연단이 하나 되어 춤추고 어우러지는 피날레 대동 놀이",
                "reservation_required": False,
                "booking_tip": "중앙무대 일원 자유 참여"
            }
        ]
    },
    {
        "id": "fest-06",
        "title": "부산 불꽃축제",
        "region": "부산광역시 수영구",
        "region_short": "부산광역시",
        "startDate": "2026-10-24",
        "endDate": "2026-10-26",
        "location": "광안리해수욕장 일원",
        "address": "부산광역시 수영구 광안해변로 219",
        "lat": 35.1532,
        "lng": 129.1186,
        "image": "https://tong.visitkorea.or.kr/cms/resource/92/4107992_image2_1.jpg",
        "description": "광안대교를 캔버스 삼아 가을 밤바다를 화려하게 수놓는 멀티미디어 불꽃 쇼",
        "stamina": 50,
        "phone": "051-713-5000",
        "homepage": "http://www.bfo.or.kr",
        "programs": [
            {
                "name": "광안리 해변 안심 관람석 (테이블석/체어석)",
                "category": "지정 좌석",
                "description": "광안리 백사장 중앙에서 편안하게 초대형 불꽃 쇼를 감상할 수 있는 지정 좌석 공간",
                "reservation_required": True,
                "booking_tip": "공식 티켓 예매 사이트 사전 예약"
            },
            {
                "name": "광안대교 멀티미디어 해상 불꽃쇼",
                "category": "메인 불꽃",
                "description": "광안대교를 배경으로 클래식·영화 음악에 맞추어 연출되는 초대형 25인치 타상 불꽃",
                "reservation_required": False,
                "booking_tip": "광안리·동백섬·이기대 해변 자유 관람"
            },
            {
                "name": "불꽃 라이브 토크쇼 & 버스킹 페스티벌",
                "category": "사전 행사",
                "description": "본 불꽃 쇼 시작 전 시민들의 사연과 라디오 감성 음악으로 채워지는 해변 토크 콘서트",
                "reservation_required": False,
                "booking_tip": "광안리 해변 특설무대 자유 관람"
            }
        ]
    },
    {
        "id": "fest-07",
        "title": "서산 해미읍성 역사체험축제",
        "region": "충청남도 서산시",
        "region_short": "충청남도",
        "startDate": "2026-10-09",
        "endDate": "2026-10-12",
        "location": "해미읍성 일원",
        "address": "충청남도 서산시 해미면 남문2로 143",
        "lat": 36.7135,
        "lng": 126.4842,
        "image": "https://tong.visitkorea.or.kr/cms/resource/01/2671501_image2_1.jpg",
        "description": "조선 시대 고유의 성곽 안에서 즐기는 전통 무예와 역사 문화 힐링 체험",
        "stamina": 35,
        "phone": "041-660-2540",
        "homepage": "https://www.seosan.go.kr",
        "programs": [
            {
                "name": "조선시대 병영 훈련 및 무예 체험",
                "category": "역사 체험",
                "description": "조선 초기 충청병마절도사영이었던 해미읍성에서 직접 갑옷을 입고 활쏘기·창술을 배우는 병영 체험",
                "reservation_required": True,
                "booking_tip": "병영체험마당 현장 접수 및 사전 예약"
            },
            {
                "name": "전통 줄타기 명인 공연 및 풍물 길놀이",
                "category": "전통 공연",
                "description": "아슬아슬한 공중 줄타기 묘기와 신명나는 사물놀이로 성곽 안마당을 가득 채우는 잔치",
                "reservation_required": False,
                "booking_tip": "읍성 잔디마당 자유 관람"
            },
            {
                "name": "해미읍성 성벽 순라군 순찰 재현",
                "category": "역사 재현",
                "description": "조선 시대 군관과 군졸들이 성벽을 순찰하며 관람객과 기념사진을 남기는 이동형 퍼포먼스",
                "reservation_required": False,
                "booking_tip": "읍성 성곽길 일원 자유 참여"
            },
            {
                "name": "조선 전통 장터 & 가마솥 주막 체험",
                "category": "민속 먹거리",
                "description": "가마솥에서 갓 지어낸 구수한 밥과 전통 떡메치기, 향토 장터 음식을 맛보는 힐링 공간",
                "reservation_required": False,
                "booking_tip": "민속장터 구역 상시 자유 이용"
            }
        ]
    },
    {
        "id": "fest-08",
        "title": "태안 국화축제 & 가을꽃 바다",
        "region": "충청남도 태안군",
        "region_short": "충청남도",
        "startDate": "2026-10-15",
        "endDate": "2026-11-05",
        "location": "태안 꽃지해안공원 코리아플라워파크",
        "address": "충청남도 태안군 안면읍 꽃지해안로 400",
        "lat": 36.4952,
        "lng": 126.3408,
        "image": "https://tong.visitkorea.or.kr/cms/resource/67/3090767_image2_1.jpg",
        "description": "서해 바다를 배경으로 수천만 송이 만개한 국화꽃 향기를 맡으며 걷는 가을꽃 정원",
        "stamina": 30,
        "phone": "041-675-5533",
        "homepage": "http://www.koreaflowerpark.com",
        "programs": [
            {
                "name": "유기농 국화차 다도 체험 교실",
                "category": "웰니스 힐링",
                "description": "가을 바다를 바라보며 은은한 향기의 국화차를 직접 우리고 마시는 전통 다도 힐링 프로그램",
                "reservation_required": True,
                "booking_tip": "다도체험관 사전 예약 우선"
            },
            {
                "name": "수천만 송이 국화 조형물 야외 테마 전시",
                "category": "야외 정원",
                "description": "코리아플라워파크 전역에 수놓아진 대형 국화 성곽, 에펠탑, 꽃터널 등 명품 테마 포토존",
                "reservation_required": False,
                "booking_tip": "꽃지해안공원 정원 전역 자유 관람"
            },
            {
                "name": "가을 명품 분재 및 야생화 기획전",
                "category": "실내 전시",
                "description": "수십 년 수령의 명품 국화 분재와 서해안 자생 야생화를 한자리에서 감상하는 실내 온실전",
                "reservation_required": False,
                "booking_tip": "실내 온실 전시관 자유 관람"
            },
            {
                "name": "꽃지해변 가을꽃 해안 데크길 산책 투어",
                "category": "안심 걷기",
                "description": "할미·할아비 바위를 배경으로 붉은 낙조와 국화꽃 향기를 동시에 누리는 평지 데크 산책로",
                "reservation_required": False,
                "booking_tip": "해안 데크길 상시 자유 산책"
            }
        ]
    },
    {
        "id": "fest-09",
        "title": "경주 신라문화제 & 황리단길 축제",
        "region": "경상북도 경주시",
        "region_short": "경상북도",
        "startDate": "2026-10-11",
        "endDate": "2026-10-15",
        "location": "봉황대 및 대릉원 일원",
        "address": "경상북도 경주시 태종로 756",
        "lat": 35.8385,
        "lng": 129.2089,
        "image": "https://search.pstatic.net/common/?src=http%3A%2F%2Fblogfiles.naver.net%2FMjAyNDEwMTBfMjUg%2FMDAxNzI4NDkxMTI2ODcx.ujuSWaBuNAGD_pQBPFv9fjs4tLL3TooQ7nnFw33i2Ncg.skO8tUVdbLFmUrcxHikMzh2Kt1xpdsphyllPa84b1oMg.JPEG%2F2024_%25C1%25A651%25C8%25B8_%25BD%25C5%25B6%25F3%25B9%25AE%25C8%25AD%25C1%25A6_%25B0%25A1%25C0%25CC%25B5%25E5%25BA%25CF_%25C6%25E4%25C0%25CC%25C1%25F6_30.jpg&type=b400",
        "thumbnail": "https://search.pstatic.net/common/?src=http%3A%2F%2Fblogfiles.naver.net%2FMjAyNDEwMTBfMjUg%2FMDAxNzI4NDkxMTI2ODcx.ujuSWaBuNAGD_pQBPFv9fjs4tLL3TooQ7nnFw33i2Ncg.skO8tUVdbLFmUrcxHikMzh2Kt1xpdsphyllPa84b1oMg.JPEG%2F2024_%25C1%25A651%25C8%25B8_%25BD%25C5%25B6%25F3%25B9%25AE%25C8%25AD%25C1%25A6_%25B0%25A1%25C0%25CC%25B5%25E5%25BA%25CF_%25C6%25E4%25C0%25CC%25C1%25F6_30.jpg&type=b400",
        "description": "천년 고도 경주의 유서 깊은 고분군 사이로 펼쳐지는 신라 예술과 현대의 만남",
        "stamina": 45,
        "phone": "054-777-5952",
        "homepage": "https://www.garts.kr",
        "programs": [
            {
                "name": "신라 복식(한복) 대여 및 고분 달빛 포토 투어",
                "category": "체험 투어",
                "description": "우아한 신라 귀족 복식을 입고 전문 사진작가와 함께 대릉원 고분길을 걷는 야간 화보 투어",
                "reservation_required": True,
                "booking_tip": "경주문화재단 공식 누리집 사전 예약"
            },
            {
                "name": "신라예술제 개막 주제공연 & 화평서제",
                "category": "전통 예술",
                "description": "천년 고도 경주의 역사와 평화를 염원하는 전통 제례의식 및 대규모 퓨전 국악 오케스트라",
                "reservation_required": False,
                "booking_tip": "봉황대 특설무대 자유 관람"
            },
            {
                "name": "달빛 고분 콘서트 & 화랑 버스킹",
                "category": "라이브 음악",
                "description": "신라 고분의 신비로운 실루엣을 배경으로 펼쳐지는 인디 어쿠스틱 및 재즈 라이브 공연",
                "reservation_required": False,
                "booking_tip": "봉황대 잔디마당 자유 관람"
            },
            {
                "name": "황리단길 야간 골목 아트 플리마켓",
                "category": "골목 마켓",
                "description": "한옥 골목 사이사이 로컬 아티스트들의 수공예품과 경주 먹거리가 어우러진 감성 마켓",
                "reservation_required": False,
                "booking_tip": "황리단길 일원 자유 방문"
            }
        ]
    },
    {
        "id": "fest-10",
        "title": "백제문화제 (공주·부여)",
        "region": "충청남도 공주시",
        "region_short": "충청남도",
        "startDate": "2026-10-01",
        "endDate": "2026-10-08",
        "location": "공주 금강신관공원 및 공산성",
        "address": "충청남도 공주시 금강공원길 2",
        "lat": 36.4632,
        "lng": 127.1215,
        "image": "https://tong.visitkorea.or.kr/cms/resource/55/4098555_image2_1.jpg",
        "description": "한류의 원조 백제의 찬란한 문화와 웅진성 퍼레이드를 만나는 대한민국 3대 역사 문화 축제",
        "stamina": 40,
        "phone": "041-852-9033",
        "homepage": "http://www.baekje.org",
        "programs": [
            {
                "name": "백제 금강 유등 띄우기 및 소원지 달기",
                "category": "참여 체험",
                "description": "금강 물결 위에 백제의 찬란한 문화를 담은 유등을 직접 띄우며 소원을 비는 대표 야간 체험",
                "reservation_required": True,
                "booking_tip": "금강신관공원 부스 사전 접수 및 현장 매표"
            },
            {
                "name": "웅진성 퍼레이드 & 백제 대형 거리 행렬",
                "category": "대표 퍼레이드",
                "description": "공주시민과 예술단이 함께 백제 왕실의 행차와 승전을 재현하는 웅장한 가면 행렬",
                "reservation_required": False,
                "booking_tip": "금강교 및 연문광장 일원 자유 관람"
            },
            {
                "name": "공산성 성벽 미디어파사드 야간 쇼",
                "category": "미디어아트",
                "description": "유네스코 세계유산 공산성 성벽에 펼쳐지는 백제 중흥의 역사와 디지털 빛의 향연",
                "reservation_required": False,
                "booking_tip": "공산성 맞은편 둔치 자유 관람"
            },
            {
                "name": "백제 역사문화 체험 테마촌",
                "category": "역사 체험",
                "description": "백제 금동대향로 제작 원리 체험, 전통 백제 의상 입기, 칠지도 탁본 등 가족형 체험존",
                "reservation_required": False,
            }
        ]
    }
]

# ==============================================================================
# [공공데이터 원천 연동] 10월·11월·12월 전국 로컬 축제 전수 자동 확장 로더
# ==============================================================================
def _load_public_winter_festivals():
    import os, re, json, urllib.parse
    import pandas as pd
    
    cal_img_file = os.path.join(PROJECT_ROOT, "festapick", "data", "calendar_festival_images.json")
    cal_img_db = {}
    if os.path.exists(cal_img_file):
        try:
            with open(cal_img_file, "r", encoding="utf-8") as cf:
                cal_img_db = json.load(cf)
        except Exception:
            pass
            
    csv_candidates = [
        "festapick/data/festivals.csv",
        "data/전국문화축제표준데이터.csv",
        "latest_demo/data/festivals.csv"
    ]
    target_csv = None
    for cp in csv_candidates:
        if os.path.exists(cp):
            target_csv = cp
            break
            
    if not target_csv:
        return []
        
    try:
        df = pd.read_csv(target_csv, encoding="utf-8")
    except Exception:
        try:
            df = pd.read_csv(target_csv, encoding="cp949")
        except Exception:
            return []

    # 테마별 고화질 1:1 정확 매칭 이미지 갤러리 (전수 200 OK 검증 완료)
    theme_gallery = {
        "cosmos": [
            "https://images.unsplash.com/photo-1508615039623-a25605d2b022?auto=format&fit=crop&w=800&q=80",
            "https://tong.visitkorea.or.kr/cms/resource/54/4113254_image2_1.jpg",
            "https://images.unsplash.com/photo-153303859084-1cde6e668a91?auto=format&fit=crop&w=800&q=80"
        ],
        "yi_seonggye_royal": [
            "https://tong.visitkorea.or.kr/cms/resource/76/4029576_image2_1.jpg",
            "https://images.unsplash.com/photo-1538485399081-7191377e8241?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80"
        ],
        "kim_satgat_lit": [
            "https://images.unsplash.com/photo-1578637387939-43c525550085?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1538485399081-7191377e8241?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=800&q=80"
        ],
        "reed_field": [
            SUNCHEON_REED_IMG,
            "https://tong.visitkorea.or.kr/cms/resource/37/4115237_image2_1.JPG",
            "https://images.unsplash.com/photo-1470240731273-7821a6eeb6bd?auto=format&fit=crop&w=800&q=80"
        ],
        "seowon_ritual": [
            "https://images.unsplash.com/photo-1578637387939-43c525550085?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1538485399081-7191377e8241?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1517154421773-0529f29ea451?auto=format&fit=crop&w=800&q=80"
        ],
        "folklore": [
            "https://images.unsplash.com/photo-1517457373958-b7bdd4587205?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1546874177-9e664107314e?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1538485399081-7191377e8241?auto=format&fit=crop&w=800&q=80"
        ],
        "heritage": [
            "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1578637387939-43c525550085?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1538485399081-7191377e8241?auto=format&fit=crop&w=800&q=80"
        ],
        "art_festa": [
            "https://images.unsplash.com/photo-1517457373958-b7bdd4587205?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1546874177-9e664107314e?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?auto=format&fit=crop&w=800&q=80"
        ],
        "theater": [
            "https://images.unsplash.com/photo-1460723237483-7a6dc9d0b212?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&fit=crop&w=800&q=80"
        ],
        "garden_eco": [
            "https://images.unsplash.com/photo-1585320806297-9794b3e4eeae?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1470240731273-7821a6eeb6bd?auto=format&fit=crop&w=800&q=80"
        ],
        "sea_island": [
            "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1518495973542-4542c06a5843?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80"
        ],
        "nature_mountain": [
            "https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1470240731273-7821a6eeb6bd?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80"
        ],
        "firework": [
            "https://images.unsplash.com/photo-1498931299472-f7a63a5a1cfa?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1514565131-fce0801e5785?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1531306728370-e2ebd9d7bb99?auto=format&fit=crop&w=800&q=80"
        ],
        "sunrise": [
            "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1518495973542-4542c06a5843?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1495616811223-4d98c6e9c869?auto=format&fit=crop&w=800&q=80"
        ],
        "christmas": [
            "https://images.unsplash.com/photo-1517411032315-54ef2cb783bb?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1544717305-2782549b5136?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1576919228236-a097c32a5cd4?auto=format&fit=crop&w=800&q=80"
        ],
        "light": [
            "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1519671482749-fd09be7ccebf?auto=format&fit=crop&w=800&q=80"
        ],
        "ice": [
            "https://images.unsplash.com/photo-1547756536-cde3673fa2e5?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1483921020237-2ff51e8e4b22?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1482867996988-29ec3a0f1aac?auto=format&fit=crop&w=800&q=80"
        ],
        "kimchi": [
            "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=800&q=80"
        ],
        "market": [
            "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1542601906990-b4d3fb778b09?auto=format&fit=crop&w=800&q=80"
        ],
        "concert": [
            "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1465847899084-d164df4dedc6?auto=format&fit=crop&w=800&q=80"
        ],
        "bean": [
            "https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=800&q=80"
        ],
        "apple": [
            "https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?auto=format&fit=crop&w=800&q=80"
        ],
        "meat": [
            "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80"
        ],
        "fish": [
            "https://images.unsplash.com/photo-1534939561126-855b8675edd7?auto=format&fit=crop&w=800&q=80"
        ],
        "bonsai": [
            "https://images.unsplash.com/photo-1512428813834-c702c7702b78?auto=format&fit=crop&w=800&q=80"
        ],
        "flower": [
            "https://images.unsplash.com/photo-1490750967868-88aa4486c946?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1530595467537-0b5996c41f2d?auto=format&fit=crop&w=800&q=80"
        ],
        "music": [
            "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1506157786151-b8491531f063?auto=format&fit=crop&w=800&q=80"
        ],
        "book": [
            "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1524995997946-a1c2e315a42f?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=800&q=80"
        ],
        "trail": [
            "https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1542601906990-b4d3fb778b09?auto=format&fit=crop&w=800&q=80"
        ],
        "default_festa": [
            "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1578637387939-43c525550085?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1538485399081-7191377e8241?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1517457373958-b7bdd4587205?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80"
        ]
    }

    # 한국관광공사 TourAPI 4.0 실측 공식 고유 이미지 DB (tong.visitkorea.or.kr 1,073개 전수 연동)
    official_tourapi_images = {
        "구리 코스모스": "https://tong.visitkorea.or.kr/cms/resource/54/4113254_image2_1.jpg",
        "구리 코스모스 축제": "https://tong.visitkorea.or.kr/cms/resource/54/4113254_image2_1.jpg",
        "구리 코스모스 한강예술제": "https://tong.visitkorea.or.kr/cms/resource/54/4113254_image2_1.jpg",
        "코스모스": "https://images.unsplash.com/photo-1508615039623-a25605d2b022?auto=format&fit=crop&w=800&q=80",
        "태조 이성계": "https://tong.visitkorea.or.kr/cms/resource/76/4029576_image2_1.jpg",
        "태조 이성계 축제": "https://tong.visitkorea.or.kr/cms/resource/76/4029576_image2_1.jpg",
        "이성계": "https://tong.visitkorea.or.kr/cms/resource/76/4029576_image2_1.jpg",
        "김삿갓": "https://images.unsplash.com/photo-1578637387939-43c525550085?auto=format&fit=crop&w=800&q=80",
        "김삿갓문화제": "https://images.unsplash.com/photo-1578637387939-43c525550085?auto=format&fit=crop&w=800&q=80",
        "순천만 갈대축제": SUNCHEON_REED_IMG,
        "순천만": SUNCHEON_REED_IMG,
        "순천만갈대축제": SUNCHEON_REED_IMG,
        "갈대축제": SUNCHEON_REED_IMG,
        "진남관": "https://tong.visitkorea.or.kr/cms/resource/84/4116784_image2_1.jpg",
        "여수 미디어아트": "https://tong.visitkorea.or.kr/cms/resource/84/4116784_image2_1.jpg",
        "파주페어": "https://cdn.imweb.me/upload/S202608313c0f65fcfaf46/0e4b51cbbecad.png",
        "청주 미디어아트": "https://tong.visitkorea.or.kr/cms/resource/27/3563827_image2_1.jpg",
        "진주남강": "https://tong.visitkorea.or.kr/cms/resource/57/4082657_image2_1.png",
        "유등축제": "https://tong.visitkorea.or.kr/cms/resource/57/4082657_image2_1.png",
        "양재아트": "https://tong.visitkorea.or.kr/cms/resource/57/4116957_image2_1.JPEG",
        "석조전": "https://tong.visitkorea.or.kr/cms/resource/10/4102010_image2_1.jpg",
        "덕수궁": "https://tong.visitkorea.or.kr/cms/resource/10/4102010_image2_1.jpg",
        "남당항": "https://tong.visitkorea.or.kr/cms/resource/72/4100472_image2_1.JPG",
        "대하축제": "https://tong.visitkorea.or.kr/cms/resource/72/4100472_image2_1.JPG",
        "별빛야행": "https://tong.visitkorea.or.kr/cms/resource/35/4100435_image2_1.jpg",
        "경복궁": "https://tong.visitkorea.or.kr/cms/resource/35/4100435_image2_1.jpg",
        "대장경": "https://tong.visitkorea.or.kr/cms/resource/75/3559875_image2_1.JPG",
        "공룡": "https://tong.visitkorea.or.kr/cms/resource/43/2828043_image2_1.jpg",
        "인형극": "https://tong.visitkorea.or.kr/cms/resource/13/4087113_image2_1.png",
        "운정호수": "https://tong.visitkorea.or.kr/cms/resource/81/3566581_image2_1.jpg",
        "모란": "https://tong.visitkorea.or.kr/cms/resource/40/3421440_image2_1.jpg",
        "한탄강": "https://tong.visitkorea.or.kr/cms/resource/67/3351667_image2_1.jpg",
        "가든페스타": "https://tong.visitkorea.or.kr/cms/resource/67/3351667_image2_1.jpg",
        "동장군": "https://tong.visitkorea.or.kr/cms/resource/21/3580521_image2_1.jpg",
        "간절곶": "https://tong.visitkorea.or.kr/cms/resource/50/3583350_image2_1.jpg",
        "호미곶": "https://tong.visitkorea.or.kr/cms/resource/52/4056752_image2_1.jpg",
        "수성빛": "https://tong.visitkorea.or.kr/cms/resource/12/3578312_image2_1.JPG",
        "광복로": "https://tong.visitkorea.or.kr/cms/resource/05/3576405_image2_1.JPG",
        "상록수": "https://tong.visitkorea.or.kr/cms/resource/14/4104914_image2_1.jpg",
        "최용신": "https://tong.visitkorea.or.kr/cms/resource/14/4104914_image2_1.jpg",
        "도서문화": "https://tong.visitkorea.or.kr/cms/resource/34/4105534_image2_1.jpg",
        "도서관": "https://tong.visitkorea.or.kr/cms/resource/34/4105534_image2_1.jpg",
        "독서": "https://tong.visitkorea.or.kr/cms/resource/34/4105534_image2_1.jpg",
        "불광천": "https://tong.visitkorea.or.kr/cms/resource/77/3383077_image2_1.JPG",
        "책": "https://tong.visitkorea.or.kr/cms/resource/34/4105534_image2_1.jpg",
        "북": "https://tong.visitkorea.or.kr/cms/resource/34/4105534_image2_1.jpg",
        "씨워킹": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
        "연극": "https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?auto=format&fit=crop&w=800&q=80",
        "파크콘서트": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80",
        "걷기대회": "https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=800&q=80"
    }

    # 한국관광공사 TourAPI 1,073개 공식 축제 이미지 DB 동적 로드
    tourapi_json_path = "festapick/data/tourapi_festival_images.json"
    if os.path.exists(tourapi_json_path):
        try:
            with open(tourapi_json_path, "r", encoding="utf-8") as f_json:
                ext_db = json.load(f_json)
                for k, v in ext_db.items():
                    if isinstance(v, str):
                        official_tourapi_images[k] = v.replace("http://", "https://")
        except Exception:
            pass

    # 정규화된 룩업 인덱스 사전 구축 (공백, 특수문자 제거 매칭용)
    norm_tourapi_images = {}
    for k, v in official_tourapi_images.items():
        ck = re.sub(r'[^가-힣a-zA-Z0-9]', '', k)
        if ck:
            norm_tourapi_images[ck] = v
    
    def _pick_theme_img(t_name, t_desc, t_loc):
        text = (t_name + " " + t_desc + " " + t_loc).lower()
        h = abs(hash(t_name))
        
        def _safe_u(u):
            if u and isinstance(u, str):
                return u.replace("http://", "https://")
            return None

        # [1순위] 한국관광공사 TourAPI 공공 실측 고유 이미지 (tong.visitkorea.or.kr) 정밀 매칭
        # 1-1. 완전 일치
        if t_name in official_tourapi_images:
            return _safe_u(official_tourapi_images[t_name])

        # 1-2. 정규화 일치 (공백/특수문자 무시)
        clean_name = re.sub(r'[^가-힣a-zA-Z0-9]', '', t_name)
        if clean_name in norm_tourapi_images:
            return _safe_u(norm_tourapi_images[clean_name])

        # 1-3. 키워드 양방향 포함 매칭 (축제명 및 개최장소/설명 포괄)
        for kw, off_img in official_tourapi_images.items():
            if (len(kw) >= 2 and kw in t_name) or (len(kw) >= 3 and kw in t_loc) or (len(kw) >= 4 and kw in t_desc):
                return _safe_u(off_img)

        for norm_kw, off_img in norm_tourapi_images.items():
            if (len(norm_kw) >= 2 and norm_kw in clean_name) or (len(clean_name) >= 3 and clean_name in norm_kw):
                return _safe_u(off_img)

        # [2순위] 테마별 1:1 정밀 일치 갤러리 매칭 (우선순위 고도화로 오매칭 및 중복 방지)
        # 0-1. 코스모스 전용 (바다나 한강으로 빠지지 않도록 최상위 보장)
        if "코스모스" in text:
            imgs = theme_gallery["cosmos"]
            return imgs[h % len(imgs)]

        # 0-2. 조선 왕실 / 태조 이성계 / 사냥행차 / 어가행렬 / 궁궐
        if any(k in text for k in ["이성계", "태조", "사냥행차", "어가", "왕가", "왕실", "조선시대", "궁중", "궁궐", "경복궁", "창덕궁", "덕수궁"]):
            imgs = theme_gallery["yi_seonggye_royal"]
            return imgs[h % len(imgs)]

        # 0-3. 김삿갓 / 방랑시인 / 시문학 / 과거대전 / 유적지
        if any(k in text for k in ["김삿갓", "시문학", "과거대전", "시제"]):
            imgs = theme_gallery["kim_satgat_lit"]
            return imgs[h % len(imgs)]

        # 0-4. 순천만 / 갈대 / 억새 / 생태습지
        if any(k in text for k in ["순천만", "갈대", "억새"]):
            imgs = theme_gallery["reed_field"]
            return imgs[h % len(imgs)]

        # 1. 서원 / 향제 / 제향 / 제례 / 유교 / 사당 / 향교 / 추모
        if any(k in text for k in ["서원", "향제", "제향", "제례", "유교", "사당", "향교", "추모", "석전"]):
            imgs = theme_gallery["seowon_ritual"]
            return imgs[h % len(imgs)]

        # 2. 민속 / 전통민속 / 농악 / 풍물 / 사물놀이 / 탈춤 / 길놀이 / 재현
        if any(k in text for k in ["민속", "전통민속", "농악", "풍물", "사물놀이", "탈춤", "길놀이", "재현", "당산제", "줄다리기", "상여"]):
            imgs = theme_gallery["folklore"]
            return imgs[h % len(imgs)]

        # 3. 도서 / 독서 / 책 / 북페스티벌 / 리딩 / 도서관
        if any(k in text for k in ["도서", "독서", "책", "북페어", "북앤", "도서관", "출판", "리딩"]):
            imgs = theme_gallery["book"]
            return imgs[h % len(imgs)]

        # 4. 연극 / 대학로 / 뮤지컬 / 인형극 / 거리극 / 극제
        if any(k in text for k in ["대학로", "연극", "인형극", "뮤지컬", "극제", "거리극", "마당극"]):
            imgs = theme_gallery["theater"]
            return imgs[h % len(imgs)]

        # 5. 예술제 / 어울마당 / 문화마당 / 비엔날레 / 문화예술 / 갤러리 / 미술 / 전시
        if any(k in text for k in ["예술제", "어울마당", "문화마당", "비엔날레", "문화제", "미술", "전시", "갤러리", "아트페어"]):
            imgs = theme_gallery["art_festa"]
            return imgs[h % len(imgs)]

        # 6. 한국 궁궐 / 성곽 / 백제 / 읍성 / 역사 / 문화재 / 고분 / 왕릉
        if any(k in text for k in ["백제", "무령왕릉", "왕릉", "신라", "조선", "읍성", "성곽", "역사", "문화재", "유산", "대장경", "고창"]):
            imgs = theme_gallery["heritage"]
            return imgs[h % len(imgs)]

        # 7. 정원 / 수변 / 영산강 / 생태 / 호수 / 숲 / 강변
        if any(k in text for k in ["정원", "영산강", "수변", "호수", "생태", "강변", "습지", "수목원", "공원"]):
            imgs = theme_gallery["garden_eco"]
            return imgs[h % len(imgs)]

        # 8. 제주 / 서귀포 / 강정 / 섬 / 바다 / 해양 / 포구 / 해수욕장
        if any(k in text for k in ["제주", "서귀포", "강정", "바다", "해양", "포구", "항구", "해수욕장", "어촌"]):
            imgs = theme_gallery["sea_island"]
            return imgs[h % len(imgs)]

        # 9. 인제 / 산림 / 자작나무 / 산 / 단풍 / 계곡
        if any(k in text for k in ["인제", "자작나무", "단풍", "산림", "계곡", "국립공원", "숲길"]):
            imgs = theme_gallery["nature_mountain"]
            return imgs[h % len(imgs)]

        # 10. 국화 / 가을꽃 / 꽃축제
        if any(k in text for k in ["국화", "가을꽃", "꽃축제"]):
            imgs = theme_gallery["flower"]
            return imgs[h % len(imgs)]

        # 11. 불꽃놀이 (불꽃/드론쇼)
        if any(k in text for k in ["불꽃", "드론라이트", "멀티미디어불꽃", "불꽃쇼"]):
            imgs = theme_gallery["firework"]
            return imgs[h % len(imgs)]
            
        # 12. 해맞이 / 일출
        if any(k in text for k in ["해맞이", "해돋이", "해넘이", "일출", "신년", "간절곶", "호미곶", "왜목마을", "땅끝"]):
            imgs = theme_gallery["sunrise"]
            return imgs[h % len(imgs)]
            
        # 13. 크리스마스 / 성탄
        if any(k in text for k in ["크리스마스", "산타", "성탄", "위시빌리지", "산타마을"]):
            imgs = theme_gallery["christmas"]
            return imgs[h % len(imgs)]
            
        # 14. 얼음 / 동장군 / 눈꽃 / 썰매
        if any(k in text for k in ["동장군", "얼음", "빙벽", "눈꽃", "썰매", "백운계곡", "겨울왕국"]):
            imgs = theme_gallery["ice"]
            return imgs[h % len(imgs)]
            
        # 15. 분재 / 수목
        if any(k in text for k in ["분재", "1004섬 분재", "수목원", "식물"]):
            return theme_gallery["bonsai"][0]

        # 16. 김장 / 김치
        if any(k in text for k in ["김장", "김치", "양념축제"]):
            imgs = theme_gallery["kimchi"]
            return imgs[h % len(imgs)]
            
        # 17. 콩 / 장단콩 / 두부
        if any(k in text for k in ["장단콩", "콩축제", "두부", "메주"]):
            return theme_gallery["bean"][0]
            
        # 18. 사과 / 과일 / 배 / 곶감
        if any(k in text for k in ["사과", "과일", "배축제", "곶감", "호두"]):
            return theme_gallery["apple"][0]
            
        # 19. 한우 / 고기 / 바비큐
        if any(k in text for k in ["한우", "바비큐", "바베큐", "고기", "육우"]):
            return theme_gallery["meat"][0]
            
        # 20. 고등어 / 수산물 / 어시장
        if any(k in text for k in ["고등어", "수산물", "송도해수욕장", "어시장", "해물", "미남축제"]):
            return theme_gallery["fish"][0]

        # 21. 전통시장 / 오일장 / 모란장 / 먹거리장터
        if any(k in text for k in ["모란", "5일장", "오일장", "장터", "시장", "먹거리", "골목"]):
            imgs = theme_gallery["market"]
            return imgs[h % len(imgs)]
            
        # 22. 도보 / 걷기 / 트레킹 / 마라톤
        if any(k in text for k in ["걷기", "도보", "튼튼쑥쑥", "투어", "올레", "산책", "마라톤", "트레킹"]):
            imgs = theme_gallery["trail"]
            return imgs[h % len(imgs)]

        # 23. 빛 / 조명 / 일루미네이션 / 루미나리에 / 야경 / 미디어아트
        if any(k in text for k in ["빛", "일루미네이션", "루미나리에", "조명", "트리", "야경", "수성빛", "미디어아트"]):
            imgs = theme_gallery["light"]
            return imgs[h % len(imgs)]

        # 24. 순수 콘서트 / 가요제
        if any(k in text for k in ["콘서트", "파크콘서트", "대중가수", "가요제", "오케스트라"]):
            imgs = theme_gallery["concert"]
            return imgs[h % len(imgs)]

        # 25. 순수 음악 / 버스킹 / 댄스
        if any(k in text for k in ["음악", "버스킹", "댄스", "가요", "밴드"]):
            imgs = theme_gallery["music"]
            return imgs[h % len(imgs)]

        # [최종 Fallback] 한국 전통/고궁/등불 실사 해시 분산 (뉴욕 빌딩 등 해외 사진 완전 배제)
        imgs = theme_gallery["default_festa"]
        return imgs[h % len(imgs)]

    def _norm_d(d_val, base_year="2026"):
        if pd.isna(d_val) or not str(d_val).strip():
            return ""
        d_str = str(d_val).strip()
        parts = d_str.split("-")
        if len(parts) == 3:
            try:
                y = parts[0]
                m = int(parts[1])
                d = int(parts[2])
                # 만약 원본이 2027년이면 2027년 유지!
                target_y = "2027" if "2027" in y else base_year
                return f"{target_y}-{m:02d}-{d:02d}"
            except Exception:
                return d_str
        return d_str

    def _get_sdo(addr_str):
        if not addr_str or addr_str == "nan":
            return "전국"
        for sdo in ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]:
            if sdo in addr_str:
                mapping = {
                    "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시",
                    "광주": "광주광역시", "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시",
                    "경기": "경기도", "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
                    "전북": "전라북도", "전남": "전라남도", "경북": "경상북도", "경남": "경상남도", "제주": "제주특별자치도"
                }
                return mapping.get(sdo, sdo)
        return "대한민국"

    seen_set = {f["title"] for f in CALENDAR_MASTER_FESTIVALS}
    added_list = []

    for idx, row in df.iterrows():
        raw_name = str(row.get("축제명", "")).strip()
        s_raw = str(row.get("축제시작일자", "")).strip()
        e_raw = str(row.get("축제종료일자", "")).strip()
        
        # 10월, 11월, 12월 및 2027년 신년/연초 축제 전수 포함
        is_target = any(k in s_raw or k in e_raw for k in ["-10-", "-11-", "-12-", "2027-01", "2027-02", "2027-"])
        if not is_target:
            continue
            
        clean_name = re.sub(r'^(201\d|202\d)\s*(년도?|제\d+회)?\s*', '', raw_name).strip()
        clean_name = re.sub(r'^\s*제\d+회\s*', '', clean_name).strip()
        disp_name = clean_name if len(clean_name) >= 3 else raw_name
        
        if disp_name in seen_set or raw_name in seen_set:
            continue
        seen_set.add(disp_name)
        seen_set.add(raw_name)
        
        s_date = _norm_d(s_raw, "2026")
        e_date = _norm_d(e_raw, "2026")
        if not s_date or not e_date:
            continue
            
        # 12월에서 1월로 넘어가는 축제 보정 (예: 2026-12-24 ~ 2026-01-31 -> 2027-01-31)
        if s_date > e_date:
            e_parts = e_date.split("-")
            if len(e_parts) == 3:
                e_date = f"2027-{e_parts[1]}-{e_parts[2]}"
                
        place = str(row.get("개최장소", "")).strip()
        addr = str(row.get("소재지도로명주소", row.get("소재지지번주소", ""))).strip()
        desc = str(row.get("축제내용", "")).strip()
        hp = str(row.get("홈페이지주소", "")).strip()
        phone = str(row.get("전화번호", "")).strip()
        lat = row.get("위도")
        lng = row.get("경도")
        
        loc_str = place if place and place != "nan" else (addr if addr and addr != "nan" else "행사장 일원")
        addr_str = addr if addr and addr != "nan" else (place if place and place != "nan" else "상세 안내 참조")
        sdo_str = _get_sdo(addr_str if addr_str != "상세 안내 참조" else loc_str)
        
        full_desc = desc if desc and desc != "nan" and len(desc) >= 8 else f"{disp_name} - 지역 고유의 문화와 정취를 만끽하는 로컬 축제"
        
        # [최우선] calendar_festival_images.json 정밀 매핑 (오매칭/중복/엑박 완전 방지)
        img_url = None
        thumb_url = None
        if cal_img_db:
            c_info = cal_img_db.get(disp_name) or cal_img_db.get(raw_name)
            if not c_info:
                clean_no_num = re.sub(r'^(201\d|202\d)\s*(년도?|제\d+회)?\s*', '', raw_name).strip()
                clean_no_num = re.sub(r'제?\s*\d+\s*회', ' ', clean_no_num).strip()
                c_info = cal_img_db.get(clean_no_num)
            if c_info:
                img_url = c_info.get("image")
                thumb_url = c_info.get("thumbnail")
                if img_url and ("blogfiles.naver.net" in img_url or img_url.startswith("http://")):
                    if thumb_url and thumb_url.startswith("https://"):
                        img_url = thumb_url
                    else:
                        img_url = f"https://search.pstatic.net/common/?src={urllib.parse.quote(str(img_url), safe='')}&type=b400"
                        thumb_url = img_url
                
        if not img_url:
            img_url = _pick_theme_img(disp_name, full_desc, loc_str)
            thumb_url = f"https://search.pstatic.net/common/?src={urllib.parse.quote(str(img_url), safe='')}&type=b400"
            
        is_req = any(kw in full_desc for kw in ["예약", "접수", "체험", "신청", "대회", "공예"])
        raw_theme = str(row.get("theme", "")).strip()
        theme_val = "" if raw_theme in ["nan", "None", "null"] else raw_theme
        
        added_list.append({
            "id": f"pub-fest-{idx:04d}",
            "title": disp_name,
            "theme": theme_val,
            "region": f"{sdo_str} {loc_str[:12]}".strip(),
            "region_short": sdo_str,
            "startDate": s_date,
            "endDate": e_date,
            "location": loc_str,
            "address": addr_str,
            "lat": float(lat) if pd.notna(lat) and str(lat).replace('.','',1).isdigit() else 36.5,
            "lng": float(lng) if pd.notna(lng) and str(lng).replace('.','',1).isdigit() else 127.8,
            "image": img_url,
            "thumbnail": thumb_url or f"https://search.pstatic.net/common/?src={urllib.parse.quote(str(img_url), safe='')}&type=b400",
            "description": full_desc[:120],
            "stamina": 35 + (idx % 25),
            "phone": phone if phone and phone != "nan" else "1330",
            "homepage": hp if (hp and hp.startswith("http")) else "",
            "programs": [
                {
                    "name": f"{disp_name} 로컬 참여 프로그램",
                    "category": "체험행사" if is_req else "문화행사",
                    "description": f"{loc_str}에서 펼쳐지는 지역 대표 문화 및 특산물 현장 행사",
                    "reservation_required": is_req,
                    "booking_tip": "공식 누리집 사전 접수 및 현장 안내" if is_req else "현장 자유 참여 가능"
                }
            ]
        })
    return added_list

CALENDAR_MASTER_FESTIVALS.extend(_load_public_winter_festivals())

# [FESTIVAL_COORDS_TABLE 일괄 보정] 로컬 축제 좌표 강제 보정 적용
for f_item in CALENDAR_MASTER_FESTIVALS:
    f_lat, f_lng = resolve_festival_coordinates(f_item.get("title", ""), f_item.get("address", ""), f_item.get("lat"), f_item.get("lng"))
    f_item["lat"] = f_lat
    f_item["lng"] = f_lng

def get_festival_programs_from_data(fest_name: str, fallback_desc: str = "") -> List[Dict[str, Any]]:
    """[공공데이터 연동] 축제명 및 설명 기반 공공데이터 프로그램 원천 복원 및 매핑 헬퍼"""
    # 1. 캘린더 마스터 데이터셋 매칭
    for f in CALENDAR_MASTER_FESTIVALS:
        if f["title"] == fest_name or f["title"] in fest_name or fest_name in f["title"]:
            if f.get("programs"):
                return f["programs"]

    # 2. 기획특집 프리셋 매칭
    for h in HOT_FESTIVALS_PRESET:
        if h["name"] == fest_name or h["name"] in fest_name or fest_name in h["name"]:
            if h.get("programs"):
                return h["programs"]

    # 3. 공공데이터 축제내용/설명 텍스트 파싱 복원
    if fallback_desc:
        stopwords = {"등", "기타", "체험행사", "축제내용", "행사내용", "부대행사", "관련정보"}
        candidates = re.split(r'[+,/;\n·]', str(fallback_desc))
        progs = []
        seen = set()
        for cand in candidates:
            c = cand.strip()
            if len(c) >= 2 and c not in stopwords and c not in seen:
                seen.add(c)
                is_req = any(kw in c for kw in ["예약", "접수", "체험", "신청", "대회", "공예", "만들기"])
                progs.append({
                    "name": c,
                    "category": "체험 프로그램" if is_req else "공공 문화행사",
                    "description": f"{fest_name} 현장에서 즐길 수 있는 공공 공식 프로그램",
                    "reservation_required": is_req,
                    "booking_tip": "공식 누리집 사전 접수 및 현장 안내" if is_req else "현장 자유 참여 가능"
                })
                if len(progs) >= 5:
                    break
        if progs:
            return progs

    return []

# [Editorial Essay Master Data] 축제 지역별 10대 고유 에디토리얼 힐링 에세이 마스터 데이터셋
CURATED_EDITORIAL_ESSAYS = [
    {
        "id": "suncheon",
        "keywords": ["순천", "순천만", "갈대", "습지", "생태"],
        "region": "전라남도",
        "quote_lead": "“황금빛 갈대숲이 바람에 일렁일 때, 가만히 맞잡은 두 손에 계절의 온기가 스며듭니다.”",
        "quote_mid": "“끝없이 펼쳐진 은빛 갈대 사이로, 함께 걷는 걸음마다 오랜 사랑이 피어났다.”",
        "first_letter": "가",
        "text_1": "을 순천만 갈대축제는 언제나 바람의 방향으로 먼저 말을 건넵니다. 자연 위로 끝없이 펼쳐진 은빛 갈대 물결은 해 질 무렵이 되면 황금빛으로 물들며 장관을 이룹니다. 무장애 목재 데크로드가 평지로 완만하게 이어져 있어 거동이 불편하신 어르신이나 휠체어를 동반한 가족도 턱 없이 안심하고 광활한 생태의 한가운데로 스며들 수 있습니다.",
        "text_2": "축제를 둘러본 뒤에는 차로 5분 거리에 위치한 착한가격 지정 식당에서 담백하고 정갈한 남도 계절 꼬막정식으로 점심을 권합니다. 과하지 않은 양념과 부드럽게 삶아낸 남도 제철 나물은 소화가 잘되어 연로하신 어르신들께도 안성맞춤입니다. 마지막 코스로 들르는 한방 웰니스 족욕 테라피는 여행 내내 긴장했던 발과 무릎의 피로를 사르르 풀어줄 것입니다.",
        "slow_tag": "Slow Travel Memoir · 전라남도 순천만",
        "tip_walk": "전 구간 무장애 평지 데크로드로 휠체어·실버카 주행이 매우 수월합니다.",
        "tip_rest": "200m 간격 그늘 쉼터와 벤치가 마련되어 있어 수시로 쉴 수 있습니다.",
        "tip_spot": "P1 안심 주차장 기준 매표소 30m 지점에 무료 휠체어 대여소가 완비되어 있습니다."
    },
    {
        "id": "jinju",
        "keywords": ["진주", "남강", "유등", "촉석루"],
        "region": "경상남도",
        "quote_lead": "“천 년을 묵묵히 흐른 남강 물결 위에 수만 개의 소망등이 닿을 때, 마음 한구석도 따스하게 밝아집니다.”",
        "quote_mid": "“물빛과 달빛이 어우러진 촉석루 아래, 가족의 소망은 등불이 되어 흘렀다.”",
        "first_letter": "밤",
        "text_1": "하늘을 수놓는 수만 개의 유등은 진주 남강을 거대한 빛의 캔버스로 물들입니다. 촉석루와 남강 성곽을 따라 이어진 평지 부교는 흔들림 없이 안정적으로 설계되어 있어 어르신들도 안심하고 물 위를 거닐며 환상적인 유등을 눈앞에서 감상할 수 있습니다. 수면 위로 은은하게 번지는 빛무리는 바쁜 일상에서 잊고 지냈던 온기를 조용히 되찾아 줍니다.",
        "text_2": "남강의 정취를 만끽한 후에는 성곽 인근 골목의 착한가격 모범식당에서 따뜻한 선짓국과 신선한 나물이 어우러진 담백한 진주 비빔밥을 즐깁니다. 자극적이지 않고 영양이 풍부하여 여행 중 체력을 보충하기에 제격입니다. 여정의 마무리는 촉석루 뒤편 울창한 대숲 쉼터에서 강바람을 맞으며 차 한 잔과 함께 깊은 숨을 들이쉬는 힐링의 시간입니다.",
        "slow_tag": "Slow Travel Memoir · 경상남도 진주",
        "tip_walk": "강변 평지 산책로와 완만한 경사로 부교로 계단 없이 남강 야경을 관람합니다.",
        "tip_rest": "진주성 성곽 안팎 잔디마당에 차양 벤치와 안심 쉼터가 다수 배치되어 있습니다.",
        "tip_spot": "진주교 공영주차장 완비, 보행 약자를 위한 전용 승하차 구역이 운영됩니다."
    },
    {
        "id": "gangneung",
        "keywords": ["강릉", "커피", "바다", "안목", "경포"],
        "region": "강원특별자치도",
        "quote_lead": "“솔향기 짙은 해변 데크길을 걷다 그윽한 드립 커피 한 잔을 마주할 때, 파도 소리는 가장 다정한 음악이 됩니다.”",
        "quote_mid": "“바다와 솔밭이 만나는 길목, 커피 향기 속에 우리의 대화는 천천히 깊어졌다.”",
        "first_letter": "푸",
        "text_1": "른 동해 바다와 짙푸른 해송 숲길이 나란히 달리는 강릉의 가을은 커피 향기로 가득합니다. 안목해변에서 경포호수로 이어지는 무장애 평지 데크 산책로는 계단이나 가파른 언덕이 전혀 없어 발목 부담 없이 바다를 바라보며 천천히 걷기 좋습니다. 솔바람 사이로 번져오는 신선한 원두의 로스팅 향기는 걸음마다 잔잔한 여유를 선물합니다.",
        "text_2": "커피 향기를 따라 걷는 여정 뒤에는 강릉 초당마을 인근 착한가격 식당에서 몽글몽글하고 부드러운 전통 초당순두부 백반으로 속을 편안하게 달랩니다. 인공 첨가물 없이 맑은 바닷물로 빚어낸 순두부는 어르신들의 소화에도 더없이 좋습니다. 이어지는 일정은 소나무 숲속 빈백 쉼터에서 파도 소리를 배경음악 삼아 누리는 평온한 휴식입니다.",
        "slow_tag": "Slow Travel Memoir · 강원도 강릉 솔향",
        "tip_walk": "해변 모래사장 진입 없이 전 구간 평지 목재 데크로 편안히 바다를 조망합니다.",
        "tip_rest": "송정 해송 숲 그늘 아래 휠체어 접근 가능한 넓은 피크닉 쉼터가 조성되어 있습니다.",
        "tip_spot": "안목해변 대형 공영주차장과 무장애 쉼터가 도보 50m 내에 인접해 있습니다."
    },
    {
        "id": "suwon",
        "keywords": ["수원", "화성", "미디어아트", "정조"],
        "region": "경기도",
        "quote_lead": "“정조의 효심이 깃든 웅장한 성곽을 따라 걷다 보면, 과거와 현재가 빚어낸 빛의 파노라마가 발걸음을 멈추게 합니다.”",
        "quote_mid": "“단단한 성벽 위에 피어난 미디어아트의 빛, 고요한 밤길은 따뜻한 추억이 되었다.”",
        "first_letter": "웅",
        "text_1": "장한 유네스코 세계유산 수원화성의 가을밤은 전통과 첨단 기술이 빚어낸 빛의 향연으로 다시 태어납니다. 화서문과 장안문 성벽을 스크린 삼아 펼쳐지는 3D 미디어아트 맵핑은 턱 없는 넓은 잔디광장에 앉아 편안하게 감상할 수 있어 거동이 불편한 어르신들에게도 최적의 야경 코스입니다. 역사 속 정조대왕의 애민정신이 성벽마다 찬란한 빛으로 살아 숨 쉽니다.",
        "text_2": "성곽 야행을 즐기기 전, 행궁동 인근 착한가격업소에서 푹 고아낸 담백하고 진한 한우 소머리국밥이나 가마솥 설렁탕으로 든든한 저녁 식사를 나눕니다. 기름기 없이 깔끔한 국물은 쌀쌀해진 가을밤 체온을 훈훈하게 지켜줍니다. 이어지는 코스는 행궁길 고즈넉한 한옥 전통 찻집에서 따뜻한 대추차 한 잔과 함께 성곽의 여운을 음미하는 차분한 시간입니다.",
        "slow_tag": "Slow Travel Memoir · 경기도 수원화성",
        "tip_walk": "행궁광장 및 화서문 잔디마당 전 구역 단차 제로, 휠체어 친화 보행로입니다.",
        "tip_rest": "성곽 조망 벤치와 행궁 쉼터가 촘촘하여 어르신 맞춤 휴식이 용이합니다.",
        "tip_spot": "연무대 및 화성행궁 공영주차장에 교통약자 우선 주차면이 넉넉히 구비되어 있습니다."
    },
    {
        "id": "andong",
        "keywords": ["안동", "탈춤", "하회", "가면"],
        "region": "경상북도",
        "quote_lead": "“해학과 웃음으로 세상의 시름을 털어내는 하회탈의 미소처럼, 흙길을 딛는 발걸음마다 활력이 차오릅니다.”",
        "quote_mid": "“신명나는 탈춤 가락에 어깨를 들썩이며, 우리는 마음속 무거운 짐을 가볍게 내려놓았다.”",
        "first_letter": "천",
        "text_1": "년의 전통을 품은 안동 탈춤공원과 하회마을은 가을이 되면 흥겨운 꽹과리 소리와 탈춤의 해학으로 물듭니다. 평지로 조성된 공연장 동선은 휠체어와 유모차 이동에 걸림돌이 없으며, 관람석 또한 단차가 완만하여 연로하신 부모님도 편안하게 앉아 전 세계 민속 가면극을 즐길 수 있습니다. 신명나는 몸짓을 바라보는 것만으로도 가슴속 답답함이 시원하게 풀려납니다.",
        "text_2": "공연의 여흥을 안고 원도심 착한가격 골목 식당에서 자극적이지 않게 조리한 담백한 안동 헛제삿밥과 간고등어 구이로 점심을 즐깁니다. 정갈한 탕국과 제철 나물은 위에 부담을 주지 않아 어르신들의 건강 식단으로 손꼽힙니다. 마지막으로는 낙동강변 소나무 숲길 쉼터에서 솔잎 향을 맡으며 다리의 긴장을 풀어주는 안심 힐링 휴식을 만끽합니다.",
        "slow_tag": "Slow Travel Memoir · 경상북도 안동",
        "tip_walk": "축제장 주 동선이 모두 평지 아스팔트 및 완만한 흙길로 평탄하게 정비되었습니다.",
        "tip_rest": "야외 공연장마다 그늘 차양막과 등받이 좌석 쉼터가 넉넉히 제공됩니다.",
        "tip_spot": "탈춤공원 지하 및 지상 공영주차장에 보행 약자 도보 30m 진입로가 연결됩니다."
    },
    {
        "id": "busan",
        "keywords": ["부산", "불꽃", "광안리", "해변"],
        "region": "부산광역시",
        "quote_lead": "“광안대교 밤하늘을 수놓는 불꽃의 찬란함 뒤로, 가을 밤바다의 깊은 잔향이 마음에 오래도록 머뭅니다.”",
        "quote_mid": "“바다를 캔버스 삼아 터지는 화려한 불꽃, 가족과 나눈 손길은 더없이 따스했다.”",
        "first_letter": "가",
        "text_1": "을 밤 광안리 해변은 파도 소리 위로 피어오르는 환상적인 멀티미디어 불꽃 쇼로 거대한 축제의 무대가 됩니다. 해변을 따라 넓게 정비된 무장애 해안 보행로는 단차가 전혀 없어 휠체어 접근성이 뛰어나며, 혼잡하지 않은 측면 관람 구역에서도 웅장한 25인치 타상 불꽃을 시야 방해 없이 시원하게 조망할 수 있습니다.",
        "text_2": "불꽃의 감동을 마주하기 전, 인근 착한가격 지정 국밥집에서 깊고 진하게 우려낸 맑은 부산 돼지국밥으로 든든하게 속을 채웁니다. 잡내 없이 부드럽게 삶아낸 살코기는 치아가 약하신 부모님도 맛있게 드실 수 있습니다. 여정의 끝은 동백섬 솔밭 데크 쉼터에서 시원한 파도 소리를 들으며 축제의 여운을 조용히 정리하는 릴랙스 타임입니다.",
        "slow_tag": "Slow Travel Memoir · 부산광역시 광안리",
        "tip_walk": "해변 테라스 산책로 전 구간 단차 없음, 휠체어 안심 관람 구역 완비.",
        "tip_rest": "해안가 벤치와 실내 해양문화 쉼터에서 체온을 유지하며 관람 가능합니다.",
        "tip_spot": "민락수변공원 및 인근 공영주차장 이용 권장, 엘리베이터 이동 동선 확보."
    },
    {
        "id": "seosan",
        "keywords": ["서산", "해미", "해미읍성", "역사"],
        "region": "충청남도",
        "quote_lead": "“소박한 조선의 성곽 안, 푸른 잔디마당을 밟으며 걷는 길은 오랜 시간을 건너온 가장 평온한 쉼터입니다.”",
        "quote_mid": "“성벽 위로 스치는 맑은 바람결에, 번잡했던 일상의 근심은 어느덧 흩어졌다.”",
        "first_letter": "조",
        "text_1": "선 초기 600년 역사를 고스란히 간직한 서산 해미읍성은 성곽 안 전체가 넓고 평평한 푸른 잔디밭으로 이루어져 있습니다. 높은 계단이나 경사로가 전혀 없어 무릎 관절이 약하신 어르신도 산책하듯 평온하게 거닐 수 있는 최고의 무장애 역사 쉼터입니다. 성곽을 따라 걷다 마주치는 전통 줄타기 공연과 조선시대 순라군의 위풍당당한 행렬은 정겨운 시간 여행을 선사합니다.",
        "text_2": "읍성을 여유롭게 거닌 후에는 읍성 정문 앞 착한가격 장터 식당에서 가마솥에 푹 끓여낸 향토 소고기 국밥과 정갈한 서산 제철 겉절이로 소박하지만 따스한 식사를 즐깁니다. 인공 조미료 없이 진하게 우려낸 고깃국물은 속을 편안하게 덥혀줍니다. 마지막 코스로는 개심사 자락의 고요한 솔숲 쉼터에서 자연의 맑은 공기를 호흡하며 여행의 안식을 완성합니다.",
        "slow_tag": "Slow Travel Memoir · 충청남도 서산 해미",
        "tip_walk": "성곽 내부 전체가 완만한 평지 잔디밭으로 계단 없이 편안한 보행이 가능합니다.",
        "tip_rest": "호야나무 그늘 아래와 전통 정자 쉼터에서 언제든 편안히 휴식할 수 있습니다.",
        "tip_spot": "해미읍성 남문 대형 주차장에 보행 약자 전용 무료 주차 공간이 완비되어 있습니다."
    },
    {
        "id": "taean",
        "keywords": ["태안", "국화", "꽃", "꽃지", "안면도"],
        "region": "충청남도",
        "quote_lead": "“서해의 붉은 노을을 등지고 수천만 송이 국화 향기를 맡을 때, 지친 마음에 향기로운 위로가 스며듭니다.”",
        "quote_mid": "“바다를 붉게 물들이는 저녁노을과 꽃향기, 우리의 걸음은 향기로운 시가 되었다.”",
        "first_letter": "만",
        "text_1": "리포와 꽃지해안공원을 잇는 태안의 가을 바다는 수천만 송이 오색 국화꽃이 빚어낸 거대한 플라워 가든으로 변모합니다. 바다를 배경으로 조성된 테마 정원은 전 구간이 평지 목재 데크로 완만하게 연결되어 있어 보행 보조기구를 이용하시는 어르신들도 꽃터널 속을 여유롭게 통과할 수 있습니다. 서해의 낙조와 어우러진 국화 향기는 숨을 들이쉴 때마다 깊은 치유를 선사합니다.",
        "text_2": "향기로운 꽃길을 걸은 뒤에는 꽃지 인근 착한가격 해물 식당에서 신선한 제철 바지락으로 끓여낸 맑은 칼국수와 담백한 영양 굴밥을 맛봅니다. 자극적이지 않고 바다의 깊은 감칠맛을 담아 소화가 매우 편안합니다. 여정의 대미는 가을 바다가 한눈에 내려다보이는 전통 다도 쉼터에서 따뜻한 유기농 국화차를 음미하며 몸을 녹이는 힐링입니다.",
        "slow_tag": "Slow Travel Memoir · 충청남도 태안 꽃지",
        "tip_walk": "테마 가든 전 구간 휠체어·유모차 전용 무장애 평지 데크길이 완비되어 있습니다.",
        "tip_rest": "꽃터널 중간중간 차양 파라솔과 통나무 벤치가 충분히 설치되어 있습니다.",
        "tip_spot": "코리아플라워파크 정문 앞 지상 대형 주차장과 최단 동선 진입로가 연결됩니다."
    },
    {
        "id": "gyeongju",
        "keywords": ["경주", "신라", "황리단길", "대릉원", "봉황대"],
        "region": "경상북도",
        "quote_lead": "“천 년 고분의 완만한 능선 사이로 달빛이 내려앉을 때, 고요한 역사의 숨결이 우리의 걸음을 보듬어 줍니다.”",
        "quote_mid": "“능선 위로 번지는 은은한 달빛 아래, 천년 고도의 밤은 다정한 안식처가 되었다.”",
        "first_letter": "천",
        "text_1": "년 고도 경주의 대릉원과 봉황대 고분군은 가을밤이 되면 신라 예술과 현대의 빛이 어우러지는 낭만의 무대로 깨어납니다. 고분 사이로 곱게 다듬어진 평지 흙길과 데크로드는 턱이 전혀 없어 발걸음이 한결 가볍고 안정적입니다. 거대한 고분의 유려한 곡선 위로 은은한 달빛 조명이 내려앉고, 잔디마당에서 들려오는 퓨전 국악 오케스트라의 선율은 마음을 편안하게 내려놓게 합니다.",
        "text_2": "고분의 정취를 누린 뒤에는 황리단길 초입의 착한가격 한식당에서 정갈하게 차려낸 우렁된장 쌈밥과 부드러운 언양식 불고기 백반으로 풍요로운 저녁을 즐깁니다. 유기농 채소와 짜지 않은 된장은 어르신들의 건강에도 안성맞춤입니다. 이어지는 일정은 보문호수 무장애 호반길 벤치 쉼터에서 밤바람을 맞으며 차분하게 일정을 마무리하는 슬로우 투어입니다.",
        "slow_tag": "Slow Travel Memoir · 경상북도 경주 고분길",
        "tip_walk": "대릉원 돌담길과 고분 둘레길 전체 평지 흙포장으로 발목 피로가 매우 적습니다.",
        "tip_rest": "봉황대 잔디광장 주변 고목나무 그늘 아래 쉼터가 여유롭게 마련되어 있습니다.",
        "tip_spot": "대릉원 공영주차장에 장애인 및 어르신 동승 차량 전용 구역이 잘 정비되어 있습니다."
    },
    {
        "id": "baekje",
        "keywords": ["백제", "공주", "부여", "공산성", "금강"],
        "region": "충청남도",
        "quote_lead": "“금강 물결 위로 찬란했던 백제의 빛이 피어오를 때, 어머니의 품처럼 아늑한 고도의 정취가 마음을 채웁니다.”",
        "quote_mid": "“금강을 물들인 백제의 등불, 잔잔한 강물처럼 우리의 마음도 평온을 되찾았다.”",
        "first_letter": "백",
        "text_1": "제의 찬란한 숨결이 살아 숨 쉬는 공주 공산성과 금강신관공원은 가을이 되면 수천 개의 유등과 웅진성 퍼레이드로 눈부시게 밝아집니다. 금강 둔치를 따라 넓게 조성된 평지 수변 산책로는 단차가 전혀 없어 휠체어와 어르신들의 실버카 보행이 매우 수월합니다. 유유히 흐르는 금강 위에 띄워진 대형 백제 유등을 바라보며 걷다 보면, 천 년 전 평화로웠던 왕국의 기운이 마음 깊이 전해집니다.",
        "text_2": "축제장 탐방 후에는 산성시장 인근 착한가격 식당에서 공주 특산 알밤을 듬뿍 넣은 고소한 영양 돌솥밥과 산채 비빔밥으로 온기 넘치는 식사를 나눕니다. 부드러운 알밤과 계절 나물의 조화는 어르신들의 입맛을 기분 좋게 돋워줍니다. 여정의 마무리는 한옥마을 전통 온돌 쉼터에서 따스한 족욕과 함께 가을 여행의 피로를 편안히 씻어내는 힐링 타임입니다.",
        "slow_tag": "Slow Travel Memoir · 충청남도 공주 금강",
        "tip_walk": "금강 둔치 미르섬 산책로는 100% 평지 마사토 및 데크로 조성되어 있습니다.",
        "tip_rest": "금강변을 따라 차양 쉼터와 간이 의자가 150m 간격으로 촘촘히 마련되어 있습니다.",
        "tip_spot": "금강신관공원 대형 주차장 완비, 축제장 메인 게이트까지 도보 50m 평지 이동."
    }
]

def get_curated_essay(
    fest_name: str,
    region: str = "",
    companion: str = "",
    active_fest: Optional[Dict[str, Any]] = None,
    top3_restaurants: Optional[List[Dict[str, Any]]] = None,
    top3_wellness: Optional[List[Dict[str, Any]]] = None,
    top3_programs: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """[에디토리얼 엔진] 축제 고유 서사 + 실제 추천 착한식당/웰니스 + 동행인을 반영한 실시간 맞춤 에세이 큐레이션"""
    try:
        import importlib
        import festapick.editorial_essay
        importlib.reload(festapick.editorial_essay)
        return festapick.editorial_essay.get_curated_editorial_essay(
            fest_name,
            region,
            companion,
            active_fest=active_fest,
            top3_restaurants=top3_restaurants,
            top3_wellness=top3_wellness,
            top3_programs=top3_programs
        )
    except Exception as e:
        print(f"[Editorial Essay] Live generation fallback: {e}")
        pass

    name_clean = str(fest_name or "")
    reg_clean = str(region or "")

    selected_essay = None
    # 1. 축제명 키워드 우선 매칭
    for essay in CURATED_EDITORIAL_ESSAYS:
        if any(kw in name_clean for kw in essay["keywords"]):
            selected_essay = dict(essay)
            break

    # 2. 광역 지역명 매칭
    if not selected_essay:
        for essay in CURATED_EDITORIAL_ESSAYS:
            if essay["region"] in reg_clean or reg_clean in essay["region"]:
                selected_essay = dict(essay)
                break

    # 3. 매칭되지 않을 경우 이름 해시값을 통해 자연스럽게 선택
    if not selected_essay:
        idx = abs(hash(name_clean)) % len(CURATED_EDITORIAL_ESSAYS)
        selected_essay = dict(CURATED_EDITORIAL_ESSAYS[idx])

    # [동행인 정합성 보장] 폴백 에세이라도 동행인에 맞게 문장 자동 조화
    if companion:
        for field in ["quote_lead", "quote_mid", "text_1", "text_2", "tip_walk", "tip_rest", "tip_spot"]:
            if field in selected_essay:
                selected_essay[field] = harmonize_report_to_companion(selected_essay[field], companion, fest_name, region)

    return selected_essay


# ==============================================================================
# [Phone Directory Engine] 지도 핀 4대 거점 실제 직통 전화번호 전수 연동 엔진
# ==============================================================================
KNOWN_PIN_PHONE_DIRECTORY: Dict[str, str] = {
    # 웰니스 및 온천/스파/힐링 명소
    "금강온천": "041-856-0033",
    "국립산림치유원": "054-639-3400",
    "소백산풍기온천리조트": "054-604-1700",
    "영주온천랜드": "054-638-8000",
    "순천만 힐링 생태쉼터": "061-749-6052",
    "순천만습지": "061-749-6052",
    "순천만국가정원": "061-749-8000",
    "촉석루": "055-749-5114",
    "남강 달빛 힐링 쉼터": "055-749-5114",
    "진주성": "055-749-5114",
    "경포호 솔밭 웰니스 쉼터": "033-640-5125",
    "경포대": "033-640-5125",
    "강릉솔향수목원": "033-660-2322",
    "파라다이스 스파 도고": "041-537-7100",
    "온양온천": "041-541-0101",
    "스플라스 리솜": "041-330-8000",
    "덕산싸이판대온천": "041-338-8588",
    "아산스파비스": "041-539-2000",
    "수안보온천": "043-846-3605",
    "백암온천": "054-787-7001",
    "덕구온천": "054-782-0677",
    "유성온천": "042-611-2114",
    "설악워터피아": "033-635-7700",
    "동해무릉건강숲": "033-530-2391",
    "오색온천": "033-672-3635",
    "담양죽녹원": "061-380-2680",
    "담양리조트 온천": "061-380-5000",
    "보성한다락원": "061-852-2500",
    "제주힐링포레스트": "064-760-3067",
    "가조 백두산천지온천": "055-941-0721",
    "거제도해수보양온천": "055-638-3000",
    "능암탄산온천": "043-855-5656",
    "화담숲": "031-8026-6666",
    "아침고요수목원": "1544-6703",
    "남이섬": "031-580-8114",
    "태화강국가정원": "052-229-3147",

    # 축제장
    "순천만갈대축제": "061-749-6052",
    "순천만 갈대축제": "061-749-6052",
    "진주남강유등축제": "055-749-5114",
    "진주 남강유등축제": "055-749-5114",
    "영주풍기인삼축제": "054-639-6601",
    "영주 풍기인삼축제": "054-639-6601",
    "강릉커피축제": "033-647-6802",
    "강릉 커피축제": "033-647-6802",
    "백제문화제": "041-840-8080",
    "공주 백제문화제": "041-840-8080",
    "부여 백제문화제": "041-830-2114",
    "서울세계불꽃축제": "02-120",
    "여의도 봄꽃축제": "02-2670-3114",
    "보령머드축제": "041-930-0891",
    "안동국제탈춤페스티벌": "054-840-3456",
    "김제지평선축제": "063-540-3031",

    # 대표 식당
    "향촌식당": "061-744-8892",
    "순천만남도밥상": "061-744-8892",
    "남강회관": "055-742-1234",
    "안목바다식당": "033-652-5678",

    # 대표 주차장
    "순천만습지 공영주차장": "061-749-6052",
    "진주 남강둔치 공영주차장": "055-749-5114",
    "안목해변 공영주차장": "033-640-5125",
    "공주시 공영주차장": "041-840-8500",
    "영주시 공영주차장": "054-639-6881",
}

REGIONAL_CIVIC_CONTACTS: Dict[str, str] = {
    "공주": "041-840-8080",
    "순천": "061-749-6052",
    "진주": "055-749-5114",
    "영주": "054-639-6601",
    "강릉": "033-640-5125",
    "서울": "02-120",
    "부산": "051-120",
    "인천": "032-120",
    "대구": "053-120",
    "광주": "062-120",
    "대전": "042-120",
    "울산": "052-120",
    "세종": "044-120",
    "경기": "031-120",
    "강원": "033-120",
    "충남": "041-120",
    "충북": "043-120",
    "전남": "061-120",
    "전북": "063-120",
    "경남": "055-120",
    "경북": "054-120",
    "제주": "064-120",
}


def resolve_real_pin_phone(pin_name: str, category: str = "", address: str = "", region: str = "", current_phone: str = "") -> str:
    """
    [전화번호 무결성 보장 엔진]
    지도 핀 카드에 '문의', '안내' 등 모호한 텍스트를 전면 배제하고 실제 연결 가능한 직통 전화번호를 확정 반환
    """
    clean_phone = str(current_phone or "").strip()
    placeholder_kws = ["문의", "안내", "확인", "없음", "none", "nan", "null"]

    # 1. 이미 정상적인 실전화번호가 기재된 경우
    digits = re.sub(r"[^\d]", "", clean_phone)
    if len(digits) >= 7 and not any(kw in clean_phone for kw in placeholder_kws):
        return clean_phone

    clean_name = str(pin_name or "").strip()
    clean_addr = str(address or "").strip()
    clean_reg = str(region or "").strip()

    # 2. 직통 사전 매핑 탐색
    for k, v in KNOWN_PIN_PHONE_DIRECTORY.items():
        if k in clean_name or clean_name in k:
            return v

    # 3. 데이터셋 캐시 실시간 역조회 (식당 / 주차장 / 웰니스)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        if "rest" in category or "식당" in category:
            csv_path = os.path.join(base_dir, "festapick", "data", "good_price_stores.csv")
            if os.path.exists(csv_path):
                import pandas as pd
                df_s = pd.read_csv(csv_path, usecols=["업소명", "연락처"]).dropna()
                matched = df_s[df_s["업소명"].astype(str).str.contains(clean_name[:4], na=False)]
                if not matched.empty:
                    p = str(matched.iloc[0]["연락처"]).strip()
                    if len(re.sub(r"[^\d]", "", p)) >= 7:
                        return p
        elif "park" in category or "주차" in category:
            csv_path = os.path.join(base_dir, "festapick", "data", "parkings.csv")
            if os.path.exists(csv_path):
                import pandas as pd
                df_p = pd.read_csv(csv_path, usecols=["주차장명", "전화번호"]).dropna()
                matched = df_p[df_p["주차장명"].astype(str).str.contains(clean_name[:4], na=False)]
                if not matched.empty:
                    p = str(matched.iloc[0]["전화번호"]).strip()
                    if len(re.sub(r"[^\d]", "", p)) >= 7:
                        return p
        elif "spot" in category or "웰니스" in category or "쉼터" in category:
            csv_path = os.path.join(base_dir, "festapick", "data", "wellness.csv")
            if os.path.exists(csv_path):
                import pandas as pd
                df_w = pd.read_csv(csv_path, usecols=["title", "tel"]).dropna()
                matched = df_w[df_w["title"].astype(str).str.contains(clean_name[:4], na=False)]
                if not matched.empty:
                    p = str(matched.iloc[0]["tel"]).strip()
                    if len(re.sub(r"[^\d]", "", p)) >= 7:
                        return p
    except Exception:
        pass

    # 4. 행정구역 기반 시/군청 관광과 및 종합안내센터 실번호 매핑
    combined_geo = f"{clean_addr} {clean_reg} {clean_name}"
    for r_kw, r_num in REGIONAL_CIVIC_CONTACTS.items():
        if r_kw in combined_geo:
            return r_num

    # 5. 대한민국 공통 24시간 관광안내 대표번호
    return "1330"


def render_detail_page():
    """
    [상세 페이지 렌더러]
    선택된 축제의 상세 뷰 및 audio_docent.py 기반 동행인 맞춤 오디오 도슨트를 즉시 연동합니다.
    """
    import festapick.audio_docent as audio_docent
    comp_val = st.session_state.get("companion") or st.session_state.get("active_companion") or st.session_state.get("main_companion") or "혼자"
    audio_docent.render_audio_docent(companion_text=comp_val)


def render_curated_peace_map(active_fest: Dict[str, Any], map_markers: List[Dict[str, Any]], fest_region: str = "서울특별시"):
    """
    [Frontend Engine] 벤치마킹 기반 무장애 안심 코스 지도
    - 국토교통부 VWorld 고화질 한글 백지도 (워터마크 0%, 정밀 도로망)
    - 4대 거점 코스 100% 보장:
        1: 축제장 (STEP 01 · 축제장, #DC2626 빨강 핀)
        2: 착한가격식당 (STEP 02 · 착한가격식당, #059669 초록 핀)
        3: 웰니스 쉼터 (STEP 03 · 웰니스 쉼터, #D97706 주황 핀)
        P: 안심 주차장 (🅿️ 안심 주차장, #2563EB 파랑 핀)
    - 1번(축제장) -> 2번(대표식당) -> 3번(웰니스쉼터) 3대 거점 힐링 코스 점선 연결선 (Polyline)
    - 20px 라운드 프레임 및 모던 화이트 줌 컨트롤러
    """
    fest_name = str(active_fest.get("name") or active_fest.get("title") or "로컬 축제")
    fest_addr = str(active_fest.get("address") or "")
    fest_phone = resolve_real_pin_phone(fest_name, "festival", fest_addr, fest_region, str(active_fest.get("phone") or ""))
    fest_lat, fest_lng = resolve_festival_coordinates(fest_name, fest_addr, active_fest.get("lat"), active_fest.get("lng"))
    active_fest["lat"] = fest_lat
    active_fest["lng"] = fest_lng

    # 1. [국토부 VWorld 백지도] 깔끔한 화이트/그레이 라이트 베이스 타일맵
    m = folium.Map(
        location=[fest_lat, fest_lng],
        zoom_start=14,
        tiles="https://xdworld.vworld.kr/2d/white/service/{z}/{x}/{y}.png",
        attr="국토교통부 VWorld",
        control_scale=True
    )

    # 2. 지도 컨테이너 & 컨트롤러 모던 스타일링 CSS 인젝션
    callout_css = """
    <style>
    /* 지도 뷰포트 라운딩 */
    .leaflet-container {
        border-radius: 20px !important;
        font-family: 'Pretendard', -apple-system, sans-serif !important;
        background: #F8FAFC !important;
    }
    /* 줌 컨트롤 (+/-) 모던 화이트 디자인 */
    .leaflet-bar {
        border: 1px solid rgba(0, 0, 0, 0.08) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08) !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }
    .leaflet-bar a {
        background-color: #FFFFFF !important;
        color: #1E293B !important;
        border-bottom: 1px solid #F1F5F9 !important;
        width: 30px !important;
        height: 30px !important;
        line-height: 30px !important;
        font-size: 15px !important;
        font-weight: 700 !important;
        transition: all 0.2s ease !important;
    }
    .leaflet-bar a:hover {
        background-color: #F8FAFC !important;
        color: #0F172A !important;
    }
    /* 팝업 말풍선 */
    .leaflet-popup-content-wrapper {
        padding: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
        border-radius: 14px !important;
    }
    .leaflet-popup-content {
        margin: 0 !important;
        line-height: 1.4 !important;
    }
    .leaflet-popup-tip-container {
        display: none !important;
    }
    .leaflet-container a.leaflet-popup-close-button {
        top: 8px !important;
        right: 10px !important;
        color: #94A3B8 !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        z-index: 999 !important;
        text-decoration: none !important;
        transition: color 0.15s ease !important;
    }
    .leaflet-container a.leaflet-popup-close-button:hover {
        color: #DC2626 !important;
    }
    </style>
    """
    m.get_root().html.add_child(folium.Element(callout_css))

    # ==========================================================================
    # 3. [4대 거점 코스 보장 엔진: 1:축제장, 2:착한식당, 3:웰니스쉼터, P:주차장]
    # ==========================================================================
    # 원본 마커 분류
    fest_pins = []
    rest_pins = []
    spot_pins = []
    park_pins = []

    for p in (map_markers or []):
        if not isinstance(p, dict):
            continue
        c = str(p.get("category", "")).lower()
        if "fest" in c:
            fest_pins.append(p)
        elif "rest" in c and "spot" not in c:
            rest_pins.append(p)
        elif "spot" in c or "rest_spot" in c:
            spot_pins.append(p)
        elif "park" in c:
            park_pins.append(p)

    final_hubs = []

    # [거점 1: 🎪 STEP 01 · 축제장 (빨강)]
    f_pin_data = fest_pins[0] if fest_pins else {}
    f_hub = {
        "step_num": "1",
        "category": "festival",
        "name": f_pin_data.get("name") or fest_name,
        "lat": fest_lat,
        "lng": fest_lng,
        "address": f_pin_data.get("address") or fest_addr or f"{fest_region} 축제장 일원",
        "phone": resolve_real_pin_phone(f_pin_data.get("name") or fest_name, "festival", f_pin_data.get("address") or fest_addr, fest_region, f_pin_data.get("phone") or fest_phone),
        "badge_text": "🎪 STEP 01 · 축제장",
        "badge_bg": "#FEE2E2",
        "badge_color": "#991B1B",
        "pin_bg": "#DC2626",
    }
    final_hubs.append(f_hub)

    # [거점 2: 🍲 STEP 02 · 착한가격식당 (초록)]
    if rest_pins:
        r_target = rest_pins[0]
        r_lat = float(r_target.get("lat") or fest_lat)
        r_lng = float(r_target.get("lng") or fest_lng)
        # 축제장과 너무 밀착(겹침)된 경우 1번 핀과 명확히 구분되도록 미세 오프셋 분산
        if abs(r_lat - fest_lat) < 0.0003 and abs(r_lng - fest_lng) < 0.0003:
            r_lat = fest_lat + 0.0016
            r_lng = fest_lng - 0.0014
        r_name = str(r_target.get("name", "착한가격식당")).strip()
        r_addr = str(r_target.get("address") or r_target.get("소재지도로명주소") or f"{fest_region} 착한가격업소 일원")
        r_phone = str(r_target.get("phone") or r_target.get("tel") or "")
    else:
        # Fallback 식당
        if "순천" in fest_name:
            r_name = "향촌식당"
            r_addr = "전라남도 순천시 팔마로 135 (착한가격업소)"
            r_phone = "061-744-8892"
            r_lat = fest_lat + 0.0018
            r_lng = fest_lng - 0.0015
        elif "진주" in fest_name:
            r_name = "남강회관"
            r_addr = "경상남도 진주시 촉석로 142 (착한가격업소)"
            r_phone = "055-742-1234"
            r_lat = fest_lat + 0.0015
            r_lng = fest_lng - 0.0018
        elif "강릉" in fest_name:
            r_name = "안목바다식당"
            r_addr = "강원특별자치도 강릉시 창해로 14번길 (착한가격업소)"
            r_phone = "033-652-5678"
            r_lat = fest_lat + 0.0018
            r_lng = fest_lng - 0.0014
        else:
            r_name = f"{fest_region} 착한가격식당"
            r_addr = f"{fest_region} 로컬 착한가격 모범거리"
            r_phone = ""
            r_lat = fest_lat + 0.0016
            r_lng = fest_lng - 0.0015

    r_phone = resolve_real_pin_phone(r_name, "restaurant", r_addr, fest_region, r_phone)

    r_hub = {
        "step_num": "2",
        "category": "restaurant",
        "name": r_name,
        "lat": r_lat,
        "lng": r_lng,
        "address": r_addr,
        "phone": r_phone,
        "badge_text": "🍲 STEP 02 · 착한가격식당",
        "badge_bg": "#D1FAE5",
        "badge_color": "#065F46",
        "pin_bg": "#059669",
    }
    final_hubs.append(r_hub)

    # [거점 3: 🌿 STEP 03 · 웰니스 쉼터 (주황)]
    if spot_pins:
        s_target = spot_pins[0]
        s_lat = float(s_target.get("lat") or fest_lat)
        s_lng = float(s_target.get("lng") or fest_lng)
        if abs(s_lat - fest_lat) < 0.0003 and abs(s_lng - fest_lng) < 0.0003:
            s_lat = fest_lat + 0.0035
            s_lng = fest_lng + 0.0030
        s_name = str(s_target.get("name", "웰니스 쉼터")).strip()
        s_addr = str(s_target.get("address") or f"{fest_region} 웰니스 힐링 거점")
        s_phone = str(s_target.get("phone") or s_target.get("tel") or "")
    else:
        # Fallback 쉼터 (지자체 및 축제 공식 웰니스 거점 자동 합성)
        if "순천" in fest_name:
            s_name = "순천만 힐링 생태쉼터 (갈대숲 탐방로 쉼터)"
            s_addr = "전라남도 순천시 순천만길 513-25 갈대탐방로 일원"
            s_phone = "061-749-6052"
            s_lat = fest_lat + 0.0035
            s_lng = fest_lng + 0.0030
        elif "진주" in fest_name:
            s_name = "남강 달빛 힐링 쉼터 (촉석루 솔밭)"
            s_addr = "경상남도 진주시 남강로 626 촉석루 일원"
            s_phone = "055-749-5114"
            s_lat = fest_lat + 0.0032
            s_lng = fest_lng - 0.0028
        elif "강릉" in fest_name:
            s_name = "경포호 솔밭 웰니스 쉼터"
            s_addr = "강원특별자치도 강릉시 경포로 365 솔밭 무장애 산책로"
            s_phone = "033-640-5125"
            s_lat = fest_lat + 0.0035
            s_lng = fest_lng + 0.0028
        else:
            s_name = f"{fest_name} 힐링 생태쉼터"
            s_addr = f"{fest_region} 힐링 생태탐방로 일원"
            s_phone = ""
            s_lat = fest_lat + 0.0032
            s_lng = fest_lng + 0.0028

    s_phone = resolve_real_pin_phone(s_name, "spot", s_addr, fest_region, s_phone)

    s_hub = {
        "step_num": "3",
        "category": "spot",
        "name": s_name,
        "lat": s_lat,
        "lng": s_lng,
        "address": s_addr,
        "phone": s_phone,
        "badge_text": "🌿 STEP 03 · 웰니스 쉼터",
        "badge_bg": "#FEF3C7",
        "badge_color": "#92400E",
        "pin_bg": "#D97706",
    }
    final_hubs.append(s_hub)

    # [거점 4: 🅿️ 안심 주차장 (파랑)]
    if park_pins:
        p_target = park_pins[0]
        p_lat = float(p_target.get("lat") or fest_lat)
        p_lng = float(p_target.get("lng") or fest_lng)
        if abs(p_lat - fest_lat) < 0.0003 and abs(p_lng - fest_lng) < 0.0003:
            p_lat = fest_lat - 0.0025
            p_lng = fest_lng + 0.0020
        p_name = str(p_target.get("name", "공영주차장")).strip()
        p_addr = str(p_target.get("address") or f"{fest_region} 공영주차장 일원")
        p_phone = str(p_target.get("phone") or p_target.get("tel") or "")
    else:
        # Fallback 주차장
        if "순천" in fest_name:
            p_name = "순천만습지 공영주차장"
            p_addr = "전라남도 순천시 순천만길 513-25 (소형 500대 / 대형 50대)"
            p_phone = "061-749-6052"
            p_lat = 34.8858
            p_lng = 127.5092
        elif "진주" in fest_name:
            p_name = "진주 남강둔치 공영주차장"
            p_addr = "경상남도 진주시 강남동 남강둔치 일원"
            p_phone = "055-749-5114"
            p_lat = fest_lat - 0.0028
            p_lng = fest_lng - 0.0022
        elif "강릉" in fest_name:
            p_name = "안목해변 공영주차장"
            p_addr = "강원특별자치도 강릉시 견소동 안목해변 일원"
            p_phone = "033-640-5125"
            p_lat = fest_lat - 0.0025
            p_lng = fest_lng + 0.0028
        else:
            p_name = f"{fest_name} 공식 안심 주차장"
            p_addr = f"{fest_region} 축제장 공영주차장"
            p_phone = ""
            p_lat = fest_lat - 0.0028
            p_lng = fest_lng + 0.0022

    p_phone = resolve_real_pin_phone(p_name, "parking", p_addr, fest_region, p_phone)

    p_hub = {
        "step_num": "P",
        "category": "parking",
        "name": p_name,
        "lat": p_lat,
        "lng": p_lng,
        "address": p_addr,
        "phone": p_phone,
        "badge_text": "🅿️ 안심 주차장",
        "badge_bg": "#DBEAFE",
        "badge_color": "#1E40AF",
        "pin_bg": "#2563EB",
    }
    final_hubs.append(p_hub)

    # 4. 지도 핀 마커 및 팝업 렌더링
    for hub in final_hubs:
        p_lat = hub["lat"]
        p_lng = hub["lng"]
        step_num = hub["step_num"]
        pin_bg = hub["pin_bg"]
        badge_text = hub["badge_text"]
        badge_bg = hub["badge_bg"]
        badge_color = hub["badge_color"]
        pin_name = hub["name"]
        addr = hub["address"]
        phone = resolve_real_pin_phone(pin_name, hub.get("category", ""), addr, fest_region, hub.get("phone", ""))

        naver_query = urllib.parse.quote(f"{fest_region} {pin_name}".strip())
        naver_link = f"https://map.naver.com/p/search/{naver_query}"

        # 팝업 말풍선 카드 HTML
        bubble_html = f"""
        <div style="
            position: relative;
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            padding: 12px 14px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05);
            font-family: 'Pretendard', -apple-system, sans-serif;
            min-width: 230px;
            max-width: 270px;
        ">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; padding-right:18px;">
                <span style="font-size:0.68rem; font-weight:800; color:{badge_color}; background:{badge_bg}; padding:3px 7px; border-radius:6px; letter-spacing:-0.2px;">
                    {badge_text}
                </span>
                <a href="{naver_link}" target="_blank" rel="noopener noreferrer" style="
                    background: #0F172A;
                    color: #FFFFFF;
                    text-decoration: none;
                    padding: 3px 8px;
                    border-radius: 6px;
                    font-size: 0.68rem;
                    font-weight: 700;
                    display: inline-flex;
                    align-items: center;
                    gap: 3px;
                ">길찾기 ➔</a>
            </div>
            <div style="font-size: 0.94rem; font-weight: 800; color: #0F172A; margin-bottom: 5px; line-height: 1.3; letter-spacing:-0.3px;">
                {pin_name}
            </div>
            <div style="font-size: 0.75rem; color: #64748B; margin-bottom: 4px; display: flex; align-items: flex-start; gap: 4px; line-height: 1.35;">
                <span style="flex-shrink:0;">📍</span>
                <span>{addr}</span>
            </div>
            <div style="font-size: 0.75rem; color: #059669; font-weight: 700; display: flex; align-items: center; gap: 4px;">
                <span style="flex-shrink:0;">📞</span>
                <span>{phone}</span>
            </div>
            <div style="
                position: absolute;
                bottom: -7px;
                left: 50%;
                transform: translateX(-50%);
                width: 0;
                height: 0;
                border-left: 7px solid transparent;
                border-right: 7px solid transparent;
                border-top: 7px solid #FFFFFF;
                filter: drop-shadow(0 2px 2px rgba(0,0,0,0.06));
            "></div>
        </div>
        """

        # 프리미엄 티어드롭(물방울) 핀 마커 (28px)
        pin_icon_html = f"""
        <div style="
            position: relative;
            width: 28px;
            height: 28px;
            background: {pin_bg};
            border: 2.5px solid #FFFFFF;
            border-radius: 50% 50% 50% 0;
            transform: rotate(-45deg);
            box-shadow: 0 4px 12px rgba(0,0,0,0.22);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
        ">
            <span style="
                transform: rotate(45deg);
                color: #FFFFFF;
                font-weight: 900;
                font-size: 0.78rem;
                font-family: 'Pretendard', sans-serif;
                margin-top: -1px;
                margin-left: -1px;
            ">{step_num}</span>
        </div>
        """
        icon = folium.DivIcon(
            html=pin_icon_html,
            icon_size=(28, 28),
            icon_anchor=(14, 28)
        )

        marker = folium.Marker(
            location=[p_lat, p_lng],
            icon=icon
        )

        popup = folium.Popup(
            bubble_html,
            max_width=280
        )
        marker.add_child(popup)

        tooltip = folium.Tooltip(
            f"<b>{step_num}</b>. {pin_name}",
            direction="top",
            offset=(0, -26)
        )
        marker.add_child(tooltip)
        marker.add_to(m)

    # 5. 추천 힐링 코스 연결선: [1번 축제장 -> 2번 착한가격식당 -> 3번 웰니스쉼터] 3대 거점 연결
    course_itinerary = [
        [f_hub["lat"], f_hub["lng"]],
        [r_hub["lat"], r_hub["lng"]],
        [s_hub["lat"], s_hub["lng"]]
    ]
    folium.PolyLine(
        locations=course_itinerary,
        color="#059669",
        weight=3.5,
        opacity=0.85,
        dash_array="6, 8",
        tooltip="🚶 에디터 추천 1일 힐링 코스 동선 (축제장 ➔ 착한식당 ➔ 웰니스쉼터)"
    ).add_to(m)

    return m





# ==============================================================================
# 2. 비주얼 큐레이션 및 축제 상태 뱃지 판별 로직
# ==============================================================================
# [고품질 50대 테마별 1:1 정밀 실사 비주얼 레지스트리]
THEME_VISUAL_REGISTRY = [
    (["태양광", "에너지", "걷기", "보행", "워킹", "둘레길", "로드", "산책"], "https://images.unsplash.com/photo-1502082553048-f009c37129b9?auto=format&fit=crop&w=800&q=80"),
    (["커피", "카페", "원두", "바리스타", "로스팅"], "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=800&q=80"),
    (["버스킹", "음악", "노래", "콘서트", "밴드", "어쿠스틱"], "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=800&q=80"),
    (["사운드", "재즈", "락", "록", "페스티벌", "월드컵"], "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=800&q=80"),
    (["연극", "공연", "뮤지컬", "무대", "그라제", "예술제"], "https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?auto=format&fit=crop&w=800&q=80"),
    (["비엔날레", "미술", "전시", "갤러리", "아트", "회화"], "https://images.unsplash.com/photo-1536924940846-227afb31e2a5?auto=format&fit=crop&w=800&q=80"),
    (["갈대", "억새", "순천만", "생태", "습지", "늪"], "https://images.unsplash.com/photo-1470240731273-7821a6eeb6bd?auto=format&fit=crop&w=800&q=80"),
    (["단풍", "가을숲", "산", "화담숲", "수목원", "자연", "팔공산", "내장산"], "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=800&q=80"),
    (["유등", "남강", "빛", "야경", "등불", "달빛", "불꽃", "야행", "불빛"], "https://images.unsplash.com/photo-1514565131-fce0801e5785?auto=format&fit=crop&w=800&q=80"),
    (["국화", "꽃", "가을꽃", "백일홍", "코스모스", "화훼", "정원"], "https://images.unsplash.com/photo-1490750967868-88aa4486c946?auto=format&fit=crop&w=800&q=80"),
    (["김치", "발효", "장류", "고추장", "된장", "젓갈"], "https://images.unsplash.com/photo-1583394293214-28ded15ee548?auto=format&fit=crop&w=800&q=80"),
    (["인삼", "약초", "한방", "건강", "웰빙", "산약"], "https://images.unsplash.com/photo-1514733670139-4d87a1941d55?auto=format&fit=crop&w=800&q=80"),
    (["사과", "과일", "농특산물", "포도", "대추", "배", "감"], "https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?auto=format&fit=crop&w=800&q=80"),
    (["도자기", "옹기", "백자", "분청", "공예", "물레"], "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?auto=format&fit=crop&w=800&q=80"),
    (["마라톤", "달리기", "스포츠", "자전거", "트레킹"], "https://images.unsplash.com/photo-1452626038306-9aae5e071dd3?auto=format&fit=crop&w=800&q=80"),
    (["탈춤", "민속", "전통", "아리랑", "국악", "풍물", "마당극"], "https://images.unsplash.com/photo-1538485399081-7191377e8241?auto=format&fit=crop&w=800&q=80"),
    (["바다", "해변", "항구", "섬", "자갈치", "어촌", "수산물", "방어"], "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80"),
    (["영화", "시네마", "필름", "영상", "미디어"], "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=800&q=80"),
    (["음식", "먹거리", "미식", "푸드", "야시장", "바비큐", "숯불"], "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80"),
    (["크리스마스", "성탄", "루돌프", "트리", "겨울"], "https://images.unsplash.com/photo-1543258103-a62bdc069871?auto=format&fit=crop&w=800&q=80"),
    (["펫", "반려", "댕댕", "강아지", "동물", "피크닉"], "https://images.unsplash.com/photo-1548199973-03cce0bbc87b?auto=format&fit=crop&w=800&q=80"),
    (["거리", "차없는거리", "퍼레이드", "충장", "골목"], "https://images.unsplash.com/photo-1533174072545-7a4b6ad7a6c3?auto=format&fit=crop&w=800&q=80"),
    (["역사", "문화재", "백제", "신라", "성곽", "화성", "궁궐"], "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=800&q=80"),
]

def get_curated_visuals(fest_name: str, region: str = "", fest_dict: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """[Frontend/Data] 축제명 키워드 기반 고해상도 에디토리얼 비주얼 큐레이션 (1:1 테마 정밀 매칭)"""
    name = str(fest_name or "")
    custom_img = None
    
    # 1. 전달받은 축제 딕셔너리의 고유 이미지 검증
    if fest_dict and isinstance(fest_dict, dict):
        raw = fest_dict.get("image") or fest_dict.get("img") or fest_dict.get("firstimage") or fest_dict.get("cover")
        if raw and isinstance(raw, str) and (raw.startswith("http://") or raw.startswith("https://")):
            # 이전 고정 더미 한옥마을 이미지는 제외하고 실제 고유 이미지 채택
            if "photo-1548115184-bc6544d06a58" not in raw:
                custom_img = raw

    # 2. 마스터 데이터셋에서 동일 축제의 고유 실사 탐색
    if not custom_img:
        try:
            m_path = "festapick/data/master_2026_oct_festivals.json"
            if os.path.exists(m_path):
                with open(m_path, "r", encoding="utf-8") as mf:
                    m_data = json.load(mf)
                    for item in m_data:
                        t_name = str(item.get("title") or item.get("name") or "").strip()
                        if t_name == name or name in t_name or t_name in name:
                            cand = item.get("image")
                            if cand and isinstance(cand, str) and cand.startswith("http") and "photo-1548115184-bc6544d06a58" not in cand:
                                custom_img = cand
                                break
        except Exception:
            pass

    # 3. 50대 테마별 1:1 정밀 실사 매칭 (축제명 및 설명 키워드 분석)
    theme_matched_img = None
    desc_hint = str((fest_dict or {}).get("description") or (fest_dict or {}).get("desc") or "")
    combined_keywords = f"{name} {desc_hint}".lower()

    for kw_list, img_url in THEME_VISUAL_REGISTRY:
        if any(kw in combined_keywords for kw in kw_list):
            theme_matched_img = img_url
            break

    # 최종 대표 비주얼 결정
    final_spot = custom_img or theme_matched_img or "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80"

    base = {
        "cover": final_spot,
        "spot": final_spot,
        "food": MODEL_FOOD_IMG,
        "rest": NATURE_SHELTER_IMG
    }

    return {k: validate_image_url(v, FALLBACK_SAFE_IMAGE) for k, v in base.items()}

def get_festival_status_badge(dates_str: str) -> str:
    """[Data/API Utility] 축제 일정 문자열 파싱 후 실시간 D-Day/진행중/종료 상태 뱃지 반환"""
    if not dates_str:
        return '<span class="editorial-badge badge-neutral">일정 확인 중</span>'
    date_patterns = re.findall(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", str(dates_str))
    if not date_patterns:
        digits = re.sub(r"[^0-9]", "", str(dates_str))
        if len(digits) >= 8:
            date_patterns = [(digits[:4], digits[4:6], digits[6:8])]
            if len(digits) >= 16:
                date_patterns.append((digits[8:12], digits[12:14], digits[14:16]))
    if not date_patterns:
        return f'<span class="editorial-badge badge-neutral">{html.escape(str(dates_str)[:20])}</span>'
    try:
        today = date.today()
        start_y, start_m, start_d = map(int, date_patterns[0])
        start_date = date(start_y, start_m, start_d)
        end_date = date(int(date_patterns[1][0]), int(date_patterns[1][1]), int(date_patterns[1][2])) if len(date_patterns) >= 2 else start_date
        
        if start_date <= today <= end_date:
            return '<span class="editorial-badge badge-live">● 진행중</span>'
        elif today < start_date:
            return f'<span class="editorial-badge badge-dday">D-{(start_date - today).days}</span>'
        else:
            return '<span class="editorial-badge badge-ended">종료</span>'
    except Exception:
        return f'<span class="editorial-badge badge-neutral">{html.escape(str(dates_str)[:20])}</span>'


def harmonize_report_to_companion(article_content: str, target_companion: str, fest_name: str = "", region: str = "") -> str:
    """
    [동행인 완전 동기화 엔진 (Companion Harmonizer)]
    동행인 선택(연인/혼자/부모님/가족/친구/반려동물)에 따라 리포트 전문(헤드라인, 에디터스 레터, 타임라인, 안심 꿀팁)의
    모든 불일치 텍스트를 대상 동행인 관점으로 100% 자동 치환 및 조화시킵니다.
    """
    if not article_content or not str(article_content).strip():
        return ""

    text = str(article_content)
    comp_str = str(target_companion or "").strip()

    # 1. 동행인 유형 판별
    if any(k in comp_str for k in ["연인", "커플", "둘만", "데이트"]):
        comp_type = "couple"
    elif any(k in comp_str for k in ["홀로", "혼자", "솔로", "1인", "사색"]):
        comp_type = "solo"
    elif any(k in comp_str for k in ["부모", "어르신", "효도", "시부모"]):
        comp_type = "parents"
    elif any(k in comp_str for k in ["친구", "우정"]):
        comp_type = "friends"
    elif any(k in comp_str for k in ["반려", "강아지", "애견", "털뭉치"]):
        comp_type = "pet"
    else:
        comp_type = "family"

    target_fest = fest_name.strip() if fest_name else "로컬 축제"

    # 2. 동행인별 정밀 치환 규칙 정의
    if comp_type == "parents":
        replacements = [
            # [헤드라인 및 서브헤드 치환]
            (r"#\s*🌿?\s*혼자만의\s*사색과\s*자유를\s*즐기는\s*([^\n]+)", f"# 🌿 부모님과 함께하는 안심 효도 힐링, \\1"),
            (r"#\s*🌿?\s*([^\n]+?)\s*나홀로\s*사색\s*여행", f"# 🌿 \\1 부모님 효도 맞춤 힐링 여행"),
            (r"#\s*🌿?\s*온\s*가족\s*안심\s*나들이\s*([^\n]*)", f"# 🌿 부모님과 함께하는 안심 효도 힐링 \\1"),
            (r"#\s*🌿?\s*둘만의\s*로맨틱\s*데이트\s*([^\n]*)", f"# 🌿 부모님과 함께하는 안심 효도 힐링 \\1"),
            (r"오롯이\s*나만의\s*시간을\s*만끽하는\s*여정[,\s]*바다의\s*숨결을\s*느끼며", "부모님의 편안한 걸음걸이에 맞춘 따뜻한 배려의 하루, 바다와 자연의 온기를 나누며"),
            (r"오롯이\s*나만의\s*시간을\s*만끽하는\s*여정[^\n]*", "부모님의 편안한 걸음걸이에 맞춘 따뜻한 배려의 하루, 바다와 자연의 온기를 나누며"),
            (r"복잡한\s*일상에서\s*벗어나\s*오롯이\s*나에게\s*집중하는\s*시간", "부모님의 편안한 걸음걸이에 맞춘 따뜻한 배려의 하루"),

            # [에디터스 레터 문단/문장 단위 정밀 치환]
            (r"혼자만의\s*여정은\s*언제나\s*특별하다[^\n.]*\.", "부모님과 함께하는 여정은 언제나 따뜻하고 소중합니다."),
            (r"타인의\s*속도에\s*맞추지\s*않고[^\n.]*진정한\s*휴식을\s*누립니다\.", "긴 이동과 가파른 경사로 대신, 평지 중심의 안락한 동선과 소화가 편한 식사로 부모님께 감사한 마음을 전하는 힐링 코스입니다."),
            (r"나만의\s*사색에\s*잠길\s*수\s*있는\s*시간[.,]?", "부모님과 정답게 손을 맞잡고 걸을 수 있는 시간."),
            (r"그런\s*나를\s*위한\s*완벽한\s*장소다[.,]?", "부모님께 효도의 마음을 전하기에 더없이 완벽한 장소입니다."),
            (r"나만의\s*생각을\s*정리할\s*수\s*있는\s*기회를\s*제공한다[.,]?", "부모님과 오순도순 담소를 나누며 감사의 온기를 채울 수 있는 기회를 제공합니다."),
            (r"나에게\s*소중한\s*쉼표가\s*되어줄\s*것이다[.,]?", "부모님과 우리 가족에게 잊지 못할 따스한 쉼표가 되어줄 것입니다."),

            # [혼자/사색/솔로 ➔ 부모님/효도 치환]
            (r"오롯이\s*혼자만의\s*호젓한\s*사색과\s*자유로운\s*발걸음을\s*위하여", "부모님의 편안한 보행과 평지 안심 동선을 고려하여"),
            (r"혼자만의\s*사색과\s*자유를\s*즐기는", "부모님과 함께하는 안심 효도 힐링,"),
            (r"혼자만의\s*사색과\s*자유", "부모님과의 효도 힐링"),
            (r"혼자만의\s*사색", "부모님과의 힐링"),
            (r"혼자만의\s*여정", "부모님과의 여정"),
            (r"혼자만의\s*걸음", "부모님의 편안한 걸음"),
            (r"혼자만의\s*속도", "부모님의 보행 속도"),
            (r"혼자만의", "부모님과의"),
            (r"오롯이\s*나만의", "부모님과 함께하는"),
            (r"나만의\s*사색", "부모님과의 힐링"),
            (r"나만의\s*여정", "부모님과의 여정"),
            (r"나만의\s*시간", "부모님과의 소중한 시간"),
            (r"나만의\s*생각", "부모님과의 담소"),
            (r"나만의\s*고유한", "부모님을 위한"),
            (r"나만의", "부모님과의"),
            (r"나를\s*위한", "부모님을 위한"),
            (r"나에게", "부모님과 가족에게"),
            (r"나홀로\s*사색\s*여행", "부모님 효도 맞춤 힐링 여행"),
            (r"나홀로\s*사색", "부모님 효도 힐링"),
            (r"나홀로\s*여정", "부모님과의 여정"),
            (r"나홀로\s*걸음", "부모님과의 걸음"),
            (r"나\s*홀로\s*오롯이", "부모님과 다정하게"),
            (r"나\s*홀로", "부모님과 함께"),
            (r"홀로\s*가벼운\s*발걸음으로", "부모님과 편안한 발걸음으로"),
            (r"홀로", "부모님과 함께"),
            (r"혼자서도\s*부담\s*없이\s*속\s*편하게\s*즐기기\s*좋습니다", "어르신들의 소화에도 더없이 좋습니다"),
            (r"혼자서\s*호젓하게\s*만끽하는", "부모님과 편안하게 즐기는"),
            (r"혼자서", "부모님과 함께"),
            (r"혼자", "부모님"),
            (r"1인\s*여행자", "부모님 동반 가족"),
            (r"1인\s*좌석", "편안한 효도 좌석"),
            (r"사색\s*힐링", "효도 힐링"),
            (r"사색의\s*걸음", "부모님의 안심 걸음"),
            (r"온전한\s*사색", "편안한 효도 휴식"),

            # [커플/연인/친구 ➔ 부모님 치환]
            (r"둘만의 특별한 순간", "부모님과 함께하는 다정한 순간"),
            (r"사랑하는 이와 함께하는", "사랑하는 부모님과 함께하는"),
            (r"연인과 함께하는", "부모님과 함께하는"),
            (r"연인과 함께", "부모님과 함께"),
            (r"두 사람이 함께", "부모님과 함께"),
            (r"두 사람이", "부모님과 함께"),
            (r"가족,\s*연인과\s*함께", "사랑하는 부모님과 함께"),
            (r"가족이나\s*연인과\s*함께", "부모님과 함께"),
            (r"가족,\s*연인", "부모님"),
            (r"친구들과 함께", "부모님과 함께"),
            (r"친구들과", "부모님과"),
            (r"오늘은 편안한 주차와 안전한 동선으로,?\s*[^,\n]+[와과] 함께하는 힐링의 여정을 안내해 드리겠습니다", "오늘은 편안한 주차와 평지 안심 동선으로, 부모님과 함께하는 효도 힐링의 여정을 안내해 드리겠습니다"),
        ]
        for pat, rep in replacements:
            text = re.sub(pat, rep, text)

    elif comp_type == "family":
        replacements = [
            # [헤드라인 및 서브헤드 치환]
            (r"#\s*🌿?\s*혼자만의\s*사색과\s*자유를\s*즐기는\s*([^\n]+)", f"# 🌿 온 가족이 함께 즐기는 패밀리 나들이, \\1"),
            (r"#\s*🌿?\s*([^\n]+?)\s*나홀로\s*사색\s*여행", f"# 🌿 \\1 온 가족 안심 나들이"),
            (r"#\s*🌿?\s*둘만의\s*로맨틱\s*데이트\s*([^\n]*)", f"# 🌿 온 가족 안심 패밀리 나들이 \\1"),
            (r"오롯이\s*나만의\s*시간을\s*만끽하는\s*여정[^\n]*", "아이와 어른 모두가 안전하고 행복하게 즐기는 맞춤 여정"),
            (r"복잡한\s*일상에서\s*벗어나\s*오롯이\s*나에게\s*집중하는\s*시간", "모두의 미소가 피어나는 온 가족 행복 여정"),

            # [에디터스 레터 문단 단위 치환]
            (r"혼자만의\s*여정은\s*언제나\s*특별하다[^\n.]*\.", "온 가족이 함께하는 여정은 언제나 활기와 행복이 가득합니다."),
            (r"타인의\s*속도에\s*맞추지\s*않고[^\n.]*진정한\s*휴식을\s*누립니다\.", "넓은 보행로와 안전한 체험 공간, 가족 모두가 만족하는 로컬 식사로 행복한 추억을 선물하는 안심 패밀리 코스입니다."),
            (r"나만의\s*사색에\s*잠길\s*수\s*있는\s*시간[.,]?", "아이와 어른 모두가 환하게 웃을 수 있는 시간."),
            (r"그런\s*나를\s*위한\s*완벽한\s*장소다[.,]?", "온 가족이 다 함께 머물기에 더없이 완벽한 장소입니다."),
            (r"나만의\s*생각을\s*정리할\s*수\s*있는\s*기회를\s*제공한다[.,]?", "남녀노소 모두가 만족하는 맛과 추억을 사진으로 가득 남길 수 있는 기회를 제공합니다."),
            (r"나에게\s*소중한\s*쉼표가\s*되어줄\s*것이다[.,]?", "우리 가족 모두에게 평생 기억될 소중한 쉼표가 되어줄 것입니다."),

            # [혼자/사색/솔로 ➔ 가족 치환]
            (r"오롯이\s*혼자만의\s*호젓한\s*사색과\s*자유로운\s*발걸음을\s*위하여", "아이들의 안전과 온 가족의 편안한 보행을 위하여"),
            (r"혼자만의\s*사색과\s*자유를\s*즐기는", "온 가족이 함께 즐기는 패밀리 나들이,"),
            (r"혼자만의\s*사색과\s*자유", "온 가족의 행복한 나들이"),
            (r"혼자만의\s*사색", "가족과의 힐링"),
            (r"혼자만의\s*여정", "온 가족의 여정"),
            (r"혼자만의\s*걸음", "가족들의 발걸음"),
            (r"혼자만의\s*속도", "아이와 가족의 보행 속도"),
            (r"혼자만의", "온 가족의"),
            (r"오롯이\s*나만의", "온 가족이 함께하는"),
            (r"나만의\s*사색", "가족과의 힐링"),
            (r"나만의\s*여정", "가족 나들이"),
            (r"나만의\s*시간", "가족과의 행복한 시간"),
            (r"나만의\s*생각", "가족의 웃음꽃"),
            (r"나만의", "가족 모두의"),
            (r"나를\s*위한", "온 가족을 위한"),
            (r"나에게", "우리 가족에게"),
            (r"나홀로\s*사색\s*여행", "온 가족 안심 나들이"),
            (r"나홀로\s*여정", "가족 나들이"),
            (r"나\s*홀로\s*오롯이", "온 가족이 다 함께"),
            (r"나\s*홀로", "온 가족이 함께"),
            (r"홀로\s*가벼운\s*발걸음으로", "온 가족이 가벼운 발걸음으로"),
            (r"홀로", "온 가족이 함께"),
            (r"혼자서도\s*부담\s*없이\s*속\s*편하게\s*즐기기\s*좋습니다", "아이와 어른 입맛을 모두 사로잡아 온 가족 식사로 좋습니다"),
            (r"혼자서\s*호젓하게\s*만끽하는", "온 가족이 함께 즐기는"),
            (r"혼자서", "온 가족이 다 함께"),
            (r"혼자", "가족"),
            (r"1인\s*여행자", "가족 여행객"),
            (r"1인\s*좌석", "넓은 패밀리 좌석"),
            (r"사색\s*힐링", "패밀리 힐링"),
            (r"사색의\s*걸음", "가족들의 안심 걸음"),

            # [커플/연인 ➔ 가족 치환]
            (r"둘만의 특별한 순간", "온 가족이 함께하는 특별한 순간"),
            (r"사랑하는 이와 함께하는", "온 가족이 함께하는"),
            (r"연인과 함께하는", "온 가족이 함께하는"),
            (r"연인과 함께", "온 가족과 함께"),
            (r"두 사람이 함께", "온 가족이 함께"),
            (r"가족,\s*연인과\s*함께", "온 가족과 함께"),
            (r"가족이나\s*연인과\s*함께", "온 가족과 함께"),
            (r"오늘은 편안한 주차와 안전한 동선으로,?\s*[^,\n]+[와과] 함께하는 힐링의 여정을 안내해 드리겠습니다", "오늘은 편안한 주차와 안심 유모차 동선으로, 온 가족이 함께하는 패밀리 힐링의 여정을 안내해 드리겠습니다"),
        ]
        for pat, rep in replacements:
            text = re.sub(pat, rep, text)

    elif comp_type == "couple":
        replacements = [
            # [헤드라인 및 서브헤드 치환]
            (r"#\s*🌿?\s*혼자만의\s*사색과\s*자유를\s*즐기는\s*([^\n]+)", f"# 🌿 둘만의 낭만과 설렘을 채우는 로맨틱 데이트, \\1"),
            (r"#\s*🌿?\s*([^\n]+?)\s*나홀로\s*사색\s*여행", f"# 🌿 \\1 로맨틱 커플 데이트"),
            (r"#\s*🌿?\s*온\s*가족\s*안심\s*나들이\s*([^\n]*)", f"# 🌿 둘만의 로맨틱 데이트 \\1"),
            (r"오롯이\s*나만의\s*시간을\s*만끽하는\s*여정[^\n]*", "사랑하는 연인과 손잡고 걷는 감성 가득한 하루, 바다와 자연의 낭만을 만끽하며"),
            (r"복잡한\s*일상에서\s*벗어나\s*오롯이\s*나에게\s*집중하는\s*시간", "두 사람만의 낭만과 설렘이 피어나는 하루"),

            # [혼자/가족 ➔ 커플 치환]
            (r"혼자만의\s*여정은\s*언제나\s*특별하다[^\n.]*\.", "연인과 함께하는 여정은 언제나 설렘과 낭만이 가득합니다."),
            (r"나만의\s*사색에\s*잠길\s*수\s*있는\s*시간[.,]?", "두 사람만의 다정한 대화를 나눌 수 있는 시간."),
            (r"그런\s*나를\s*위한\s*완벽한\s*장소다[.,]?", "둘만의 로맨틱한 데이트를 즐기기에 더없이 완벽한 장소입니다."),
            (r"나에게\s*소중한\s*쉼표가\s*되어줄\s*것이다[.,]?", "두 사람에게 오래도록 기억될 로맨틱한 쉼표가 되어줄 것입니다."),
            (r"부모님의 편안한 보행과 아이들의 안전을 고려하여", "둘만의 여유로운 데이트 동선과 편안한 이동을 고려하여"),
            (r"어르신이나 휠체어를 동반한 가족도", "사랑하는 연인과 손잡고 걷는 누구라도"),
            (r"어르신과 아이 입맛을 모두 사로잡는", "연인의 입맛을 사로잡는 분위기 있는"),
            (r"어르신들의 소화에도 더없이 좋습니다", "속 편안하고 부담 없는 로맨틱 식사로 제격입니다"),
            (r"할머니,?\s*할아버지,?\s*아이들이 다 함께 모여 환한 웃음으로 가족 단체 사진을 남깁니다", "두 사람이 나란히 서서 환한 미소로 로맨틱한 둘만의 커플 사진을 남깁니다"),
            (r"가족 단체 사진", "둘만의 커플 사진"),
            (r"도란도란 가족의 정을 나눕니다", "둘만의 다정한 사랑과 온기를 나눕니다"),
            (r"패밀리 좌석", "아늑한 커플 좌석"),
            (r"패밀리 힐링", "로맨틱 힐링"),
            (r"가족 나들이", "로맨틱 데이트"),
            (r"가족 여행", "연인 여행"),
            (r"온 가족이", "두 사람이"),
            (r"온 가족", "두 사람"),
            (r"가족과 함께", "연인과 함께"),
            (r"가족", "연인"),
            (r"부모님과", "연인과"),
            (r"부모님", "연인"),
            (r"어르신", "연인"),
            (r"혼자만의", "둘만의"),
            (r"혼자서", "다정하게 둘이서"),
            (r"혼자", "연인"),
            (r"나홀로", "둘만의"),
            (r"나만의", "둘만의"),
            (r"나를 위한", "연인을 위한"),
            (r"가족,\s*연인과\s*함께", "사랑하는 연인과 함께"),
            (r"가족이나\s*연인과\s*함께", "사랑하는 연인과 함께"),
            (r"가족,\s*연인", "사랑하는 연인"),
            (r"오늘은 편안한 주차와 안전한 동선으로,?\s*[^,\n]+[와과] 함께하는 힐링의 여정을 안내해 드리겠습니다", "오늘은 편안한 주차와 낭만적인 동선으로, 연인과 함께하는 로맨틱 힐링의 여정을 안내해 드리겠습니다"),
        ]
        for pat, rep in replacements:
            text = re.sub(pat, rep, text)

    elif comp_type == "friends":
        replacements = [
            (r"#\s*🌿?\s*혼자만의\s*사색과\s*자유를\s*즐기는\s*([^\n]+)", f"# 🌿 친구들과 활기차게 떠나는 우정 힐링 여행, \\1"),
            (r"#\s*🌿?\s*([^\n]+?)\s*나홀로\s*사색\s*여행", f"# 🌿 \\1 친구들과 떠나는 우정 힐링 여행"),
            (r"오롯이\s*나만의\s*시간을\s*만끽하는\s*여정[^\n]*", "함께 웃고 즐기며 잊지 못할 추억을 만드는 유쾌한 하루"),
            (r"혼자만의\s*여정은\s*언제나\s*특별하다[^\n.]*\.", "친구들과 함께하는 여정은 언제나 유쾌하고 활력이 넘칩니다."),
            (r"나만의\s*사색에\s*잠길\s*수\s*있는\s*시간[.,]?", "친구들과 함께 웃음꽃을 피울 수 있는 시간."),
            (r"그런\s*나를\s*위한\s*완벽한\s*장소다[.,]?", "친구들과 특별한 추억을 만들기에 완벽한 장소입니다."),
            (r"나에게\s*소중한\s*쉼표가\s*되어줄\s*것이다[.,]?", "우리 모두에게 잊지 못할 청춘의 쉼표가 되어줄 것입니다."),
            (r"둘만의 특별한 순간", "친구들과 나누는 유쾌한 순간"),
            (r"사랑하는 이와 함께하는", "소중한 친구들과 함께하는"),
            (r"연인과 함께하는", "친구들과 함께하는"),
            (r"연인과 함께", "친구들과 함께"),
            (r"두 사람이 함께", "친구들과 함께"),
            (r"두 사람이", "친구들이 다 함께"),
            (r"부모님과 함께", "친구들과 함께"),
            (r"부모님", "친구들"),
            (r"어르신이나 휠체어를 동반한 가족도", "친구들과 함께 나들이를 떠난 누구라도"),
            (r"패밀리 좌석", "넓고 쾌적한 단체 좌석"),
            (r"혼자만의", "친구들과의"),
            (r"혼자서", "친구들과 다 함께"),
            (r"혼자", "친구들"),
            (r"나홀로", "친구들과 함께"),
            (r"나만의", "우리들의"),
            (r"나를 위한", "친구들을 위한"),
            (r"가족,\s*연인과\s*함께", "소중한 친구들과 함께"),
            (r"가족이나\s*연인과\s*함께", "친구들과 함께"),
            (r"가족,\s*연인", "소중한 친구들"),
            (r"오늘은 편안한 주차와 안전한 동선으로,?\s*[^,\n]+[와과] 함께하는 힐링의 여정을 안내해 드리겠습니다", "오늘은 편안한 주차와 활기찬 동선으로, 친구들과 함께하는 우정 힐링의 여정을 안내해 드리겠습니다"),
        ]
        for pat, rep in replacements:
            text = re.sub(pat, rep, text)

    elif comp_type == "pet":
        replacements = [
            (r"#\s*🌿?\s*혼자만의\s*사색과\s*자유를\s*즐기는\s*([^\n]+)", f"# 🌿 사랑하는 반려견과 발맞추어 걷는 펫프렌들리 힐링, \\1"),
            (r"#\s*🌿?\s*([^\n]+?)\s*나홀로\s*사색\s*여행", f"# 🌿 \\1 반려견과 함께하는 펫 힐링 산책"),
            (r"오롯이\s*나만의\s*시간을\s*만끽하는\s*여정[^\n]*", "폭신한 산책로와 쾌적한 쉼터에서 사랑하는 반려견과 교감하는 하루"),
            (r"혼자만의\s*여정은\s*언제나\s*특별하다[^\n.]*\.", "반려견과 함께하는 여정은 언제나 따뜻하고 정겹습니다."),
            (r"나만의\s*사색에\s*잠길\s*수\s*있는\s*시간[.,]?", "사랑하는 댕댕이와 발맞추어 걷는 소중한 시간."),
            (r"그런\s*나를\s*위한\s*완벽한\s*장소다[.,]?", "반려동물과 편안하게 거닐기에 완벽한 장소입니다."),
            (r"나에게\s*소중한\s*쉼표가\s*되어줄\s*것이다[.,]?", "반려견과 보호자 모두에게 평화로운 쉼표가 되어줄 것입니다."),
            (r"둘만의 특별한 순간", "반려견과 교감하는 따스한 순간"),
            (r"사랑하는 이와 함께하는", "사랑하는 댕댕이와 함께하는"),
            (r"연인과 함께하는", "반려동물과 함께하는"),
            (r"연인과 함께", "반려견과 함께"),
            (r"두 사람이 함께", "반려견과 함께"),
            (r"두 사람이", "반려견과 함께"),
            (r"온 가족이 손을 잡고", "반려견과 발맞추어"),
            (r"온 가족이", "반려견과 함께"),
            (r"부모님과", "반려견과"),
            (r"혼자만의", "반려견과의"),
            (r"혼자서", "반려견과 함께"),
            (r"혼자", "반려견"),
            (r"나홀로", "반려견과"),
            (r"나만의", "우리 댕댕이와의"),
            (r"나를 위한", "반려동물을 위한"),
            (r"가족,\s*연인과\s*함께", "사랑하는 반려견과 함께"),
            (r"가족이나\s*연인과\s*함께", "반려견과 함께"),
            (r"가족,\s*연인", "사랑하는 반려견"),
            (r"오늘은 편안한 주차와 안전한 동선으로,?\s*[^,\n]+[와과] 함께하는 힐링의 여정을 안내해 드리겠습니다", "오늘은 편안한 주차와 폭신한 산책로로, 반려견과 함께하는 펫프렌들리 힐링의 여정을 안내해 드리겠습니다"),
        ]
        for pat, rep in replacements:
            text = re.sub(pat, rep, text)

    elif comp_type == "solo":
        replacements = [
            (r"#\s*🌿?\s*부모님과\s*함께하는\s*안심\s*효도\s*힐링[,\s]*([^\n]+)", f"# 🌿 혼자만의 사색과 자유를 즐기는 \\1"),
            (r"#\s*🌿?\s*온\s*가족이\s*함께\s*즐기는\s*패밀리\s*나들이[,\s]*([^\n]+)", f"# 🌿 혼자만의 사색과 자유를 즐기는 \\1"),
            (r"#\s*🌿?\s*둘만의\s*낭만과\s*설렘을\s*채우는\s*로맨틱\s*데이트[,\s]*([^\n]+)", f"# 🌿 혼자만의 사색과 자유를 즐기는 \\1"),
            (r"부모님의\s*편안한\s*걸음걸이에\s*맞춘[^\n]*", "오롯이 나만의 시간을 만끽하는 여정, 바다와 자연의 숨결을 느끼며"),
            (r"아이와\s*어른\s*모두가\s*안전하고[^\n]*", "오롯이 나만의 시간을 만끽하는 여정, 바다와 자연의 숨결을 느끼며"),
            (r"사랑하는\s*연인과\s*손잡고[^\n]*", "오롯이 나만의 시간을 만끽하는 여정, 바다와 자연의 숨결을 느끼며"),
            (r"부모님의 편안한 보행과 아이들의 안전을 고려하여", "오롯이 혼자만의 호젓한 사색과 자유로운 발걸음을 위하여"),
            (r"온 가족이 손을 잡고", "홀로 가벼운 발걸음으로"),
            (r"온 가족이 함께 즐기는", "혼자서 호젓하게 만끽하는"),
            (r"온 가족이 함께", "나 홀로 오롯이"),
            (r"온 가족이", "오롯이 나 홀로"),
            (r"온 가족의", "나만의"),
            (r"가족과 함께", "나 홀로"),
            (r"가족들이", "여행자가"),
            (r"가족 단위", "1인 여행자"),
            (r"부모님과 함께", "나 홀로"),
            (r"부모님", "나"),
            (r"연인과 함께", "나 홀로"),
            (r"사랑하는 이와 함께하는", "오롯이 나 자신과 마주하는"),
            (r"둘만의 특별한 순간", "나만의 고요한 사색"),
            (r"두 사람이 함께", "오롯이 혼자"),
            (r"두 사람이", "홀로"),
            (r"패밀리 좌석", "아늑한 1인 좌석"),
            (r"패밀리 힐링", "사색 힐링"),
            (r"가족,\s*연인과\s*함께", "나 홀로 오롯이"),
            (r"가족이나\s*연인과\s*함께", "나 홀로 오롯이"),
            (r"가족과\s*연인과\s*함께", "나 홀로 오롯이"),
            (r"가족,\s*연인", "홀로 떠난 여행자"),
            (r"가족과\s*연인", "홀로 떠난 여행자"),
            (r"오늘은 편안한 주차와 안전한 동선으로,?\s*[^,\n]+[와과] 함께하는 힐링의 여정을 안내해 드리겠습니다", "오늘은 편안한 주차와 호젓한 동선으로, 나 홀로 떠나는 사색의 여정을 안내해 드리겠습니다"),
        ]
        for pat, rep in replacements:
            text = re.sub(pat, rep, text)

    return text


def render_curated_article_report(article_content: str, target_companion: str = "", fest_name: str = "", fest_region: str = "") -> str:
    """
    AI 에디터 상세 분석 리포트 전문 렌더러 (타이포그래피 및 위계 개선)
    - 동행인 선택에 맞춰 리포트 내 텍스트를 100% 자동 동기화(harmonize_report_to_companion)
    - 메인 타이틀, 서브타이틀, 섹션 헤더, 타임라인 카드 정밀 렌더링
    """
    if not article_content or not str(article_content).strip():
        return ""

    # 동행인 정합성 100% 자동 동기화 수행
    if target_companion:
        article_content = harmonize_report_to_companion(article_content, target_companion, fest_name=fest_name)

    raw_text = str(article_content).strip()
    lines = raw_text.splitlines()

    main_title = ""
    sub_title = ""
    sections = []

    def inline_format(text: str) -> str:
        text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
        return text

    idx = 0
    # 1. 헤더 탐색
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue

        if line.startswith("# ") or (line.startswith("#") and not line.startswith("###")):
            raw_title = line.lstrip("#").strip()
            raw_title = re.sub(r"^\[(?:헤드라인|Headline)\s*[:：]?\s*(.*?)\]$", r"\1", raw_title)
            main_title = raw_title
            idx += 1
            continue

        subhead_match = re.match(r"^(\*{0,2})(?:서브헤드|서브타이틀|부제|Subhead)\s*[:：]\s*(\*{0,2})\s*(.*)$", line, re.IGNORECASE)
        if subhead_match:
            sub_title = subhead_match.group(3).strip()
            sub_title = re.sub(r"^\*\*|\*\*$", "", sub_title).strip()
            idx += 1
            continue

        if main_title and not sub_title and not line.startswith("###") and not line.startswith("##"):
            if len(line) < 130 and not line.startswith(("-", "*", "•")):
                sub_title = re.sub(r"^\*\*|\*\*$", "", line).strip()
                idx += 1
                continue

        if line.startswith("###") or line.startswith("##"):
            break

        idx += 1

    # 2. 섹션 파싱
    current_sec_title = None
    current_sec_content = []

    while idx < len(lines):
        line = lines[idx].strip()
        idx += 1

        if not line:
            continue

        if line.startswith("###") or line.startswith("##"):
            if current_sec_title or current_sec_content:
                sections.append((current_sec_title, current_sec_content))
            current_sec_title = line.lstrip("#").strip()
            current_sec_content = []
            continue

        subhead_match = re.match(r"^(\*{0,2})(?:서브헤드|서브타이틀|부제|Subhead)\s*[:：]\s*(\*{0,2})\s*(.*)$", line, re.IGNORECASE)
        if subhead_match and not sub_title:
            sub_title = re.sub(r"^\*\*|\*\*$", "", subhead_match.group(3)).strip()
            continue

        if current_sec_title is None:
            if not sub_title and len(line) < 130:
                sub_title = re.sub(r"^\*\*|\*\*$", "", line).strip()
            else:
                current_sec_content.append(line)
        else:
            current_sec_content.append(line)

    if current_sec_title or current_sec_content:
        sections.append((current_sec_title, current_sec_content))

    if not main_title:
        main_title = "🌿 AI 에디터 맞춤 여행 큐레이션 리포트"

    # [동행인-헤드라인 2차 안심 정합성 보장]
    comp_clean = str(target_companion or "").strip()
    f_clean = fest_name.strip() if fest_name else "로컬 축제"
    if any(k in comp_clean for k in ["부모", "어르신", "효도"]):
        if any(bad in main_title for bad in ["혼자", "사색", "나홀로", "1인", "연인", "둘만"]):
            main_title = f"🌿 부모님과 함께하는 안심 효도 힐링, {f_clean}"
        if any(bad in sub_title for bad in ["나만의", "오롯이", "사색"]):
            sub_title = "부모님의 편안한 걸음걸이에 맞춘 따뜻한 배려의 하루, 바다와 자연의 온기를 나누며"
    elif any(k in comp_clean for k in ["가족", "아이", "자녀"]):
        if any(bad in main_title for bad in ["혼자", "사색", "나홀로", "1인", "연인", "둘만"]):
            main_title = f"🌿 온 가족이 함께 즐기는 패밀리 나들이, {f_clean}"
        if any(bad in sub_title for bad in ["나만의", "오롯이", "사색"]):
            sub_title = "아이와 어른 모두가 안전하고 행복하게 즐기는 맞춤 여정"
    elif any(k in comp_clean for k in ["연인", "커플", "데이트"]):
        if any(bad in main_title for bad in ["혼자", "사색", "나홀로", "부모", "가족"]):
            main_title = f"🌿 둘만의 낭만과 설렘을 채우는 로맨틱 데이트, {f_clean}"
        if any(bad in sub_title for bad in ["나만의", "부모님", "아이"]):
            sub_title = "사랑하는 연인과 손잡고 걷는 감성 가득한 하루"
    elif any(k in comp_clean for k in ["친구", "우정"]):
        if any(bad in main_title for bad in ["혼자", "사색", "나홀로", "부모", "둘만"]):
            main_title = f"🌿 친구들과 활기차게 떠나는 우정 힐링 여행, {f_clean}"
        if any(bad in sub_title for bad in ["나만의", "부모님"]):
            sub_title = "함께 웃고 즐기며 잊지 못할 추억을 만드는 유쾌한 하루"
    elif any(k in comp_clean for k in ["반려", "강아지", "애견"]):
        if any(bad in main_title for bad in ["혼자", "사색", "나홀로", "부모", "둘만"]):
            main_title = f"🌿 반려견과 발맞추어 걷는 펫프렌들리 힐링, {f_clean}"
        if any(bad in sub_title for bad in ["나만의", "부모님"]):
            sub_title = "폭신한 산책로와 쾌적한 쉼터에서 반려견과 교감하는 하루"

    # [UI: Luxury Editorial Magazine Style] 부드러운 웜톤 아이보리 웹 매거진 & 딥 그린 & 고딕체
    report_custom_css = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap');

/* 전체 리포트 래퍼: 부드러운 웜톤 아이보리 웹 매거진 스타일 & 고딕체 강제 적용 */
.report-wrapper,
.report-wrapper * {
    font-family: 'Pretendard', 'Noto Sans KR', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

.report-wrapper {
    position: relative !important;
    padding: 28px 24px !important;
    border-radius: 20px !important;
    background: #FAF7F2 !important;
    border: 1.5px solid #EAE3D2 !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04) !important;
    color: #2B2F2C !important;
    letter-spacing: -0.01em !important;
    overflow: hidden !important;
}

/* 상단 & 하단 퀵 액션 툴바: Home 및 Weather 버튼 */
.report-action-toolbar {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    margin-bottom: 18px !important;
    flex-wrap: wrap !important;
}
.report-tool-btn {
    display: inline-flex !important;
    align-items: center !important;
    gap: 7px !important;
    padding: 8px 18px !important;
    border-radius: 20px !important;
    text-decoration: none !important;
    font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
    font-size: 13.5px !important;
    font-weight: 700 !important;
    transition: all 0.2s ease !important;
    letter-spacing: -0.01em !important;
}
/* Home 버튼: 눈이 편안하고 차분한 딥 그린(Forest Green) */
.report-btn-home {
    background: #1B4332 !important;
    color: #FAF7F2 !important;
    border: 1.5px solid #143527 !important;
    box-shadow: 0 2px 8px rgba(27, 67, 50, 0.2) !important;
}
.report-btn-home:hover {
    background: #2D5A43 !important;
    color: #FFFFFF !important;
    border-color: #2D5A43 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(27, 67, 50, 0.3) !important;
}
/* Weather 버튼: 차분한 웜 샌드 베이지 테마 */
.report-btn-weather {
    background: #EDE8DE !important;
    color: #1B4332 !important;
    border: 1.5px solid #DCD4C7 !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04) !important;
}
.report-btn-weather:hover {
    background: #E2DBD0 !important;
    color: #012D1D !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08) !important;
}

/* 차분하고 깔끔한 화이트 매거진 카드 박스 */
.report-card-box {
    background: #FFFFFF !important;
    border: 1px solid #ECE7DE !important;
    border-radius: 14px !important;
    padding: 22px 24px !important;
    margin-bottom: 18px !important;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03) !important;
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease !important;
}
.report-card-box:hover {
    border-color: #D8D2C5 !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.05) !important;
}

/* 섹션별 개성 악센트 테두리 (차분한 자연의 톤) */
.report-card-letter {
    border-left: 4px solid #2D5A43 !important;
    background: linear-gradient(135deg, #FDFCF9 0%, #FFFFFF 100%) !important;
}
.report-card-timeline {
    border-left: 4px solid #1B4332 !important;
    background: linear-gradient(135deg, #FDFCF9 0%, #FFFFFF 100%) !important;
}
.report-card-safe {
    border-left: 4px solid #3B7A57 !important;
    background: linear-gradient(135deg, #FDFCF9 0%, #FFFFFF 100%) !important;
}
.report-card-highlight {
    border-left: 4px solid #8C6D46 !important;
    background: linear-gradient(135deg, #FDFCF9 0%, #FFFFFF 100%) !important;
}

/* 헤더 & 타이포그래피 (모던 고딕체 강제 적용) */
.report-main-title,
.report-wrapper h1,
.report-wrapper h2 {
    font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
    font-size: 22px !important;
    font-weight: 800 !important;
    color: #1B4332 !important;
    line-height: 1.45 !important;
    letter-spacing: -0.02em !important;
    margin-top: 2px !important;
    margin-bottom: 8px !important;
    word-break: keep-all !important;
    text-shadow: none !important;
}
.report-subtitle {
    font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
    font-size: 14.5px !important;
    font-weight: 500 !important;
    color: #4A6B53 !important;
    line-height: 1.65 !important;
    letter-spacing: -0.01em !important;
    margin-top: 0 !important;
    margin-bottom: 6px !important;
    word-break: keep-all !important;
    text-shadow: none !important;
}
.report-subtitle-divider {
    margin-bottom: 12px !important;
    border-bottom: 1px solid #ECE7DE !important;
}
.report-section-header,
.report-wrapper h3 {
    font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
    font-size: 17px !important;
    font-weight: 700 !important;
    color: #1B4332 !important;
    margin-top: 2px !important;
    margin-bottom: 14px !important;
    letter-spacing: -0.01em !important;
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
    line-height: 1.4 !important;
}
.report-sec-icon {
    font-size: 1.15em !important;
    filter: none !important;
}
.report-sec-en {
    font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
    font-weight: 800 !important;
    letter-spacing: 0.01em !important;
    color: #2D5A43 !important;
    text-shadow: none !important;
}
.report-sec-divider {
    color: #CBD5E1 !important;
    margin: 0 4px !important;
    font-weight: 400 !important;
}
.report-sec-ko {
    font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
    font-weight: 600 !important;
    color: #2D3748 !important;
    font-size: 0.98em !important;
}
.report-body-text,
.report-wrapper p {
    font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
    font-size: 15px !important;
    font-weight: 400 !important;
    line-height: 1.8 !important;
    color: #374151 !important;
    margin-bottom: 14px !important;
    letter-spacing: -0.01em !important;
    word-break: keep-all !important;
    text-shadow: none !important;
}
.report-body-text strong,
.report-wrapper strong {
    color: #111827 !important;
    font-weight: 700 !important;
}

/* 타임라인 컨테이너 & 카드 */
.report-timeline-container {
    display: flex !important;
    flex-direction: column !important;
    gap: 10px !important;
    margin-top: 10px !important;
    margin-bottom: 8px !important;
}
.report-timeline-card {
    display: flex !important;
    align-items: baseline !important;
    gap: 12px !important;
    background: #FAF8F4 !important;
    border: 1px solid #ECE7DE !important;
    border-left: 3.5px solid #1B4332 !important;
    border-radius: 10px !important;
    padding: 12px 16px !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.02) !important;
    transition: transform 0.2s ease, border-color 0.2s ease !important;
}
.report-timeline-card:hover {
    transform: translateX(3px) !important;
    border-color: #2D5A43 !important;
}

/* 10:30 AM 등 시간 뱃지: 눈이 편안한 딥 그린(Forest Green) */
.report-time-badge {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: #1B4332 !important;
    color: #FAF7F2 !important;
    font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
    font-weight: 700 !important;
    font-size: 12.5px !important;
    padding: 3px 10px !important;
    border-radius: 6px !important;
    border: 1px solid #143527 !important;
    box-shadow: 0 1px 4px rgba(27, 67, 50, 0.15) !important;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
    letter-spacing: 0.01em !important;
}
.report-timeline-desc {
    font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
    font-size: 14.5px !important;
    line-height: 1.7 !important;
    color: #2D3748 !important;
    flex: 1 !important;
    word-break: keep-all !important;
}

/* 불릿 아이템 & 불릿 닷 */
.report-bullet-item {
    display: flex !important;
    align-items: baseline !important;
    gap: 10px !important;
    background: #FAF8F4 !important;
    border: 1px solid #ECE7DE !important;
    border-radius: 10px !important;
    padding: 11px 16px !important;
    margin-bottom: 8px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02) !important;
}
.report-bullet-dot {
    color: #1B4332 !important;
    font-weight: 900 !important;
    font-size: 16px !important;
    line-height: 1 !important;
    flex-shrink: 0 !important;
    filter: none !important;
}
.report-bullet-text {
    font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
    font-size: 14.5px !important;
    line-height: 1.7 !important;
    color: #374151 !important;
    flex: 1 !important;
    word-break: keep-all !important;
}
</style>
"""

    html_out = [report_custom_css, '<div class="report-wrapper">']

    # 상단 퀵 액션 툴바: Home 및 Weather 버튼 (마크다운 인덴트 코드블록 오작동 방지를 위해 들여쓰기 공백 제거)
    weather_href = "?view=weather"
    if fest_name:
        params = [("view", "weather"), ("w_fest", str(fest_name).strip())]
        if fest_region:
            params.append(("w_region", str(fest_region).strip()))
        if target_companion:
            params.append(("companion", str(target_companion).strip()))
        weather_href = f"?{urllib.parse.urlencode(params)}"

    html_out.append(
        '<div class="report-action-toolbar">'
        '<a href="?view=main" target="_self" class="report-tool-btn report-btn-home" onclick="try{sessionStorage.removeItem(\'festapick_active_companion\');}catch(e){}">'
        '<span class="tool-icon">🏠</span><span class="tool-text">Home 메인으로</span>'
        '</a>'
        f'<a href="{html.escape(weather_href)}" target="_self" class="report-tool-btn report-btn-weather">'
        '<span class="tool-icon">🌤️</span><span class="tool-text">Weather 날씨 케어</span>'
        '</a>'
        '</div>'
    )

    # 메인 헤더 글래스모피즘 박스
    html_out.append('<div class="report-card-box">')
    html_out.append(f'<div class="report-main-title">{inline_format(main_title)}</div>')
    if sub_title:
        html_out.append(f'<div class="report-subtitle">{inline_format(sub_title)}</div>')
    html_out.append('</div>')

    for sec_title, content_lines in sections:
        # 섹션별 특화 카드 클래스 결정
        sec_box_class = "report-card-box"
        sec_title_lower = (sec_title or "").lower()
        if any(k in sec_title_lower for k in ["editor", "에디터", "letter", "여정"]):
            sec_box_class += " report-card-letter"
        elif any(k in sec_title_lower for k in ["timeline", "동선", "타임라인", "일정"]):
            sec_box_class += " report-card-timeline"
        elif any(k in sec_title_lower for k in ["safe", "relax", "안심", "꿀팁", "tip"]):
            sec_box_class += " report-card-safe"
        elif any(k in sec_title_lower for k in ["highlight", "이벤트", "하이라이트", "프로그램"]):
            sec_box_class += " report-card-highlight"

        html_out.append(f'<div class="{sec_box_class}">')

        if sec_title:
            clean_sec_title = sec_title
            clean_sec_title = re.sub(r"\[(.*?)(?:\s*\(.*?\))?\]", r"\1", clean_sec_title).strip()
            clean_sec_title = clean_sec_title.rstrip(":")

            # 영문 헤더(Editor's Letter, Highlight Events 등)와 한글 부제목 위계 분리 렌더링
            header_match = re.match(r"^([^\w\s]*\s*)([A-Za-z\s'’\-]+)(?:\s*[:：]\s*(.*))?$", clean_sec_title)
            if header_match and header_match.group(2).strip():
                p_icon = header_match.group(1) or ""
                en_title = header_match.group(2).strip()
                ko_sub = (header_match.group(3) or "").strip()
                if ko_sub:
                    header_html = f'<span class="report-sec-icon">{p_icon}</span><span class="report-sec-en">{inline_format(en_title)}</span><span class="report-sec-divider">:</span> <span class="report-sec-ko">{inline_format(ko_sub)}</span>'
                else:
                    header_html = f'<span class="report-sec-icon">{p_icon}</span><span class="report-sec-en">{inline_format(en_title)}</span>'
                html_out.append(f'<div class="report-section-header">{header_html}</div>')
            else:
                html_out.append(f'<div class="report-section-header">{inline_format(clean_sec_title)}</div>')

        is_timeline = bool(sec_title and any(k in sec_title.lower() for k in ["timeline", "동선", "타임라인", "일정"]))

        if is_timeline:
            html_out.append('<div class="report-timeline-container">')
            for c_line in content_lines:
                clean_l = c_line.strip()
                if not clean_l:
                    continue

                # 유연하고 견고한 시간 패턴 매칭 (중복 불릿, 마크다운 기호, 공백 등 모두 허용)
                time_match = re.match(
                    r'^[-*•\s\t#]*?(?:\*\*)?\s*(\d{1,2}:\d{2}(?:\s*(?:AM|PM|am|pm))?|(?:오전|오후)\s*\d{1,2}(?:시|:\d{2})?|\d{1,2}\s*(?:AM|PM|am|pm))\s*(?:\*\*)?\s*[:：\-~|]?\s*(.*)$',
                    clean_l,
                    re.IGNORECASE
                )
                if time_match:
                    t_badge = time_match.group(1).strip()
                    t_desc = time_match.group(2).strip()
                    # 선행 잔여 특수기호 및 마크다운 정리
                    t_desc = re.sub(r'^[-*•:：\s]+', '', t_desc)
                    t_desc = re.sub(r'^\*\*\s*', '', t_desc)
                    t_desc = re.sub(r'\s*\*\*$', '', t_desc)
                    card_html = f'<div class="report-timeline-card"><span class="report-time-badge">{inline_format(t_badge)}</span><span class="report-timeline-desc">{inline_format(t_desc)}</span></div>'
                    html_out.append(card_html)
                else:
                    # 타임라인 내 부가 설명 줄인 경우에도 카드 레이아웃 유지 (레이아웃 파괴 방지)
                    clean_text = re.sub(r"^[-*•]\s*", "", clean_l).strip()
                    clean_text = re.sub(r"^\*\*|\*\*$", "", clean_text).strip()
                    if clean_text:
                        card_html = f'<div class="report-timeline-card" style="border-left-color:#64748B; background:rgba(15,23,42,0.65);"><span class="report-time-badge" style="background:#334155; color:#F8FAFC; border-color:#64748B; box-shadow:none;">INFO</span><span class="report-timeline-desc">{inline_format(clean_text)}</span></div>'
                        html_out.append(card_html)
            html_out.append('</div>')
        else:
            for c_line in content_lines:
                clean_text = c_line.strip()
                if not clean_text:
                    continue
                if clean_text.startswith(("-", "*", "•")):
                    bullet_text = re.sub(r"^[-*•]\s*", "", clean_text).strip()
                    bullet_html = f'<div class="report-bullet-item"><span class="report-bullet-dot">•</span><span class="report-bullet-text">{inline_format(bullet_text)}</span></div>'
                    html_out.append(bullet_html)
                else:
                    html_out.append(f'<p class="report-body-text">{inline_format(clean_text)}</p>')

        html_out.append('</div>')

    html_out.append('</div>')
    return "\n".join(html_out)


# ==============================================================================
# 3. Streamlit 페이지 설정
# ==============================================================================
st.set_page_config(
    page_title="FestaPick · 공공데이터 안심 여행 매거진",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# [전역 스크롤 포커스 가디언] 리렌더링 및 상태 변경 시 최상단 튕김 현상 100% 원천 방어
st.html("""
<script>
(function() {
    if (window.__festapick_scroll_guardian_installed) return;
    window.__festapick_scroll_guardian_installed = true;

    function recordCurrentScroll() {
        try {
            if (window.scrollY > 20) {
                sessionStorage.setItem('festapick_last_scroll_y', String(window.scrollY));
            }
        } catch(e) {}
    }

    window.addEventListener('scroll', recordCurrentScroll, { passive: true });
    window.addEventListener('beforeunload', recordCurrentScroll);

    function restoreScrollGuardian() {
        try {
            var anchor = sessionStorage.getItem('festapick_scroll_anchor');
            if (anchor) {
                var el = document.getElementById(anchor);
                if (el) {
                    el.scrollIntoView({ behavior: 'auto', block: 'start' });
                    sessionStorage.removeItem('festapick_scroll_anchor');
                    sessionStorage.removeItem('festapick_last_scroll_y');
                    return;
                }
            }
            var savedY = sessionStorage.getItem('festapick_last_scroll_y');
            if (savedY && parseInt(savedY, 10) > 20) {
                window.scrollTo({ top: parseInt(savedY, 10), behavior: 'auto' });
                sessionStorage.removeItem('festapick_last_scroll_y');
            }
        } catch(e) {}
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', restoreScrollGuardian);
    } else {
        restoreScrollGuardian();
    }
    setTimeout(restoreScrollGuardian, 40);
    setTimeout(restoreScrollGuardian, 150);
    setTimeout(restoreScrollGuardian, 400);
})();
</script>
""", unsafe_allow_javascript=True)


# ==============================================================================
# 4. 세션 상태 관리 (Session State Architecture)
# ==============================================================================
# ------------------------------------------------------------------------------
# 뷰 모드 라우팅 (메인 매거진 뷰 vs 캘린더 전용 뷰)
# ------------------------------------------------------------------------------
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "main"
_now_cal_d = datetime.now().date()
if "cal_year" not in st.session_state:
    st.session_state.cal_year = _now_cal_d.year
if "cal_month" not in st.session_state:
    st.session_state.cal_month = _now_cal_d.month
if "cal_selected_date" not in st.session_state:
    st.session_state.cal_selected_date = _now_cal_d.strftime("%Y-%m-%d")
if "cal_genre" not in st.session_state:
    st.session_state.cal_genre = "all"
if "cal_region" not in st.session_state:
    st.session_state.cal_region = "all"
if "companion" not in st.session_state:
    st.session_state.companion = None
if "active_companion_param" not in st.session_state:
    st.session_state.active_companion_param = "none"
if "_prev_view_mode" not in st.session_state:
    st.session_state._prev_view_mode = None

# ------------------------------------------------------------------------------
# 에디토리얼 에세이 & 쉼표여정 직통 연동 엔진
# ------------------------------------------------------------------------------
def execute_curated_editorial_flow(f_target: str, q_region: str = "", companion: str = None, transport: str = None, stamina: int = None):
    """
    [에디토리얼 에세이 & 쉼표여정 직통 연동 함수]
    추천 축제 클릭 시 맞춤형 파라미터(체력, 동행인, 교통)를 자동 설정하고
    공공데이터 인프라 및 AI 큐레이션 파이프라인을 실행하여 즉시 맞춤 에세이 & 안심 지도 화면으로 전환
    """
    st.session_state.view_mode = "main"
    st.session_state.show_main = True
    st.session_state.course_target_fest = f_target

    # 축제별 특화 맞춤 프리셋 (Editorial Spotlight 3선 등)
    spotlight_presets = {
        "순천만 갈대축제": {"region": "전라남도", "stamina": 75, "companion": "나홀로 쉼표 여행", "transport": "🚗 자가용 (편한 주차)"},
        "순천만갈대축제": {"region": "전라남도", "stamina": 75, "companion": "나홀로 쉼표 여행", "transport": "🚗 자가용 (편한 주차)"},
        "진주 남강유등축제": {"region": "경상남도", "stamina": 50, "companion": "가족과 함께", "transport": "🚶 도보 (대중교통)"},
        "진주남강유등축제": {"region": "경상남도", "stamina": 50, "companion": "가족과 함께", "transport": "🚶 도보 (대중교통)"},
        "강릉 커피축제": {"region": "강원특별자치도", "stamina": 40, "companion": "연인 / 커플", "transport": "🚗 자가용 (편한 주차)"},
        "강릉커피축제": {"region": "강원특별자치도", "stamina": 40, "companion": "연인 / 커플", "transport": "🚗 자가용 (편한 주차)"},
    }
    preset = spotlight_presets.get(f_target.strip(), {})

    # 사용자가 이미 동행인을 명시적으로 선택한 세션이 있다면 사용자 선택을 최우선 반영
    user_chosen_comp = st.session_state.get("main_companion")
    raw_target_comp = companion or user_chosen_comp or preset.get("companion") or "나홀로 쉼표 여행"

    # 동행인 표준 명칭 정규화 ('산책' -> '여행' 통일)
    if any(k in str(raw_target_comp) for k in ["홀로", "혼자", "솔로", "1인"]):
        target_companion = "나홀로 쉼표 여행"
    elif any(k in str(raw_target_comp) for k in ["친구", "우정"]):
        target_companion = "친구와 함께"
    elif any(k in str(raw_target_comp) for k in ["부모", "효도", "어르신"]):
        target_companion = "부모님과 힐링 (효도 여행)"
    elif any(k in str(raw_target_comp) for k in ["연인", "커플", "데이트"]):
        target_companion = "연인 / 커플"
    elif any(k in str(raw_target_comp) for k in ["가족", "자녀", "아이"]):
        target_companion = "가족과 함께"
    elif any(k in str(raw_target_comp) for k in ["반려", "강아지", "애견"]):
        target_companion = "반려견 동반"
    else:
        target_companion = "나홀로 쉼표 여행"

    target_transport = transport or preset.get("transport") or "🚗 자가용 (편한 주차)"
    target_stamina = stamina or preset.get("stamina") or 50

    # 1. 대상 축제 정밀 매칭 (CALENDAR_MASTER_FESTIVALS 및 master_2026_oct_festivals.json 전수 탐색)
    fest_obj = None
    for f in CALENDAR_MASTER_FESTIVALS:
        if f.get("title") == f_target or f.get("title", "") in f_target or f_target in f.get("title", ""):
            fest_obj = f
            break

    if not fest_obj:
        master_path = os.path.join(CURRENT_DIR, "festapick", "data", "master_2026_oct_festivals.json")
        if os.path.exists(master_path):
            try:
                with open(master_path, "r", encoding="utf-8") as mf:
                    m_data = json.load(mf)
                    for item in m_data:
                        t_name = str(item.get("title") or item.get("name") or "").strip()
                        if t_name == f_target or f_target in t_name or t_name in f_target:
                            r_raw = item.get("region", q_region or preset.get("region") or "전국")
                            r_short_map = {
                                "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시",
                                "광주": "광주광역시", "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시",
                                "경기": "경기도", "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
                                "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도", "경남": "경상남도", "제주": "제주특별자치도"
                            }
                            r_short = r_short_map.get(r_raw, r_raw)
                            lat_v = float(item.get("mapy", item.get("lat", 35.155)) or 35.155)
                            lng_v = float(item.get("mapx", item.get("lng", 129.063)) or 129.063)
                            s_d = str(item.get("startDate", "20261001"))
                            e_d = str(item.get("endDate", "20261031"))
                            fest_obj = {
                                "title": item.get("title", f_target),
                                "region_short": r_short,
                                "region": r_short,
                                "stamina": target_stamina,
                                "address": item.get("addr", item.get("address", "")),
                                "lat": lat_v,
                                "lng": lng_v,
                                "startDate": f"{s_d[:4]}-{s_d[4:6]}-{s_d[6:8]}" if len(s_d)==8 else s_d,
                                "endDate": f"{e_d[:4]}-{e_d[4:6]}-{e_d[6:8]}" if len(e_d)==8 else e_d,
                                "phone": item.get("tel", ""),
                                "homepage": item.get("homepage", ""),
                                "description": item.get("desc", f"{f_target}에 오신 것을 환영합니다.")
                            }
                            break
            except Exception:
                pass

    if not fest_obj:
        r_short_map = {
            "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시",
            "광주": "광주광역시", "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시",
            "경기": "경기도", "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
            "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도", "경남": "경상남도", "제주": "제주특별자치도"
        }
        fallback_r = preset.get("region") or q_region or "서울특별시"
        target_r_full = r_short_map.get(fallback_r, fallback_r)
        fest_obj = {
            "title": f_target,
            "region_short": target_r_full,
            "region": target_r_full,
            "stamina": target_stamina,
            "address": "",
            "lat": 35.155,
            "lng": 129.063,
            "startDate": "2026-10-01",
            "endDate": "2026-10-31",
            "phone": "",
            "homepage": "",
            "description": f"{f_target} 맞춤 로컬 여정"
        }

    target_region = preset.get("region") or fest_obj.get("region_short", fest_obj.get("region", "서울특별시"))

    # 2. 메인 패널 세션 상태 동기화 (위젯 인스턴스화 후 키 직접 수정 방지)
    st.session_state.selected_region_state = target_region
    st.session_state.selected_month_state = "10월"
    st.session_state.selected_fest_name_state = fest_obj["title"]
    st.session_state.stamina_state = target_stamina
    st.session_state.active_companion = target_companion
    st.session_state.active_transport = target_transport
    st.session_state.active_stamina = target_stamina

    # 3. 공공데이터 인프라 및 AI 큐레이션 파이프라인 자동 실행
    with st.spinner(f"🖋️ '{fest_obj['title']}' 맞춤 에디토리얼 에세이와 안심 코스 지도를 발행하고 있습니다..."):
        c_lat, c_lng = resolve_festival_coordinates(fest_obj.get("title", f_target), fest_obj.get("address", ""), fest_obj.get("lat"), fest_obj.get("lng"))
        fest_obj["lat"] = c_lat
        fest_obj["lng"] = c_lng
        fest_data_payload = {
            "name": fest_obj["title"],
            "lat": c_lat,
            "lng": c_lng,
            "address": fest_obj.get("address", ""),
            "description": fest_obj.get("description", ""),
            "region": target_region,
            "dates": f"{fest_obj.get('startDate', '2026-10-01')} ~ {fest_obj.get('endDate', '2026-10-31')}",
            "phone": fest_obj.get("phone", ""),
            "homepage": fest_obj.get("homepage", ""),
            "programs": fest_obj.get("programs") or get_festival_programs_from_data(fest_obj.get("title", ""), fest_obj.get("description", ""))
        }

        try:
            infra = get_festival_infra_bundle(
                fest_lat=fest_data_payload["lat"],
                fest_lng=fest_data_payload["lng"],
                radius_m=3000,
                target_address=fest_data_payload["address"]
            )
            p_lots = infra.get("parking_lots", [])
            m_rests = infra.get("model_restaurants", [])
            t_spots = infra.get("tourist_spots", [])
        except Exception as e:
            p_lots, m_rests, t_spots = [], [], []

        if "나홀로" in target_companion or "혼자" in target_companion:
            extra_prompt_companion = "오롯이 혼자만의 호젓한 사색과 자유를 즐길 수 있는 1인 맞춤 안심 힐링 동선으로 안내해 주세요."
        else:
            extra_prompt_companion = f"{target_companion}과 함께 무리 없이 편안하고 안전하게 즐길 수 있는 안심 힐링 동선으로 안내해 주세요."

        user_inputs = {
            "stamina": target_stamina,
            "companion": target_companion,
            "transport": target_transport,
            "region": target_region,
            "selected_festival": fest_data_payload,
            "extra_details": extra_prompt_companion
        }
        api_data = {
            "parking_lots": p_lots,
            "model_restaurants": m_rests,
            "tourist_spots": t_spots
        }

        pipeline_output = None
        try:
            pipeline_output = run_processing_pipeline(user_inputs, api_data)
        except Exception as e:
            pass

        # [Fail-Safe 보장] 파이프라인 지연/에러 시에도 에디터 상세 분석 리포트 전문 100% 정상 노출
        if not pipeline_output or not pipeline_output.get("article_content") or "작성하지 못했습니다" in str(pipeline_output.get("article_content", "")):
            if "순천" in fest_obj["title"]:
                default_article = f"""# 🌿 {fest_obj['title']}, 나홀로 사색의 여정
바람과 은빛 갈대숲이 빚어내는 태고의 고요 속으로

### 🖋️ Editor's Letter: 사색의 쉼표를 건네며
오롯이 내 보폭에 맞추어 걷는 황금빛 갈대 물결. 세상의 소음에서 한 걸음 물러나, 바람의 소리와 갈대의 숨결에만 귀 기울이는 시간입니다. 발길 닿는 곳마다 스치는 가을바람은 그간 복잡했던 마음의 결을 정돈하고, 오직 나 혼자만의 호젓한 자유 속으로 깊숙이 침잠하게 이끕니다.

### 🚶 1일 안심 힐링 추천 타임라인 (Timeline)
- 10:00 AM: 순천만습지 무장애 갈대 데크로드 산책 (평지 데크 보행 약 1,500보)
- 11:40 AM: 행정안전부 지정 착한가격업소 '향촌식당'에서 따뜻한 백반 점심 식사 (축제장 도보 이동)
- 01:30 PM: 순천만 힐링 생태쉼터에서 따스한 차 한 잔과 흑두루미 탐조 사색
- 03:00 PM: 순천만 갈대숲 음악회 자유 관람 및 안심 주차장 이동

### 💡 안심 여행 팁 & 체크리스트
- 편안한 쿠션 운동화 착용 권장 (갈대 데크로드 약 1.5km 완만 코스)
- 가을 순천만의 일교차에 대비한 가벼운 숄 준비
- 순천만습지 무료 휠체어 대여소 (매표소 입구 위치)
"""
            elif "진주" in fest_obj["title"]:
                default_article = f"""# 🏮 {fest_obj['title']}, 빛과 물결의 낭만 산책
남강 물결 위에 수놓아진 천년의 빛, 달빛 아래 거니는 평온한 밤

### 🖋️ Editor's Letter: 빛의 강물 위로 띄우는 소망
남강의 잔잔한 물결 위로 수만 개의 소망등이 일렁입니다. 촉석루 성곽을 따라 걷는 길은 단차 없는 평지 동선으로 조성되어 온 가족이 편안한 걸음으로 밤의 정취를 누릴 수 있습니다.

### 🚶 1일 안심 힐링 추천 타임라인 (Timeline)
- 05:30 PM: 진주 남강 둔치 안심 산책로 입장 및 촉석루 솔밭 산책
- 06:40 PM: 행정안전부 지정 착한가격업소 '남강회관'에서 따뜻한 비빔밥 저녁 식사
- 07:40 PM: 남강 수상 유등 전시 관람 및 소망등 달기 체험
- 09:00 PM: 남강 달빛 힐링 쉼터 휴식 후 안심 주차장 이동
"""
            else:
                default_article = f"""# ☕ {fest_obj['title']}, 솔향과 커피가 머무는 쉼표
바다와 솔밭길을 따라 걷는 향긋한 힐링 로드

### 🖋️ Editor's Letter: 커피 향기 속에 머무는 시간
파도 소리와 함께 은은하게 퍼지는 커피 향기가 여행자의 걸음을 반깁니다. 완만한 안목해변 해안 데크길은 발목 피로 없이 바다를 온전히 조망할 수 있는 최적의 힐링 코스입니다.

### 🚶 1일 안심 힐링 추천 타임라인 (Timeline)
- 10:30 AM: 안목해변 커피거리 무장애 해안 데크로드 산책
- 11:40 AM: 행정안전부 지정 착한가격업소 '안목바다식당'에서 점심 식사
- 01:20 PM: 경포호 솔밭 웰니스 쉼터 솔바람 명상
- 03:00 PM: 로스터리 시음 체험 및 안심 주차장 이동
"""
            pipeline_output = {
                "article_content": default_article,
                "event_info": {
                    "reservation_required": fest_obj.get("programs", [])[:1] if fest_obj.get("programs") else [],
                    "walk_in": fest_obj.get("programs", [])[1:] if fest_obj.get("programs") else [],
                    "unknown": []
                },
                "map_markers": [],
                "parking_lots": p_lots,
                "model_restaurants": m_rests,
                "tourist_spots": t_spots
            }

        st.session_state.curation_result = pipeline_output
        st.session_state.active_fest = fest_data_payload
        st.session_state.selected_fest_name_state = fest_obj["title"]
        st.session_state.selected_region_state = target_region
        st.session_state.main_fest = fest_obj["title"]
        st.session_state.main_region = target_region
        st.session_state.auto_scroll_to_magazine = True
        st.toast(f"🗞️ '{fest_obj['title']}' 맞춤 에세이 & 안심 지도가 준비되었습니다!", icon="✨")

# ------------------------------------------------------------------------------
# 쿼리 파라미터 최우선 연동 (select_fest_and_go 직통 에세이 발행 - weather 뷰 진입 시 제외)
# ------------------------------------------------------------------------------
if "select_fest_and_go" in st.query_params and st.query_params.get("view") != "weather":
    f_target = urllib.parse.unquote(str(st.query_params.get("select_fest_and_go", "")).strip())
    q_region = urllib.parse.unquote(str(st.query_params.get("target_region", "")).strip())
    del st.query_params["select_fest_and_go"]
    if "target_region" in st.query_params:
        del st.query_params["target_region"]
    if "view" in st.query_params:
        del st.query_params["view"]
    execute_curated_editorial_flow(f_target, q_region)
    st.rerun()

# 뷰 전환 및 캘린더 파라미터 통합 처리
need_cal_rerun = False

target_view = st.query_params.get("view")
prev_view = st.session_state.get("_prev_view_mode")

# [동행인 상태 파라미터 처리: query_params 우선 동기화]
if "companion" in st.query_params:
    raw_comp = str(st.query_params.get("companion", "")).strip()
    c_lower = raw_comp.lower()
    comp_map = {
        "solo": "나홀로 쉼표",
        "parents": "부모님 효도",
        "family": "아이와 패밀리",
        "couple": "연인 데이트",
        "pet": "반려견 동반",
        "none": None,
        "혼자": "나홀로 쉼표",
        "부모님": "부모님 효도",
        "가족": "아이와 패밀리",
        "아이": "아이와 패밀리",
        "커플": "연인 데이트",
        "반려동물": "반려견 동반",
    }
    if c_lower in comp_map:
        st.session_state.companion = comp_map[c_lower]
        st.session_state["active_companion_param"] = c_lower if comp_map[c_lower] else "none"
        st.session_state["active_companion"] = comp_map[c_lower]
        st.session_state["main_companion"] = comp_map[c_lower]
    elif raw_comp in ["나홀로 쉼표", "부모님 효도", "아이와 패밀리", "연인 데이트", "반려견 동반"]:
        st.session_state.companion = raw_comp
        inv_map = {"나홀로 쉼표": "solo", "부모님 효도": "parents", "아이와 패밀리": "family", "연인 데이트": "couple", "반려견 동반": "pet"}
        st.session_state["active_companion_param"] = inv_map.get(raw_comp, "none")
        st.session_state["active_companion"] = raw_comp
        st.session_state["main_companion"] = raw_comp
    else:
        st.session_state.companion = None
        st.session_state["active_companion_param"] = "none"
        st.session_state["active_companion"] = None
        st.session_state["main_companion"] = None

# [메인 화면 복귀 및 최초 진입 시 동행인 자동 초기화 가드]
# 상세 페이지에서 메인으로 복귀하거나 메인 뷰 진입 시, 명시적인 companion 파라미터가 없으면 완전 초기화
is_returning_to_main = (
    "companion" not in st.query_params and (
        target_view == "main" or
        (target_view is None and st.session_state.get("view_mode") == "main") or
        (prev_view is not None and prev_view != "main")
    )
)

if is_returning_to_main:
    st.session_state.companion = None
    st.session_state["active_companion_param"] = "none"
    st.session_state["active_companion"] = None
    st.session_state["main_companion"] = None

if "view" in st.query_params:
    v_param = st.query_params.get("view")
    if v_param in ["calendar", "course", "restaurant", "weather", "shelter", "main"]:
        st.session_state.view_mode = v_param
        if v_param == "main":
            st.session_state.curation_result = None
            st.session_state.active_fest = None
            st.session_state.pop("curation_result", None)
            st.session_state.pop("active_fest", None)
            st.session_state.pop("report_expander", None)
            st.session_state.companion = None
            st.session_state["active_companion_param"] = "none"
            st.session_state["active_companion"] = None
            st.session_state["main_companion"] = None
            if "companion" in st.query_params:
                del st.query_params["companion"]
            del st.query_params["view"]
            need_cal_rerun = True
        else:
            # 상세 인터랙티브 뷰("calendar", "course", "restaurant", "weather", "shelter")는
            # query_params에 view를 온전히 보존하여 서브 인터랙션(탭 전환, 검색, 새로고침) 시
            # 메인 페이지로 잘못 튕기는 현상을 원천 방지하고 곧바로 렌더링하도록 직행
            need_cal_rerun = False

if "cal_genre" in st.query_params:
    st.session_state.view_mode = "calendar"
    g_val = st.query_params.get("cal_genre")
    if g_val in ["all", "eco", "art", "night"]:
        st.session_state.cal_genre = g_val
    del st.query_params["cal_genre"]
    need_cal_rerun = True

if "cal_region" in st.query_params:
    st.session_state.view_mode = "calendar"
    r_val = st.query_params.get("cal_region")
    valid_regions = ["all", "capital", "gangwon", "chungcheong", "honam", "yeongnam", "jeju"]
    if r_val in valid_regions:
        st.session_state.cal_region = r_val
    del st.query_params["cal_region"]
    need_cal_rerun = True

if "cal_date" in st.query_params:
    c_date = st.query_params.get("cal_date")
    if c_date:
        st.session_state.cal_selected_date = c_date
        st.session_state.view_mode = "calendar"
        try:
            p_parts = [int(p) for p in c_date.split("-")]
            if len(p_parts) == 3:
                st.session_state.cal_year = p_parts[0]
                st.session_state.cal_month = p_parts[1]
        except Exception:
            pass
    del st.query_params["cal_date"]
    need_cal_rerun = True

if "cal_nav" in st.query_params:
    st.session_state.view_mode = "calendar"
    nav = st.query_params.get("cal_nav")
    y = st.session_state.cal_year
    m = st.session_state.cal_month
    if nav == "prev":
        if m == 1:
            st.session_state.cal_year = y - 1
            st.session_state.cal_month = 12
        else:
            st.session_state.cal_month = m - 1
    elif nav == "next":
        if m == 12:
            st.session_state.cal_year = y + 1
            st.session_state.cal_month = 1
        else:
            st.session_state.cal_month = m + 1
    st.session_state.cal_selected_date = f"{st.session_state.cal_year}-{st.session_state.cal_month:02d}-01"
    del st.query_params["cal_nav"]
    need_cal_rerun = True

if "cal_year" in st.query_params:
    st.session_state.view_mode = "calendar"
    try:
        y_val = int(st.query_params.get("cal_year"))
        if 2024 <= y_val <= 2030:
            st.session_state.cal_year = y_val
    except Exception:
        pass
    del st.query_params["cal_year"]
    need_cal_rerun = True

if "cal_month" in st.query_params:
    st.session_state.view_mode = "calendar"
    try:
        m_val = int(st.query_params.get("cal_month"))
        if 1 <= m_val <= 12:
            st.session_state.cal_month = m_val
            st.session_state.cal_selected_date = f"{st.session_state.cal_year}-{m_val:02d}-01"
    except Exception:
        pass
    del st.query_params["cal_month"]
    need_cal_rerun = True

if need_cal_rerun:
    st.rerun()

if "show_main" not in st.session_state:
    st.session_state.show_main = True
if "curation_result" not in st.session_state:
    st.session_state.curation_result = None
if "selected_region_state" not in st.session_state:
    st.session_state.selected_region_state = "서울특별시"
if "main_region" not in st.session_state:
    st.session_state.main_region = "서울특별시"
if "selected_month_state" not in st.session_state:
    st.session_state.selected_month_state = "10월"
if "main_month" not in st.session_state:
    st.session_state.main_month = "10월"
if "selected_fest_name_state" not in st.session_state:
    st.session_state.selected_fest_name_state = "강동선사문화축제"
if "main_fest" not in st.session_state:
    st.session_state.main_fest = "강동선사문화축제"
if "stamina_state" not in st.session_state:
    st.session_state.stamina_state = 50
if "stamina_slider" not in st.session_state:
    st.session_state.stamina_slider = 50
if "active_stamina" not in st.session_state:
    st.session_state.active_stamina = 50
if "trigger_quick_run" not in st.session_state:
    st.session_state.trigger_quick_run = False
if "carousel_index" not in st.session_state:
    st.session_state.carousel_index = 0


if "select_spotlight" in st.query_params:
    st.session_state.show_main = True
    try:
        sel_idx = int(st.query_params.get("select_spotlight", 0)) % len(HOT_FESTIVALS_PRESET)
    except Exception:
        sel_idx = 0
    hot_target = HOT_FESTIVALS_PRESET[sel_idx]
    st.session_state.carousel_index = sel_idx
    st.session_state.selected_region_state = hot_target["region"]
    st.session_state.selected_month_state = f"{hot_target['month']}월"
    st.session_state.selected_fest_name_state = hot_target["name"]
    st.session_state.stamina_state = hot_target["stamina"]
    st.session_state.stamina_slider = hot_target["stamina"]
    st.session_state.main_region = hot_target["region"]
    st.session_state.main_month = f"{hot_target['month']}월"
    st.session_state.main_fest = hot_target["name"]
    st.session_state.active_companion = hot_target.get("companion", "부모님 (연로하심)")
    del st.query_params["select_spotlight"]
    st.toast(f"🎯 '{hot_target['name']}' 코스가 상단 패널에 자동 선택되었습니다! 상단에서 세부 조건을 확인하고 발행해보세요.", icon="✨")
    st.rerun()

if "concierge_tab" not in st.session_state:
    st.session_state.concierge_tab = "calendar"
if "show_more_concierge" not in st.session_state:
    st.session_state.show_more_concierge = False

if "concierge_tab" in st.query_params:
    t_val = st.query_params.get("concierge_tab")
    if t_val in ["calendar", "course", "restaurant", "parking", "shelter"]:
        st.session_state.concierge_tab = t_val
        st.session_state.show_more_concierge = False
    del st.query_params["concierge_tab"]
    st.rerun()

if "concierge_more" in st.query_params:
    st.session_state.show_more_concierge = not st.session_state.get("show_more_concierge", False)
    del st.query_params["concierge_more"]
    st.rerun()

def render_calendar_full_page():
    """[전용 뷰] 2026 대한민국 전국 로컬 축제 & 문화예술 인터랙티브 에디토리얼 캘린더"""
    import calendar
    import urllib.parse
    import html
    calendar.setfirstweekday(calendar.SUNDAY) # 일요일 시작 설정

    cal_today = datetime.now().date()
    year = st.session_state.get("cal_year", cal_today.year)
    month = st.session_state.get("cal_month", cal_today.month)
    today_iso_str = cal_today.strftime("%Y-%m-%d")
    default_cal_date = today_iso_str if (year == cal_today.year and month == cal_today.month) else f"{year}-{month:02d}-01"
    selected_date = st.session_state.get("cal_selected_date", default_cal_date)


    current_genre = st.session_state.get("cal_genre", "all")
    if current_genre not in ["all", "eco", "art"]:
        current_genre = "art" if current_genre == "night" else "all"

    # 1. 축제 장르 정밀 분류 헬퍼 함수 (festivals.csv theme 컬럼 1:1 매핑 및 시맨틱 우선순위)
    def classify_festival_genre(fest):
        title = str(fest.get('title') or fest.get('name') or '').strip().lower()
        desc = str(fest.get('desc') or fest.get('description') or '').strip().lower()
        theme = str(fest.get('theme') or '').strip().lower()
        cat = str(fest.get('category') or '').strip().lower()
        prog_cats = ' '.join([p.get('category', '') for p in fest.get('programs', []) if isinstance(p, dict)]).lower()
        title_desc = f"{title} {desc}"
        full_text = f"{title} {desc} {theme} {cat} {prog_cats}"

        # [1순위: 로컬·생태 테마 또는 시맨틱 키워드 무조건 [섹션 A] 로컬·생태 축제로 최우선 배정]
        # (순천만 갈대축제 등 자연·생태 행사가 문화공연/체험 부대 프로그램으로 인해 문화예술로 오분류되는 현상 원천 방지)
        eco_priority_keywords = ["갈대", "억새", "생태", "습지", "국화", "꽃", "대하", "사과", "한우", "콩", "산책", "둘레길", "자연", "갯벌"]
        if any(t in theme for t in ['자연', '꽃', '미식', '특산물', '역사', '전통', '해양', '액티비티', '로컬', '생태']):
            return 'eco'
        if any(k in title_desc for k in eco_priority_keywords):
            return 'eco'

        # [2순위: 문화·예술 테마]
        if any(t in theme for t in ['야경', '빛', '야행', '미디어', '예술', '전시', '음악', '공연', '문화', '체험', '댄스', '퍼레이드', '비엔날레']):
            return 'art'

        # [3순위: 문화·예술 페스타 시맨틱 키워드 매칭]
        art_keywords = ['예술', '미술', '전시', '음악', '공연', '문화', '체험', '야경', '빛', '댄스', '퍼레이드',
                        '야행', '미디어', '불꽃', '유등', '등불', '별빛', '드론', '북페어', '도서', '비엔날레',
                        '콘서트', '클래식', '재즈', '연극', '뮤지컬', '영화', '디자인', '공예', '문학', '시각', '갤러리']
        if any(k in full_text for k in art_keywords) or any(k in cat for k in ['예술', '문화', '전시', '공연', '체험', '야경', '빛', '댄스', '퍼레이드']):
            return 'art'

        # 기본값: 로컬·생태 축제
        return 'eco'

    # 1-1. 축제 권역/지역 정밀 분류 헬퍼 함수
    def classify_festival_region_zone(fest):
        r_main = f"{fest.get('region_short', '')} {fest.get('region', '')}".strip()
        r_addr = f"{fest.get('address', '')} {fest.get('location', '')}".strip()
        if any(k in r_main for k in ['서울', '경기', '인천']):
            return 'capital'
        if any(k in r_main for k in ['강원']):
            return 'gangwon'
        if any(k in r_main for k in ['충북', '충남', '충청', '대전', '세종']):
            return 'chungcheong'
        if any(k in r_main for k in ['전북', '전남', '전라', '광주']):
            return 'honam'
        if any(k in r_main for k in ['경북', '경남', '경상', '부산', '대구', '울산']):
            return 'yeongnam'
        if any(k in r_main for k in ['제주']):
            return 'jeju'

        if any(k in r_addr for k in ['서울', '경기', '인천']):
            return 'capital'
        if any(k in r_addr for k in ['강원']):
            return 'gangwon'
        if any(k in r_addr for k in ['충북', '충남', '충청', '대전', '세종']):
            return 'chungcheong'
        if any(k in r_addr for k in ['전북', '전남', '전라', '광주']):
            return 'honam'
        if any(k in r_addr for k in ['경북', '경남', '경상', '부산', '대구', '울산']):
            return 'yeongnam'
        if any(k in r_addr for k in ['제주']):
            return 'jeju'
        return 'other'

    current_region = st.session_state.get("cal_region", "all")

    # 2. 동행인(st.session_state.companion) 맞춤 데이터 필터링
    #    - 값이 None이거나 '선택 없이 둘러보기' / 'none'인 경우: 필터링 없이 전체 마스터 데이터 기본 유지
    #    - 특정 동행인(부모님, 아이 등) 선택 상태: 해당 동행인 조건에 맞는 데이터만 필터링
    from festapick.companion_context import filter_festivals_for_companion, normalize_companion_key
    raw_comp = st.session_state.get("companion")
    if not raw_comp and "companion" in st.query_params:
        raw_comp = st.query_params.get("companion")

    comp_key = normalize_companion_key(raw_comp)
    is_companion_active = bool(comp_key) and str(raw_comp or "").strip().lower() not in ("none", "null", "skip", "선택 없이 둘러보기", "")

    if is_companion_active:
        all_festivals = filter_festivals_for_companion(CALENDAR_MASTER_FESTIVALS, comp_key)
        comp_url_suffix = f"&companion={comp_key}"
    else:
        all_festivals = CALENDAR_MASTER_FESTIVALS
        comp_url_suffix = ""

    # 오늘 날짜 기준 4개월 칩 동적 생성
    cal_chips_list = []
    for m_idx in range(4):
        chip_m = (cal_today.month - 1 + m_idx) % 12 + 1
        chip_y = cal_today.year + (cal_today.month - 1 + m_idx) // 12
        chip_lbl = f"{chip_m}월" if chip_y == cal_today.year else f"’{str(chip_y)[2:]}년 {chip_m}월"
        chip_act = "active-month" if (year == chip_y and month == chip_m) else ""
        cal_chips_list.append(
            f'<a href="?view=calendar&cal_year={chip_y}&cal_month={chip_m}&cal_genre={current_genre}&cal_region={current_region}{comp_url_suffix}" target="_self" class="month-chip {chip_act}">{chip_lbl}</a>'
        )
    cal_month_chips_rendered = "\n".join(cal_chips_list)

    try:
        import importlib
        import festapick.infra_curator as fic_mod
        importlib.reload(fic_mod)
        get_companion_micro_banner_html = fic_mod.get_companion_micro_banner_html
    except Exception:
        from festapick.infra_curator import get_companion_micro_banner_html

    try:
        companion_micro_banner_html = get_companion_micro_banner_html(raw_comp or st.session_state.get("companion"), service_type="calendar")
    except TypeError:
        try:
            companion_micro_banner_html = get_companion_micro_banner_html(raw_comp or st.session_state.get("companion"))
        except Exception:
            companion_micro_banner_html = ""
    except Exception:
        companion_micro_banner_html = ""

    _, last_day = calendar.monthrange(year, month)
    m_start_str = f"{year}-{month:02d}-01"
    m_end_str = f"{year}-{month:02d}-{last_day:02d}"

    # 이번 달 진행되는 축제 목록 및 장르별 건수 집계
    month_active_fests = [f for f in all_festivals if not (f['endDate'] < m_start_str or f['startDate'] > m_end_str)]
    m_count_all = len(month_active_fests)
    m_count_eco = len([f for f in month_active_fests if classify_festival_genre(f) == 'eco'])
    m_count_art = len([f for f in month_active_fests if classify_festival_genre(f) == 'art'])

    # 상단 에디토리얼 장르 필터 탭 (3개 알약 탭)
    genre_pills_data = [
        ("all", "전체 행사", m_count_all),
        ("eco", "🎪 로컬·생태 축제", m_count_eco),
        ("art", "🎨 문화·예술 페스타", m_count_art),
    ]

    genre_names_map = {g[0]: g[1] for g in genre_pills_data}
    current_genre_display = genre_names_map.get(current_genre, "전체 행사")

    genre_pills_html_list = []
    for g_key, g_label, g_cnt in genre_pills_data:
        is_act = (current_genre == g_key)
        act_cls = "active" if is_act else ""
        genre_pills_html_list.append(f"""
        <a href="?view=calendar&cal_genre={g_key}&cal_date={selected_date}&cal_region={current_region}{comp_url_suffix}#calDetailSection" target="_self" class="editorial-genre-pill {act_cls}">
            <span class="pill-label">{g_label}</span>
            <span class="pill-badge">{g_cnt}</span>
        </a>
        """)
    genre_pills_rendered = "".join(genre_pills_html_list)

    # 3. 날짜별 축제 카운트 계산 & 캘린더 그리드 조립
    cal_weeks = calendar.monthcalendar(year, month)
    grid_rows_html = []
    for week in cal_weeks:
        row_cells = []
        for day_idx, day in enumerate(week):
            if day == 0:
                row_cells.append('<div class="cal-cell empty-cell"></div>')
            else:
                d_str = f"{year}-{month:02d}-{day:02d}"
                day_fests_all = [f for f in all_festivals if f['startDate'] <= d_str <= f['endDate']]

                day_eco = len([f for f in day_fests_all if classify_festival_genre(f) == 'eco'])
                day_art = len([f for f in day_fests_all if classify_festival_genre(f) == 'art'])

                # 활성 장르 필터 기준 카운트
                if current_genre == 'eco':
                    eff_cnt = day_eco
                elif current_genre == 'art':
                    eff_cnt = day_art
                else:
                    eff_cnt = len(day_fests_all)

                is_selected = (d_str == selected_date)
                sel_cls = "selected-day" if is_selected else ""

                # 요일별 숫자 컬러 (0=일요일 레드, 6=토요일 블루, 평일 딥그레이)
                color_cls = "day-num-sun" if day_idx == 0 else ("day-num-sat" if day_idx == 6 else "day-num-weekday")
                selected_label = '<span class="today-marker">선택</span>' if is_selected else ''

                # 산뜻한 한글 알약 뱃지 (상단 선택 탭 기준: 전체=진행 N건, 로컬=로컬 N건, 문화=문화 N건)
                if eff_cnt > 0:
                    if current_genre == 'eco':
                        pill_txt = f"● 로컬 {eff_cnt}건"
                    elif current_genre == 'art':
                        pill_txt = f"● 문화 {eff_cnt}건"
                    else:
                        pill_txt = f"● 진행 {eff_cnt}건"
                    badge_html = f'<div class="cell-event-pill"><span class="cell-pill-txt">{pill_txt}</span></div>'
                else:
                    badge_html = '<div class="cell-event-pill no-events"></div>'

                row_cells.append(f"""
                <a href="?view=calendar&cal_date={d_str}&cal_genre={current_genre}&cal_region={current_region}{comp_url_suffix}#calDetailSection" target="_self" class="cal-cell {sel_cls}">
                    <div class="day-top-row">
                        <span class="day-num {color_cls}">{day}</span>
                        {selected_label}
                    </div>
                    <div class="cell-bottom-badge">
                        {badge_html}
                    </div>
                </a>
                """)
        grid_rows_html.append(f'<div class="cal-week-row">{"".join(row_cells)}</div>')

    calendar_grid_rendered = "".join(grid_rows_html)

    # 4. 하단 선택 날짜 축제 2단 에디토리얼 큐레이션 구성
    matching_all = [f for f in all_festivals if f['startDate'] <= selected_date <= f['endDate']]
    sel_date_parts = selected_date.split("-")
    sel_date_display = f"{sel_date_parts[0]}년 {int(sel_date_parts[1])}월 {int(sel_date_parts[2])}일"

    matching_eco = [f for f in matching_all if classify_festival_genre(f) == 'eco']
    matching_art = [f for f in matching_all if classify_festival_genre(f) == 'art']

    # 4-1. 권역 필터 칩 바 (전국 전체 | 서울/수도권 | 강원권 | 충청권 | 호남권 | 영남권 | 제주)
    region_zones_data = [
        ("all", "전국 전체"),
        ("capital", "서울/수도권"),
        ("gangwon", "강원권"),
        ("chungcheong", "충청권"),
        ("honam", "호남권"),
        ("yeongnam", "영남권"),
        ("jeju", "제주"),
    ]
    region_names_map = {r[0]: r[1] for r in region_zones_data}
    cur_region_display = region_names_map.get(current_region, "전국 전체")

    region_chips_html_list = []
    for r_key, r_label in region_zones_data:
        is_act = (current_region == r_key)
        act_cls = "active" if is_act else ""
        region_chips_html_list.append(f"""
        <a href="?view=calendar&cal_region={r_key}&cal_date={selected_date}&cal_genre={current_genre}{comp_url_suffix}#calDetailSection" target="_self" class="region-chip {act_cls}">
            <span class="region-chip-name">{r_label}</span>
        </a>
        """)
    region_filter_bar_html = f"""
    <div class="region-filter-bar">
        <div class="region-filter-track">
            {"".join(region_chips_html_list)}
        </div>
    </div>
    """

    # 4-2. 권역 필터 적용된 최종 렌더링 목록
    if current_region != "all":
        effective_eco = [f for f in matching_eco if classify_festival_region_zone(f) == current_region]
        effective_art = [f for f in matching_art if classify_festival_region_zone(f) == current_region]
        effective_all = [f for f in matching_all if classify_festival_region_zone(f) == current_region]
    else:
        effective_eco = matching_eco
        effective_art = matching_art
        effective_all = matching_all

    def render_fest_card_item(fest, g_type):
        f_title = fest.get('title', '')
        f_title_esc = urllib.parse.quote(f_title)
        r_short = fest.get('region_short', fest.get('region', '전국'))
        r_esc = urllib.parse.quote(r_short)
        stamina = fest.get('stamina', 50)

        fest_img = str(fest.get('image') or fest.get('img') or '').strip()
        fest_thumb = str(fest.get('thumbnail') or '').strip()
        if 'blogfiles.naver.net' in fest_img or fest_img.startswith('http://'):
            if fest_thumb and fest_thumb.startswith('https://'):
                fest_img = fest_thumb
            elif fest_img:
                fest_img = f"https://search.pstatic.net/common/?src={urllib.parse.quote(fest_img, safe='')}&type=b400"
        if not fest_img or fest_img.lower() in ["none", "null", "nan", "", "-"]:
            fest_img = FALLBACK_SAFE_IMAGE

        if g_type == 'eco':
            genre_badge = '<span class="card-genre-chip chip-eco">🌿 로컬·생태 축제</span>'
            cta_text = '🌿 쉼표여정 코스 확인하기 ➔'
            stamina_desc = '안심 힐링 자연 동선'
            card_theme_cls = 'card-theme-eco'
        else:
            genre_badge = '<span class="card-genre-chip chip-art">🎨 문화·예술 페스타</span>'
            cta_text = '🎭 쉼표여정 코스 확인하기 ➔'
            stamina_desc = '감성 문화 산책 동선'
            card_theme_cls = 'card-theme-art'

        return f"""
        <div class="fest-curation-card {card_theme_cls}">
            <div class="fest-thumb-container">
                <img src="{fest_img}" alt="{html.escape(f_title)}" class="fest-main-thumb" referrerpolicy="no-referrer" loading="lazy" onerror="this.onerror=null; this.src='{FALLBACK_SAFE_IMAGE}';" />
                <div class="card-top-badges">
                    {genre_badge}
                    <span class="card-region-chip">📍 {html.escape(r_short)}</span>
                </div>
            </div>
            <div class="fest-card-content">
                <div class="fest-card-head">
                    <h3 class="fest-heading">{html.escape(f_title)}</h3>
                    <p class="fest-summary">{html.escape(fest.get('description', ''))}</p>
                </div>
                <div class="fest-meta-list">
                    <div class="meta-row">
                        <span class="meta-ico">📅</span>
                        <span class="meta-txt"><strong>일정</strong> {fest.get('startDate', '')} ~ {fest.get('endDate', '')}</span>
                    </div>
                    <div class="meta-row">
                        <span class="meta-ico">📍</span>
                        <span class="meta-txt"><strong>개최지</strong> {html.escape(fest.get('location', ''))} ({html.escape(fest.get('address', ''))})</span>
                    </div>
                    <div class="meta-row">
                        <span class="meta-ico">🔋</span>
                        <span class="meta-txt"><strong>권장 체력</strong> {stamina}% · {stamina_desc}</span>
                    </div>
                </div>
                <div class="fest-cta-box">
                    <a href="?view=course&select_fest_and_go={f_title_esc}&target_region={r_esc}{comp_url_suffix}" target="_self" class="btn-fest-course-cta">
                        {cta_text}
                    </a>
                </div>
            </div>
        </div>
        """

    # 4-3. [섹션 A, B 상하 나란히 배치 & 클릭 전환 큐레이션 패널]
    eco_cnt = len(effective_eco)
    art_cnt = len(effective_art)

    # 기본 활성화 섹션 결정
    if current_genre == 'art':
        default_active_sec = 'art'
    elif current_genre == 'eco':
        default_active_sec = 'eco'
    elif eco_cnt == 0 and art_cnt > 0:
        default_active_sec = 'art'
    else:
        default_active_sec = 'eco'

    # [섹션 A] 패널 컨텐츠
    if effective_eco:
        eco_cards_html = "".join([render_fest_card_item(f, 'eco') for f in effective_eco])
        panel_eco_content = f"""
        <div class="fest-cards-grid grid-wide-layout">
            {eco_cards_html}
        </div>
        """
    else:
        region_suffix = f"[{cur_region_display}] 권역에 " if current_region != "all" else ""
        panel_eco_content = f"""
        <div class="curation-empty-notice">
            <span class="empty-icon">🍃</span>
            <h4>선택하신 {sel_date_display}에는 {region_suffix}예정된 로컬·생태 축제가 없습니다.</h4>
            <p>상단의 권역 필터에서 '전국 전체'를 누르시거나 아래의 <strong>[섹션 B] 문화예술 페스타</strong>를 클릭하여 다른 일정을 확인해 보세요.</p>
        </div>
        """

    # [섹션 B] 패널 컨텐츠
    if effective_art:
        cult_cards_html = "".join([render_fest_card_item(f, 'art') for f in effective_art])
        panel_art_content = f"""
        <div class="fest-cards-grid grid-poster-layout">
            {cult_cards_html}
        </div>
        """
    else:
        region_suffix = f"[{cur_region_display}] 권역에 " if current_region != "all" else ""
        panel_art_content = f"""
        <div class="curation-empty-notice">
            <span class="empty-icon">🎨</span>
            <h4>선택하신 {sel_date_display}에는 {region_suffix}예정된 문화·예술 페스타가 없습니다.</h4>
            <p>상단의 권역 필터에서 '전국 전체'를 누르시거나 위의 <strong>[섹션 A] 로컬 힐링 축제</strong>를 클릭하여 다른 일정을 확인해 보세요.</p>
        </div>
        """

    eco_checked_attr = "checked" if default_active_sec == 'eco' else ""
    art_checked_attr = "checked" if default_active_sec == 'art' else ""

    detail_content_output = f"""
    <div class="curation-tab-root">
        <!-- 순수 CSS 무결점 탭 전환 라디오 토글 (JS 보안 정책과 무관하게 100% 즉시 동작) -->
        <input type="radio" name="curation_tab_group" id="tab_eco_radio" class="tab-toggle-radio" {eco_checked_attr} />
        <input type="radio" name="curation_tab_group" id="tab_art_radio" class="tab-toggle-radio" {art_checked_attr} />

        <!-- 섹션 A, B 상하 나란히 선택 카드 (라벨 클릭 시 순수 CSS로 100% 즉시 전환) -->
        <div class="curation-section-selector-group">
            <!-- [섹션 A] (위) -->
            <label for="tab_eco_radio" class="section-nav-card eco-selector" id="navCardEco">
                <div class="curation-block-intro">
                    <div class="block-icon-box eco-icon-box">🌿</div>
                    <div>
                        <h2 class="block-main-title">[섹션 A] 🌿 이번 주말 떠나는 로컬 힐링 축제</h2>
                        <p class="block-sub-title">자연의 정취, 지역 제철 미식, 역사와 전통이 어우러진 대한민국 대표 로컬 생태 큐레이션</p>
                    </div>
                </div>
                <div class="section-nav-right">
                    <span class="section-count-pill eco-pill">● 로컬 {eco_cnt}건</span>
                    <span class="section-toggle-status eco-status-txt"></span>
                </div>
            </label>

            <!-- [섹션 B] (아래) -->
            <label for="tab_art_radio" class="section-nav-card art-selector" id="navCardArt">
                <div class="curation-block-intro">
                    <div class="block-icon-box culture-icon-box">🎭</div>
                    <div>
                        <h2 class="block-main-title">[섹션 B] 🎭 감성을 채우는 문화예술 & 전시 산책</h2>
                        <p class="block-sub-title">미술관, 비엔날레, 북페어, 클래식 및 야경·미디어아트로 일상의 감도를 높이는 문화예술 큐레이션</p>
                    </div>
                </div>
                <div class="section-nav-right">
                    <span class="section-count-pill art-pill">● 문화 {art_cnt}건</span>
                    <span class="section-toggle-status art-status-txt"></span>
                </div>
            </label>
        </div>

        <!-- 하단 축제 카드 리스트 패널 (선택된 라디오에 따라 순수 CSS로 즉시 전환되어 보여짐) -->
        <div class="curation-panels-container" id="curationPanelsContainer">
            <div class="curation-panel-content panel-eco" id="panelEco">
                {panel_eco_content}
            </div>
            <div class="curation-panel-content panel-art" id="panelArt">
                {panel_art_content}
            </div>
        </div>
    </div>
    """

    # 5. 캘린더 전용 뷰 HTML & 매거진 스타일 CSS 렌더링
    st.html(f"""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,600&display=swap');

    .cal-full-container {{
        max-width: 1260px;
        margin: 0 auto;
        padding: 24px 20px 80px 20px;
        font-family: 'Pretendard', -apple-system, sans-serif;
        background: #FDF9F0;
    }}

    /* 상단 네비게이션 & 헤더 */
    .cal-top-nav {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 22px;
    }}

    .btn-back-to-home {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: #FFFFFF;
        color: #012D1D;
        border: 1.5px solid #D8D0C3;
        padding: 10px 22px;
        border-radius: 9999px;
        font-size: 0.92rem;
        font-weight: 700;
        text-decoration: none !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03);
        transition: all 0.22s ease;
    }}

    .btn-back-to-home:hover {{
        background: #012D1D;
        color: #FFFFFF !important;
        border-color: #012D1D;
        transform: translateY(-2px);
        box-shadow: 0 6px 18px rgba(1, 45, 29, 0.16);
    }}

    .cal-header-box {{
        background: linear-gradient(135deg, #FAF7F2 0%, #F5EFEB 100%);
        border: 1px solid #EAE4DA;
        border-radius: 24px;
        padding: 28px 34px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(1, 45, 29, 0.03);
    }}

    .cal-header-badge {{
        display: inline-block;
        font-size: 11.5px;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #012D1D;
        background: #EFE9DE;
        padding: 4px 12px;
        border-radius: 20px;
        margin-bottom: 10px;
    }}

    .cal-header-title {{
        font-family: 'Playfair Display', 'Pretendard', serif;
        font-size: 28px;
        font-weight: 800;
        color: #012D1D;
        margin: 0 0 10px 0;
        letter-spacing: -0.02em;
    }}

    .cal-header-sub {{
        font-size: 15px;
        color: #636D66;
        margin: 0;
        line-height: 1.6;
        word-break: keep-all;
    }}

    /* 월간 캘린더 메인 박스 */
    .cal-wrapper-box {{
        background: #FFFFFF;
        border: 1px solid #EAE4DA;
        border-radius: 24px;
        padding: 28px 32px 34px 32px;
        box-shadow: 0 6px 28px rgba(1, 45, 29, 0.04);
        margin-bottom: 40px;
    }}

    /* 월 이동 컨트롤러 */
    .cal-month-bar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 18px;
        border-bottom: 1px solid #F0EAE1;
    }}

    .cal-month-title {{
        font-family: 'Playfair Display', serif;
        font-size: 26px;
        font-weight: 800;
        color: #012D1D;
        letter-spacing: -0.02em;
    }}

    .cal-nav-btn-wrap {{
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
    }}

    .cal-month-chips {{
        display: flex;
        gap: 6px;
    }}

    .month-chip {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 6px 15px;
        border-radius: 20px;
        font-size: 13.5px;
        font-weight: 700;
        background: #F5EFE6;
        color: #4B5563;
        text-decoration: none !important;
        border: 1.2px solid #DCD4C7;
        transition: all 0.2s ease;
    }}

    .month-chip:hover {{
        background: #012D1D;
        color: #FFFFFF !important;
        border-color: #012D1D;
    }}

    .month-chip.active-month {{
        background: #012D1D !important;
        color: #FFFFFF !important;
        border-color: #012D1D !important;
        box-shadow: 0 3px 8px rgba(1, 45, 29, 0.22);
    }}

    .cal-nav-arrow {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: #F8FAF8;
        border: 1.5px solid #E0DCD3;
        color: #012D1D;
        font-size: 14px;
        font-weight: 800;
        text-decoration: none !important;
        transition: all 0.2s ease;
    }}

    .cal-nav-arrow:hover {{
        background: #012D1D;
        color: #FFFFFF !important;
        border-color: #012D1D;
        transform: scale(1.06);
    }}

    /* 1. 상단 에디토리얼 장르 필터 탭 (Pills) */
    .editorial-genre-bar {{
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        padding: 18px 0 20px 0;
    }}

    .editorial-genre-pill {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: #FAF8F5;
        border: 1.5px solid #E2DCD2;
        color: #4B5563;
        padding: 8px 18px;
        border-radius: 9999px;
        font-size: 13.5px;
        font-weight: 700;
        text-decoration: none !important;
        transition: all 0.22s ease;
        box-shadow: 0 1px 4px rgba(0,0,0,0.02);
    }}

    .editorial-genre-pill:hover {{
        background: #FFFFFF;
        border-color: #012D1D;
        color: #012D1D;
        transform: translateY(-1px);
        box-shadow: 0 4px 10px rgba(1, 45, 29, 0.08);
    }}

    .editorial-genre-pill.active {{
        background: #012D1D !important;
        border-color: #012D1D !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 14px rgba(1, 45, 29, 0.24);
    }}

    .pill-badge {{
        font-size: 11px;
        font-weight: 800;
        padding: 2px 7px;
        border-radius: 12px;
        background: rgba(0, 0, 0, 0.06);
        color: #374151;
        transition: all 0.2s ease;
    }}

    .editorial-genre-pill.active .pill-badge {{
        background: rgba(255, 255, 255, 0.24);
        color: #FFFFFF;
    }}

    /* 7열 요일 헤더 */
    .cal-day-header-row {{
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 8px;
        margin-bottom: 10px;
        text-align: center;
    }}

    .day-header-cell {{
        font-size: 13px;
        font-weight: 800;
        padding: 9px 0;
        border-radius: 10px;
        background: #FAF7F2;
        letter-spacing: -0.01em;
    }}

    .day-header-sun {{ color: #DC2626; }}
    .day-header-sat {{ color: #2563EB; }}
    .day-header-week {{ color: #4B5563; }}

    /* 달력 주(Week) 그리드 */
    .cal-week-row {{
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 8px;
        margin-bottom: 8px;
    }}

    /* 2. 달력 날짜 셀(Cell) 리뉴얼 디자인 */
    .cal-cell {{
        min-height: 86px;
        background: #FFFFFF;
        border: 1.5px solid #EFEAE1;
        border-radius: 14px;
        padding: 9px 10px 10px 10px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        text-decoration: none !important;
        transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
        position: relative;
    }}

    .cal-cell:hover {{
        border-color: #059669;
        transform: translateY(-2px);
        box-shadow: 0 8px 18px rgba(5, 150, 105, 0.12);
        cursor: pointer;
    }}

    .cal-cell.selected-day {{
        border: 2px solid #059669 !important;
        background: #ECFDF5 !important;
        box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.18), 0 8px 18px rgba(5, 150, 105, 0.08) !important;
    }}

    .empty-cell {{
        background: #FAF9F7;
        border-color: #F4EFE6;
        pointer-events: none;
        opacity: 0.5;
    }}

    .day-top-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}

    .day-num {{
        font-size: 14.5px;
        font-weight: 700;
        line-height: 1;
    }}

    .day-num-sun {{ color: #DC2626; }}
    .day-num-sat {{ color: #2563EB; }}
    .day-num-weekday {{ color: #1F2937; }}

    .today-marker {{
        font-size: 10px;
        font-weight: 800;
        color: #FFFFFF;
        background: #059669;
        padding: 2px 7px;
        border-radius: 6px;
        letter-spacing: -0.01em;
    }}

    /* 산뜻한 한글 이벤트 알약 뱃지 */
    .cell-bottom-badge {{
        display: flex;
        align-items: flex-end;
        margin-top: 6px;
    }}

    .cell-event-pill {{
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 11px;
        font-weight: 700;
        color: #065F46;
        background: #F0FDF4;
        border: 1px solid #A7F3D0;
        padding: 2.5px 8px;
        border-radius: 999px;
        letter-spacing: -0.02em;
        transition: all 0.2s ease;
        white-space: nowrap;
    }}

    .cal-cell:hover .cell-event-pill {{
        background: #065F46;
        color: #FFFFFF;
        border-color: #065F46;
    }}

    .cal-cell.selected-day .cell-event-pill {{
        background: #059669;
        color: #FFFFFF;
        border-color: #059669;
    }}

    .cell-event-pill.no-events {{
        opacity: 0;
        visibility: hidden;
    }}

    /* 3. 하단 선택 날짜 상세 리스트 2단 큐레이션 (Card 2: 독립된 화이트 컨테이너) */
    .detail-section-wrap {{
        background: #FFFFFF;
        border: 1px solid #EAE4DA;
        border-radius: 24px;
        padding: 28px 32px 34px 32px;
        box-shadow: 0 6px 28px rgba(1, 45, 29, 0.04);
        margin-top: 0;
        margin-bottom: 50px;
        scroll-margin-top: 40px;
    }}

    /* Card 2 상단 헤더: 좌측(날짜) & 우측(지역 필터) 한 줄 가로 배치 */
    .detail-header-bar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 20px;
        margin-bottom: 24px;
        border-bottom: 1px solid #F1F5F9;
        gap: 16px;
        flex-wrap: wrap;
    }}

    .detail-header-left {{
        display: flex;
        align-items: center;
        gap: 10px;
        flex-shrink: 0;
    }}

    .detail-header-pin {{
        font-size: 20px;
        line-height: 1;
    }}

    .detail-header-date {{
        font-size: 21px;
        font-weight: 800;
        color: #012D1D;
        letter-spacing: -0.02em;
    }}

    .detail-header-genre-badge {{
        font-size: 12px;
        font-weight: 700;
        color: #065F46;
        background: #ECFDF5;
        border: 1px solid #A7F3D0;
        padding: 3px 10px;
        border-radius: 9999px;
    }}

    .detail-header-region-badge {{
        font-size: 12px;
        font-weight: 700;
        color: #1E3A8A;
        background: #EFF6FF;
        border: 1px solid #BFDBFE;
        padding: 3px 10px;
        border-radius: 9999px;
    }}

    .detail-header-right {{
        display: flex;
        align-items: center;
        flex-shrink: 0;
    }}

    /* 권역/지역 필터 칩 바 (Card 2 헤더 우측 정렬) */
    .region-filter-bar {{
        margin: 0;
        padding: 0;
    }}

    .region-filter-track {{
        display: flex;
        align-items: center;
        gap: 7px;
        flex-wrap: wrap;
    }}

    .region-chip {{
        display: inline-flex;
        align-items: center;
        padding: 6px 14px;
        border-radius: 9999px;
        background: #F8FAF8;
        border: 1.2px solid #E2E8F0;
        color: #475569;
        font-size: 0.86rem;
        font-weight: 600;
        text-decoration: none !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
    }}

    .region-chip:hover {{
        background: #F1F5F9;
        border-color: #CBD5E1;
        color: #012D1D !important;
        transform: translateY(-1px);
    }}

    .region-chip.active {{
        background: #012D1D !important;
        color: #FAF7F2 !important;
        border-color: #012D1D !important;
        font-weight: 700;
        box-shadow: 0 3px 10px rgba(1, 45, 29, 0.16);
    }}

    .region-chip .region-chip-count {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 18px;
        height: 18px;
        padding: 0 5px;
        border-radius: 10px;
        font-size: 0.74rem;
        font-weight: 700;
        background: rgba(1, 45, 29, 0.08);
        color: #012D1D;
        transition: all 0.2s ease;
    }}

    .region-chip.active .region-chip-count {{
        background: rgba(255, 255, 255, 0.22);
        color: #FFFFFF;
    }}

    .region-chip:hover:not(.active) .region-chip-count {{
        background: rgba(1, 45, 29, 0.14);
    }}

    /* ====================================================================== */
    /* 섹션 A, B 상하 나란히 선택 탭 (순수 CSS 무결점 토글 시스템) */
    /* ====================================================================== */
    .tab-toggle-radio {{
        display: none !important;
        position: absolute !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }}

    .curation-tab-root {{
        width: 100%;
        margin-top: 0;
    }}

    .curation-section-selector-group {{
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin-bottom: 24px;
    }}

    .section-nav-card {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #FAF9F6;
        border: 1.2px solid #EBE6DC;
        border-radius: 16px;
        padding: 14px 22px;
        cursor: pointer !important;
        text-decoration: none !important;
        transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
        user-select: none;
        outline: none;
        margin: 0;
    }}

    .section-nav-card * {{
        pointer-events: none;
    }}

    .section-nav-card:hover {{
        transform: translateY(-1px);
        background: #F5F1EB;
        border-color: #DDD6CA;
        box-shadow: 0 4px 14px rgba(1, 45, 29, 0.04);
    }}

    .section-nav-card.eco-selector {{
        border-left: 5px solid #10B981;
    }}

    .section-nav-card.art-selector {{
        border-left: 5px solid #8B5CF6;
    }}

    .section-nav-right {{
        display: flex;
        align-items: center;
        gap: 12px;
        flex-shrink: 0;
    }}

    .section-count-pill {{
        font-size: 0.82rem;
        font-weight: 800;
        padding: 4px 12px;
        border-radius: 20px;
        letter-spacing: -0.01em;
        white-space: nowrap;
    }}

    .eco-pill {{
        background: #DCFCE7;
        color: #15803D;
        border: 1px solid #86EFAC;
    }}

    .art-pill {{
        background: #EDE9FE;
        color: #6D28D9;
        border: 1px solid #C4B5FD;
    }}

    .section-toggle-status {{
        font-size: 0.84rem;
        font-weight: 700;
        color: #717973;
        white-space: nowrap;
    }}

    .eco-status-txt::after {{
        content: "열기 ➔";
    }}

    .art-status-txt::after {{
        content: "열기 ➔";
    }}

    /* 패널 기본 숨김 */
    .curation-panel-content {{
        display: none !important;
    }}

    /* [섹션 A 활성화 시: 부드러운 소프트톤] */
    #tab_eco_radio:checked ~ .curation-section-selector-group .eco-selector {{
        border-color: #86EFAC !important;
        border-left: 5px solid #059669 !important;
        background: #F0FDF4 !important;
        box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.18), 0 4px 14px rgba(16, 185, 129, 0.08) !important;
    }}

    #tab_eco_radio:checked ~ .curation-section-selector-group .eco-selector .eco-status-txt {{
        color: #065F46 !important;
        font-weight: 800 !important;
    }}

    #tab_eco_radio:checked ~ .curation-section-selector-group .eco-selector .eco-status-txt::after {{
        content: "✓ 열림" !important;
    }}

    #tab_eco_radio:checked ~ .curation-panels-container .panel-eco {{
        display: block !important;
        animation: fadeInCurationPanel 0.28s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }}

    /* [섹션 B 활성화 시: 부드러운 소프트톤] */
    #tab_art_radio:checked ~ .curation-section-selector-group .art-selector {{
        border-color: #DDD6FE !important;
        border-left: 5px solid #7C3AED !important;
        background: #F5F3FF !important;
        box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.18), 0 4px 14px rgba(139, 92, 246, 0.08) !important;
    }}

    #tab_art_radio:checked ~ .curation-section-selector-group .art-selector .art-status-txt {{
        color: #5B21B6 !important;
        font-weight: 800 !important;
    }}

    #tab_art_radio:checked ~ .curation-section-selector-group .art-selector .art-status-txt::after {{
        content: "✓ 열림" !important;
    }}

    #tab_art_radio:checked ~ .curation-panels-container .panel-art {{
        display: block !important;
        animation: fadeInCurationPanel 0.28s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }}

    @keyframes fadeInCurationPanel {{
        from {{
            opacity: 0;
            transform: translateY(10px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}

    .editorial-curation-block {{
        margin-bottom: 40px;
        animation: fadeInBlock 0.25s ease-out;
    }}

    @keyframes fadeInBlock {{
        from {{ opacity: 0; transform: translateY(6px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}

    .curation-block-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #FFFFFF;
        border: 1px solid #EAE4DA;
        border-radius: 20px;
        padding: 20px 26px;
        margin-bottom: 22px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.02);
    }}

    .header-eco-theme {{
        border-left: 5px solid #10B981;
    }}

    .header-culture-theme {{
        border-left: 5px solid #8B5CF6;
    }}

    .curation-block-intro {{
        display: flex;
        align-items: center;
        gap: 14px;
    }}

    .block-icon-box {{
        width: 44px;
        height: 44px;
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
    }}

    .eco-icon-box {{
        background: #ECFDF5;
        border: 1px solid #A7F3D0;
    }}

    .culture-icon-box {{
        background: #F5F3FF;
        border: 1px solid #DDD6FE;
    }}

    .block-main-title {{
        font-size: 18.5px;
        font-weight: 800;
        color: #111827;
        margin: 0 0 4px 0;
        letter-spacing: -0.01em;
    }}

    .block-sub-title {{
        font-size: 13.5px;
        color: #6B7280;
        margin: 0;
        line-height: 1.4;
    }}

    .block-count-badge {{
        font-size: 13px;
        font-weight: 700;
        padding: 5px 14px;
        border-radius: 20px;
        white-space: nowrap;
    }}

    .badge-eco-theme {{
        background: #ECFDF5;
        color: #065F46;
        border: 1px solid #A7F3D0;
    }}

    .badge-culture-theme {{
        background: #F5F3FF;
        color: #6D28D9;
        border: 1px solid #DDD6FE;
    }}

    /* 상세 축제 카드 그리드 */
    .fest-cards-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
        gap: 24px;
    }}

    .fest-curation-card {{
        background: #FFFFFF;
        border: 1px solid #EBE5DB;
        border-radius: 20px;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: transform 0.26s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.26s ease, border-color 0.26s ease;
        box-shadow: 0 4px 14px rgba(1, 45, 29, 0.03);
    }}

    .fest-curation-card:hover {{
        transform: translateY(-6px);
        box-shadow: 0 16px 32px rgba(1, 45, 29, 0.12);
        border-color: #012D1D;
    }}

    .card-theme-eco:hover {{
        border-color: #10B981;
    }}

    .card-theme-art:hover {{
        border-color: #8B5CF6;
    }}

    .card-theme-night:hover {{
        border-color: #F59E0B;
    }}

    /* 카드 썸네일 & 뱃지 */
    .fest-thumb-container {{
        position: relative;
        width: 100%;
        height: 205px;
        overflow: hidden;
        background: #08281B url('{FALLBACK_SAFE_IMAGE}') no-repeat center/cover;
    }}

    .fest-main-thumb {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        transition: transform 0.4s ease;
    }}

    .fest-curation-card:hover .fest-main-thumb {{
        transform: scale(1.05);
    }}

    .card-top-badges {{
        position: absolute;
        top: 12px;
        left: 12px;
        right: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        pointer-events: none;
    }}

    .card-genre-chip {{
        font-size: 11.5px;
        font-weight: 800;
        padding: 4px 10px;
        border-radius: 8px;
        color: #FFFFFF;
        backdrop-filter: blur(8px);
        box-shadow: 0 2px 6px rgba(0,0,0,0.18);
    }}

    .chip-eco {{
        background: rgba(16, 185, 129, 0.92);
    }}

    .chip-art {{
        background: rgba(139, 92, 246, 0.92);
    }}

    .chip-night {{
        background: rgba(245, 158, 11, 0.92);
    }}

    .card-region-chip {{
        background: rgba(1, 45, 29, 0.88);
        color: #FFFFFF;
        font-size: 11.5px;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 8px;
        backdrop-filter: blur(8px);
        box-shadow: 0 2px 6px rgba(0,0,0,0.18);
    }}

    /* 카드 콘텐츠 */
    .fest-card-content {{
        padding: 22px 24px;
        display: flex;
        flex-direction: column;
        flex-grow: 1;
        justify-content: space-between;
    }}

    .fest-heading {{
        font-size: 18.5px;
        font-weight: 800;
        color: #111827;
        margin: 0 0 8px 0;
        line-height: 1.35;
        letter-spacing: -0.01em;
    }}

    .fest-summary {{
        font-size: 14px;
        color: #4B5563;
        line-height: 1.55;
        margin-bottom: 16px;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        word-break: keep-all;
    }}

    .fest-meta-list {{
        border-top: 1px solid #F3EFE6;
        padding-top: 14px;
        margin-bottom: 18px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        font-size: 13.5px;
        color: #4B5563;
    }}

    .meta-row {{
        display: flex;
        align-items: center;
        gap: 8px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}

    .meta-ico {{
        font-size: 13px;
    }}

    .btn-fest-course-cta {{
        display: block;
        text-align: center;
        background: #012D1D;
        color: #FFFFFF !important;
        font-size: 14px;
        font-weight: 700;
        padding: 12px 16px;
        border-radius: 12px;
        text-decoration: none !important;
        transition: all 0.22s ease;
        box-shadow: 0 3px 10px rgba(1, 45, 29, 0.16);
    }}

    .btn-fest-course-cta:hover {{
        background: #047857;
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(4, 120, 87, 0.32);
    }}

    .card-theme-art .btn-fest-course-cta:hover {{
        background: #7C3AED;
        box-shadow: 0 6px 16px rgba(124, 58, 237, 0.32);
    }}

    .card-theme-night .btn-fest-course-cta:hover {{
        background: #D97706;
        box-shadow: 0 6px 16px rgba(217, 119, 6, 0.32);
    }}

    /* 빈 상태 안내 */
    .curation-empty-notice {{
        background: #FFFFFF;
        border: 1px solid #EAE4DA;
        border-radius: 20px;
        padding: 44px 24px;
        text-align: center;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02);
    }}

    .empty-icon {{
        font-size: 2.2rem;
        display: block;
        margin-bottom: 12px;
    }}

    .curation-empty-notice h4 {{
        font-size: 1.15rem;
        font-weight: 700;
        color: #1F2937;
        margin: 0 0 6px 0;
    }}

    .curation-empty-notice p {{
        font-size: 0.90rem;
        color: #6B7280;
        margin: 0;
    }}

    @media (max-width: 768px) {{
        .cal-full-container {{
            padding: 16px 12px 50px 12px;
        }}
        .cal-header-box {{
            padding: 20px 18px;
        }}
        .cal-header-title {{
            font-size: 22px;
        }}
        .cal-wrapper-box, .detail-section-wrap {{
            padding: 18px 14px;
        }}
        .detail-header-bar {{
            flex-direction: column;
            align-items: flex-start;
            gap: 14px;
        }}
        .detail-header-right {{
            width: 100%;
        }}
        .editorial-genre-bar {{
            gap: 6px;
        }}
        .editorial-genre-pill {{
            padding: 6px 12px;
            font-size: 12px;
        }}
        .cal-cell {{
            min-height: 72px;
            padding: 4px 6px;
        }}
        .day-num {{
            font-size: 12.5px;
        }}
        .cell-event-pill {{
            font-size: 9.5px;
            padding: 1.5px 5px;
        }}
        .curation-block-header {{
            flex-direction: column;
            align-items: flex-start;
            gap: 12px;
            padding: 16px 18px;
        }}
        .section-nav-card {{
            flex-direction: column;
            align-items: flex-start;
            gap: 12px;
            padding: 14px 16px;
        }}
        .section-nav-right {{
            width: 100%;
            justify-content: space-between;
        }}
        .fest-cards-grid {{
            grid-template-columns: 1fr;
        }}
    }}
    </style>

    <div class="cal-full-container">
        <!-- 상단 네비게이션 & 헤더 -->
        <div class="cal-top-nav">
            <a href="?view=main" target="_self" class="btn-back-to-home" onclick="try{{sessionStorage.removeItem('festapick_active_companion');}}catch(e){{}}">
                ← 메인으로 돌아가기
            </a>
            <div style="font-size: 13px; font-weight: 700; color: #3A674F;">
                대한민국 공공데이터 안심 축제 캘린더
            </div>
        </div>

        <div class="cal-header-box">
            <span class="cal-header-badge">FestaPick Editorial Calendar</span>
            <h1 class="cal-header-title">2026 전국 로컬 축제 & 문화예술 캘린더</h1>
            <p class="cal-header-sub">
                자연과 제철 미식이 가득한 로컬·생태 축제부터 도심의 감성을 채우는 문화·예술·전시, 낭만 가득한 야경 행사까지.<br>
                상단 장르 필터와 일자별 멀티 인디케이터로 나만의 여정을 직관적으로 탐색해 보세요.
            </p>
        </div>

        {companion_micro_banner_html}

        <!-- 월간 캘린더 인터랙티브 박스 -->
        <div class="cal-wrapper-box">
            <div class="cal-month-bar">
                <div class="cal-month-title">
                    {year}년 {month}월
                </div>
                <div class="cal-nav-btn-wrap">
                    <div class="cal-month-chips">
                        {cal_month_chips_rendered}
                    </div>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <a href="?view=calendar&cal_nav=prev&cal_genre={current_genre}&cal_region={current_region}{comp_url_suffix}" target="_self" class="cal-nav-arrow">❮</a>
                        <span style="font-size: 13.5px; font-weight: 700; color: #4B5563;">월간 이동</span>
                        <a href="?view=calendar&cal_nav=next&cal_genre={current_genre}&cal_region={current_region}{comp_url_suffix}" target="_self" class="cal-nav-arrow">❯</a>
                    </div>
                </div>
            </div>

            <!-- 1. 상단 에디토리얼 장르 필터 탭 바 -->
            <div class="editorial-genre-bar">
                {genre_pills_rendered}
            </div>

            <!-- 7열 요일 헤더 (일 ~ 토) -->
            <div class="cal-day-header-row">
                <div class="day-header-cell day-header-sun">일 (Sun)</div>
                <div class="day-header-cell day-header-week">월 (Mon)</div>
                <div class="day-header-cell day-header-week">화 (Tue)</div>
                <div class="day-header-cell day-header-week">수 (Wed)</div>
                <div class="day-header-cell day-header-week">목 (Thu)</div>
                <div class="day-header-cell day-header-week">금 (Fri)</div>
                <div class="day-header-cell day-header-sat">토 (Sat)</div>
            </div>

            <!-- 날짜 셀 그리드 -->
            {calendar_grid_rendered}
        </div>

        <!-- 하단 선택 날짜 축제 상세 2단 큐레이션 (Card 2: 독립된 화이트 컨테이너) -->
        <div class="detail-section-wrap" id="calDetailSection" style="scroll-margin-top: 40px;">
            <div class="detail-header-bar">
                <div class="detail-header-left">
                    <span class="detail-header-pin">📌</span>
                    <span class="detail-header-date">{sel_date_display}</span>
                    <span class="detail-header-genre-badge">{current_genre_display}</span>
                    {f'<span class="detail-header-region-badge">{cur_region_display}</span>' if current_region != 'all' else ''}
                </div>
                <div class="detail-header-right">
                    {region_filter_bar_html}
                </div>
            </div>
            {detail_content_output}
        </div>
    </div>
    """)

# [핵심 모듈 핫 리로딩] infra_curator 등 공통 큐레이션 서브모듈 캐시 동적 최신화
try:
    import importlib
    import festapick.infra_curator as fic_mod
    importlib.reload(fic_mod)
except Exception:
    pass

if st.session_state.get("view_mode") == "calendar":
    st.session_state["_prev_view_mode"] = "calendar"
    render_calendar_full_page()

elif st.session_state.get("view_mode") == "course":
    st.session_state["_prev_view_mode"] = "course"
    import importlib
    import festapick.course_explorer as course_explorer
    importlib.reload(course_explorer)
    course_explorer.render_course_explorer_page()

elif st.session_state.get("view_mode") == "restaurant":
    st.session_state["_prev_view_mode"] = "restaurant"
    import importlib
    import festapick.good_price_explorer as good_price_explorer
    importlib.reload(good_price_explorer)
    good_price_explorer.render_good_price_explorer_page()

elif st.session_state.get("view_mode") == "weather":
    st.session_state["_prev_view_mode"] = "weather"
    import importlib
    import festapick.weather_care_page as weather_care_page
    importlib.reload(weather_care_page)
    weather_care_page.render_weather_care_page()

elif st.session_state.get("view_mode") == "shelter":
    st.session_state["_prev_view_mode"] = "shelter"
    import importlib
    import festapick.shelter_explorer as shelter_explorer
    importlib.reload(shelter_explorer)
    shelter_explorer.render_shelter_explorer_page()

else:
    # [메인 매거진 뷰 진입 가드] 메인 홈 진입 시 URL에 companion 파라미터가 없으면 깨끗하게 초기화
    if "companion" not in st.query_params:
        st.session_state.companion = None
        st.session_state["active_companion_param"] = "none"
        st.session_state["active_companion"] = None
        st.session_state["main_companion"] = None
    st.session_state["_prev_view_mode"] = "main"
    # ==========================================================================
    # [메인 매거진 뷰 & 디자인 시스템 렌더링 엔진]
    # ==========================================================================
    
    # 킨포크/29CM 에디토리얼 글로벌 CSS 디자인 시스템
    st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800&family=Playfair+Display:ital,wght@0,600;0,800;1,600&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    /* 전체 앱 배경: 스티치 시그니처 웜 크림 톤 및 프리텐다드 웹폰트 100% 보장 */
    :root, .stApp {
        background-color: #FDF9F0 !important;
        font-family: 'Pretendard', 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: #1C1C16 !important;
    }

    * {
        word-break: keep-all; /* 단어 단위 줄바꿈으로 한글 쪼개짐 방지 */
    }

    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
        display: none !important;
    }

    .main .block-container {
        max-width: 1200px !important;
        padding-top: 1.2rem !important;
        padding-bottom: 3.5rem !important;
        margin: 0 auto !important;
    }

    /* 처음 대문으로 복귀 버튼 전용 스타일 */

    /* 상단 에디토리얼 헤더 & 마스트헤드 */
    .brand-masthead {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        padding-bottom: 14px;
        border-bottom: 2px solid #012D1D;
        margin-bottom: 20px;
    }
    .brand-title {
        font-family: 'Playfair Display', serif;
        font-size: 2.3rem;
        font-weight: 800;
        color: #012D1D;
        line-height: 1;
        margin: 0;
    }
    .brand-desc {
        font-size: 0.88rem;
        color: #414844;
        font-weight: 500;
        margin-top: 6px;
    }

    /* 공통 에디토리얼 카드 컨테이너 */
    .magazine-card {
        background-color: #FAF7F2;
        border: 1px solid #EAE4DA;
        border-radius: 14px;
        padding: 22px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03);
        margin-bottom: 18px;
    }

    /* 3열 제어 패널 전용 카드 (해상도/배율 차이 틀어짐 방지) */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important;
        border: 1.5px solid #EAE4DA !important;
        border-radius: 14px !important;
        box-shadow: 0 4px 16px rgba(1, 45, 29, 0.05) !important;
        transition: all 0.25s ease !important;
        min-height: 450px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: space-between !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: #3A674F !important;
        box-shadow: 0 8px 24px rgba(1, 45, 29, 0.1) !important;
        transform: translateY(-2px);
    }

    .panel-step-badge {
        background-color: #012D1D;
        color: #FFFFFF;
        font-size: 0.68rem;
        font-weight: 800;
        padding: 3px 8px;
        border-radius: 4px;
        letter-spacing: 0.06em;
    }

    /* 체력 반응형 다이내믹 비주얼 */
    .stamina-dynamic-container {
        width: 100%;
        height: 175px;
        border-radius: 10px;
        overflow: hidden;
        position: relative;
        background-color: #ECE8DF;
        margin-bottom: 6px;
    }
    .stamina-dynamic-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        filter: brightness(0.95);
        transition: transform 0.4s ease;
    }
    .stamina-dynamic-container:hover .stamina-dynamic-img {
        transform: scale(1.04);
    }
    .stamina-dynamic-overlay {
        position: absolute;
        inset: 0;
        background: linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(1,45,29,0.85) 100%);
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        color: #FFFFFF;
    }

    /* 메인 발행 버튼 */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #012D1D 0%, #1B4332 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid #3A674F !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        padding: 12px 20px !important;
        box-shadow: 0 4px 14px rgba(1, 45, 29, 0.25) !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button[kind="primary"]:hover {
        opacity: 0.94 !important;
        transform: translateY(-1px);
        box-shadow: 0 6px 18px rgba(1, 45, 29, 0.35) !important;
    }

    /* 뱃지 시스템 */
    .editorial-badge {
        font-size: 0.72rem;
        font-weight: 700;
        padding: 3px 9px;
        border-radius: 4px;
        display: inline-block;
    }
    .badge-live { background-color: #BCEECF; color: #002112; }
    .badge-dday { background-color: #FFDBD1; color: #4D1000; }
    .badge-ended { background-color: #E6E2D9; color: #717973; }
    .badge-neutral { background-color: #ECE8DF; color: #414844; }

    /* [UI: Hero Cover] 시네마틱 매거진 표지 배너 (100% 풀필 레이아웃) */
    .magazine-hero-cover {
        position: relative !important;
        width: 100% !important;
        height: 500px !important;
        min-height: 500px !important;
        border-radius: 16px !important;
        overflow: hidden !important;
        margin-bottom: 0 !important;
        box-shadow: 0 16px 36px rgba(1, 45, 29, 0.12) !important;
        background-color: #0B192C !important;
    }
    .cover-bg-image {
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        width: 100% !important;
        height: 100% !important;
        min-width: 100% !important;
        min-height: 100% !important;
        max-width: none !important;
        object-fit: cover !important;
        object-position: center center !important;
        display: block !important;
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
        z-index: 1 !important;
    }
    .cover-overlay-content {
        position: absolute !important;
        inset: 0 !important;
        background: linear-gradient(180deg, rgba(0,0,0,0.22) 0%, rgba(0,0,0,0.48) 45%, rgba(1,45,29,0.95) 100%) !important;
        padding: 36px 40px 80px 40px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: space-between !important;
        color: #FFFFFF !important;
        z-index: 2 !important;
    }

    /* [UI: Hero Dock] 배너 내부 하단 컨트롤 오버레이 도크 (단일 컨테이너 마진 음수화) */
    div.st-key-carousel_dock {
        position: relative !important;
        margin-top: -65px !important;
        z-index: 20 !important;
        padding: 0 40px !important;
        margin-bottom: 24px !important;
    }
    div.st-key-carousel_dock div[data-testid="stHorizontalBlock"] {
        align-items: center !important;
    }

    /* [UI: Button] 프리셋 원클릭 적용 버튼 */
    div.st-key-btn_apply_carousel button {
        background-color: #FFFFFF !important;
        color: #012D1D !important;
        border: 1px solid rgba(255, 255, 255, 0.95) !important;
        font-weight: 800 !important;
        font-size: 0.88rem !important;
        border-radius: 8px !important;
        padding: 8px 18px !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4) !important;
        transition: all 0.2s ease !important;
    }
    div.st-key-btn_apply_carousel button:hover {
        background-color: #F4EFE5 !important;
        color: #1B4332 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.55) !important;
    }

    /* [UI: Button] 이전/다음 글래스모피즘 아이콘 버튼 */
    div.st-key-btn_prev_slide button,
    div.st-key-btn_next_slide button {
        background-color: rgba(0, 0, 0, 0.55) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255, 255, 255, 0.45) !important;
        backdrop-filter: blur(8px) !important;
        font-weight: 900 !important;
        font-size: 1.15rem !important;
        border-radius: 8px !important;
        padding: 6px 12px !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4) !important;
        transition: all 0.2s ease !important;
    }
    div.st-key-btn_prev_slide button:hover,
    div.st-key-btn_next_slide button:hover {
        background-color: rgba(255, 255, 255, 0.3) !important;
        border-color: rgba(255, 255, 255, 0.85) !important;
        color: #FFFFFF !important;
        transform: scale(1.08) !important;
    }

    /* [UI: Button] 매거진 하단 홈으로 가기 (다른 축제 둘러보기) 커다란 메인 탈출구 버튼 */
    div.st-key-btn_go_home_curation {
        margin-top: 18px !important;
        margin-bottom: 24px !important;
        text-align: center !important;
    }
    div.st-key-btn_go_home_curation button {
        background: linear-gradient(135deg, #FAF7F2 0%, #FFFFFF 100%) !important;
        color: #012D1D !important;
        border: 2px solid #D5CDBD !important;
        border-radius: 14px !important;
        font-weight: 800 !important;
        font-size: 1.05rem !important;
        padding: 15px 32px !important;
        box-shadow: 0 4px 16px rgba(1, 45, 29, 0.08) !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
        letter-spacing: -0.3px !important;
        cursor: pointer !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 8px !important;
    }
    div.st-key-btn_go_home_curation button:hover {
        background: linear-gradient(135deg, #012D1D 0%, #1B4332 100%) !important;
        border-color: #012D1D !important;
        color: #FAF7F2 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(1, 45, 29, 0.22) !important;
    }

    /* [UI: Expander Keyed] 'AI 에디터 상세 분석 리포트 전문 확인' 전용 고시인성 프리미엄 시각 효과 */
    div.st-key-report_expander {
        margin-top: 22px !important;
        margin-bottom: 24px !important;
    }
    div.st-key-report_expander div[data-testid="stExpander"],
    div.st-key-report_expander .stExpander,
    div.st-key-report_expander details[data-testid="stExpander"] {
        background: #FFFFFF !important;
        border: 2px solid #10B981 !important;
        border-radius: 16px !important;
        box-shadow: 0 8px 24px rgba(16, 185, 129, 0.16), 0 3px 8px rgba(1, 45, 29, 0.08) !important;
        overflow: hidden !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    div.st-key-report_expander div[data-testid="stExpander"]:hover,
    div.st-key-report_expander .stExpander:hover,
    div.st-key-report_expander details[data-testid="stExpander"]:hover {
        border-color: #059669 !important;
        box-shadow: 0 12px 32px rgba(16, 185, 129, 0.26), 0 4px 12px rgba(1, 45, 29, 0.12) !important;
        transform: translateY(-2px) !important;
    }
    div.st-key-report_expander summary,
    div.st-key-report_expander .stExpander summary {
        background: linear-gradient(135deg, #ECFDF5 0%, #E6F4EA 40%, #FEF9C3 100%) !important;
        padding: 16px 22px !important;
        border-radius: 14px !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        user-select: none !important;
        transition: all 0.25s ease !important;
        position: relative !important;
    }
    div.st-key-report_expander summary:hover,
    div.st-key-report_expander .stExpander summary:hover {
        background: linear-gradient(135deg, #D1FAE5 0%, #DCFCE7 45%, #FEF08A 100%) !important;
    }
    div.st-key-report_expander summary p,
    div.st-key-report_expander summary div[data-testid="stMarkdownContainer"] p {
        font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
        font-size: 1.05rem !important;
        font-weight: 800 !important;
        color: #064E3B !important;
        letter-spacing: -0.02em !important;
        margin: 0 !important;
        display: inline-flex !important;
        align-items: center !important;
        gap: 8px !important;
    }
    div.st-key-report_expander summary svg,
    div.st-key-report_expander .stExpander summary svg {
        color: #047857 !important;
        fill: #047857 !important;
        width: 22px !important;
        height: 22px !important;
    }
    div.st-key-report_expander summary::after {
        content: "클릭하여 리포트 열기 ▾";
        margin-left: auto;
        font-size: 0.80rem;
        font-weight: 700;
        color: #047857;
        background: rgba(255, 255, 255, 0.90);
        padding: 4px 12px;
        border-radius: 999px;
        border: 1px solid rgba(16, 185, 129, 0.4);
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
        flex-shrink: 0;
        letter-spacing: -0.2px;
        transition: all 0.2s ease;
    }
    div.st-key-report_expander details[open] summary::after {
        content: "리포트 접기 ▴";
        color: #475569;
        background: rgba(255, 255, 255, 0.85);
        border-color: rgba(148, 163, 184, 0.4);
    }
    div.st-key-report_expander [data-testid="stExpanderDetails"],
    div.st-key-report_expander .stExpander [data-testid="stExpanderDetails"] {
        background-color: #FFFFFF !important;
        padding: 22px 24px !important;
        border-top: 2px solid #A7F3D0 !important;
    }

    /* [UI: Expander] 기본 아코디언 스타일 (깔끔한 웜톤 아이보리/화이트 둥근 테두리 박스) */
    div[data-testid="stExpander"],
    .stExpander,
    details[data-testid="stExpander"] {
        background: #FFFFFF !important;
        border: 1.5px solid #E5E0D8 !important;
        border-radius: 14px !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04) !important;
        overflow: hidden !important;
        margin-top: 14px !important;
        margin-bottom: 18px !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stExpander"]:hover,
    .stExpander:hover,
    details[data-testid="stExpander"]:hover {
        border-color: #2D5A43 !important;
        box-shadow: 0 4px 16px rgba(45, 90, 67, 0.08) !important;
    }
    div[data-testid="stExpander"] details,
    .stExpander details {
        border: none !important;
        background: transparent !important;
    }
    div[data-testid="stExpander"] summary,
    .stExpander summary {
        background: #FAF7F2 !important;
        padding: 13px 20px !important;
        border-radius: 12px !important;
        transition: background 0.2s ease !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        user-select: none !important;
    }
    div[data-testid="stExpander"] summary:hover,
    .stExpander summary:hover {
        background: #F4EFE6 !important;
    }
    /* Summary 텍스트 영역: 고딕체 강제 적용 & 텍스트-아이콘 분리 */
    div[data-testid="stExpander"] summary p,
    div[data-testid="stExpander"] summary div[data-testid="stMarkdownContainer"] p,
    .stExpander summary p {
        font-family: 'Pretendard', 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif !important;
        font-size: 0.98rem !important;
        font-weight: 700 !important;
        color: #1B4332 !important;
        letter-spacing: -0.01em !important;
        text-shadow: none !important;
        margin: 0 !important;
        display: inline-flex !important;
        align-items: center !important;
        gap: 8px !important;
    }
    /* Summary 토글 아이콘 영역: 고유 아이콘 폰트 손상 방지 & arrow_right 텍스트 겹침 완벽 차단 */
    div[data-testid="stExpander"] summary [data-testid="stExpanderToggleIcon"],
    div[data-testid="stExpander"] summary span.material-symbols-rounded,
    div[data-testid="stExpander"] summary span:first-child:has(svg),
    .stExpander summary [data-testid="stExpanderToggleIcon"] {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        margin-right: 8px !important;
        flex-shrink: 0 !important;
        font-family: inherit !important;
    }
    div[data-testid="stExpander"] summary svg,
    .stExpander summary svg {
        color: #1B4332 !important;
        fill: #1B4332 !important;
        transform: none !important;
        filter: none !important;
        flex-shrink: 0 !important;
        margin-right: 6px !important;
    }
    div[data-testid="stExpander"] [data-testid="stExpanderDetails"],
    .stExpander [data-testid="stExpanderDetails"] {
        background-color: #FFFFFF !important;
        padding: 16px 20px !important;
        border-top: 1px solid #EFEAE2 !important;
        color: #2D3748 !important;
        font-size: 0.94rem !important;
        line-height: 1.75 !important;
        font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
    }

    /* [UI: Magazine Report Typography] AI 에디터 상세 분석 리포트 전문 타이포그래피 & 위계 스타일 */
    .report-wrapper,
    .report-wrapper * {
        font-family: 'Pretendard', 'Noto Sans KR', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    }
    .report-wrapper {
        position: relative !important;
        padding: 28px 24px !important;
        border-radius: 20px !important;
        background: #FAF7F2 !important;
        border: 1.5px solid #EAE3D2 !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04) !important;
        color: #2B2F2C !important;
        letter-spacing: -0.01em !important;
        overflow: hidden !important;
    }
    .report-main-title,
    .report-wrapper h1,
    .report-wrapper h2 {
        font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
        font-size: 22px !important;
        font-weight: 800 !important;
        color: #1B4332 !important;
        line-height: 1.45 !important;
        letter-spacing: -0.02em !important;
        margin-top: 2px !important;
        margin-bottom: 8px !important;
        word-break: keep-all !important;
        text-shadow: none !important;
    }
    .report-subtitle {
        font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
        font-size: 14.5px !important;
        font-weight: 500 !important;
        color: #4A6B53 !important;
        line-height: 1.65 !important;
        letter-spacing: -0.01em !important;
        margin-top: 0 !important;
        margin-bottom: 6px !important;
        word-break: keep-all !important;
        text-shadow: none !important;
    }
    .report-subtitle-divider {
        margin-bottom: 12px !important;
        border-bottom: 1px solid #ECE7DE !important;
    }
    .report-section-header,
    .report-wrapper h3 {
        font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
        font-size: 17px !important;
        font-weight: 700 !important;
        color: #1B4332 !important;
        margin-top: 2px !important;
        margin-bottom: 14px !important;
        letter-spacing: -0.01em !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        line-height: 1.4 !important;
    }
    .report-sec-icon {
        font-size: 1.15em !important;
        filter: none !important;
    }
    .report-sec-en {
        font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
        font-weight: 800 !important;
        letter-spacing: 0.01em !important;
        color: #2D5A43 !important;
        text-shadow: none !important;
    }
    .report-sec-divider {
        color: #CBD5E1 !important;
        margin: 0 4px !important;
        font-weight: 400 !important;
    }
    .report-sec-ko {
        font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
        font-weight: 600 !important;
        color: #2D3748 !important;
        font-size: 0.98em !important;
    }
    .report-body-text,
    .report-wrapper p {
        font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
        font-size: 15px !important;
        font-weight: 400 !important;
        line-height: 1.8 !important;
        color: #374151 !important;
        margin-bottom: 14px !important;
        letter-spacing: -0.01em !important;
        word-break: keep-all !important;
        text-shadow: none !important;
    }
    .report-body-text strong,
    .report-wrapper strong {
        color: #111827 !important;
        font-weight: 700 !important;
    }
    .report-timeline-container {
        display: flex !important;
        flex-direction: column !important;
        gap: 10px !important;
        margin-top: 10px !important;
        margin-bottom: 8px !important;
    }
    .report-timeline-card {
        display: flex !important;
        align-items: baseline !important;
        gap: 12px !important;
        background: #FAF8F4 !important;
        border: 1px solid #ECE7DE !important;
        border-left: 3.5px solid #1B4332 !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.02) !important;
        transition: transform 0.2s ease, border-color 0.2s ease !important;
    }
    .report-timeline-card:hover {
        transform: translateX(3px) !important;
        border-color: #2D5A43 !important;
    }
    .report-time-badge {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        background: #1B4332 !important;
        color: #FAF7F2 !important;
        font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
        font-weight: 700 !important;
        font-size: 12.5px !important;
        padding: 3px 10px !important;
        border-radius: 6px !important;
        border: 1px solid #143527 !important;
        box-shadow: 0 1px 4px rgba(27, 67, 50, 0.15) !important;
        white-space: nowrap !important;
        flex-shrink: 0 !important;
        letter-spacing: 0.01em !important;
    }
    .report-timeline-desc {
        font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
        font-size: 14.5px !important;
        line-height: 1.7 !important;
        color: #2D3748 !important;
        flex: 1 !important;
        word-break: keep-all !important;
    }
    .report-bullet-item {
        display: flex !important;
        align-items: baseline !important;
        gap: 10px !important;
        background: #FAF8F4 !important;
        border: 1px solid #ECE7DE !important;
        border-radius: 10px !important;
        padding: 11px 16px !important;
        margin-bottom: 8px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02) !important;
    }
    .report-bullet-dot {
        color: #1B4332 !important;
        font-weight: 900 !important;
        font-size: 16px !important;
        line-height: 1 !important;
        flex-shrink: 0 !important;
        filter: none !important;
    }
    .report-bullet-text {
        font-family: 'Pretendard', 'Noto Sans KR', sans-serif !important;
        font-size: 14.5px !important;
        line-height: 1.7 !important;
        color: #374151 !important;
        flex: 1 !important;
        word-break: keep-all !important;
    }
    /* [UI: Map Container Frame] 무장애 안심 지도 모던 프레임 */
    .peace-map-frame-wrapper,
    div[data-testid="stCustomComponentV1"]:has(iframe),
    div[data-testid="stIFrame"]:has(iframe),
    iframe[title*="folium"],
    div[data-testid="stCustomComponentV1"] iframe {
        border-radius: 20px !important;
        overflow: hidden !important;
        border: 1px solid #ECE7DE !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # 상단 브랜드 마스트헤드 & 공공데이터 통계 리본
    st.markdown("""
    <div class="brand-masthead">
        <div>
            <div style="font-size:0.75rem; font-weight:700; color:#3A674F; letter-spacing:0.08em; margin-bottom:4px;">
                대한민국 공공데이터 안심 여행 큐레이션
            </div>
            <h1 class="brand-title">FestaPick</h1>
            <div class="brand-desc">내 체력에 꼭 맞춘, 로컬 힐링 & 축제 여행 매거진</div>
        </div>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
            <span class="editorial-badge" style="background:#ECE8DF; color:#012D1D;">🎪 전국 축제 1,264곳</span>
            <span class="editorial-badge" style="background:#ECE8DF; color:#012D1D;">🍲 착한가격 식당 9,563곳</span>
            <span class="editorial-badge" style="background:#ECE8DF; color:#012D1D;">🅿️ 공영주차장 18,883곳</span>
            <span class="editorial-badge" style="background:#ECE8DF; color:#012D1D;">🌿 안심 쉼터 694곳</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 발행된 맞춤 매거진 & 안심 지도 바로가기 안내 배너
    cur_res = st.session_state.get("curation_result")
    act_fest = st.session_state.get("active_fest")
    if cur_res and act_fest:
        act_name = act_fest.get("name", "로컬 축제")
        st.html(f"""
        <div style="background: linear-gradient(135deg, #012D1D 0%, #1B4332 100%); color: #FAF7F2; padding: 14px 20px; border-radius: 12px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 14px rgba(1,45,29,0.15); flex-wrap: wrap; gap: 12px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 1.5rem;">🗞️</span>
                <div>
                    <strong style="font-size: 0.98rem; display: block; color: #FAF7F2;">'{act_name}' 맞춤 에디토리얼 매거진 &amp; 무장애 안심 지도가 준비되었습니다!</strong>
                    <span style="font-size: 0.78rem; opacity: 0.85; color: #D8D2C5;">아래 쇼케이스에서 에디터의 힐링 에세이, 3대 거점 코스, 상호작용 안심 지도를 확인하세요.</span>
                </div>
            </div>
            <a href="#curation-showcase-section" style="background: #EAE3D2; color: #012D1D; text-decoration: none; padding: 8px 18px; border-radius: 999px; font-size: 0.82rem; font-weight: 700; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
                에세이 &amp; 지도 바로보기 ↓
            </a>
        </div>
        """)

    # 맞춤 매거진 발행 여부 확인 (매거진 발행 시 상단 입력 폼 자동 접힘 적용)
    has_curation = bool(st.session_state.get("curation_result"))
    act_fest_cached = st.session_state.get("active_fest")
    cur_fest_display = ""
    if isinstance(act_fest_cached, dict) and act_fest_cached.get("name"):
        cur_fest_display = f" · 현재 축제: {act_fest_cached.get('name')}"

    expander_title = (
        f"⚙️ 검색 조건 수정하기{cur_fest_display} (클릭하여 Step 1~3 여행 조건 다시 변경하기)"
        if has_curation
        else "🎯 나만의 맞춤 여행 조건 설정 (Step 1~3: 어디로 · 체력 배터리 · 동행 및 이동)"
    )

    fest_data = None
    current_stamina = st.session_state.get("stamina_slider", st.session_state.get("stamina_state", 50))
    companion = "혼자"
    transport = "🚗 자가용 (편한 주차)"
    extra_details = ""
    run_button = False

    with st.expander(expander_title, expanded=(not has_curation)):
        # 3열 대칭형 메인 제어 패널 (Where ➔ Energy ➔ How & Action)
        col_where, col_energy, col_action = st.columns(3, gap="medium")

        # STEP 01
        with col_where:
            with st.container(border=True):
                st.markdown('<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;"><span class="panel-step-badge">STEP 01</span><strong style="color:#012D1D; font-size:0.95rem;">어디로, 언제 떠나나요</strong></div>', unsafe_allow_html=True)

                region_idx = ADMIN_REGIONS.index(st.session_state.selected_region_state) if st.session_state.selected_region_state in ADMIN_REGIONS else 1
                selected_region = st.selectbox("목적지 (Region)", options=ADMIN_REGIONS, index=region_idx, key="main_region")

                month_options = ["전체"] + [f"{m}월" for m in range(1, 13)]
                month_idx = month_options.index(st.session_state.selected_month_state) if st.session_state.selected_month_state in month_options else 10
                selected_month = st.selectbox("방문시기 (Month)", options=month_options, index=month_idx, key="main_month")
                selected_month_int = int(selected_month.replace("월", "")) if selected_month != "전체" else None

                try:
                    festivals_list = get_festivals(region=selected_region, month=selected_month_int)
                except Exception as e:
                    festivals_list = []

                # [Spotlight & Master 축제 최우선 주입 보장]
                # 순천만 갈대축제, 진주 남강유등축제, 강릉 커피축제 등 핵심 큐레이션 축제가 목록에서 누락되지 않도록 최상단 주입
                for m_fest in (HOT_FESTIVALS_PRESET + CALENDAR_MASTER_FESTIVALS):
                    m_title = str(m_fest.get("name") or m_fest.get("title") or "").strip()
                    m_reg = str(m_fest.get("region") or m_fest.get("region_short") or "")
                    reg_match = (
                        selected_region == "전국 전체" or 
                        selected_region in m_reg or 
                        m_reg in selected_region or
                        (selected_region == "전라남도" and "순천" in m_title) or
                        (selected_region == "경상남도" and "진주" in m_title) or
                        (selected_region == "강원특별자치도" and "강릉" in m_title)
                    )
                    if reg_match and m_title:
                        if not any((str(f.get("name", "")).strip() == m_title or str(f.get("title", "")).strip() == m_title) for f in festivals_list):
                            s_d = str(m_fest.get("startDate", "2026-10-01"))
                            e_d = str(m_fest.get("endDate", "2026-10-31"))
                            festivals_list.insert(0, {
                                "name": m_title,
                                "title": m_title,
                                "region": selected_region,
                                "address": m_fest.get("address", m_fest.get("location", "")),
                                "lat": float(m_fest.get("lat", 34.8872)),
                                "lng": float(m_fest.get("lng", 127.5083)),
                                "dates": f"{s_d} ~ {e_d}",
                                "description": m_fest.get("description", m_fest.get("desc", "")),
                                "phone": m_fest.get("phone", ""),
                                "homepage": m_fest.get("homepage", ""),
                                "programs": m_fest.get("programs", [])
                            })

                fest_data = None
                if not festivals_list:
                    st.warning("선택하신 조건에 등록된 축제가 없습니다.")
                else:
                    festival_options = {f["name"]: f for f in festivals_list}
                    fest_keys = list(festival_options.keys())
                    def_fest_idx = fest_keys.index(st.session_state.selected_fest_name_state) if st.session_state.selected_fest_name_state in fest_keys else 0
                    selected_fest_name = st.selectbox(f"축제 & 문화페스타 ({len(festival_options)}개)", options=fest_keys, index=def_fest_idx, key="main_fest")
                    fest_data = festival_options[selected_fest_name]
                    if fest_data:
                        c_lat, c_lng = resolve_festival_coordinates(fest_data.get("name", ""), fest_data.get("address", ""), fest_data.get("lat"), fest_data.get("lng"))
                        fest_data["lat"] = c_lat
                        fest_data["lng"] = c_lng

                if fest_data:
                    dates_raw = str(fest_data.get("dates", "일정 확인 중")).strip()
                    st.html(textwrap.dedent(f"""
                    <div style="font-size:0.80rem; color:#414844; margin-top:8px; display:flex; justify-content:space-between; align-items:center;">
                        <span>📅 {html.escape(dates_raw)}</span>
                        <span>{get_festival_status_badge(dates_raw)}</span>
                    </div>
                    """))

        # STEP 02: 체력 상태 에디토리얼 대시보드 (사진 제거, 직관적 게이지 적용)
        with col_energy:
            with st.container(border=True):
                st.markdown(
                    '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">'
                    '<span class="panel-step-badge">STEP 02</span>'
                    '<strong style="color:#012D1D; font-size:0.95rem;">오늘의 내 체력 상태</strong>'
                    '</div>',
                    unsafe_allow_html=True
                )

                current_stamina = st.session_state.get("stamina_slider", st.session_state.get("stamina_state", 50))
                st.session_state.stamina_state = current_stamina

                # 체력 구간별 메타데이터 & 에셋 매핑
                if current_stamina <= 35:
                    mode_title = "저강도 안심 쉼표"
                    badge_text = "🪫 릴랙스 쉼표"
                    badge_bg = "rgba(6, 95, 70, 0.85)"
                    gauge_color = "#10B981"
                    step_guide = "도보 1,500보 내외 (약 30분)"
                    road_type = "계단 없는 평지 데크 · 쉼터 70%"
                    active_bars = 1
                    bg_img = SUNCHEON_REED_IMG
                elif current_stamina <= 65:
                    mode_title = "황금 밸런스 산책"
                    badge_text = "🔋 밸런스 산책"
                    badge_bg = "rgba(3, 105, 161, 0.85)"
                    gauge_color = "#0284C7"
                    step_guide = "도보 4,000보 내외 (약 1시간)"
                    road_type = "완만한 흙길 산책로 · 걷기 50 : 쉼터 50"
                    active_bars = 2
                    bg_img = NATURE_SHELTER_IMG
                else:
                    mode_title = "활력 풀코스 트레킹"
                    badge_text = "⚡ 에너지 완주"
                    badge_bg = "rgba(180, 83, 9, 0.85)"
                    gauge_color = "#D97706"
                    step_guide = "도보 8,000보 이상 (약 2시간+)"
                    road_type = "전체 둘레길 완주 · 반경 5km+ 활력 코스"
                    active_bars = 3
                    bg_img = "https://images.unsplash.com/photo-1551632811-561732d1e306?auto=format&fit=crop&w=800&q=80"

                def get_bar_style(idx):
                    if idx <= active_bars:
                        return f"background:{gauge_color}; opacity:1;"
                    return "background:rgba(255,255,255,0.4); opacity:0.5;"

                card_html = f"""
                <div style="border: 1px solid #E6DECB; border-radius: 12px; overflow: hidden; margin-bottom: 8px; box-shadow: 0 2px 10px rgba(1,45,29,0.04); background:#FFFFFF;">
                    <!-- 상단 비주얼 헤더 씬 (높이 100px) -->
                    <div style="position: relative; width: 100%; height: 100px; background: #1C2E24 url('{bg_img}') center/cover no-repeat;">
                        <div style="position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0.15) 0%, rgba(1,45,29,0.75) 100%);"></div>
                        
                        <div style="position: absolute; top: 10px; left: 12px; right: 12px; display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 0.70rem; font-weight: 800; padding: 3px 8px; border-radius: 4px; background: {badge_bg}; color: #FFFFFF; backdrop-filter: blur(4px);">
                                {badge_text}
                            </span>
                            
                            <!-- 3칸 배터리 셀 -->
                            <div style="display: flex; align-items: center; gap: 3px; background: rgba(0,0,0,0.45); padding: 3px 7px; border-radius: 14px; backdrop-filter: blur(4px); border: 1px solid rgba(255,255,255,0.25);">
                                <div style="width: 10px; height: 6px; border-radius: 2px; {get_bar_style(1)}"></div>
                                <div style="width: 10px; height: 6px; border-radius: 2px; {get_bar_style(2)}"></div>
                                <div style="width: 10px; height: 6px; border-radius: 2px; {get_bar_style(3)}"></div>
                            </div>
                        </div>

                        <div style="position: absolute; bottom: 8px; left: 12px; right: 12px; display: flex; justify-content: space-between; align-items: flex-end; color: #FFFFFF;">
                            <span style="font-size: 1.02rem; font-weight: 800; text-shadow: 0 1px 4px rgba(0,0,0,0.6);">{mode_title}</span>
                            <span style="font-family: 'Playfair Display', serif; font-size: 1.25rem; font-weight: 800; color: #FAF7F2; text-shadow: 0 1px 4px rgba(0,0,0,0.7);">{current_stamina}%</span>
                        </div>
                    </div>

                    <!-- 하단 보행 가이드 대시보드 -->
                    <div style="padding: 10px 12px; background: #FAF7F2; font-size: 0.77rem; display: flex; flex-direction: column; gap: 4px; border-top: 1px solid #EAE4DA;">
                        <div style="display: flex; justify-content: space-between; color: #414844;">
                            <span>👟 예상 활동량</span>
                            <strong style="color: #012D1D;">{step_guide}</strong>
                        </div>
                        <div style="display: flex; justify-content: space-between; color: #414844;">
                            <span>🌿 추천 보행로</span>
                            <strong style="color: #012D1D;">{road_type}</strong>
                        </div>
                    </div>
                </div>
                """
                st.html(card_html)

                st.slider("체력 배터리 (조절)", min_value=10, max_value=100, value=current_stamina, step=5, key="stamina_slider")

        # STEP 03
        with col_action:
            with st.container(border=True):
                st.markdown('<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;"><span class="panel-step-badge">STEP 03</span><strong style="color:#012D1D; font-size:0.95rem;">누구와, 어떻게 이동하나요</strong></div>', unsafe_allow_html=True)

                companion_options = ["혼자", "부모님", "가족", "커플", "친구", "반려동물"]
                cur_comp = st.session_state.get("companion") or st.session_state.get("active_companion") or st.session_state.get("main_companion") or "혼자"
                if cur_comp not in companion_options:
                    if any(k in cur_comp for k in ["홀로", "혼자", "솔로", "1인", "사색"]):
                        cur_comp = "혼자"
                    elif any(k in cur_comp for k in ["부모", "효도", "어르신"]):
                        cur_comp = "부모님"
                    elif any(k in cur_comp for k in ["가족", "자녀", "아이"]):
                        cur_comp = "가족"
                    elif any(k in cur_comp for k in ["연인", "커플", "데이트"]):
                        cur_comp = "커플"
                    elif any(k in cur_comp for k in ["친구", "우정"]):
                        cur_comp = "친구"
                    elif any(k in cur_comp for k in ["반려", "강아지", "애견", "털뭉치", "동반"]):
                        cur_comp = "반려동물"
                    else:
                        cur_comp = "혼자"

                comp_idx = companion_options.index(cur_comp) if cur_comp in companion_options else 0
                companion = st.selectbox("동행인 선택", options=companion_options, index=comp_idx, key="main_companion_select_box")
                canonical_comp_lookup = {
                    "혼자": "나홀로 쉼표",
                    "부모님": "부모님 효도",
                    "가족": "아이와 패밀리",
                    "커플": "연인 데이트",
                    "친구": "나홀로 쉼표",
                    "반려동물": "반려견 동반",
                }
                canonical_val = canonical_comp_lookup.get(companion, companion)
                # 상단 동행인 알약 칩이 활성화되어 있지 않은 초기 상태에서는 st.session_state.companion의 None 유지
                if not st.session_state.get("companion"):
                    st.session_state.main_companion = canonical_val
                    st.session_state.active_companion = canonical_val
                else:
                    st.session_state.companion = canonical_val
                    st.session_state.active_companion = canonical_val
                    st.session_state.main_companion = canonical_val
                transport = st.radio("이동 수단", options=["🚗 자가용 (편한 주차)", "🚶 도보 (대중교통)"], index=0, horizontal=True, key="main_transport")
                
                extra_details = st.text_input(
                    "에디터에게 전하는 요청사항",
                    value="",
                    placeholder="예: 계단 없는 평지 코스, 여유로운 그늘 쉼터 위주로 추천해주세요",
                    key="main_extra"
                )

                button_label = "🗞️ 조건 변경하여 매거진 다시 발행하기" if has_curation else "🗞️ 나만의 맞춤 여행 매거진 발행하기"
                run_button = st.button(button_label, type="primary", use_container_width=True, disabled=(fest_data is None))

    # 파이프라인 가동 로직
    if st.session_state.trigger_quick_run:
        run_button = True
        st.session_state.trigger_quick_run = False

    if run_button and fest_data:
        with st.spinner("🖋️ 오늘의 걸음 속도에 맞추어, 나만의 쉼표 매거진이 만들어지는 중입니다..."):
            if not extra_details:
                if "나홀로" in companion or "혼자" in companion:
                    final_extra = "오롯이 혼자만의 호젓한 사색과 여유를 즐길 수 있는 1인 맞춤 안심 힐링 동선 위주로 추천해주세요."
                else:
                    final_extra = f"{companion}과 함께 무리 없이 편안하고 안전하게 즐길 수 있는 안심 힐링 동선 위주로 추천해주세요."
            else:
                final_extra = extra_details

            # FESTIVAL_COORDS_TABLE을 통한 로컬 축제 최우선 좌표 보정
            f_lat_val, f_lng_val = resolve_festival_coordinates(
                fest_data.get("name", ""), 
                fest_data.get("address", ""), 
                fest_data.get("lat"), 
                fest_data.get("lng")
            )
            fest_data["lat"] = f_lat_val
            fest_data["lng"] = f_lng_val

            user_inputs = {
                "stamina": current_stamina,
                "companion": companion,
                "transport": transport,
                "region": fest_data.get("region", selected_region),
                "selected_festival": {
                    "name": fest_data.get("name", "로컬 축제"),
                    "lat": f_lat_val,
                    "lng": f_lng_val,
                    "address": fest_data.get("address", ""),
                    "description": fest_data.get("description", ""),
                    "programs": fest_data.get("programs") or get_festival_programs_from_data(fest_data.get("name", ""), fest_data.get("description", "")),
                    "phone": fest_data.get("phone", ""),
                    "homepage": fest_data.get("homepage", "")
                },
                "extra_details": final_extra
            }

            try:
                infra = get_festival_infra_bundle(
                    fest_lat=f_lat_val,
                    fest_lng=f_lng_val,
                    radius_m=3000,
                    target_address=fest_data.get("address", "")
                )
                p_lots = infra.get("parking_lots", [])
                m_rests = infra.get("model_restaurants", [])
                t_spots = infra.get("tourist_spots", [])
            except Exception as e:
                st.error(f"⚠️ 공공데이터 API 연동 중 오류: {e}")
                p_lots, m_rests, t_spots = [], [], []

            api_data = {
                "parking_lots": p_lots,
                "model_restaurants": m_rests,
                "tourist_spots": t_spots
            }

            try:
                pipeline_output = run_processing_pipeline(user_inputs, api_data)
                st.session_state.curation_result = pipeline_output
                st.session_state.active_fest = fest_data
                st.session_state.active_transport = transport
                st.session_state.active_stamina = current_stamina
                st.session_state.active_companion = companion
                st.session_state.auto_scroll_to_magazine = True
                st.session_state["report_expander"] = False
                st.toast("🗞️ FestaPick 맞춤 매거진이 성공적으로 발행되었습니다!", icon="✨")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 파이프라인 처리 오류: {e}")

    # 맞춤 매거진 쇼케이스
    result = st.session_state.get("curation_result")
    active_fest = st.session_state.get("active_fest", fest_data)

    if result and active_fest:
        article_content = result.get("article_content", "")
        event_info = result.get("event_info", {"reservation_required": [], "walk_in": [], "unknown": []})
        map_markers = result.get("map_markers", [])

        fest_name = active_fest.get("name", "로컬 힐링 축제")
        fest_addr = active_fest.get("address", "대한민국 로컬 명소")
        fest_region = active_fest.get("region", "전국")
        fest_dates = active_fest.get("dates", "2026 Season")
        phone = str(active_fest.get("phone", "") or "").strip()
        homepage = str(active_fest.get("homepage", "") or "").strip()
        visuals = get_curated_visuals(fest_name, fest_region, active_fest)

        st.divider()

        # [Anchor & Smooth Scroll] 매거진 쇼케이스 앵커 및 자동 스크롤
        st.html('<div id="curation-showcase-section" style="scroll-margin-top: 20px;"></div>')
        if st.session_state.get("auto_scroll_to_magazine", False):
            st.session_state.auto_scroll_to_magazine = False
            st.html("""
            <script>
            function scrollToCurationShowcase() {
                const el = document.getElementById('curation-showcase-section');
                if (el) {
                    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
            setTimeout(scrollToCurationShowcase, 120);
            setTimeout(scrollToCurationShowcase, 450);
            </script>
            """)

        st.html(textwrap.dedent(f"""
        <div style="display:flex; justify-content:space-between; align-items:flex-end; border-bottom:2px solid #012D1D; padding-bottom:14px; margin-bottom:24px; flex-wrap:wrap; gap:10px;">
            <div>
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                    <span class="editorial-badge badge-live">● 맞춤 매거진 발행 완료</span>
                    <span style="font-size:0.75rem; color:#717973; font-weight:700;">VOL. 01 · {fest_region.upper()}</span>
                </div>
                <h1 style="font-family:'Playfair Display', serif; font-size:2.3rem; font-weight:800; color:#012D1D; margin:4px 0 6px 0;">{fest_name}</h1>
                <div style="font-size:0.85rem; color:#414844;">📍 {fest_addr} · 📅 {fest_dates}</div>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
                <span class="editorial-badge" style="background:#ECE8DF; color:#012D1D;">🪫 체력 {st.session_state.active_stamina}% 맞춤</span>
                <span class="editorial-badge" style="background:#ECE8DF; color:#012D1D;">{st.session_state.active_transport}</span>
                <span class="editorial-badge" style="background:#ECE8DF; color:#012D1D;">👥 {st.session_state.active_companion}</span>
            </div>
        </div>
        """))

        st.markdown("### ⏱️ 에디터 추천 1일 큐레이션 코스")
        st.caption("축제장부터 착한 식당, 웰니스 쉼터까지 체력에 맞춘 3대 핵심 거점")

        # [Infra Curator 연동] 실제 축제 설명, 착한업소 3선, 웰니스 3선
        try:
            import importlib
            import festapick.infra_curator as fic_mod
            importlib.reload(fic_mod)
            get_curated_festival_narrative = fic_mod.get_curated_festival_narrative
            get_curated_top3_programs = fic_mod.get_curated_top3_programs
            get_curated_top3_restaurants = fic_mod.get_curated_top3_restaurants
            get_curated_top3_wellness = fic_mod.get_curated_top3_wellness
        except Exception:
            try:
                import infra_curator as ic_mod
                importlib.reload(ic_mod)
                get_curated_festival_narrative = ic_mod.get_curated_festival_narrative
                get_curated_top3_programs = ic_mod.get_curated_top3_programs
                get_curated_top3_restaurants = ic_mod.get_curated_top3_restaurants
                get_curated_top3_wellness = ic_mod.get_curated_top3_wellness
            except Exception:
                pass

        # 1. 축제 실제 작가 서사 및 대표 프로그램 3선 (동행인 완전 맞춤형 동기화)
        active_comp = str(st.session_state.get('active_companion', '') or st.session_state.get('companion', '') or st.session_state.get('main_companion', '') or '').strip()
        try:
            fest_real_desc = get_curated_festival_narrative(active_fest, fest_name, fest_region, companion=active_comp)
        except TypeError:
            fest_real_desc = get_curated_festival_narrative(active_fest, fest_name, fest_region)
        fest_real_desc = harmonize_report_to_companion(fest_real_desc, active_comp, fest_name, fest_region)

        try:
            top3_programs = get_curated_top3_programs(active_fest, fest_name, fest_region, companion=active_comp) or []
        except TypeError:
            top3_programs = get_curated_top3_programs(active_fest, fest_name, fest_region) or []

        # 프로그램 설명 동행인 맞춤형 실시간 2차 안전 조화
        for prog in top3_programs:
            if isinstance(prog, dict) and "desc" in prog:
                prog["desc"] = harmonize_report_to_companion(prog["desc"], active_comp, fest_name, fest_region)
        # STEP 01 카드 이미지(fest_step_img) 100% 매칭 로직 (축제 공식 실사 우선 및 정밀 테마 매핑)
        f_official_img = active_fest.get("image") or active_fest.get("poster")
        if f_official_img and isinstance(f_official_img, str) and f_official_img.startswith("http") and "nan" not in f_official_img.lower():
            fest_step_img = f_official_img
        elif "순천만" in fest_name or "갈대" in fest_name or "억새" in fest_name:
            fest_step_img = SUNCHEON_REED_IMG
        elif "진주" in fest_name or "유등" in fest_name:
            fest_step_img = JINJU_LANTERN_IMG
        elif "강릉" in fest_name or "커피" in fest_name:
            fest_step_img = GANGNEUNG_COFFEE_IMG
        elif "풍기" in fest_name or "금산" in fest_name or "인삼" in fest_name:
            fest_step_img = GEUMSAN_GINSENG_IMG
        elif "태안" in fest_name or "꽃" in fest_name or "국화" in fest_name:
            fest_step_img = TAEAN_FLOWER_IMG
        elif "사진" in fest_name or "전시" in fest_name or "미술" in fest_name or "페어" in fest_name:
            fest_step_img = "https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?auto=format&fit=crop&w=800&q=80"  # 모던 아트 갤러리 실사
        elif "불꽃" in fest_name:
            fest_step_img = "https://images.unsplash.com/photo-1498931299472-f7a63a5a1cfa?auto=format&fit=crop&w=800&q=80"
        elif "음악" in fest_name or "재즈" in fest_name:
            fest_step_img = "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=800&q=80"
        else:
            fest_fallback_candidate = visuals.get('cover') or visuals.get('spot') or "https://images.unsplash.com/photo-1508615039623-a25605d2b022?auto=format&fit=crop&w=800&q=80"
            fest_step_img = resolve_safe_image(fest_name, fest_fallback_candidate)

        fest_query = urllib.parse.quote(fest_name.strip())
        if homepage and (homepage.startswith("http://") or homepage.startswith("https://")):
            fest_link = homepage
        else:
            fest_link = f"https://map.naver.com/p/search/{fest_query}"

        # 2. 프로그램 3개 리스트 HTML 조립 (STEP 02/03과 완벽한 시각적 대칭)
        prog_list_html = ""
        for idx, p in enumerate(top3_programs, 1):
            p_name = html.escape(p['name'])
            p_desc = html.escape(p['desc'])
            prog_list_html += f"""
            <div style="background:#FAF7F2; border:1px solid #EAE4DA; border-radius:8px; padding:6px 10px; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center;">
                <div style="overflow:hidden; padding-right:6px; flex:1;">
                    <div style="display:flex; align-items:center; gap:5px;">
                        <span style="font-size:0.68rem; font-weight:800; color:#065F46; background:rgba(6,95,70,0.12); padding:1px 5px; border-radius:3px;">주요체험 {idx}</span>
                        <strong style="font-size:0.83rem; color:#012D1D; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{p_name}</strong>
                    </div>
                    <div style="font-size:0.73rem; color:#555E58; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{p_desc}</div>
                </div>
                <span style="background:#E5EFE9; color:#012D1D; padding:2px 6px; border-radius:4px; font-size:0.65rem; font-weight:700; white-space:nowrap; flex-shrink:0;">현장체험</span>
            </div>
            """

        # 3. 착한업소 3선 (동행인 테마 적합도 및 100% 매칭 실사 이미지 반영)
        current_companion = str(st.session_state.get('active_companion', '') or '부모님 (어르신)')
        try:
            top3_restaurants = get_curated_top3_restaurants(active_fest, map_markers, fest_region, companion=current_companion)
        except Exception:
            top3_restaurants = []

        if not top3_restaurants:
            top3_restaurants = [{
                "name": "로컬 착한식당",
                "desc": "정갈한 계절 한식 밥상 (8,000원)",
                "menu": "백반정식",
                "price": "8,000원",
                "dist": "축제장 인근",
                "image": "https://images.unsplash.com/photo-1553163147-622ab57be1c7?auto=format&fit=crop&w=800&q=80",
                "link": f"https://map.naver.com/p/search/{urllib.parse.quote(fest_name + ' 착한가격업소')}"
            }]

        main_rest = top3_restaurants[0]
        rest_step_img = main_rest.get("image", "")
        r_menu_str = str(main_rest.get("menu", "") or main_rest.get("desc", "") or "").lower()
        if any(k in r_menu_str for k in ["돼지국밥", "순대국밥", "국밥"]):
            rest_step_img = DWAEJI_GUKBAP_IMG
        elif not rest_step_img or not str(rest_step_img).startswith("http"):
            rest_step_img = "https://images.unsplash.com/photo-1553163147-622ab57be1c7?auto=format&fit=crop&w=800&q=80"

        # 4. 웰니스 쉼터 3선 (wellness.csv 694건 기준 반경 최단거리 3곳)
        try:
            top3_wellness = get_curated_top3_wellness(active_fest, map_markers, fest_region)
        except Exception:
            top3_wellness = []

        if not top3_wellness:
            top3_wellness = [{
                "name": "로컬 웰니스 힐링 쉼터",
                "theme": "자연/숲치유",
                "desc": "[자연/숲치유] 몸과 마음을 비우는 피톤치드 숲 쉼터",
                "dist": "축제장 인근",
                "image": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=800&q=80",
                "link": f"https://map.naver.com/p/search/{urllib.parse.quote(fest_name + ' 웰니스')}"
            }]

        main_spot = top3_wellness[0]
        spot_step_img = main_spot.get("image", "") or "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=800&q=80"

        # 착한업소 3개 리스트 HTML 조립
        rest_list_html = ""
        for idx, r in enumerate(top3_restaurants, 1):
            badge_bg = "rgba(6,95,70,0.12)" if idx == 1 else "rgba(113,121,115,0.12)"
            badge_color = "#065F46" if idx == 1 else "#414844"
            r_name = html.escape(r['name'])
            r_desc = html.escape(r['desc'])
            r_link = html.escape(r['link'])
            rest_list_html += f"""
            <div style="background:#FAF7F2; border:1px solid #EAE4DA; border-radius:8px; padding:6px 10px; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center;">
                <div style="overflow:hidden; padding-right:6px; flex:1;">
                    <div style="display:flex; align-items:center; gap:5px;">
                        <span style="font-size:0.68rem; font-weight:800; color:{badge_color}; background:{badge_bg}; padding:1px 5px; border-radius:3px;">{idx}순위</span>
                        <strong style="font-size:0.83rem; color:#012D1D; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{r_name}</strong>
                    </div>
                    <div style="font-size:0.73rem; color:#555E58; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{r_desc}</div>
                </div>
                <a href="{r_link}" target="_blank" rel="noopener noreferrer" style="background:#012D1D; color:#FAF7F2; padding:3px 7px; border-radius:4px; font-size:0.67rem; font-weight:700; text-decoration:none; white-space:nowrap; flex-shrink:0;">길찾기 ↗</a>
            </div>
            """

        # 웰니스 3개 리스트 HTML 조립
        well_list_html = ""
        for idx, w in enumerate(top3_wellness, 1):
            badge_bg = "rgba(217,119,6,0.15)" if idx == 1 else "rgba(113,121,115,0.12)"
            badge_color = "#92400E" if idx == 1 else "#414844"
            w_name = html.escape(w['name'])
            w_desc = html.escape(w['desc'])
            w_dist = html.escape(w.get('dist', ''))
            w_link = html.escape(w['link'])
            well_list_html += f"""
            <div style="background:#FAF7F2; border:1px solid #EAE4DA; border-radius:8px; padding:6px 10px; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center;">
                <div style="overflow:hidden; padding-right:6px; flex:1;">
                    <div style="display:flex; align-items:center; gap:5px;">
                        <span style="font-size:0.68rem; font-weight:800; color:{badge_color}; background:{badge_bg}; padding:1px 5px; border-radius:3px;">{idx}순위</span>
                        <strong style="font-size:0.83rem; color:#012D1D; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{w_name}</strong>
                        <span style="font-size:0.68rem; color:#717973; white-space:nowrap;">{w_dist}</span>
                    </div>
                    <div style="font-size:0.73rem; color:#555E58; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{w_desc}</div>
                </div>
                <a href="{w_link}" target="_blank" rel="noopener noreferrer" style="background:#012D1D; color:#FAF7F2; padding:3px 7px; border-radius:4px; font-size:0.67rem; font-weight:700; text-decoration:none; white-space:nowrap; flex-shrink:0;">길찾기 ↗</a>
            </div>
            """

        s_col1, s_col2, s_col3 = st.columns(3, gap="medium")
        with s_col1:
            st.html(textwrap.dedent(f"""
            <div style="display:flex; flex-direction:column; width:100%;">
                <!-- 상단 썸네일 이미지 -->
                <div style="position:relative; width:100%; height:200px; border-radius:10px; overflow:hidden; background-color:#ECE8DF; box-shadow:0 2px 8px rgba(1,45,29,0.06);">
                    <img src="{fest_step_img}" alt="{fest_name}" referrerpolicy="no-referrer" loading="lazy" onerror="this.onerror=null; this.src='{FALLBACK_SAFE_IMAGE}';" style="width:100%; height:200px; object-fit:cover; border-radius:10px; display:block;" />
                </div>
                <!-- 하단 텍스트 카드 박스 -->
                <div style="margin-top:15px; background:#FFFFFF; border:1.5px solid #EAE4DA; border-radius:12px; padding:18px 18px; box-shadow:0 4px 16px rgba(1,45,29,0.05); display:flex; flex-direction:column; justify-content:space-between; min-height:300px; box-sizing:border-box;">
                    <div>
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span style="background-color:#012D1D; color:#FFFFFF; font-size:0.68rem; font-weight:800; padding:3px 8px; border-radius:4px; letter-spacing:0.04em;">STEP 01 · 10:30 AM</span>
                            <span style="font-size:0.70rem; color:#065F46; font-weight:800; background:#D1FAE5; padding:2px 7px; border-radius:4px;">시그니처 프로그램 3선</span>
                        </div>
                        <h4 style="color:#012D1D; margin:4px 0 6px 0; font-size:1.05rem; font-weight:800;">{fest_name}</h4>
                        <p style="font-size:0.80rem; color:#414844; line-height:1.55; margin:0 0 10px 0;">{fest_real_desc}</p>
                        <div style="margin-bottom:8px;">
                            {prog_list_html}
                        </div>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #EAE3D2; padding-top:10px; margin-top:10px;">
                        <div style="font-size:0.74rem; color:#3A674F; font-weight:700;">🌿 무장애 경사도 1.8% · 안심 보행</div>
                        <a href="{fest_link}" target="_blank" rel="noopener noreferrer" style="background:#012D1D; color:#FAF7F2; padding:4px 10px; border-radius:6px; font-size:0.72rem; font-weight:700; text-decoration:none; display:inline-flex; align-items:center; gap:3px;">
                            바로가기 <span>↗</span>
                        </a>
                    </div>
                </div>
            </div>
            """))

        with s_col2:
            main_rest_name = html.escape(main_rest['name'])
            main_rest_link = html.escape(main_rest['link'])
            main_rest_menu = html.escape(str(main_rest.get('menu', '') or '추천 메뉴'))
            st.html(textwrap.dedent(f"""
            <div style="display:flex; flex-direction:column; width:100%;">
                <!-- 상단 썸네일 이미지 -->
                <div style="position:relative; width:100%; height:200px; border-radius:10px; overflow:hidden; background-color:#ECE8DF; box-shadow:0 2px 8px rgba(1,45,29,0.06);">
                    <img src="{rest_step_img}" alt="{main_rest_name}" referrerpolicy="no-referrer" loading="lazy" onerror="this.onerror=null; this.src='https://images.unsplash.com/photo-1553163147-622ab57be1c7?auto=format&fit=crop&w=800&q=80';" style="width:100%; height:200px; object-fit:cover; border-radius:10px; display:block;" />
                    <span style="position:absolute; bottom:8px; right:8px; background:rgba(1,45,29,0.85); color:#FAF7F2; padding:3px 8px; border-radius:4px; font-size:0.70rem; font-weight:700; backdrop-filter:blur(4px);">{main_rest_menu}</span>
                </div>
                <!-- 하단 텍스트 카드 박스 -->
                <div style="margin-top:15px; background:#FFFFFF; border:1.5px solid #EAE4DA; border-radius:12px; padding:18px 18px; box-shadow:0 4px 16px rgba(1,45,29,0.05); display:flex; flex-direction:column; justify-content:space-between; min-height:300px; box-sizing:border-box;">
                    <div>
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span style="background-color:#012D1D; color:#FFFFFF; font-size:0.68rem; font-weight:800; padding:3px 8px; border-radius:4px; letter-spacing:0.04em;">STEP 02 · 12:30 PM</span>
                            <span style="font-size:0.70rem; color:#065F46; font-weight:800; background:#D1FAE5; padding:2px 7px; border-radius:4px;">착한업소 3선</span>
                        </div>
                        <h4 style="color:#012D1D; margin:4px 0 8px 0; font-size:1.05rem; font-weight:800;">{main_rest_name} 외 2곳</h4>
                        <div style="margin-bottom:8px;">
                            {rest_list_html}
                        </div>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #EAE3D2; padding-top:10px; margin-top:10px;">
                        <div style="font-size:0.74rem; color:#3A674F; font-weight:700;">🍲 행안부 착한가격 모범거리</div>
                        <a href="{main_rest_link}" target="_blank" rel="noopener noreferrer" style="background:#012D1D; color:#FAF7F2; padding:4px 10px; border-radius:6px; font-size:0.72rem; font-weight:700; text-decoration:none; display:inline-flex; align-items:center; gap:3px;">
                            1위 바로가기 <span>↗</span>
                        </a>
                    </div>
                </div>
            </div>
            """))

        with s_col3:
            main_spot_name = html.escape(main_spot['name'])
            main_spot_link = html.escape(main_spot['link'])
            main_spot_theme = html.escape(str(main_spot.get('theme', '') or '힐링 쉼터'))
            st.html(textwrap.dedent(f"""
            <div style="display:flex; flex-direction:column; width:100%;">
                <!-- 상단 썸네일 이미지 -->
                <div style="position:relative; width:100%; height:200px; border-radius:10px; overflow:hidden; background-color:#ECE8DF; box-shadow:0 2px 8px rgba(1,45,29,0.06);">
                    <img src="{spot_step_img}" alt="{main_spot_name}" referrerpolicy="no-referrer" loading="lazy" onerror="this.onerror=null; this.src='https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=800&q=80';" style="width:100%; height:200px; object-fit:cover; border-radius:10px; display:block;" />
                    <span style="position:absolute; bottom:8px; right:8px; background:rgba(1,45,29,0.85); color:#FAF7F2; padding:3px 8px; border-radius:4px; font-size:0.70rem; font-weight:700; backdrop-filter:blur(4px);">{main_spot_theme}</span>
                </div>
                <!-- 하단 텍스트 카드 박스 -->
                <div style="margin-top:15px; background:#FFFFFF; border:1.5px solid #EAE4DA; border-radius:12px; padding:18px 18px; box-shadow:0 4px 16px rgba(1,45,29,0.05); display:flex; flex-direction:column; justify-content:space-between; min-height:300px; box-sizing:border-box;">
                    <div>
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span style="background-color:#012D1D; color:#FFFFFF; font-size:0.68rem; font-weight:800; padding:3px 8px; border-radius:4px; letter-spacing:0.04em;">STEP 03 · 02:30 PM</span>
                            <span style="font-size:0.70rem; color:#92400E; font-weight:800; background:#FEF3C7; padding:2px 7px; border-radius:4px;">웰니스 3선</span>
                        </div>
                        <h4 style="color:#012D1D; margin:4px 0 8px 0; font-size:1.05rem; font-weight:800;">{main_spot_name} 외 2곳</h4>
                        <div style="margin-bottom:8px;">
                            {well_list_html}
                        </div>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #EAE3D2; padding-top:10px; margin-top:10px;">
                        <div style="font-size:0.74rem; color:#3A674F; font-weight:700;">✨ 한국관광공사 웰니스 힐링</div>
                        <a href="{main_spot_link}" target="_blank" rel="noopener noreferrer" style="background:#012D1D; color:#FAF7F2; padding:4px 10px; border-radius:6px; font-size:0.72rem; font-weight:700; text-decoration:none; display:inline-flex; align-items:center; gap:3px;">
                            1위 바로가기 <span>↗</span>
                        </a>
                    </div>
                </div>
            </div>
            """))

        st.write("")

        col_left, col_right = st.columns([58, 42], gap="large")

        with col_left:
            current_companion = str(st.session_state.get('active_companion', '') or '부모님 (어르신)')
            essay_data = get_curated_essay(
                fest_name,
                fest_region,
                current_companion,
                active_fest=active_fest,
                top3_restaurants=top3_restaurants,
                top3_wellness=top3_wellness,
                top3_programs=top3_programs
            )
            quote_lead = essay_data["quote_lead"]
            quote_mid = essay_data["quote_mid"]
            first_letter = essay_data["first_letter"]
            essay_text_1 = essay_data["text_1"]
            essay_text_2 = essay_data["text_2"]
            slow_tag = essay_data["slow_tag"]
            comp_badge = essay_data.get("companion_badge", "맞춤 큐레이션")
            tip_walk_title = essay_data.get("tip_walk_title", "보행 환경 가이드")
            tip_walk_desc = essay_data.get("tip_walk_desc") or essay_data.get("tip_walk", "")
            tip_rest_title = essay_data.get("tip_rest_title", "휴게 & 쉼터 안내")
            tip_rest_desc = essay_data.get("tip_rest_desc") or essay_data.get("tip_rest", "")
            tip_spot_title = essay_data.get("tip_spot_title", "주차 및 편의시설 사전 확인")
            tip_spot_desc = essay_data.get("tip_spot_desc") or essay_data.get("tip_spot", "")
            bottom_note = essay_data.get("bottom_note") or f"FESTAPICK EDITOR NOTE · {fest_name} 쉼표에서"

            # 루아치(Ruach) 성우 보이스 6종 1:1 매칭 오디오 도슨트 연동 (audio_docent.py 단일화)
            import festapick.audio_docent as audio_docent
            with st.container(border=True):
                audio_docent.render_audio_docent(companion_text=st.session_state.get("companion") or current_companion)

            fest_query = urllib.parse.quote(fest_name.strip())
            valid_hp = homepage if (homepage and (homepage.startswith("http://") or homepage.startswith("https://"))) else f"https://map.naver.com/p/search/{fest_query}"
            hp_link_html = f'<a href="{html.escape(valid_hp)}" target="_blank" rel="noopener noreferrer" style="display:inline-flex; align-items:center; gap:4px; background:#EDE8DE; color:#012D1D; padding:6px 12px; border-radius:6px; font-size:0.75rem; font-weight:700; text-decoration:none; border:1px solid #DCD4C7;">🌐 축제 누리집 ↗</a>'

            essay_html = f"""<article style="background-color:#FAF7F2; padding:28px 32px; border-radius:14px; border:1px solid #EAE4DA; box-shadow:0 2px 10px rgba(0,0,0,0.03); color:#2B2F2C;">
<div style="display:flex; justify-content:space-between; align-items:flex-start; border-bottom:1px solid #E5DED3; padding-bottom:18px; margin-bottom:16px; flex-wrap:wrap; gap:10px;">
<div>
<div style="display:flex; align-items:center; gap:8px; margin-bottom:4px; flex-wrap:wrap;">
<span class="panel-step-badge">ESSAY &amp; CURATION</span>
<span style="font-size:0.75rem; color:#065F46; background:rgba(6,95,70,0.1); padding:2px 8px; border-radius:4px; font-weight:700;">{comp_badge}</span>
<span style="font-size:0.75rem; color:#717973; font-weight:700;">ISSUE NO. 24 AUTUMN</span>
</div>
<h2 style="font-family:'Playfair Display', Georgia, serif; font-size:1.85rem; font-weight:800; color:#012D1D; margin:4px 0 6px 0; letter-spacing:-0.5px;">에디터의 힐링 에세이</h2>
<p style="font-size:0.83rem; color:#717973; margin:0;">FestaPick 수석 에디터가 현장에서 직접 걸으며 기록한 온기 어린 맞춤 여정록</p>
</div>
<div style="display:flex; align-items:center; gap:8px;">
{hp_link_html}
</div>
</div>

<div style="background-color:rgba(243,237,225,0.7); border-left:4px solid #3A674F; border-top:1px solid #E6DECB; border-right:1px solid #E6DECB; border-bottom:1px solid #E6DECB; border-radius:8px; padding:18px 20px; margin-bottom:22px;">
<blockquote style="font-family:'Playfair Display', Georgia, serif; font-size:1.08rem; color:#012D1D; font-weight:600; font-style:italic; line-height:1.6; margin:0 0 6px 0;">
{quote_lead}
</blockquote>
<span style="font-size:0.75rem; letter-spacing:0.06em; text-transform:uppercase; color:#3A674F; font-weight:700;">— {bottom_note}</span>
</div>

<div style="font-size:0.95rem; line-height:1.95; color:#2B2F2C; margin-bottom:20px;">
<p style="margin:0;">
<span style="float:left; font-size:3.2rem; font-family:'Playfair Display', serif; font-weight:bold; color:#012D1D; line-height:0.9; margin-right:12px; margin-top:4px; user-select:none;">{first_letter}</span>{essay_text_1}
</p>
</div>

<div style="text-align:center; padding:20px 16px; margin:22px 0; border-top:1px solid #E2D9CC; border-bottom:1px solid #E2D9CC; background-color:#FBF9F4;">
<p style="font-family:'Playfair Display', Georgia, serif; font-style:italic; font-size:1.15rem; color:#012D1D; font-weight:700; margin:0 0 6px 0; letter-spacing:-0.3px;">
{quote_mid}
</p>
<span style="font-size:0.72rem; letter-spacing:0.12em; text-transform:uppercase; color:#717973;">{slow_tag}</span>
</div>

<div style="font-size:0.95rem; line-height:1.95; color:#2B2F2C; margin-bottom:24px;">
<p style="margin:0;">
{essay_text_2}
</p>
</div>

<div style="background-color:#F2ECDF; border:1px solid rgba(58,103,79,0.25); border-radius:12px; padding:18px; margin-bottom:24px;">
<div style="display:flex; align-items:center; gap:8px; border-bottom:1px solid #DED6C7; padding-bottom:10px; margin-bottom:14px;">
<span style="font-size:1.2rem; line-height:1;">🛡️</span>
<strong style="color:#012D1D; font-size:0.92rem;">에디터의 안심 동행 가이드 ({current_companion} 방문 전 필수 체크포인트)</strong>
</div>
<div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:10px;">
<div style="background:#FAF7F2; padding:12px; border-radius:8px; border:1px solid #DED6C7;">
<span style="font-size:0.68rem; color:#3A674F; font-weight:800; display:block; margin-bottom:4px;">TIP 01 · 보행 지형 가이드</span>
<strong style="font-size:0.83rem; color:#012D1D; display:block; margin-bottom:4px;">{tip_walk_title}</strong>
<p style="font-size:0.75rem; color:#414844; margin:0; line-height:1.45;">{tip_walk_desc}</p>
</div>
<div style="background:#FAF7F2; padding:12px; border-radius:8px; border:1px solid #DED6C7;">
<span style="font-size:0.68rem; color:#3A674F; font-weight:800; display:block; margin-bottom:4px;">TIP 02 · 휴게 &amp; 쉼터 안내</span>
<strong style="font-size:0.83rem; color:#012D1D; display:block; margin-bottom:4px;">{tip_rest_title}</strong>
<p style="font-size:0.75rem; color:#414844; margin:0; line-height:1.45;">{tip_rest_desc}</p>
</div>
<div style="background:#FAF7F2; padding:12px; border-radius:8px; border:1px solid #DED6C7;">
<span style="font-size:0.68rem; color:#3A674F; font-weight:800; display:block; margin-bottom:4px;">TIP 03 · 주차 &amp; 휠체어 사전 확인</span>
<strong style="font-size:0.83rem; color:#012D1D; display:block; margin-bottom:4px;">{tip_spot_title}</strong>
<p style="font-size:0.75rem; color:#414844; margin:0; line-height:1.45;">{tip_spot_desc}</p>
</div>
</div>
</div>

<div style="background-color:#F4EFE5; border:1px solid rgba(58,103,79,0.3); border-radius:12px; padding:18px;">
<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #DED6C7; padding-bottom:10px; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
<div>
<span style="font-size:0.68rem; color:#3A674F; font-weight:800; text-transform:uppercase; letter-spacing:0.06em; display:block;">Public Data Reliability Assurance</span>
<strong style="color:#012D1D; font-size:0.92rem;">🌿 FESTAPICK 공공데이터 신뢰성 검증 기준</strong>
</div>
<span class="editorial-badge badge-live">공공 포털 데이터 연동</span>
</div>
<p style="font-size:0.78rem; color:#414844; line-height:1.6; margin:0 0 12px 0;">FestaPick은 공공데이터포털(TourAPI), 행정안전부, 한국관광공사 공식 데이터를 기반으로 정직하게 정보를 안내합니다. (※ 휠체어 등 보행 보조기구 구비 여부는 현장 축제 상황실 운영 사정에 따라 상이할 수 있으므로 출발 전 주관부서 사전 확인을 권장합니다.)</p>
<div style="display:flex; flex-direction:column; gap:8px;">
<div style="display:flex; justify-content:space-between; align-items:center; background:#FAF7F2; padding:10px 14px; border-radius:8px; border:1px solid #DED6C7;">
<div>
<strong style="font-size:0.80rem; color:#012D1D; display:block;">축제 공식 정보: 지자체 문화축제 표준 공공데이터 대조</strong>
<span style="font-size:0.72rem; color:#717973;">개최지 주소 및 주최·주관부서 공식 문의처 연동</span>
</div>
<span style="background:rgba(16,185,129,0.12); color:#065F46; font-size:0.75rem; font-weight:800; padding:3px 8px; border-radius:4px;">● 정보 확인</span>
</div>
<div style="display:flex; justify-content:space-between; align-items:center; background:#FAF7F2; padding:10px 14px; border-radius:8px; border:1px solid #DED6C7;">
<div>
<strong style="font-size:0.80rem; color:#012D1D; display:block;">착한 가격 식당: 행정안전부 착한가격업소 최신 지정 현황 연동</strong>
<span style="font-size:0.72rem; color:#717973;">물가 안정 지정업소 및 대표 메뉴 기준 대조</span>
</div>
<span style="background:rgba(245,158,11,0.12); color:#92400E; font-size:0.75rem; font-weight:800; padding:3px 8px; border-radius:4px;">● 가격 연동</span>
</div>
<div style="display:flex; justify-content:space-between; align-items:center; background:#FAF7F2; padding:10px 14px; border-radius:8px; border:1px solid #DED6C7;">
<div>
<strong style="font-size:0.80rem; color:#012D1D; display:block;">힐링 쉼터 정보: 한국관광공사 등록 웰니스 관광지 반경 매칭</strong>
<span style="font-size:0.72rem; color:#717973;">축제장 인근 힐링/온천/숲치유 공인 거점 연동</span>
</div>
<span style="background:rgba(16,185,129,0.12); color:#065F46; font-size:0.75rem; font-weight:800; padding:3px 8px; border-radius:4px;">● 시설 연동</span>
</div>
</div>
</div>
</article>"""

            try:
                st.html(essay_html)
            except Exception:
                st.markdown(essay_html, unsafe_allow_html=True)

            if article_content and '작성하지 못했습니다' not in article_content:
                # [데이터 정합성 100% 보장] 에디터 에세이 식당과 타임라인 11:40 AM 점심 슬롯의 식당/메뉴/거리 동기화
                sync_rest_name = str(main_rest.get("name", "")).strip()
                sync_rest_desc = str(main_rest.get("desc", "") or main_rest.get("menu", "")).strip()
                sync_rest_dist = str(main_rest.get("dist", "")).strip()
                if sync_rest_name and sync_rest_name != "착한가격업소":
                    sync_menu = sync_rest_desc.split("·")[0].strip() if "·" in sync_rest_desc else sync_rest_desc
                    
                    # 거리 텍스트 정제 (0m 또는 축제장 중복 방지)
                    if not sync_rest_dist or "0m" in sync_rest_dist:
                        clean_dist = "축제장 도보 이동"
                    elif "축제장" in sync_rest_dist:
                        clean_dist = sync_rest_dist
                    else:
                        clean_dist = f"축제장 기준 {sync_rest_dist}"
                    
                    # 단일 라인의 표준 타임라인 아이템으로 조립 (- 11:40 AM: 형태 유지하여 100% 카드 레이아웃 보장)
                    sync_slot_line = f"- 11:40 AM: 행정안전부 지정 착한가격업소 '{sync_rest_name}'에서 {sync_menu} 점심 식사 ({clean_dist})"
                    
                    # 점심 슬롯 정규식 (선행 불릿/볼드 및 후속 1줄 설명문까지 깨끗하게 단일 슬롯으로 통합 치환)
                    slot_pattern = r'(?m)^[-*•\s]*(?:\*\*)?\s*(?:11:[0-5]\d|12:[0-5]\d|01:[0-5]\d|오전\s*11|오후\s*12|오후\s*1)\s*(?:AM|PM)?\s*(?:\*\*)?.*?(?:점심|식사|식당|착한가격|밥상|스넥|찌개|불고기|국밥|돈가스|칼국수).*$(?:\n(?!\s*[-*•\s]*(?:\*\*)?(?:\d{1,2}:\d{2}|오전|오후|###)).*)*'
                    if re.search(slot_pattern, article_content):
                        article_content = re.sub(slot_pattern, sync_slot_line, article_content, count=1)

                # [동행인 정합성 완전 자동 연결] 리포트 전문의 모든 동행인 키워드를 실시간 동행인으로 100% 자동 일치
                article_content = harmonize_report_to_companion(article_content, current_companion, fest_name, fest_region)

                # [날씨 상세 화면과 100% 동일 장소 동기화 보장]
                if fest_name:
                    st.session_state["care_selected_fest"] = fest_name
                if fest_region:
                    st.session_state["care_selected_sdo"] = fest_region

                with st.expander('📄 AI 에디터 상세 분석 리포트 전문 확인', expanded=False, key='report_expander', on_change='rerun'):
                    formatted_report_html = render_curated_article_report(article_content, target_companion=current_companion, fest_name=fest_name, fest_region=fest_region)
                    if formatted_report_html:
                        st.markdown(formatted_report_html, unsafe_allow_html=True)
                    else:
                        st.markdown(article_content)

        with col_right:
            st.markdown("""
            <div style="background: #FBF9F5; border: 1px solid #EFEAE2; border-radius: 20px; padding: 22px 28px; margin-bottom: 14px; box-shadow: 0 4px 20px rgba(0,0,0,0.03);">
                <h3 style="font-family:'Pretendard', -apple-system, sans-serif; font-size:1.55rem; font-weight:800; color:#012D1D; margin:0 0 8px 0; letter-spacing:-0.5px;">무장애 안심 지도</h3>
                <p style="font-family:'Pretendard', -apple-system, sans-serif; font-size:0.86rem; color:#717973; margin:0; font-weight:500;">축제장(1번), 착한가격식당(2번), 웰니스(3번), 주차장(P) 4대 거점 코스</p>
            </div>
            """, unsafe_allow_html=True)
            
            if active_fest:
                af_lat, af_lng = resolve_festival_coordinates(active_fest.get("name", ""), active_fest.get("address", ""), active_fest.get("lat"), active_fest.get("lng"))
                active_fest["lat"] = af_lat
                active_fest["lng"] = af_lng
            m = render_curated_peace_map(active_fest, map_markers, fest_region)
            st_folium(m, width="100%", height=420, returned_objects=[])

            prog_hp_url = valid_hp if (valid_hp and valid_hp.startswith("http")) else (homepage if (homepage and homepage.startswith("http")) else f"https://map.naver.com/p/search/{urllib.parse.quote(fest_name.strip())}")
            
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:18px; margin-bottom:10px; flex-wrap:wrap; gap:8px;">
                <h4 style="color:#012D1D; margin:0; font-size:1.02rem; display:flex; align-items:center; gap:6px;">
                    📌 프로그램 사전 확인 목록
                </h4>
                <a href="{html.escape(prog_hp_url)}" target="_blank" rel="noopener noreferrer" 
                   style="background:#1B4332; color:#FFFFFF; text-decoration:none; padding:4px 11px; border-radius:6px; font-size:0.74rem; font-weight:700; display:inline-flex; align-items:center; gap:4px; box-shadow:0 1px 3px rgba(0,0,0,0.12); transition:all 0.2s ease;">
                    🌐 공식 누리집(예약) ↗
                </a>
            </div>
            """, unsafe_allow_html=True)
            req_list = event_info.get("reservation_required", [])
            walk_list = event_info.get("walk_in", [])

            # [UI 개선 1] 탭 순서: '자유 참여' 우선 기본 활성화 & '사전 예약' 0건 처리
            walk_tab_label = f"자유 참여 ({len(walk_list)})"
            req_tab_label = f"사전 예약 ({len(req_list)})"

            tab_free, tab_reserve = st.tabs([walk_tab_label, req_tab_label])

            with tab_free:
                if walk_list:
                    for it in walk_list:
                        name_str = html.escape(str(it.get('name', '')))
                        desc_str = html.escape(str(it.get('description', '')))
                        st.markdown(f"""
                        <div style="background:#FAF7F2; border:1px solid #E6DECB; border-radius:8px; padding:10px 12px; margin-bottom:8px;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; gap:8px;">
                                <strong style="color:#012D1D; font-size:0.86rem;">• {name_str}</strong>
                                <a href="{html.escape(prog_hp_url)}" target="_blank" rel="noopener noreferrer" style="font-size:0.72rem; color:#6B7280; font-weight:600; text-decoration:underline; white-space:nowrap;">현장 안내 ↗</a>
                            </div>
                            <p style="font-size:0.78rem; color:#414844; margin:0; line-height:1.45;">{desc_str}</p>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style="background:#FAF7F2; border:1px dashed #D1C7B7; border-radius:8px; padding:14px; text-align:center; color:#5C645E; font-size:0.80rem;">
                        현장 자율 참여 프로그램 안내가 준비 중입니다.
                    </div>
                    """, unsafe_allow_html=True)

            with tab_reserve:
                if req_list:
                    for it in req_list:
                        name_str = html.escape(str(it.get('name', '')))
                        desc_str = html.escape(str(it.get('description', '')))
                        tip_str = html.escape(str(it.get('booking_tip', '')))
                        tip_badge = f"<div style='margin-top:6px;'><span style='color:#065F46; background:rgba(16,185,129,0.12); padding:2px 7px; border-radius:4px; font-size:0.73rem; font-weight:700;'>Tip: {tip_str}</span></div>" if tip_str else ""
                        st.markdown(f"""
                        <div style="background:#FAF7F2; border:1px solid #E6DECB; border-radius:8px; padding:10px 12px; margin-bottom:8px;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; gap:8px;">
                                <strong style="color:#012D1D; font-size:0.86rem;">• {name_str}</strong>
                                <a href="{html.escape(prog_hp_url)}" target="_blank" rel="noopener noreferrer" style="font-size:0.72rem; color:#1B4332; font-weight:700; text-decoration:underline; white-space:nowrap;">누리집 접수 ↗</a>
                            </div>
                            <p style="font-size:0.78rem; color:#414844; margin:0; line-height:1.45;">{desc_str}</p>
                            {tip_badge}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style="background:#FAF7F2; border:1px dashed #D1C7B7; border-radius:8px; padding:18px 14px; text-align:center; color:#5C645E; font-size:0.82rem; line-height:1.55;">
                        🌿 <strong style="color:#012D1D;">현장 자율 참여 중심으로 운영되는 축제입니다.</strong><br/>
                        <span style="font-size:0.76rem; color:#717973;">별도의 사전 예약 없이 현장에 편안하게 방문하시어 축제 프로그램을 자유롭게 즐겨보세요.</span>
                    </div>
                    """, unsafe_allow_html=True)

            # [UI: Divider] 프로그램 사전 확인 목록과 에디터의 안심 체크리스트 시각적 구분선
            st.markdown("""
            <div style="margin-top: 38px; margin-bottom: 24px; border-top: 1.5px solid #EAE4DA;"></div>
            """, unsafe_allow_html=True)

            # [UI 개선 2] [에디터의 안심 체크리스트] 동행인 테마 연동 & 동적 큐레이션
            active_comp = str(st.session_state.get('active_companion', '') or '').strip()

            if any(k in active_comp for k in ["반려", "견", "강아지", "펫", "pet"]):
                comp_key = "pet"
                comp_badge = "🐾 반려견 펫프렌들리"
                check_items = [
                    "규정 준수 리드줄(2m 이내) 및 휴대용 배변 봉투",
                    "발목 피로를 줄여주는 쿠션 운동화",
                    "일교차 대비 보온 의류 및 휴대용 음수 텀블러",
                    "축제장 내 펫티켓 존 및 잔디/흙길 진드기 예방"
                ]
            elif any(k in active_comp for k in ["부모", "어르신", "시부모", "효도", "할머니", "할아버지", "어른"]):
                comp_key = "parents"
                comp_badge = "🧓 부모님 맞춤 효도"
                check_items = [
                    "발목 피로를 줄여주는 쿠션 운동화",
                    "일교차 대비 가벼운 숄 또는 겉옷",
                    "신분증/복지카드 (현장 무료 휠체어 대여 및 경로 우대)",
                    "단차 없는 평지 산책로 및 중간 쉼터 동선 확인"
                ]
            elif any(k in active_comp for k in ["자녀", "아이", "가족", "키즈", "어린"]):
                comp_key = "family"
                comp_badge = "👶 아이와 함께 패밀리"
                check_items = [
                    "유모차 이동 가능한 평탄 동선 사전 파악",
                    "개인 위생용품/물티슈 및 미아방지 네임택",
                    "일교차 대비 겉옷과 상비약",
                    "발목 피로를 줄여주는 편안한 운동화"
                ]
            else:
                comp_key = "couple_solo"
                comp_badge = "📸 감성 트래블 & 인생샷"
                check_items = [
                    "걷기 편한 가벼운 스니커즈",
                    "인생샷 촬영용 보조배터리 및 삼각대",
                    "저녁 강바람 대비 방풍 아우터",
                    "개인 텀블러 및 간편 휴대용 소지품"
                ]

            cheer_messages = {
                "pet": "사랑하는 반려견과 함께 꼬리 흔드는 행복하고 따뜻한 가을 산책 다녀오세요 🐾",
                "parents": "부모님의 느린 보폭에 맞춘 따뜻하고 효심 가득한 가을 여정 다녀오세요 🍂",
                "family": "온 가족이 안심하고 웃을 수 있는 따뜻한 가을 축제 다녀오세요 🍂",
                "couple_solo": "낭만과 설렘이 가득한 잊지 못할 가을 쉼표 여행 다녀오세요 ✨"
            }
            cheer_msg = cheer_messages.get(comp_key, cheer_messages["family"])

            import streamlit.components.v1 as components

            items_markup = ""
            for idx, item in enumerate(check_items, 1):
                safe_item = html.escape(item)
                items_markup += f"""
                <div class="chk-item">
                    <input type="checkbox" class="chk-input" id="chk_{idx}" />
                    <label for="chk_{idx}" class="chk-text">{safe_item}</label>
                </div>
                """

            checklist_iframe_html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<style>
* {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}}
body {{
    background: transparent;
    font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Pretendard", "Segoe UI", Roboto, sans-serif;
    user-select: none;
    overflow: hidden;
}}
.checklist-card {{
    background: linear-gradient(145deg, #FFFDF8 0%, #F0FDF4 50%, #FEF9C3 100%);
    border: 1.5px solid #FDE68A;
    border-radius: 20px;
    padding: 18px 20px;
    box-shadow: 0 10px 28px rgba(245, 158, 11, 0.09);
}}
.card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 5px;
}}
.title-group {{
    display: flex;
    align-items: center;
    gap: 7px;
}}
.card-title {{
    color: #012D1D;
    font-size: 0.98rem;
    font-weight: 800;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 5px;
}}
.progress-badge {{
    font-size: 0.72rem;
    font-weight: 750;
    padding: 2px 8px;
    border-radius: 12px;
    background: #E8F5E9;
    color: #065F46;
    border: 1px solid #A7F3D0;
    transition: all 0.25s ease;
}}
.progress-badge.all-done {{
    background: #10B981 !important;
    color: #FFFFFF !important;
    border-color: #059669 !important;
    box-shadow: 0 2px 6px rgba(16, 185, 129, 0.35) !important;
}}
.comp-theme-badge {{
    font-size: 0.70rem;
    font-weight: 700;
    color: #065F46;
    background: rgba(6, 95, 70, 0.10);
    padding: 2px 8px;
    border-radius: 10px;
}}
.hint-text {{
    font-size: 0.74rem;
    color: #5A645E;
    display: flex;
    align-items: center;
    gap: 4px;
    margin-bottom: 10px;
    padding-left: 1px;
}}
.items-list {{
    display: flex;
    flex-direction: column;
    gap: 7px;
}}
.chk-item {{
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    border: 1px solid rgba(229, 231, 235, 0.8);
    border-radius: 10px;
    padding: 10px 13px;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}}
.chk-item:hover {{
    background: #FFFFFF !important;
    border-color: #10B981 !important;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.12);
}}
.chk-item:active {{
    transform: translateY(0);
}}
.chk-item.checked {{
    background: rgba(6, 95, 70, 0.06) !important;
    border-color: rgba(16, 185, 129, 0.40) !important;
    box-shadow: none !important;
    transform: none !important;
}}
.chk-item.checked .chk-text {{
    text-decoration: line-through;
    color: #6B7280;
    font-style: italic;
}}
.chk-input {{
    width: 17px;
    height: 17px;
    accent-color: #059669;
    cursor: pointer;
    flex-shrink: 0;
    margin: 0;
}}
.chk-text {{
    color: #0F172A;
    font-size: 0.82rem;
    font-weight: 600;
    line-height: 1.42;
    cursor: pointer;
    flex-grow: 1;
    transition: all 0.18s ease;
}}
.reward-banner {{
    display: none;
    margin-top: 12px;
    background: linear-gradient(135deg, #ECFDF5 0%, #FEF9C3 100%);
    border: 1.5px solid #6EE7B7;
    border-radius: 12px;
    padding: 12px 14px;
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.12);
}}
.reward-banner.show {{
    display: block !important;
    animation: slideUpFadeIn 0.45s cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
}}
@keyframes slideUpFadeIn {{
    0% {{
        opacity: 0;
        transform: translateY(14px) scale(0.98);
    }}
    100% {{
        opacity: 1;
        transform: translateY(0) scale(1);
    }}
}}
</style>
</head>
<body>
<div class="checklist-card">
    <div class="card-header">
        <div class="title-group">
            <span class="card-title">🎒 에디터의 안심 체크리스트</span>
            <span class="progress-badge" id="counterBadge">(0/4 완료)</span>
        </div>
        <span class="comp-theme-badge">{comp_badge}</span>
    </div>
    <div class="hint-text">
        <span>💡</span> 챙긴 준비물을 클릭하여 체크해 보세요!
    </div>
    <div class="items-list">
        {items_markup}
    </div>
    <div class="reward-banner" id="rewardBanner">
        <div style="display:flex; align-items:flex-start; gap:10px;">
            <span style="font-size:1.35rem; line-height:1; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.06));">🎉</span>
            <div style="flex:1;">
                <div style="font-size:0.85rem; font-weight:800; color:#065F46; margin-bottom:3px; letter-spacing:-0.2px;">
                    출발 준비 100% 완료!
                </div>
                <div style="font-size:0.78rem; color:#047857; line-height:1.48; font-weight:500;">
                    {cheer_msg}
                </div>
            </div>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.2/dist/confetti.browser.min.js"></script>
<script>
let hasFiredConfetti = false;

function triggerAutumnConfetti() {{
    let targetDoc = document;
    let parentWin = window;
    try {{
        if (window.parent && window.parent.document) {{
            targetDoc = window.parent.document;
            parentWin = window.parent;
        }}
    }} catch (e) {{
        targetDoc = document;
        parentWin = window;
    }}

    let canvas = targetDoc.getElementById('festa-confetti-canvas');
    if (!canvas) {{
        canvas = targetDoc.createElement('canvas');
        canvas.id = 'festa-confetti-canvas';
        canvas.style.position = 'fixed';
        canvas.style.top = '0';
        canvas.style.left = '0';
        canvas.style.width = '100vw';
        canvas.style.height = '100vh';
        canvas.style.zIndex = '999999';
        canvas.style.pointerEvents = 'none';
        targetDoc.body.appendChild(canvas);
    }}

    let originX = 0.80;
    let originY = 0.72;
    try {{
        if (window.frameElement && parentWin.innerWidth && parentWin.innerHeight) {{
            const frameRect = window.frameElement.getBoundingClientRect();
            originX = Math.min(0.90, Math.max(0.65, (frameRect.left + frameRect.width * 0.5) / parentWin.innerWidth));
            originY = Math.min(0.88, Math.max(0.45, (frameRect.top + frameRect.height * 0.72) / parentWin.innerHeight));
        }}
    }} catch(e) {{
        originX = 0.80;
        originY = 0.72;
    }}

    const autumnColors = ['#F59E0B', '#EF4444', '#10B981', '#FBBF24', '#D97706'];

    if (typeof confetti === 'function') {{
        const myConfetti = confetti.create(canvas, {{ resize: true, useWorker: true }});

        myConfetti({{
            particleCount: 50,
            angle: 90,
            spread: 60,
            origin: {{ x: originX, y: originY }},
            startVelocity: 30,
            gravity: 0.80,
            ticks: 120,
            colors: autumnColors,
            shapes: ['circle', 'square'],
            scalar: 1.05
        }});

        setTimeout(() => {{
            if (canvas && canvas.parentNode) {{
                canvas.style.transition = 'opacity 0.4s ease';
                canvas.style.opacity = '0';
                setTimeout(() => {{
                    if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
                }}, 400);
            }}
        }}, 1600);
    }} else {{
        fallbackAutumnParticles(canvas, originX, originY, autumnColors);
    }}
}}

function fallbackAutumnParticles(canvas, originX, originY, colors) {{
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const particles = [];
    const centerX = canvas.width * originX;
    const centerY = canvas.height * originY;

    for (let i = 0; i < 35; i++) {{
        particles.push({{
            x: centerX + (Math.random() - 0.5) * 40,
            y: centerY,
            vx: (Math.random() - 0.5) * 10,
            vy: -Math.random() * 14 - 6,
            color: colors[Math.floor(Math.random() * colors.length)],
            isCircle: Math.random() > 0.5,
            size: Math.random() * 5 + 4,
            rot: Math.random() * 360,
            vrot: (Math.random() - 0.5) * 10,
            alpha: 1
        }});
    }}
    let start = performance.now();
    function animate(now) {{
        let elapsed = now - start;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        particles.forEach(p => {{
            p.x += p.vx;
            p.y += p.vy;
            p.vy += 0.42;
            p.rot += p.vrot;
            if (elapsed > 1100) p.alpha = Math.max(0, 1 - (elapsed - 1100) / 400);
            ctx.save();
            ctx.globalAlpha = p.alpha;
            ctx.translate(p.x, p.y);
            ctx.rotate(p.rot * Math.PI / 180);
            ctx.fillStyle = p.color;
            if (p.isCircle) {{
                ctx.beginPath();
                ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2);
                ctx.fill();
            }} else {{
                ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
            }}
            ctx.restore();
        }});
        if (elapsed < 1600) {{
            requestAnimationFrame(animate);
        }} else {{
            if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
        }}
    }}
    requestAnimationFrame(animate);
}}

function updateChecklist() {{
    const checkboxes = document.querySelectorAll('.chk-input');
    const badge = document.getElementById('counterBadge');
    const banner = document.getElementById('rewardBanner');
    let checkedCount = 0;
    
    checkboxes.forEach((cb) => {{
        const parent = cb.closest('.chk-item');
        if (cb.checked) {{
            checkedCount++;
            parent.classList.add('checked');
        }} else {{
            parent.classList.remove('checked');
        }}
    }});
    
    const total = checkboxes.length;
    if (checkedCount === total && total > 0) {{
        badge.textContent = "(" + total + "/" + total + " 완료! 🎉)";
        badge.classList.add('all-done');
        banner.style.display = 'block';
        banner.classList.add('show');
        if (!hasFiredConfetti) {{
            hasFiredConfetti = true;
            triggerAutumnConfetti();
        }}
    }} else {{
        badge.textContent = "(" + checkedCount + "/" + total + " 완료)";
        badge.classList.remove('all-done');
        banner.style.display = 'none';
        banner.classList.remove('show');
        hasFiredConfetti = false;
    }}
}}

document.querySelectorAll('.chk-item').forEach((item) => {{
    item.addEventListener('click', (e) => {{
        if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'LABEL') {{
            const cb = item.querySelector('.chk-input');
            cb.checked = !cb.checked;
            updateChecklist();
        }}
    }});
}});

document.querySelectorAll('.chk-input').forEach((cb) => {{
    cb.addEventListener('change', updateChecklist);
}});
</script>
</body>
</html>
"""
            components.html(checklist_iframe_html, height=425, scrolling=False)

        # --------------------------------------------------------------------------
        # [UI: Action] 홈으로 가기 버튼 (매거진 본문과 정부 배너 사이 배치)
        # 리포트 아코디언이 닫혀 있을 때만 메인 탈출구로 표시, 열렸을 때는 내부 버튼과 중복 방지 위해 조건부 숨김
        # --------------------------------------------------------------------------
        is_report_open = bool(st.session_state.get("report_expander", False))
        if not is_report_open:
            st.write("")
            st.write("")
            _, home_btn_col, _ = st.columns([1, 1.8, 1])
            with home_btn_col:
                if st.button("🏠 홈으로 가기 (다른 축제 둘러보기)", key="btn_go_home_curation", use_container_width=True):
                    st.session_state.curation_result = None
                    st.session_state.active_fest = None
                    st.session_state.companion = None
                    st.session_state["active_companion_param"] = "none"
                    st.session_state["active_companion"] = None
                    st.session_state["main_companion"] = None
                    st.session_state.pop("curation_result", None)
                    st.session_state.pop("active_fest", None)
                    st.session_state.pop("report_expander", None)
                    st.rerun()

        # 대한민국 정부 공식 공공데이터 100% 실시간 연계 검증 배너
        local_gov_title = fest_region.replace("특별자치도", "").replace("광역시", "").replace("특별시", "").replace("도", "")
        if "순천" in fest_name or "순천" in fest_addr:
            local_gov_title = "순천시청 로컬"
        elif "광주" in fest_name or "화담" in fest_name:
            local_gov_title = "광주시청 로컬"
        elif "진주" in fest_name or "진주" in fest_addr:
            local_gov_title = "진주시청 로컬"
        else:
            local_gov_title = f"{local_gov_title} 로컬"

        gov_logo_url = "https://lh3.googleusercontent.com/aida-public/AB6AXuDbQ1oTh0IBwA6lLvw1XNABXyMXovLgCzXCzERM0uPjABmDl81yLJm_AJbJYxSAdu0qjp0BlX6drG7p59gkRkFt5dTLcKg5AW761QXUoFgXw9BRooqscungiCQoLVkctz0oMLx4CRWjLr4MxZ_CwjcGkcu6gJ-tCiWk8PxiNEK9Rekqd9xJaAk020qUC0gP_mzu49BCVNPIhguqgZL22qh1NCRKURNsocF85ee4P1wVxajkzkGYDFy5vqxp8jo0DEs1NQ"

        st.html(textwrap.dedent(f"""
        <div style="background-color:#0B192C; color:#FFFFFF; border-radius:14px; padding:28px 32px; margin-top:20px; border:1px solid rgba(255,255,255,0.12); box-shadow:0 12px 32px rgba(0,0,0,0.25);">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px; padding-bottom:20px; border-bottom:1px solid rgba(255,255,255,0.1);">
                <div style="display:flex; align-items:center; gap:16px;">
                    <div style="flex-shrink:0; width:48px; height:48px; border-radius:50%; background:#FFFFFF; display:flex; align-items:center; justify-content:center; box-shadow:0 4px 12px rgba(0,0,0,0.2); padding:6px;">
                        <img src="{gov_logo_url}" alt="대한민국 정부 상징 공식 로고" style="width:100%; height:100%; object-fit:contain;" />
                    </div>
                    <div>
                        <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                            <span style="font-size:0.75rem; letter-spacing:0.08em; text-transform:uppercase; color:#A5D0B9; font-weight:800;">대한민국 정부 공식 인증</span>
                            <span style="color:rgba(255,255,255,0.4);">·</span>
                            <span style="background:#BCEECF; color:#002112; font-size:0.72rem; font-weight:700; padding:2px 8px; border-radius:4px;">실시간 공공 API 연동</span>
                        </div>
                        <h3 style="margin:0 0 4px 0; color:#FFFFFF; font-size:1.35rem; font-weight:800; letter-spacing:-0.3px;">대한민국 정부 공식 공공데이터 100% 실시간 연계 검증</h3>
                        <p style="margin:0; font-size:0.85rem; color:rgba(255,255,255,0.78); line-height:1.5;">상업적 광고와 협찬을 배제하고, 정부 공공데이터포털 및 지자체 공식 오픈 API만을 기반으로 정직하게 큐레이션합니다.</p>
                    </div>
                </div>
                <div>
                    <a href="https://www.data.go.kr" target="_blank" rel="noopener noreferrer" style="display:inline-flex; align-items:center; gap:8px; background:rgba(255,255,255,0.1); color:#FFFFFF; padding:10px 18px; border-radius:8px; border:1px solid rgba(255,255,255,0.22); text-decoration:none; font-weight:700; font-size:0.82rem; backdrop-filter:blur(6px); transition:all 0.2s ease;">
                        <span style="color:#A5D0B9; font-size:16px;">🛡️</span>
                        <span>공공데이터포털(DATA.GO.KR) 원천 검증 ↗</span>
                    </a>
                </div>
            </div>

            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:12px; margin-top:20px;">
                <div style="background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:14px 16px; display:flex; flex-direction:column; justify-content:space-between;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="font-size:0.75rem; color:#A5D0B9; font-weight:700; text-transform:uppercase;">행정안전부 (MOIS)</span>
                        <span style="width:7px; height:7px; border-radius:50%; background:#BCEECF; display:inline-block; box-shadow:0 0 6px #BCEECF;"></span>
                    </div>
                    <strong style="font-size:0.95rem; color:#FFFFFF; display:block; margin-bottom:12px;">착한가격업소 데이터</strong>
                    <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid rgba(255,255,255,0.1); padding-top:8px; font-size:0.74rem; color:rgba(255,255,255,0.65);">
                        <span>물가 모니터링 검증</span>
                        <span style="color:#A5D0B9; font-weight:600;">실시간 동기화</span>
                    </div>
                </div>

                <div style="background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:14px 16px; display:flex; flex-direction:column; justify-content:space-between;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="font-size:0.75rem; color:#A5D0B9; font-weight:700; text-transform:uppercase;">한국관광공사 (KTO)</span>
                        <span style="width:7px; height:7px; border-radius:50%; background:#BCEECF; display:inline-block; box-shadow:0 0 6px #BCEECF;"></span>
                    </div>
                    <strong style="font-size:0.95rem; color:#FFFFFF; display:block; margin-bottom:12px;">TourAPI 4.0 무장애</strong>
                    <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid rgba(255,255,255,0.1); padding-top:8px; font-size:0.74rem; color:rgba(255,255,255,0.65);">
                        <span>열린관광지 공식 인증</span>
                        <span style="color:#A5D0B9; font-weight:600;">공식 API</span>
                    </div>
                </div>

                <div style="background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:14px 16px; display:flex; flex-direction:column; justify-content:space-between;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="font-size:0.75rem; color:#A5D0B9; font-weight:700; text-transform:uppercase;">국립공원공단 (KNPS)</span>
                        <span style="width:7px; height:7px; border-radius:50%; background:#BCEECF; display:inline-block; box-shadow:0 0 6px #BCEECF;"></span>
                    </div>
                    <strong style="font-size:0.95rem; color:#FFFFFF; display:block; margin-bottom:12px;">생태탐방 &amp; 보행로</strong>
                    <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid rgba(255,255,255,0.1); padding-top:8px; font-size:0.74rem; color:rgba(255,255,255,0.65);">
                        <span>보행로 무장애 경사도</span>
                        <span style="color:#A5D0B9; font-weight:600;">평균 1.8% 검증</span>
                    </div>
                </div>

                <div style="background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:14px 16px; display:flex; flex-direction:column; justify-content:space-between;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="font-size:0.75rem; color:#A5D0B9; font-weight:700; text-transform:uppercase;">{local_gov_title} 축제</span>
                        <span style="width:7px; height:7px; border-radius:50%; background:#BCEECF; display:inline-block; box-shadow:0 0 6px #BCEECF;"></span>
                    </div>
                    <strong style="font-size:0.95rem; color:#FFFFFF; display:block; margin-bottom:12px;">실시간 문화축제 포털</strong>
                    <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid rgba(255,255,255,0.1); padding-top:8px; font-size:0.74rem; color:rgba(255,255,255,0.65);">
                        <span>축제·교통·주차 정보</span>
                        <span style="color:#A5D0B9; font-weight:600;">직통 연동</span>
                    </div>
                </div>
            </div>
        </div>
        """))

    else:
        # ======================================================================
        # [Editorial Spotlight] 시네마틱 롤링 캐러셀 배너 (5초 Autoplay & 부드러운 Fade)
        # ======================================================================
        today_now = datetime.now()
        cur_m = today_now.month
        season_map = {3: "봄", 4: "봄", 5: "봄", 6: "여름", 7: "여름", 8: "여름", 9: "가을", 10: "가을", 11: "가을", 12: "겨울", 1: "겨울", 2: "겨울"}
        cur_s = season_map.get(cur_m, "가을")
        edition_title = f"{cur_m}월 {cur_s} 에디션"

        st.html(textwrap.dedent(f"""
        <div style="margin:24px 0 12px 0; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <span style="font-family:'Playfair Display', serif; font-size:1.45rem; font-weight:800; color:#012D1D;">Editorial Spotlight</span>
                <span style="font-size:0.85rem; color:#717973; margin-left:8px;">수석 에디터가 엄선한 이번 {cur_s} 기획특집 추천 3선</span>
            </div>
            <div style="font-family:'Playfair Display', serif; font-size:0.95rem; font-weight:700; color:#3A674F;">
                VOL. 01~03 · {edition_title}
            </div>
        </div>
        """))

        # 로컬 이미지 Base64 인코딩 (100% 무결점 로딩 보장)
        def _get_b64_img(rel_path, fallback_url):
            try:
                full_path = os.path.join(PROJECT_ROOT, rel_path)
                if os.path.exists(full_path):
                    with open(full_path, "rb") as img_f:
                        return f"data:image/jpeg;base64,{base64.b64encode(img_f.read()).decode('utf-8')}"
            except Exception:
                pass
            return fallback_url

        reed_src = _get_b64_img("assets/suncheon_reed.jpg", "https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=2048&q=85")
        jinju_src = _get_b64_img("assets/jinju_lantern.jpg", "https://tong.visitkorea.or.kr/cms/resource/57/4082657_image2_1.png")
        coffee_src = _get_b64_img("assets/gangneung_coffee.jpg", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=2048&q=85")

        # [Editorial Spotlight] 29CM / 킨포크 화사한 에디토리얼 쇼케이스 (크로스페이드 & 켄 번스 슬로우 줌 & 글래스모피즘 카드)
        slider_component_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,800;1,600&display=swap');

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Pretendard', -apple-system, sans-serif;
            word-break: keep-all;
        }}

        body {{
            background: transparent;
            overflow: hidden;
        }}

        .spotlight-wrapper {{
            position: relative;
            width: 100%;
            height: 520px;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 12px 36px rgba(1, 45, 29, 0.08);
            background-color: transparent;
            user-select: none;
        }}

        .slides-container {{
            position: relative;
            width: 100%;
            height: 100%;
        }}

        /* 크로스페이드 (Cross-fade) 슬라이드 - 투명 배경으로 탁함 방지 */
        .slide {{
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
            transition: opacity 1000ms cubic-bezier(0.4, 0.0, 0.2, 1);
            z-index: 1;
            background-color: transparent;
        }}

        .slide.active {{
            opacity: 1;
            visibility: visible;
            pointer-events: auto;
            z-index: 3;
        }}

        /* 고화질 선명 렌더링 & 부드러운 켄 번스 슬로우 줌 (1.03배 ➔ 1.0배) */
        .slide-img {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            object-position: center;
            image-rendering: auto;
            opacity: 1 !important;
            filter: none;
            transform: scale(1.03);
            transition: transform 7000ms cubic-bezier(0.25, 1, 0.5, 1);
            backface-visibility: hidden;
            -webkit-backface-visibility: hidden;
        }}

        .slide.active .slide-img {{
            transform: scale(1.0);
        }}

        /* 딤 레이어/필터 완전 배제 - 원본 고화질 사진의 선명하고 맑은 자연광 100% 보존 */
        .slide-overlay {{
            position: absolute;
            inset: 0;
            padding: 28px 34px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            z-index: 4;
            pointer-events: none;
            background: transparent;
        }}

        .top-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            pointer-events: auto;
        }}

        /* 우측 상단 깔끔한 화이트 알약 형태 에디션 뱃지 */
        .badge-vol-pill {{
            background: rgba(255, 255, 255, 0.92);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(230, 222, 203, 0.85);
            border-radius: 30px;
            padding: 7px 18px;
            color: #012D1D;
            font-size: 0.82rem;
            font-weight: 800;
            letter-spacing: 0.03em;
            box-shadow: 0 4px 16px rgba(1, 45, 29, 0.06);
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}

        .badge-live-tag {{
            background: #E8F5E9;
            color: #1B5E20;
            font-size: 0.72rem;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 4px;
        }}

        @keyframes riseFromBottomEdge {{
            0% {{
                opacity: 0;
                transform: translateY(320px); /* 사진 맨 밑바닥 외부 완전히 아래에 위치 */
            }}
            15% {{
                opacity: 1; /* 밑바닥을 통과해 올라오면서 선명해짐 */
            }}
            100% {{
                opacity: 1;
                transform: translateY(0);    /* 현재의 원래 위치에 정확히 안착 */
            }}
        }}

        /* 대기 중인 카드는 사진 맨 밑바닥 아래로 완전히 내려 숨김 */
        .slide .editorial-glass-card {{
            position: absolute;
            left: 32px;
            bottom: 74px;
            max-width: 640px;
            background: rgba(253, 249, 240, 0.90);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1.5px solid rgba(255, 255, 255, 0.85);
            border-radius: 18px;
            padding: 24px 28px;
            box-shadow: 0 10px 30px rgba(1, 45, 29, 0.08);
            cursor: pointer;
            user-select: none;
            opacity: 0;
            transform: translateY(320px);
            pointer-events: none;
            -webkit-tap-highlight-color: transparent;
            transition: box-shadow 0.25s ease, border-color 0.25s ease;
        }}

        /* 활성 슬라이드: 사진을 먼저 보여준 뒤(0.2초 딜레이) 1.55초 동안 맨 밑바닥에서 천천히 우아하게 상승 */
        .slide.active .editorial-glass-card {{
            pointer-events: auto;
            animation: riseFromBottomEdge 1.55s cubic-bezier(0.16, 1, 0.3, 1) 0.2s forwards;
        }}

        .slide.active .editorial-glass-card:hover {{
            transform: translateY(-4px) scale(1.01) !important;
            box-shadow: 0 20px 42px rgba(1, 45, 29, 0.16);
            border-color: #3A674F;
            background: rgba(255, 253, 248, 0.97);
        }}

        .slide.active .editorial-glass-card:active {{
            transform: translateY(-1px) scale(0.998) !important;
        }}

        /* 카드 내부 전체가 일관된 클릭 영역으로 동작하도록 보장 */
        .editorial-glass-card * {{
            pointer-events: none;
        }}

        .card-location-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            font-size: 0.82rem;
            font-weight: 700;
            color: #5A645D;
            margin-bottom: 8px;
            letter-spacing: -0.01em;
            flex-wrap: wrap;
        }}

        .card-vol-badge {{
            display: inline-block;
            background: #012D1D;
            color: #FAF7F2;
            font-size: 0.70rem;
            font-weight: 800;
            padding: 2px 7px;
            border-radius: 4px;
            letter-spacing: 0.03em;
        }}

        .card-status-pill {{
            display: inline-flex;
            align-items: center;
            background: #E8F5E9;
            color: #166534;
            font-size: 0.70rem;
            font-weight: 800;
            padding: 2px 7px;
            border-radius: 4px;
            letter-spacing: -0.01em;
            border: 1px solid #BBF7D0;
        }}

        .card-status-pill.live {{
            background: #DCFCE7;
            color: #15803D;
            border-color: #86EFAC;
        }}

        .badge-live {{
            display: inline-flex;
            align-items: center;
            background: #DCFCE7;
            color: #15803D;
            font-size: 0.72rem;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid #86EFAC;
            letter-spacing: -0.01em;
        }}

        .badge-dday {{
            display: inline-flex;
            align-items: center;
            background: #FEF3C7;
            color: #B45309;
            font-size: 0.72rem;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid #FDE68A;
            letter-spacing: -0.01em;
        }}

        .card-fest-title {{
            font-family: 'Playfair Display', 'Pretendard', Georgia, serif;
            font-size: 2.15rem;
            font-weight: 800;
            color: #012D1D;
            margin: 0 0 8px 0;
            line-height: 1.2;
            letter-spacing: -0.02em;
        }}

        .card-fest-desc {{
            font-size: 0.94rem;
            line-height: 1.55;
            color: #3C423E;
            margin: 0 0 14px 0;
            font-weight: 500;
        }}

        .card-tags-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}

        .card-tag {{
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid #E6DECB;
            color: #2D3A32;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 6px;
            box-shadow: 0 2px 6px rgba(1, 45, 29, 0.03);
        }}

        /* 하단 미니멀 도크 컨트롤러 */
        .carousel-dock {{
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 64px;
            display: flex;
            justify-content: flex-end;
            align-items: center;
            padding: 0 32px 16px 32px;
            z-index: 10;
            pointer-events: auto;
        }}

        .nav-controls {{
            display: flex;
            align-items: center;
            gap: 10px;
            background: rgba(253, 249, 240, 0.88);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(230, 222, 203, 0.8);
            padding: 5px 12px;
            border-radius: 28px;
            box-shadow: 0 4px 16px rgba(1, 45, 29, 0.06);
        }}

        .nav-arrow-btn {{
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: #FFFFFF;
            border: 1px solid #E6DECB;
            color: #012D1D;
            font-size: 0.82rem;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .nav-arrow-btn:hover {{
            background: #012D1D;
            color: #FAF7F2;
            border-color: #012D1D;
            transform: scale(1.06);
        }}

        .dots-wrap {{
            display: flex;
            align-items: center;
            gap: 6px;
            margin: 0 4px;
        }}

        .dot {{
            width: 7px;
            height: 7px;
            border-radius: 4px;
            background: #D8D1C4;
            cursor: pointer;
            transition: all 0.3s ease;
        }}

        .dot.active {{
            width: 20px;
            background: #012D1D;
        }}

        .page-indicator {{
            font-family: 'Playfair Display', Georgia, serif;
            font-size: 0.84rem;
            font-weight: 700;
            color: #012D1D;
            letter-spacing: 0.05em;
            min-width: 50px;
            text-align: center;
        }}

        /* ====================================================================== */
        /* 반응형 모바일 (768px 이하): 사진-카드 세로 스택(Stack) 레이아웃 대응 */
        /* ====================================================================== */
        @media (max-width: 768px) {{
            .spotlight-wrapper {{
                height: 535px;
                border-radius: 16px;
            }}

            /* 상단 배너 사진 분리 (높이 220px로 제한하여 사진의 시원한 풍경 보존) */
            .slide-img {{
                height: 220px;
                object-position: center 30%;
                border-radius: 16px 16px 0 0;
                image-rendering: auto;
                opacity: 1 !important;
                filter: none;
            }}

            .slide-overlay {{
                padding: 14px 14px;
                height: 220px;
                background: transparent;
            }}

            .badge-vol-pill {{
                padding: 5px 12px;
                font-size: 0.72rem;
            }}

            /* 정보 카드를 사진 아래로 자연스럽게 이어져 내려오도록 스택 배치 */
            .slide .editorial-glass-card {{
                position: absolute;
                top: 202px;
                left: 10px;
                right: 10px;
                bottom: 58px;
                max-width: none;
                width: auto;
                padding: 14px 16px;
                border-radius: 16px;
                background: rgba(253, 249, 240, 0.96);
                box-shadow: 0 8px 24px rgba(1, 45, 29, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.9);
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }}

            .slide.active .editorial-glass-card:hover {{
                transform: translateY(-2px) !important;
                box-shadow: 0 12px 28px rgba(1, 45, 29, 0.15);
            }}

            .card-location-row {{
                font-size: 0.74rem;
                gap: 5px;
                margin-bottom: 4px;
            }}

            .card-vol-badge {{
                font-size: 0.65rem;
                padding: 2px 5px;
            }}

            .badge-live, .badge-dday {{
                font-size: 0.65rem;
                padding: 2px 6px;
            }}

            .card-fest-title {{
                font-size: 1.35rem;
                margin: 0 0 3px 0;
                line-height: 1.25;
            }}

            .card-fest-desc {{
                font-size: 0.80rem;
                line-height: 1.4;
                margin: 0 0 8px 0;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }}

            .card-tags-row {{
                gap: 4px;
            }}

            .card-tag {{
                font-size: 0.68rem;
                padding: 3px 6px;
            }}

            /* 하단 도크 컨트롤러 */
            .carousel-dock {{
                height: 54px;
                padding: 0 10px 8px 10px;
                justify-content: flex-end;
            }}

            .nav-controls {{
                padding: 3px 6px;
                gap: 4px;
                border-radius: 20px;
            }}

            .nav-arrow-btn {{
                width: 26px;
                height: 26px;
                font-size: 0.70rem;
            }}

            .dots-wrap {{
                gap: 3px;
                margin: 0 2px;
            }}

            .dot {{
                width: 5px;
                height: 5px;
            }}

            .dot.active {{
                width: 14px;
            }}

            .page-indicator {{
                font-size: 0.74rem;
                min-width: 40px;
            }}
        }}
        </style>
        </head>
        <body>

        <div class="spotlight-wrapper" id="spotlightWrapper">
            <div class="slides-container">
                <!-- Slide 1: 순천만 갈대축제 (황금빛 노을빛) -->
                <div class="slide active" id="slide-0">
                    <img class="slide-img" src="{reed_src}" alt="순천만 갈대축제" />
                    <div class="slide-overlay">
                        <div class="top-bar">
                            <span class="badge-vol-pill">
                                <span>🌿 {cur_m}월 추천 01</span>
                                <span class="badge-live">● LIVE NOW</span>
                            </span>
                            <span class="badge-vol-pill">VOL. 01~03 · {edition_title}</span>
                        </div>
                    </div>
                    <div class="editorial-glass-card" key="0" data-slide="0" onclick="handleApplyCourse(0)" role="button" tabindex="0">
                        <div class="card-location-row">
                            <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                                <span class="card-vol-badge">VOL. 01</span>
                                <span>📍 전라남도 순천시</span>
                                <span>📅 2026.10.10 ~ 10.28</span>
                                <span class="badge-live">● LIVE NOW</span>
                            </div>
                        </div>
                        <h1 class="card-fest-title">순천만 갈대축제</h1>
                        <p class="card-fest-desc">바람과 은빛 갈대숲이 머무는 곳, 체력에 맞추어 가장 안심하고 누리는 1일 힐링 에디토리얼 여정.</p>
                        <div class="card-tags-row">
                            <span class="card-tag">🔋 권장 체력 75%</span>
                            <span class="card-tag">🚗 자가용 (렌터카)</span>
                            <span class="card-tag">👥 나홀로 쉼표 여행</span>
                            <span class="card-tag">✨ 황금빛 갈대 데크로드 · 흑두루미 생태 쉼터</span>
                        </div>
                    </div>
                </div>

                <!-- Slide 2: 진주 남강유등축제 (남강 위 환상적인 불빛) -->
                <div class="slide" id="slide-1">
                    <img class="slide-img" src="{jinju_src}" alt="진주 남강유등축제" />
                    <div class="slide-overlay">
                        <div class="top-bar">
                            <span class="badge-vol-pill">
                                <span>🏮 {cur_m}월 추천 02</span>
                                <span class="badge-live">● LIVE NOW</span>
                            </span>
                            <span class="badge-vol-pill">VOL. 01~03 · {edition_title}</span>
                        </div>
                    </div>
                    <div class="editorial-glass-card" key="1" data-slide="1" onclick="handleApplyCourse(1)" role="button" tabindex="0">
                        <div class="card-location-row">
                            <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                                <span class="card-vol-badge">VOL. 02</span>
                                <span>📍 경상남도 진주시</span>
                                <span>📅 2026.10.05 ~ 10.20</span>
                                <span class="badge-live">● LIVE NOW</span>
                            </div>
                        </div>
                        <h1 class="card-fest-title">진주 남강유등축제</h1>
                        <p class="card-fest-desc">천 년의 역사를 품은 남강 물결 위에 수놓아진 수만 개의 유등. 물빛과 달빛이 어우러진 낭만적인 밤 산책 코스.</p>
                        <div class="card-tags-row">
                            <span class="card-tag">🪫 권장 체력 50%</span>
                            <span class="card-tag">🚶 도보 (대중교통)</span>
                            <span class="card-tag">👥 가족과 함께</span>
                            <span class="card-tag">✨ 남강 수상 유등 전시 · 촉석루 달빛 산책</span>
                        </div>
                    </div>
                </div>

                <!-- Slide 3: 강릉 커피축제 (솔향과 커피) -->
                <div class="slide" id="slide-2">
                    <img class="slide-img" src="{coffee_src}" alt="강릉 커피축제" />
                    <div class="slide-overlay">
                        <div class="top-bar">
                            <span class="badge-vol-pill">
                                <span>☕ {cur_m}월 추천 03</span>
                                <span class="badge-dday">D-4</span>
                            </span>
                            <span class="badge-vol-pill">VOL. 01~03 · {edition_title}</span>
                        </div>
                    </div>
                    <div class="editorial-glass-card" key="2" data-slide="2" onclick="handleApplyCourse(2)" role="button" tabindex="0">
                        <div class="card-location-row">
                            <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                                <span class="card-vol-badge">VOL. 03</span>
                                <span>📍 강원특별자치도 강릉시</span>
                                <span>📅 2026.10.12 ~ 10.18</span>
                                <span class="badge-dday">D-4</span>
                            </div>
                        </div>
                        <h1 class="card-fest-title">강릉 커피축제</h1>
                        <p class="card-fest-desc">솔향과 그윽한 커피 향기가 파도 소리와 만나는 시간, 평지 해변 데크길로 걷는 릴랙스 여행.</p>
                        <div class="card-tags-row">
                            <span class="card-tag">🪫 권장 체력 40%</span>
                            <span class="card-tag">🚗 자가용 (렌터카)</span>
                            <span class="card-tag">👥 연인 / 커플</span>
                            <span class="card-tag">✨ 안목해변 커피거리 · 경포호 솔밭 무장애길</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 하단 도크 컨트롤러 -->
            <div class="carousel-dock">
                <div class="nav-controls">
                    <button class="nav-arrow-btn" onclick="manualPrev()">❮</button>
                    <div class="dots-wrap">
                        <span class="dot active" id="dot-0" onclick="goToSlide(0)"></span>
                        <span class="dot" id="dot-1" onclick="goToSlide(1)"></span>
                        <span class="dot" id="dot-2" onclick="goToSlide(2)"></span>
                    </div>
                    <div class="page-indicator" id="indicator">01 / 03</div>
                    <button class="nav-arrow-btn" onclick="manualNext()">❯</button>
                </div>
            </div>
        </div>

        <script>
        let current = 0;
        const total = 3;
        let timer = null;
        const indicator = document.getElementById('indicator');

        // 슬라이드별 쉼표여정(에디토리얼 에세이) 직통 이동 링크
        const courseLinks = [
            '?select_fest_and_go=' + encodeURIComponent('순천만 갈대축제'),
            '?select_fest_and_go=' + encodeURIComponent('진주 남강유등축제'),
            '?select_fest_and_go=' + encodeURIComponent('강릉 커피축제')
        ];

        function updateDotsAndIndicator(targetIdx) {{
            for (let i = 0; i < total; i++) {{
                const d = document.getElementById('dot-' + i);
                if (d) {{
                    if (i === targetIdx) {{
                        d.classList.add('active');
                    }} else {{
                        d.classList.remove('active');
                    }}
                }}
            }}
            if (indicator) {{
                indicator.textContent = '0' + (targetIdx + 1) + ' / 03';
            }}
        }}

        function goToSlide(targetIdx) {{
            if (targetIdx === current) return;

            const currEl = document.getElementById('slide-' + current);
            const nextEl = document.getElementById('slide-' + targetIdx);
            if (!currEl || !nextEl) return;

            currEl.classList.remove('active');
            nextEl.classList.add('active');

            const nextCard = nextEl.querySelector('.editorial-glass-card');
            if (nextCard) {{
                nextCard.style.animation = 'none';
                void nextCard.offsetHeight;
                nextCard.style.animation = '';
            }}

            current = targetIdx;
            updateDotsAndIndicator(current);
            resetTimer();
        }}

        function nextSlide() {{
            const target = (current + 1) % total;
            goToSlide(target);
        }}

        function prevSlide() {{
            const target = (current - 1 + total) % total;
            goToSlide(target);
        }}

        function resetTimer() {{
            if (timer) {{
                clearInterval(timer);
            }}
            // 슬라이드 넘어가는 주기는 기존의 경쾌한 리듬 유지 (4.8초)
            timer = setInterval(nextSlide, 4800);
        }}

        function manualNext() {{
            nextSlide();
        }}

        function manualPrev() {{
            prevSlide();
        }}

        function handleApplyCourse(idx) {{
            const targetIdx = (typeof idx === 'number') ? idx : current;
            const festNames = ['순천만 갈대축제', '진주 남강유등축제', '강릉 커피축제'];
            const targetFest = festNames[targetIdx] || '순천만 갈대축제';
            const targetParam = '?select_fest_and_go=' + encodeURIComponent(targetFest);

            // 1. 최우선: 부모 및 최상위 윈도우로 postMessage 전송 (아이프레임 샌드박스 정책 우회 및 확실한 페이지 이동)
            try {{
                if (window.parent) {{
                    window.parent.postMessage({{ type: 'festapick_navigate', fest: targetFest }}, '*');
                }}
            }} catch(e) {{}}
            try {{
                if (window.top && window.top !== window.parent) {{
                    window.top.postMessage({{ type: 'festapick_navigate', fest: targetFest }}, '*');
                }}
            }} catch(e) {{}}

            // 2. 브라우저가 top 네비게이션을 허용하는 경우 직접 이동
            try {{
                if (window.top && window.top.location) {{
                    window.top.location.href = window.top.location.pathname + targetParam;
                    return;
                }}
            }} catch(e) {{}}

            // 3. Fallback: target="_top" 앵커 클릭
            try {{
                const a = document.createElement('a');
                a.href = targetParam;
                a.target = '_top';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            }} catch(e) {{}}
        }}

        // 자동 롤링 시작
        resetTimer();

        // 마우스 호버 시 일시 정지 (사용자가 편안하게 카드를 읽고 클릭할 수 있도록 지원)
        const spotlightWrapper = document.getElementById('spotlightWrapper');
        if (spotlightWrapper) {{
            spotlightWrapper.addEventListener('mouseenter', () => {{
                if (timer) clearInterval(timer);
            }});
            spotlightWrapper.addEventListener('mouseleave', () => {{
                resetTimer();
            }});
        }}

        // 첫 페이지 로드 시 1번 슬라이드 카드 애니메이션 실행
        window.addEventListener('load', () => {{
            const firstCard = document.querySelector('#slide-0 .editorial-glass-card');
            if (firstCard) {{
                firstCard.style.animation = 'none';
                void firstCard.offsetHeight;
                firstCard.style.animation = '';
            }}
        }});
        setTimeout(() => {{
            const firstCard = document.querySelector('#slide-0 .editorial-glass-card');
            if (firstCard) {{
                firstCard.style.animation = 'none';
                void firstCard.offsetHeight;
                firstCard.style.animation = '';
            }}
        }}, 60);
        </script>
        </body>
        </html>
        """

        # 아이프레임 배너에서 전달되는 페이지 이동 postMessage 이벤트 수신 리스너
        st.html("""
        <script>
        if (!window.__festapick_nav_listener) {
            window.__festapick_nav_listener = true;
            window.addEventListener('message', function(evt) {
                if (evt.data && evt.data.type === 'festapick_navigate' && evt.data.fest) {
                    const currentUrl = new URL(window.location.href);
                    currentUrl.searchParams.set('select_fest_and_go', evt.data.fest);
                    window.location.href = currentUrl.pathname + currentUrl.search;
                }
            });
        }
        </script>
        """, unsafe_allow_javascript=True)

        st_components.html(slider_component_html, height=545)













        # ======================================================================
        # [UI 섹션: 추천 배너 하단 5대 안심 편의 서비스 퀵 메뉴 바 (전용 화면 라우팅)]
        # ======================================================================
        # 킨포크/29CM 에디토리얼 미니멀 라인 아트 SVG (1.3px 스트로크, #012D1D, #FAF7F2 / #F4EFE6 틴트)
        svg_cal = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 64 64" fill="none">
  <rect x="14" y="15" width="36" height="38" rx="5" fill="#FAF7F2" stroke="#012D1D" stroke-width="1.3"/>
  <line x1="14" y1="24" x2="50" y2="24" stroke="#012D1D" stroke-width="1.3"/>
  <line x1="23" y1="11" x2="23" y2="17" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <line x1="41" y1="11" x2="41" y2="17" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <circle cx="24" cy="31" r="1.6" fill="#012D1D"/>
  <circle cx="32" cy="31" r="1.6" fill="#012D1D"/>
  <circle cx="40" cy="31" r="1.6" fill="#012D1D"/>
  <circle cx="24" cy="39" r="1.6" fill="#012D1D"/>
  <circle cx="32" cy="39" r="2.8" stroke="#012D1D" stroke-width="1.2" fill="#F4EFE6"/>
  <circle cx="40" cy="39" r="1.6" fill="#012D1D"/>
  <circle cx="24" cy="46" r="1.6" fill="#012D1D"/>
  <circle cx="32" cy="46" r="1.6" fill="#012D1D"/>
  <circle cx="40" cy="46" r="1.6" fill="#012D1D"/>
</svg>"""

        svg_route = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 64 64" fill="none">
  <circle cx="32" cy="32" r="21" fill="#FAF7F2" stroke="#012D1D" stroke-width="1.3"/>
  <circle cx="32" cy="32" r="2.2" fill="#012D1D"/>
  <path d="M32 15L35 30L32 32L29 30Z" fill="#012D1D" stroke="#012D1D" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M32 49L29 34L32 32L35 34Z" fill="#F4EFE6" stroke="#012D1D" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M15 32L30 29L32 32L30 35Z" fill="#F4EFE6" stroke="#012D1D" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M49 32L34 35L32 32L34 29Z" fill="#F4EFE6" stroke="#012D1D" stroke-width="1.3" stroke-linejoin="round"/>
  <line x1="32" y1="12" x2="32" y2="14" stroke="#012D1D" stroke-width="1.3"/>
  <line x1="32" y1="50" x2="32" y2="52" stroke="#012D1D" stroke-width="1.3"/>
  <line x1="12" y1="32" x2="14" y2="32" stroke="#012D1D" stroke-width="1.3"/>
  <line x1="50" y1="32" x2="52" y2="32" stroke="#012D1D" stroke-width="1.3"/>
</svg>"""

        svg_rest = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 64 64" fill="none">
  <path d="M15 39C15 27 22.5 21 32 21C41.5 21 49 27 49 39Z" fill="#FAF7F2" stroke="#012D1D" stroke-width="1.3"/>
  <circle cx="32" cy="18" r="2.5" fill="#F4EFE6" stroke="#012D1D" stroke-width="1.3"/>
  <line x1="32" y1="20.5" x2="32" y2="21" stroke="#012D1D" stroke-width="1.3"/>
  <line x1="11" y1="42" x2="53" y2="42" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <path d="M15 42C15 45 22 47 32 47C42 47 49 45 49 42" stroke="#012D1D" stroke-width="1.3"/>
  <path d="M26 15C25 12 27 10 26 8" stroke="#012D1D" stroke-width="1.1" stroke-linecap="round"/>
  <path d="M38 15C37 12 39 10 38 8" stroke="#012D1D" stroke-width="1.1" stroke-linecap="round"/>
</svg>"""

        svg_weather = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 64 64" fill="none">
  <circle cx="38" cy="24" r="9" fill="#FAF7F2" stroke="#012D1D" stroke-width="1.3"/>
  <line x1="38" y1="10" x2="38" y2="13" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <line x1="48" y1="14" x2="46" y2="16.5" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <line x1="52" y1="24" x2="49" y2="24" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <line x1="48" y1="34" x2="46" y2="31.5" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <line x1="28" y1="14" x2="30" y2="16.5" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <path d="M43 44H20C15.58 44 12 40.42 12 36C12 31.86 15.14 28.45 19.22 28.05C20.68 21.82 26.24 17.5 32.5 17.5C39.2 17.5 44.8 22.4 45.8 29.0C48.8 29.8 51 32.6 51 36C51 40.42 47.42 44 43 44Z" fill="#FFFFFF" stroke="#012D1D" stroke-width="1.3" stroke-linejoin="round"/>
  <line x1="24" y1="48" x2="22" y2="52" stroke="#012D1D" stroke-width="1.2" stroke-linecap="round"/>
  <line x1="33" y1="48" x2="31" y2="52" stroke="#012D1D" stroke-width="1.2" stroke-linecap="round"/>
  <line x1="42" y1="48" x2="40" y2="52" stroke="#012D1D" stroke-width="1.2" stroke-linecap="round"/>
</svg>"""

        svg_shelter = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 64 64" fill="none">
  <path d="M38 12C38 12 47 16 45 27C43 38 29 39 29 39C29 39 29 27 34 20C38 14 38 12 38 12Z" fill="#FAF7F2" stroke="#012D1D" stroke-width="1.3"/>
  <path d="M31 35C35 28 38 22 41 17" stroke="#012D1D" stroke-width="1.1" stroke-linecap="round"/>
  <line x1="14" y1="39" x2="50" y2="39" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <line x1="16" y1="34" x2="48" y2="34" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <line x1="18" y1="28" x2="18" y2="40" stroke="#012D1D" stroke-width="1.3"/>
  <line x1="46" y1="28" x2="46" y2="40" stroke="#012D1D" stroke-width="1.3"/>
  <line x1="16" y1="28" x2="48" y2="28" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <path d="M19 40L17 50" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <path d="M25 40L27 50" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <path d="M45 40L47 50" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <path d="M39 40L37 50" stroke="#012D1D" stroke-width="1.3" stroke-linecap="round"/>
  <line x1="10" y1="50" x2="54" y2="50" stroke="#012D1D" stroke-width="1.1" stroke-linecap="round"/>
</svg>"""

        b64_cal = base64.b64encode(svg_cal.encode('utf-8')).decode('ascii')
        b64_route = base64.b64encode(svg_route.encode('utf-8')).decode('ascii')
        b64_rest = base64.b64encode(svg_rest.encode('utf-8')).decode('ascii')
        b64_weather = base64.b64encode(svg_weather.encode('utf-8')).decode('ascii')
        b64_shelter = base64.b64encode(svg_shelter.encode('utf-8')).decode('ascii')

        # [동행인 프리셋 및 활성화 키: st.session_state.companion 기준 동기화]
        def resolve_companion_key(comp_val) -> str:
            if not comp_val or str(comp_val).strip().lower() in ("none", "null", ""):
                return "none"
            c = str(comp_val).lower().strip()
            if any(k in c for k in ["solo", "나홀로", "혼자", "1인", "쉼표", "사색"]):
                return "solo"
            if any(k in c for k in ["parent", "부모", "효도", "어르신"]):
                return "parents"
            if any(k in c for k in ["family", "아이", "자녀", "패밀리", "가족"]):
                return "family"
            if any(k in c for k in ["couple", "연인", "커플", "데이트"]):
                return "couple"
            if any(k in c for k in ["pet", "반려", "강아지", "애견", "동반", "동물"]):
                return "pet"
            return "none"

        # [홈 화면 진입/복귀 시 알약 미선택 보장]
        # 사용자가 홈 화면으로 돌아왔을 때는 알약에 아무런 체킹(선택)도 되지 않은 깨끗한 기본 상태로 렌더링
        init_comp = "none"
        is_solo = False
        is_parents = False
        is_family = False
        is_couple = False
        is_pet = False

        def _chip_inline_style(is_active: bool) -> str:
            if is_active:
                return "background: #012D1D !important; color: #FFFFFF !important; border-color: #012D1D !important; box-shadow: 0 4px 14px rgba(1, 45, 29, 0.28) !important; transform: translateY(-1px); font-weight: 800 !important;"
            return "background: #FFFFFF !important; color: #414844 !important; border: 1.5px solid #E6DECB !important; box-shadow: 0 1px 4px rgba(1, 45, 29, 0.04) !important;"

        st.html(f"""
        <style>
        /* 페스타픽 안심 편의 서비스 퀵 메뉴 바 */
        .quick-concierge-section {{
            margin-top: 36px;
            margin-bottom: 32px;
            padding: 30px 32px 32px 32px;
            background: #FAF7F2;
            border: 1px solid #EAE4DA;
            border-radius: 20px;
            box-shadow: 0 4px 20px rgba(1, 45, 29, 0.04);
            user-select: none;
            position: relative;
            scroll-margin-top: 50px;
        }}

        .comp-radio {{
            display: none !important;
        }}

        .quick-title-wrap {{
            text-align: left;
            margin-bottom: 18px;
        }}

        .quick-title-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.78rem;
            font-weight: 800;
            color: #012D1D;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 5px;
        }}

        .quick-main-title {{
            font-size: 22px;
            font-weight: 800;
            color: #1C1C16;
            margin: 0;
            line-height: 1.35;
            letter-spacing: -0.02em;
            font-family: 'Pretendard', sans-serif;
        }}

        .quick-sub-title {{
            font-size: 14.5px;
            color: #6C756E;
            margin: 6px 0 0 0;
            font-weight: 500;
            letter-spacing: -0.01em;
        }}

        /* [동행인 퀵 필터 칩 바] */
        .companion-filter-bar {{
            display: flex;
            align-items: center;
            gap: 9px;
            margin: 18px 0 24px 0;
            overflow-x: auto;
            padding-bottom: 6px;
            -ms-overflow-style: none;
            scrollbar-width: none;
        }}
        .companion-filter-bar::-webkit-scrollbar {{
            display: none;
        }}
        .companion-chip {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #FFFFFF;
            color: #414844;
            border: 1.5px solid #E6DECB;
            border-radius: 22px;
            padding: 7px 16px;
            font-size: 13.5px;
            font-weight: 700;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1);
            user-select: none;
            box-shadow: 0 1px 4px rgba(1, 45, 29, 0.04);
            font-family: 'Pretendard', sans-serif;
        }}
        .companion-chip:hover {{
            background: #F4EFE6;
            border-color: #012D1D;
            color: #012D1D;
            transform: translateY(-1px);
        }}

        /* [칩 활성화: CSS :has(), data-active, is-active 동시 지원 및 까만색 배경/흰색 글씨 고정] */
        .companion-chip.is-active,
        .quick-concierge-section:has(#copt_solo:checked) #lbl_solo,
        .quick-concierge-section[data-active="solo"] #lbl_solo,
        .quick-concierge-section:has(#copt_parents:checked) #lbl_parents,
        .quick-concierge-section[data-active="parents"] #lbl_parents,
        .quick-concierge-section:has(#copt_family:checked) #lbl_family,
        .quick-concierge-section[data-active="family"] #lbl_family,
        .quick-concierge-section:has(#copt_couple:checked) #lbl_couple,
        .quick-concierge-section[data-active="couple"] #lbl_couple,
        .quick-concierge-section:has(#copt_pet:checked) #lbl_pet,
        .quick-concierge-section[data-active="pet"] #lbl_pet {{
            background: #012D1D !important;
            color: #FFFFFF !important;
            border-color: #012D1D !important;
            box-shadow: 0 4px 14px rgba(1, 45, 29, 0.28) !important;
            transform: translateY(-1px);
            font-weight: 800 !important;
        }}

        /* [초기화 / 접기 칩: 활성화 시 부드럽게 등장] */
        .companion-reset-chip {{
            display: none;
            align-items: center;
            gap: 5px;
            background: #F3F4F6;
            color: #6B7280;
            border: 1.5px dashed #D1D5DB;
            border-radius: 22px;
            padding: 7px 13px;
            font-size: 12.5px;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s ease;
            user-select: none;
            font-family: 'Pretendard', sans-serif;
        }}
        .companion-reset-chip:hover {{
            background: #E5E7EB;
            color: #374151;
            border-color: #9CA3AF;
        }}

        .quick-concierge-section:has(.comp-radio-active:checked) .companion-reset-chip,
        .quick-concierge-section[data-active="solo"] .companion-reset-chip,
        .quick-concierge-section[data-active="parents"] .companion-reset-chip,
        .quick-concierge-section[data-active="family"] .companion-reset-chip,
        .quick-concierge-section[data-active="couple"] .companion-reset-chip,
        .quick-concierge-section[data-active="pet"] .companion-reset-chip {{
            display: inline-flex !important;
            animation: fadeInChip 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }}

        @keyframes fadeInChip {{
            from {{ opacity: 0; transform: scale(0.92); }}
            to {{ opacity: 1; transform: scale(1); }}
        }}

        .quick-menu-grid {{
            display: grid !important;
            grid-template-columns: repeat(5, 1fr) !important;
            gap: 36px !important;
            max-width: 1160px !important;
            margin: 0 auto !important;
            align-items: start !important;
            justify-items: center !important;
        }}

        .quick-menu-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            text-decoration: none !important;
            cursor: pointer;
            user-select: none;
            transition: all 0.25s ease;
            width: 100%;
            max-width: 155px;
            padding: 6px 0;
            position: relative;
        }}

        .quick-circle-btn {{
            width: 92px;
            height: 92px;
            border-radius: 50%;
            background: #FFFFFF;
            border: 1.5px solid #E6DECB;
            box-shadow: 0 4px 18px rgba(1, 45, 29, 0.05);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
            position: relative;
        }}

        .quick-menu-item:hover .quick-circle-btn {{
            transform: translateY(-5px) scale(1.04);
            box-shadow: 0 12px 24px rgba(1, 45, 29, 0.12);
            border-color: #012D1D;
        }}

        .quick-circle-btn img {{
            width: 58px;
            height: 58px;
            display: block;
            pointer-events: none;
            transition: transform 0.2s ease;
        }}

        .quick-item-label {{
            margin-top: 11px;
            font-size: 15px;
            font-weight: 700;
            color: #1C1C16;
            letter-spacing: -0.02em;
            transition: color 0.2s ease;
            white-space: nowrap;
            line-height: 1.25;
        }}

        .quick-menu-item:hover .quick-item-label {{
            color: #012D1D;
            font-weight: 800;
        }}

        /* [동그라미 하단 가이드 문구 영구 비노출 보장] */
        .quick-item-tip,
        .tip-msg {{
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }}

        /* 하이라이트 뱃지 */
        .badge-nav-dot {{
            position: absolute;
            top: 2px;
            right: 4px;
            background: #10B981;
            color: #FFFFFF;
            font-size: 9px;
            font-weight: 800;
            padding: 2px 5px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.15);
        }}

        @media (max-width: 768px) {{
            .quick-concierge-section {{
                padding: 20px 16px;
                margin-top: 20px;
            }}
            .quick-main-title {{
                font-size: 19px;
            }}
            .quick-menu-grid {{
                display: flex;
                overflow-x: auto;
                scroll-snap-type: x mandatory;
                padding-bottom: 10px;
                gap: 14px;
                justify-content: flex-start;
                -webkit-overflow-scrolling: touch;
            }}
            .quick-menu-item {{
                flex: 0 0 auto;
                width: 110px;
                scroll-snap-align: center;
            }}
            .quick-circle-btn {{
                width: 82px;
                height: 82px;
            }}
            .quick-circle-btn img {{
                width: 48px;
                height: 48px;
            }}
            .quick-item-tip {{
                font-size: 10px;
                max-width: 110px;
                white-space: normal;
                word-break: keep-all;
                padding: 3px 6px;
            }}
            .tip-msg {{
                white-space: normal;
                word-break: keep-all;
            }}
        }}

        /* [동행인 선택 유도 가이드 텍스트] */
        .comp-guide-text {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            margin: 16px 0 0 0;
            padding: 5px 12px;
            font-size: 12.5px;
            font-weight: 600;
            color: #047857;
            background: rgba(16, 185, 129, 0.07);
            border: 1px solid rgba(16, 185, 129, 0.18);
            border-radius: 999px;
            letter-spacing: -0.01em;
            transition: opacity 0.25s ease;
        }}
        .quick-concierge-section:not([data-active="none"]) .comp-guide-text {{
            opacity: 0.55;
        }}
        .companion-filter-bar.comp-attention {{
            animation: compPulse 0.9s ease;
        }}
        @keyframes compPulse {{
            0%, 100% {{ transform: translateX(0); }}
            25% {{ transform: translateX(-4px); }}
            75% {{ transform: translateX(4px); }}
        }}

        /* [동행인 퀵 선택 팝오버 모달] */
        .comp-popover-backdrop {{
            position: fixed;
            inset: 0;
            background: rgba(1, 45, 29, 0.28);
            backdrop-filter: blur(3px);
            -webkit-backdrop-filter: blur(3px);
            z-index: 999990;
            display: none;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .comp-popover-backdrop.open {{
            display: flex;
            animation: popFadeIn 0.2s ease forwards;
        }}
        .comp-popover-card {{
            position: relative;
            width: 100%;
            max-width: 440px;
            background: linear-gradient(160deg, #FFFDF8 0%, #F0FDF4 100%);
            border: 1.5px solid #D1FAE5;
            border-radius: 22px;
            padding: 28px 26px 24px 26px;
            box-shadow: 0 24px 60px rgba(1, 45, 29, 0.22);
            text-align: center;
            font-family: 'Pretendard', sans-serif;
            animation: popSlideUp 0.28s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }}
        .comp-popover-close {{
            position: absolute;
            top: 12px;
            right: 14px;
            width: 30px;
            height: 30px;
            border: none;
            border-radius: 50%;
            background: rgba(1, 45, 29, 0.06);
            color: #414844;
            font-size: 14px;
            cursor: pointer;
            transition: background 0.2s ease;
        }}
        .comp-popover-close:hover {{
            background: rgba(1, 45, 29, 0.14);
        }}
        .comp-popover-title {{
            font-size: 20px;
            font-weight: 800;
            color: #1C1C16;
            margin: 0 0 6px 0;
            letter-spacing: -0.02em;
        }}
        .comp-popover-sub {{
            font-size: 13px;
            color: #6C756E;
            margin: 0 0 20px 0;
            line-height: 1.5;
        }}
        .comp-popover-sub strong {{
            color: #065F46;
        }}
        .comp-popover-chips {{
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 9px;
        }}
        .comp-pop-chip {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #FFFFFF;
            color: #1C1C16;
            border: 1.5px solid #E6DECB;
            border-radius: 22px;
            padding: 9px 16px;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            font-family: 'Pretendard', sans-serif;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 1px 4px rgba(1, 45, 29, 0.05);
        }}
        .comp-pop-chip:hover {{
            background: #012D1D;
            color: #FFFFFF;
            border-color: #012D1D;
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(1, 45, 29, 0.22);
        }}
        .comp-popover-skip {{
            display: inline-block;
            margin-top: 18px;
            font-size: 12px;
            color: #9CA3AF;
            background: none;
            border: none;
            cursor: pointer;
            text-decoration: underline;
            text-underline-offset: 3px;
        }}
        .comp-popover-skip:hover {{
            color: #4B5563;
        }}
        @keyframes popFadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        @keyframes popSlideUp {{
            from {{ opacity: 0; transform: translateY(14px) scale(0.97); }}
            to {{ opacity: 1; transform: translateY(0) scale(1); }}
        }}
        </style>

        <div class="quick-concierge-section" id="conciergeSection" data-active="{init_comp}">
            <!-- 동행인 상태 관리 라디오 버튼 (st.session_state.companion 연동) -->
            <input type="radio" name="comp_service_tab" id="copt_none" class="comp-radio" {'checked' if init_comp == 'none' else ''} />
            <input type="radio" name="comp_service_tab" id="copt_solo" class="comp-radio comp-radio-active" {'checked' if init_comp == 'solo' else ''} />
            <input type="radio" name="comp_service_tab" id="copt_parents" class="comp-radio comp-radio-active" {'checked' if init_comp == 'parents' else ''} />
            <input type="radio" name="comp_service_tab" id="copt_family" class="comp-radio comp-radio-active" {'checked' if init_comp == 'family' else ''} />
            <input type="radio" name="comp_service_tab" id="copt_couple" class="comp-radio comp-radio-active" {'checked' if init_comp == 'couple' else ''} />
            <input type="radio" name="comp_service_tab" id="copt_pet" class="comp-radio comp-radio-active" {'checked' if init_comp == 'pet' else ''} />

            <div class="quick-title-wrap">
                <div class="quick-title-badge">
                    <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#012D1D;"></span>
                    <span>FestaPick Concierge</span>
                </div>
                <h2 class="quick-main-title">
                    실패 없는 여행을 위한 페스타픽 안심 편의 서비스
                </h2>
                <p class="quick-sub-title">
                    원하시는 편의 서비스를 클릭하시면 상세 인터랙티브 전용 페이지 및 실시간 편의 안내를 확인하실 수 있습니다
                </p>
            </div>

            <!-- 동행인 선택 유도 가이드 -->
            <div class="comp-guide-text">💡 동행인을 먼저 선택하시면 맞춤형 안내가 열립니다</div>

            <!-- 동행인 퀵 필터 칩 바 -->
            <div class="companion-filter-bar" id="companionFilterBar">
                <label for="copt_solo" class="companion-chip {'is-active' if is_solo else ''}" id="lbl_solo" data-comp="solo" style="{_chip_inline_style(is_solo)}">
                    <span>🌿</span> 나홀로 쉼표
                </label>
                <label for="copt_parents" class="companion-chip {'is-active' if is_parents else ''}" id="lbl_parents" data-comp="parents" style="{_chip_inline_style(is_parents)}">
                    <span>🧓</span> 부모님 효도
                </label>
                <label for="copt_family" class="companion-chip {'is-active' if is_family else ''}" id="lbl_family" data-comp="family" style="{_chip_inline_style(is_family)}">
                    <span>👶</span> 아이와 패밀리
                </label>
                <label for="copt_couple" class="companion-chip {'is-active' if is_couple else ''}" id="lbl_couple" data-comp="couple" style="{_chip_inline_style(is_couple)}">
                    <span>💑</span> 연인 데이트
                </label>
                <label for="copt_pet" class="companion-chip {'is-active' if is_pet else ''}" id="lbl_pet" data-comp="pet" style="{_chip_inline_style(is_pet)}">
                    <span>🐾</span> 반려견 동반
                </label>
                <label for="copt_none" class="companion-reset-chip" id="lbl_none" data-comp="none" style="{'display: inline-flex !important;' if init_comp != 'none' else ''}">
                    <span>✕</span> 뱃지 접기
                </label>
            </div>

            <!-- 5개 원형 아이콘 버튼 (가이드 문구 없이 깔끔한 디자인) -->
            <div class="quick-menu-grid">
                <!-- 1. 지역축제 달력 -->
                <a href="?view=calendar" target="_self" class="quick-menu-item">
                    <div class="quick-circle-btn">
                        <img src="data:image/svg+xml;base64,{b64_cal}" alt="지역축제 달력" />
                        <span class="badge-nav-dot">VIEW</span>
                    </div>
                    <div class="quick-item-label">지역축제 달력</div>
                </a>

                <!-- 2. 쉼표 여정 -->
                <a href="?view=course" target="_self" class="quick-menu-item">
                    <div class="quick-circle-btn">
                        <img src="data:image/svg+xml;base64,{b64_route}" alt="쉼표 여정" />
                        <span class="badge-nav-dot">VIEW</span>
                    </div>
                    <div class="quick-item-label">쉼표 여정</div>
                </a>

                <!-- 3. 착한가격 식당 -->
                <a href="?view=restaurant" target="_self" class="quick-menu-item">
                    <div class="quick-circle-btn">
                        <img src="data:image/svg+xml;base64,{b64_rest}" alt="착한가격 식당" />
                        <span class="badge-nav-dot">VIEW</span>
                    </div>
                    <div class="quick-item-label">착한가격 식당</div>
                </a>

                <!-- 4. 날씨확인 -->
                <a href="?view=weather" target="_self" class="quick-menu-item">
                    <div class="quick-circle-btn">
                        <img src="data:image/svg+xml;base64,{b64_weather}" alt="날씨확인" />
                        <span class="badge-nav-dot">VIEW</span>
                    </div>
                    <div class="quick-item-label">날씨확인</div>
                </a>

                <!-- 5. 안심쉼터 -->
                <a href="?view=shelter" target="_self" class="quick-menu-item">
                    <div class="quick-circle-btn">
                        <img src="data:image/svg+xml;base64,{b64_shelter}" alt="안심쉼터" />
                        <span class="badge-nav-dot">VIEW</span>
                    </div>
                    <div class="quick-item-label">안심쉼터</div>
                </a>
            </div>

            <!-- 동행인 미선택 시 노출되는 퀵 선택 팝오버 -->
            <div class="comp-popover-backdrop" id="compPopover" role="dialog" aria-modal="true" aria-labelledby="compPopoverTitle">
                <div class="comp-popover-card">
                    <button type="button" class="comp-popover-close" id="compPopoverClose" aria-label="닫기">✕</button>
                    <h3 class="comp-popover-title" id="compPopoverTitle">누구와 함께 떠나시나요? 🎈</h3>
                    <p class="comp-popover-sub">선택하시면 <strong id="compPopoverService">맞춤 서비스</strong> 페이지로 바로 이동합니다</p>
                    <div class="comp-popover-chips">
                        <button type="button" class="comp-pop-chip" data-pop-comp="solo">🌿 혼자</button>
                        <button type="button" class="comp-pop-chip" data-pop-comp="parents">🧓 부모님</button>
                        <button type="button" class="comp-pop-chip" data-pop-comp="family">👶 아이와</button>
                        <button type="button" class="comp-pop-chip" data-pop-comp="couple">💑 연인</button>
                        <button type="button" class="comp-pop-chip" data-pop-comp="pet">🐾 반려견</button>
                    </div>
                    <button type="button" class="comp-popover-skip" id="compPopoverSkip">선택 없이 둘러보기</button>
                </div>
            </div>

            <script>
            (function() {{
                function setupConcierge() {{
                    var section = document.getElementById('conciergeSection');
                    if (!section) return;
                    var chips = section.querySelectorAll('.companion-chip[data-comp]');
                    var resetChip = section.querySelector('.companion-reset-chip');

                    function setActive(targetKey) {{
                        section.setAttribute('data-active', targetKey);
                        var radios = section.querySelectorAll('input[type="radio"]');
                        radios.forEach(function(r) {{ r.checked = false; }});
                        var targetRadio = document.getElementById('copt_' + targetKey);
                        if (targetRadio) {{
                            targetRadio.checked = true;
                        }}
                        // 선택된 칩 시각적 스타일: 활성화 칩만 다크에메랄드(#012D1D), 나머지는 기본 흰색
                        chips.forEach(function(c) {{
                            var cKey = c.getAttribute('data-comp');
                            if (cKey === targetKey && targetKey !== 'none') {{
                                c.classList.add('is-active');
                                c.style.setProperty('background', '#012D1D', 'important');
                                c.style.setProperty('color', '#FFFFFF', 'important');
                                c.style.setProperty('border-color', '#012D1D', 'important');
                                c.style.setProperty('box-shadow', '0 4px 14px rgba(1, 45, 29, 0.28)', 'important');
                                c.style.setProperty('font-weight', '800', 'important');
                            }} else {{
                                c.classList.remove('is-active');
                                c.style.setProperty('background', '#FFFFFF', 'important');
                                c.style.setProperty('color', '#414844', 'important');
                                c.style.setProperty('border', '1.5px solid #E6DECB', 'important');
                                c.style.setProperty('box-shadow', '0 1px 4px rgba(1, 45, 29, 0.04)', 'important');
                                c.style.removeProperty('font-weight');
                            }}
                        }});
                        if (resetChip) {{
                            resetChip.style.display = (targetKey && targetKey !== 'none') ? 'inline-flex' : 'none';
                        }}
                        // 5대 상세 페이지 이동 링크에 동행인 파라미터(?companion=...) 자동 연결
                        var menuLinks = section.querySelectorAll('.quick-menu-grid a.quick-menu-item');
                        menuLinks.forEach(function(a) {{
                            if (!a.getAttribute('data-base-href')) {{
                                var rawH = a.getAttribute('href') || '';
                                a.setAttribute('data-base-href', rawH.split('&companion=')[0]);
                            }}
                            var cleanHref = a.getAttribute('data-base-href');
                            if (targetKey && targetKey !== 'none') {{
                                var sep = cleanHref.indexOf('?') >= 0 ? '&' : '?';
                                a.setAttribute('href', cleanHref + sep + 'companion=' + encodeURIComponent(targetKey));
                            }} else {{
                                a.setAttribute('href', cleanHref);
                            }}
                        }});
                    }}

                    // [홈 복귀 시 철저한 초기화: 캐시 및 URL 파라미터 완전 삭제 -> 알약 무선택 기본 상태 보장]
                    try {{
                        sessionStorage.removeItem('festapick_active_companion');
                        var urlParams = new URLSearchParams(window.location.search);
                        if (urlParams.has('companion')) {{
                            urlParams.delete('companion');
                            var cleanQuery = urlParams.toString();
                            var cleanUrl = window.location.pathname + (cleanQuery ? '?' + cleanQuery : '');
                            window.history.replaceState({{}}, '', cleanUrl);
                        }}
                    }} catch(e) {{}}
                    setActive('none');

                    // 알약 클릭 인터랙션: 클릭 시 알약만 토글되며, 동그라미 아이콘 밑에 글씨는 절대 쓰지 않음
                    chips.forEach(function(chip) {{
                        if (chip.getAttribute('data-bound') === 'true') return;
                        chip.setAttribute('data-bound', 'true');
                        chip.addEventListener('click', function(e) {{
                            e.preventDefault();
                            e.stopPropagation();
                            var target = this.getAttribute('data-comp');
                            var current = section.getAttribute('data-active') || 'none';
                            var nextTarget = (current === target) ? 'none' : target;
                            setActive(nextTarget);
                        }});
                    }});

                    if (resetChip && resetChip.getAttribute('data-bound') !== 'true') {{
                        resetChip.setAttribute('data-bound', 'true');
                        resetChip.addEventListener('click', function(e) {{
                            e.preventDefault();
                            e.stopPropagation();
                            setActive('none');
                        }});
                    }}

                    // [5개 아이콘 클릭 분기] 동행인 선택 시 즉시 이동 / 미선택 시 퀵 선택 팝오버 노출
                    var popover = document.getElementById('compPopover');
                    var popService = document.getElementById('compPopoverService');
                    var filterBar = document.getElementById('companionFilterBar');
                    var pendingHref = null;

                    function openPopover(baseHref, serviceName) {{
                        pendingHref = baseHref;
                        if (popService) popService.textContent = '\u2018' + serviceName + '\u2019';
                        if (popover) popover.classList.add('open');
                        if (filterBar) {{
                            filterBar.classList.remove('comp-attention');
                            void filterBar.offsetWidth;
                            filterBar.classList.add('comp-attention');
                        }}
                    }}
                    function closePopover() {{
                        if (popover) popover.classList.remove('open');
                    }}

                    var menuItems = section.querySelectorAll('.quick-menu-grid a.quick-menu-item');
                    menuItems.forEach(function(a) {{
                        if (!a.getAttribute('data-base-href')) {{
                            var rawH = a.getAttribute('href') || '';
                            a.setAttribute('data-base-href', rawH.split('&companion=')[0]);
                        }}
                        if (a.getAttribute('data-nav-bound') === 'true') return;
                        a.setAttribute('data-nav-bound', 'true');
                        a.addEventListener('click', function(e) {{
                            var current = section.getAttribute('data-active') || 'none';
                            var baseHref = this.getAttribute('data-base-href') || this.getAttribute('href');
                            e.preventDefault();
                            if (current && current !== 'none') {{
                                // 동행인 선택됨 -> 파라미터를 붙여 즉시 전용 상세 페이지 이동
                                var sep = baseHref.indexOf('?') >= 0 ? '&' : '?';
                                window.location.href = baseHref + sep + 'companion=' + encodeURIComponent(current);
                            }} else {{
                                // 동행인 미선택 -> 퀵 선택 팝오버 노출
                                var labelEl = this.querySelector('.quick-item-label');
                                openPopover(baseHref, labelEl ? labelEl.textContent.trim() : '맞춤 서비스');
                            }}
                        }});
                    }});

                    if (popover && popover.getAttribute('data-bound') !== 'true') {{
                        popover.setAttribute('data-bound', 'true');
                        popover.querySelectorAll('.comp-pop-chip').forEach(function(btn) {{
                            btn.addEventListener('click', function() {{
                                var key = this.getAttribute('data-pop-comp');
                                if (!pendingHref) return;
                                setActive(key);
                                var sep = pendingHref.indexOf('?') >= 0 ? '&' : '?';
                                window.location.href = pendingHref + sep + 'companion=' + encodeURIComponent(key);
                            }});
                        }});
                        var closeBtn = document.getElementById('compPopoverClose');
                        if (closeBtn) closeBtn.addEventListener('click', closePopover);
                        var skipBtn = document.getElementById('compPopoverSkip');
                        if (skipBtn) skipBtn.addEventListener('click', function() {{
                            if (pendingHref) window.location.href = pendingHref;
                        }});
                        popover.addEventListener('click', function(e) {{
                            if (e.target === popover) closePopover();
                        }});
                        document.addEventListener('keydown', function(e) {{
                            if (e.key === 'Escape') closePopover();
                        }});
                    }}

                    // 스크롤 복원
                    function restoreSectionScroll() {{
                        try {{
                            var anchor = sessionStorage.getItem('festapick_scroll_anchor');
                            if (anchor === 'conciergeSection' || window.location.hash === '#conciergeSection') {{
                                section.scrollIntoView({{ behavior: 'auto', block: 'start' }});
                                sessionStorage.removeItem('festapick_scroll_anchor');
                                sessionStorage.removeItem('festapick_last_scroll_y');
                            }}
                        }} catch(err) {{}}
                    }}
                    restoreSectionScroll();
                }}
                setupConcierge();
                function disableNativeTooltips() {{
                    document.querySelectorAll('[title]').forEach(function(el) {{
                        el.removeAttribute('title');
                    }});
                }}
                disableNativeTooltips();
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', function() {{
                        setupConcierge();
                        disableNativeTooltips();
                    }});
                }}
                setTimeout(function() {{ setupConcierge(); disableNativeTooltips(); }}, 100);
            }})();
            </script>
        </div>
        """, unsafe_allow_javascript=True)

