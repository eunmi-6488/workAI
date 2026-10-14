"""
festapick/weather_care_page.py - FestaPick 안심 날씨 케어 상세 UI 모듈
================================================================================
[16:9 와이드스크린 화면 최적화 (FHD 1920x1080)]
- 가로:세로 16:9 황금 비율에 맞춘 2단 Bento Grid 대시보드 레이아웃
- 스크롤 압박 없이 16:9 모니터 한눈에 들어오는 밀도 높은 컴팩트 핏
- 톤앤매너: 딥그린 (#14382B) & 웜 베이지 (#FDFBF7) & 에메랄드 (#059669)

[하단 균형 정돈 & CTA 리뉴얼 사양]
1. 하단 4단 카드 그리드 높이 균일화 (Equal Height):
   - 4개 카드 (주간 5일 예보, 체력 맞춤 인덱스, 오늘 필수 준비물, 주변 실내 힐링 명소)
   - 1행 4열 그리드 (`grid-template-columns: repeat(4, 1fr)`)로 정렬 일원화
   - `height: 100%`, `display: flex; flex-direction: column; justify-content: space-between;` 적용
2. 하단 전체 폭 액션 바 (Next Action CTA):
   - "☀️ {fest_name}의 날씨가 완벽해요! 이 날씨에 딱 맞는 맞춤 여행 코스를 확인해보세요."
   - 우측 딥그린 버튼: [이 날씨 맞춤 코스 보러가기 →]
   - 클릭 시 여행코스 페이지(`?view=course`)로 자연스러운 이동 연동
3. 지역/축제 전환 시 매끄러운 페이드 인 인터랙션 애니메이션 (CSS `@keyframes careFadeInUp`)
================================================================================
"""

import os
import json
import html
import urllib.parse
import math
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import streamlit as st

# 기상청 실시간 API 수집 및 격자 좌표 변환기 연동
from festapick.weather_api import (
    map_to_grid,
    calculate_feels_like_temp,
    parse_sky_and_pty,
    generate_fallback_weather,
    get_weather_for_coordinate
)

# ------------------------------------------------------------------------------
# 1. 전국 17개 시/도 명칭 정규화 매핑 & 공공데이터 축제 카탈로그 연동
# ------------------------------------------------------------------------------
REGION_SHORT_TO_FULL = {
    "서울": "서울특별시",
    "부산": "부산광역시",
    "대구": "대구광역시",
    "인천": "인천광역시",
    "광주": "광주광역시",
    "대전": "대전광역시",
    "울산": "울산광역시",
    "세종": "세종특별자치시",
    "경기": "경기도",
    "강원": "강원특별자치도",
    "충북": "충청북도",
    "충남": "충청남도",
    "전북": "전북특별자치도",
    "전남": "전라남도",
    "경북": "경상북도",
    "경남": "경상남도",
    "제주": "제주특별자치도",
}

REGION_FULL_TO_SHORT = {v: k for k, v in REGION_SHORT_TO_FULL.items()}

# 전국 17개 광역 시/도별 기초자치단체(시·군·구) 표준 전수 매핑 사전
PROVINCE_SGG_MAP: Dict[str, List[str]] = {
    "전라남도": ["목포시", "여수시", "순천시", "나주시", "광양시", "담양군", "곡성군", "구례군", "고흥군", "보성군", "화순군", "장흥군", "강진군", "해남군", "영암군", "무안군", "함평군", "영광군", "장성군", "완도군", "진도군", "신안군"],
    "전북특별자치도": ["전주시", "군산시", "익산시", "정읍시", "남원시", "김제시", "완주군", "진안군", "무주군", "장수군", "임실군", "순창군", "고창군", "부안군"],
    "경상남도": ["창원시", "진주시", "통영시", "사천시", "김해시", "밀양시", "거제시", "양산시", "의령군", "함안군", "창녕군", "고성군", "남해군", "하동군", "산청군", "함양군", "거창군", "합천군"],
    "경상북도": ["포항시", "경주시", "김천시", "안동시", "구미시", "영주시", "영천시", "상주시", "문경시", "경산시", "의성군", "청송군", "영양군", "영덕군", "청도군", "고령군", "성주군", "칠곡군", "예천군", "봉화군", "울진군", "울릉군"],
    "충청남도": ["천안시", "공주시", "보령시", "아산시", "서산시", "논산시", "계룡시", "당진시", "금산군", "부여군", "서천군", "청양군", "홍성군", "예산군", "태안군"],
    "충청북도": ["청주시", "충주시", "제천시", "보은군", "옥천군", "영동군", "증평군", "진천군", "괴산군", "음성군", "단양군"],
    "강원특별자치도": ["춘천시", "원주시", "강릉시", "동해시", "태백시", "속초시", "삼척시", "홍천군", "횡성군", "영월군", "평창군", "정선군", "철원군", "화천군", "양구군", "인제군", "고성군", "양양군"],
    "경기도": ["수원시", "용인시", "고양시", "화성시", "성남시", "부천시", "남양주시", "안산시", "평택시", "안양시", "시흥시", "파주시", "김포시", "의정부시", "광주시", "하남시", "광명시", "군포시", "양주시", "오산시", "이천시", "안성시", "구리시", "의왕시", "포천시", "양평군", "여주시", "동두천시", "가평군", "과천시", "연천군"],
    "서울특별시": ["종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구"],
    "부산광역시": ["중구", "서구", "동구", "영도구", "부산진구", "동래구", "남구", "북구", "해운대구", "사하구", "금정구", "강서구", "연제구", "수영구", "사상구", "기장군"],
    "대구광역시": ["중구", "동구", "서구", "남구", "북구", "수성구", "달서구", "달성군", "군위군"],
    "인천광역시": ["중구", "동구", "미추홀구", "연수구", "남동구", "부평구", "계양구", "서구", "강화군", "옹진군"],
    "광주광역시": ["동구", "서구", "남구", "북구", "광산구"],
    "대전광역시": ["동구", "중구", "서구", "유성구", "대덕구"],
    "울산광역시": ["중구", "남구", "동구", "북구", "울주군"],
    "세종특별자치시": ["세종시"],
    "제주특별자치도": ["제주시", "서귀포시"]
}


def load_all_catalog_festivals() -> Tuple[List[str], Dict[str, List[Dict[str, Any]]]]:
    """
    공공데이터 852건 전수 축제 및 문화예술행사 데이터를 로드하여 17개 시/도별(풀네임 및 축약형 동시 지원) 목록으로 구조화
    """
    json_path = os.path.join(os.path.dirname(__file__), "data", "master_2026_oct_festivals.json")
    catalog_by_sdo: Dict[str, List[Dict[str, Any]]] = {}

    for sdo_full in REGION_SHORT_TO_FULL.values():
        catalog_by_sdo[sdo_full] = []
        short_k = REGION_FULL_TO_SHORT.get(sdo_full, sdo_full[:2])
        catalog_by_sdo[short_k] = []

    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                items = json.load(f)
                for it in items:
                    short_reg = str(it.get("region", "")).strip()
                    sdo_full = REGION_SHORT_TO_FULL.get(short_reg, short_reg)
                    if sdo_full not in catalog_by_sdo:
                        catalog_by_sdo[sdo_full] = []
                    catalog_by_sdo[sdo_full].append(it)
                    if short_reg and short_reg not in catalog_by_sdo:
                        catalog_by_sdo[short_reg] = []
                    if short_reg:
                        catalog_by_sdo[short_reg].append(it)
        except Exception:
            pass

    available_sdos = [sdo for sdo in REGION_SHORT_TO_FULL.values() if len(catalog_by_sdo.get(sdo, [])) > 0]
    if not available_sdos:
        available_sdos = list(REGION_SHORT_TO_FULL.values())

    return available_sdos, catalog_by_sdo


def extract_sgg_from_addr(addr: str, default_sgg: str = "", title: str = "", sdo: str = "") -> str:
    """
    주소 텍스트와 축제명, 관할 시·도를 교차 분석하여 정확한 시·군·구를 추출합니다.
    (예: '전남 전라', '전라남도 전라' 등 접두어 중복 오기재 원천 차단)
    """
    addr_str = str(addr or "").strip()
    if addr_str.lower() in ["nan", "none", "null"]:
        addr_str = ""

    # 1. 주소 토큰에서 시/군/구 우선 추출 (특별시/광역시/도 단어 제외)
    if addr_str:
        for t in addr_str.split():
            if t.endswith(("시", "군", "구")) and len(t) > 1 and not t.endswith(("특별시", "광역시", "특별자치도", "도")):
                return t

    # 2. 해당 시/도에 속한 전국 표준 시·군·구 사전 기반 텍스트 매칭 (축제명 + 주소 종합)
    full_sdo = REGION_SHORT_TO_FULL.get(sdo, sdo) if sdo else ""
    sgg_candidates = PROVINCE_SGG_MAP.get(full_sdo, []) if full_sdo else [s for s_list in PROVINCE_SGG_MAP.values() for s in s_list]

    search_corpus = f"{title} {addr_str}".strip()

    # 2-1. 정식 시·군·구 포함 검사 (예: '광양시', '순천시')
    for sgg in sgg_candidates:
        if sgg in search_corpus:
            return sgg

    # 2-2. 2글자 이상 지명 어근 매칭 (예: '광양' in '광양전통숯불구이축제' -> '광양시')
    for sgg in sgg_candidates:
        root = sgg[:-1]
        if len(root) >= 2 and root in search_corpus:
            return sgg

    # 3. 읍/면/동 명칭에서 관할 시/군/구 매핑
    if "광양읍" in search_corpus:
        return "광양시"

    # 4. default_sgg가 '전라', '충청', '경상' 등 도명 앞글자일 경우 중복 방지를 위해 빈 문자열 처리
    if default_sgg in ["전라", "충청", "경상", "강원", "경기", "제주", "로컬"]:
        return ""

    return default_sgg

