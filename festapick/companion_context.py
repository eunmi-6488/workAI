# -*- coding: utf-8 -*-
"""
festapick/companion_context.py - FestaPick Concierge 동행인 전수 연동 공통 모듈
================================================================================
메인 화면 FestaPick Concierge 알약 버튼(나홀로 / 부모님 / 아이와 / 연인 / 반려견)에서
선택된 동행인을 5대 편의 서비스 전체가 동일한 기준으로 해석하도록 단일 진실 공급원을 제공합니다.

1. 지역축제 달력     : filter_festivals_for_companion()  - 동행인 적합 축제만 섹션 A/B에 유지
2. 쉼표 여정         : render_course_companion_panel()   - 전용 오디오 트랙 / 에디터 에세이 / 무장애 동선 지도
3. 착한가격 식당     : rerank_restaurants_for_companion() - 동행인 맞춤 업종 상단 우선 정렬
4. 날씨확인          : render_weather_companion_guide()  - 동행인별 외출 안심 가이드
5. 안심쉼터/로컬큐레이션: apply_barrier_auto_default() / is_gentle_slope_shelter() - 완경사 자동 활성화
================================================================================
"""

import html
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    st = None


# ------------------------------------------------------------------------------
# 0. 동행인 프로필 정의 (canonical key: solo / parents / family / couple / pet)
# ------------------------------------------------------------------------------
COMPANION_KEYS = ["solo", "parents", "family", "couple", "pet"]

# 완경사 안심 코스 체크박스를 자동 활성화할 동행인
BARRIER_AUTO_KEYS = {"parents", "family"}

