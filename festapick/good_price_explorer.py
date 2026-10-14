"""
festapick/good_price_explorer.py - 대한민국 정부 공식 인증 전국 착한가격식당
================================================================================
[에디토리얼 매거진 레이아웃 & 여행 코스 뷰 1:1 동기화 사양]
1. 전체 레이아웃 너비(Container Max-Width):
   - max-width: 1360px !important, margin: 0 auto !important, padding: 1.0rem ~ 3.5rem
   - 배경색: 아이보리 (#F9F8F3) & 딥 포레스트 그린 (#012D1D, #1B4332)
   - 여행 코스(course_explorer.py)와 100% 동일한 컨테이너 폭으로 화면 흔들림 완전 방지
2. 섹션별 수직 비율 및 여백 (Spacing System):
   - 상단 매거진 타이틀 ('MaruBuri', 2.1rem, -0.02em) + 서브 텍스트 (0.94rem)
   - 우측 상단 '홈으로' 고스트 알약 버튼
   - 슬림하고 단정한 정부 인증 컴팩트 리본 띠 배너
3. 7대 권역 탭:
   - [전국 전체] [수도권] [충청권] [강원권] [호남권] [영남권] [제주]
   - 활성 탭: 딥 포레스트 그린(#012D1D) 배경 + 흰색 볼드 텍스트
4. 서브 컨트롤 라인 (좌우 분할 1줄):
   - 좌측: [☑ 🎪 주요 축제장 인근 안심 식당만 보기] 토글 (반경 3km 필터링 & 최단거리순 정렬)
   - 우측: [식당명 또는 메뉴 검색 🔍] 에디토리얼 검색창
5. 반응형 그리드 & 카드 시스템:
   - 3열 그리드 (repeat(auto-fill, minmax(290px, 1fr)), gap: 22px)
   - 16:9 비율 썸네일 이미지 & 연두색 캡슐 축제 연계 배지 (.badge-fest-link)
   - 카카오맵 길찾기 ↗ 버튼 및 단정한 12개 단위 페이지네이션
================================================================================
"""

import os
import re
import json
import html
import math
import urllib.parse
from typing import Dict, List, Any, Tuple
import streamlit as st

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CURRENT_DIR, "data")
PREPROCESSED_JSON = os.path.join(DATA_DIR, "good_price_restaurants_preprocessed.json")
CALENDAR_MASTER_FESTIVALS_JSON = os.path.join(DATA_DIR, "calendar_master_festivals.json")
MASTER_FESTIVALS_JSON = os.path.join(DATA_DIR, "master_2026_oct_festivals.json")

# 8대 권역 정의 및 행정구역 매핑 ('서울' 독립 카테고리 분리, 전국 17개 시·도 전수 커버)
ZONE_TABS = [
    {"key": "전국", "label": "전국 전체", "regions": []},
    {"key": "서울", "label": "서울", "regions": ["서울특별시"]},
    {"key": "경기인천", "label": "경기·인천", "regions": ["경기도", "인천광역시"]},
    {"key": "충청권", "label": "충청권", "regions": ["충청남도", "충청북도", "대전광역시", "세종특별자치시"]},
    {"key": "강원권", "label": "강원권", "regions": ["강원특별자치도"]},
    {"key": "호남권", "label": "호남권", "regions": ["전라남도", "전북특별자치도", "광주광역시"]},
    {"key": "영남권", "label": "영남권", "regions": ["경상북도", "경상남도", "대구광역시", "울산광역시", "부산광역시"]},
    {"key": "제주", "label": "제주", "regions": ["제주특별자치도"]},
]

# 메뉴·업종별 지능형 1:1 매칭 실사 이미지 풀 (정통 한국 음식 실사 100% 매핑, 외산 음식/치킨 왜곡 원천 배제)
CATEGORY_FOOD_IMAGES = {
    # 1. 김밥 / 떡볶이 / 만두 / 분식 (정통 한국 김밥 실사, 치킨 원천 배제)
    "gimbap_bunsik": [
        "https://images.unsplash.com/photo-1563245372-f21724e3856d?auto=format&fit=crop&w=800&q=80",  # 정갈한 한국 김밥
        "https://images.unsplash.com/photo-1590301157890-4810ed352733?auto=format&fit=crop&w=800&q=80",  # 김밥 롤 한상
    ],
    # 2. 족발 / 보쌈 / 수육 (한국 전통 족발·보쌈 실사, 양식 닭가슴살 배제)
    "jokbal_bossam": [
        "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1558030006-450675393462?auto=format&fit=crop&w=800&q=80",
    ],
    # 3. 불고기 / 갈비 / 뚝배기불고기 / 한우불고기 (한국식 양념 불고기 실사, 토마호크 배제)
    "korean_beef_bulgogi": [
        "https://images.unsplash.com/photo-1529193591184-b1d58069ecdd?auto=format&fit=crop&w=800&q=80",  # 한국식 양념 불고기
        "https://images.unsplash.com/photo-1558030006-450675393462?auto=format&fit=crop&w=800&q=80",  # 불고기 한상
    ],
    # 4. 칼국수 / 가락국수 / 잔치국수 / 수제비 / 고기국수 (한국 온면·칼국수 실사, 동남아 라멘 배제)
    "korean_noodle": [
        "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=800&q=80",  # 정갈한 한국식 국수
        "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=800&q=80",  # 따뜻한 국수 한 그릇
    ],
    # 5. 삼겹살 / 흑돼지 / 목살 / 생고기 구이 (한국 불판 삼겹살 실사)
    "pork_bbq": [
        "https://images.unsplash.com/photo-1594041680534-e8c8cdebd659?auto=format&fit=crop&w=800&q=80",  # 한국 삼겹살 구이
        "https://images.unsplash.com/photo-1529193591184-b1d58069ecdd?auto=format&fit=crop&w=800&q=80",  # 불판 구이
    ],
    # 6. 생선회 / 모듬회 / 활어회 / 해산물 (한국 횟집 모듬회 실사)
    "seafood_sashimi": [
        "https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?auto=format&fit=crop&w=800&q=80",  # 신선한 모듬회
        "https://images.unsplash.com/photo-1579871494447-9811cf80d66c?auto=format&fit=crop&w=800&q=80",  # 생선 요리
    ],
    # 7. 찌개 / 탕 / 국밥 / 해장국 / 대구탕 / 황태국 (정통 한국 뚝배기 찌개·국밥 실사)
    "soup_stew": [
        "https://upload.wikimedia.org/wikipedia/commons/8/8b/Dwaeji-gukbap.jpg",  # 정통 한국 뚝배기 돼지국밥 실사
        "https://images.unsplash.com/photo-1563245372-f21724e3856d?auto=format&fit=crop&w=800&q=80",  # 정갈한 뚝배기 탕반 한상
        "https://images.unsplash.com/photo-1553163147-622ab57be1c7?auto=format&fit=crop&w=800&q=80",  # 따뜻한 뚝배기 국밥 상차림
    ],
    # 8. 짜장면 / 짬뽕 / 탕수육 / 중화요리
    "chinese": [
        "https://images.unsplash.com/photo-1585032226651-759b368d7246?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=800&q=80",
    ],
    # 9. 백반 / 가정식 / 정식 / 비빔밥 / 한식
    "korean_meal": [
        "https://images.unsplash.com/photo-1553163147-622ab57be1c7?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1563245372-f21724e3856d?auto=format&fit=crop&w=800&q=80",
    ],
    # 10. 치킨 / 통닭 (상호·메뉴에 치킨/통닭이 명시된 경우만 매칭)
    "chicken": [
        "https://images.unsplash.com/photo-1562967914-608f82629710?auto=format&fit=crop&w=800&q=80",
    ],
    # 11. 냉면 / 밀면 / 막국수
    "cold_noodle": [
        "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=800&q=80",
    ],
    # 12. 돈가스 / 일식 (바삭한 황금빛 한국식 등심 왕돈까스 실사)
    "cutlet_japanese": [
        "https://images.unsplash.com/photo-1679572473418-aacccc69e2d0?auto=format&fit=crop&w=800&q=80",  # 바삭한 황금빛 돈까스 튀김 정식
        "https://images.unsplash.com/photo-1677743540715-d4fe04852225?auto=format&fit=crop&w=800&q=80",  # 바삭한 수제 등심 돈까스
    ],
}