FESTIVAL_WEATHER_PRESETS: Dict[str, Dict[str, Any]] = {
    "순천시 - 순천만 갈대축제": {
        "region_sdo": "전라남도",
        "region_sgg": "순천시",
        "loc_badge": "전남 순천시",
        "festival_name": "순천만 갈대축제",
        "dates": "2026.10.15 ~ 2026.10.19",
        "weather_alert": "기상특보 없음 · 쾌적",
        "current": {
            "weather": "맑음",
            "icon": "☀️",
            "temp": 21,
            "feels_like": 21.5,
            "temp_min": 12,
            "temp_max": 23,
            "rain_prob": 10,
            "humidity": 55,
            "wind_speed": 1.4,
            "dust_status": "좋음 (14㎍/㎥)",
            "guide_badge": "야외 축제 걷기 아주 좋은 쾌적한 날씨예요 🌿",
            "guide_badge_type": "safe"
        },
        "hourly": [
            {"time": "09:00", "icon": "🌤️", "temp": 15, "rain": 0},
            {"time": "12:00", "icon": "☀️", "temp": 21, "rain": 0},
            {"time": "15:00", "icon": "☀️", "temp": 23, "rain": 10},
            {"time": "18:00", "icon": "🌅", "temp": 18, "rain": 10},
            {"time": "21:00", "icon": "🌙", "temp": 14, "rain": 0}
        ],
        "weekly": [
            {"day": "오늘", "date": "10.10(토)", "icon": "☀️", "min": 12, "max": 23, "rain": 10},
            {"day": "내일", "date": "10.11(일)", "icon": "🌤️", "min": 13, "max": 22, "rain": 20},
            {"day": "월", "date": "10.12(월)", "icon": "☁️", "min": 14, "max": 21, "rain": 30},
            {"day": "화", "date": "10.13(화)", "icon": "☀️", "min": 11, "max": 22, "rain": 0},
            {"day": "수", "date": "10.14(수)", "icon": "☀️", "min": 12, "max": 23, "rain": 10}
        ],
        "care_index": {
            "stamina": {
                "level": "보통 (지수 45/100)",
                "desc": "선선한 가을바람으로 2~3시간 야외 도보에 최적입니다.",
                "color": "#10B981",
                "recommended_time": "14:00 ~ 17:30"
            },
            "prep_items": [
                {"item": "선글라스", "icon": "🕶️", "reason": "은빛 반사광 대비"},
                {"item": "가벼운 겉옷", "icon": "🧥", "reason": "일몰 후 강바람 체온 유지"},
                {"item": "편한 운동화", "icon": "👟", "reason": "데크길 3km 산책"}
            ],
            "indoor_spot": {
                "name": "순천만에코촌 전통찻집 & 생태관",
                "distance": "축제장 도보 5분",
                "desc": "통유리창으로 갈대 군락을 감상하며 따뜻한 발효차를 즐기는 실내 쉼터",
                "highlight": "비가 올 때도 습지 전경 360도 관람 에코 전망대"
            }
        }
    },
    "수원시 - 수원화성문화제": {
        "region_sdo": "경기도",
        "region_sgg": "수원시 팔달구",
        "loc_badge": "경기 수원시",
        "festival_name": "수원화성문화제",
        "dates": "2026.10.09 ~ 2026.10.12",
        "weather_alert": "기상특보 없음 · 쾌청",
        "current": {
            "weather": "맑고 쾌청",
            "icon": "🌤️",
            "temp": 19,
            "feels_like": 18.8,
            "temp_min": 11,
            "temp_max": 22,
            "rain_prob": 15,
            "humidity": 50,
            "wind_speed": 2.1,
            "dust_status": "보통 (32㎍/㎥)",
            "guide_badge": "성곽길 트레킹에 상쾌한 바람이 불어요 🍂",
            "guide_badge_type": "safe"
        },
        "hourly": [
            {"time": "09:00", "icon": "🌤️", "temp": 13, "rain": 0},
            {"time": "12:00", "icon": "☀️", "temp": 19, "rain": 10},
            {"time": "15:00", "icon": "🌤️", "temp": 22, "rain": 15},
            {"time": "18:00", "icon": "⛅", "temp": 17, "rain": 20},
            {"time": "21:00", "icon": "🌙", "temp": 13, "rain": 10}
        ],
        "weekly": [
            {"day": "오늘", "date": "10.10(토)", "icon": "🌤️", "min": 11, "max": 22, "rain": 15},
            {"day": "내일", "date": "10.11(일)", "icon": "☀️", "min": 10, "max": 21, "rain": 10},
            {"day": "월", "date": "10.12(월)", "icon": "⛅", "min": 12, "max": 20, "rain": 20},
            {"day": "화", "date": "10.13(화)", "icon": "🌧️", "min": 13, "max": 18, "rain": 60},
            {"day": "수", "date": "10.14(수)", "icon": "☀️", "min": 9, "max": 19, "rain": 10}
        ],
        "care_index": {
            "stamina": {
                "level": "약간 높음 (지수 60/100)",
                "desc": "성곽길 경사로와 계단이 있어 중간 휴식이 필요합니다.",
                "color": "#F59E0B",
                "recommended_time": "10:30 ~ 13:00"
            },
            "prep_items": [
                {"item": "보온 바람막이", "icon": "🧥", "reason": "성곽 맞바람 대비"},
                {"item": "텀블러/생수", "icon": "💧", "reason": "성곽 보행 수분 보충"},
                {"item": "스마트폰 삼각대", "icon": "📸", "reason": "행궁 야경 촬영"}
            ],
            "indoor_spot": {
                "name": "수원시립아이파크미술관 & 행궁카페",
                "distance": "행궁 광장 도보 2분",
                "desc": "기획 현대미술 전시와 통유리 카페에서 행궁 전경을 감상하는 복합 문화공간",
                "highlight": "미술관 아트샵 및 어린이 인터랙티브 도서관"
            }
        }
    },
    "강릉시 - 강릉 커피축제": {
        "region_sdo": "강원특별자치도",
        "region_sgg": "강릉시",
        "loc_badge": "강원 강릉시",
        "festival_name": "강릉 커피축제",
        "dates": "2026.10.10 ~ 2026.10.13",
        "weather_alert": "동해안 강풍주의 권고 · 선선",
        "current": {
            "weather": "구름 조금",
            "icon": "⛅",
            "temp": 17,
            "feels_like": 16.2,
            "temp_min": 9,
            "temp_max": 19,
            "rain_prob": 20,
            "humidity": 62,
            "wind_speed": 3.2,
            "dust_status": "좋음 (10㎍/㎥)",
            "guide_badge": "동해 바닷바람이 쌀쌀해요. 도톰한 외투를 준비하세요 ☕",
            "guide_badge_type": "caution"
        },
        "hourly": [
            {"time": "09:00", "icon": "⛅", "temp": 11, "rain": 10},
            {"time": "12:00", "icon": "🌤️", "temp": 17, "rain": 10},
            {"time": "15:00", "icon": "⛅", "temp": 19, "rain": 20},
            {"time": "18:00", "icon": "☁️", "temp": 15, "rain": 20},
            {"time": "21:00", "icon": "🌙", "temp": 11, "rain": 10}
        ],
        "weekly": [
            {"day": "오늘", "date": "10.10(토)", "icon": "⛅", "min": 9, "max": 19, "rain": 20},
            {"day": "내일", "date": "10.11(일)", "icon": "☁️", "min": 10, "max": 18, "rain": 30},
            {"day": "월", "date": "10.12(월)", "icon": "☀️", "min": 8, "max": 19, "rain": 10},
            {"day": "화", "date": "10.13(화)", "icon": "☀️", "min": 9, "max": 20, "rain": 0},
            {"day": "수", "date": "10.14(수)", "icon": "🌤️", "min": 10, "max": 21, "rain": 10}
        ],
        "care_index": {
            "stamina": {
                "level": "낮음 (지수 30/100)",
                "desc": "안목해변 카페거리 평지 위주로 체력 부담이 적습니다.",
                "color": "#10B981",
                "recommended_time": "11:00 ~ 16:00"
            },
            "prep_items": [
                {"item": "머플러/니트", "icon": "🧣", "reason": "해변 찬바람 차단"},
                {"item": "텀블러(개인컵)", "icon": "☕", "reason": "커피 무료 시음"},
                {"item": "보조배터리", "icon": "🔋", "reason": "바다 배경 야외 촬영"}
            ],
            "indoor_spot": {
                "name": "아르떼뮤지엄 강릉 & 커피박물관",
                "distance": "축제장 차량 8분",
                "desc": "웅장한 미디어아트와 함께 실내에서 따뜻하게 커피 역사를 체험하는 몰입형 전시관",
                "highlight": "비가 오거나 바람이 강할 때 최상의 실내 핫플"
            }
        }
    },
    "공주시 - 백제문화제": {
        "region_sdo": "충청남도",
        "region_sgg": "공주시",
        "loc_badge": "충남 공주시",
        "festival_name": "백제문화제",
        "dates": "2026.10.03 ~ 2026.10.12",
        "weather_alert": "기상특보 없음 · 온화",
        "current": {
            "weather": "맑음",
            "icon": "☀️",
            "temp": 20,
            "feels_like": 20.0,
            "temp_min": 11,
            "temp_max": 22,
            "rain_prob": 10,
            "humidity": 52,
            "wind_speed": 1.6,
            "dust_status": "좋음 (22㎍/㎥)",
            "guide_badge": "금강 유등 야경을 즐기기에 더없이 청명한 가을밤입니다 🏮",
            "guide_badge_type": "safe"
        },
        "hourly": [
            {"time": "09:00", "icon": "🌤️", "temp": 14, "rain": 0},
            {"time": "12:00", "icon": "☀️", "temp": 20, "rain": 0},
            {"time": "15:00", "icon": "☀️", "temp": 22, "rain": 10},
            {"time": "18:00", "icon": "🌅", "temp": 17, "rain": 10},
            {"time": "21:00", "icon": "🌙", "temp": 13, "rain": 0}
        ],
        "weekly": [
            {"day": "오늘", "date": "10.10(토)", "icon": "☀️", "min": 11, "max": 22, "rain": 10},
            {"day": "내일", "date": "10.11(일)", "icon": "☀️", "min": 10, "max": 21, "rain": 0},
            {"day": "월", "date": "10.12(월)", "icon": "🌤️", "min": 11, "max": 22, "rain": 10},
            {"day": "화", "date": "10.13(화)", "icon": "☁️", "min": 12, "max": 20, "rain": 20},
            {"day": "수", "date": "10.14(수)", "icon": "🌧️", "min": 11, "max": 18, "rain": 50}
        ],
        "care_index": {
            "stamina": {
                "level": "보통 (지수 50/100)",
                "desc": "금강신관공원 평지와 공산성 성곽길을 균형 있게 탐방 가능합니다.",
                "color": "#10B981",
                "recommended_time": "15:30 ~ 20:30"
            },
            "prep_items": [
                {"item": "경량 패딩", "icon": "🧥", "reason": "야간 강변 체온 보호"},
                {"item": "편안한 단화", "icon": "👟", "reason": "부교 잔디광장 보행"},
                {"item": "손난로/핫팩", "icon": "🔥", "reason": "수상 공연 관람 필수"}
            ],
            "indoor_spot": {
                "name": "국립공주박물관 & 무령왕릉 전시관",
                "distance": "축제장 차량 5분",
                "desc": "무령왕릉 출토 유물과 첨단 실감 콘텐츠를 즐기는 쾌적한 실내 박물관",
                "highlight": "무료입장 및 카페 테라스 완비"
            }
        }
    },
    "진주시 - 진주 남강유등축제": {
        "region_sdo": "경상남도",
        "region_sgg": "진주시",
        "loc_badge": "경남 진주시",
        "festival_name": "진주 남강유등축제",
        "dates": "2026.10.04 ~ 2026.10.18",
        "weather_alert": "기상특보 없음 · 포근",
        "current": {
            "weather": "맑고 포근",
            "icon": "🌤️",
            "temp": 22,
            "feels_like": 22.2,
            "temp_min": 13,
            "temp_max": 24,
            "rain_prob": 10,
            "humidity": 58,
            "wind_speed": 1.5,
            "dust_status": "좋음 (18㎍/㎥)",
            "guide_badge": "물 위에 비치는 7만 개 유등 산책에 최적의 온도예요 ✨",
            "guide_badge_type": "safe"
        },
        "hourly": [
            {"time": "09:00", "icon": "🌤️", "temp": 16, "rain": 0},
            {"time": "12:00", "icon": "☀️", "temp": 22, "rain": 0},
            {"time": "15:00", "icon": "☀️", "temp": 24, "rain": 10},
            {"time": "18:00", "icon": "🌅", "temp": 19, "rain": 10},
            {"time": "21:00", "icon": "🌙", "temp": 15, "rain": 0}
        ],
        "weekly": [
            {"day": "오늘", "date": "10.10(토)", "icon": "🌤️", "min": 13, "max": 24, "rain": 10},
            {"day": "내일", "date": "10.11(일)", "icon": "☀️", "min": 12, "max": 23, "rain": 0},
            {"day": "월", "date": "10.12(월)", "icon": "☀️", "min": 13, "max": 24, "rain": 0},
            {"day": "화", "date": "10.13(화)", "icon": "⛅", "min": 14, "max": 22, "rain": 20},
            {"day": "수", "date": "10.14(수)", "icon": "☀️", "min": 12, "max": 23, "rain": 10}
        ],
        "care_index": {
            "stamina": {
                "level": "보통 (지수 45/100)",
                "desc": "남강 둔치 평지 보행 위주로 여유롭게 야경을 즐길 수 있습니다.",
                "color": "#10B981",
                "recommended_time": "17:30 ~ 21:30"
            },
            "prep_items": [
                {"item": "가벼운 숄", "icon": "🧣", "reason": "강변 밤바람 보온"},
                {"item": "보조배터리", "icon": "📱", "reason": "유등 야경 연속 촬영"},
                {"item": "물티슈", "icon": "🧼", "reason": "야외 푸드존 미식 필수"}
            ],
            "indoor_spot": {
                "name": "국립진주박물관 & 유등전시관",
                "distance": "촉석루 바로 옆 도보 3분",
                "desc": "진주대첩 역사 유물과 사계절 실내 유등 아트를 감상하는 감성 전시관",
                "highlight": "야간 운영 실내 유등 미디어아트 라운지"
            }
        }
    },
    "서귀포시 - 휴애리 핑크뮬리 축제": {
        "region_sdo": "제주특별자치도",
        "region_sgg": "서귀포시 남원읍",
        "loc_badge": "제주 서귀포시",
        "festival_name": "휴애리 핑크뮬리 축제",
        "dates": "2026.09.15 ~ 2026.11.15",
        "weather_alert": "기상특보 없음 · 산뜻",
        "current": {
            "weather": "선선한 가을바람",
            "icon": "🌤️",
            "temp": 21,
            "feels_like": 20.5,
            "temp_min": 15,
            "temp_max": 23,
            "rain_prob": 15,
            "humidity": 65,
            "wind_speed": 4.1,
            "dust_status": "매우좋음 (8㎍/㎥)",
            "guide_badge": "제주 바람이 살랑여요. 핑크빛 물결 인생샷에 최고의 날 🌸",
            "guide_badge_type": "safe"
        },
        "hourly": [
            {"time": "09:00", "icon": "🌤️", "temp": 17, "rain": 10},
            {"time": "12:00", "icon": "☀️", "temp": 21, "rain": 10},
            {"time": "15:00", "icon": "🌤️", "temp": 23, "rain": 15},
            {"time": "18:00", "icon": "🌅", "temp": 19, "rain": 15},
            {"time": "21:00", "icon": "🌙", "temp": 16, "rain": 10}
        ],
        "weekly": [
            {"day": "오늘", "date": "10.10(토)", "icon": "🌤️", "min": 15, "max": 23, "rain": 15},
            {"day": "내일", "date": "10.11(일)", "icon": "☀️", "min": 16, "max": 24, "rain": 10},
            {"day": "월", "date": "10.12(월)", "icon": "🌤️", "min": 15, "max": 23, "rain": 10},
            {"day": "화", "date": "10.13(화)", "icon": "🌧️", "min": 17, "max": 21, "rain": 50},
            {"day": "수", "date": "10.14(수)", "icon": "☀️", "min": 14, "max": 22, "rain": 0}
        ],
        "care_index": {
            "stamina": {
                "level": "낮음 (지수 35/100)",
                "desc": "정원 평지와 완만한 야자수 매트 보행로로 온 가족 힐링에 제격입니다.",
                "color": "#10B981",
                "recommended_time": "13:30 ~ 16:30"
            },
            "prep_items": [
                {"item": "바람막이", "icon": "🧥", "reason": "산간 돌풍 대비"},
                {"item": "자외선 차단제", "icon": "🧴", "reason": "정원 햇살 케어"},
                {"item": "화이트 계열 의상", "icon": "👗", "reason": "핑크뮬리 인생샷"}
            ],
            "indoor_spot": {
                "name": "휴애리 온실 정원 카페 & 본태박물관",
                "distance": "원내 온실 / 차량 15분",
                "desc": "사계절 야생화와 귤나무가 가득한 대형 실내 온실 카페 및 건축 박물관",
                "highlight": "비가 와도 실내 핑크뮬리 관람 온실"
            }
        }
    },
    "영등포구 - 서울세계불꽃축제": {
        "region_sdo": "서울특별시",
        "region_sgg": "영등포구 여의도동",
        "loc_badge": "서울 영등포구",
        "festival_name": "서울세계불꽃축제",
        "dates": "2026.10.03 ~ 2026.10.05",
        "weather_alert": "기상특보 없음 · 일교차 주의",
        "current": {
            "weather": "맑고 청명",
            "icon": "🎆",
            "temp": 18,
            "feels_like": 17.2,
            "temp_min": 10,
            "temp_max": 21,
            "rain_prob": 5,
            "humidity": 48,
            "wind_speed": 1.9,
            "dust_status": "좋음 (19㎍/㎥)",
            "guide_badge": "한강변 야간 체온이 급격히 떨어지니 두꺼운 겉옷을 챙기세요 🌌",
            "guide_badge_type": "caution"
        },
        "hourly": [
            {"time": "09:00", "icon": "🌤️", "temp": 12, "rain": 0},
            {"time": "12:00", "icon": "☀️", "temp": 18, "rain": 0},
            {"time": "15:00", "icon": "☀️", "temp": 21, "rain": 0},
            {"time": "18:00", "icon": "🌅", "temp": 16, "rain": 5},
            {"time": "21:00", "icon": "🌙", "temp": 12, "rain": 5}
        ],
        "weekly": [
            {"day": "오늘", "date": "10.10(토)", "icon": "☀️", "min": 10, "max": 21, "rain": 5},
            {"day": "내일", "date": "10.11(일)", "icon": "🌤️", "min": 11, "max": 20, "rain": 10},
            {"day": "월", "date": "10.12(월)", "icon": "⛅", "min": 12, "max": 19, "rain": 20},
            {"day": "화", "date": "10.13(화)", "icon": "☀️", "min": 10, "max": 21, "rain": 0},
            {"day": "수", "date": "10.14(수)", "icon": "☀️", "min": 11, "max": 22, "rain": 0}
        ],
        "care_index": {
            "stamina": {
                "level": "약간 높음 (지수 65/100)",
                "desc": "인파 분산 대기 및 지하철역 도보 이동으로 체력 소모가 큽니다.",
                "color": "#F59E0B",
                "recommended_time": "16:00 ~ 21:30"
            },
            "prep_items": [
                {"item": "도톰한 담요", "icon": "🧣", "reason": "강변 찬바람 체온 유지"},
                {"item": "캠핑방석", "icon": "🏕️", "reason": "잔디밭 장시간 착석"},
                {"item": "보조배터리", "icon": "🔋", "reason": "불꽃놀이 고화질 촬영"}
            ],
            "indoor_spot": {
                "name": "IFC몰 & 더현대 서울 복합공간",
                "distance": "한강공원 도보 10분",
                "desc": "실내 정원 사운즈 포레스트에서 따뜻하게 대기 가능한 공간",
                "highlight": "지하철역 직결로 안전한 동선 확보"
            }
        }
    }
}


