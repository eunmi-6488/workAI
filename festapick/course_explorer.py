"""
festapick/course_explorer.py - 2026년 10월 가을 시즌 프리미엄 매거진 에디토리얼 여행코스 & 축제 큐레이션 뷰
================================================================================
[중요 원칙 - 기능 무결성 100% 보존]
- 기존 지역 클릭 이벤트(exp_region), 상태 관리(st.session_state), 데이터 필터링 로직 100% 동일 유지
- '부산' 클릭 시 정확히 부산 데이터가 필터링되도록 기존 데이터 매핑 구조 완벽 보존
- 테마별 필터(exp_theme), 정렬 필터(exp_sort), 1일 코스 연동 쿼리 파라미터 100% 유지

[디자인 리뉴얼 사양]
1. 상단 헤더: 매거진 에디토리얼 감성 (타이포그래피 & 문구)
   - 폰트: 대제목 Noto Serif KR / Playfair Display, 본문 Pretendard
   - 카피:
     ① [VOL. 02 · AUTUMN CURATION] 배지와 "2026 대한민국 가을의 순간들"
     ② 메인 타이틀: "바람 따라 머무는 곳, 10월의 로컬 여정" (명조 폰트, 딥그린 #14382B)
     ③ 에디토리얼 서문: "찬 바람이 기분 좋게 닿는 계절, 붐비지 않는 쉼과 이야기를 품은 전국 465곳의 축제와 산책길을 에디터의 시선으로 엮었습니다."
   - 하단 1px 베이지 라인 구분선
2. 지역 선택 영역: 18개 원형 아이콘 ➔ 가로 스크롤 미니멀 정갈한 텍스트 칩으로 UI 교체
   - [전체 465] [서울 68] [부산 27] [대구 16] [인천 18] ...
   - 선택된 칩: 딥그린 배경(#14382B) + 흰색 텍스트
   - 미선택 칩: 연한 크림색 테두리 + 차분한 텍스트
3. 필터 & 툴바 통합:
   - 좌측: "총 N개의 큐레이션 코스"
   - 우측: 테마 필터 칩 + 정렬 칩(인기순 / 최신순 / 무장애 안심순)을 카드 목록 위 단일 툴바로 일원화
4. 카드 리스트 UI 정돈:
   - 썸네일 비율(16:9) 및 이미지 object-cover 통일
   - 카드 하단 텍스트 위계 3줄 구조: [지역 뱃지] ➔ [축제·코스명] ➔ [개최 기간]
   - 찜(하트) 아이콘 위치: 우측 상단 반투명 원형 버튼으로 통일
5. 전체 스타일: FestaPick 메인 아이보리(#FDFBF7) 유지
================================================================================
"""

import os
import re
import json
import html
import urllib.parse
from datetime import date, datetime
from typing import Dict, List, Any, Optional
import streamlit as st

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CURRENT_DIR, "data")
MASTER_2026_JSON = os.path.join(DATA_DIR, "master_2026_oct_festivals.json")
FESTIVALS_CSV = os.path.join(DATA_DIR, "festivals.csv")
NAVER_POSTER_CACHE_JSON = os.path.join(DATA_DIR, "festival_poster_naver_cache.json")


def get_naver_poster_cache() -> Dict[str, str]:
    if os.path.exists(NAVER_POSTER_CACHE_JSON):
        try:
            with open(NAVER_POSTER_CACHE_JSON, "r", encoding="utf-8") as _f:
                return json.load(_f)
        except Exception:
            return {}
    return {}


try:
    from festapick.fallback_assets import DEFAULT_FESTIVAL_GRAPHIC_DATA_URI
except Exception:
    DEFAULT_FESTIVAL_GRAPHIC_DATA_URI = "https://images.unsplash.com/photo-1506157786151-b8491531f063?auto=format&fit=crop&w=800&q=80"

# 18개 시·도 기본 목록
REGION_LIST_ORDER = [
    "전체", "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"
]

# 7대 권역 원형(Circle) 메뉴 목록 및 로컬 랜드마크 이모지 매핑
ZONE_OPTIONS = ["전국", "수도권", "충청권", "강원권", "호남권", "영남권", "제주"]

ZONE_ICONS = {
    "전국": "🗺️",
    "수도권": "🗼",
    "충청권": "🏞️",
    "강원권": "🌲",
    "호남권": "🌾",
    "영남권": "🌊",
    "제주": "🏝️",
}

ZONE_REGIONS = {
    "전국": [],
    "전체": [],
    "수도권": ["서울", "경기", "인천"],
    "충청권": ["대전", "세종", "충남", "충북"],
    "강원권": ["강원"],
    "호남권": ["광주", "전남", "전북"],
    "영남권": ["부산", "대구", "울산", "경북", "경남"],
    "제주": ["제주"],
}

REGION_TO_ZONE = {}
for _z, _r_list in ZONE_REGIONS.items():
    if _z in ["전국", "전체"]:
        continue
    for _r in _r_list:
        REGION_TO_ZONE[_r] = _z