COMPANION_PROFILES: Dict[str, Dict[str, Any]] = {
    "solo": {
        "label": "나홀로 쉼표",
        "short": "혼자",
        "icon": "🌿",
        "audio_label": "혼자",
        "festival_focus": "전시·사색",
        "festival_include": [
            "전시", "미술", "갤러리", "사색", "북", "도서", "책", "문학", "클래식", "재즈", "영화",
            "비엔날레", "박물관", "공예", "디자인", "다도", "차문화", "명상", "산책", "둘레길",
            "커피", "미디어아트", "국가유산", "문화유산", "고택", "서원", "사찰", "음악",
            "힐링", "자연", "숲", "치유", "여유", "슬로우", "공원", "호수",
        ],
        "festival_exclude": ["어린이", "키즈", "유아"],
        "restaurant_focus": "1인 백반·국수",
        "restaurant_include": [
            "백반", "국밥", "국수", "칼국수", "잔치국수", "김밥", "분식", "덮밥", "비빔밥", "찌개",
            "해장국", "혼밥", "라면", "우동", "콩나물", "순대국", "수제비", "기사식당",
        ],
        "restaurant_exclude": ["뷔페", "한정식", "코스"],
        "route_focus": "혼잡도 낮은 사색 산책 동선",
        "route_include": ["산책", "둘레길", "숲", "호수", "정원", "수목원", "미술", "박물관", "전시", "사찰", "서원"],
        "color": "#0F766E",
    },
    "parents": {
        "label": "부모님 효도",
        "short": "부모님",
        "icon": "🧓",
        "audio_label": "부모님",
        "festival_focus": "자연·힐링",
        "festival_include": [
            "자연", "힐링", "꽃", "국화", "갈대", "억새", "단풍", "코스모스", "생태", "습지", "정원",
            "수목원", "전통", "역사", "한옥", "온천", "약초", "인삼", "한방", "차", "녹차", "국악",
            "민속", "사찰", "산사", "미식", "특산물", "한우", "사과", "대하", "향토", "유등", "문화유산",
            "무장애", "완만", "평지", "데크", "단차", "숲", "호수", "공원", "나눔길",
        ],
        "festival_exclude": ["록", "edm", "힙합", "클럽", "맥주", "비어", "마라톤", "익스트림", "레이스"],
        "restaurant_focus": "한식·탕류",
        "restaurant_include": [
            "한식", "백반", "정식", "한정식", "찌개", "된장", "청국장", "순두부", "국밥", "해장국",
            "설렁탕", "곰탕", "갈비탕", "추어탕", "삼계탕", "도가니탕", "보리밥", "쌈밥", "비빔밥",
            "죽", "생선구이", "한식뷔페", "누룽지",
        ],
        "restaurant_exclude": ["호프", "주점", "포차", "치킨", "맥주", "소주", "횟집", "스시", "마라"],
        "route_focus": "단차 없는 무장애 평지 효도 동선",
        "route_include": [],  # 무장애 판정 함수 사용
        "color": "#B45309",
    },
    "family": {
        "label": "아이와 패밀리",
        "short": "아이와",
        "icon": "👶",
        "audio_label": "가족",
        "festival_focus": "체험·잔디",
        "festival_include": [
            "체험", "어린이", "키즈", "가족", "놀이", "잔디", "과학", "동물", "공룡", "만들기",
            "퍼레이드", "캐릭터", "농장", "수확", "고구마", "사과", "빵", "피크닉", "마술", "인형",
            "불꽃", "로봇", "곤충", "목장", "썰매", "눈", "얼음", "빛축제", "동화", "숲", "물놀이",
            "유모차", "공원", "놀이터", "테마파크",
        ],
        "festival_exclude": ["주류", "와인", "맥주", "비어", "막걸리", "소주", "전통주"],
        "restaurant_focus": "돈까스·양식",
        "restaurant_include": [
            "돈가스", "돈까스", "돈카츠", "카츠", "경양식", "양식", "함박", "오므라이스", "오무라이스",
            "피자", "스파게티", "파스타", "불고기", "짜장", "자장", "김밥", "만두", "떡볶이", "분식",
            "우동", "국수",
        ],
        "restaurant_exclude": ["호프", "주점", "포차", "맥주", "소주", "마라", "횟집"],
        "route_focus": "유모차도 거뜬한 안심 피크닉 동선",
        "route_include": [],  # 무장애 판정 함수 사용
        "color": "#1D4ED8",
    },
    "couple": {
        "label": "연인 데이트",
        "short": "연인",
        "icon": "💑",
        "audio_label": "커플",
        "festival_focus": "야경·낭만",
        "festival_include": [
            "야경", "불꽃", "빛", "노을", "유등", "등불", "별빛", "음악", "재즈", "와인", "커피",
            "낭만", "데이트", "포토", "미디어", "드론", "꽃", "해변", "바다", "야행", "달빛",
            "일루미네이션", "콘서트", "카페", "정원", "호수", "단풍", "갈대", "억새", "핑크뮬리",
            "선셋", "로맨틱", "감성", "뷰",
        ],
        "festival_exclude": ["어린이", "키즈", "유아", "효도"],
        "restaurant_focus": "카페·양식",
        "restaurant_include": [
            "카페", "커피", "라떼", "베이커리", "케이크", "디저트", "브런치", "양식", "경양식",
            "파스타", "스파게티", "스테이크", "피자", "함박", "카츠", "돈카츠", "덮밥", "우동", "정식",
        ],
        "restaurant_exclude": ["기사식당", "해장국", "순대국"],
        "route_focus": "손잡고 걷는 노을·야경 데이트 로드",
        "route_include": ["야경", "불꽃", "빛", "노을", "호수", "해변", "바다", "정원", "유등", "등", "강변", "공원"],
        "color": "#BE185D",
    },
    "pet": {
        "label": "반려견 동반",
        "short": "반려견",
        "icon": "🐾",
        "audio_label": "반려동물",
        "festival_focus": "야외·펫프렌들리",
        "festival_include": [
            "반려", "펫", "애견", "강아지", "야외", "공원", "생태", "갈대", "억새", "숲", "산책",
            "해변", "바다", "강변", "호수", "꽃", "국화", "코스모스", "둘레길", "정원", "들판", "캠핑",
            "단풍", "트레킹", "자연", "마당", "피크닉", "잔디", "숲길", "산책로",
        ],
        "festival_exclude": ["미술관", "박물관", "공연장", "실내", "전시관", "북페어", "도서"],
        "restaurant_focus": "야외 테라스·가든",
        "restaurant_include": [
            "테라스", "가든", "야외", "정원", "뜰", "마당", "카페", "커피", "보리밥", "막국수",
            "농원", "숲", "공원",
        ],
        "restaurant_exclude": [],
        "route_focus": "흙길·잔디 위주 펫 산책 동선",
        "route_include": ["공원", "숲", "산책", "둘레길", "생태", "갈대", "억새", "해변", "강변", "호수", "정원", "들판"],
        "color": "#047857",
    },
}


# ------------------------------------------------------------------------------
# 1. 동행인 키 정규화 및 활성 동행인 조회
# ------------------------------------------------------------------------------
def normalize_companion_key(raw: Any) -> str:
    """다양한 표기(영문 키·한글 라벨)를 canonical key로 정규화. 해당 없음/해제는 빈 문자열."""
    c = str(raw or "").strip().lower()
    if not c or c in ("none", "all", "null", "skip") or "선택 없이" in str(raw or "") or "둘러보기" in str(raw or ""):
        return ""
    if c in COMPANION_PROFILES:
        return c
    if any(k in c for k in ["parent", "부모", "어르신", "효도", "시부모"]):
        return "parents"
    if any(k in c for k in ["family", "아이", "자녀", "가족", "키즈"]):
        return "family"
    if any(k in c for k in ["couple", "연인", "커플", "데이트"]):
        return "couple"
    if any(k in c for k in ["pet", "반려", "펫", "강아지", "애견"]):
        return "pet"
    if any(k in c for k in ["solo", "나홀로", "혼자", "1인", "쉼표"]):
        return "solo"
    return ""


def get_active_companion_key() -> str:
    """URL 쿼리 파라미터 → 세션 상태 순으로 활성 동행인 키를 조회."""
    if st is None:
        return ""
    raw = ""
    try:
        raw = st.query_params.get("companion") or ""
    except Exception:
        raw = ""
    if not raw:
        raw = st.session_state.get("active_companion_param") or ""
    return normalize_companion_key(raw)