def get_preset_for_festival(sdo: str, fest_option: str) -> Dict[str, Any]:
    """선택된 시/도 및 축제 옵션에 맞는 날씨 데이터 프리셋 반환 (누락 시 지능형 합성)"""
    if fest_option in FESTIVAL_WEATHER_PRESETS:
        return FESTIVAL_WEATHER_PRESETS[fest_option]

    full_sdo = REGION_SHORT_TO_FULL.get(sdo, sdo)
    short_sdo = REGION_FULL_TO_SHORT.get(full_sdo, full_sdo[:2])

    clean_title = fest_option.split(" - ")[-1].split(" (")[0].strip()
    sgg = extract_sgg_from_addr("", default_sgg="", title=clean_title, sdo=full_sdo)
    loc_badge_text = f"{short_sdo} {sgg}".strip() if sgg else short_sdo

    dates_str = "2026.10.10 ~ 2026.10.25"
    if "광양" in clean_title:
        dates_str = "2026.10.01 ~ 2026.10.04"

    return {
        "region_sdo": full_sdo,
        "region_sgg": sgg,
        "loc_badge": loc_badge_text,
        "festival_name": clean_title,
        "dates": dates_str,
        "weather_alert": "기상특보 없음 · 쾌적",
        "current": {
            "weather": "맑고 상쾌",
            "icon": "🌤️",
            "temp": 20,
            "feels_like": 19.8,
            "temp_min": 11,
            "temp_max": 22,
            "rain_prob": 10,
            "humidity": 54,
            "wind_speed": 1.8,
            "dust_status": "좋음 (18㎍/㎥)",
            "guide_badge": f"{clean_title} 현장 나들이에 최적의 청명한 가을 날씨예요 🍁",
            "guide_badge_type": "safe"
        },
        "hourly": [
            {"time": "09:00", "icon": "🌤️", "temp": 14, "rain": 0},
            {"time": "12:00", "icon": "☀️", "temp": 20, "rain": 0},
            {"time": "15:00", "icon": "☀️", "temp": 22, "rain": 10},
            {"time": "18:00", "icon": "🌅", "temp": 17, "rain": 10},
            {"time": "21:00", "icon": "🌙", "temp": 13, "rain": 0}
        ],
        "weekly": [
            {"day": "오늘", "date": "10.10(토)", "icon": "☀️", "min": 11, "max": 22, "rain": 10},
            {"day": "내일", "date": "10.11(일)", "icon": "☀️", "min": 10, "max": 21, "rain": 10},
            {"day": "월", "date": "10.12(월)", "icon": "🌤️", "min": 12, "max": 22, "rain": 20},
            {"day": "화", "date": "10.13(화)", "icon": "☁️", "min": 11, "max": 20, "rain": 20},
            {"day": "수", "date": "10.14(수)", "icon": "☀️", "min": 10, "max": 21, "rain": 10}
        ],
        "care_index": {
            "stamina": {
                "level": "보통 (지수 48/100)",
                "desc": f"{clean_title} 행사 코스 도보에 쾌적한 컨디션입니다.",
                "color": "#10B981",
                "recommended_time": "13:00 ~ 17:30"
            },
            "prep_items": [
                {"item": "가벼운 외투", "icon": "🧥", "reason": "일몰 후 기온 강하 대비"},
                {"item": "편한 신발", "icon": "👟", "reason": "축제장 도보 관람"},
                {"item": "보온 음료", "icon": "☕", "reason": "체온 유지"}
            ],
            "indoor_spot": {
                "name": f"{sgg} 복합문화센터 & 인근 카페" if sgg else "로컬 복합문화센터 & 인근 카페",
                "distance": "축제장 도보 7분",
                "desc": "비나 쌀쌀한 바람을 피해 따뜻하게 휴식할 수 있는 실내 쉼터",
                "highlight": "쾌적한 냉난방 및 편의시설 완비"
            }
        }
    }