def load_all_festivals_and_events() -> List[Dict[str, Any]]:
    """2026년 10월 가을 시즌 전국 축제 마스터 데이터를 실시간으로 로드하며 중복 축제를 1개만 남기고 정제합니다."""
    if os.path.exists(MASTER_2026_JSON):
        try:
            with open(MASTER_2026_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data and len(data) > 0:
                    # [무결점 중복 제거 엔진] 동일 지역·동일 축제의 중복 등록 방어
                    deduped = []
                    seen_keys = set()
                    for item in data:
                        raw_t = str(item.get("title", "")).strip()
                        t = re.sub(r"202[0-9]\s*", "", raw_t)
                        t = re.sub(r"제\s*[0-9]+회\s*", "", t)
                        t = re.sub(r"\(.*?\)|\[.*?\]", "", t)
                        for p in ["경북", "경남", "전북", "전남", "충북", "충남", "강원", "경기", "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "제주"]:
                            if t.startswith(p) and len(t) > len(p) + 2:
                                t = t[len(p):].strip()
                                break
                        t = re.sub(r"[\s\-_·,]+", "", t)
                        t = re.sub(r"(축제|대축제|페스티벌|문화제)$", "", t)
                        reg = item.get("region", "")
                        
                        k = (reg, t) if len(t) >= 2 else (reg, raw_t)
                        if k in seen_keys:
                            continue
                        seen_keys.add(k)
                        deduped.append(item)
                    return deduped
        except Exception:
            pass
    return []


def get_fallback_banner(region: str) -> str:
    """지역별 고화질 풍경 기본 이미지"""
    fallbacks = {
        "전남": "https://images.unsplash.com/photo-1470240731273-7821a6eeb6bd?auto=format&fit=crop&w=800&q=80",
        "충남": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
        "경기": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=800&q=80",
        "서울": "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=800&q=80",
        "부산": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
        "강원": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=800&q=80",
        "경북": "https://images.unsplash.com/photo-1514565131-fce0801e5785?auto=format&fit=crop&w=800&q=80",
        "경남": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80",
        "전북": "https://images.unsplash.com/photo-1528127269322-539801943592?auto=format&fit=crop&w=800&q=80",
        "충북": "https://images.unsplash.com/photo-1511497584788-87676104235f?auto=format&fit=crop&w=800&q=80",
        "제주": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=800&q=80",
        "인천": "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=800&q=80",
        "대구": "https://images.unsplash.com/photo-1477959858617-67f30bc75b82?auto=format&fit=crop&w=800&q=80",
        "대전": "https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=800&q=80",
        "광주": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=800&q=80",
        "울산": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=800&q=80",
        "세종": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=800&q=80",
    }
    return fallbacks.get(region, DEFAULT_FESTIVAL_GRAPHIC_DATA_URI)


def classify_item_category(item: Dict[str, Any]) -> str:
    """공공데이터 기반 코스/행사 카테고리 3대 분류 ('로컬 축제', '자연·힐링', '역사·문화')"""
    cat = str(item.get("category", "")).lower()
    title = str(item.get("title", "")).lower()
    
    nature_kw = [
        "자연", "힐링", "숲", "수목원", "공원", "호수", "정원", "생태", "산책", 
        "둘레길", "코스", "갈대", "억새", "단풍", "국화", "꽃", "바다", "해변", 
        "비치", "섬", "휴양", "온천", "녹차", "맨발", "계곡", "폭포", "나눔길"
    ]
    culture_kw = [
        "역사", "문화", "예술", "박물관", "유적", "서원", "향교", "궁", "성터", 
        "전승", "제향", "민속", "음악", "연극", "공연", "전시", "도자기", "미술", 
        "비엔날레", "문학", "전통", "사찰", "산성", "국악", "영화"
    ]

    if cat == "course" or any(k in title for k in nature_kw):
        return "자연·힐링"
    elif cat == "culture" or any(k in title for k in culture_kw):
        return "역사·문화"
    else:
        return "로컬 축제"


def is_barrier_free_course(item: Dict[str, Any]) -> bool:
    """무장애 완경사 편의 코스 판별"""
    text = (str(item.get("title", "")) + " " + str(item.get("addr", ""))).lower()
    barrier_kw = [
        "무장애", "열린관광", "완경사", "편의", "안심", "힐링", "산책", 
        "공원", "생태", "데크", "자연", "숲길", "나눔길", "호수", "정원", "수목원", "갈대"
    ]
    return any(k in text for k in barrier_kw)


def get_item_stamina_intensity(item: Dict[str, Any]) -> int:
    """공공데이터 기반 코스/축제 난이도 및 체력 배터리 소모율 (낮을수록 가벼운 코스)"""
    title = str(item.get("title", "")).lower()
    cat = str(item.get("category", "")).lower()
    if any(k in title for k in ["무장애", "완경사", "나눔길", "호수", "수목원", "정원", "갈대", "억새", "산책"]):
        return 20
    elif cat == "course" or any(k in title for k in ["둘레길", "공원", "숲길", "생태", "단풍"]):
        return 35
    elif cat == "culture" or any(k in title for k in ["전시", "박물관", "미술관", "공연", "음악"]):
        return 40
    elif any(k in title for k in ["거리", "마당", "장터", "야시장"]):
        return 50
    else:
        return 45 + (abs(hash(title)) % 20)


def parse_festival_dates(item_or_dates: Any) -> tuple:
    """
    축제 딕셔너리 또는 날짜 문자열에서 (start_date, end_date) date 객체를 안전하게 추출합니다.
    - 지원 포맷: '20261001', '2026-10-01', '2026.10.01', '2026-10-01 ~ 2026-10-11', '2026.10.01 ~ 10.11' 등
    """
    if isinstance(item_or_dates, dict):
        s_raw = str(item_or_dates.get("startDate") or "").strip()
        e_raw = str(item_or_dates.get("endDate") or "").strip()
        dates_raw = str(item_or_dates.get("dates") or "").strip()
    else:
        s_raw = ""
        e_raw = ""
        dates_raw = str(item_or_dates or "").strip()

    # 1. 8자리 연속 숫자 (YYYYMMDD) 우선 파싱
    s_digits = re.sub(r"[^0-9]", "", s_raw)
    e_digits = re.sub(r"[^0-9]", "", e_raw)
    if len(s_digits) == 8:
        try:
            s_date = date(int(s_digits[:4]), int(s_digits[4:6]), int(s_digits[6:8]))
            e_date = date(int(e_digits[:4]), int(e_digits[4:6]), int(e_digits[6:8])) if len(e_digits) == 8 else s_date
            return s_date, e_date
        except Exception:
            pass

    # 2. 정규식 패턴 파싱 (YYYY[-./]MM[-./]DD)
    combined = f"{s_raw} {e_raw} {dates_raw}".strip()
    patterns = re.findall(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", combined)
    if patterns:
        try:
            s_date = date(int(patterns[0][0]), int(patterns[0][1]), int(patterns[0][2]))
            if len(patterns) >= 2:
                e_date = date(int(patterns[1][0]), int(patterns[1][1]), int(patterns[1][2]))
            else:
                # 2026.10.01 ~ 10.11 처럼 종료일 연도가 생략된 경우 매칭
                short_end = re.search(r"~\s*(\d{1,2})[-./](\d{1,2})", combined)
                if short_end:
                    e_date = date(s_date.year, int(short_end.group(1)), int(short_end.group(2)))
                else:
                    e_date = s_date
            return s_date, e_date
        except Exception:
            pass

    return None, None


def get_festival_date_sort_key(item: Dict[str, Any]) -> tuple:
    """
    개최 일정순 (빠른순) 실시간 정렬 기준 (datetime.date.today() 기반):
    1) 1순위: 현재 진행중인 축제 (s_date <= today <= e_date) 최우선!
       - tier 0: 당월(10월) 개막 진행중 -> tier 1: 이전 개막 장기/상설 진행중
    2) 2순위: 앞으로 열릴 개최예정 축제 (s_date > today, D-Day 빠른순 / 오름차순, tier 2)
    3) 3순위: 이미 종료된 축제 (e_date < today, 종료일 최근순 / 내림차순, tier 3 - 목록 뒤쪽으로 정돈)
    4) 4순위: 기타 날짜 미정 항목 (tier 4)
    """
    today = date.today()
    s_date, e_date = parse_festival_dates(item)

    if not s_date or not e_date:
        return (4, 0, 0)

    # 1. 진행중인 축제 (s_date <= today <= e_date)
    if s_date <= today <= e_date:
        tier = 0 if (today - s_date).days <= 30 else 1
        return (tier, -s_date.toordinal(), e_date.toordinal())

    # 2. 앞으로 열릴 개최예정 축제 (s_date > today, D-Day 빠른순)
    elif s_date > today:
        return (2, s_date.toordinal(), e_date.toordinal())

    # 3. 이미 종료된 축제 (e_date < today, 최근 종료된 순으로 목록 뒤쪽에 배치)
    else:
        return (3, -e_date.toordinal(), -s_date.toordinal())


def get_festival_status_badge(item_or_dates: Any) -> str:
    """
    [실시간 날짜 기반 자동 판별 축제 상태 뱃지 - app_demo.py와 통일]
    - 오늘이 축제 기간 내에 있는 경우: <span class="card-status-badge badge-live"><span class="live-dot">●</span> 진행중</span> (초록색)
    - 오늘이 축제 시작일 이전인 경우: <span class="card-status-badge badge-dday">D-{남은일수}</span> (주황/노란색)
    - 오늘이 축제 종료일 이후인 경우: <span class="card-status-badge badge-ended">종료</span> (차분한 회색)
    - 날짜 파싱이 불가능한 경우: <span class="card-status-badge badge-neutral">일정 확인 중</span>
    """
    s_date, e_date = parse_festival_dates(item_or_dates)
    if not s_date or not e_date:
        return '<span class="card-status-badge badge-neutral">일정 확인 중</span>'

    today = date.today()
    if s_date <= today <= e_date:
        return '<span class="card-status-badge badge-live"><span class="live-dot">●</span> 진행중</span>'
    elif today < s_date:
        diff_days = (s_date - today).days
        return f'<span class="card-status-badge badge-dday">D-{diff_days}</span>'
    else:
        return '<span class="card-status-badge badge-ended">종료</span>'


def get_course_explorer_css() -> str:
    """프리미엄 라이프스타일 매거진(Editorial) 전용 CSS 스타일시트"""
    return """
    <style>
    @import url('https://cdn.jsdelivr.net/gh/sun-typeface/maruburi@master/dist/web/font.css');
    @import url('https://cdn.jsdelivr.net/npm/font-kopubworld@1.0.3/kopubworldbatang.css');
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,600&family=Noto+Serif+KR:wght@500;600;700;900&display=swap');
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    /* 1. 글로벌 컨테이너: 아이보리 (#F9F8F3) & 딥그린 (#1B4332) */
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

    /* 2. 상단 헤더: 매거진 에디토리얼 감성 */
    .editorial-header-bar {
        padding: 10px 0 20px 0;
        border-bottom: 1.5px solid #EAE3D6;
        margin-bottom: 22px;
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
        font-size: 2.2rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: #012D1D;
        margin: 0 0 8px 0;
        line-height: 1.3;
    }
    .editorial-lead-text {
        font-size: 0.94rem;
        color: #4B5563;
        margin: 0;
        line-height: 1.6;
        max-width: 780px;
    }
    .editorial-header-actions {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
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
    .editorial-ghost-btn .btn-icon {
        font-size: 0.92rem;
        line-height: 1;
    }

    /* 3. 7대 권역 원형(Circle) 카테고리 칩 UI */
    .circle-zone-container {
        display: flex;
        align-items: flex-start;
        justify-content: center;
        gap: 28px;
        flex-wrap: wrap;
        padding: 6px 0 14px 0;
        margin: 0 auto;
        max-width: 1040px;
    }
    .circle-zone-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-decoration: none !important;
        cursor: pointer;
        background: transparent;
        border: none;
        outline: none;
        transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
        user-select: none;
        width: 76px;
    }
    .circle-zone-item:hover {
        transform: translateY(-4px);
    }
    .circle-symbol-avatar {
        width: 68px;
        height: 68px;
        border-radius: 50%;
        background-color: #FFFFFF;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
        border: 2px solid #EDE8DF;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 28px;
        transition: all 0.22s ease;
    }
    .circle-zone-item:hover .circle-symbol-avatar {
        border-color: #012D1D;
        box-shadow: 0 8px 20px rgba(1, 45, 29, 0.12);
    }
    .circle-zone-name {
        font-size: 14px;
        font-weight: 700;
        color: #4B5563;
        margin-top: 10px;
        letter-spacing: -0.01em;
        text-align: center;
        transition: color 0.2s ease, font-weight 0.2s ease;
    }
    .circle-zone-item:hover .circle-zone-name {
        color: #012D1D;
    }
    /* 활성화(Active) 스타일: 포레스트 그린(#012D1D) 2.5px 테두리 및 진한 폰트 */
    .circle-zone-item.active .circle-symbol-avatar {
        border: 2.5px solid #012D1D;
        background-color: #FFFFFF;
        box-shadow: 0 6px 18px rgba(1, 45, 29, 0.18);
        transform: scale(1.05);
    }
    .circle-zone-item.active .circle-zone-name {
        color: #012D1D;
        font-weight: 800;
    }

    /* 미니멀 은은한 가로선 (1줄) */
    .zone-subfilter-divider {
        border-bottom: 1px solid #ECE6DA;
        margin: 24px 0 20px 0;
        width: 100%;
    }

    /* 테마 세그먼트 컨트롤 */
    div[data-testid="stSegmentedControl"] {
        background-color: #EFECE6 !important;
        border-radius: 9999px !important;
        padding: 3px !important;
        border: 1px solid #DFD8CD !important;
        display: inline-flex !important;
        width: 100% !important;
    }
    div[data-testid="stSegmentedControl"] button {
        border-radius: 9999px !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        color: #4B5563 !important;
        padding: 6px 14px !important;
        border: none !important;
        background: transparent !important;
        transition: all 0.15s ease !important;
        flex: 1 1 auto !important;
    }
    div[data-testid="stSegmentedControl"] button:hover {
        color: #012D1D !important;
        background-color: rgba(255, 255, 255, 0.6) !important;
    }
    div[data-testid="stSegmentedControl"] button[aria-selected="true"],
    div[data-testid="stSegmentedControl"] button[aria-checked="true"] {
        background-color: #FFFFFF !important;
        color: #012D1D !important;
        font-weight: 800 !important;
        box-shadow: 0 2px 6px rgba(1, 45, 29, 0.12) !important;
    }

    /* 체크박스 완경사 무장애 안심 토글 */
    div[data-testid="stCheckbox"] {
        margin: 0 !important;
        display: flex !important;
        align-items: center !important;
        padding-top: 5px !important;
    }
    div[data-testid="stCheckbox"] label span {
        font-size: 0.83rem !important;
        font-weight: 700 !important;
        color: #1B4332 !important;
    }

    /* 정렬 셀렉트박스 */
    div[data-testid="stSelectbox"] {
        margin: 0 !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] {
        border-radius: 9999px !important;
        border: 1.5px solid #D8D2C5 !important;
        background-color: #FFFFFF !important;
        font-size: 0.82rem !important;
        font-weight: 700 !important;
        color: #1B4332 !important;
        transition: all 0.15s ease !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"]:hover {
        border-color: #1B4332 !important;
        box-shadow: 0 2px 8px rgba(27, 67, 50, 0.12) !important;
    }

    /* 5. 카드 리스트 UI (16:9 썸네일 & 3줄 위계 구조) */
    .editorial-cards-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 22px;
        margin-bottom: 50px;
    }
    .editorial-card {
        background: #FFFFFF;
        border: 1.5px solid #EAE3D6;
        border-radius: 18px;
        overflow: hidden;
        box-shadow: 0 4px 14px rgba(20, 56, 43, 0.04);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }
    .editorial-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 26px rgba(27, 67, 50, 0.12);
        border-color: #1B4332;
    }

    /* 썸네일: 16:9 비율 & object-fit: cover */
    .card-thumb-wrap {
        position: relative;
        width: 100%;
        aspect-ratio: 16 / 9;
        overflow: hidden;
        background-color: #08281B;
    }
    .card-thumb-img {
        width: 100%;
        height: 100%;
        aspect-ratio: 16 / 9;
        object-fit: cover;
        transition: transform 0.35s ease;
        display: block;
    }
    .editorial-card:hover .card-thumb-img {
        transform: scale(1.04);
    }

    /* 우측 상단 축제 상태 뱃지 (은색 하트 대체: 축제 종료 / 진행중 / 개최예정) */
    .card-status-badge {
        position: absolute;
        top: 10px;
        right: 10px;
        padding: 5px 11px;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: -0.01em;
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.18);
        z-index: 10;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        line-height: 1.2;
        user-select: none;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .card-status-badge:hover {
        transform: scale(1.05);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.25);
    }
    .card-status-badge.badge-active, .card-status-badge.badge-live, .badge-live {
        background: rgba(16, 185, 129, 0.94) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
    }
    .card-status-badge.badge-ended, .badge-ended {
        background: rgba(75, 85, 99, 0.90) !important;
        color: #E5E7EB !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }
    .card-status-badge.badge-upcoming, .card-status-badge.badge-dday, .badge-dday {
        background: rgba(245, 158, 11, 0.94) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
    }
    .card-status-badge.badge-neutral, .badge-neutral {
        background: rgba(107, 114, 128, 0.88) !important;
        color: #F3F4F6 !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }
    .live-dot {
        display: inline-block;
        font-size: 0.55rem;
        color: #A7F3D0;
        animation: pulseLiveDot 1.5s infinite;
    }
    @keyframes pulseLiveDot {
        0% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.35; transform: scale(0.8); }
        100% { opacity: 1; transform: scale(1); }
    }

    /* 카드 하단 3줄 위계 구조 */
    .card-content-body {
        padding: 16px 16px 12px 16px;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    /* 1줄: 지역 뱃지 */
    .card-loc-pill {
        display: inline-flex;
        align-self: flex-start;
        font-size: 0.72rem;
        font-weight: 800;
        color: #1B4332;
        background: #E8F5E9;
        border: 1px solid #C8E6C9;
        padding: 2px 8px;
        border-radius: 6px;
        letter-spacing: 0.02em;
    }
    /* 2줄: 축제·코스명 */
    .card-title-text {
        font-size: 1.05rem;
        font-weight: 800;
        color: #14382B;
        line-height: 1.35;
        margin: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        height: 2.7em;
    }
    /* 3줄: 개최 기간 */
    .card-date-text {
        font-size: 0.78rem;
        color: #6B7280;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 4px;
    }

    /* 카드 최하단 1일 힐링 코스 세팅 버튼 */
    .card-footer-action {
        padding: 10px 16px 16px 16px;
        border-top: 1px solid #F3EFE6;
    }
    .card-action-link {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        width: 100%;
        background: #FAF7F2;
        color: #14382B !important;
        font-size: 0.82rem;
        font-weight: 800;
        padding: 9px 0;
        border-radius: 10px;
        border: 1px solid #D8CFC0;
        text-decoration: none !important;
        transition: all 0.2s ease;
    }
    .card-action-link:hover {
        background: #1B4332;
        color: #FAF7F2 !important;
        border-color: #1B4332;
    }

    /* 8. 페이지네이션 (1 2 3 4 ... 순서 버튼 연결 UI) */
    .pagination-wrapper {
        margin-top: 40px;
        margin-bottom: 52px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 14px;
    }
    .pagination-info {
        font-size: 0.86rem;
        color: #6B7280;
        font-weight: 500;
    }
    .pagination-info strong {
        color: #14382B;
        font-weight: 700;
    }
    .pagination-btn-group {
        display: flex;
        align-items: center;
        gap: 6px;
        flex-wrap: wrap;
        justify-content: center;
    }
    .page-nav-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 38px;
        height: 38px;
        padding: 0 12px;
        border-radius: 8px;
        border: 1.5px solid #E5E7EB;
        background: #FFFFFF;
        color: #374151;
        font-size: 0.90rem;
        font-weight: 700;
        text-decoration: none !important;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        cursor: pointer;
        user-select: none;
    }
    .page-nav-btn:hover:not(.disabled):not(.active) {
        border-color: #012D1D;
        color: #012D1D;
        background: #F4EFE5;
        transform: translateY(-1px);
        box-shadow: 0 3px 8px rgba(0, 0, 0, 0.08);
    }
    .page-nav-btn.active {
        background: #012D1D !important;
        color: #FAF7F2 !important;
        border-color: #012D1D !important;
        font-weight: 800;
        cursor: default;
        box-shadow: 0 3px 10px rgba(1, 45, 29, 0.25);
    }
    .page-nav-btn.page-arrow {
        padding: 0 14px;
        font-size: 0.82rem;
        color: #1B4332;
    }
    .page-nav-btn.disabled {
        opacity: 0.4;
        cursor: not-allowed;
        background: #F9FAFB;
        border-color: #E5E7EB;
        color: #9CA3AF;
    }
    .page-ellipsis {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        color: #9CA3AF;
        font-weight: 700;
    }
    </style>
    """


# ------------------------------------------------------------------------------
# 2. [뷰 렌더러] render_course_explorer_page
# ------------------------------------------------------------------------------
def render_course_explorer_page():
    """프리미엄 매거진 에디토리얼 여행코스 & 축제 큐레이션 전용 뷰"""
    
    # CSS 스타일시트 주입
    st.markdown(get_course_explorer_css(), unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # 0. 쿼리 파라미터 및 세션 상태 동행인 통합 연동 (어떤 인터랙션에서도 유실 방지)
    from festapick.companion_context import (
        normalize_companion_key,
        score_festival_for_companion,
        get_profile,
        COMPANION_PROFILES,
    )

    raw_comp = st.session_state.get("companion") or st.query_params.get("companion") or st.session_state.get("active_companion_param") or ""
    comp_key = normalize_companion_key(raw_comp)
    is_companion_active = bool(comp_key) and str(raw_comp).strip().lower() not in ("none", "null", "skip", "선택 없이 둘러보기", "")

    if is_companion_active:
        companion_param = comp_key
        st.session_state["active_companion_param"] = comp_key
        if not st.session_state.get("companion") or str(st.session_state.get("companion")).strip().lower() in ("none", "null", ""):
            st.session_state["companion"] = COMPANION_PROFILES.get(comp_key, {}).get("label", comp_key)
    else:
        companion_param = ""
        st.session_state["active_companion_param"] = "none"

    target_fest_spotlight = None
    if "select_fest_and_go" in st.query_params:
        target_fest_spotlight = urllib.parse.unquote(str(st.query_params.get("select_fest_and_go", "")).strip())
        del st.query_params["select_fest_and_go"]
    elif st.session_state.get("course_target_fest"):
        target_fest_spotlight = str(st.session_state.get("course_target_fest", "")).strip()
        del st.session_state["course_target_fest"]

    if "exp_zone" in st.query_params:
        z_param = st.query_params.get("exp_zone")
        if z_param in ["전체", "전국"]:
            st.session_state.selectedZone = "전국"
        elif z_param in ZONE_OPTIONS:
            st.session_state.selectedZone = z_param
        del st.query_params["exp_zone"]

    if "exp_region" in st.query_params:
        r_param = st.query_params.get("exp_region")
        if r_param in ["전국", "전체"]:
            st.session_state.selectedZone = "전국"
        elif r_param in ZONE_OPTIONS:
            st.session_state.selectedZone = r_param
        elif r_param in REGION_TO_ZONE:
            st.session_state.selectedZone = REGION_TO_ZONE[r_param]
        del st.query_params["exp_region"]

    if "exp_theme" in st.query_params:
        t_param = st.query_params.get("exp_theme")
        theme_map = {"all": "전체", "festival": "로컬 축제", "nature": "자연·힐링", "course": "자연·힐링", "culture": "역사·문화"}
        if t_param in theme_map:
            st.session_state.selectedCategory = theme_map[t_param]
        elif t_param in ["전체", "로컬 축제", "자연·힐링", "역사·문화"]:
            st.session_state.selectedCategory = t_param
        del st.query_params["exp_theme"]

    if "exp_sort" in st.query_params:
        s_param = st.query_params.get("exp_sort")
        sort_map = {"date": "개최 일정순 (빠른순)", "name": "이름순 (가나다)", "stamina": "체력 배터리순 (가벼운 코스)"}
        if s_param in sort_map:
            st.session_state.sortOption = sort_map[s_param]
        elif s_param in ["개최 일정순 (빠른순)", "이름순 (가나다)", "체력 배터리순 (가벼운 코스)"]:
            st.session_state.sortOption = s_param
        del st.query_params["exp_sort"]

    # 세션 상태 기본값 초기화
    if "selectedZone" not in st.session_state or st.session_state.selectedZone not in ZONE_OPTIONS:
        st.session_state.selectedZone = "전국"
    if "selectedCategory" not in st.session_state or st.session_state.selectedCategory not in ["전체", "로컬 축제", "자연·힐링", "역사·문화"]:
        st.session_state.selectedCategory = "전체"
    if "sortOption" not in st.session_state or st.session_state.sortOption not in ["개최 일정순 (빠른순)", "이름순 (가나다)", "체력 배터리순 (가벼운 코스)"]:
        st.session_state.sortOption = "개최 일정순 (빠른순)"
    if "barrier_only" not in st.session_state:
        st.session_state.barrier_only = False

    # 전수 데이터 로드 (438건)
    all_events = load_all_festivals_and_events()

    # --------------------------------------------------------------------------
    # 1. 상단 헤더: 안심 큐레이션 정체성 서브카피 & 모던 고스트 버튼
    # --------------------------------------------------------------------------
    header_html = f"""
    <div class="editorial-header-bar">
        <div>
            <!-- ① 상단 라벨 -->
            <div class="editorial-meta-row">
                <span class="editorial-vol-badge">VOL. 02 · LOCAL CURATION</span>
                <span class="editorial-sub-badge">대한민국 로컬 큐레이션 매거진</span>
            </div>
            <!-- ② 메인 타이틀: 범용 감성 카피 -->
            <h1 class="editorial-main-title">취향과 발걸음을 잇는 로컬 큐레이션 여정</h1>
            <!-- ③ 에디토리얼 서문: 공공데이터 무장애 편의 및 체력 맞춤형 안심 카피 -->
            <p class="editorial-lead-text">
                공공데이터 기반 무장애 편의 정보와 체력 맞춤형 동선으로 설계된 전국 로컬 코스를 탐색해보세요.
            </p>
        </div>
        <!-- 우측 액션: 모던 아웃라인 캡슐 스타일 (Ghost Button) -->
        <div class="editorial-header-actions">
            <a href="?view=weather" target="_self" class="editorial-ghost-btn">
                <span class="btn-icon">🌤️</span>
                <span>날씨 확인</span>
            </a>
            <a href="?view=main" target="_self" class="editorial-ghost-btn" onclick="try{{sessionStorage.removeItem('festapick_active_companion');}}catch(e){{}}">
                <span class="btn-icon">←</span>
                <span>메인으로 돌아가기</span>
            </a>
        </div>
    </div>
    """
    st.html(header_html)

    # [상단 동행인 맞춤 안내 마이크로 배너]
    try:
        from festapick.infra_curator import get_companion_micro_banner_html
        micro_banner = get_companion_micro_banner_html(companion_param or st.session_state.get("companion"), service_type="course")
    except TypeError:
        try:
            micro_banner = get_companion_micro_banner_html(companion_param or st.session_state.get("companion"))
        except Exception:
            micro_banner = ""
    except Exception:
        micro_banner = ""

    if micro_banner:
        st.html(micro_banner)

    # --------------------------------------------------------------------------
    # 2. 7대 권역 원형(Circle) 카테고리 칩 UI (박스 테두리 제거 및 감성 큐레이션 메뉴)
    # --------------------------------------------------------------------------
    selected_zone = st.session_state.get("selectedZone", "전국")
    if selected_zone not in ZONE_OPTIONS:
        selected_zone = "전국"

    circle_items_html = []
    for z in ZONE_OPTIONS:
        icon = ZONE_ICONS.get(z, "🗺️")
        is_active = (selected_zone == z) or (selected_zone in ["전국", "전체"] and z == "전국")
        active_cls = " active" if is_active else ""
        comp_url_part = f"&companion={urllib.parse.quote(companion_param)}" if is_companion_active else ""
        link_href = f"?view=course&exp_zone={urllib.parse.quote(z)}{comp_url_part}"
        circle_items_html.append(f"""
        <a href="{link_href}" target="_self" class="circle-zone-item{active_cls}">
            <div class="circle-symbol-avatar">{icon}</div>
            <span class="circle-zone-name">{z}</span>
        </a>
        """)

    zone_nav_html = f"""
    <div class="circle-zone-container">
        {"".join(circle_items_html)}
    </div>
    <div class="zone-subfilter-divider"></div>
    """
    st.html(zone_nav_html)

    # --------------------------------------------------------------------------
    # 3. 서브 컨트롤 한 줄 정렬: 좌측 미니멀 테마 칩 / 우측 완경사 + 정렬 드롭다운
    # --------------------------------------------------------------------------
    col_theme, col_right = st.columns([5.2, 4.8], vertical_alignment="center")

    with col_theme:
        cat_val = st.segmented_control(
            "테마 분류",
            options=["전체", "로컬 축제", "자연·힐링", "역사·문화"],
            key="selectedCategory",
            label_visibility="collapsed"
        )
        current_category = cat_val or "전체"

    with col_right:
        col_barrier, col_sort = st.columns([4.2, 5.8], vertical_alignment="center")
        with col_barrier:
            barrier_val = st.checkbox(
                "♿ 완경사 안심 코스만",
                key="barrier_only"
            )
            current_barrier_only = bool(barrier_val)
        with col_sort:
            sort_options = ["개최 일정순 (빠른순)", "이름순 (가나다)", "체력 배터리순 (가벼운 코스)"]
            sort_val = st.selectbox(
                "정렬 기준",
                options=sort_options,
                key="sortOption",
                label_visibility="collapsed"
            )
            current_sort = sort_val or "개최 일정순 (빠른순)"

    # 하단 여행 카드 그리드와의 시원하고 여유 있는 48px 분리 여백
    st.markdown('<div style="margin-bottom: 48px;"></div>', unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # 4. 데이터 필터링 및 정렬 파이프라인 (완벽한 교집합 AND 조건 누적 적용)
    #    [조건 1] 권역(수도권 등) AND
    #    [조건 2] 카테고리(자연·힐링 등) AND
    #    [조건 3] 동행인(st.session_state.companion)
    # --------------------------------------------------------------------------
    # ① 권역 필터 (Zone)
    if selected_zone not in ["전국", "전체"]:
        target_regs = ZONE_REGIONS.get(selected_zone, [])
        cur_list = [e for e in all_events if e.get("region") in target_regs]
    else:
        cur_list = list(all_events)

    # ② 카테고리/테마 필터 [ 전체 | 로컬 축제 | 자연·힐링 | 역사·문화 ] (Category)
    if current_category != "전체":
        cur_list = [e for e in cur_list if classify_item_category(e) == current_category]

    # ③ 동행인(st.session_state.companion) 맞춤 필터 (Companion - 완벽한 AND 교집합)
    if is_companion_active:
        matched_comp = []
        for e in cur_list:
            score = score_festival_for_companion(e, companion_param)
            if score > 0:
                e_copy = dict(e)
                e_copy["_comp_score"] = score
                matched_comp.append(e_copy)
        cur_list = matched_comp

    # ④ 무장애 / 완경사 코스 토글 필터 (Barrier-free)
    if current_barrier_only:
        b_list = [e for e in cur_list if is_barrier_free_course(e)]
        if b_list:
            cur_list = b_list

    # ⑤ 중복 제거 (단 1건만 단일 보존)
    seen_unique = set()
    dedup_filtered = []
    for it in cur_list:
        t_clean = urllib.parse.quote(str(it.get("title") or "").strip().lower())
        if t_clean not in seen_unique:
            seen_unique.add(t_clean)
            dedup_filtered.append(it)
    filtered = dedup_filtered

    # ⑥ 정렬 (Sort) 기준 엄밀 적용
    if current_sort == "개최 일정순 (빠른순)":
        filtered.sort(key=get_festival_date_sort_key)
    elif current_sort == "이름순 (가나다)":
        filtered.sort(key=lambda x: str(x.get("title") or ""))
    elif current_sort == "체력 배터리순 (가벼운 코스)":
        filtered.sort(key=lambda x: get_item_stamina_intensity(x))
    else:
        filtered.sort(key=get_festival_date_sort_key)

    # 동행인 맞춤 상위 아이템 추천 뱃지 플래그 지정
    if is_companion_active:
        for idx, cand in enumerate(filtered):
            if cand.get("_comp_score", 0) > 0 and idx < 3:
                cand["_is_custom_recommended"] = True

    # ⑦ 스포트라이트 추천 축제(순천만 갈대축제, 진주 남강유등축제, 강릉 커피축제 등) 최우선 배치
    highlight_badge_html = ""
    if target_fest_spotlight:
        t_kw = target_fest_spotlight.replace("축제", "").strip()
        match_items = [e for e in all_events if t_kw in str(e.get("title", "")) or str(e.get("title", "")) in t_kw]
        if match_items:
            m_it = match_items[0]
            filtered = [e for e in filtered if str(e.get("title", "")) != str(m_it.get("title", ""))]
            filtered.insert(0, m_it)
            highlight_badge_html = f"""
            <div style="background:#FAF7F2; border:1.5px solid #012D1D; border-radius:14px; padding:16px 22px; margin-bottom:28px; display:flex; align-items:center; gap:12px; color:#012D1D; font-weight:700; font-size:0.95rem; box-shadow:0 6px 20px rgba(1,45,29,0.06);">
                <span style="font-size:1.3rem;">🌿</span>
                <div>
                    <div>스포트라이트 추천 축제 <strong>'{html.escape(str(m_it.get("title")))}'</strong> 쉼표여정 코스가 1순위로 준비되었습니다.</div>
                    <div style="font-size:0.82rem; color:#5A645D; font-weight:500; margin-top:2px;">아래 1번 카드에서 상세 코스 정보 및 맞춤 일정을 확인해보세요.</div>
                </div>
            </div>
            """

    # --------------------------------------------------------------------------
    # 5. 카드 리스트 UI: 썸네일(16:9), 3줄 텍스트 위계, 우측 상단 찜 하트
    # --------------------------------------------------------------------------
    if highlight_badge_html:
        st.html(highlight_badge_html)

    if not filtered:
        comp_info = f" · {COMPANION_PROFILES.get(companion_param, {}).get('label', '')}" if is_companion_active else ""
        cat_info = f" · {current_category}" if current_category != "전체" else ""
        st.html(f"""
        <div style="text-align:center; padding:60px 20px; background:#FAF7F2; border-radius:18px; border:1.5px solid #EAE3D6; margin-bottom:48px;">
            <div style="font-size:2.4rem; margin-bottom:12px;">🌾</div>
            <h3 style="font-family:'MaruBuri', 'KoPubWorld Batang', serif; color:#14382B; margin:0 0 8px 0; font-size:1.20rem;">
                선택하신 조건({selected_zone}{cat_info}{comp_info})의 여정 코스를 준비 중입니다
            </h3>
            <p style="color:#6B7280; font-size:0.88rem; margin:0;">
                상단의 '전국' 또는 다른 권역/테마를 선택하시면 풍성한 가을 로컬 여정을 만나보실 수 있습니다.
            </p>
        </div>
        """)
        return

    # --------------------------------------------------------------------------
    # 5. 페이지네이션 (Pagination): 가로 4열 x 세로 4줄 = 페이지당 16개 카드
    # --------------------------------------------------------------------------
    PER_PAGE = 16
    total_items = len(filtered)
    total_pages = max(1, (total_items + PER_PAGE - 1) // PER_PAGE)

    # 쿼리 파라미터 또는 세션 상태에서 현재 페이지 추출
    if "exp_page" in st.query_params:
        try:
            p_val = int(st.query_params.get("exp_page"))
            if 1 <= p_val <= total_pages:
                st.session_state.exp_page = p_val
        except Exception:
            pass
        del st.query_params["exp_page"]

    current_page = st.session_state.get("exp_page", 1)
    if current_page > total_pages or current_page < 1:
        current_page = 1
        st.session_state.exp_page = 1

    start_idx = (current_page - 1) * PER_PAGE
    end_idx = min(start_idx + PER_PAGE, total_items)
    display_items = filtered[start_idx:end_idx]

    cards_html_list = []
    poster_cache = get_naver_poster_cache()

    for it in display_items:
        raw_title = str(it.get('title') or '').strip()
        c_title = html.escape(raw_title or "로컬 축제")
        c_addr = html.escape(str(it.get("addr") or "대한민국 로컬 명소"))
        c_region = str(it.get("region") or "전국")
        c_thumb = str(it.get("thumbnail") or "").strip()
        c_raw = str(it.get("image") or "").strip()

        # Unsplash 범용 사진이거나 비어있을 경우 네이버 수집 포스터 캐시 우선 연동
        if (not c_raw) or ("unsplash.com" in c_raw) or ("traveli.co.kr" in c_raw):
            if raw_title in poster_cache:
                c_raw = poster_cache[raw_title]
            else:
                cn = re.sub(r'[\s\d제회\(\)\[\]\<\>]+', '', raw_title).lower()
                if cn in poster_cache:
                    c_raw = poster_cache[cn]

        if not c_raw or c_raw.lower() in ["none", "null", "nan", "", "-"]:
            c_img = c_thumb or get_fallback_banner(c_region)
        else:
            c_img = c_raw

        # VisitKorea 및 네이버 프록시 이미지 URL 정제
        if "search.pstatic.net" in c_img and "tong.visitkorea.or.kr" in c_img:
            m = re.search(r"src=([^&]+)", c_img)
            if m:
                raw_u = urllib.parse.unquote(m.group(1))
                if "tong.visitkorea.or.kr" in raw_u:
                    c_img = raw_u

        if "tong.visitkorea.or.kr" in c_img and c_img.startswith("http://"):
            c_img = "https://" + c_img[7:]

        # URL 내부 잔여 특수 인코딩 및 \u0026 정제
        if "search.pstatic.net/common/?src=" in c_img:
            m = re.search(r"src=([^&]+)", c_img)
            if m:
                inner = urllib.parse.unquote(m.group(1))
                inner = inner.split('\\u0026')[0].split('%5Cu0026')[0].split('%5cu0026')[0]
                if "tong.visitkorea.or.kr" in inner:
                    c_img = inner if inner.startswith("https://") else ("https://" + inner.replace("http://", ""))
                else:
                    c_img = f"https://search.pstatic.net/common/?src={urllib.parse.quote(inner, safe='')}&type=b400"
        elif "blogfiles.naver.net" in c_img:
            if c_thumb and c_thumb.startswith("https://"):
                c_img = c_thumb
            elif not c_img.startswith("https://search.pstatic.net"):
                c_img = f"https://search.pstatic.net/common/?src={urllib.parse.quote(c_img, safe='')}&type=b400"

        # 날짜 포맷 (3줄 위계 중 3번째 줄)
        s_date = str(it.get("startDate") or "").strip()
        e_date = str(it.get("endDate") or "").strip()
        if len(s_date) == 8 and len(e_date) == 8 and s_date.isdigit() and e_date.isdigit():
            date_label = f"{s_date[0:4]}.{s_date[4:6]}.{s_date[6:8]} ~ {e_date[4:6]}.{e_date[6:8]}"
        else:
            date_label = "2026.10 ~ 가을 시즌"

        status_badge_html = get_festival_status_badge(it)

        comp_go_part = f"&companion={urllib.parse.quote(companion_param)}" if is_companion_active else ""
        go_link = f"?select_fest_and_go={urllib.parse.quote(raw_title)}&target_region={urllib.parse.quote(c_region)}{comp_go_part}"
        
        c_cat_tag = classify_item_category(it)
        c_stamina = get_item_stamina_intensity(it)
        is_bf = is_barrier_free_course(it)
        bf_pill = '<span style="font-size:0.68rem; font-weight:700; color:#065F46; background:#ECFDF5; border:1px solid #A7F3D0; padding:2px 6px; border-radius:5px;">♿ 완경사</span>' if is_bf else ''
        custom_badge = '<span style="background:#012D1D; color:#FDE68A; font-size:0.70rem; font-weight:800; padding:2px 6px; border-radius:5px; margin-right:5px; vertical-align:middle;">★ 맞춤 추천</span>' if it.get("_is_custom_recommended") else ""

        cards_html_list.append(f"""
        <div class="editorial-card">
            <div>
                <!-- 16:9 썸네일 래퍼 & 우측 상단 축제 상태 뱃지 (은색 하트 대체) -->
                <div class="card-thumb-wrap">
                    <img src="{c_img}"
                         alt=""
                         class="card-thumb-img"
                         referrerpolicy="no-referrer"
                         loading="lazy"
                         onerror="this.onerror=null; this.src='{DEFAULT_FESTIVAL_GRAPHIC_DATA_URI}';" />
                    {status_badge_html}
                </div>

                <!-- 카드 본문 3줄 위계 구조: [지역/카테고리/체력 뱃지] ➔ [축제·코스명] ➔ [개최 기간] -->
                <div class="card-content-body">
                    <!-- 1줄: [지역 뱃지 + 테마 뱃지 + 완경사 + 체력배터리] -->
                    <div style="display:flex; align-items:center; gap:5px; flex-wrap:wrap; margin-bottom:2px;">
                        <span class="card-loc-pill">📍 {c_region}</span>
                        <span style="font-size:0.68rem; font-weight:700; color:#4B5563; background:#F3F4F6; border:1px solid #E5E7EB; padding:2px 6px; border-radius:5px;">{c_cat_tag}</span>
                        {bf_pill}
                        <span style="font-size:0.70rem; font-weight:800; color:#047857; margin-left:auto;">🔋 {c_stamina}%</span>
                    </div>
                    <!-- 2줄: [축제·코스명] -->
                    <h3 class="card-title-text">{custom_badge}{c_title}</h3>
                    <!-- 3줄: [개최 기간] -->
                    <div class="card-date-text">
                        <span>🗓️</span>
                        <span>{date_label}</span>
                    </div>
                    <!-- 부가 주소 안내 -->
                    <div style="font-size:0.75rem; color:#9CA3AF; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-top:2px;">
                        {c_addr}
                    </div>
                </div>
            </div>

            <!-- 하단 1일 힐링 코스 세팅 버튼 -->
            <div class="card-footer-action">
                <a href="{go_link}" target="_self" class="card-action-link">
                    <span>1일 힐링 코스 생성하기</span>
                    <span>➔</span>
                </a>
            </div>
        </div>
        """)

    # --------------------------------------------------------------------------
    # 6. 하단 페이지 번호 네비게이션 (1, 2, 3, 4 ... 순서 버튼 연결 UI)
    # --------------------------------------------------------------------------
    pagination_html = ""
    if total_pages > 1:
        page_btn_list = []
        base_query = f"?view=course&exp_zone={urllib.parse.quote(selected_zone)}"
        if current_category != "전체":
            base_query += f"&exp_theme={urllib.parse.quote(current_category)}"
        if current_sort != "개최 일정순 (빠른순)":
            base_query += f"&exp_sort={urllib.parse.quote(current_sort)}"
        if is_companion_active:
            base_query += f"&companion={urllib.parse.quote(companion_param)}"

        # 이전 페이지 버튼
        if current_page > 1:
            prev_link = f"{base_query}&exp_page={current_page - 1}"
            page_btn_list.append(f'<a href="{prev_link}" target="_self" class="page-nav-btn page-arrow">❮ 이전</a>')
        else:
            page_btn_list.append('<span class="page-nav-btn page-arrow disabled">❮ 이전</span>')

        # 표시할 페이지 번호 범위 계산 (최대 7개 번호 스마트 슬라이딩)
        max_visible_pages = 7
        if total_pages <= max_visible_pages:
            p_start = 1
            p_end = total_pages
        else:
            half = max_visible_pages // 2
            p_start = max(1, current_page - half)
            p_end = min(total_pages, p_start + max_visible_pages - 1)
            if p_end - p_start < max_visible_pages - 1:
                p_start = max(1, p_end - max_visible_pages + 1)

        if p_start > 1:
            page_btn_list.append(f'<a href="{base_query}&exp_page=1" target="_self" class="page-nav-btn">1</a>')
            if p_start > 2:
                page_btn_list.append('<span class="page-ellipsis">…</span>')

        for p in range(p_start, p_end + 1):
            is_cur = (p == current_page)
            active_cls = " active" if is_cur else ""
            if is_cur:
                page_btn_list.append(f'<span class="page-nav-btn{active_cls}">{p}</span>')
            else:
                p_link = f"{base_query}&exp_page={p}"
                page_btn_list.append(f'<a href="{p_link}" target="_self" class="page-nav-btn{active_cls}">{p}</a>')

        if p_end < total_pages:
            if p_end < total_pages - 1:
                page_btn_list.append('<span class="page-ellipsis">…</span>')
            page_btn_list.append(f'<a href="{base_query}&exp_page={total_pages}" target="_self" class="page-nav-btn">{total_pages}</a>')

        # 다음 페이지 버튼
        if current_page < total_pages:
            next_link = f"{base_query}&exp_page={current_page + 1}"
            page_btn_list.append(f'<a href="{next_link}" target="_self" class="page-nav-btn page-arrow">다음 ❯</a>')
        else:
            page_btn_list.append('<span class="page-nav-btn page-arrow disabled">다음 ❯</span>')

        pagination_html = f"""
        <div class="pagination-wrapper">
            <div class="pagination-info">
                총 <strong>{total_items}</strong>개 축제 중 <strong>{start_idx + 1}~{end_idx}</strong>번째 (페이지 {current_page} / {total_pages})
            </div>
            <div class="pagination-btn-group">
                {"".join(page_btn_list)}
            </div>
        </div>
        """

    final_grid_html = f"""
    <div class="editorial-cards-grid">
        {"".join(cards_html_list)}
    </div>
    {pagination_html}
    """
    st.html(final_grid_html)


if __name__ == "__main__":
    st.set_page_config(
        page_title="FestaPick 가을 축제 큐레이션",
        page_icon="🍁",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    render_course_explorer_page()