def get_profile(comp_key: str) -> Optional[Dict[str, Any]]:
    return COMPANION_PROFILES.get(normalize_companion_key(comp_key))


def _text_of(item: Dict[str, Any], fields: List[str]) -> str:
    parts = []
    for f in fields:
        v = item.get(f)
        if isinstance(v, list):
            for p in v:
                if isinstance(p, dict):
                    parts.append(" ".join(str(x) for x in p.values()))
                else:
                    parts.append(str(p))
        elif v is not None:
            parts.append(str(v))
    return " ".join(parts).lower()


# ------------------------------------------------------------------------------
# 2. 공통 상단 상태 배너 ("선택하신 [동행인] 맞춤 서비스가 적용되었습니다")
# ------------------------------------------------------------------------------
def render_companion_status_banner(comp_key: str, view_name: str, detail: str = "") -> None:
    """모든 상세 뷰 상단에 동일한 형식의 동행인 적용 배너를 출력."""
    prof = get_profile(comp_key)
    if st is None or not prof:
        return
    detail_html = (
        f'<div style="color:#4B5563; font-size:0.84rem; font-weight:500; margin-top:3px; line-height:1.5;">{html.escape(detail)}</div>'
        if detail else ""
    )
    st.html(f"""
    <div style="
        background: linear-gradient(135deg, #F0FDF4 0%, #FEF9C3 100%);
        border: 1.5px solid #BBF7D0; border-radius: 14px; padding: 13px 18px; margin: 12px 0 20px 0;
        display: flex; align-items: center; gap: 13px; box-shadow: 0 2px 10px rgba(6,95,70,0.05);
        font-family: 'Pretendard', sans-serif;">
        <span style="font-size:1.45rem; line-height:1;">{prof['icon']}</span>
        <div style="flex:1; min-width:0;">
            <div style="color:#065F46; font-size:0.95rem; font-weight:800; letter-spacing:-0.01em;">
                ✅ 선택하신 [{html.escape(prof['label'])}] 맞춤 서비스가 적용되었습니다
            </div>
            {detail_html}
        </div>
        <a href="?view={view_name}&companion=none" target="_self"
           style="margin-left:auto; background:#FFFFFF; color:#012D1D; border:1px solid #A7F3D0; font-size:0.74rem;
                  font-weight:800; padding:5px 10px; border-radius:999px; text-decoration:none; white-space:nowrap;">
            ✕ 맞춤 해제
        </a>
    </div>
    """)


# ------------------------------------------------------------------------------
# 3. [지역축제 달력] 동행인 적합 축제 필터링
# ------------------------------------------------------------------------------
FESTIVAL_TEXT_FIELDS = ["title", "description", "desc", "theme", "category", "location", "programs", "addr", "tags", "overview"]


def score_festival_for_companion(fest: Dict[str, Any], comp_key: str) -> int:
    """동행인 적합도 점수 (0 이하 = 부적합)."""
    prof = get_profile(comp_key)
    if not prof:
        return 1
    text = _text_of(fest, FESTIVAL_TEXT_FIELDS)
    if any(k in text for k in prof["festival_exclude"]):
        return -1
    return sum(1 for k in prof["festival_include"] if k in text)


def filter_festivals_for_companion(fests: List[Dict[str, Any]], comp_key: str) -> List[Dict[str, Any]]:
    """동행인 적합 축제만 남긴 목록 (적합도 높은 순 정렬). 동행인 미선택 시 원본 그대로."""
    prof = get_profile(comp_key)
    if not prof:
        return list(fests)
    scored = [(score_festival_for_companion(f, comp_key), idx, f) for idx, f in enumerate(fests)]
    kept = [(s, idx, f) for s, idx, f in scored if s > 0]
    kept.sort(key=lambda x: (-x[0], x[1]))
    return [f for _, _, f in kept]


# ------------------------------------------------------------------------------
# 4. [착한가격 식당] 동행인 맞춤 업종 Re-ranking
# ------------------------------------------------------------------------------
def rerank_restaurants_for_companion(items: List[Dict[str, Any]], comp_key: str) -> Tuple[List[Dict[str, Any]], int]:
    """
    맞춤 업종 → 일반 → 비추천 업종 순으로 재정렬(기존 큐레이션 순서는 그룹 내부에서 보존).
    반환: (재정렬 목록, 맞춤 업종 건수)
    """
    prof = get_profile(comp_key)
    if not prof:
        return list(items), 0

    inc = prof["restaurant_include"]
    exc = prof["restaurant_exclude"]

    def _txt(it):
        return f"{it.get('name', '')} {it.get('menu1', '')} {it.get('menu2', '')} {it.get('sector', '')}".lower()

    ranked = []
    matched_cnt = 0
    for idx, it in enumerate(items):
        t = _txt(it)
        hits = sum(1 for k in inc if k in t)
        is_exc = any(k in t for k in exc)
        if is_exc:
            group = 2
        elif hits > 0:
            group = 0
            matched_cnt += 1
        else:
            group = 1
        it["_comp_match"] = (group == 0)
        it["_comp_hits"] = hits
        ranked.append((group, -hits if group == 0 else 0, idx, it))
    ranked.sort(key=lambda x: (x[0], x[1], x[2]))
    return [r[3] for r in ranked], matched_cnt