def check_is_festival_ended(end_date_info: Any, travel_date: Optional[date] = None) -> bool:
    """
    축제 종료 여부(Date Check) 판별:
    '여행 일정(날짜)' 또는 현재 날짜가 축제의 '종료일(endDate)'보다 이후인 경우 True 반환
    """
    today = date.today()
    end_date_obj = None

    if isinstance(end_date_info, date):
        end_date_obj = end_date_info
    elif isinstance(end_date_info, str):
        raw = end_date_info.split("~")[-1].strip()
        digits = "".join([c for c in raw if c.isdigit()])
        if len(digits) >= 8:
            target_str = digits[:8]
            try:
                end_date_obj = date(int(target_str[:4]), int(target_str[4:6]), int(target_str[6:8]))
            except ValueError:
                end_date_obj = None

    if end_date_obj:
        if travel_date and travel_date > end_date_obj:
            return True
        if today > end_date_obj:
            return True

    return False


def get_live_weather_for_festival(sdo: str, fest_label: str, travel_date: date) -> Dict[str, Any]:
    """
    선택된 축제의 위경도(mapx, mapy) 기반 기상청 LCC 격자 변환 및 실시간 기상 데이터 수집/생성
    """
    available_sdos, catalog = load_all_catalog_festivals()
    sdo_full = REGION_SHORT_TO_FULL.get(sdo, sdo)
    fest_list = catalog.get(sdo_full, []) or catalog.get(sdo, [])

    # 축제 객체 매칭 (라벨 내 축제명 부분 매칭)
    matched_fest = None
    clean_target = fest_label.split(" (")[0].split(" - ")[-1].strip()

    for it in fest_list:
        t = it.get("title", "")
        if t and (t in clean_target or clean_target in t):
            matched_fest = it
            break

    # 해당 시/도 목록에서 매칭되지 않으면 전체 카탈로그 전수 검색
    if not matched_fest:
        for k_sdo, f_items in catalog.items():
            for it in f_items:
                t = it.get("title", "")
                if t and (t in clean_target or clean_target in t):
                    matched_fest = it
                    sdo_full = REGION_SHORT_TO_FULL.get(k_sdo, k_sdo)
                    sdo = sdo_full
                    break
            if matched_fest:
                break

    if not matched_fest and fest_list:
        matched_fest = fest_list[0]

    if matched_fest:
        try:
            lat = float(matched_fest.get("mapy", 37.5665))
            lng = float(matched_fest.get("mapx", 126.9780))
            if math.isnan(lat) or math.isnan(lng) or lat < 30.0 or lat > 40.0 or lng < 120.0 or lng > 135.0:
                lat, lng = 37.5665, 126.9780
        except (ValueError, TypeError):
            lat, lng = 37.5665, 126.9780

        fest_title = matched_fest.get("title", fest_label)
        fest_addr = matched_fest.get("addr", sdo)
        sgg = extract_sgg_from_addr(fest_addr, default_sgg="", title=fest_title, sdo=sdo)
        short_sdo = REGION_FULL_TO_SHORT.get(sdo, sdo[:2])
        loc_badge = f"{short_sdo} {sgg}".strip() if sgg else short_sdo

        start_d = str(matched_fest.get("startDate", "20261010")).replace("-", "").strip()
        end_d = str(matched_fest.get("endDate", "20261025")).replace("-", "").strip()

        # 실제 다일 축제 기간 보정 사전 (공공데이터 상 단일일자로 오기재된 대표 축제 복원)
        KNOWN_MULTI_DAY_FESTIVALS = {
            "광양전통숯불구이": ("20261001", "20261004"),
            "평택 원평나루 억새": ("20261024", "20261025"),
            "포항국제불빛": ("20261009", "20261011"),
        }
        for k_name, (k_s, k_e) in KNOWN_MULTI_DAY_FESTIVALS.items():
            if k_name in fest_title:
                start_d, end_d = k_s, k_e
                break

        end_date_obj = None
        if len(end_d) == 8 and end_d.isdigit():
            try:
                end_date_obj = date(int(end_d[:4]), int(end_d[4:6]), int(end_d[6:8]))
            except ValueError:
                end_date_obj = None

        if len(start_d) == 8 and len(end_d) == 8:
            if start_d == end_d:
                dates_str = f"{start_d[:4]}.{start_d[4:6]}.{start_d[6:]} (당일 행사)"
            else:
                dates_str = f"{start_d[:4]}.{start_d[4:6]}.{start_d[6:]} ~ {end_d[:4]}.{end_d[4:6]}.{end_d[6:]}"
        elif len(start_d) == 8:
            dates_str = f"{start_d[:4]}.{start_d[4:6]}.{start_d[6:]}"
        else:
            dates_str = f"{start_d} ~ {end_d}" if end_d and end_d != start_d else str(start_d)

        # 기상청 단기예보 격자 변환 및 실시간 데이터 수집 (1시간 캐싱)
        w_data = get_weather_for_coordinate(
            lat=lat,
            lng=lng,
            fest_name=fest_title,
            addr=fest_addr,
            target_date_str=travel_date.strftime("%Y-%m-%d")
        )

        is_ended = check_is_festival_ended(end_date_obj or end_d, travel_date)

        w_data["region_sdo"] = sdo
        w_data["region_sgg"] = sgg
        w_data["loc_badge"] = loc_badge
        w_data["festival_name"] = fest_title
        w_data["dates"] = dates_str
        w_data["lat"] = lat
        w_data["lng"] = lng
        w_data["is_ended"] = is_ended
        w_data["end_date"] = end_date_obj
        w_data["travel_date"] = travel_date

        # 주변 실내 힐링 명소 지능형 추천
        if "care_index" in w_data and "indoor_spot" in w_data["care_index"]:
            w_data["care_index"]["indoor_spot"]["name"] = f"{sgg} 복합문화센터 & 로컬 힐링 스팟"
            w_data["care_index"]["indoor_spot"]["distance"] = "축제장 도보 7~10분"

        return w_data

    # 매칭 실패 시 기본 프리셋 반환
    preset = get_preset_for_festival(sdo, fest_label)
    preset["travel_date"] = travel_date
    preset["is_ended"] = check_is_festival_ended(preset.get("dates", ""), travel_date)
    return preset