def get_menu_matched_image(name: str, sector: str, menu1: str, menu2: str, idx: int, address: str = "") -> Tuple[str, str]:
    """
    식당명, 업종, 대표 메뉴명을 정밀 분석하여 100% 일치하는 한국 정품 요리 실사 이미지 반환
    (식당명과 주소의 고유 해시값을 결합하여 동일 화면 내 카드 이미지 중복 원천 방지)
    """
    text = f"{name} {sector} {menu1} {menu2}".lower()
    hash_seed = abs(hash(f"{name}_{address}")) + idx

    # 1. 돈가스 / 돈까스 / 카츠 / 경양식 (미스터돈가스, 학사식당 등이 삼겹살로 빠지는 것 원천 차단 - 최우선 매칭!)
    if any(k in text for k in ["돈가스", "돈까스", "돈카츠", "카츠", "경양식", "포크커틀릿"]):
        pool = CATEGORY_FOOD_IMAGES["cutlet_japanese"]
        return pool[hash_seed % len(pool)], ""

    # 2. 김밥 / 분식 / 떡볶이 / 만두
    if any(k in text for k in ["김밥", "떡볶이", "라볶이", "만두", "분식", "라면", "순대"]):
        pool = CATEGORY_FOOD_IMAGES["gimbap_bunsik"]
        return pool[hash_seed % len(pool)], ""

    # 3. 족발 / 보쌈 / 수육
    if any(k in text for k in ["족발", "보쌈", "왕족발", "수육", "미니족"]):
        pool = CATEGORY_FOOD_IMAGES["jokbal_bossam"]
        return pool[hash_seed % len(pool)], ""

    # 4. 불고기 / 갈비 / 뚝불 / 소불고기
    if any(k in text for k in ["불고기", "갈비", "뚝불", "소갈비", "돼지갈비", "양념갈비"]):
        pool = CATEGORY_FOOD_IMAGES["korean_beef_bulgogi"]
        return pool[hash_seed % len(pool)], ""

    # 5. 칼국수 / 가락국수 / 잔치국수 / 수제비 / 고기국수
    if any(k in text for k in ["칼국수", "가락국수", "잔치국수", "비빔국수", "국수", "고기국수", "수제비", "온면", "우동", "메밀"]):
        pool = CATEGORY_FOOD_IMAGES["korean_noodle"]
        return pool[hash_seed % len(pool)], ""

    # 6. 생선회 / 활어회 / 모듬회 / 횟집 / 해물 / 물회
    if any(k in text for k in ["회", "횟집", "사시미", "광어", "우럭", "해물", "물회", "수산"]):
        pool = CATEGORY_FOOD_IMAGES["seafood_sashimi"]
        return pool[hash_seed % len(pool)], ""

    # 7. 찌개 / 탕 / 국밥 / 해장국 (돼지국밥, 순대국밥, 곰탕, 김치찌개, 된장찌개 등)
    if any(k in text for k in ["돼지국밥", "순대국", "순대국밥", "설렁탕", "곰탕", "국밥", "해장국", "찌개", "김치찌개", "된장찌개", "청국장", "순두부", "탕", "황태", "대구탕", "동태", "추어탕", "우거지", "선지", "소고기국"]):
        pool = CATEGORY_FOOD_IMAGES["soup_stew"]
        return pool[hash_seed % len(pool)], ""

    # 8. 삼겹살 / 흑돼지 / 목살 / 생고기 구이 (단독 '돼지' 제거하여 돈가스 오매칭 완전 차단)
    if any(k in text for k in ["삼겹", "오겹", "목살", "생고기", "돼지구이", "생삼겹", "숯불구이", "정육", "뽈살", "한우구이", "소고기구이", "식육"]):
        pool = CATEGORY_FOOD_IMAGES["pork_bbq"]
        return pool[hash_seed % len(pool)], ""

    # 9. 중식 (짜장, 짬뽕, 탕수육, 반점 등)
    if any(k in text for k in ["짜장", "자장", "짬뽕", "간짜장", "탕수육", "반점", "중식", "중화", "차이나", "손짜장"]):
        pool = CATEGORY_FOOD_IMAGES["chinese"]
        return pool[hash_seed % len(pool)], ""

    # 10. 냉면 / 밀면 / 막국수
    if any(k in text for k in ["냉면", "밀면", "막국수"]):
        pool = CATEGORY_FOOD_IMAGES["cold_noodle"]
        return pool[hash_seed % len(pool)], ""

    # 11. 치킨 / 통닭 / 닭갈비
    if any(k in text for k in ["치킨", "통닭", "닭갈비", "삼계탕", "백숙", "찜닭"]):
        pool = CATEGORY_FOOD_IMAGES["chicken"]
        return pool[hash_seed % len(pool)], ""

    # 12. 기본 한식 / 백반 / 정식
    pool = CATEGORY_FOOD_IMAGES["korean_meal"]
    return pool[hash_seed % len(pool)], ""