# ------------------------------------------------------------------------------
# 5. [날씨확인] 동행인별 외출 안심 가이드
# ------------------------------------------------------------------------------
def _num(v: Any, default: float = 0.0) -> float:
    try:
        if isinstance(v, (int, float)):
            return float(v)
        m = re.search(r"-?\d+(\.\d+)?", str(v))
        return float(m.group()) if m else default
    except Exception:
        return default


def build_weather_companion_guide(comp_key: str, weather: Dict[str, Any]) -> List[Dict[str, str]]:
    """동행인 + 실시간 기상값으로 안심 가이드 카드 목록 생성. level: safe / caution / warn"""
    prof = get_profile(comp_key)
    if not prof:
        return []
    cur = (weather or {}).get("current", {}) or {}
    temp = _num(cur.get("temp"), 18)
    feels = _num(cur.get("feels_like"), temp)
    t_min = _num(cur.get("temp_min"), temp - 5)
    t_max = _num(cur.get("temp_max"), temp + 3)
    rain = _num(cur.get("rain_prob"), 0)
    hum = _num(cur.get("humidity"), 50)
    wind = _num(cur.get("wind_speed"), 1.5)
    dust_raw = str(cur.get("dust_status", "") or "")
    dust = _num(dust_raw, 25)
    diurnal = max(0.0, t_max - t_min)

    def lv(cond_warn: bool, cond_caution: bool) -> str:
        return "warn" if cond_warn else ("caution" if cond_caution else "safe")

    cards: List[Dict[str, str]] = []
    if comp_key == "parents":
        cards.append({
            "icon": "🌡️", "title": f"일교차 {diurnal:.0f}℃",
            "desc": ("일교차가 커 혈압 변동 위험이 있어요. 목을 감싸는 머플러와 보온 겉옷을 꼭 챙겨주세요."
                     if diurnal >= 10 else "일교차가 크지 않아요. 얇은 겉옷 하나면 충분합니다."),
            "level": lv(diurnal >= 12, diurnal >= 9),
        })
        cards.append({
            "icon": "❤️", "title": f"혈압·보온 케어 (최저 {t_min:.0f}℃)",
            "desc": ("아침·저녁 기온이 낮아 혈관 수축 위험이 있어요. 오전 10시 이후 출발을 권장합니다."
                     if t_min <= 8 else "기온이 온화해 혈압 부담이 적어요. 따뜻한 차 한 잔으로 체온만 유지해 주세요."),
            "level": lv(t_min <= 3, t_min <= 8),
        })
        cards.append({
            "icon": "🍃", "title": f"바람 {wind:.1f}m/s",
            "desc": ("바람이 강해 체감온도가 뚝 떨어져요. 그늘보다 햇볕 드는 쉼터 위주로 동선을 짜주세요."
                     if wind >= 5 else "바람이 잔잔해 걷기 편안한 날입니다."),
            "level": lv(wind >= 8, wind >= 5),
        })
        cards.append({
            "icon": "☔", "title": f"강수확률 {rain:.0f}%",
            "desc": ("노면이 미끄러울 수 있어요. 미끄럼 방지 신발과 지팡이를 챙겨주세요."
                     if rain >= 40 else "노면 상태가 양호해 낙상 걱정이 적어요."),
            "level": lv(rain >= 60, rain >= 40),
        })
    elif comp_key == "family":
        cards.append({
            "icon": "😷", "title": f"미세먼지 {dust_raw or f'{dust:.0f}㎍/㎥'}",
            "desc": ("아이 호흡기에 부담이 될 수 있어요. KF80 아동용 마스크와 실내 대체 코스를 준비해 주세요."
                     if dust >= 50 else "공기가 깨끗해 아이와 야외 활동하기 좋아요."),
            "level": lv(dust >= 80, dust >= 50),
        })
        cards.append({
            "icon": "🌡️", "title": f"아이 체온 케어 (체감 {feels:.0f}℃)",
            "desc": ("아이는 어른보다 체온이 빨리 떨어져요. 여벌 옷과 담요를 꼭 챙기세요."
                     if feels <= 12 else ("땀띠·탈수에 주의하세요. 물을 자주 마시게 해주세요." if feels >= 27
                                          else "활동하기 딱 좋은 온도예요. 얇은 겉옷 하나면 충분해요.")),
            "level": lv(feels <= 5 or feels >= 31, feels <= 12 or feels >= 27),
        })
        cards.append({
            "icon": "☔", "title": f"강수확률 {rain:.0f}%",
            "desc": ("잔디밭·놀이터가 젖을 수 있어요. 우비와 실내 키즈 쉼터를 미리 확인해 두세요."
                     if rain >= 40 else "잔디 피크닉이 가능한 날씨예요."),
            "level": lv(rain >= 60, rain >= 40),
        })
        cards.append({
            "icon": "🧴", "title": "자외선·수분",
            "desc": ("한낮(12~15시) 직사광선이 강해요. 아이용 선크림과 챙 넓은 모자를 준비하세요."
                     if t_max >= 22 else "자외선 부담이 적어요. 입술 보습제 정도만 챙기면 됩니다."),
            "level": lv(False, t_max >= 22),
        })
    elif comp_key == "pet":
        walk = 100
        walk -= max(0, temp - 24) * 6
        walk -= max(0, 5 - temp) * 5
        walk -= rain * 0.5
        walk -= max(0, dust - 30) * 0.6
        walk -= max(0, wind - 5) * 4
        walk = int(max(0, min(100, walk)))
        cards.append({
            "icon": "🐕", "title": f"산책 지수 {walk}/100",
            "desc": ("반려견 산책하기 최고의 날이에요!" if walk >= 75 else
                     ("짧은 산책 위주로 계획해 주세요." if walk >= 50 else "오늘은 실내 펫프렌들리 공간을 권장해요.")),
            "level": lv(walk < 50, walk < 75),
        })
        ground = temp + (8 if t_max >= 25 else 4)
        cards.append({
            "icon": "🔥", "title": f"지면 온도 약 {ground:.0f}℃",
            "desc": ("아스팔트가 뜨거워 발바닥 화상 위험이 있어요. 손등을 5초 대보고 흙길·잔디로 걸어주세요."
                     if ground >= 35 else "지면 열기가 없어 발바닥 부담이 적어요."),
            "level": lv(ground >= 45, ground >= 35),
        })
        cards.append({
            "icon": "💧", "title": f"습도 {hum:.0f}% · 수분 보충",
            "desc": ("헥헥거림이 심해질 수 있어요. 휴대용 물병을 챙겨 20분마다 쉬어주세요."
                     if hum >= 70 or temp >= 24 else "쾌적한 습도예요. 기본 물병만 챙기면 충분합니다."),
            "level": lv(False, hum >= 70 or temp >= 24),
        })
        cards.append({
            "icon": "🌧️", "title": f"강수확률 {rain:.0f}%",
            "desc": ("비 예보가 있어요. 강아지 우비와 발 닦을 수건을 준비하세요."
                     if rain >= 40 else "비 걱정 없는 산책 날씨예요."),
            "level": lv(rain >= 60, rain >= 40),
        })
    elif comp_key == "couple":
        cards.append({
            "icon": "🌅", "title": "골든아워 17:20 ~ 17:50",
            "desc": ("노을이 선명할 확률이 높아요. 일몰 30분 전 뷰포인트에 도착해 인생샷을 남겨보세요."
                     if rain < 40 else "구름이 많아 노을은 아쉬울 수 있어요. 야경 스팟으로 동선을 바꿔보세요."),
            "level": lv(rain >= 60, rain >= 40),
        })
        cards.append({
            "icon": "🌙", "title": f"야경 체감온도 {t_min:.0f}℃",
            "desc": ("해가 지면 금세 쌀쌀해져요. 커플 담요나 따뜻한 음료를 준비하세요."
                     if t_min <= 12 else "밤 산책하기 포근한 날씨예요."),
            "level": lv(t_min <= 5, t_min <= 12),
        })
        cards.append({
            "icon": "☔", "title": f"강수확률 {rain:.0f}%",
            "desc": ("우산 하나를 함께 쓰는 낭만도 좋지만, 실내 카페 코스를 대안으로 챙겨두세요."
                     if rain >= 40 else "비 걱정 없이 야외 데이트를 즐기세요."),
            "level": lv(rain >= 60, rain >= 40),
        })
        cards.append({
            "icon": "📸", "title": f"포토 컨디션 · 바람 {wind:.1f}m/s",
            "desc": ("바람이 강해 머리카락이 날릴 수 있어요. 바람을 등지고 촬영해 보세요."
                     if wind >= 5 else "바람이 잔잔해 사진 찍기 좋은 날이에요."),
            "level": lv(False, wind >= 5),
        })
    else:  # solo
        comfort = int(max(0, min(100, 100 - abs(temp - 19) * 4 - rain * 0.4 - max(0, dust - 30) * 0.5)))
        cards.append({
            "icon": "🎧", "title": f"나홀로 쾌적 지수 {comfort}/100",
            "desc": ("혼자 천천히 걷기 좋은 날이에요. 이어폰 하나 챙겨 나만의 속도로 걸어보세요."
                     if comfort >= 70 else "컨디션이 애매해요. 실내 전시·카페 위주 일정을 권장해요."),
            "level": lv(comfort < 45, comfort < 70),
        })
        cards.append({
            "icon": "🕰️", "title": "한산한 시간대 10:00 ~ 12:00",
            "desc": "오전 시간대는 인파가 적어 사색하며 둘러보기 좋아요.",
            "level": "safe",
        })
        cards.append({
            "icon": "🌡️", "title": f"일교차 {diurnal:.0f}℃",
            "desc": ("가벼운 겉옷으로 체온을 조절하세요." if diurnal >= 9 else "얇은 옷차림으로도 충분해요."),
            "level": lv(diurnal >= 12, diurnal >= 9),
        })
        cards.append({
            "icon": "☔", "title": f"강수확률 {rain:.0f}%",
            "desc": ("접이식 우산을 챙기고 실내 쉼터 위치를 미리 확인하세요." if rain >= 40 else "우산 없이 가볍게 나서도 좋아요."),
            "level": lv(rain >= 60, rain >= 40),
        })
    return cards