# ------------------------------------------------------------------------------
# 2. 16:9 와이드스크린 최적화 CSS 스타일시트 (페이드 인 인터랙션 포함)
# ------------------------------------------------------------------------------
def get_weather_care_css() -> str:
    return """
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    /* 지역/축제 전환 시 매끄러운 페이드 인 인터랙션 애니메이션 */
    @keyframes careFadeInUp {
        0% {
            opacity: 0;
            transform: translateY(8px);
        }
        100% {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* 16:9 모니터(1920x1080) 최적 폭 & 상단 여백 슬림화 */
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 2.2rem !important;
        padding-left: 2.2rem !important;
        padding-right: 2.2rem !important;
        max-width: 1560px !important; /* 16:9 황금비 너비 */
    }

    /* 16:9 메인 대시보드 캔버스 래퍼 */
    .care-page-wrapper {
        font-family: 'Pretendard', -apple-system, sans-serif;
        color: #1A2E26;
        background-color: #FDFBF7;
        width: 100%;
        max-width: 1560px;
        margin: 0 auto;
    }

    /* 1. 상단 네비게이션 헤더 (콤팩트 단일 라인) */
    .care-header-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 10px;
        border-bottom: 1.5px solid #EAE3D6;
        margin-bottom: 12px;
        gap: 12px;
    }
    .btn-return-home {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #FFFFFF;
        color: #14382B !important;
        border: 1.5px solid #D8CFC0;
        padding: 5px 15px;
        border-radius: 9999px;
        font-size: 0.84rem;
        font-weight: 700;
        text-decoration: none !important;
        transition: all 0.2s ease;
        box-shadow: 0 2px 5px rgba(20, 56, 43, 0.04);
    }
    .btn-return-home:hover {
        background: #14382B;
        color: #FAF7F2 !important;
        border-color: #14382B;
        transform: translateY(-1px);
    }
    .care-header-title-box {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .care-brand-tag {
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.05em;
        color: #059669;
        background: #ECFDF5;
        padding: 2px 7px;
        border-radius: 8px;
    }
    .care-main-title {
        font-size: 1.30rem;
        font-weight: 900;
        color: #14382B;
        letter-spacing: -0.03em;
        margin: 0;
    }

    /* 2. 상단 3단계 필터바 */
    .care-filter-section-title {
        font-size: 0.80rem;
        font-weight: 800;
        color: #059669;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 5px;
    }

    /* 3. 16:9 와이드스크린 Stage Row 1 (중단 대시보드) */
    .widescreen-stage-row1 {
        display: grid;
        grid-template-columns: 1.08fr 0.92fr;
        gap: 16px;
        margin-top: 12px;
        margin-bottom: 16px;
        animation: careFadeInUp 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    @media (max-width: 1024px) {
        .widescreen-stage-row1 {
            grid-template-columns: 1fr;
        }
    }

    /* 메인 실시간 날씨 히어로 카드 */
    .bento-hero-weather {
        background: linear-gradient(135deg, #14382B 0%, #1A4736 60%, #0F3325 100%);
        color: #FAF7F2;
        border-radius: 20px;
        padding: 24px 24px 20px 24px;
        box-shadow: 0 12px 28px rgba(20, 56, 43, 0.16);
        position: relative;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 290px;
    }
    .bento-hero-weather::after {
        content: "";
        position: absolute;
        top: -50px;
        right: -50px;
        width: 180px;
        height: 180px;
        background: radial-gradient(circle, rgba(16, 185, 129, 0.16) 0%, transparent 70%);
        pointer-events: none;
    }
    .hero-weather-top {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 14px;
        gap: 10px;
    }
    .hero-region-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: rgba(16, 185, 129, 0.22);
        color: #A7F3D0;
        border: 1px solid rgba(16, 185, 129, 0.4);
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.76rem;
        font-weight: 800;
        margin-bottom: 4px;
    }
    .hero-loc-title {
        font-size: 1.48rem;
        font-weight: 900;
        letter-spacing: -0.03em;
        color: #FFFFFF;
        margin: 0;
        line-height: 1.22;
    }
    .hero-fest-dates {
        font-size: 0.80rem;
        color: #D1FAE5;
        margin-top: 2px;
    }
    .hero-top-badges-group {
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .hero-alert-badge {
        font-size: 0.72rem;
        background: rgba(254, 240, 138, 0.18);
        border: 1px solid rgba(254, 240, 138, 0.45);
        color: #FEF08A;
        padding: 3px 8px;
        border-radius: 10px;
        font-weight: 800;
        white-space: nowrap;
    }
    .hero-obs-badge {
        font-size: 0.72rem;
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.25);
        color: #E2E8F0;
        padding: 3px 8px;
        border-radius: 10px;
        font-weight: 700;
        white-space: nowrap;
    }
    .hero-obs-badge-ended {
        background: rgba(220, 38, 38, 0.28) !important;
        border: 1px solid rgba(248, 113, 113, 0.6) !important;
        color: #FEE2E2 !important;
        font-weight: 800 !important;
    }
    .hero-weather-center {
        display: flex;
        align-items: center;
        gap: 18px;
        margin-bottom: 16px;
    }
    .hero-weather-big-icon {
        font-size: 3.8rem;
        line-height: 1;
        filter: drop-shadow(0 6px 12px rgba(0,0,0,0.22));
    }
    .hero-current-temp {
        font-size: 3.1rem;
        font-weight: 900;
        line-height: 0.95;
        letter-spacing: -0.04em;
        color: #FEF08A;
    }
    .hero-feels-like {
        font-size: 0.88rem;
        color: #D1FAE5;
        margin-top: 4px;
    }
    .hero-temp-range {
        font-size: 0.82rem;
        color: #A7F3D0;
        margin-top: 1px;
    }
    .hero-guide-badge {
        display: flex;
        align-items: center;
        gap: 8px;
        background: rgba(255, 255, 255, 0.13);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.20);
        padding: 9px 14px;
        border-radius: 12px;
        font-size: 0.86rem;
        font-weight: 700;
        color: #FFFFFF;
    }
    .hero-guide-badge-ended {
        background: rgba(245, 158, 11, 0.20) !important;
        border: 1px solid rgba(251, 191, 36, 0.45) !important;
        color: #FEF3C7 !important;
    }

    /* 우측 2단 복합 Bento 컬럼 */
    .widescreen-right-stack {
        display: flex;
        flex-direction: column;
        gap: 12px;
        justify-content: space-between;
    }

    /* 환경 세부 지표 카드 */
    .bento-env-stats-card {
        background: #FFFFFF;
        border: 1.5px solid #EAE3D6;
        border-radius: 18px;
        padding: 14px 18px;
        box-shadow: 0 4px 12px rgba(20, 56, 43, 0.03);
    }
    .env-stat-title {
        font-size: 0.86rem;
        font-weight: 900;
        color: #14382B;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .env-metrics-grid-4 {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px;
    }
    .env-metric-item {
        background: #F9FAFB;
        border: 1px solid #F3F4F6;
        border-radius: 10px;
        padding: 8px 10px;
        display: flex;
        flex-direction: column;
        gap: 2px;
        text-align: center;
    }
    .env-metric-label {
        font-size: 0.70rem;
        color: #6B7280;
        font-weight: 600;
    }
    .env-metric-val {
        font-size: 1.02rem;
        font-weight: 800;
        color: #111827;
    }

    /* 시간대별 축제 예보 슬라이더 */
    .bento-hourly-card {
        background: #FFFFFF;
        border: 1.5px solid #EAE3D6;
        border-radius: 18px;
        padding: 14px 18px;
        box-shadow: 0 4px 12px rgba(20, 56, 43, 0.03);
    }
    .scroll-rail-hourly {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding-bottom: 4px;
    }
    .hourly-pill-card {
        flex: 1;
        min-width: 82px;
        background: #FDFBF7;
        border: 1px solid #EAE3D6;
        border-radius: 12px;
        padding: 8px 6px;
        text-align: center;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 3px;
        flex-shrink: 0;
        transition: all 0.15s ease;
    }
    .hourly-pill-card:hover {
        background: #F0FDF4;
        border-color: #10B981;
    }
    .hourly-time {
        font-size: 0.74rem;
        font-weight: 700;
        color: #4B5563;
    }
    .hourly-icon {
        font-size: 1.35rem;
    }
    .hourly-temp {
        font-size: 0.95rem;
        font-weight: 800;
        color: #14382B;
    }
    .hourly-rain {
        font-size: 0.68rem;
        color: #0284C7;
        font-weight: 700;
    }

    /* 4. 하단 4단 카드 그리드 높이 균일화 (Equal Height 4-Column Grid) */
    .care-bottom-4cards-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 18px;
        align-items: stretch; /* 모든 카드의 상하 높이 완벽 일치 */
        animation: careFadeInUp 0.40s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    @media (max-width: 1160px) {
        .care-bottom-4cards-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    @media (max-width: 680px) {
        .care-bottom-4cards-grid {
            grid-template-columns: 1fr;
        }
    }

    /* 통일된 4단 공통 카드 스타일 (Equal Height) */
    .care-equal-card {
        background: #FFFFFF;
        border: 1.5px solid #EAE3D6;
        border-radius: 18px;
        padding: 18px 16px;
        box-shadow: 0 4px 12px rgba(20, 56, 43, 0.03);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 100%;
        min-height: 290px; /* 균일한 세로 규격 보장 */
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .care-equal-card:hover {
        transform: translateY(-2px);
        border-color: #059669;
        box-shadow: 0 8px 20px rgba(20, 56, 43, 0.08);
    }
    .care-card-tag {
        font-size: 0.72rem;
        font-weight: 800;
        color: #059669;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 4px;
    }
    .care-card-title {
        font-size: 0.98rem;
        font-weight: 900;
        color: #14382B;
        margin: 0 0 10px 0;
    }
    .care-card-body-grow {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        margin-bottom: 10px;
    }

    /* 주간 예보 행 */
    .weekly-row-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 5px 8px;
        background: #FDFBF7;
        border: 1px solid #EAE3D6;
        border-radius: 8px;
        margin-bottom: 4px;
    }

    /* 준비물 뱃지 */
    .prep-badges-wrap {
        display: flex;
        flex-direction: column;
        gap: 6px;
        width: 100%;
    }
    .prep-badge-item {
        background: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 6px 10px;
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 8px;
        font-size: 0.76rem;
        line-height: 1.3;
        min-height: 36px;
        box-sizing: border-box;
    }
    .prep-badge-item:hover {
        background: #F3F4F6;
    }
    .prep-badge-item .prep-badge-icon,
    .prep-badge-item > span:first-child {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 22px;
        height: 22px;
        font-size: 1.05rem;
        line-height: 1;
        flex-shrink: 0;
        vertical-align: middle;
    }
    .prep-badge-item .prep-badge-title,
    .prep-badge-item > strong {
        color: #111827;
        font-size: 0.76rem;
        font-weight: 700;
        white-space: nowrap;
        flex-shrink: 0;
        display: inline-flex;
        align-items: center;
        line-height: 1.3;
    }
    .prep-badge-item .prep-badge-reason,
    .prep-badge-item > span:last-child {
        color: #4B5563;
        font-size: 0.72rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex: 1;
        min-width: 0;
        display: inline-flex;
        align-items: center;
        line-height: 1.3;
    }

    /* 실내 대체 명소 박스 */
    .indoor-spot-box {
        background: #F0FDF4;
        border: 1.2px solid #A7F3D0;
        border-radius: 12px;
        padding: 8px 10px;
        display: flex;
        flex-direction: column;
        gap: 5px;
        flex-grow: 1;
        justify-content: flex-start;
        overflow: hidden;
    }
    .indoor-thumb-container {
        position: relative;
        width: 100%;
        height: 88px;
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 2px;
        background: #E6F4EA;
    }
    .indoor-spot-thumb {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
        transition: transform 0.3s ease;
    }
    .indoor-thumb-container:hover .indoor-spot-thumb {
        transform: scale(1.03);
    }
    .indoor-thumb-badge {
        position: absolute;
        top: 6px;
        left: 6px;
        background: rgba(20, 56, 43, 0.85);
        backdrop-filter: blur(4px);
        color: #ECFDF5;
        font-size: 0.64rem;
        font-weight: 700;
        padding: 2px 7px;
        border-radius: 6px;
        border: 1px solid rgba(167, 243, 208, 0.35);
    }
    .indoor-spot-title {
        font-size: 0.82rem;
        font-weight: 800;
        color: #064E3B;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .indoor-spot-dist {
        font-size: 0.68rem;
        background: #FFFFFF;
        color: #059669;
        padding: 1px 6px;
        border-radius: 4px;
        border: 1px solid #A7F3D0;
        font-weight: 700;
        white-space: nowrap;
    }
    .indoor-spot-desc {
        font-size: 0.73rem;
        color: #065F46;
        line-height: 1.34;
    }
    .indoor-tags-row {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        margin-top: 2px;
    }
    .indoor-tag-chip {
        display: inline-flex;
        align-items: center;
        background: #FFFFFF;
        border: 1px solid #A7F3D0;
        color: #047857;
        font-size: 0.65rem;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 6px;
        white-space: nowrap;
    }

    /* 5. 하단 액션 바 (Next Action CTA 배너) */
    .care-next-action-banner {
        background: linear-gradient(90deg, #F0FDF4 0%, #FFFFFF 50%, #FEF9C3 100%);
        border: 1.5px solid #A7F3D0;
        border-radius: 18px;
        padding: 16px 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 16px;
        margin-bottom: 24px;
        box-shadow: 0 6px 18px rgba(20, 56, 43, 0.05);
        animation: careFadeInUp 0.45s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    .banner-left-content {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .banner-icon {
        font-size: 1.85rem;
        line-height: 1;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));
    }
    .banner-text-wrap {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .banner-title-text {
        font-size: 1.05rem;
        font-weight: 900;
        color: #14382B;
        letter-spacing: -0.02em;
    }
    .banner-sub-text {
        font-size: 0.84rem;
        color: #4B5563;
        font-weight: 600;
    }
    .banner-cta-btn {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: #14382B;
        color: #FAF7F2 !important;
        padding: 11px 22px;
        border-radius: 9999px;
        font-size: 0.90rem;
        font-weight: 800;
        text-decoration: none !important;
        box-shadow: 0 4px 14px rgba(20, 56, 43, 0.22);
        transition: all 0.2s ease;
        white-space: nowrap;
    }
    .banner-cta-btn:hover {
        background: #065F46;
        color: #FFFFFF !important;
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(20, 56, 43, 0.30);
    }
    </style>
    """