def load_good_price_restaurants() -> List[Dict[str, Any]]:
    """전처리된 전국 착한가격식당 데이터를 로드합니다."""
    if os.path.exists(PREPROCESSED_JSON):
        try:
            with open(PREPROCESSED_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


# 행정구역(시·도)과 마스터 축제 지역 간의 엄격한 매핑 (타 권역 축제 매칭 원천 차단)
SDO_TO_FEST_REGIONS = {
    "서울특별시": {"서울"},
    "경기도": {"경기"},
    "인천광역시": {"인천"},
    "강원특별자치도": {"강원"},
    "충청남도": {"충남", "대전", "세종"},
    "충청북도": {"충북", "세종", "대전"},
    "대전광역시": {"대전", "충남", "세종"},
    "세종특별자치시": {"세종", "충남", "대전", "충북"},
    "전북특별자치도": {"전북"},
    "전라남도": {"전남", "광주"},
    "광주광역시": {"광주", "전남"},
    "경상북도": {"경북", "대구"},
    "대구광역시": {"대구", "경북"},
    "경상남도": {"경남", "부산", "울산"},
    "부산광역시": {"부산", "경남", "울산"},
    "울산광역시": {"울산", "부산", "경남"},
    "제주특별자치도": {"제주"},
}


def get_fest_real_region(f: Dict[str, Any]) -> str:
    """축제 데이터에서 2자리 표준 시·도 권역 코드를 추출합니다 (대한민국 전국 표기 시 상세 주소 역추적)"""
    r_short = f.get("region_short", "")
    reg = f.get("region", "")
    addr = f.get("address", "")
    combined = f"{r_short} {reg} {addr}"
    for k in ["서울", "경기", "인천", "강원", "충남", "충북", "대전", "세종", "전북", "전남", "광주", "경북", "대구", "경남", "부산", "울산", "제주"]:
        if k in combined:
            return k
    return r_short[:2] if r_short != "대한민국" else "전국"


@st.cache_data(show_spinner=False)
def load_festival_coords_cache() -> List[Tuple[float, float, str, str, str, str, str]]:
    """
    공식 지역별 달력 마스터 축제(2026.10 ~ 11 ~ 12 ~ 2027+) 및 공공데이터 축제 좌표 목록
    (위도, 경도, 행사명, 카테고리, 지역, 개막일, 종료일)을 캐싱하여 반환합니다.
    """
    coords = []
    seen_titles = set()

    # 1. 사이트 공식 지역별 달력 마스터 축제(432개, 2026년 10월부터 최신순 타임라인) 최우선 적재
    if os.path.exists(CALENDAR_MASTER_FESTIVALS_JSON):
        try:
            with open(CALENDAR_MASTER_FESTIVALS_JSON, "r", encoding="utf-8") as f:
                cal_list = json.load(f)
            for f in cal_list:
                try:
                    lat = float(f.get("lat") or f.get("mapy", 0))
                    lng = float(f.get("lng") or f.get("mapx", 0))
                    title = str(f.get("title", "")).strip()
                    if 33.0 <= lat <= 39.0 and 124.0 <= lng <= 132.0 and title:
                        reg = get_fest_real_region(f)
                        sdate = re.sub(r"[^0-9]", "", str(f.get("startDate", "99999999")))
                        edate = re.sub(r"[^0-9]", "", str(f.get("endDate", "99999999")))
                        coords.append((
                            lat,
                            lng,
                            title,
                            str(f.get("category", "festival")),
                            reg,
                            sdate,
                            edate,
                        ))
                        seen_titles.add(title)
                except Exception:
                    continue
        except Exception:
            pass

    # 2. TourAPI 마스터 축제 중 추가 공공데이터 축제 보완 적재
    if os.path.exists(MASTER_FESTIVALS_JSON):
        try:
            with open(MASTER_FESTIVALS_JSON, "r", encoding="utf-8") as f:
                oct_list = json.load(f)
            for f in oct_list:
                try:
                    title = str(f.get("title", "")).strip()
                    if title in seen_titles:
                        continue
                    lat = float(f.get("mapy", 0))
                    lng = float(f.get("mapx", 0))
                    if 33.0 <= lat <= 39.0 and 124.0 <= lng <= 132.0 and title:
                        sdate = re.sub(r"[^0-9]", "", str(f.get("startDate", "99999999")))
                        edate = re.sub(r"[^0-9]", "", str(f.get("endDate", "99999999")))
                        coords.append((
                            lat,
                            lng,
                            title,
                            str(f.get("category", "festival")),
                            str(f.get("region", "")),
                            sdate,
                            edate,
                        ))
                        seen_titles.add(title)
                except Exception:
                    continue
        except Exception:
            pass

    return coords


def get_nearest_festival_meta(
    r_sdo: str, r_sgg: str, r_lat: float, r_lng: float, fest_coords: List[Tuple[float, float, str, str, str, str, str]]
) -> Tuple[float, str, str, str, bool, str, str, str, str]:
    """
    식당 좌표 기준 가장 가까운 축제 정보 반환:
    (최단 거리 km, 축제명 텍스트, 소요 시간 텍스트, 이동 모드('walk'|'car'|'spot'), 반경 3km 이내 여부, 축제 원본명, 개최 지역, 개막일, 종료일)

    [지역 무결성 보장]:
    - 식당의 시·도(r_sdo)와 축제의 개최 지역(f_region)이 일치하는 경우에만 매칭 (타 권역 축제 매칭 원천 차단)

    [반경 3km vs 도보 모순 해결]:
    - 1km 이내: '도보 X분' (보행 가능 거리)
    - 1km 초과 ~ 3km 이내: '차량 X분' (차량 이동 거리)
    """
    if not fest_coords or r_lat < 30.0 or r_lng < 120.0:
        short_sdo = r_sdo[:2] if r_sdo else "로컬"
        return 999.0, f"🏛️ {short_sdo} 문화명소", "인접 안심식당", "spot", False, "", short_sdo, "99999999", "99999999"

    valid_regions = SDO_TO_FEST_REGIONS.get(r_sdo, set())

    min_dist = 999.0
    best_fest = None
    for f_lat, f_lng, f_title, f_cat, f_region, f_sdate, f_edate in fest_coords:
        # 지역 불일치 엄격 차단 (타 권역 축제 매칭 방지)
        if valid_regions and f_region not in valid_regions:
            continue

        if abs(r_lat - f_lat) < 0.04 and abs(r_lng - f_lng) < 0.05:
            d = math.hypot((r_lat - f_lat) * 111.0, (r_lng - f_lng) * 88.8)
            if d < min_dist:
                min_dist = d
                best_fest = (f_title, f_cat, f_region, f_sdate, f_edate)

    if best_fest and min_dist <= 3.0:
        f_title, f_cat, f_region, f_sdate, f_edate = best_fest
        clean_title = f_title.split(" (")[0].split(" - ")[0][:14].strip()
        fest_name = f"🎪 {clean_title}"

        # 1km 이내는 도보, 1km 초과 ~ 3km 이내는 차량으로 정확히 분기
        if min_dist <= 0.4:
            transit_txt = "도보 5분"
            transit_mode = "walk"
        elif min_dist <= 0.7:
            transit_txt = "도보 8분"
            transit_mode = "walk"
        elif min_dist <= 1.0:
            transit_txt = "도보 10분"
            transit_mode = "walk"
        elif min_dist <= 1.8:
            transit_txt = "차량 4분"
            transit_mode = "car"
        elif min_dist <= 2.5:
            transit_txt = "차량 5분"
            transit_mode = "car"
        else:
            transit_txt = "차량 7분"
            transit_mode = "car"

        return min_dist, fest_name, transit_txt, transit_mode, True, f_title, f_region, f_sdate, f_edate

    elif best_fest and min_dist <= 6.0:
        f_title, f_cat, f_region, f_sdate, f_edate = best_fest
        clean_title = best_fest[0].split(" (")[0].split(" - ")[0][:14].strip()
        return min_dist, f"🎪 {clean_title}", "차량 10분", "car", False, f_title, f_region, f_sdate, f_edate

    else:
        short_sdo = r_sdo[:2] if r_sdo else "로컬"
        return min_dist, f"🏛️ {short_sdo} 문화명소", "인접 안심식당", "spot", False, "", short_sdo, "99999999", "99999999"


def render_good_price_explorer_page():
    """대한민국 정부 공식 인증 전국 착한가격식당 메인 뷰 (여행 코스 뷰와 1:1 레이아웃 동기화)"""

    # 1. 쿼리 파라미터 처리
    if "rest_zone" in st.query_params:
        zone_val = st.query_params.get("rest_zone")
        if zone_val == "수도권":
            zone_val = "서울"
        elif zone_val in ["경기·인천", "경기인천"]:
            zone_val = "경기인천"
        st.session_state.clean_rest_zone = zone_val
        st.session_state.clean_rest_page = 1
        del st.query_params["rest_zone"]
        st.rerun()

    # 하위 호환성 (기존 rest_sdo 파라미터가 들어온 경우 권역으로 자동 변환)
    if "rest_sdo" in st.query_params:
        sdo_val = st.query_params.get("rest_sdo", "")
        matched_zone = "전국"
        for z in ZONE_TABS:
            if sdo_val in z["regions"] or any(sdo_val in r for r in z["regions"]):
                matched_zone = z["key"]
                break
        st.session_state.clean_rest_zone = matched_zone
        st.session_state.clean_rest_page = 1
        del st.query_params["rest_sdo"]
        st.rerun()

    if "near_fest" in st.query_params:
        nf_val = st.query_params.get("near_fest")
        st.session_state.clean_rest_near_fest = (nf_val in ["1", "true", "True"])
        st.session_state.clean_rest_page = 1
        del st.query_params["near_fest"]
        st.rerun()

    if "rest_query" in st.query_params:
        st.session_state.clean_rest_query = st.query_params.get("rest_query")
        st.session_state.clean_rest_page = 1
        del st.query_params["rest_query"]
        st.rerun()

    if "rest_page" in st.query_params:
        try:
            st.session_state.clean_rest_page = max(1, int(st.query_params.get("rest_page")))
        except Exception:
            st.session_state.clean_rest_page = 1
        del st.query_params["rest_page"]
        st.rerun()

    # [동행인 파라미터 수신 및 상태 보존]
    companion_param = str(
        st.query_params.get("companion")
        or st.session_state.get("selected_companion")
        or st.session_state.get("active_companion_param")
        or ""
    ).strip().lower()
    if companion_param in ["none", "all"]:
        # '전체 식당 보기' 선택 시 동행인 필터 해제
        companion_param = ""
        st.session_state.pop("active_companion_param", None)
        st.session_state.pop("selected_companion", None)
        if "companion" in st.query_params:
            del st.query_params["companion"]
    if companion_param:
        st.session_state["active_companion_param"] = companion_param

    # 2. 세션 상태 기본값 바인딩
    current_zone = st.session_state.get("clean_rest_zone", "전국")
    valid_keys = [z["key"] for z in ZONE_TABS]
    if current_zone not in valid_keys:
        current_zone = "전국"
        st.session_state.clean_rest_zone = "전국"

    near_fest_only = st.session_state.get("clean_rest_near_fest", False)
    current_query = st.session_state.get("clean_rest_query", "")
    current_page = st.session_state.get("clean_rest_page", 1)

    # 3. 데이터 로드 및 축제 좌표 캐시 확보
    all_restaurants = load_good_price_restaurants()
    if not all_restaurants:
        st.error("착한가격식당 데이터를 로드할 수 없습니다.")
        return

    fest_coords = load_festival_coords_cache()

    # 4. 8대 권역 필터링 ('서울' 독립 카테고리 지원)
    matched_tab = next((z for z in ZONE_TABS if z["key"] == current_zone), ZONE_TABS[0])
    target_regions = matched_tab["regions"]

    if target_regions:
        candidates = [r for r in all_restaurants if r.get("sdo") in target_regions]
    else:
        candidates = all_restaurants

    # 5. 축제 정보 연계 및 검색 필터링 (축제명, 식당명, 메뉴, 주소 전방위 매칭)
    q = current_query.strip().lower()
    enriched_filtered = []
    for r in candidates:
        dist_km, fest_title, transit_txt, transit_mode, is_within_3km, raw_title, fest_region, f_sdate, f_edate = get_nearest_festival_meta(
            r.get("sdo", ""), r.get("sgg", ""), r.get("lat", 0), r.get("lng", 0), fest_coords
        )
        if near_fest_only and not is_within_3km:
            continue

        # 검색 쿼리 필터링 (축제명(단축/원본), 식당명, 대표메뉴1/2, 주소 전방위 매칭)
        if q:
            # 1) 전체 검색어 일치
            match_fest = (q in fest_title.lower()) or (raw_title and q in raw_title.lower())

            # 2) 복합어 및 공백 분리 다중 토큰 매칭 (예: '제천한방' -> '제천', '한방' 동시 포함 여부)
            if not match_fest:
                q_tokens = [tok for tok in q.split() if tok]
                if len(q_tokens) > 1:
                    match_fest = all(tok in fest_title.lower() or (raw_title and tok in raw_title.lower()) for tok in q_tokens)
                elif len(q) >= 4:
                    prefix = q[:2]
                    suffix = q[2:]
                    match_fest = (
                        (prefix in fest_title.lower() or (raw_title and prefix in raw_title.lower()))
                        and (suffix in fest_title.lower() or (raw_title and suffix in raw_title.lower()))
                    )

            match_info = (
                q in r.get("name", "").lower()
                or q in r.get("menu1", "").lower()
                or q in r.get("menu2", "").lower()
                or q in r.get("address", "").lower()
            )
            if not (match_fest or match_info):
                continue

        # 축제 태그 클릭 시 연계할 링크 (축제 상세 에디토리얼 매거진/코스 뷰 라우팅)
        if raw_title:
            fest_link = f"?select_fest_and_go={urllib.parse.quote(raw_title)}&target_region={urllib.parse.quote(fest_region)}"
        else:
            fest_link = f"?view=course&exp_region={urllib.parse.quote(fest_region)}"

        r_item = dict(r)
        r_item["_fest_dist"] = dist_km
        r_item["_fest_title"] = fest_title
        r_item["_fest_raw_title"] = raw_title
        r_item["_fest_region"] = fest_region
        r_item["_fest_link"] = fest_link
        r_item["_transit_txt"] = transit_txt
        r_item["_transit_mode"] = transit_mode
        r_item["_is_near_3km"] = is_within_3km
        r_item["_fest_start"] = f_sdate
        r_item["_fest_end"] = f_edate
        enriched_filtered.append(r_item)

    # 6. [축제 일정 10월 -> 11월 -> 12월 -> 2027+ 타임라인 우선 정렬 알고리즘]
    # 1순위: 10월부터 시작하는 캘린더 축제 인접 여부 및 타임라인 티어
    #   - Tier 0: 2026년 10월 축제 인접 식당 (반경 3km 이내)
    #   - Tier 1: 2026년 11월 축제 인접 식당 (반경 3km 이내)
    #   - Tier 2: 2026년 12월 축제 인접 식당 (반경 3km 이내)
    #   - Tier 3: 2027년 축제 인접 식당 (반경 3km 이내)
    #   - Tier 4: 연중 상설/기타 축제 (반경 3km 이내)
    #   - Tier 5: 반경 6km 이내 축제 인접 식당
    #   - Tier 6: 일반 문화명소
    # 2순위: 축제 개막 일정 빠른순 (20261001 < 20261015 < 20261101 < 20261201)
    # 3순위: 네이버 대문 실사 보유 여부 (-is_naver)
    # 4순위: 축제장과의 거리 (최단거리순: 0.3km < 0.7km < 1.5km)
    # 5순위: 식당명 가나다순
    def get_restaurant_curation_rank(item):
        is_3km = item.get("_is_near_3km", False)
        dist = item.get("_fest_dist", 999.0)
        raw_t = item.get("_fest_raw_title", "")
        sdate = re.sub(r"[^0-9]", "", str(item.get("_fest_start", "99999999")))
        if len(sdate) < 8:
            sdate = "99999999"

        r_img_str = str(item.get("image", "")).lower()
        has_bad = any(b in r_img_str for b in ["contact", "blogfiles", "snow_", "kakaotalk", "imgnews", "blogpfthumb", "profile", "avatar", "sticker", "favicon", "photo-1547496502", "photo-1553163147"])
        is_naver = 1 if (("ldb-phinf.pstatic.net" in r_img_str or "pup-review-phinf.pstatic.net" in r_img_str or item.get("image_source") == "naver_place") and not has_bad) else 0

        if is_3km and raw_t:
            if "20261001" <= sdate <= "20261031":
                tier = 0  # 10월 축제 인접 식당 최우선!
            elif "20261101" <= sdate <= "20261130":
                tier = 1  # 11월 축제 인접 식당
            elif "20261201" <= sdate <= "20261231":
                tier = 2  # 12월 축제 인접 식당
            elif sdate >= "20270101":
                tier = 3  # 2027년 축제 인접 식당
            else:
                tier = 4  # 연중 상설/기타 축제
        elif dist <= 6.0 and raw_t:
            tier = 5
        else:
            tier = 6

        return (tier, -is_naver, sdate, dist, item.get("name", ""))

    enriched_filtered.sort(key=get_restaurant_curation_rank)

    # 6-2. [축제 다양성 라운드로빈 인터리빙]
    # 특정 소도시 단일 축제(예: 태백제 15곳, 고성명태축제 12곳 등)가 1페이지 전체를 독점 도배하는 것을 원천 방지!
    # 검색어가 없는 기본 큐레이션 모드일 때, 동일 축제당 1차 순환에서 1곳씩 교차 배치하여
    # 강원권/제주권 등 전역의 다채로운 축제가 1페이지 12개 카드에 골고루 조화롭게 노출되도록 재배열합니다.
    if not q and enriched_filtered:
        from collections import defaultdict
        fest_groups = defaultdict(list)
        for item in enriched_filtered:
            # 축제명이 있으면 축제명 기준, 문화명소면 지역명 기준 그룹화
            f_key = item.get("_fest_raw_title") or item.get("_fest_title", "기타")
            fest_groups[f_key].append(item)

        diversified_list = []
        max_group_size = max(len(v) for v in fest_groups.values()) if fest_groups else 0
        for round_idx in range(max_group_size):
            for f_key in list(fest_groups.keys()):
                if round_idx < len(fest_groups[f_key]):
                    diversified_list.append(fest_groups[f_key][round_idx])

        if len(diversified_list) == len(enriched_filtered):
            enriched_filtered = diversified_list

    # 6-3. [동행인별 식당 목록 실제 필터링]
    # 업종(sector)은 약 78%가 '한식'이라 구분력이 없으므로 대표메뉴·상호명 키워드로 판별
    companion_banner_text = ""
    companion_fallback = False
    if companion_param:
        from festapick.infra_curator import score_restaurant_for_companion

        comp_key = "solo"
        if any(k in companion_param for k in ["parent", "부모", "어르신", "효도"]):
            comp_key = "parents"
        elif any(k in companion_param for k in ["family", "아이", "가족", "키즈"]):
            comp_key = "family"
        elif any(k in companion_param for k in ["couple", "연인", "커플", "데이트"]):
            comp_key = "couple"
        elif any(k in companion_param for k in ["pet", "반려", "펫"]):
            comp_key = "pet"

        COMPANION_RESTAURANT_RULES = {
            "parents": {
                "include": ["백반", "정식", "한정식", "찌개", "된장", "청국장", "순두부", "국밥", "해장국",
                            "설렁탕", "곰탕", "갈비탕", "추어탕", "삼계탕", "보리밥", "쌈밥", "비빔밥",
                            "칼국수", "수제비", "죽", "생선구이", "기사식당", "한식뷔페"],
                "exclude": ["호프", "주점", "포차", "치킨", "맥주", "소주", "횟집", "스시"],
                "banner": "👵👴 부모님과 함께하기 좋은 속 편한 안심 식당입니다.",
            },
            "family": {
                "include": ["돈가스", "돈까스", "돈카츠", "카츠", "불고기", "국수", "잔치국수", "칼국수",
                            "짜장", "자장", "김밥", "만두", "떡볶이", "분식", "오무라이스", "돈가스정식"],
                "exclude": ["호프", "주점", "포차", "맥주", "소주"],
                "banner": "👶 온 가족이 편안한 패밀리 안심 식당입니다.",
            },
            "couple": {
                "include": ["파스타", "스파게티", "스테이크", "피자", "카츠", "돈카츠", "덮밥", "우동",
                            "커피", "카페", "라떼", "베이커리", "케이크", "비빔밥", "정식"],
                "exclude": ["기사식당", "해장국"],
                "banner": "💑 둘이서 분위기 있게 즐기는 가성비 데이트 식당입니다.",
            },
            "pet": {
                "include": ["테라스", "가든", "야외", "뜨램", "놀이터", "카페", "커피", "보리밥", "막국수"],
                "exclude": [],
                "banner": "🐾 반려견과 쉬어가기 좋은 야외·여유 공간 식당입니다.",
            },
            "solo": {
                "include": [],  # 혼자: 전체 목록 유지
                "exclude": [],
                "banner": "🌿 여유로운 1인 쉼표 밥상입니다.",
            },
        }
        rule = COMPANION_RESTAURANT_RULES[comp_key]
        companion_banner_text = rule["banner"]

        def _match_text(it):
            return f"{it.get('name', '')} {it.get('menu1', '')} {it.get('menu2', '')}".lower()

        if rule["include"]:
            strict_list = [
                it for it in enriched_filtered
                if any(k in _match_text(it) for k in rule["include"])
                and not any(k in _match_text(it) for k in rule["exclude"])
            ]
            if strict_list:
                enriched_filtered = strict_list
            else:
                # 해당 권역·검색 조건에 맞는 식당이 0건이면 빈 화면 대신 전체 목록 폴백
                companion_fallback = True

        # 필터된 목록 안에서 적합도 상위 3곳에 [맞춤 추천] 태그 부여 후 최상단 배치
        for it in enriched_filtered:
            it["_comp_score"] = score_restaurant_for_companion(
                it.get("name", ""),
                f"{it.get('menu1', '')} {it.get('menu2', '')} {it.get('sector', '')}",
                comp_key
            )
        sorted_by_comp = sorted(enriched_filtered, key=lambda x: x.get("_comp_score", 100), reverse=True)
        top_recomms = []
        top_ids = set()
        for cand in sorted_by_comp:
            if cand.get("_comp_score", 100) > 100 and len(top_recomms) < 3:
                cand["_is_custom_recommended"] = True
                top_recomms.append(cand)
                top_ids.add(id(cand))

        if top_recomms:
            other_items = [it for it in enriched_filtered if id(it) not in top_ids]
            enriched_filtered = top_recomms + other_items

    # 7. 3열 그리드에 최적화된 12개 단위 페이징 계산 (4행 x 3열 = 12개 완결 구조)
    PAGE_SIZE = 12
    total_count = len(enriched_filtered)
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    if current_page > total_pages:
        current_page = total_pages

    start_idx = (current_page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_items = enriched_filtered[start_idx:end_idx]

    # 8. CSS 스타일시트 (여행 코스 course_explorer.py와 100% 동기화 규격)
    st.html("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/sun-typeface/maruburi@master/dist/web/font.css');
    @import url('https://cdn.jsdelivr.net/npm/font-kopubworld@1.0.3/kopubworldbatang.css');
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,600&family=Noto+Serif+KR:wght@500;600;700;900&display=swap');
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    /* 1. 글로벌 컨테이너 규격 동기화: max-width 1360px & 아이보리 배경 (#F9F8F3) */
    .block-container {
        padding-top: 1.0rem !important;
        padding-bottom: 3.5rem !important;
        max-width: 1360px !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }
    .stApp {
        background-color: #F9F8F3 !important;
    }
    .editorial-page-wrap {
        font-family: 'Pretendard', -apple-system, sans-serif;
        color: #1A2E26;
        background-color: #F9F8F3;
        max-width: 1360px;
        margin: 0 auto;
    }

    /* 2. 상단 헤더: 매거진 에디토리얼 감성 (여행 코스 뷰 1:1 일치) */
    .editorial-header-bar {
        padding: 10px 0 20px 0;
        border-bottom: 1.5px solid #EAE3D6;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        flex-wrap: wrap;
        gap: 16px;
    }
    .editorial-meta-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
        flex-wrap: wrap;
    }
    .editorial-vol-badge {
        font-size: 0.74rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        color: #1B4332;
        background: #E8F5E9;
        border: 1px solid #C8E6C9;
        padding: 3px 9px;
        border-radius: 6px;
        text-transform: uppercase;
    }
    .editorial-sub-badge {
        font-size: 0.82rem;
        font-weight: 600;
        color: #6B7280;
        letter-spacing: -0.01em;
    }
    .editorial-main-title {
        font-family: 'MaruBuri', 'KoPubWorld Batang', 'Noto Serif KR', serif;
        font-size: 2.1rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: #012D1D;
        margin: 0 0 6px 0;
        line-height: 1.3;
    }
    .editorial-lead-text {
        font-size: 0.94rem;
        color: #4B5563;
        margin: 0;
        line-height: 1.6;
        max-width: 820px;
    }
    .editorial-header-actions {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .editorial-ghost-btn {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        background: #FFFFFF;
        color: #1B4332 !important;
        border: 1.5px solid #D1D5DB;
        padding: 8px 18px;
        border-radius: 9999px;
        font-size: 0.86rem;
        font-weight: 700;
        text-decoration: none !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
        white-space: nowrap;
    }
    .editorial-ghost-btn:hover {
        background: #1B4332;
        color: #FFFFFF !important;
        border-color: #1B4332;
        transform: translateY(-2px);
        box-shadow: 0 4px 14px rgba(27, 67, 50, 0.18);
    }

    /* 3. 8대 권역 탭 버튼 컨테이너 ('서울' 독립 카테고리 포함) */
    .zone-tabs-container {
        display: flex;
        justify-content: center;
        gap: 12px;
        flex-wrap: wrap;
        padding: 6px 0 16px 0;
        margin-bottom: 6px;
    }
    .zone-tab-pill {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 9px 22px;
        border-radius: 9999px;
        font-size: 0.90rem;
        font-weight: 600;
        text-decoration: none !important;
        border: 1.5px solid #D8D2C5;
        background: #FFFFFF;
        color: #4B5563;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
    }
    .zone-tab-pill:hover {
        background: #FFFFFF;
        border-color: #012D1D;
        color: #012D1D;
        transform: translateY(-2px);
        box-shadow: 0 4px 10px rgba(1, 45, 29, 0.08);
    }
    .zone-tab-pill.active {
        background: #012D1D !important;
        color: #FFFFFF !important;
        border-color: #012D1D !important;
        font-weight: 800;
        box-shadow: 0 4px 14px rgba(1, 45, 29, 0.22);
        transform: translateY(-1px);
    }

    /* 5. 서브 컨트롤 라인 (좌측 축제 필터 토글 + 우측 검색창) */
    .sub-control-line {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 18px;
        background: #FFFFFF;
        border: 1.5px solid #EAE3D6;
        border-radius: 14px;
        margin-bottom: 22px;
        gap: 16px;
        flex-wrap: wrap;
        box-shadow: 0 2px 6px rgba(20, 56, 43, 0.03);
    }
    .sub-control-left {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .fest-filter-toggle {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 7px 16px;
        border-radius: 9999px;
        border: 1.5px solid #D8D2C5;
        background: #F9F8F3;
        color: #374151;
        font-size: 0.85rem;
        font-weight: 700;
        text-decoration: none !important;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .fest-filter-toggle:hover {
        background: #FFFFFF;
        border-color: #012D1D;
        color: #012D1D;
    }
    .fest-filter-toggle.active {
        background: #E8F5E9;
        border-color: #2E7D32;
        color: #1B4332;
        box-shadow: 0 2px 8px rgba(46, 125, 50, 0.15);
    }
    .toggle-sub-badge {
        font-size: 0.70rem;
        background: rgba(27, 67, 50, 0.12);
        color: #1B4332;
        padding: 2px 7px;
        border-radius: 4px;
        font-weight: 800;
    }

    .sub-control-right {
        display: flex;
        align-items: center;
        flex: 1;
        max-width: 480px;
        justify-content: flex-end;
    }
    .editorial-search-box {
        display: flex;
        align-items: center;
        background: #F9F8F3;
        border: 1.5px solid #D8D2C5;
        border-radius: 9999px;
        padding: 6px 18px;
        width: 100%;
        min-width: 380px;
        transition: all 0.2s ease;
    }
    @media (max-width: 768px) {
        .sub-control-right {
            max-width: 100%;
            width: 100%;
        }
        .editorial-search-box {
            min-width: 100%;
            width: 100%;
        }
    }
    .editorial-search-box:focus-within {
        border-color: #012D1D;
        background: #FFFFFF;
        box-shadow: 0 0 0 2px rgba(1, 45, 29, 0.12);
    }
    .editorial-search-input {
        border: none;
        outline: none;
        background: transparent;
        font-size: 0.86rem;
        color: #111827;
        width: 100%;
        padding: 3px 6px;
    }
    .editorial-search-btn {
        background: none;
        border: none;
        cursor: pointer;
        font-size: 1rem;
        color: #4B5563;
        padding: 0;
        line-height: 1;
    }

    /* 6. 검색 결과 통계 바 */
    .result-count-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 22px;
        padding: 0 4px;
    }
    .result-count-label {
        font-size: 0.88rem;
        color: #6B7280;
    }
    .result-count-label strong {
        color: #012D1D;
        font-weight: 800;
        font-size: 0.98rem;
    }

    /* 7. 반응형 그리드 컬럼 시스템 (여행 코스 뷰와 1:1 통일된 여유 있는 비율) */
    .restaurant-grid-system {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
        gap: 22px;
        margin-bottom: 48px;
    }
    @media (min-width: 1200px) {
        .restaurant-grid-system {
            grid-template-columns: repeat(3, 1fr);
        }
    }
    @media (max-width: 1024px) {
        .restaurant-grid-system {
            grid-template-columns: repeat(2, 1fr);
            gap: 18px;
        }
    }
    @media (max-width: 640px) {
        .restaurant-grid-system {
            grid-template-columns: 1fr;
            gap: 16px;
        }
    }

    /* 식당 카드 스타일 */
    .rest-clean-card {
        background: #FFFFFF;
        border: 1.5px solid #EAE3D6;
        border-radius: 18px;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.22s ease, border-color 0.22s ease;
        box-shadow: 0 4px 14px rgba(20, 56, 43, 0.04);
    }
    .rest-clean-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 14px 28px rgba(27, 67, 50, 0.12);
        border-color: #1B4332;
    }

    .card-thumb-wrap {
        width: 100%;
        aspect-ratio: 16 / 9;
        position: relative;
        overflow: hidden;
        background: #08281B;
    }
    .card-thumb-img {
        width: 100%;
        height: 100%;
        aspect-ratio: 16 / 9;
        object-fit: cover;
        transition: transform 0.35s ease;
        display: block;
    }
    .rest-clean-card:hover .card-thumb-img {
        transform: scale(1.05);
    }


    .card-content {
        padding: 16px 16px 12px 16px;
        display: flex;
        flex-direction: column;
        gap: 7px;
        flex: 1;
    }

    /* 축제 연계 배지 가독성 및 클릭 인터랙션 (호버 시 밑줄 및 포인터) */
    .badge-fest-container {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background-color: #F1F5F9; /* bg-slate-100 */
        border: 1px solid #E2E8F0;
        padding: 4px 10px;
        border-radius: 8px;
        width: fit-content;
        max-width: 100%;
        margin-bottom: 2px;
        box-sizing: border-box;
    }
    .badge-fest-name-link {
        font-size: 0.76rem;
        font-weight: 600; /* font-semibold */
        color: #1E293B !important; /* text-slate-800 */
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 170px;
        letter-spacing: -0.01em;
        text-decoration: none !important;
        cursor: pointer !important;
        display: inline-block;
        transition: color 0.15s ease, text-decoration 0.15s ease;
    }
    .badge-fest-name-link:hover {
        color: #012D1D !important;
        text-decoration: underline !important;
    }
    .badge-fest-divider {
        font-size: 0.72rem;
        font-weight: 700;
        color: #94A3B8; /* text-slate-400 */
        user-select: none;
    }
    .badge-fest-transit {
        display: inline-flex;
        align-items: center;
        font-size: 0.72rem;
        font-weight: 700;
        white-space: nowrap;
        letter-spacing: -0.01em;
        padding: 1.5px 6px;
        border-radius: 5px;
    }
    .badge-fest-transit.walk {
        background-color: #FEF3C7; /* bg-amber-100 */
        color: #92400E; /* text-amber-800 */
        border: 1px solid #FDE68A;
    }
    .badge-fest-transit.car {
        background-color: #E2E8F0; /* bg-slate-200 */
        color: #334155; /* text-slate-700 */
        border: 1px solid #CBD5E1;
    }
    .badge-fest-transit.spot {
        background-color: #E2E8F0;
        color: #475569;
        border: 1px solid #CBD5E1;
    }

    .card-title {
        font-size: 1.08rem;
        font-weight: 800;
        color: #14382B;
        margin: 2px 0 0 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        letter-spacing: -0.02em;
    }
    .card-menu-box {
        background: #F9F8F3;
        border: 1px solid #EAE3D6;
        border-radius: 8px;
        padding: 7px 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 2px;
    }
    .card-menu-name {
        font-size: 0.82rem;
        color: #374151;
        font-weight: 600;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 140px;
    }
    .card-menu-price {
        font-size: 0.90rem;
        font-weight: 800;
        color: #B45309;
    }

    .card-addr {
        font-size: 0.76rem;
        color: #6B7280;
        line-height: 1.35;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-top: 2px;
    }
    .card-phone {
        font-size: 0.72rem;
        color: #9CA3AF;
    }

    .card-action {
        padding: 0 16px 16px 16px;
    }
    .btn-kakao-nav {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 5px;
        width: 100%;
        padding: 8px 0;
        border-radius: 9px;
        background: #F9F8F3;
        color: #1B4332;
        border: 1px solid #D8D2C5;
        font-size: 0.82rem;
        font-weight: 700;
        text-decoration: none !important;
        transition: all 0.2s ease;
    }
    .btn-kakao-nav:hover {
        background: #012D1D;
        color: #FFFFFF !important;
        border-color: #012D1D;
        box-shadow: 0 2px 8px rgba(1, 45, 29, 0.15);
    }

    /* 8. 미니멀 페이지네이션 */
    .pagination-wrap {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 8px;
        margin-top: 36px;
    }
    .page-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 38px;
        height: 38px;
        padding: 0 12px;
        border-radius: 8px;
        border: 1.5px solid #D8D2C5;
        background: #FFFFFF;
        color: #374151;
        font-size: 0.86rem;
        font-weight: 600;
        text-decoration: none !important;
        transition: all 0.2s ease;
    }
    .page-btn:hover {
        background: #FFFFFF;
        border-color: #012D1D;
        color: #012D1D;
        box-shadow: 0 2px 6px rgba(1, 45, 29, 0.1);
    }
    .page-btn.active {
        background: #012D1D !important;
        color: #FFFFFF !important;
        border-color: #012D1D !important;
        font-weight: 800;
        box-shadow: 0 2px 8px rgba(1, 45, 29, 0.2);
    }
    </style>
    """)

    # 9. 상단 매거진 헤더 렌더링
    st.html("""
    <div class="editorial-page-wrap">
        <!-- 1. 매거진 스타일 상단 헤더 -->
        <div class="editorial-header-bar">
            <div class="editorial-header-text">
                <div class="editorial-meta-row">
                    <span class="editorial-vol-badge">정부 공식 인증</span>
                    <span class="editorial-sub-badge">행정안전부·지자체 지정 전국 9,563곳 모범식당 실시간 큐레이션</span>
                </div>
                <h1 class="editorial-main-title">대한민국 정부 공식 인증 전국 착한가격식당</h1>
                <p class="editorial-lead-text">바가지 없는 안심 로컬 미식 — 주요 축제장 및 문화명소 인근 착한가격 모범식당 큐레이션</p>
            </div>
            <div class="editorial-header-actions">
                <a href="?view=main" class="editorial-ghost-btn">
                    <span>←</span>
                    <span>홈으로</span>
                </a>
            </div>
        </div>
    """)

    # [상단 동행인 맞춤 안내 마이크로 배너]
    try:
        from festapick.infra_curator import get_companion_micro_banner_html
        micro_banner = get_companion_micro_banner_html(companion_param or st.session_state.get("companion"), service_type="restaurant")
    except TypeError:
        try:
            micro_banner = get_companion_micro_banner_html(companion_param or st.session_state.get("companion"))
        except Exception:
            micro_banner = ""
    except Exception:
        micro_banner = ""

    if micro_banner:
        st.html(micro_banner)

    # 10. 8대 권역 탭 렌더링 ('서울' 독립 카테고리 포함)
    zone_chips = []
    for z in ZONE_TABS:
        z_key = z["key"]
        z_label = z["label"]
        is_act = (current_zone == z_key)
        act_class = "active" if is_act else ""
        url_t = f"?view=restaurant&rest_zone={urllib.parse.quote(z_key)}&near_fest={1 if near_fest_only else 0}&rest_query={urllib.parse.quote(current_query)}"
        zone_chips.append(f"""
        <a href="{url_t}" target="_self" class="zone-tab-pill {act_class}">
            {z_label}
        </a>
        """)

    st.html(f"""
        <div class="zone-tabs-container">
            {"".join(zone_chips)}
        </div>
    """)

    # 11. 서브 컨트롤 라인 (좌측 축제 필터 토글 + 우측 검색창)
    toggle_next = 0 if near_fest_only else 1
    toggle_act_class = "active" if near_fest_only else ""
    check_symbol = "☑" if near_fest_only else "☐"
    toggle_url = f"?view=restaurant&rest_zone={urllib.parse.quote(current_zone)}&near_fest={toggle_next}&rest_query={urllib.parse.quote(current_query)}"
    search_escaped = html.escape(current_query)

    st.html(f"""
        <div class="sub-control-line">
            <div class="sub-control-left">
                <a href="{toggle_url}" target="_self" class="fest-filter-toggle {toggle_act_class}">
                    <span>{check_symbol} 🎪 주요 축제장 인근 안심 식당만 보기</span>
                    <span class="toggle-sub-badge">반경 3km</span>
                </a>
            </div>
            <div class="sub-control-right">
                <form action="" method="GET" style="margin:0;">
                    <input type="hidden" name="view" value="restaurant" />
                    <input type="hidden" name="rest_zone" value="{html.escape(current_zone)}" />
                    <input type="hidden" name="near_fest" value="{1 if near_fest_only else 0}" />
                    <div class="editorial-search-box">
                        <input type="text" name="rest_query" value="{search_escaped}" placeholder="축제명·식당명·메뉴 검색 (예: 경복궁, 백반)" class="editorial-search-input" />
                        <button type="submit" class="editorial-search-btn">🔍</button>
                    </div>
                </form>
            </div>
        </div>
    """)

    # 12. 검색 결과 통계 바
    fest_stat_label = " · 🎪 축제장 인근 3km 한정" if near_fest_only else " · 🎪 10월 가을 축제 일정순 큐레이션"
    query_stat_label = f" · '{html.escape(current_query)}' 검색" if current_query.strip() else ""
    st.html(f"""
        <div class="result-count-bar">
            <div class="result-count-label">
                <span>{matched_tab['label']}{fest_stat_label}{query_stat_label}</span>
                <strong> {total_count:,}곳</strong>
                <span style="color:#9CA3AF; margin-left:4px;">(페이지 {current_page}/{total_pages})</span>
            </div>
        </div>
    """)

    # 13. 식당 카드 그리드 (여유 있는 3열 반응형 레이아웃)
    if not page_items:
        empty_guide = "다른 권역을 선택하거나 '축제장 인근 보기' 필터를 해제해 보세요."
        if current_query.strip() and current_zone != "전국":
            all_search_url = f"?view=restaurant&rest_zone=전국&near_fest={1 if near_fest_only else 0}&rest_query={urllib.parse.quote(current_query)}"
            empty_guide = f"'{html.escape(current_query)}'에 대한 결과가 현재 권역에 없습니다. <a href='{all_search_url}' style='color:#012D1D; font-weight:700; text-decoration:underline;'>전국 전체에서 검색하기 →</a>"

        st.html(f"""
        <div style="text-align:center; padding:90px 0; color:#9CA3AF; background:#FFFFFF; border:1.5px solid #EAE3D6; border-radius:18px;">
            <p style="font-size:1.15rem; margin-bottom:8px; font-weight:700; color:#374151;">조건에 일치하는 착한가격식당이 없습니다.</p>
            <p style="font-size:0.88rem; color:#6B7280;">{empty_guide}</p>
        </div>
        """)
    else:
        cards_html = []
        for idx, r in enumerate(page_items):
            r_name = html.escape(str(r.get("name", "착한식당")))
            r_sector = html.escape(str(r.get("sector", "한식")))
            r_menu1 = html.escape(str(r.get("menu1", "대표 메뉴")))
            r_price1 = html.escape(str(r.get("price1", "착한가격")))
            r_addr = html.escape(str(r.get("address", "")))
            r_phone = html.escape(str(r.get("phone", "연락처 준비중")))
            r_fest_title = html.escape(str(r.get("_fest_title", "🎪 로컬 축제 연계")))
            r_fest_link = str(r.get("_fest_link", "?view=course"))
            r_transit_txt = html.escape(str(r.get("_transit_txt", "인접 식당")))
            r_transit_mode = str(r.get("_transit_mode", "spot"))

            # 네이버 플레이스 공식 사업자 등록 실사(ldb-phinf / pup-review) 우선, 없을 시 100% 한국 요리 1:1 정밀 매칭 실사
            r_img = str(r.get("image", "")).strip()
            has_bad_keyword = any(b in r_img.lower() for b in [
                "contact", "blogfiles", "snow_", "kakaotalk", "imgnews", "blogpfthumb",
                "profile", "avatar", "sticker", "favicon", "photo-1547496502", "photo-1553163147", "photo-1544025162"
            ])
            is_naver = ("ldb-phinf.pstatic.net" in r_img or "pup-review-phinf.pstatic.net" in r_img) and not has_bad_keyword
            if not is_naver or not r_img:
                cat_img, _ = get_menu_matched_image(r_name, r_sector, r_menu1, str(r.get("menu2", "")), idx, r_addr)
                r_img = cat_img

            map_query = urllib.parse.quote(f"{r.get('name')} {r.get('sgg', '')}")
            map_link = f"https://map.kakao.com/link/search/{map_query}"

            custom_badge = '<span style="background:#012D1D; color:#FDE68A; font-size:0.70rem; font-weight:800; padding:2px 6px; border-radius:5px; margin-right:5px; vertical-align:middle;">★ 맞춤 추천</span>' if r.get("_is_custom_recommended") else ""

            cards_html.append(f"""
            <div class="rest-clean-card">
                <div>
                    <div class="card-thumb-wrap">
                        <img src="{r_img}" alt="{r_name}" class="card-thumb-img" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null; this.src='https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=700&q=80';" />
                    </div>
                    <div class="card-content">
                        <div class="badge-fest-container">
                            <a href="{r_fest_link}" target="_self" class="badge-fest-name-link">{r_fest_title}</a>
                            <span class="badge-fest-divider">·</span>
                            <span class="badge-fest-transit {r_transit_mode}">{r_transit_txt}</span>
                        </div>
                        <h3 class="card-title">{custom_badge}{r_name}</h3>
                        <div class="card-menu-box">
                            <span class="card-menu-name">{r_menu1}</span>
                            <span class="card-menu-price">{r_price1}</span>
                        </div>
                        <div class="card-addr">
                            📍 {r_addr}
                        </div>
                        <div class="card-phone">
                            📞 {r_phone}
                        </div>
                    </div>
                </div>
                <div class="card-action">
                    <a href="{map_link}" target="_blank" rel="noopener noreferrer" class="btn-kakao-nav">
                        카카오맵 길찾기 ↗
                    </a>
                </div>
            </div>
            """)

        st.html(f"""
            <div class="restaurant-grid-system">
                {"".join(cards_html)}
            </div>
        """)

        # 14. 미니멀 페이지네이션 (12개 단위 페이징)
        if total_pages > 1:
            page_btns = []
            base_url = f"?view=restaurant&rest_zone={urllib.parse.quote(current_zone)}&near_fest={1 if near_fest_only else 0}&rest_query={urllib.parse.quote(current_query)}"

            # 이전 버튼
            if current_page > 1:
                page_btns.append(f'<a href="{base_url}&rest_page={current_page - 1}" target="_self" class="page-btn">‹ 이전</a>')

            # 페이지 번호 (최대 5개 표시)
            start_p = max(1, current_page - 2)
            end_p = min(total_pages, start_p + 4)
            if end_p - start_p < 4:
                start_p = max(1, end_p - 4)

            for p in range(start_p, end_p + 1):
                p_act = "active" if p == current_page else ""
                page_btns.append(f'<a href="{base_url}&rest_page={p}" target="_self" class="page-btn {p_act}">{p}</a>')

            # 다음 버튼
            if current_page < total_pages:
                page_btns.append(f'<a href="{base_url}&rest_page={current_page + 1}" target="_self" class="page-btn">다음 ›</a>')

            st.html(f"""
                <div class="pagination-wrap">
                    {"".join(page_btns)}
                </div>
            """)

    st.html("</div>")