def render_weather_companion_guide(comp_key: str, weather: Dict[str, Any]) -> None:
    prof = get_profile(comp_key)
    if st is None or not prof:
        return
    cards = build_weather_companion_guide(comp_key, weather)
    if not cards:
        return
    level_style = {
        "safe": ("#ECFDF5", "#A7F3D0", "#065F46", "안심"),
        "caution": ("#FFFBEB", "#FDE68A", "#92400E", "주의"),
        "warn": ("#FEF2F2", "#FECACA", "#991B1B", "경계"),
    }
    items = []
    for c in cards:
        bg, bd, fg, tag = level_style.get(c["level"], level_style["safe"])
        items.append(f"""
        <div class="fp-wg-card" style="background:{bg}; border:1.5px solid {bd};">
            <div style="display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:8px;">
                <span style="font-size:1.4rem; line-height:1;">{c['icon']}</span>
                <span style="background:{fg}; color:#FFFFFF; font-size:0.68rem; font-weight:800; padding:2px 8px; border-radius:999px;">{tag}</span>
            </div>
            <div style="color:{fg}; font-weight:800; font-size:0.95rem; margin-bottom:5px; letter-spacing:-0.01em;">{html.escape(c['title'])}</div>
            <div style="color:#374151; font-size:0.83rem; line-height:1.55;">{html.escape(c['desc'])}</div>
        </div>
        """)
    fest_name = html.escape(str((weather or {}).get("festival_name", "") or ""))
    st.html(f"""
    <style>
    .fp-wg-wrap {{ font-family:'Pretendard', sans-serif; background:#FFFDF8; border:1.5px solid #EAE3D6; border-radius:20px;
                   padding:22px 24px; margin:6px 0 28px 0; box-shadow:0 8px 26px rgba(1,45,29,0.05); }}
    .fp-wg-grid {{ display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:14px; }}
    .fp-wg-card {{ border-radius:16px; padding:16px 16px 14px 16px; transition:transform .2s ease, box-shadow .2s ease; }}
    .fp-wg-card:hover {{ transform:translateY(-3px); box-shadow:0 10px 22px rgba(1,45,29,0.08); }}
    @media (max-width: 900px) {{ .fp-wg-grid {{ grid-template-columns:repeat(2, minmax(0,1fr)); }} }}
    </style>
    <div class="fp-wg-wrap">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:16px; flex-wrap:wrap;">
            <span style="background:#012D1D; color:#FDE68A; font-size:0.72rem; font-weight:800; padding:4px 10px; border-radius:999px; letter-spacing:0.04em;">
                {prof['icon']} {html.escape(prof['label'])} 외출 안심 가이드
            </span>
            <span style="color:#1C1C16; font-weight:800; font-size:1.05rem;">{fest_name} 기상 기준 동행인 맞춤 체크포인트</span>
        </div>
        <div class="fp-wg-grid">{''.join(items)}</div>
    </div>
    """)