# ------------------------------------------------------------------------------
# 3. 16:9 와이드스크린 컴포넌트 단위 렌더러 함수들
# ------------------------------------------------------------------------------

def render_header_nav():
    """상단 네비게이션: '← 메인으로 돌아가기' 및 타이틀 (16:9 단일 라인)"""
    st.html("""
    <div class="care-header-bar">
        <div>
            <a href="?view=main" class="btn-return-home">
                <span>←</span>
                <span>메인으로 돌아가기</span>
            </a>
        </div>
        <div class="care-header-title-box">
            <span class="care-brand-tag">🛡️ FESTAPICK CONCIERGE</span>
            <h1 class="care-main-title">FestaPick 안심 날씨 케어</h1>
        </div>
    </div>
    """)


def render_selector_bar() -> Tuple[str, str, date]:
    """공공데이터 438건 전수 축제 카탈로그 연동 3단계 상단 필터바 ([시/도] -> [상세 축제] -> [날짜])"""
    available_sdos, catalog = load_all_catalog_festivals()

    # 쿼리 파라미터 딥링크 연동 지원
    if "exp_region" in st.query_params:
        r_param = st.query_params.get("exp_region")
        full_sdo = REGION_SHORT_TO_FULL.get(r_param, r_param)
        if full_sdo in available_sdos:
            st.session_state.care_selected_sdo = full_sdo

    if "select_fest_and_go" in st.query_params:
        f_param = st.query_params.get("select_fest_and_go")
        if f_param:
            st.session_state.care_selected_fest = f_param

    cur_sdo = st.session_state.get("care_selected_sdo", "서울특별시")
    if cur_sdo not in available_sdos:
        cur_sdo = REGION_SHORT_TO_FULL.get(cur_sdo, available_sdos[0])
    sdo_idx = available_sdos.index(cur_sdo) if cur_sdo in available_sdos else 0

    with st.container(border=True):
        col_sdo, col_fest, col_date = st.columns([1.1, 1.8, 1.1], gap="medium")

        with col_sdo:
            st.markdown('<div class="care-filter-section-title">📍 지역 (시/도)</div>', unsafe_allow_html=True)
            chosen_sdo = st.selectbox(
                "시/도 선택",
                options=available_sdos,
                index=sdo_idx,
                label_visibility="collapsed",
                key="care_filter_sdo"
            )

        # 선택된 시/도에 속한 실제 축제 및 문화예술행사 목록 실시간 필터링
        fest_items = catalog.get(chosen_sdo, [])
        if fest_items:
            fest_options = []
            seen_labels = set()
            for it in fest_items:
                t = it.get("title", "")
                sgg = extract_sgg_from_addr(it.get("addr", ""), default_sgg="", title=t, sdo=chosen_sdo)
                label = f"{t} ({sgg})" if sgg else t
                if label not in seen_labels:
                    seen_labels.add(label)
                    fest_options.append(label)
        else:
            fest_options = REGION_FESTIVAL_MAP.get(chosen_sdo, ["가을 로컬 축제"])

        cur_fest = st.session_state.get("care_selected_fest", fest_options[0] if fest_options else "")
        fest_idx = 0
        for i, opt in enumerate(fest_options):
            if cur_fest and (cur_fest in opt or opt in cur_fest):
                fest_idx = i
                break

        with col_fest:
            st.markdown('<div class="care-filter-section-title">🎪 축제 & 문화예술행사 선택</div>', unsafe_allow_html=True)
            chosen_fest = st.selectbox(
                "상세 축제 선택",
                options=fest_options,
                index=fest_idx,
                label_visibility="collapsed",
                key="care_filter_fest"
            )

        with col_date:
            st.markdown('<div class="care-filter-section-title">📅 여행 일정 (날짜)</div>', unsafe_allow_html=True)
            today_date = datetime.now().date()
            default_care_date = st.session_state.get("care_selected_date", today_date)
            min_date_bound = min(today_date - timedelta(days=90), date(2026, 1, 1))
            max_date_bound = max(today_date + timedelta(days=365), date(2027, 12, 31))
            chosen_date = st.date_input(
                "여행 날짜 선택",
                value=default_care_date,
                min_value=min_date_bound,
                max_value=max_date_bound,
                label_visibility="collapsed",
                key="care_filter_date"
            )

    st.session_state.care_selected_sdo = chosen_sdo
    st.session_state.care_selected_fest = chosen_fest
    st.session_state.care_selected_date = chosen_date

    return chosen_sdo, chosen_fest, chosen_date


def render_widescreen_stage_1(preset_data: Dict[str, Any]):
    """
    16:9 Stage Row 1 (중단 대시보드):
    - [좌측 52%]: 대형 메인 실시간 날씨 히어로 카드
    - [우측 48%]: 2단 Bento (상단: 환경 지표 4종 / 하단: 시간대별 예보 슬라이더)
    """
    cur = preset_data["current"]
    fest_name = preset_data["festival_name"]
    loc_sdo = preset_data["region_sdo"]
    loc_sgg = preset_data.get("region_sgg", "")
    short_sdo = REGION_FULL_TO_SHORT.get(loc_sdo, loc_sdo[:2])

    if loc_sgg and loc_sgg not in [loc_sdo, loc_sdo[:2], short_sdo]:
        loc_badge = preset_data.get("loc_badge") or f"{short_sdo} {loc_sgg}"
        loc_full_addr = f"{loc_sdo} {loc_sgg}"
    else:
        loc_badge = preset_data.get("loc_badge") or short_sdo
        loc_full_addr = loc_sdo

    dates = preset_data.get("dates", "2026.10.10 ~ 2026.10.25")
    weather_alert = preset_data.get("weather_alert", "기상특보 없음 · 쾌적")
    hourly_list = preset_data.get("hourly", [])

    # 1. 축제 종료 여부 판별 (여행 일정 또는 현재 날짜가 축제 종료일보다 이후인 경우)
    is_ended = preset_data.get("is_ended")
    if is_ended is None:
        is_ended = check_is_festival_ended(preset_data.get("end_date") or dates, preset_data.get("travel_date"))

    # 우측 상단 뱃지: [실시간 관측] vs [● 축제 종료]
    if is_ended:
        obs_badge_html = '<span class="hero-obs-badge hero-obs-badge-ended">● 축제 종료</span>'
    else:
        obs_badge_html = '<span class="hero-obs-badge">실시간 관측</span>'

    # 메인 카드 하단 안내 카피와 체력 지수 간 톤앤매너 동기화
    stamina_info = preset_data.get("care_index", {}).get("stamina", {})
    stamina_level = stamina_info.get("level", "")
    cur_temp = cur.get("temp", 20)
    temp_max = cur.get("temp_max", cur_temp)
    alert_text = str(preset_data.get("weather_alert", ""))
    weather_text = str(cur.get("weather", ""))
    pty = cur.get("pty", 0)

    is_snow_cold = (pty in [2, 3]) or ("눈" in weather_text) or ("진눈깨비" in weather_text) or ("한파" in alert_text) or ("대설" in alert_text) or (cur_temp <= 3)
    is_heat_wave = (cur_temp >= 28) or (temp_max >= 28) or ("폭염" in alert_text) or ("열대야" in alert_text)

    if is_ended:
        guide_icon = "📌"
        guide_badge_text = "해당 축제 일정은 종료되었으나, 축제장 일원 산책을 위한 현장 날씨 정보를 제공합니다."
        guide_badge_class = "hero-guide-badge hero-guide-badge-ended"
    elif is_snow_cold or ("위험" in stamina_level):
        guide_icon = "❄️"
        guide_badge_text = "눈길·빙판으로 낙상 위험이 높고 체온 소모가 극심하니 야외 보행을 최소화하세요."
        guide_badge_class = "hero-guide-badge"
    elif "주의" in stamina_level:
        guide_icon = "🌿"
        guide_badge_text = "낮 시간대 기온이 다소 높으니 그늘 쉼터와 수분을 챙기며 안전하게 걸어보세요🌿"
        guide_badge_class = "hero-guide-badge"
    elif is_heat_wave or ("경고" in stamina_level):
        guide_icon = "☀️"
        guide_badge_text = "온열질환 위험이 있으니 직사광선을 피하고 그늘 쉼터에서 수시로 수분을 섭취하세요."
        guide_badge_class = "hero-guide-badge"
    elif cur.get("rain_prob", 0) >= 50 or (pty in [1, 4]) or ("비" in weather_text):
        guide_icon = "🌂"
        guide_badge_text = "비 예보가 있어요! 실내 대체 명소나 우산을 챙겨주세요 🌂"
        guide_badge_class = "hero-guide-badge"
    elif cur.get("wind_speed", 0) >= 3.5 or ("강풍" in alert_text):
        guide_icon = "🧣"
        guide_badge_text = "바람이 다소 강해요. 겉옷을 챙겨 체온을 유지하세요 🧣"
        guide_badge_class = "hero-guide-badge"
    else:
        guide_icon = "✨"
        guide_badge_text = cur.get("guide_badge") or f"{fest_name} 야외 관람과 걷기에 완벽한 쾌적한 날씨예요 🌿"
        guide_badge_class = "hero-guide-badge"

    hourly_cards_html = []
    for h in hourly_list:
        hourly_cards_html.append(f"""
        <div class="hourly-pill-card">
            <span class="hourly-time">{h['time']}</span>
            <span class="hourly-icon">{h['icon']}</span>
            <span class="hourly-temp">{h['temp']}°</span>
            <span class="hourly-rain">💧 {h['rain']}%</span>
        </div>
        """)

    stage_1_html = f"""
    <div class="widescreen-stage-row1">
        <!-- 1. 좌측: 대형 실시간 날씨 히어로 카드 -->
        <div class="bento-hero-weather">
            <div>
                <div class="hero-weather-top">
                    <div>
                        <span class="hero-region-badge">📍 {loc_badge}</span>
                        <h2 class="hero-loc-title">{fest_name} 현장 날씨</h2>
                        <div class="hero-fest-dates">{loc_full_addr} · {dates}</div>
                    </div>
                    <div class="hero-top-badges-group">
                        <span class="hero-alert-badge">⚡ {weather_alert}</span>
                        {obs_badge_html}
                    </div>
                </div>

                <div class="hero-weather-center">
                    <div class="hero-weather-big-icon">{cur['icon']}</div>
                    <div>
                        <div class="hero-current-temp">{cur['temp']}°C</div>
                        <div class="hero-feels-like">체감 온도 {cur['feels_like']}°C · {cur['weather']}</div>
                        <div class="hero-temp-range">최저 {cur['temp_min']}°C / 최고 {cur['temp_max']}°C</div>
                    </div>
                </div>
            </div>

            <div class="{guide_badge_class}">
                <span style="font-size:1.15rem;">{guide_icon}</span>
                <span>{guide_badge_text}</span>
            </div>
        </div>

        <!-- 2. 우측: 2단 복합 Bento (환경 지표 4종 + 시간대별 예보 슬라이더) -->
        <div class="widescreen-right-stack">
            <!-- 상단: 환경 지표 4종 -->
            <div class="bento-env-stats-card">
                <div class="env-stat-title">
                    <span>📊 상세 여행 환경 지표</span>
                    <span style="font-size:0.72rem; color:#059669; font-weight:700;">쾌적도 S등급</span>
                </div>
                <div class="env-metrics-grid-4">
                    <div class="env-metric-item">
                        <span class="env-metric-label">🌧️ 강수확률</span>
                        <span class="env-metric-val">{cur['rain_prob']}%</span>
                    </div>
                    <div class="env-metric-item">
                        <span class="env-metric-label">💧 대기습도</span>
                        <span class="env-metric-val">{cur['humidity']}%</span>
                    </div>
                    <div class="env-metric-item">
                        <span class="env-metric-label">💨 풍속</span>
                        <span class="env-metric-val">{cur['wind_speed']} m/s</span>
                    </div>
                    <div class="env-metric-item">
                        <span class="env-metric-label">🍃 미세먼지</span>
                        <span class="env-metric-val" style="color:#059669;">{cur['dust_status'].split(' ')[0]}</span>
                    </div>
                </div>
            </div>

            <!-- 하단: 시간대별 축제 현장 예보 (오전/오후) -->
            <div class="bento-hourly-card">
                <div class="env-stat-title">
                    <span>⏱️ 시간대별 현장 예보</span>
                    <span style="font-size:0.72rem; color:#6B7280;">기상청 단기예보</span>
                </div>
                <div class="scroll-rail-hourly">
                    {"".join(hourly_cards_html)}
                </div>
            </div>
        </div>
    </div>
    """
    st.html(stage_1_html)


def render_widescreen_stage_2_and_cta(preset_data: Dict[str, Any]):
    """
    하단 균등 4단 카드 그리드 (Equal Height) & Next Action CTA 배너:
    1. 4개 카드 (주간 5일 예보, 체력 맞춤 인덱스, 오늘 필수 준비물, 주변 실내 힐링 명소)
    2. 강수확률 50% 이상 시 우천 안심 플랜 하이라이트 활성화
    3. 하단 전체 폭 연결 CTA 배너 -> 여행 코스 화면(?view=course) 연동
    """
    fest_name = preset_data["festival_name"]
    loc_sdo = preset_data["region_sdo"]
    short_region = REGION_FULL_TO_SHORT.get(loc_sdo, loc_sdo[:2])
    weekly_list = preset_data.get("weekly", [])
    care = preset_data.get("care_index", {})
    stamina = care.get("stamina", {})
    prep_items = care.get("prep_items", [])
    indoor = care.get("indoor_spot", {})
    cur = preset_data.get("current", {})

    cur_temp = cur.get("temp", 20)
    weather_text = str(cur.get("weather", ""))
    alert_text = str(preset_data.get("weather_alert", ""))
    pty = cur.get("pty", 0)

    # 1. 눈/빙판/한파 조건 검사 (기상청 PTY=눈/진눈깨비 또는 기온 3°C 이하, 한파/대설특보)
    is_snow_cold = (pty in [2, 3]) or ("눈" in weather_text) or ("진눈깨비" in weather_text) or ("한파" in alert_text) or ("대설" in alert_text) or (cur_temp <= 3)

    # 2. 무더위/폭염 조건 검사 (기온 28°C 이상 또는 폭염특보)
    is_heat_wave = (cur_temp >= 28) or ("폭염" in alert_text) or ("열대야" in alert_text)

    # --------------------------------------------------------------------------
    # 동행인(st.session_state.companion) 조건에 따른 체력 지수 및 필수 준비물 동적 분기
    # --------------------------------------------------------------------------
    raw_comp = (
        st.session_state.get("companion")
        or st.query_params.get("companion")
        or st.session_state.get("active_companion_param")
        or ""
    )
    companion_raw = str(raw_comp).strip().lower()

    if any(k in companion_raw for k in ["부모", "parent"]):
        comp_key = "parents"
    elif any(k in companion_raw for k in ["아이", "family", "패밀리", "child", "키즈"]):
        comp_key = "child"
    elif any(k in companion_raw for k in ["반려견", "반려동물", "pet", "강아지"]):
        comp_key = "pet"
    else:
        comp_key = "general"

    COMPANION_DYNAMIC_CARE = {
        "parents": {
            "stamina": {
                "level": "주의 요망 (지수 55/100)",
                "desc": "관절 보호와 체온 유지가 최우선입니다. 경사로 대신 완만한 평지 데크길을 이용하시고, 30분 간격으로 온기 있는 쉼터에서 휴식을 취하세요.",
                "color": "#F59E0B",
                "recommended_time": "11:00 ~ 15:30 (따뜻한 낮 시간)"
            },
            "prep_items": [
                {"item": "미끄럼 방지화", "icon": "👟", "reason": "관절 보호 및 안전 보행"},
                {"item": "얇은 담요", "icon": "🧣", "reason": "체온 유지 및 찬바람 대비"},
                {"item": "따뜻한 물", "icon": "🍵", "reason": "수분 섭취 및 온기 유지"}
            ]
        },
        "child": {
            "stamina": {
                "level": "보통 (지수 45/100)",
                "desc": "호흡기 보호와 위생 관리가 핵심입니다. 찬바람과 미세먼지를 차단하고 실내 편의시설 동선을 미리 확보해 주세요.",
                "color": "#0284C7",
                "recommended_time": "13:00 ~ 16:30 (햇살 따스한 시간)"
            },
            "prep_items": [
                {"item": "유모차 방풍 커버", "icon": "👶", "reason": "호흡기 보호 및 찬바람 차단"},
                {"item": "유아용 물티슈", "icon": "🧻", "reason": "위생 관리 및 청결 유지"},
                {"item": "휴대용 비상약", "icon": "💊", "reason": "응급 상황 및 상비약 대비"}
            ]
        },
        "pet": {
            "stamina": {
                "level": "보통 (지수 45/100)",
                "desc": "해충 방지와 발바닥 보호가 강조됩니다. 잔디밭 풀숲 진드기에 주의하시고, 보도블록 지면 온도와 발바닥 상태를 수시로 체크하세요.",
                "color": "#D97706",
                "recommended_time": "10:00 ~ 12:00 / 15:00 ~ 17:00"
            },
            "prep_items": [
                {"item": "진드기 기피제", "icon": "🧴", "reason": "해충 방지 및 풀숲 산책"},
                {"item": "배변 봉투", "icon": "🐕", "reason": "펫티켓 및 청결 유지"},
                {"item": "휴대용 물통", "icon": "💧", "reason": "탈수 예방 및 발바닥 세척"}
            ]
        },
        "general": {
            "stamina": {
                "level": "쾌적 (지수 35/100)",
                "desc": "가벼운 활동성을 강조한 최적의 코스입니다. 축제장 도보 동선이 여유로우니 사진 촬영과 길거리 미식을 자유롭게 즐겨보세요.",
                "color": "#10B981",
                "recommended_time": "13:00 ~ 17:30 (활동 최적기)"
            },
            "prep_items": [
                {"item": "보조 배터리", "icon": "🔋", "reason": "사진 촬영 및 배터리 확보"},
                {"item": "텀블러", "icon": "☕", "reason": "개인위생 및 수분 보충"},
                {"item": "가벼운 외투", "icon": "🧥", "reason": "일몰 후 일교차 체온 보호"}
            ]
        }
    }

    comp_care = COMPANION_DYNAMIC_CARE[comp_key]
    stamina = dict(comp_care["stamina"])
    prep_items = list(comp_care["prep_items"])

    # 극한 기상(한파/폭염) 특보 연동 보정
    if is_snow_cold:
        stamina["level"] = "위험 (지수 90/100)"
        stamina["color"] = "#6D28D9"
        stamina["desc"] = f"눈길·빙판 체온 소모 주의! {stamina['desc']}"
        stamina["recommended_time"] = "12:00 ~ 14:30 (햇살 시간대)"
        if comp_key == "parents":
            prep_items[0] = {"item": "방한 미끄럼 방지화", "icon": "🥾", "reason": "빙판 낙상 및 관절 보호"}
        elif comp_key == "child":
            prep_items[0] = {"item": "방한 방풍 커버", "icon": "👶", "reason": "혹한 바람 차단 및 보온"}
        elif comp_key == "pet":
            prep_items[1] = {"item": "보온 신발 / 패딩", "icon": "🐕", "reason": "발바닥 동상 및 염화칼슘 차단"}
        else:
            prep_items[0] = {"item": "핫팩 / 방한 장갑", "icon": "🧤", "reason": "손발 동상 및 체온 저하 방지"}
    elif is_heat_wave:
        stamina["level"] = "경고 (지수 85/100)"
        stamina["color"] = "#DC2626"
        stamina["desc"] = f"온열질환 위험 주의! {stamina['desc']}"
        stamina["recommended_time"] = "09:00 ~ 11:00 / 17:00 이후"
        if comp_key == "parents":
            prep_items[2] = {"item": "이온음료 / 시원한 물", "icon": "🧊", "reason": "탈수 방지 및 체온 조절"}
        elif comp_key == "child":
            prep_items[0] = {"item": "쿨링 썬커버", "icon": "👶", "reason": "자외선 차단 및 열사병 예방"}
        elif comp_key == "pet":
            prep_items[2] = {"item": "얼음물 휴대 물통", "icon": "🧊", "reason": "열사병 예방 및 발바닥 냉각"}
        else:
            prep_items[0] = {"item": "양산 / 자외선 차단 모자", "icon": "👒", "reason": "직사광선 차단 및 두피 보호"}

    # 강수확률 50% 이상 시 우천 안심 플랜 자동 활성화
    rain_prob = cur.get("rain_prob", 0)
    is_rain_alert = rain_prob >= 50
    if is_rain_alert:
        rain_tag_html = '<span style="color:#DC2626; font-weight:800; background:#FEE2E2; padding:2px 8px; border-radius:6px;">🚨 우천 안심 플랜 가동!</span>'
        indoor_box_custom_style = 'border: 2px solid #059669; background: #ECFDF5; box-shadow: 0 4px 14px rgba(5, 150, 105, 0.18);'
    else:
        rain_tag_html = '<span>🌧️ 우천/돌풍 안심 플랜</span>'
        indoor_box_custom_style = ''

    # 1) 주간 예보 행 HTML
    weekly_rows_html = []
    for w in weekly_list:
        weekly_rows_html.append(f"""
        <div class="weekly-row-item">
            <div style="display:flex; align-items:center; gap:6px; width:74px;">
                <strong style="color:#14382B; font-size:0.78rem;">{w['day']}</strong>
                <span style="font-size:0.70rem; color:#6B7280;">{w['date'].split('(')[0]}</span>
            </div>
            <div style="font-size:1.05rem;">{w['icon']}</div>
            <div style="font-size:0.78rem; font-weight:800; color:#14382B;">
                {w['min']}°/<span style="color:#B45309;">{w['max']}°</span>
            </div>
            <div style="font-size:0.70rem; color:#0284C7; font-weight:700; width:40px; text-align:right;">
                💧{w['rain']}%
            </div>
        </div>
        """)

    # 2) 준비물 뱃지 HTML
    prep_badges_html = []
    for item in prep_items:
        prep_badges_html.append(f"""
        <div class="prep-badge-item">
            <span class="prep-badge-icon">{item['icon']}</span>
            <strong class="prep-badge-title">{item['item']}</strong>
            <span class="prep-badge-reason">{item['reason']}</span>
        </div>
        """)

    # 3) 실내 명소 대표 썸네일 이미지 (고화질 안심 문화쉼터/갤러리 실사)
    indoor_thumb_img = indoor.get("image") or "https://images.unsplash.com/photo-1518998053901-5348d3961a04?auto=format&fit=crop&w=500&q=80"

    # 4) 여행코스 연결 URL (선택된 축제명을 URI 인코딩하여 메인 매거진 발행 파라미터로 정밀 연동)
    course_cta_url = f"?select_fest_and_go={urllib.parse.quote(fest_name.strip())}"

    # 5) Next Action CTA 배너 문구 및 톤앤매너 설정
    is_ended = preset_data.get("is_ended", False)
    if is_ended:
        cta_icon = "🌿"
        cta_title = f"{fest_name} 축제 일정은 종료되었지만 산책하기 좋아요!"
        cta_sub = "해당 축제 일정은 종료되었으나, 축제장 일원 산책과 함께 즐길 수 있는 추천 여행 코스를 확인해보세요."
        cta_btn_text = "축제장 인근 힐링 산책 코스 보러가기 →"
    elif "주의" in stamina.get("level", ""):
        cta_icon = "🌤️"
        cta_title = f"{fest_name} 현장 나들이, 쉼터와 수분을 챙겨보세요!"
        cta_sub = "낮 시간대 기온을 고려한 여유롭고 쾌적한 맞춤 여행 코스를 확인해보세요."
        cta_btn_text = "이 날씨 맞춤 코스 보러가기 →"
    elif is_heat_wave:
        cta_icon = "🥤"
        cta_title = f"{fest_name} 더위 안심! 시원한 그늘 쉼터 코스"
        cta_sub = "무더위를 피해 쾌적하게 즐길 수 있는 실내 & 그늘 명소를 확인해보세요."
        cta_btn_text = "시원한 실내 추천 코스 보러가기 →"
    elif is_snow_cold:
        cta_icon = "🧣"
        cta_title = f"{fest_name} 한파 대비! 따뜻한 실내 힐링 코스"
        cta_sub = "추위를 피해 따뜻한 차와 전시를 즐길 수 있는 추천 코스를 확인해보세요."
        cta_btn_text = "따뜻한 실내 추천 코스 보러가기 →"
    else:
        cta_icon = "☀️"
        cta_title = f"{fest_name}의 날씨가 완벽해요!"
        cta_sub = "이 날씨에 딱 맞는 맞춤 여행 코스를 확인해보세요."
        cta_btn_text = "이 날씨 맞춤 코스 보러가기 →"

    bottom_html = f"""
    <!-- 하단 4단 카드 그리드 (Equal Height) -->
    <div class="care-bottom-4cards-grid">
        <!-- 1. 축제 주간 5일 예보 -->
        <div class="care-equal-card">
            <div>
                <div class="care-card-tag">
                    <span>📅 중기 기상 전망</span>
                </div>
                <h3 class="care-card-title">축제 주간 5일 예보</h3>
            </div>
            <div class="care-card-body-grow">
                {"".join(weekly_rows_html)}
            </div>
            <div style="font-size:0.70rem; color:#6B7280; text-align:right;">
                기상청 주간 전망 기준
            </div>
        </div>

        <!-- 2. 체력 맞춤 인덱스 -->
        <div class="care-equal-card">
            <div>
                <div class="care-card-tag">
                    <span>🏃 체력 맞춤 인덱스</span>
                </div>
                <h3 class="care-card-title">야외 도보 체력 지수</h3>
            </div>
            <div class="care-card-body-grow">
                <div style="font-size:1.08rem; font-weight:900; color:{stamina.get('color', '#10B981')}; margin-bottom:6px;">
                    {stamina.get('level', '보통')}
                </div>
                <div style="font-size:0.80rem; color:#4B5563; line-height:1.5;">
                    {stamina.get('desc', '')}
                </div>
            </div>
            <div style="background:#F9FAFB; padding:7px 10px; border-radius:10px; border:1px solid #F3F4F6; font-size:0.74rem; color:#4B5563;">
                ⏰ <strong>활동 추천:</strong> {stamina.get('recommended_time', '14:00~17:00')}
            </div>
        </div>

        <!-- 3. 오늘 필수 준비물 -->
        <div class="care-equal-card">
            <div>
                <div class="care-card-tag">
                    <span>🎒 필수 챙김 가이드</span>
                </div>
                <h3 class="care-card-title">오늘 필수 준비물</h3>
            </div>
            <div class="care-card-body-grow">
                <div class="prep-badges-wrap">
                    {"".join(prep_badges_html)}
                </div>
            </div>
            <div style="font-size:0.70rem; color:#059669; font-weight:700;">
                ✓ 현장 기상 분석 기반 스마트 체크리스트
            </div>
        </div>

        <!-- 4. 주변 실내 힐링 명소 (우천/돌풍 안심 플랜 비주얼 강화) -->
        <div class="care-equal-card">
            <div>
                <div class="care-card-tag">
                    {rain_tag_html}
                </div>
                <h3 class="care-card-title">주변 실내 힐링 명소</h3>
            </div>
            <div class="care-card-body-grow">
                <div class="indoor-spot-box" style="{indoor_box_custom_style}">
                    <div class="indoor-thumb-container">
                        <img src="{indoor_thumb_img}" alt="{indoor.get('name', '실내 쉼터')}" class="indoor-spot-thumb" onerror="this.src='https://images.unsplash.com/photo-1518998053901-5348d3961a04?auto=format&fit=crop&w=500&q=80'" />
                        <span class="indoor-thumb-badge">🏛️ 실내 안심 쉼터</span>
                    </div>
                    <div class="indoor-spot-title">
                        <span>{indoor.get('name', '실내 쉼터')}</span>
                        <span class="indoor-spot-dist">{indoor.get('distance', '인근')}</span>
                    </div>
                    <div class="indoor-spot-desc">
                        {indoor.get('desc', '')}
                    </div>
                    <div class="indoor-tags-row">
                        <span class="indoor-tag-chip">♿ 휠체어/유모차 평지 진입</span>
                        <span class="indoor-tag-chip">🍵 따뜻한 차 & 쉼터</span>
                        <span class="indoor-tag-chip">🎨 실내 상설 전시</span>
                    </div>
                </div>
            </div>
            <div style="font-size:0.70rem; color:#047857; line-height:1.3;">
                💡 <strong>안심 포인트:</strong> {indoor.get('highlight', '')}
            </div>
        </div>
    </div>

    <!-- 하단 액션 바 (Next Action CTA 배너) -->
    <div class="care-next-action-banner">
        <div class="banner-left-content">
            <span class="banner-icon">{cta_icon}</span>
            <div class="banner-text-wrap">
                <div class="banner-title-text">{cta_title}</div>
                <div class="banner-sub-text">{cta_sub}</div>
            </div>
        </div>
        <div>
            <a href="{course_cta_url}" target="_self" class="banner-cta-btn">
                <span>{cta_btn_text}</span>
            </a>
        </div>
    </div>
    """
    st.html(bottom_html)