# ------------------------------------------------------------------------------
# 6. [안심쉼터 & 로컬 큐레이션] 완경사 자동 활성화 / 평지 쉼터 판별
# ------------------------------------------------------------------------------
def apply_barrier_auto_default(comp_key: str, state_key: str) -> None:
    """
    동행인이 바뀐 직후 1회만 체크박스 기본값을 지정합니다.
    (부모님·아이와 → True, 그 외 → False / 이후 사용자가 직접 해제·선택한 값은 존중)
    반드시 해당 st.checkbox 위젯 생성 '이전'에 호출해야 합니다.
    """
    if st is None:
        return
    key = normalize_companion_key(comp_key)
    marker = f"_{state_key}_auto_comp"
    if st.session_state.get(marker) != key:
        st.session_state[marker] = key
        st.session_state[state_key] = key in BARRIER_AUTO_KEYS


GENTLE_POSITIVE = [
    "평지", "무장애", "완만", "완경사", "데크", "공원", "수목원", "정원", "스파", "온천", "찜질", "사우나",
    "한방", "다도", "명상", "실내", "호수", "생태", "체험관", "센터", "리조트", "호텔", "카페", "치유센터",
    "테라피", "마사지", "요가", "족욕", "해변", "산책로", "잔디",
]
GENTLE_NEGATIVE = [
    "등산", "산행", "정상", "암벽", "계단", "트레킹", "봉우리", "클라이밍", "급경사", "능선", "오름",
    "고개", "험로", "산악",
]
GENTLE_THEMES = ["뷰티/스파", "힐링/명상", "한방체험"]


def is_gentle_slope_shelter(s: Dict[str, Any]) -> bool:
    """계단·급경사 없이 평지 위주로 이용 가능한 쉼터인지 판별."""
    text = f"{s.get('title', '')} {s.get('theme', '')} {s.get('overview', '')}".lower()
    if any(k in text for k in GENTLE_NEGATIVE):
        return False
    theme = str(s.get("theme", ""))
    if any(t in theme for t in GENTLE_THEMES):
        return True
    return any(k in text for k in GENTLE_POSITIVE)


# ------------------------------------------------------------------------------
# 7. [쉼표 여정] 동행인 전용 에디터 에세이 + 오디오 트랙 + 무장애 동선 지도
# ------------------------------------------------------------------------------
COMPANION_ESSAYS: Dict[str, Dict[str, Any]] = {
    "solo": {
        "title": "아무도 재촉하지 않는 길 위에서",
        "lead": "혼자 떠나는 여행은 가장 정직한 휴식입니다.",
        "body": [
            "누군가의 일정에 맞추지 않아도 되는 하루. 마음에 드는 풍경 앞에서는 오래 머물고, 지루해지면 미련 없이 걸음을 옮깁니다.",
            "오전의 한산한 전시장, 바람만 지나가는 둘레길, 창가 자리가 비어 있는 작은 카페. 에디터는 붐비지 않는 시간과 장소만 골라 동선을 엮었습니다.",
            "이어폰 너머로 들려오는 도슨트의 목소리를 길잡이 삼아, 오늘만큼은 세상의 속도가 아닌 당신의 속도로 걸어보세요.",
        ],
    },
    "parents": {
        "title": "부모님의 보폭에 맞춰 걷는 하루",
        "lead": "늘 앞서 걸으시던 분들의 걸음에, 이제는 우리가 속도를 맞출 차례입니다.",
        "body": [
            "계단 대신 완만한 데크길을, 긴 줄 대신 바로 앉아 쉴 수 있는 그늘 벤치를 먼저 찾았습니다. 오늘 코스는 모두 단차 없는 평지 위주로 이어집니다.",
            "점심은 속이 편한 따뜻한 국물 한 그릇. 걷다 지치시기 전에 쉼터가 나타나도록 30분 간격으로 휴식 지점을 배치했습니다.",
            "사진 한 장, 손 한 번 잡아드리는 일이 생각보다 오래 기억됩니다. 부모님의 미소가 오늘 여정의 유일한 목적지입니다.",
        ],
    },
    "family": {
        "title": "유모차 바퀴도 멈추지 않는 피크닉",
        "lead": "아이의 웃음이 가장 큰 축제가 되는 날입니다.",
        "body": [
            "직접 만지고 만들어 보는 체험 부스, 마음껏 뛰어도 안전한 넓은 잔디밭, 유모차가 지나갈 수 있는 넓고 평평한 동선을 먼저 골랐습니다.",
            "수유실과 화장실이 가까운 쉼터, 자극 없이 맛있는 가족 메뉴까지 동선 안에 담았습니다. 갑작스러운 비에도 바로 피할 수 있는 실내 대안도 함께 표시했습니다.",
            "조금 느려도 괜찮습니다. 아이가 멈춰 서는 곳마다 오늘의 가장 좋은 장면이 숨어 있으니까요.",
        ],
    },
    "couple": {
        "title": "노을이 지는 쪽으로 나란히",
        "lead": "같은 풍경을 함께 바라보는 일, 그것만으로 충분한 데이트입니다.",
        "body": [
            "해 질 무렵 가장 아름다운 뷰포인트와, 불이 켜지면 더 빛나는 야경 산책로를 이어 붙였습니다. 골든아워 30분 전 도착을 추천합니다.",
            "걷다 지치면 분위기 좋은 카페에서 따뜻한 음료 한 잔. 사람이 몰리지 않는 포토 스팟도 에디터가 미리 표시해 두었습니다.",
            "맞잡은 손끝의 온기와 나직한 대화가 오늘 여정의 배경음이 되기를 바랍니다.",
        ],
    },
    "pet": {
        "title": "작은 발걸음에 맞춘 산책 지도",
        "lead": "반려견에게 축제는 새로운 냄새와 바람으로 가득한 모험입니다.",
        "body": [
            "뜨거운 아스팔트 대신 흙길과 잔디 위주로, 실내 전시장 대신 탁 트인 야외 공원과 강변길 위주로 동선을 짰습니다.",
            "물그릇을 채울 수 있는 음수대와 잠시 쉬어갈 그늘을 20분 간격으로 배치했고, 반려견 동반이 어려운 구역은 우회하도록 표시했습니다.",
            "목줄을 짧게, 마음은 넉넉하게. 오늘은 우리 아이의 속도에 맞춰 천천히 걸어보세요.",
        ],
    },
}