# ------------------------------------------------------------------------------
# 4. 전체 화면 메인 조립 렌더러
# ------------------------------------------------------------------------------
def render_weather_care_page():
    """FestaPick 안심 날씨 케어 전용 상세 UI 메인 실행 함수 (16:9 와이드스크린 최적화)"""
    st.markdown(get_weather_care_css(), unsafe_allow_html=True)

    # 1. 상단 네비게이션 ('← 메인으로 돌아가기')
    render_header_nav()

    # [상단 동행인 맞춤 안내 마이크로 배너]
    try:
        from festapick.infra_curator import get_companion_micro_banner_html
        raw_comp = st.session_state.get("companion") or st.query_params.get("companion") or st.session_state.get("active_companion_param")
        companion_banner_html = get_companion_micro_banner_html(raw_comp, service_type="weather")
    except TypeError:
        try:
            companion_banner_html = get_companion_micro_banner_html(raw_comp)
        except Exception:
            companion_banner_html = ""
    except Exception:
        companion_banner_html = ""

    if companion_banner_html:
        st.html(companion_banner_html)

    # 2. 3단계 상단 셀렉터 필터바 ([지역 (시/도)] -> [상세 지역 및 축제] -> [여행 일정 (날짜)])
    sdo, fest, travel_date = render_selector_bar()

    # 3. 실시간 공공데이터 기상청 날씨 API 수집 및 축제 위치 기반 바인딩
    live_weather_data = get_live_weather_for_festival(sdo, fest, travel_date)

    # 4. 16:9 Stage Row 1 (중단 대시보드: 메인 히어로 + 환경 지표 4종 & 시간별 예보)
    render_widescreen_stage_1(live_weather_data)

    # 5. 하단 4단 카드 그리드 높이 균일화 & Next Action CTA 배너
    render_widescreen_stage_2_and_cta(live_weather_data)


if __name__ == "__main__":
    st.set_page_config(
        page_title="FestaPick 안심 날씨 케어",
        page_icon="🌤️",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    render_weather_care_page()