def _route_candidates(items: List[Dict[str, Any]], comp_key: str, barrier_fn=None) -> List[Dict[str, Any]]:
    prof = get_profile(comp_key)
    if not prof:
        return []
    out = []
    for it in items:
        try:
            lat = float(it.get("mapy") or it.get("lat") or 0)
            lng = float(it.get("mapx") or it.get("lng") or 0)
        except (TypeError, ValueError):
            continue
        if not (33.0 <= lat <= 39.0 and 124.0 <= lng <= 132.0):
            continue
        text = f"{it.get('title', '')} {it.get('addr', '')} {it.get('category', '')}".lower()
        if prof["route_include"]:
            ok = any(k in text for k in prof["route_include"])
        else:
            ok = bool(barrier_fn(it)) if barrier_fn else True
        if ok:
            out.append({"title": str(it.get("title", "")), "addr": str(it.get("addr", "")), "lat": lat, "lng": lng})
    return out


def render_course_companion_panel(comp_key: str, items: List[Dict[str, Any]], barrier_fn=None) -> None:
    """[쉼표 여정] 동행인 전용 오디오 트랙 · 에디터 힐링 에세이 · 무장애 동선 지도 패널."""
    prof = get_profile(comp_key)
    if st is None or not prof:
        return
    key = normalize_companion_key(comp_key)
    essay = COMPANION_ESSAYS.get(key, COMPANION_ESSAYS["solo"])

    st.html(f"""
    <div style="font-family:'Pretendard', sans-serif; margin:4px 0 14px 0; display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
        <span style="background:#012D1D; color:#FDE68A; font-size:0.72rem; font-weight:800; padding:4px 10px; border-radius:999px; letter-spacing:0.04em;">
            {prof['icon']} {html.escape(prof['label'])} 전용 쉼표 여정
        </span>
        <span style="color:#1C1C16; font-weight:800; font-size:1.08rem;">오디오 도슨트 · 에디터 에세이 · {html.escape(prof['route_focus'])}</span>
    </div>
    """)

    col_left, col_right = st.columns([1, 1.15], gap="large")
    with col_left:
        try:
            import festapick.audio_docent as audio_docent
            audio_docent.render_audio_docent(companion_text=prof["audio_label"])
        except Exception:
            st.caption("오디오 도슨트를 불러오지 못했습니다.")

        paragraphs = "".join(
            f'<p style="margin:0 0 12px 0; color:#2B2F2C; font-size:0.92rem; line-height:1.85;">{html.escape(p)}</p>'
            for p in essay["body"]
        )
        st.html(f"""
        <div style="font-family:'Pretendard', sans-serif; background:#FFFDF8; border:1.5px solid #EAE3D6; border-left:4px solid {prof['color']};
                    border-radius:16px; padding:20px 22px; margin-top:10px; box-shadow:0 6px 20px rgba(1,45,29,0.05);">
            <div style="font-size:0.72rem; font-weight:800; color:{prof['color']}; letter-spacing:0.06em; margin-bottom:6px;">EDITOR'S HEALING ESSAY</div>
            <h3 style="font-family:'MaruBuri','Noto Serif KR',serif; color:#14382B; font-size:1.25rem; margin:0 0 8px 0; line-height:1.4;">{html.escape(essay['title'])}</h3>
            <p style="margin:0 0 14px 0; color:#065F46; font-weight:700; font-size:0.92rem;">{html.escape(essay['lead'])}</p>
            {paragraphs}
        </div>
        """)

    with col_right:
        points = _route_candidates(items, key, barrier_fn)[:12]
        if not points:
            st.info("현재 조건에서 지도에 표시할 맞춤 동선 거점이 없습니다. 권역·테마를 바꿔보세요.")
            return
        try:
            import folium
            import streamlit.components.v1 as st_components

            c_lat = sum(p["lat"] for p in points) / len(points)
            c_lng = sum(p["lng"] for p in points) / len(points)
            spread = max(max(p["lat"] for p in points) - min(p["lat"] for p in points),
                         max(p["lng"] for p in points) - min(p["lng"] for p in points))
            zoom = 11 if spread < 0.3 else (9 if spread < 1.2 else 7)
            fmap = folium.Map(location=[c_lat, c_lng], zoom_start=zoom, tiles="CartoDB positron", control_scale=True)
            for i, p in enumerate(points, 1):
                folium.CircleMarker(
                    location=[p["lat"], p["lng"]],
                    radius=9,
                    color="#FFFFFF",
                    weight=2,
                    fill=True,
                    fill_color=prof["color"],
                    fill_opacity=0.92,
                    tooltip=f"{i}. {p['title']}",
                    popup=folium.Popup(f"<b>{html.escape(p['title'])}</b><br>{html.escape(p['addr'])}", max_width=260),
                ).add_to(fmap)
            if len(points) > 1:
                fmap.fit_bounds([[min(p["lat"] for p in points), min(p["lng"] for p in points)],
                                 [max(p["lat"] for p in points), max(p["lng"] for p in points)]], padding=(24, 24))
            st.html(f"""
            <div style="font-family:'Pretendard', sans-serif; display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:{prof['color']};"></span>
                <strong style="color:#012D1D; font-size:0.92rem;">♿ {html.escape(prof['route_focus'])} 지도</strong>
                <span style="color:#6B7280; font-size:0.8rem;">({len(points)}곳 거점)</span>
            </div>
            """)
            st_components.html(fmap.get_root().render(), height=470)
        except Exception as e:
            st.caption(f"지도를 불러오지 못했습니다: {e}")
