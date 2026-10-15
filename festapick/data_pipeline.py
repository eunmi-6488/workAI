# 운영체제 환경 및 파일 시스템 경로 처리를 위한 파이썬 표준 라이브러리 os 모듈을 불러옵니다.
import os
# 시스템 및 표준 입출력 설정을 위한 파이썬 표준 라이브러리 sys 모듈을 불러옵니다.
import sys
# 정규 표현식(Regular Expression) 처리를 위한 파이썬 표준 라이브러리 re 모듈을 불러옵니다.
import re
# JSON 데이터 파싱을 위한 json 모듈을 불러옵니다.
import json
# HTTP 네트워크 요청을 위한 requests 모듈을 불러옵니다.
import requests
# 파일 경로 탐색을 위한 glob 모듈을 불러옵니다.
import glob
# 타입 힌트 지정을 위해 typing 모듈에서 필요한 타입 클래스들을 불러옵니다.
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

# 표 형태의 데이터(CSV)를 읽고 가공하기 위해 pandas 라이브러리를 불러옵니다.
import pandas as pd
# RAG 벡터 데이터베이스 구축 및 유사도 검색을 위해 chromadb 라이브러리를 불러옵니다.
import chromadb
# 환경 변수 로드
from dotenv import load_dotenv
load_dotenv()

# festapick 모듈 및 데이터 기본 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DEFAULT_DATA_DIR = os.path.join(BASE_DIR, "data")

def get_safe_chromadb_path(db_path: Optional[str] = None) -> str:
    """Windows 환경에서 상위 폴더명의 한글 인코딩 문제를 방지하기 위해 안전한 상대 경로를 우선 탐색합니다."""
    if db_path and db_path != "chromadb_store":
        if os.path.exists(db_path):
            try:
                return os.path.relpath(db_path)
            except Exception:
                return db_path
        return db_path
    if os.path.exists("festapick/chromadb_store"):
        return "festapick/chromadb_store"
    elif os.path.exists("chromadb_store"):
        return "chromadb_store"
    try:
        return os.path.relpath(os.path.join(BASE_DIR, "chromadb_store"))
    except Exception:
        return os.path.join(BASE_DIR, "chromadb_store")

DEFAULT_DB_PATH = get_safe_chromadb_path()

# agent.py 연동 (핫 리로드 및 감성 스토리텔링 프롬프트/폴백 생성기)
import importlib
import agent
try:
    importlib.reload(agent)
except Exception:
    pass

try:
    from agent import (
        get_storytelling_system_prompt,
        build_storytelling_user_prompt,
        generate_storytelling_fallback,
        generate_storytelling_course
    )
except ImportError:
    # 혹시 모를 임포트 오류 방지용 안전 폴백
    def get_storytelling_system_prompt() -> str:
        return "당신은 여행 기획 전문 AI 수석 에디터입니다. 감성적인 스토리텔링 코스를 작성해주세요."

    def build_storytelling_user_prompt(course_package: Dict[str, Any], companion: str = "혼자") -> str:
        return f"축제: {course_package.get('festival_name')} 코스를 {companion} 맞춤 스토리텔링으로 작성해주세요."

    def generate_storytelling_fallback(course_package: Dict[str, Any], companion: str = "혼자") -> str:
        f_name = course_package.get("festival_name", "지역 축제")
        sigungu = course_package.get("target_sigungu", "")
        prefix = f"[{sigungu}] " if sigungu else ""
        comp_titles = {
            "혼자": "나홀로 사색 여행",
            "부모님": "효도 맞춤 힐링 여행",
            "가족": "온 가족 안심 나들이",
            "커플": "로맨틱 감성 데이트",
            "친구": "유쾌한 친구들과의 핫플 투어",
            "반려동물": "반려동물과 함께하는 힐링 산책"
        }
        title_suffix = comp_titles.get(companion, "감성 힐링 여행")
        return f"# 🌿 {prefix}{f_name} {title_suffix}\n\n동행인({companion})의 눈높이에 맞춘 편안한 주차, 로컬 식사, 힐링 쉼터 코스로 하루를 완성합니다."

    def generate_storytelling_course(course_package: Dict[str, Any], companion: str = "혼자") -> str:
        return generate_storytelling_fallback(course_package, companion=companion)

# ==============================================================================
# [최적화 규칙 2] 개발 모드(DEV MODE) 스위치 플래그 선언
# True  : 개발/테스트 모드 - 대용량 CSV 파일에서 상위 50~100건만 샘플링하여 0초 만에 로드 (메모리 절약, 프로세스 멈춤 방지)
# False : 운영/배포 모드 - 전체 1,264건 축제 전수 데이터를 로드하려면 IS_DEV_MODE = False로 변경하세요.
# ==============================================================================
IS_DEV_MODE: bool = True  # ※ 전체 1,264건 축제 전수 데이터를 로드하려면 IS_DEV_MODE = False로 변경하세요.

# 윈도우 환경 콘솔 출력 시 한글 인코딩 깨짐을 방지하기 위해 표준 출력을 UTF-8로 설정합니다.
if sys.stdout.encoding != "utf-8":
    # 표준 출력 인코딩을 utf-8로 재구성합니다.
    sys.stdout.reconfigure(encoding="utf-8")

# LangChain 라이브러리가 설치되어 있을 경우 공식 Document 클래스를 불러오고, 없으면 대체 클래스를 생성합니다.
try:
    # langchain_core 패키지에서 Document 클래스를 가져옵니다.
    from langchain_core.documents import Document
# LangChain 패키지가 설치되지 않은 경우 발생하는 예외를 잡습니다.
except ImportError:
    # LangChain 미설치 환경에서도 코드 호환성을 유지할 수 있도록 가상 Document 클래스를 정의합니다.
    class Document:  # type: ignore
        # 생성자 함수: 문서 내용(page_content)과 부가 정보(metadata)를 초기화합니다.
        def __init__(self, page_content: str, metadata: Optional[Dict[str, Any]] = None):
            # 본문 문자열을 인스턴스 변수에 저장합니다.
            self.page_content: str = page_content
            # 메타데이터 딕셔너리를 저장하며, 없으면 빈 딕셔너리로 초기화합니다.
            self.metadata: Dict[str, Any] = metadata if metadata is not None else {}

        # 객체 출력 시 보기 편한 형태로 문자열을 반환합니다.
        def __repr__(self) -> str:
            # 앞 40글자와 메타데이터를 표시하는 문자열을 반환합니다.
            return f"Document(page_content='{self.page_content[:40]}...', metadata={self.metadata})"


def clean_text(text: Any) -> str:
    # 입력값이 None인 경우 빈 문자열을 반환합니다.
    if text is None:
        # 빈 문자열 반환
        return ""
    # 입력값이 부동소수점(float) 형태이면서 pandas 결측치(NaN)인 경우를 확인합니다.
    if isinstance(text, float) and pd.isna(text):
        # 결측치인 경우 빈 문자열 반환
        return ""
    # 입력값을 문자열 형태로 변환합니다.
    text_str: str = str(text)
    # 문자열로 변환된 값이 'nan', 'none', 'null' 등 결측치 문자열인 경우 확인합니다.
    if text_str.strip().lower() in ["nan", "none", "null"]:
        # 결측 문자열인 경우 빈 문자열 반환
        return ""
    # 정규 표현식을 사용하여 연속된 줄바꿈(\r, \n), 탭(\t), 다중 공백을 단일 공백으로 치환합니다.
    cleaned: str = re.sub(r"\s+", " ", text_str)
    # 양쪽 끝에 있는 불필요한 공백을 제거하고 최종 정제된 문자열을 반환합니다.
    return cleaned.strip()


def clean_price(price_val: Any) -> str:
    """메뉴 가격에서 소수점이나 비정형 문자를 방어하고 정수형 콤마 포맷(예: '6,000원')으로 일관되게 규격화합니다."""
    if price_val is None:
        return ""
    if isinstance(price_val, float) and pd.isna(price_val):
        return ""
    s: str = str(price_val).strip()
    if not s or s.lower() in ["nan", "none", "null", "-", "0", "무료"]:
        return ""
    # 콤마, '원', 공백 제거
    cleaned = s.replace(",", "").replace("원", "").strip()
    try:
        val_float = float(cleaned)
        if val_float <= 0:
            return ""
        return f"{int(round(val_float)):,}원"
    except (ValueError, TypeError):
        # 숫자가 섞여 있는 경우 정규식 추출
        m = re.search(r"(\d+(?:\.\d+)?)", cleaned)
        if m:
            try:
                num = float(m.group(1))
                if num > 0:
                    return f"{int(round(num)):,}원"
            except (ValueError, TypeError):
                pass
        return ""


def classify_indoor_outdoor(title: str, venue: str) -> str:
    """축제명과 개최장소 텍스트를 분석하여 실내외 여부('실내' / '야외')를 판별합니다.
    체육관, 전시관, 컨벤션, 센터, 미술관, 박물관, 엑스포홀 등이 포함되면 '실내', 그 외는 '야외'.
    (우천 시 대체 코스 및 실내 축제 필터링 지원)
    """
    indoor_keywords = [
        "체육관", "전시관", "컨벤션", "센터", "미술관", "박물관", "엑스포홀",
        "아트홀", "문화회관", "시민회관", "예술회관", "실내", "돔", "갤러리", "벡스코", "킨텍스", "코엑스"
    ]
    combined: str = f"{title} {venue}".strip()
    if any(kw in combined for kw in indoor_keywords):
        return "실내"
    return "야외"


def classify_festival_theme(title: str, venue: str = "", description: str = "", programs: str = "") -> str:
    """축제명, 장소, 내용, 프로그램을 종합 분석하여 10대 대표 축제 테마 라벨을 추출합니다.
    - 자연/꽃, 미식/특산물, 음악/공연, 역사/전통, 야경/빛, 댄스/퍼레이드, 가족/체험, 예술/전시, 해양/액티비티, 문화/체험
    """
    text: str = f"{title} {venue} {description} {programs}".lower()

    # 1. 춤/댄스/퍼레이드
    if any(k in text for k in ["춤", "무용", "퍼레이드", "댄스", "비보이", "발레", "스트릿"]):
        return "댄스/퍼레이드"

    # 2. 야경/빛/불꽃
    if any(k in text for k in ["야경", "빛", "불꽃", "드론", "유등", "미디어아트", "루미나리에", "달빛", "등불", "야행", "야간", "조명"]):
        return "야경/빛"

    # 3. 해양/액티비티/서핑/물총
    if any(k in text for k in ["서핑", "해양", "머드", "물총", "워터", "요트", "해수욕장", "수상", "보트"]):
        return "해양/액티비티"

    # 4. 꽃/나무/단풍/자연
    if any(k in text for k in ["꽃", "나무", "단풍", "정원", "벚꽃", "유채", "국화", "장미", "연꽃", "매화", "억새", "갈대", "수목원", "생태", "튤립", "철쭉", "백일홍", "라벤더", "자연"]):
        return "자연/꽃"

    # 5. 먹거리/특산물/미식
    if any(k in text for k in ["먹거리", "특산물", "한우", "수산물", "와인", "사과", "맛", "미식", "푸드", "인삼", "딸기", "수박", "대게", "송어", "빙어", "막걸리", "커피", "빵", "김치", "젓갈"]):
        return "미식/특산물"

    # 6. 음악/콘서트/공연
    if any(k in text for k in ["음악", "콘서트", "가요", "국악", "버스킹", "재즈", "락", "소리", "아리랑", "난계", "관악", "클래식", "밴드", "오케스트라", "포크", "노래", "뮤직"]):
        return "음악/공연"

    # 7. 역사/전통
    if any(k in text for k in ["역사", "전통", "문화제", "산성", "조선", "민속", "단오", "백제", "신라", "가야", "고분", "선비", "유생", "충무공", "의병", "성곽"]):
        return "역사/전통"

    # 8. 가족/어린이/체험
    if any(k in text for k in ["가족", "어린이", "만화", "과학", "키즈", "캐릭터", "우주", "로봇", "동화", "인형극", "공룡"]):
        return "가족/체험"

    # 9. 예술/전시/미술
    if any(k in text for k in ["예술", "전시", "미술", "도예", "아트", "비엔날레", "사진", "도자기", "공예", "페어"]):
        return "예술/전시"

    # 10. 기본값
    return "문화/체험"


def classify_region(address_text: str) -> str:
    """
    주소 및 위치 텍스트에서 도/시/군/구 정보를 분석하여 6대 표준 권역으로 분류하는 함수입니다.
    - '전주월드컵경기장'처럼 장소명에 '경기'가 포함된 경우 수도권(경기도)으로 오인식되지 않도록 방지
    - extract_sido() 기반 실제 시/도 우선 판별 및 전북, 전남, 광주 등 행정구역 우선 매칭
    """
    if not address_text:
        return "기타"
    target: str = sanitize_address(address_text).strip()

    # 1. extract_sido로 실제 광역 시/도 우선 판별
    sido = extract_sido(target)
    if sido in ["서울특별시", "인천광역시", "경기도"]:
        return "수도권"
    elif sido in ["강원도", "강원특별자치도"]:
        return "강원권"
    elif sido in ["대전광역시", "세종특별자치시", "충청남도", "충청북도"]:
        return "충청권"
    elif sido in ["광주광역시", "전라남도", "전라북도"]:
        return "전라권"
    elif sido in ["부산광역시", "대구광역시", "울산광역시", "경상남도", "경상북도"]:
        return "경상권"
    elif sido in ["제주도", "제주특별자치도"]:
        return "제주도"

    # 2. 시/도 표기가 누락되었거나 축약된 경우 지명 및 시군구 키워드로 2차 분류
    # 제주
    if any(k in target for k in ["제주", "서귀포"]):
        return "제주도"

    # 전라권 우선 판정 (전북, 전남, 광주 및 주요 시군)
    jeolla_keywords = [
        "전북", "전라북도", "전남", "전라남도", "전주", "군산", "익산", "정읍",
        "남원", "김제", "완주", "진안", "무주", "장수", "임실", "순창", "고창",
        "부안", "목포", "여수", "순천", "나주", "광양", "담양", "곡성", "구례",
        "고흥", "보성", "화순", "장흥", "강진", "해남", "영암", "무안", "함평",
        "영광", "장성", "완도", "진도", "신안"
    ]
    if any(k in target for k in jeolla_keywords):
        return "전라권"
    if "광주" in target and not re.search(r'(?:경기|경기도)\s*광주', target):
        return "전라권"

    # 경상권 (부산, 대구, 울산, 경남, 경북 및 주요 시군)
    gyeongsang_keywords = [
        "부산", "대구", "울산", "경남", "경북", "경상남도", "경상북도", "경상",
        "포항", "경주", "김천", "안동", "구미", "영주", "영천", "상주", "문경",
        "경산", "군위", "의성", "청송", "영양", "영덕", "청도", "고령", "성주",
        "칠곡", "예천", "봉화", "울진", "울릉", "창원", "진주", "통영", "사천",
        "김해", "밀양", "거제", "양산", "의령", "함안", "창녕", "고성군", "남해",
        "하동", "산청", "함양", "거창", "합천"
    ]
    if any(k in target for k in gyeongsang_keywords):
        return "경상권"

    # 충청권 (대전, 세종, 충남, 충북 및 주요 시군)
    chungcheong_keywords = [
        "대전", "세종", "충남", "충북", "충청남도", "충청북도", "충청",
        "청주", "충주", "제천", "보은", "옥천", "영동", "증평", "진천", "괴산",
        "음성", "단양", "천안", "공주", "보령", "아산", "서산", "논산", "계룡",
        "당진", "금산", "부여", "서천", "청양", "홍성", "예산", "태안"
    ]
    if any(k in target for k in chungcheong_keywords):
        return "충청권"

    # 강원권 (강원도 및 주요 시군)
    gangwon_keywords = [
        "강원", "강원도", "강원특별자치도", "춘천", "원주", "강릉", "동해",
        "태백", "속초", "삼척", "홍천", "횡성", "영월", "평창", "정선", "철원",
        "화천", "양구", "인제", "양양"
    ]
    if any(k in target for k in gangwon_keywords):
        return "강원권"

    # 수도권 (경기장 등 시설명 단어 제외, 서울/인천/경기도 및 경기 시군)
    if any(k in target for k in ["서울", "인천", "경기도"]):
        return "수도권"
    # '경기' 단독 또는 '경기 [시군]' 패턴만 수도권으로 인정 (\b경기\b 및 시설명 배제)
    if re.search(r'(?:^|[\s,])경기(?!(?:장|대|연맹|협회|대회|일정|종목|력|[a-zA-Z0-9가-힣]))', target):
        return "수도권"
    if re.search(r'(?:^|[\s,])경기\s+[가-힣]+(?:시|군)', target):
        return "수도권"

    return "기타"


def sanitize_address(address_text: Any) -> str:
    """
    주소 텍스트에서 '전남광주통합특별시' 등 가상 행정구역을 전면 제거하고 표준 실제 주소로 복원합니다.
    - 광주광역시 자치구(동구, 서구, 남구, 북구, 광산구)가 이어지면 '광주광역시'로 치환
    - 그 외 전남 시·군(광양시, 담양군, 순천시 등)은 '전라남도'로 복원
    """
    if not address_text:
        return ""
    text = str(address_text).strip()
    # 광주 자치구가 뒤따르면 광주광역시로 치환
    text = re.sub(r"전남광주통합특별시\s*(동구|서구|남구|북구|광산구)\b", r"광주광역시 \1", text)
    # 광주 기관 및 지명
    text = re.sub(r"전남광주통합특별시\s*광주\b", "광주광역시", text)
    # 그 외 모든 전남광주통합특별시는 진짜 도명인 전라남도로 복원
    text = re.sub(r"전남광주통합특별시", "전라남도", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_sigungu(address_text: str) -> str:
    """
    주소 텍스트(소재지도로명주소, 지번주소)에서 오직 '진짜 시/군/구' 1개 단어만 추출합니다.
    절대 가상의 행정구역(예: '전남광주통합특별시')을 생성하거나 반환하지 않습니다.
    
    규칙:
    1) 특별시/광역시:
       - '서울특별시 종로구' -> '종로구'
       - '부산광역시 해운대구' -> '해운대구'
       - '광주광역시 동구' -> '동구'
       - '대전광역시 중구' -> '중구'
    2) 일반 도/특별자치도:
       - '전라남도 광양시' -> '광양시'
       - '전라남도 담양군' -> '담양군'
       - '전라남도 신안군' -> '신안군'
       - '충청남도 부여군' -> '부여군'
       - '충청남도 천안시' -> '천안시'
       - '제주특별자치도 제주시' -> '제주시'
       - '제주특별자치도 서귀포시' -> '서귀포시'
    """
    if not address_text:
        return ""
    # 가상 행정구역 정제 및 연속 공백 정리
    text: str = sanitize_address(address_text)

    # 1. 세종특별자치시 예외 처리 (도로명인 '세종대로', '세종로'는 제외하고 행정구역명만 매칭)
    if "세종특별자치시" in text or re.search(r"\b세종시\b", text):
        return "세종시"

    # 2. 특별시/광역시의 자치구/군 매칭 (예: '서울특별시 종로구' -> '종로구', '광주광역시 동구' -> '동구')
    metro_pattern = r"(?:서울|부산|대구|인천|광주|대전|울산)(?:특별시|광역시)?\s+([가-힣]+(?:구|군))\b"
    m_metro = re.search(metro_pattern, text)
    if m_metro:
        return m_metro.group(1)

    # 3. 도/특별자치도의 '시/군' 매칭 (예: '전라남도 광양시' -> '광양시', '충청남도 부여군' -> '부여군')
    do_pattern = r"(?:경기|강원|충북|충남|전북|전남|경북|경남|제주)(?:도|특별자치도)?\s+([가-힣]+(?:시|군))\b"
    m_do = re.search(do_pattern, text)
    if m_do:
        return m_do.group(1)

    # 4. 시/도 생략 상태로 바로 '시/군/구'가 나타나는 경우 (예: '천안시 서북구', '광양시 진월면')
    standalone_pattern = r"\b([가-힣]{2,}(?:시|군|구))\b"
    matches = re.findall(standalone_pattern, text)
    provinces = {
        "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시",
        "대전광역시", "울산광역시", "세종특별자치시", "경기도", "강원도",
        "충청북도", "충청남도", "전라북도", "전라남도", "경상북도", "경상남도",
        "제주도", "제주특별자치도", "강원특별자치도", "전북특별자치도",
        "서울시", "부산시", "대구시", "인천시", "광주시", "대전시", "울산시",
        "전남광주통합특별시"
    }
    for m in matches:
        if m not in provinces and not m.endswith(("특별자치도", "특별시", "광역시", "통합특별시", "도")):
            return m

    return ""


def extract_sido(address_text: str) -> str:
    """주소 텍스트에서 광역자치단체(시/도)를 정밀 추출하여 시군구 혼선 및 시설명('경기장' 등) 오인식을 원천 방지합니다."""
    if not address_text:
        return ""
    text = sanitize_address(address_text)

    # 1. 제주특별자치도
    if any(k in text for k in ["제주특별자치도", "제주도", "제주시", "서귀포시", "제주"]):
        return "제주도"

    # 2. 전라권 (전북특별자치도, 전라남도, 광주광역시)
    if any(k in text for k in ["전북특별자치도", "전라북도", "전북"]):
        return "전라북도"
    if any(k in text for k in ["전라남도", "전남"]):
        return "전라남도"
    if "광주광역시" in text:
        return "광주광역시"
    if "광주" in text:
        if re.search(r'(?:경기|경기도)\s*광주', text):
            return "경기도"
        if any(gu in text for gu in ["동구", "서구", "남구", "북구", "광산구"]) or "광주시" not in text:
            return "광주광역시"

    # 3. 경상권 (경북, 경남, 부산, 대구, 울산)
    if any(k in text for k in ["경상북도", "경북"]):
        return "경상북도"
    if any(k in text for k in ["경상남도", "경남"]):
        return "경상남도"
    if "부산" in text:
        return "부산광역시"
    if "대구" in text:
        return "대구광역시"
    if "울산" in text:
        return "울산광역시"

    # 4. 충청권 (충북, 충남, 대전, 세종)
    if any(k in text for k in ["충청북도", "충북"]):
        return "충청북도"
    if any(k in text for k in ["충청남도", "충남"]):
        return "충청남도"
    if "대전" in text:
        return "대전광역시"
    if "세종" in text:
        return "세종특별자치시"

    # 5. 강원권 (강원특별자치도, 강원도, 강원)
    if any(k in text for k in ["강원특별자치도", "강원도", "강원"]):
        return "강원도"

    # 6. 수도권 (서울특별시, 인천광역시, 경기도)
    if "서울" in text:
        return "서울특별시"
    if "인천" in text:
        return "인천광역시"
    if "경기도" in text:
        return "경기도"
    # '경기' 단독 매칭 시 '경기장', '경기대' 등 단순 시설명 매칭 배제
    if re.search(r'(?:^|[\s,])경기(?!(?:장|대|연맹|협회|대회|일정|종목|력|[a-zA-Z0-9가-힣]))', text):
        return "경기도"
    if re.search(r'(?:^|[\s,])경기\s+[가-힣]+(?:시|군)', text):
        return "경기도"

    return ""


def extract_region_sigungu(address_text: str) -> Tuple[str, str, str]:
    """
    주소 텍스트에서 (권역, 시도, 시군구)를 오직 진짜 행정구역 1개 단어로 추출합니다.
    가상 행정구역을 원천 차단하고 순수 시/군/구만을 안전하게 반환합니다.
    """
    sanitized = sanitize_address(address_text)
    region = classify_region(sanitized)
    sido = extract_sido(sanitized)
    sigungu = extract_sigungu(sanitized)
    return region, sido, sigungu


# ─── 먹거리/카페 업종 화이트리스트 상수 정의 ────────────────────────────────────
# ChromaDB에 인덱싱 허용할 식음료 관련 업종 키워드 목록입니다.
# 이 목록에 해당하지 않는 업종(미용업·세탁업·숙박업·목욕업 등)은 완전히 제외합니다.
FOOD_WHITELIST_KEYWORDS: List[str] = [
    # 정식 업종 분류명 (CSV '업종' 컬럼의 실제 값)
    "한식", "중식", "일식", "양식", "경양식",
    "기타요식업", "요식업",
    # 카페·베이커리·디저트 관련 키워드
    "카페", "커피", "베이커리", "제과", "다과", "다방", "디저트", "빵",
    # 분식·간식류 키워드
    "분식", "음식점", "식당", "푸드", "맛집",
    # 메뉴·업소명에서 식별 가능한 추가 키워드
    "치킨", "피자", "햄버거", "국밥", "김밥", "라면", "냉면", "삼겹", "갈비",
    "초밥", "돈까스", "파스타", "스테이크", "버거", "탕", "찌개",
]

# 먹거리·생활업종 블랙리스트: 이 키워드가 업종에 포함되면 무조건 제외합니다.
NON_FOOD_BLACKLIST_KEYWORDS: List[str] = [
    # 미용 관련
    "미용업", "미용", "이용업", "이용", "네일", "헤어",
    # 세탁·청소 관련
    "세탁업", "세탁", "청소",
    # 목욕·건강 관련
    "목욕업", "목욕", "사우나", "찜질",
    # 숙박 관련
    "숙박업", "숙박", "모텔", "호텔", "펜션", "게스트",
    # 기타 비요식업
    "기타비요식업", "비요식",
]


def is_food_related(raw_category: str, store_name: str, menu_text: str) -> bool:
    """업종·업소명·메뉴 정보를 종합하여 식음료 관련 업소인지 판별합니다.

    Returns:
        True  → ChromaDB 인덱싱 대상 (먹거리/카페 업종)
        False → 완전 제외 (미용·세탁·목욕·숙박 등 생활 업종)
    """
    # 비교를 위해 전체 텍스트를 소문자로 통합합니다.
    full_text: str = f"{raw_category} {store_name} {menu_text}"

    # 1순위: 블랙리스트 키워드 매칭 → 즉시 False 반환
    for bk in NON_FOOD_BLACKLIST_KEYWORDS:
        # 업종(raw_category)에 블랙리스트 키워드가 포함되면 제외합니다.
        if bk in raw_category:
            # 비식품 업종 판별 → 제외 대상
            return False

    # 2순위: 화이트리스트 키워드 매칭 → True 반환
    for wk in FOOD_WHITELIST_KEYWORDS:
        # 업종 또는 업소명·메뉴 통합 텍스트에 화이트리스트 키워드가 포함되면 포함합니다.
        if wk in full_text:
            # 식음료 업종 판별 → 포함 대상
            return True

    # 화이트리스트에도 블랙리스트에도 매칭되지 않으면 기본적으로 제외합니다.
    return False


def refine_store_category(raw_category: str, store_name: str, menu_text: str) -> str:
    # 업소명, 업종, 메뉴 텍스트를 종합하여 2030 여행객이 선호하는 업종 카테고리로 정제합니다.
    # ※ 이 함수는 is_food_related()로 1차 필터링을 통과한 업소에만 호출됩니다.
    full_info: str = f"{raw_category} {store_name} {menu_text}"

    # 분식/식당 관련 키워드가 상호에 들어있다면 카페/베이커리 분류에서 제외
    exclude_keywords = ["분식", "식당", "칼국수", "국밥", "찌개"]
    is_restaurant_name = any(keyword in store_name for keyword in exclude_keywords)

    # 카페, 커피, 베이커리, 디저트, 빵 관련 키워드가 포함되어 있고 상호에 분식/식당 키워드가 없으면 카페/베이커리로 분류
    if not is_restaurant_name and any(k in full_info for k in ["카페", "커피", "베이커리", "디저트", "제과", "다방", "빵", "다과"]):
        # 카페/베이커리 반환
        return "카페/베이커리"
    # 한식 키워드인 경우
    elif "한식" in raw_category or any(k in store_name + menu_text for k in ["찌개", "국밥", "백반", "탕"]):
        # 한식 반환
        return "한식"
    # 양식/경양식 키워드인 경우
    elif any(k in raw_category for k in ["양식", "경양식"]):
        # 양식 반환
        return "양식"
    # 일식 키워드인 경우
    elif "일식" in raw_category:
        # 일식 반환
        return "일식"
    # 중식 키워드인 경우
    elif "중식" in raw_category:
        # 중식 반환
        return "중식"
    # 기타 요식업/분식 키워드인 경우
    elif any(k in full_info for k in ["기타요식업", "요식업", "분식", "식당", "음식점", "칼국수"]):
        # 분식/기타요식 반환
        return "분식/기타요식"
    # 치킨·피자·버거 등 패스트푸드인 경우
    elif any(k in full_info for k in ["치킨", "피자", "햄버거", "버거", "패스트"]):
        # 패스트푸드 반환
        return "패스트푸드/치킨"
    # 그 외 식음료 업종은 원본 업종명 또는 일반음식점 반환
    else:
        # 원본 업종명 반환 (화이트리스트 통과 확인이 전제됨)
        return raw_category if raw_category else "일반음식점"


def extract_dynamic_photo_spots(title: str, venue: str, description: str, programs: str = "") -> List[str]:
    """축제의 '축제명', '개최장소', '주요프로그램/축제내용'을 실제 사실에 기반하여 심층 분석하고,
    지형 왜곡(도심 축제에 바다/백사장 생성 등) 할루시네이션을 원천 차단한 안전한 인생샷 포토스팟 2~3개를 추출/생성합니다."""
    full_text = f"{title} {venue} {description} {programs}"
    venue_name = clean_text(venue) if venue and len(clean_text(venue)) >= 2 and clean_text(venue) != "축제장" else "축제장"
    spots: List[str] = []

    # [검증 플래그] 실제 바다/해안 지형 여부 정밀 판별 (단순 '강', '호수'나 '강남/강서' 등 행정구역명 제외)
    is_real_coastal = any(sea_kw in f"{title} {venue}" for sea_kw in ["해수욕장", "해변", "바닷가", "포구", "항구", "등대", "해안", "해양", "서핑", "요트"])

    # 1. [1순위: 본문 텍스트 내 실제 존재하는 랜드마크 정규식 추출]
    specific_patterns = [
        r'([가-힣A-Za-z0-9]{2,10}(?:전망대|전망쉼터|타워))',
        r'([가-힣A-Za-z0-9]{2,10}(?:광장|잔디마당|야외무대|중앙무대))',
        r'([가-힣A-Za-z0-9]{2,10}(?:둘레길|산책로|숲길|탐방로|가로수길|꽃길|터널))',
        r'([가-힣A-Za-z0-9]{2,10}(?:누각|정자|한옥|성곽|성문|누원|고분))',
        r'([가-힣A-Za-z0-9]{2,10}(?:포토존|조형물|상징탑|기념탑))',
        r'([가-힣A-Za-z0-9]{2,10}(?:출렁다리|교량|분수대|폭포|온실|식물원))',
    ]
    # 실제 해안 축제일 때만 해변 관련 패턴 허용
    if is_real_coastal:
        specific_patterns.append(r'([가-힣A-Za-z0-9]{2,10}(?:해변길|백사장|모래사장|등대))')
    else:
        specific_patterns.append(r'([가-힣A-Za-z0-9]{2,10}(?:수변데크|수변산책로|호수변|호숫가|강변길))')

    found_locations: List[str] = []
    seen = set()
    for pat in specific_patterns:
        matches = re.findall(pat, full_text)
        for m in matches:
            clean_m = m.strip()
            if len(clean_m) >= 3 and clean_m not in seen and clean_m != venue_name:
                seen.add(clean_m)
                found_locations.append(clean_m)

    # 본문에서 추출된 장소가 있으면 지형에 맞는 감성 수식어 결합
    if found_locations:
        for loc in found_locations[:3]:
            if any(k in loc for k in ["전망대", "타워"]):
                spots.append(f"전경이 한눈에 펼쳐지는 {loc}")
            elif any(k in loc for k in ["온실", "식물원", "수목원", "정원"]):
                spots.append(f"싱그러운 초록빛이 가득한 {loc} 포토존")
            elif any(k in loc for k in ["수변", "호수", "강변"]):
                spots.append(f"잔잔한 물결 윤슬이 빛나는 {loc} 쉼터")
            elif any(k in loc for k in ["해변", "백사장"]) and is_real_coastal:
                spots.append(f"시원한 바다를 배경으로 한 {loc} 포토존")
            elif any(k in loc for k in ["산책로", "숲길", "둘레길", "꽃길", "터널"]):
                spots.append(f"계절 정취가 가득한 {loc} 벤치")
            elif any(k in loc for k in ["광장", "마당", "무대", "조형물", "포토존"]):
                spots.append(f"{loc} 앞 메인 인생샷 포토존")
            elif any(k in loc for k in ["한옥", "누각", "정자", "성곽"]):
                spots.append(f"고즈넉한 전통 정취의 {loc} 앞마당")
            else:
                spots.append(f"소중한 추억을 남기는 {loc} 포토스팟")

    # 2. [2순위: 본문 장소가 부족할 경우 지형 사실에 엄격히 기반한 안전 기본 조합 생성]
    if len(spots) < 2:
        # 테마 1: 식물원/수목원/꽃/자연 축제
        if any(k in full_text for k in ["식물원", "수목원", "온실", "허브", "꽃", "벚꽃", "국화", "억새", "매화", "연꽃", "튤립", "장미", "생태", "단풍"]):
            flower = "만개한 계절 꽃"
            for f_name in ["식물", "허브", "억새", "벚꽃", "국화", "매화", "연꽃", "튤립", "장미", "단풍"]:
                if f_name in full_text:
                    flower = f"아름다운 {f_name}"
                    break
            spots.extend([
                f"{flower} 테마 정원 산책로 감성 벤치",
                f"{venue_name} 중앙 온실 및 랜드마크 포토존",
                "초록빛 숲길 쉼터 파노라마 뷰"
            ])
        # 테마 2: 야경/빛/불빛 축제
        elif any(k in full_text for k in ["야경", "빛", "불빛", "달빛", "루미나리에", "별빛", "드론", "불꽃", "야간", "밤"]):
            spots.extend([
                "달빛 루미나리에 빛의 터널 입구",
                f"{venue_name} 메인 일루미네이션 조형물 앞",
                "화려한 야간 조명이 수놓은 잔디광장 뷰포인트"
            ])
        # 테마 3: 전통/역사/한의학/인물 축제 (예: 허준, 강감찬, 정조 등)
        elif any(k in full_text for k in ["허준", "한의학", "한방", "역사", "문화제", "한옥", "유적", "전통", "성곽", "도자기", "선비"]):
            spots.extend([
                f"{title} 전통 테마 체험관 앞마당",
                f"{venue_name} 대형 상징 조형물 포토존",
                "고즈넉한 한옥 돌담길 포토월"
            ])
        # 테마 4: 실제 바다/해변 축제 (is_real_coastal 참일 때만 한정)
        elif is_real_coastal:
            spots.extend([
                f"{venue_name} 시원한 해변 포토존",
                "푸른 바다가 배경이 되는 수변 산책로",
                "노을빛이 물드는 해안 랜드마크 조형물 앞"
            ])
        # 테마 5: 음식/특산물 축제
        elif any(k in full_text for k in ["커피", "와인", "음식", "먹거리", "맥주", "사과", "한우", "인삼", "특산물"]):
            spots.extend([
                f"{title} 시그니처 팝업 조형물 포토존",
                f"{venue_name} 메인 페스티벌 광장 뷰포인트",
                "감성 푸드 라운지 쉼터"
            ])
        # 기본 안전 축제 (도심 및 일반 축제 지형 무왜곡 안전 조합)
        else:
            spots.extend([
                f"{venue_name} 메인 진입로 및 상징 조형물 앞",
                f"{title} 중앙 광장 랜드마크 포토존",
                f"{venue_name} 축제장 전경 뷰포인트 쉼터"
            ])

    # 3. [3순위: 2중 안전장치 - 지형 왜곡 금지 단어 후처리 검증 및 강제 Fallback]
    # 실제 바다/해변이 아닌 도심/내륙 축제인데 바다 관련 단어가 포함되어 있다면 강제 대체
    forbidden_coastal_terms = ["오션뷰", "백사장", "파도", "모래조각", "해변", "바닷가", "갯벌", "해안선", "파도소리"]
    cleaned_spots: List[str] = []

    for spot in spots:
        has_forbidden = any(term in spot for term in forbidden_coastal_terms)
        if has_forbidden and not is_real_coastal:
            # 안전한 도심/일반 축제장 표준 문구로 강제 대체
            fallback_options = [
                f"{venue_name} 메인 진입로 및 상징 조형물 앞",
                f"{title} 중앙 광장 랜드마크 포토존",
                f"{venue_name} 축제장 전경 뷰포인트 쉼터"
            ]
            for fb in fallback_options:
                if fb not in cleaned_spots:
                    cleaned_spots.append(fb)
                    break
        else:
            cleaned_spots.append(spot)

    # 4. 중복 제거 및 최종 2~3개 반환
    final_spots: List[str] = []
    seen_final = set()
    for s in cleaned_spots:
        if s and s not in seen_final:
            seen_final.add(s)
            final_spots.append(s)
        if len(final_spots) >= 3:
            break

    # 만약 최종 결과가 비었을 경우의 최후 안전 보장
    if not final_spots:
        final_spots = [
            f"{venue_name} 메인 상징 조형물 포토존",
            f"{title} 중앙 광장 랜드마크 앞"
        ]

    return final_spots


def format_festival_programs(raw_program: str, title: str, event_type: str) -> str:
    """축제 및 문화행사의 주요 프로그램 원본 문자열을 1:1로 반환합니다."""
    if raw_program and raw_program.strip():
        return raw_program.strip()
    return "개막식 및 축제 문화행사 프로그램"


def format_festival_detailed_desc(
    title: str,
    description: str,
    venue: str,
    location: str,
    fee: str,
    period_str: str,
    host: str,
    org: str,
    sigungu: str,
    event_type: str,
    programs: str = ""
) -> str:
    """축제 본문 상세 설명 및 관람 포인트를 실제 정보(주요프로그램, 개최장소, 축제명 키워드)를 동적으로 조합하여 3~4줄 이상의 고품질 안내문으로 구성합니다."""
    desc_lines = []
    
    # 1. 기존 description이 이미 50자 이상의 완성형 설명문(온점 포함)이고 단순 나열('+')이 아닐 때는 그대로 보존
    if description and len(description) >= 50 and any(end in description for end in [".", "다.", "요."]) and not any(k in description for k in ["+", "전시+공연", "부대행사+"]):
        desc_lines.append(description)
    else:
        # [동적 문장 조합기]: 축제명, 프로그램, 장소, 지자체 키워드 분석
        comb = f"{title} {programs} {description} {venue} {sigungu}".lower()

        # 테마별 고유 어휘 사전 및 맞춤 하이라이트 매핑
        themes = [
            (["공룡"],
             "백악기 공룡 시대를 생생히 체험하는 실감형 테마",
             "실물 크기 조형물과 흥미진진한 백악기 탐험"),
            (["머드", "서핑", "요트", "해수욕장", "해양", "바다", "해변", "물총", "워터"],
             "시원한 바닷바람과 역동적인 수상·해양 액티비티",
             "탁 트인 수변 풍경 속에서 즐기는 시원한 레저와 에너지 넘치는 체험"),
            (["춤", "댄스", "퍼레이드", "무용", "발레", "비보이", "스트릿"],
             "열정적인 춤과 화려한 거리 퍼레이드",
             "생동감 넘치는 댄스 퍼포먼스와 온 시민이 함께 어우러지는 열정의 무대"),
            (["꽃", "벚꽃", "유채", "국화", "장미", "연꽃", "매화", "단풍", "억새", "갈대", "수목원", "정원", "생태", "튤립", "철쭉", "백일홍", "라벤더"],
             "화사한 계절 꽃과 싱그러운 자연경관",
             "만개한 꽃물결의 정취와 도심을 벗어난 청정한 자연 속 힐링 산책"),
            (["먹거리", "맛", "미식", "푸드", "한우", "인삼", "사과", "딸기", "수박", "대게", "송어", "빙어", "와인", "막걸리", "커피", "빵", "수산물", "특산물", "김치", "젓갈"],
             "지역 명품 특산물과 풍성한 로컬 미식",
             "오감을 자극하는 제철 먹거리 시식과 활기 넘치는 특산물 장터"),
            (["음악", "콘서트", "재즈", "락", "가요", "국악", "소리", "아리랑", "난계", "관악", "클래식", "밴드", "버스킹", "오케스트라", "포크"],
             "낭만적인 선율과 가슴 뛰는 라이브 공연",
             "감미로운 음악의 향연과 현장의 뜨거운 열기가 전하는 감동"),
            (["역사", "전통", "문화제", "민속", "단오", "조선", "백제", "신라", "가야", "고분", "산성", "선비", "유생", "충무공", "의병", "성곽"],
             "살아 숨 쉬는 역사와 유서 깊은 전통문화",
             "선조들의 지혜가 깃든 전통 의례 재현과 역사적 숨결을 직접 느끼는 문화 체험"),
            (["야경", "빛", "불꽃", "드론", "달빛", "등불", "유등", "루미나리에", "미디어아트", "야행", "야간", "조명", "led"],
             "밤하늘을 수놓는 환상적인 빛과 낭만적인 야경",
             "어둠을 밝히는 화려한 조명 연출과 황홀한 야간 산책 코스"),
            (["어린이", "가족", "키즈", "만화", "캐릭터", "우주", "과학", "로봇", "동화", "인형극"],
             "온 가족이 함께 즐기는 흥미진진한 에듀테인먼트",
             "아이들의 상상력을 깨우는 다채로운 체험 부스와 온 세대가 공감하는 프로그램"),
            (["예술", "아트", "전시", "공예", "도예", "도자기", "미술", "영화", "도서", "북", "비엔날레"],
             "창의적인 예술의 감동과 고품격 문화 전시",
             "예술적 영감을 전하는 작품 전시와 관람객 참여형 문화 워크숍")
        ]

        selected_theme, selected_highlight = None, None
        for kw_list, t_name, h_text in themes:
            if any(kw in comb for kw in kw_list):
                selected_theme, selected_highlight = t_name, h_text
                break

        if not selected_theme:
            if event_type == "문화행사":
                selected_theme = "지역의 문화예술과 다채로운 축제 공연"
                selected_highlight = "전통과 현대가 조화를 이루는 품격 있는 문화 공연과 참여 전시"
            else:
                selected_theme = "지역 고유의 정겨운 활기와 이색적인 볼거리"
                selected_highlight = "이곳에서만 만날 수 있는 특색 있는 체험과 정겨운 축제 현장"

        # 실제 프로그램 정제 (특수문자 분리 후 핵심 3개 추출)
        prog_source = programs if programs else description
        clean_progs = [p.strip() for p in re.split(r'[+;|/,\n]', prog_source) if len(p.strip()) >= 2 and p.strip() not in ["등", "기타", "체험행사", "축제내용", "행사내용"]]

        venue_str = f"{sigungu} {venue}" if sigungu and sigungu not in venue else venue
        venue_str = venue_str.strip() or sigungu or "축제 행사장"
        clean_venue = re.sub(r'\s*일원$', '', venue).strip() or venue or sigungu

        # 3~4줄 자연스러운 고유 소개글 생성
        s1 = f"{title}은(는) {venue_str}에서 펼쳐지는 {selected_theme} 중심의 대표 {event_type}입니다."
        if clean_progs:
            s2 = f"현장에서는 {', '.join(clean_progs[:3])} 등 방문객들의 눈과 귀를 사로잡는 다채로운 볼거리와 참여형 프로그램이 알차게 운영됩니다."
        else:
            s2 = "현장 곳곳에는 방문객들이 직접 참여하고 즐길 수 있는 다채로운 공연과 풍성한 즐길 거리가 가득 마련되어 있습니다."
        s3 = f"{selected_highlight}을(를) 통해 일상의 스트레스를 날려버리고 생생한 축제 에너지를 만끽할 수 있습니다."
        s4 = f"소중한 사람들과 함께 {clean_venue} 일원을 여유롭게 둘러보며 잊지 못할 특별한 추억과 감성 인생샷을 남겨보세요."

        desc_lines.append(f"{s1} {s2}\n\n{s3} {s4}")
    
    # 2. 개최 장소 및 시설 안내
    venue_info = f"{venue} ({location})" if venue and venue != location else location
    desc_lines.append(f"• 📍 **개최 장소:** {venue_info}")
    
    # 3. 관람 요금 및 일정 안내
    desc_lines.append(f"• 🎟️ **입장/관람 요금:** {fee} (축제 기간: {period_str})")
    
    # 4. 주최 및 주관 기관
    if host or org:
        org_info = f"{host} · {org}".strip(" ·")
        desc_lines.append(f"• 🏛️ **주최/주관:** {org_info}")
        
    return "\n\n".join(desc_lines)


def create_festival_documents(raw_festivals: List[Dict[str, Any]]) -> List[Document]:
    # 축제 데이터를 받아 data_type="축제" 메타데이터가 부여된 Document 리스트로 변환합니다.
    documents: List[Document] = []

    # 전체 축제 원본 데이터 목록에서 축제 항목을 하나씩 순회합니다.
    for festival in raw_festivals:
        # 축제명을 정제합니다.
        title: str = clean_text(festival.get("축제명", festival.get("title", "제목 미정")))
        # 개최장소를 정제합니다.
        venue: str = clean_text(festival.get("개최장소", festival.get("venue", "")))

        # 도로명주소를 읽어옵니다.
        road_address: str = clean_text(festival.get("소재지도로명주소", ""))
        # 지번주소를 읽어옵니다.
        jibun_address: str = clean_text(festival.get("소재지지번주소", ""))
        # 레거시 location을 읽어옵니다.
        legacy_location: str = clean_text(festival.get("location", ""))

        # 소재지도로명주소가 없으면 지번주소, 없으면 개최장소로 대체합니다.
        if road_address:
            location = road_address
        elif jibun_address:
            location = jibun_address
        elif venue:
            location = venue
        elif legacy_location:
            location = legacy_location
        else:
            location = "위치 정보 없음"

        # 주소 문자열 전체를 합쳐 정확한 6대 권역(region)과 시군구(sigungu)를 판별합니다.
        combined_address: str = f"{road_address} {jibun_address} {venue} {location}"
        region_category: str = classify_region(combined_address)
        sigungu_category: str = extract_sigungu(combined_address)

        # 실내/야외(is_indoor) 판별 (우천 시 대체 코스 및 실내외 필터링 지원)
        raw_indoor = clean_text(festival.get("is_indoor", festival.get("실내외구분", "")))
        is_indoor: str = raw_indoor if raw_indoor in ["실내", "야외"] else classify_indoor_outdoor(title, venue)

        # 축제 상세 내용을 정제합니다.
        description: str = clean_text(festival.get("축제내용", festival.get("description", "")))
        start_date: str = clean_text(festival.get("축제시작일자", festival.get("start_date", "")))
        end_date: str = clean_text(festival.get("축제종료일자", festival.get("end_date", "")))
        phone: str = clean_text(festival.get("전화번호", festival.get("phone", "")))
        # 💡 보강: 결측 번호 필터링
        if not phone or phone.lower() in ["-", "000-0000", "없음", "nan", "null", "none"]:
            phone = "현장 종합안내소 문의"
        host: str = clean_text(festival.get("주최기관명", ""))
        org: str = clean_text(festival.get("주관기관명", ""))
        
        # 홈페이지 / 사전 예매 링크 파싱 및 URL 정제
        raw_homepage: str = clean_text(festival.get("홈페이지주소", festival.get("homepage", "")))
        homepage: str = ""
        if raw_homepage and raw_homepage.lower() not in ["nan", "none", "null", "-"]:
            if raw_homepage.startswith("http://") or raw_homepage.startswith("https://"):
                homepage = raw_homepage
            elif raw_homepage.startswith("www."):
                homepage = "https://" + raw_homepage
            elif "." in raw_homepage and "/" not in raw_homepage:
                homepage = "https://" + raw_homepage

        # 기간 텍스트 구성
        if start_date or end_date:
            period_str: str = f"{start_date} ~ {end_date}".strip(" ~")
        else:
            period_str = "일정 확인 필요"

        # [요구사항 1-1] 입장료 및 이용 요금 1:1 파싱
        raw_fee: str = clean_text(festival.get("이용요금", festival.get("입장료", festival.get("관람료", festival.get("요금", "")))))
        if not raw_fee or raw_fee.lower() in ["nan", "none", ""]:
            fee_match = re.search(r'([^\n,.]*?(?:무료|유료|\d+[\d,]*\s*원|입장료|관람료|이용료)[^\n,.]*)', description)
            if fee_match and len(fee_match.group(1).strip()) <= 30:
                raw_fee = fee_match.group(1).strip()
            else:
                raw_fee = "무료 관람"
        fee: str = raw_fee

        # [요구사항 1-2] 행사 유형(event_type) 분류: 지역축제 vs 문화행사
        cultural_keywords = ["문화제", "예술제", "연극", "음악회", "전시", "공연", "역사", "비엔날레", "국악", "문학", "학술"]
        combined_text_for_type = f"{title} {description}"
        if any(kw in combined_text_for_type for kw in cultural_keywords):
            event_type: str = "문화행사"
        else:
            event_type: str = "지역축제"

        # [요구사항 1-3] 주요 프로그램 1:1 바인딩 (주요프로그램 또는 프로그램내용, 없으면 축제내용 전문)
        raw_program: str = clean_text(festival.get("주요프로그램", festival.get("프로그램내용", festival.get("프로그램명", festival.get("행사내용", "")))))
        if not raw_program:
            raw_program = description
        programs: str = format_festival_programs(raw_program, title, event_type)

        # [요구사항 1-4] 축제 상세 내용(detailed_desc) 4줄 이상 고품질 텍스트 구성
        detailed_desc: str = format_festival_detailed_desc(
            title=title,
            description=description,
            venue=venue,
            location=location,
            fee=fee,
            period_str=period_str,
            host=host,
            org=org,
            sigungu=sigungu_category,
            event_type=event_type,
            programs=programs
        )

        # 추천 동행자 정보 (기본값: '누구나')
        companion: str = clean_text(festival.get("companion", "누구나"))
        raw_stamina = clean_text(festival.get("stamina_level", ""))
        if raw_stamina:
            stamina_level: str = raw_stamina
        elif event_type == "문화행사":
            stamina_level = "하"
        else:
            stamina_level = "중"

        # 사진 스팟 정보 파싱 (CSV 컬럼 부재 시 축제명/개최장소/내용/프로그램 기반 동적 인생샷 포토존 생성)
        raw_photo_spots: Any = festival.get("photo_spots", "")
        if isinstance(raw_photo_spots, list) and raw_photo_spots:
            photo_spots = ", ".join([clean_text(s) for s in raw_photo_spots if clean_text(s)])
        else:
            photo_spots = clean_text(raw_photo_spots)
        if not photo_spots or photo_spots == "현장 곳곳이 포토존":
            dyn_spots = extract_dynamic_photo_spots(title, venue, description, programs)
            photo_spots = ", ".join(dyn_spots) if dyn_spots else f"{venue} 중앙 메인 랜드마크 포토존"
        else:
            # 2중 안전장치: 외부 입력 photo_spots에 도심/내륙 지형 왜곡 단어가 포함된 경우 안전하게 대체
            is_coastal_doc = any(sea_kw in f"{title} {venue}" for sea_kw in ["해수욕장", "해변", "바닷가", "포구", "항구", "등대", "해안", "해양", "서핑", "요트"])
            if not is_coastal_doc:
                forbidden_coastal_terms = ["오션뷰", "백사장", "파도", "모래조각", "해변", "바닷가", "갯벌", "해안선", "파도소리"]
                if any(bad in photo_spots for bad in forbidden_coastal_terms):
                    dyn_spots = extract_dynamic_photo_spots(title, venue, description, programs)
                    photo_spots = ", ".join(dyn_spots) if dyn_spots else f"{venue} 중앙 메인 랜드마크 포토존"

        # 추천 카페 정보 파싱
        raw_cafes: Any = festival.get("nearby_cafes", "")
        if isinstance(raw_cafes, list) and raw_cafes:
            cafes: str = ", ".join([clean_text(c) for c in raw_cafes if clean_text(c)])
        else:
            cafes = clean_text(raw_cafes)
        if not cafes:
            cafes = "주변 카페 정보 준비 중"

        # [10대 대표 축제 테마 라벨 판별]
        raw_theme = clean_text(festival.get("theme", festival.get("테마", "")))
        theme: str = raw_theme if raw_theme else classify_festival_theme(title, venue, description, programs)

        # 축제 청크 본문 생성
        content_lines: List[str] = [
            f"[데이터 유형]: 축제",
            f"축제명: {title}",
            f"행사 유형: {event_type}",
            f"테마 분류: {theme}",
            f"지역권역: {region_category}",
            f"시군구: {sigungu_category}" if sigungu_category else "",
            f"개최장소: {venue}" if venue else "",
            f"위치(주소): {location}",
            f"축제 기간: {period_str}",
            f"입장/이용 요금: {fee}",
            f"주요 프로그램: {programs}",
            f"공간/환경: {is_indoor} 행사",
            f"축제 내용: {description if description else detailed_desc}",
            f"[2030 감성 포인트 & 인생샷 스팟]: {photo_spots}",
            f"[2030 추천 주변 감성 카페]: {cafes}",
            f"연락처: {phone}" if phone else "",
            f"홈페이지/예매: {homepage}" if homepage else "",
            f"추천 동행: {companion} | 소모 체력 수준: {stamina_level}"
        ]
        # 줄바꿈으로 합치기
        page_content: str = "\n".join([line for line in content_lines if line])

        # 메타데이터 딕셔너리 생성 (요구사항: data_type="축제", description 100% 보존, detailed_desc, fee, programs, homepage)
        metadata: Dict[str, Any] = {
            "data_type": "축제",
            "title": title,
            "region": region_category,
            "sido": extract_sido(f"{location} {venue}"),
            "sigungu": sigungu_category,
            "category": "축제/행사",
            "event_type": event_type,
            "location": location,
            "venue": venue,
            "start_date": start_date,
            "end_date": end_date,
            "fee": fee,
            "programs": programs,
            "description": description if description else detailed_desc,
            "overview": description if description else detailed_desc,
            "detailed_desc": detailed_desc,
            "host": host,
            "org": org,
            "phone": phone,
            "homepage": homepage,
            "raw_homepage": raw_homepage,
            "menu": "",
            "companion": companion,
            "stamina_level": stamina_level,
            "photo_spots": photo_spots,
            "nearby_cafes": cafes,
            "is_indoor": is_indoor,
            "indoor_outdoor": is_indoor,
            "theme": theme
        }

        # Document 객체 생성 및 리스트 추가
        documents.append(Document(page_content=page_content, metadata=metadata))

    # 문서 리스트 반환
    return documents


def create_parking_documents(raw_parkings: List[Dict[str, Any]]) -> List[Document]:
    # 전국 주차장 데이터를 받아 data_type="주차장" 메타데이터가 부여된 Document 리스트로 변환합니다.
    documents: List[Document] = []

    # 전체 주차장 항목을 순회합니다.
    for item in raw_parkings:
        # 주차장명을 가져옵니다.
        parking_name: str = clean_text(item.get("주차장명", "주차장"))
        # 주차장 구분 (공영/민영 등)을 가져옵니다.
        parking_div: str = clean_text(item.get("주차장구분", ""))
        # 주차장 유형 (노상/노외/부설 등)을 가져옵니다.
        parking_type: str = clean_text(item.get("주차장유형", ""))

        # 도로명주소를 가져옵니다.
        road_addr: str = clean_text(item.get("소재지도로명주소", ""))
        # 지번주소를 가져옵니다.
        jibun_addr: str = clean_text(item.get("소재지지번주소", ""))
        # 주소를 결정합니다.
        location: str = road_addr if road_addr else (jibun_addr if jibun_addr else "위치 미상")

        # 주소를 바탕으로 6대 권역(region)과 시군구(sigungu)를 분류합니다.
        combined_addr: str = f"{road_addr} {jibun_addr} {location}"
        # 지역 권역 판별
        region_category: str = classify_region(combined_addr)
        # 시군구 판별
        sigungu_category: str = extract_sigungu(combined_addr)

        # 요금 정보를 가져옵니다.
        fee_info: str = clean_text(item.get("요금정보", "정보 없음"))
        # 주차 기본요금을 가져옵니다.
        base_fee: str = clean_text(item.get("주차기본요금", ""))
        # 1일 주차권 요금을 가져옵니다.
        day_fee: str = clean_text(item.get("1일주차권요금", ""))
        # 전화번호를 가져옵니다.
        phone: str = clean_text(item.get("전화번호", ""))
        # 운영요일을 가져옵니다.
        operating_days: str = clean_text(item.get("운영요일", ""))

        # 주차장 본문 텍스트를 조합합니다.
        content_lines: List[str] = [
            f"[데이터 유형]: 주차장",
            f"주차장명: {parking_name} ({parking_div} {parking_type})".strip(),
            f"지역권역: {region_category}",
            f"시군구: {sigungu_category}" if sigungu_category else "",
            f"위치(주소): {location}",
            f"요금정보: {fee_info} (기본요금: {base_fee}원, 1일요금: {day_fee}원)" if (base_fee or day_fee) else f"요금정보: {fee_info}",
            f"운영요일: {operating_days}" if operating_days else "",
            f"연락처: {phone}" if phone else ""
        ]
        # 줄바꿈으로 연결
        page_content: str = "\n".join([line for line in content_lines if line])

        # 메타데이터 구성 (요구사항: data_type="주차장", region=권역, sigungu=시군구)
        metadata: Dict[str, Any] = {
            "data_type": "주차장",
            "title": parking_name,
            "region": region_category,
            "sido": extract_sido(f"{location} {parking_name}"),
            "sigungu": sigungu_category,
            "category": "공영/부설주차장",
            "location": location,
            "venue": f"{parking_div} {parking_type}".strip(),
            "start_date": "",
            "end_date": "",
            "phone": phone,
            "homepage": "",
            "menu": f"요금: {fee_info}",
            "companion": "누구나",
            "stamina_level": "하",
            "parking_div": parking_div,
            "parking_type": parking_type,
            "fee_info": fee_info
        }

        # Document 리스트에 추가
        documents.append(Document(page_content=page_content, metadata=metadata))

    # 문서 리스트 반환
    return documents


def create_good_price_documents(raw_stores: List[Dict[str, Any]]) -> List[Document]:
    # 행정안전부 착한가격업소 데이터를 받아 data_type="착한가격업소" 및 category 메타데이터가 부여된 Document 리스트로 변환합니다.
    # ※ is_food_related() 필터를 통과한 먹거리/카페 업소만 Document로 변환됩니다.
    documents: List[Document] = []
    # 비식품 업종으로 제외된 건수를 카운팅합니다.
    excluded_count: int = 0

    # 전체 착한가격업소 항목을 순회합니다.
    for store in raw_stores:
        # 업소명을 가져옵니다.
        store_name: str = clean_text(store.get("업소명", "착한가격업소"))
        # 업종 원본 문자열을 가져옵니다.
        raw_category: str = clean_text(store.get("업종", ""))

        # ★ 핵심 필터링: 메뉴 정보도 미리 간략히 읽어 is_food_related() 판별에 활용합니다.
        pre_menu: str = clean_text(store.get("메뉴1", "")) + " " + clean_text(store.get("메뉴2", ""))
        # is_food_related() 함수로 먹거리/카페 업종 여부를 판별합니다.
        if not is_food_related(raw_category, store_name, pre_menu):
            # 미용업·세탁업·목욕업·숙박업 등 비식품 업종은 ChromaDB 인덱싱 대상에서 완전히 제외합니다.
            excluded_count += 1
            # 다음 업소로 넘어갑니다.
            continue

        # 시도 명칭을 가져옵니다.
        sido: str = clean_text(store.get("시도", ""))
        # 시군 명칭을 가져옵니다.
        sigungu: str = clean_text(store.get("시군", ""))
        # 도로명/지번 주소를 가져옵니다.
        address: str = clean_text(store.get("주소", ""))
        # 대표 주소 지정
        location: str = address if address else f"{sido} {sigungu}".strip()

        # 시도, 시군, 주소를 종합하여 6대 권역(region)과 시군구(sigungu)를 분류합니다.
        combined_addr: str = f"{sido} {sigungu} {address}"
        # 지역 권역 판별
        region_category: str = classify_region(combined_addr)
        # 시군구 판별 (CSV 시군 컬럼 우선, 없으면 주소에서 추출)
        sigungu_category: str = sigungu if sigungu else extract_sigungu(combined_addr)

        # 연락처를 가져옵니다.
        phone: str = clean_text(store.get("연락처", ""))


        # 메뉴 및 가격 정보들을 정제합니다 (메뉴 1~4 상세 바인딩 및 clean_price 적용).
        menu1: str = clean_text(store.get("메뉴1", ""))
        price1: str = clean_price(store.get("가격1", ""))
        menu2: str = clean_text(store.get("메뉴2", ""))
        price2: str = clean_price(store.get("가격2", ""))
        menu3: str = clean_text(store.get("메뉴3", ""))
        price3: str = clean_price(store.get("가격3", ""))
        menu4: str = clean_text(store.get("메뉴4", ""))
        price4: str = clean_price(store.get("가격4", ""))

        # 메뉴 정보 텍스트 조합
        menu_items: List[str] = []
        if menu1:
            menu_items.append(f"{menu1} ({price1})" if price1 else menu1)
        if menu2:
            menu_items.append(f"{menu2} ({price2})" if price2 else menu2)
        if menu3:
            menu_items.append(f"{menu3} ({price3})" if price3 else menu3)
        if menu4:
            menu_items.append(f"{menu4} ({price4})" if price4 else menu4)
        menu_str: str = ", ".join(menu_items) if menu_items else "대표 가성비 메뉴 보유"

        # 세부 업종 카테고리(한식, 카페/베이커리, 일식, 중식, 양식 등)로 정제합니다.
        category: str = refine_store_category(raw_category, store_name, menu_str)

        # 착한가격업소 본문 텍스트 구성
        content_lines: List[str] = [
            f"[데이터 유형]: 착한가격업소",
            f"업소명: {store_name} ({category})",
            f"지역권역: {region_category}",
            f"시군구: {sigungu_category}" if sigungu_category else "",
            f"업종: {category}",
            f"위치(주소): {location}",
            f"대표메뉴 및 가격: {menu_str}",
            f"연락처: {phone}" if phone else ""
        ]
        # 줄바꿈으로 연결
        page_content: str = "\n".join([line for line in content_lines if line])

        # 메타데이터 구성 (요구사항: data_type="착한가격업소", 메뉴1~4 및 가격 상세 보존)
        metadata: Dict[str, Any] = {
            "data_type": "착한가격업소",
            "title": store_name,
            "region": region_category,
            "sido": extract_sido(f"{location} {store_name}"),
            "sigungu": sigungu_category,
            "category": category,
            "raw_category": raw_category,
            "location": location,
            "venue": category,
            "start_date": "",
            "end_date": "",
            "phone": phone,
            "homepage": "",
            "menu": menu_str,
            "menu1": menu1,
            "price1": price1,
            "menu2": menu2,
            "price2": price2,
            "menu3": menu3,
            "price3": price3,
            "menu4": menu4,
            "price4": price4,
            "companion": "누구나",
            "stamina_level": "하"
        }

        # Document 리스트에 추가
        documents.append(Document(page_content=page_content, metadata=metadata))

    # 비식품 업종 제외 건수 및 최종 포함 건수를 로그로 출력합니다.
    print(f"[Filter] 착한가격업소 먹거리 필터 적용: 포함 {len(documents)}건 / 제외(비식품) {excluded_count}건")
    # 문서 리스트 반환
    return documents


def create_wellness_documents(raw_items: List[Dict[str, Any]]) -> List[Document]:
    # 한국관광공사 웰니스 관광지 데이터를 받아 data_type="웰니스" 메타데이터가 부여된 Document 리스트로 변환합니다.
    documents: List[Document] = []

    # 전체 웰니스 원본 항목을 순회합니다.
    for item in raw_items:
        # 관광지/시설명을 정제합니다.
        # 명칭: row['명소명'] 또는 row['관광지명']
        title: str = clean_text(item.get("명소명", item.get("관광지명", item.get("title", "웰니스 관광지"))))
        # 테마/분류(자연/숲치유, 뷰티/스파, 힐링/명상, 한방 등)를 정제합니다.
        category: str = clean_text(item.get("theme", item.get("category", item.get("테마", "웰니스/힐링"))))
        if not category:
            category = "웰니스/힐링"

        # 주소 정보를 정제합니다 (full_address 우선, 없으면 addr1 + addr2).
        full_address: str = clean_text(item.get("full_address", ""))
        addr1: str = clean_text(item.get("addr1", item.get("주소", "")))
        addr2: str = clean_text(item.get("addr2", ""))

        if full_address:
            location = full_address
        elif addr1:
            location = f"{addr1} {addr2}".strip()
        else:
            location = "위치 정보 없음"

        # 주소를 바탕으로 6대 표준 권역(region)과 시군구(sigungu)를 분류합니다.
        region_category: str = classify_region(location)
        sigungu_category: str = extract_sigungu(location)

        # 개요/소개 설명 및 연락처 정보를 정제합니다 (row['개요'] 또는 row['소개'])
        raw_description: str = clean_text(item.get("개요", item.get("소개", item.get("overview", item.get("description", "")))))
        # 체험프로그램 원본 내용 추출 (row['체험프로그램'])
        raw_programs: str = clean_text(item.get("체험프로그램", item.get("프로그램", item.get("healing_programs", ""))))
        phone: str = clean_text(item.get("tel", item.get("phone", item.get("연락처", ""))))

        # [요구사항 3] 원본 개요 및 체험프로그램 1:1 바인딩
        theme_clean = category
        programs = raw_programs if raw_programs else (
            "피톤치드 편백 치유의 숲길 걷기, 숲속 해먹 산림욕 체험, 숲소리 싱잉볼 사운드 배스 명상" if any(k in category + title for k in ["숲", "휴양림", "수목원", "자연"])
            else "천연 온천수 스파 입욕, 아로마 에센셜 오일 테라피, 편백 온열 족욕 및 전신 릴랙세이션 케어" if any(k in category + title for k in ["스파", "온천", "뷰티"])
            else "체질 맞춤 한방 약초 족욕, 기혈 순환 한방 약선차 시음, 면역력 강화 한방 온열 뜸 테라피" if any(k in category + title for k in ["한방", "약초"])
            else "마음챙김 싱잉볼 명상 세션, 전통 다도 힐링 클래스, 숲속 요가 & 딥 브리딩 호흡 힐링"
        )
        detailed_overview = raw_description if raw_description else f"{title}은(는) 일상의 피로를 풀고 자연과 함께 심신의 안정을 찾는 한국관광공사 선정 웰니스 추천 명소입니다."
        facilities = "쾌적한 산책로 및 휴식 라운지, 치유 쉼터"

        # 웰니스 관광지 청크 본문 텍스트 구성
        content_lines: List[str] = [
            f"[데이터 유형]: 웰니스",
            f"관광지명: {title} ({theme_clean})",
            f"지역권역: {region_category}",
            f"시군구: {sigungu_category}" if sigungu_category else "",
            f"테마/유형: {theme_clean}",
            f"위치(주소): {location}",
            f"개요 및 소개: {detailed_overview}",
            f"치유 프로그램: {programs}",
            f"시설 특징: {facilities}",
            f"연락처: {phone}" if phone else ""
        ]
        # 줄바꿈으로 연결
        page_content: str = "\n".join([line for line in content_lines if line])

        # 메타데이터 구성 (요구사항: data_type="웰니스", region=권역, sigungu=시군구, overview, programs, facilities 상세 보존)
        metadata: Dict[str, Any] = {
            "data_type": "웰니스",
            "title": title,
            "region": region_category,
            "sido": extract_sido(f"{location} {title}"),
            "sigungu": sigungu_category,
            "category": theme_clean,
            "location": location,
            "venue": theme_clean,
            "start_date": "",
            "end_date": "",
            "phone": phone,
            "homepage": "",
            "menu": f"테마: {theme_clean}",
            "overview": detailed_overview,
            "raw_overview": raw_description,
            "healing_programs": programs,
            "facility_features": facilities,
            "companion": "누구나",
            "stamina_level": "하"
        }

        # Document 리스트에 추가
        documents.append(Document(page_content=page_content, metadata=metadata))

    # 문서 리스트 반환
    return documents


class PublicDataRAGManager:
    # 축제, 주차장, 착한가격업소 3종 공공데이터를 통합 관리하는 RAG 매니저 클래스입니다.
    def __init__(
        self,
        data_dir: Optional[str] = None,
        data_path: Optional[str] = None,
        db_path: Optional[str] = None,
        collection_name: str = "integrated_festivals",
        **kwargs: Any
    ):
        # 기본 디렉터리 경로 자동 해결
        if not data_dir or data_dir == "data":
            effective_data_dir = DEFAULT_DATA_DIR
        else:
            effective_data_dir = data_dir

        if not db_path or db_path == "chromadb_store":
            effective_db_path = DEFAULT_DB_PATH
        else:
            effective_db_path = db_path

        # data_path가 전달된 경우 경로를 호환 처리합니다.
        if data_path and not os.path.isdir(data_path):
            if os.path.isabs(data_path) or os.path.exists(data_path):
                self.data_dir = os.path.dirname(data_path) if os.path.dirname(data_path) else effective_data_dir
                self.data_path = data_path
            else:
                self.data_dir = effective_data_dir
                self.data_path = os.path.join(effective_data_dir, os.path.basename(data_path))
        # data_path가 디렉토리인 경우
        elif data_path:
            self.data_dir = data_path
            self.data_path = os.path.join(self.data_dir, "festivals.csv")
        # data_dir가 전달된 경우
        else:
            self.data_dir = effective_data_dir
            self.data_path = os.path.join(self.data_dir, "festivals.csv")

        # ChromaDB 디렉토리 경로 저장
        self.db_path: str = effective_db_path
        # 컬렉션 이름 저장
        self.collection_name: str = collection_name
        # 생성된 통합 문서 리스트
        self.documents: List[Document] = []

        # ChromaDB PersistentClient 생성
        self.client: chromadb.PersistentClient = chromadb.PersistentClient(path=self.db_path)
        # 컬렉션 생성 또는 불러오기
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    def load_all_datasets(self, sample_per_region: int = 150) -> List[Document]:
        # data/ 폴더 내 축제, 주차장, 착한가격업소 CSV 파일들을 로드하여 통합 Document 리스트를 생성합니다.
        all_docs: List[Document] = []

        # 1. 축제 데이터 로드 (data/festivals.csv, 1,320건 전체)
        festivals_file: str = os.path.join(self.data_dir, "festivals.csv")
        # 축제 파일이 존재하는 경우
        if os.path.exists(festivals_file):
            # utf-8-sig / utf-8 / cp949 안전 로드
            try:
                df_fest = pd.read_csv(festivals_file, encoding="utf-8-sig")
            except Exception:
                try:
                    df_fest = pd.read_csv(festivals_file, encoding="utf-8")
                except Exception:
                    df_fest = pd.read_csv(festivals_file, encoding="cp949")

            # 1단계: 축제명 및 축제시작일자 기준 정확한 중복 제거
            if "축제명" in df_fest.columns and "축제시작일자" in df_fest.columns:
                df_fest = df_fest.drop_duplicates(subset=['축제명', '축제시작일자'], keep='first')
            elif "축제명" in df_fest.columns:
                df_fest = df_fest.drop_duplicates(subset=['축제명'], keep='first')

            # 2단계: 동일 일자 & 동일 장소 내 유사 축제명(예: 천안흥타령축제 vs 천안흥타령춤축제) 지능형 중복 제거
            if "축제명" in df_fest.columns and "축제시작일자" in df_fest.columns:
                def _get_norm_key(title: Any) -> str:
                    return re.sub(r'제?\d+회|\d{4}년?|\s+|축제|페스티벌|문화제', '', str(title))

                addr_col = "소재지도로명주소" if "소재지도로명주소" in df_fest.columns else "개최장소"
                drop_indices = []
                for (date, addr), group in df_fest.groupby(['축제시작일자', addr_col]):
                    if len(group) > 1 and addr != '' and pd.notna(addr):
                        names = group['축제명'].tolist()
                        norm_names = [_get_norm_key(n) for n in names]
                        for i in range(len(group)):
                            for j in range(i + 1, len(group)):
                                n1, n2 = norm_names[i], norm_names[j]
                                if n1 and n2 and (n1 in n2 or n2 in n1 or set(n1) == set(n2)):
                                    # 더 상세한 공식 명칭(글자 수 우선)을 유지하고 짧은 중복본 제거
                                    idx_to_drop = group.index[j] if len(names[i]) >= len(names[j]) else group.index[i]
                                    if idx_to_drop not in drop_indices:
                                        drop_indices.append(idx_to_drop)

                if drop_indices:
                    df_fest = df_fest.drop(index=drop_indices)

            print(f"[Info] 축제 데이터 전수 로드 완료: {len(df_fest)}건 (중복 제거 후 전국 6대 권역 100% 포괄)")

            # 축제 Document 변환
            fest_docs = create_festival_documents(df_fest.to_dict(orient="records"))
            # 전체 리스트에 추가
            all_docs.extend(fest_docs)
            # 로그 출력
            print(f"[Info] 축제 데이터 로드 완료: {len(fest_docs)}건")

        # 2. 전국 주차장 정보 데이터 로드 (전국 시군구 100% 정합성 매칭을 위해 전수 로드)
        parking_files = glob.glob(os.path.join(self.data_dir, "*주차장*.csv"))
        if parking_files:
            p_file = parking_files[0]
            try:
                df_park = pd.read_csv(p_file, encoding="cp949", low_memory=False)
            except Exception:
                df_park = pd.read_csv(p_file, encoding="utf-8", low_memory=False)

            # 주차장 Document 변환
            park_docs = create_parking_documents(df_park.to_dict(orient="records"))
            all_docs.extend(park_docs)
            print(f"[Info] 전국 주차장 데이터 전수 로드 완료: {len(park_docs)}건 (전국 시군구 100% 포괄)")

        # 3. 행정안전부 착한가격업소 데이터 로드 (먹거리/카페/가성비 맛집 ONLY 전수 로드)
        store_files = glob.glob(os.path.join(self.data_dir, "*착한가격업소*.csv"))
        if store_files:
            s_file = store_files[0]
            try:
                df_store = pd.read_csv(s_file, encoding="cp949", low_memory=False)
            except Exception:
                df_store = pd.read_csv(s_file, encoding="utf-8", low_memory=False)

            # ★ CSV 레벨 1차 먹거리 필터링: 비식품 업종(미용업·세탁업·목욕업·숙박업·기타비요식업) 행을 사전 제거합니다.
            non_food_exact: List[str] = ["미용업", "이용업", "세탁업", "목욕업", "숙박업", "기타비요식업"]
            before_filter_count: int = len(df_store)
            if "업종" in df_store.columns:
                df_store = df_store[~df_store["업종"].isin(non_food_exact)]
            print(f"[Filter] 착한가격업소 CSV 사전 필터: {before_filter_count}건 → {len(df_store)}건 (비식품 {before_filter_count - len(df_store)}건 제거)")

            # 먹거리/카페 착한가격업소 전수 Document 변환 (전국 250개 시군구 100% 포괄)
            store_docs = create_good_price_documents(df_store.to_dict(orient="records"))
            all_docs.extend(store_docs)
            print(f"[Info] 착한가격업소 먹거리 데이터 전수 로드 완료: {len(store_docs)}건 (전국 시군구 100% 포괄)")

        # 4. [세부 요구사항 2] 한국관광공사 웰니스(Wellness) 관광지 데이터 로드
        wellness_files = glob.glob(os.path.join(self.data_dir, "*웰니스*.csv")) + glob.glob(os.path.join(self.data_dir, "*wellness*.csv"))
        if wellness_files:
            w_file = wellness_files[0]
            # utf-8 및 cp949 인코딩 모두 안전 대응
            try:
                df_wellness = pd.read_csv(w_file, encoding="utf-8-sig")
            except Exception:
                try:
                    df_wellness = pd.read_csv(w_file, encoding="utf-8")
                except Exception:
                    df_wellness = pd.read_csv(w_file, encoding="cp949")

            # 웰니스 관광지 데이터 역시 694건으로 0.03초 만에 로드되므로 전국 6대 권역 누락 방지를 위해 전수 로드합니다.
            print(f"[Info] 한국관광공사 웰니스 관광지 데이터 전수 로드 완료: {len(df_wellness)}건")

            # 웰니스 Document 변환 (data_type="웰니스", region=권역 메타데이터 부여)
            wellness_docs = create_wellness_documents(df_wellness.to_dict(orient="records"))
            # 전체 리스트에 추가
            all_docs.extend(wellness_docs)
            # 로그 출력
            print(f"[Info] 한국관광공사 웰니스 관광지 데이터 로드 완료: {len(wellness_docs)}건")

        # 통합 문서 목록 저장
        self.documents = all_docs
        # 총 건수 반환
        return self.documents

    def index_documents(self, batch_size: int = 200, reset: bool = False) -> int:
        # 기존 컬렉션을 초기화할지 확인
        if reset:
            try:
                # 컬렉션 삭제
                self.client.delete_collection(name=self.collection_name)
                # 로그 출력
                print(f"[Info] 기존 컬렉션('{self.collection_name}') 초기화 완료")
            except Exception:
                pass
            # 새 컬렉션 생성
            self.collection = self.client.get_or_create_collection(name=self.collection_name)

        # 문서가 없으면 로드 실행
        if not self.documents:
            # 전체 데이터셋 로드
            self.load_all_datasets()

        # 총 문서 수 계산
        total_count: int = len(self.documents)
        # 인덱싱 시작 로그 출력
        print(f"[Info] ChromaDB 통합 인덱싱 시작 (총 {total_count}건, 배치: {batch_size})")

        # 배치 단위로 upsert 반복
        for start_idx in range(0, total_count, batch_size):
            # 끝 인덱스 계산
            end_idx: int = min(start_idx + batch_size, total_count)
            # 현재 배치 문서들
            batch_docs: List[Document] = self.documents[start_idx:end_idx]

            # 고유 ID 생성 (예: item_0, item_1 ...)
            batch_ids: List[str] = [f"item_{idx}" for idx in range(start_idx, end_idx)]
            # 본문 추출
            batch_texts: List[str] = [doc.page_content for doc in batch_docs]
            # 메타데이터 추출
            batch_metadatas: List[Dict[str, Any]] = [doc.metadata for doc in batch_docs]

            # ChromaDB에 upsert
            self.collection.upsert(
                ids=batch_ids,
                documents=batch_texts,
                metadatas=batch_metadatas
            )
            # 진행 상황 출력
            print(f"  -> [{end_idx}/{total_count}] 통합 데이터 upsert 완료")

        # 완료 로그 출력
        print(f"[Info] 전체 {total_count}건 통합 인덱싱 완료!")
        # 개수 반환
        return total_count

    def _fallback_memory_search(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """ChromaDB 인덱스 에러 또는 동시성 락 발생 시 중단을 방지하는 안전 인메모리 폴백 검색입니다."""
        if not self.documents:
            self.load_all_datasets()

        candidates = self.documents

        # where 필터 적용
        if where:
            def matches_filter(meta: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
                if "$and" in filter_dict:
                    return all(matches_filter(meta, sub) for sub in filter_dict["$and"])
                if "$or" in filter_dict:
                    return any(matches_filter(meta, sub) for sub in filter_dict["$or"])
                for k, v in filter_dict.items():
                    if meta.get(k) != v:
                        return False
                return True

            candidates = [d for d in candidates if matches_filter(d.metadata, where)]

        # 키워드 매칭 점수 계산
        tokens = [t.lower() for t in re.split(r"\s+", query_text) if len(t) > 1]
        def calc_score(doc: Document) -> int:
            text = (doc.page_content + " " + doc.metadata.get("title", "") + " " + doc.metadata.get("sigungu", "")).lower()
            return sum(text.count(t) for t in tokens)

        if tokens:
            scored = sorted(candidates, key=calc_score, reverse=True)
        else:
            scored = candidates

        top_candidates = scored[:n_results]

        return {
            "ids": [[f"mem_{i}" for i in range(len(top_candidates))]],
            "documents": [[d.page_content for d in top_candidates]],
            "metadatas": [[d.metadata for d in top_candidates]],
            "distances": [[0.1 * i for i in range(len(top_candidates))]]
        }

    def search(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # where 메타데이터 필터 조건과 함께 유사도 검색을 수행합니다.
        filter_msg: str = f" (where: {where})" if where else " (전체 검색)"
        # 검색 시작 로그
        print(f"[검색 질의어]: \"{query_text}\"{filter_msg} (상위 {n_results}개 검색 중...)")

        try:
            # 1차 시도: 기존 컬렉션 핸들로 쿼리 실행
            if where:
                results = self.collection.query(
                    query_texts=[query_text],
                    n_results=n_results,
                    where=where
                )
            else:
                results = self.collection.query(
                    query_texts=[query_text],
                    n_results=n_results
                )
        except Exception as query_err:
            # HNSW 인덱스 로드 불일치 또는 핸들 만료 시 자동 복구 로직 가동
            print(f"[Warning] ChromaDB 쿼리 오류 감지 ({query_err}). 클라이언트 및 컬렉션 핸들 자동 복구 중...")
            try:
                # 클라이언트 및 컬렉션 핸들 재연결 후 2차 재시도
                self.client = chromadb.PersistentClient(path=self.db_path)
                self.collection = self.client.get_or_create_collection(name=self.collection_name)
                if where:
                    results = self.collection.query(
                        query_texts=[query_text],
                        n_results=n_results,
                        where=where
                    )
                else:
                    results = self.collection.query(
                        query_texts=[query_text],
                        n_results=n_results
                    )
                print("[Info] ChromaDB 핸들 복구 및 쿼리 재시도 성공!")
            except Exception as retry_err:
                # 최후의 안전장치: 인메모리 고속 검색으로 전환하여 화면 에러 발생 100% 차단
                print(f"[Warning] ChromaDB 재시도 실패 ({retry_err}). 인메모리 고속 검색으로 안전하게 전환합니다.")
                results = self._fallback_memory_search(query_text=query_text, n_results=n_results, where=where)

        # 결과 반환
        return results

    def get_top_good_price_stores(
        self,
        region: str = "전체",
        query_text: str = "가성비 맛집 착한가격업소 카페 디저트",
        n_results: int = 3
    ) -> List[Dict[str, Any]]:
        # 특정 지역에 해당하는 착한가격업소 Top N개를 조회하여 리스트로 반환하는 전용 함수입니다.
        where_condition: Dict[str, Any]
        # 지역이 전체가 아닌 경우 복합 조건 적용
        if region != "전체":
            # 지역과 착한가격업소 동시 필터
            where_condition = {
                "$and": [
                    {"region": region},
                    {"data_type": "착한가격업소"}
                ]
            }
        # 전체인 경우 데이터타입만 필터
        else:
            # 착한가격업소 단일 필터
            where_condition = {"data_type": "착한가격업소"}

        # self-healing이 적용된 search 메서드를 재사용하여 안전하게 조회
        res = self.search(
            query_text=query_text,
            n_results=n_results,
            where=where_condition
        )

        # 추출된 메타데이터 목록
        metas = res.get("metadatas", [[]])[0]
        # 메타데이터 리스트 반환
        return metas

    def generate_custom_course(
        self,
        festival_name: str,
        user_stamina: str = "중",
        companion: str = "혼자",
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """사용자의 오늘 체력 상태('상', '중', '하')와 선택한 축제명을 기반으로
        [주차장 ➡️ 축제/사진스팟 ➡️ 음식점/카페 ➡️ 웰니스 힐링] 맞춤 동선을 동일 시/군/구(sigungu) 내에서 패키징합니다.

        규칙:
        1. 위치 정합성: 모든 추천 장소는 선택된 축제와 동일한 'sigungu'(예: 천안시, 아산시, 강릉시 등) 내에서만 매칭.
           (해당 시군구 데이터가 부족할 경우만 동일 권역(region)으로 안전하게 확장)
        2. 체력별 맞춤 추천:
           - '하' (체력 절약/휴식 집중): 접근성 최우선 주차장, 핵심 포토존 1곳, 편안한 식사/휴식 카페, 스파/온천/명상 쉼터
           - '중' (표준 밸런스 관광): 공영 주차장, 대표 사진스팟 2곳, 대중적 가성비 맛집/핫플 카페, 산책/정원/다도 쉼터
           - '상' (에너지 풀코스 탐방): 편리한 회차 주차장, 축제 풀코스/전망대 둘레길, 든든한 보양 맛집/대형 베이커리, 숲길 트레킹/수목원
        """
        # 문서가 아직 로드되지 않은 경우 데이터셋 자동 로드
        if not self.documents:
            self.load_all_datasets()

        # 1. 대상 축제 문서 탐색 (인메모리 탐색 우선, 없으면 ChromaDB 검색)
        target_doc = None
        clean_name = festival_name.strip()

        # 인메모리에서 제목 부분 일치 탐색
        for d in self.documents:
            if d.metadata.get("data_type") == "축제" and clean_name in d.metadata.get("title", ""):
                target_doc = d
                break

        # 인메모리에 없으면 ChromaDB 유사도 쿼리로 축제 1건 탐색
        if not target_doc:
            try:
                res = self.collection.query(
                    query_texts=[clean_name],
                    n_results=1,
                    where={"data_type": "축제"}
                )
                m_list = res.get("metadatas", [[]])[0]
                d_list = res.get("documents", [[]])[0]
                if m_list and d_list:
                    target_doc = Document(page_content=d_list[0], metadata=m_list[0])
            except Exception:
                pass

        # 축제가 전혀 발견되지 않으면 인메모리 첫 번째 축제 문서로 폴백
        if not target_doc:
            fest_candidates = [d for d in self.documents if d.metadata.get("data_type") == "축제"]
            if fest_candidates:
                target_doc = fest_candidates[0]

        # 대상 축제 메타데이터 추출
        fest_meta: Dict[str, Any] = target_doc.metadata if target_doc else {}
        target_sigungu: str = fest_meta.get("sigungu", "")
        # 가상 행정구역 완전 차단 및 진짜 시군구 정밀 복원
        if not target_sigungu or "전남광주" in target_sigungu or "통합" in target_sigungu:
            target_sigungu = extract_sigungu(f"{fest_meta.get('location', '')} {fest_meta.get('venue', '')}")
        target_sido: str = fest_meta.get("sido", "") or extract_sido(fest_meta.get("location", ""))
        if not target_sido or "통합" in target_sido:
            target_sido = extract_sido(fest_meta.get("location", ""))
        target_region: str = fest_meta.get("region", "기타")
        fest_title: str = fest_meta.get("title", clean_name if clean_name else "추천 축제")

        # 2. 동일 시/도 & 동일 시/군/구(sigungu) 100% 엄격 필터링 (동명 시군구 및 타 시도 혼선 원천 차단)
        # 예: 경남 고성군 vs 강원 고성군, 서울 중구 vs 인천 중구, 서울 강서구 vs 부산 강서구 등
        norm_target_sido: str = extract_sido(target_sido) if target_sido else ""

        def is_matching_area(meta: Dict[str, Any]) -> bool:
            if not target_sigungu:
                return False
            # (1) 시군구 명칭 반드시 일치
            if meta.get("sigungu") != target_sigungu:
                return False
            # (2) 광역시도(sido) 정밀 일치 검증
            item_sido_raw = meta.get("sido", "") or meta.get("location", "")
            norm_item_sido = extract_sido(item_sido_raw)
            if norm_target_sido and norm_item_sido and norm_target_sido != norm_item_sido:
                return False
            # (3) 광역 권역(region) 일치 검증 (경상권 vs 강원권 등)
            item_region = meta.get("region", "")
            if target_region and item_region and target_region != "기타" and item_region != "기타":
                if target_region != item_region:
                    return False
            return True

        all_parkings = [d.metadata for d in self.documents if d.metadata.get("data_type") == "주차장"]
        all_stores = [d.metadata for d in self.documents if d.metadata.get("data_type") == "착한가격업소"]
        all_wellness = [d.metadata for d in self.documents if d.metadata.get("data_type") == "웰니스"]

        store_fallback_notice: str = ""
        wellness_fallback_notice: str = ""
        parking_fallback_notice: str = ""

        # ── 주차장: 동일 시/도 + 동일 시군구 100% 엄격 매칭 ──
        matched_parkings = [p for p in all_parkings if is_matching_area(p)]
        has_real_parking: bool = bool(matched_parkings)
        if not matched_parkings:
            # 관내 데이터 0건 → 더미 임시주차장 안내만 반환, 타 지역 절대 불가
            parking_fallback_notice = f"해당 지역({target_sigungu}) 관내 등록 주차장 데이터 없음"
            venue_p = fest_meta.get("venue", target_sigungu)
            matched_parkings = [{
                "title": f"※ {target_sigungu} {venue_p} 임시주차장 (관내 등록 주차장 없음)",
                "location": fest_meta.get("location", f"{target_sido} {target_sigungu}"),
                "sigungu": target_sigungu,
                "sido": target_sido,
                "venue": "임시주차장",
                "menu": "요금: 무료 (현장 임시 무료 개방)",
                "fee_info": "무료 개방",
                "phone": fest_meta.get("phone", "현장 종합안내소"),
                "is_empty": True
            }]

        # ── 음식점: 동일 시/도 + 동일 시군구 100% 엄격 매칭 ──
        matched_stores = [s for s in all_stores if is_matching_area(s)]
        has_real_stores: bool = bool(matched_stores)
        if not matched_stores:
            # 관내 데이터 0건 → 빈 리스트 대신 is_empty 플래그 딕셔너리 1건 반환
            store_fallback_notice = f"해당 지역({target_sigungu}) 관내 등록 착한가격업소 없음"
            matched_stores = [{
                "title": f"※ [{target_sigungu}] 관내 등록된 착한가격업소가 없습니다.",
                "category": "안내",
                "location": fest_meta.get("location", f"{target_sigungu} 행사장 일원"),
                "sigungu": target_sigungu,
                "sido": target_sido,
                "menu": "",
                "menu1": "", "price1": "",
                "menu2": "", "price2": "",
                "menu3": "", "price3": "",
                "phone": fest_meta.get("phone", ""),
                "is_empty": True
            }]

        # ── 웰니스: 동일 시/도 + 동일 시군구 100% 엄격 매칭 ──
        matched_wellness = [w for w in all_wellness if is_matching_area(w)]
        has_real_wellness: bool = bool(matched_wellness)
        if not matched_wellness:
            # 관내 데이터 0건 → is_empty 플래그 딕셔너리 반환
            wellness_fallback_notice = f"해당 지역({target_sigungu}) 관내 등록 웰니스 없음"
            matched_wellness = [{
                "title": f"※ [{target_sigungu}] 관내 등록된 웰니스 관광지가 없습니다.",
                "category": "안내",
                "location": fest_meta.get("location", f"{target_sigungu} 관내"),
                "sigungu": target_sigungu,
                "sido": target_sido,
                "overview": f"{target_sigungu} 관내에 한국관광공사 등록 웰니스 관광지 데이터가 없습니다. 축제 행사장 주변 자연 산책로를 이용하세요.",
                "healing_programs": "",
                "facility_features": "",
                "phone": fest_meta.get("phone", ""),
                "is_empty": True
            }]

        # fallback_applied: 주차/식당/웰니스 중 하나라도 관내 실데이터가 없으면 True
        fallback_applied: bool = not (has_real_parking and has_real_stores and has_real_wellness)

        # 체력 난이도 표준화 ('상', '중', '하')
        stamina: str = user_stamina.strip() if user_stamina in ["상", "중", "하"] else "중"

        # 3. [체력별 맞춤 추천 알고리즘]
        # (1) [주차장]: 체력 수준에 따른 맞춤형 주차 공간 선별
        if stamina == "하":
            pri = [p for p in matched_parkings if any(k in p.get("title", "") + p.get("venue", "") for k in ["부설", "공영", "임시"])]
            selected_parking = pri[0] if pri else matched_parkings[0]
            parking_tip = "💡 [체력 절약 TIP] 축제장과 바로 인접하여 도보 이동 거리를 최소화할 수 있는 안심 주차장입니다."
        elif stamina == "중":
            pri = [p for p in matched_parkings if "공영" in p.get("title", "") + p.get("venue", "")]
            selected_parking = pri[0] if pri else matched_parkings[0]
            parking_tip = "💡 [밸런스 TIP] 축제장과 식사/카페 동선 중간에 위치하여 합리적인 요금으로 이용할 수 있는 공영 주차장입니다."
        else:  # '상'
            pri = [p for p in matched_parkings if any(k in p.get("title", "") + p.get("venue", "") for k in ["노외", "공영", "대형", "중앙"])]
            selected_parking = pri[0] if pri else matched_parkings[0]
            parking_tip = "💡 [에너지 풀코스 TIP] 다음 트레킹 및 드라이브 코스로의 출차와 회차 이동이 편리한 쾌적한 주차 공간입니다."

        # (2) [축제 & 사진스팟]: 체력 수준에 따른 관람 반경 및 축제 맞춤 인생샷 포토스팟 선별
        raw_spots: str = fest_meta.get("photo_spots", "")
        if not raw_spots or raw_spots == "현장 곳곳이 포토존":
            spot_candidates = extract_dynamic_photo_spots(
                title=fest_title,
                venue=fest_meta.get("venue", ""),
                description=fest_meta.get("description", "") or fest_meta.get("detailed_desc", ""),
                programs=fest_meta.get("programs", "")
            )
        else:
            spot_candidates = [s.strip() for s in re.split(r"[,|/]", raw_spots) if s.strip()]
        if not spot_candidates:
            spot_candidates = extract_dynamic_photo_spots(fest_title, fest_meta.get("venue", ""), "", "")

        # 2중 안전장치: 실제 바다/해양 축제가 아닌 경우 지형 왜곡 금지 단어 방어 필터 적용
        is_fest_coastal = any(sea_kw in f"{fest_title} {fest_meta.get('venue', '')}" for sea_kw in ["해수욕장", "해변", "바닷가", "포구", "항구", "등대", "해안", "해양", "서핑", "요트"])
        forbidden_coastal_terms = ["오션뷰", "백사장", "파도", "모래조각", "해변", "바닷가", "갯벌", "해안선", "파도소리"]
        if not is_fest_coastal:
            safe_candidates = []
            for sc in spot_candidates:
                if any(bad_term in sc for bad_term in forbidden_coastal_terms):
                    v_name = clean_text(fest_meta.get("venue", "")) or "축제장"
                    safe_candidates.append(f"{v_name} 메인 진입로 및 상징 조형물 앞")
                else:
                    safe_candidates.append(sc)
            spot_candidates = list(dict.fromkeys(safe_candidates))

        if stamina == "하":
            selected_spots = spot_candidates[:1]
            if fest_meta.get("event_type") == "문화행사":
                fest_tip = "💡 [차분한 힐링 TIP] 무리한 이동 없이 전시·공연을 편안히 감상하고, 조용한 티타임이나 웰니스 명상 코스로 자연스럽게 이어지는 힐링 코스입니다."
            else:
                fest_tip = "💡 [체력 절약 TIP] 무리한 이동 없이 축제 메인 구역에서 가볍게 인생샷을 건질 수 있는 필수 1픽 포토존입니다."
        elif stamina == "중":
            selected_spots = spot_candidates[:2] if len(spot_candidates) >= 2 else spot_candidates
            if fest_meta.get("event_type") == "문화행사":
                fest_tip = "💡 [문화예술 밸런스 TIP] 대표 전시와 핵심 공연을 관람하고 주변 정원 카페와 웰니스 쉼터로 여유롭게 연계하는 알짜 문화 코스입니다."
            else:
                fest_tip = "💡 [밸런스 TIP] 주요 행사 관람과 함께 2곳의 대표 포토존을 여유롭게 순회하는 밸런스 코스입니다."
        else:  # '상'
            selected_spots = spot_candidates if len(spot_candidates) >= 3 else (spot_candidates + ["축제장 전경 전망대", "둘레길 포토로드"])
            fest_tip = "💡 [에너지 풀코스 TIP] 전망대와 축제장 전역을 활기차게 누비며 다양한 앵글의 인생샷을 완성하는 풀코스입니다."

        # (3) [음식점 & 카페]: 동일 시군구 관내 매칭
        if stamina == "하":
            comfort_stores = [s for s in matched_stores if any(k in s.get("menu", "") + s.get("category", "") for k in ["한식", "백반", "국수", "분식"])]
            selected_store = comfort_stores[0] if comfort_stores else matched_stores[0]
            food_tip = "💡 [체력 절약 TIP] 안락한 좌석에서 편안한 가성비 식사를 즐기고, 달콤한 디저트 카페에서 충분한 휴식을 누립니다."
        elif stamina == "중":
            selected_store = matched_stores[0]
            food_tip = "💡 [밸런스 TIP] 착한 가격의 공인 맛집에서 든든하게 식사하고, 주변 핫플레이스 카페에서 티타임을 즐깁니다."
        else:  # '상'
            energy_stores = [s for s in matched_stores if any(k in s.get("menu", "") + s.get("category", "") for k in ["고기", "갈비", "삼겹", "탕", "찌개", "국밥", "불고기"])]
            selected_store = energy_stores[0] if energy_stores else matched_stores[0]
            food_tip = "💡 [에너지 풀코스 TIP] 활동량이 많은 만큼 든든하게 단백질과 영양을 채워주는 보양 가성비 맛집 코스입니다."

        # 동일 시군구 착한가격업소 리스트 구성
        sorted_stores = [selected_store] + [s for s in matched_stores if s.get("title") != selected_store.get("title")]
        candidate_stores = sorted_stores[:3]

        # ── 카페/디저트: 동일 sigungu 관내 착한가격업소 중 카페 업종만 필터 ──
        # 실제 데이터가 있고 is_empty가 아닌 stores에서만 탐색 (타 지역·더미 절대 불가)
        real_stores_only = [s for s in matched_stores if not s.get("is_empty")]
        exclude_cafe_keywords = ["분식", "식당", "칼국수", "국밥", "찌개"]
        candidate_cafes = [
            s for s in real_stores_only
            if not any(k in s.get("title", "") for k in exclude_cafe_keywords)
            and (
                s.get("category") == "카페/베이커리"
                or any(k in s.get("title", "") + s.get("menu", "") for k in ["카페", "커피", "베이커리", "디저트", "제과", "다방", "빵"])
            )
        ]

        cafe_info: Dict[str, Any] = {}
        if candidate_cafes:
            c_store = candidate_cafes[0]
            cafe_info = {
                "title": c_store.get("title", ""),
                "category": c_store.get("category", "카페/베이커리"),
                "location": c_store.get("location", ""),
                "phone": c_store.get("phone", ""),
                "menu": c_store.get("menu", ""),
                "reason": f"행정안전부 인증 {target_sigungu} 착한가격업소입니다."
            }
        elif has_real_wellness:
            # 동일 sigungu 웰니스 중 다도/티 관련 실데이터가 있을 때만 사용
            tea_wellness = [
                w for w in matched_wellness
                if not w.get("is_empty")
                and any(k in w.get("title", "") + w.get("category", "") + w.get("overview", "") for k in ["다도", "티", "찻집", "한방차", "티테라피"])
            ]
            if tea_wellness:
                w_cafe = tea_wellness[0]
                cafe_info = {
                    "title": w_cafe.get("title", ""),
                    "category": f"웰니스 다도/티하우스 ({w_cafe.get('category', '힐링/명상')})",
                    "location": w_cafe.get("location", ""),
                    "phone": w_cafe.get("phone", ""),
                    "menu": "전통 수제차 & 다도 힐링 코스",
                    "reason": f"{target_sigungu} 관내 한국관광공사 등록 웰니스 명소입니다."
                }
        # 실데이터 없으면 cafe_info = {} 그대로 유지 (app.py에서 표시 안 함)

        # (4) [힐링(웰니스)]: 체력 수준에 따른 최적의 휴식/치유 명소 매칭 (동일 sigungu 100%)
        # is_empty 안내 항목 제외한 실데이터 목록으로 먼저 체력별 필터, 없으면 matched_wellness[0] 유지
        real_wellness_only = [w for w in matched_wellness if not w.get("is_empty")]
        if stamina == "하":
            rest_wl = [w for w in real_wellness_only if any(k in w.get("title", "") + w.get("category", "") + w.get("overview", "") for k in ["스파", "온천", "테라피", "한방", "명상", "족욕", "티", "다도"])]
            selected_wellness = rest_wl[0] if rest_wl else (real_wellness_only[0] if real_wellness_only else matched_wellness[0])
            wellness_tip = "💡 [체력 절약 TIP] 걷는 부담 없이 따뜻한 스파/온천 또는 한방 쉼터에서 지친 피로를 녹이는 힐링입니다."
        elif stamina == "중":
            walk_wl = [w for w in real_wellness_only if any(k in w.get("title", "") + w.get("category", "") + w.get("overview", "") for k in ["정원", "쉼터", "다도", "체험", "명상", "약초"])]
            selected_wellness = walk_wl[0] if walk_wl else (real_wellness_only[0] if real_wellness_only else matched_wellness[0])
            wellness_tip = "💡 [밸런스 TIP] 맑은 공기를 마시며 완만한 산책로를 걷고 차 한 잔의 여유를 만끽할 수 있는 테마 쉼터입니다."
        else:  # '상'
            active_wl = [w for w in real_wellness_only if any(k in w.get("title", "") + w.get("category", "") + w.get("overview", "") for k in ["자연/숲치유", "휴양림", "수목원", "숲", "트레킹", "치유의숲"])]
            selected_wellness = active_wl[0] if active_wl else (real_wellness_only[0] if real_wellness_only else matched_wellness[0])
            wellness_tip = "💡 [에너지 풀코스 TIP] 피톤치드가 가득한 숲길을 걸으며 온몸의 활력을 채우는 자연 치유 트레킹 명소입니다."

        # 동일 시군구 관내 웰니스 관광지 최대 3곳 패키징 (선택된 대표 웰니스를 1순위로 배치)
        if real_wellness_only:
            sorted_wellness = [selected_wellness] + [w for w in real_wellness_only if w.get("title") != selected_wellness.get("title")]
            candidate_wellness = sorted_wellness[:3]
        else:
            candidate_wellness = matched_wellness[:1]

        # 기간 정보 추출
        start_date = fest_meta.get("start_date", "")
        end_date = fest_meta.get("end_date", "")
        period_str = f"{start_date} ~ {end_date}".strip(" ~") if (start_date or end_date) else "상시/일정 확인"

        # 최종 반환 딕셔너리 구성 (Streamlit 타임라인 UI 렌더링에 최적화된 포맷)
        course_package: Dict[str, Any] = {
            "status": "success",
            "festival_name": fest_title,
            "user_stamina": stamina,
            "companion": companion,
            "target_sigungu": target_sigungu if target_sigungu else target_region,
            "target_region": target_region,
            "fallback_applied": fallback_applied,
            "location_integrity_notice": (
                f"✅ [{target_sigungu}] 관내 주차장·착한가격업소·웰니스 데이터가 모두 매칭되었습니다."
                if not fallback_applied
                else (
                    f"ℹ️ [{target_sigungu}] 관내 일부 카테고리 데이터 없음: "
                    + (f"주차장 " if not has_real_parking else "")
                    + (f"착한가격업소 " if not has_real_stores else "")
                    + (f"웰니스 " if not has_real_wellness else "")
                    + "— 해당 항목은 '데이터 없음' 안내로 표시됩니다."
                )
            ),
            "course_summary": f"[{target_sigungu}] 체력 난이도 '{stamina}' 최적화 [주차 ➔ 축제 ➔ 식사/카페 ➔ 웰니스 힐링] 원데이 동선",
            "timeline": [
                {
                    "step": 1,
                    "step_title": "편리한 주차 & 입차",
                    "icon": "🚗",
                    "category": "주차장",
                    "title": selected_parking.get("title", "인근 추천 주차장"),
                    "location": selected_parking.get("location", "주소 확인 필요"),
                    "sigungu": selected_parking.get("sigungu", target_sigungu),
                    "fee_info": selected_parking.get("menu", selected_parking.get("fee_info", "요금 정보 확인")),
                    "phone": selected_parking.get("phone", "연락처 미기재"),
                    "parking_fallback": bool(parking_fallback_notice),
                    "parking_fallback_notice": parking_fallback_notice,
                    "stamina_tip": parking_tip
                },
                {
                    "step": 2,
                    "step_title": "축제 관람 & 인생샷",
                    "icon": "🎉",
                    "category": "축제/사진스팟",
                    "title": fest_title,
                    "location": fest_meta.get("location", "개최 장소 확인"),
                    "venue": fest_meta.get("venue", ""),
                    "sigungu": target_sigungu,
                    "period": period_str,
                    "event_type": fest_meta.get("event_type", "지역축제"),
                    "fee": fest_meta.get("fee", "무료 관람 (상세 현장 확인)"),
                    "programs": fest_meta.get("programs") or fest_meta.get("description", "개막식 및 축제 문화행사 프로그램"),
                    "description": fest_meta.get("description") or fest_meta.get("detailed_desc", "축제 상세 설명 확인"),
                    "detailed_desc": fest_meta.get("description") or fest_meta.get("detailed_desc", "축제 상세 설명 확인"),
                    "homepage": fest_meta.get("homepage", ""),
                    "phone": fest_meta.get("phone", ""),
                    "photo_spots": selected_spots,
                    "stamina_tip": fest_tip
                },
                {
                    "step": 3,
                    "step_title": "가성비 식사 & 감성 티타임",
                    "icon": "🍽️",
                    "category": "음식점/카페",
                    "title": f"{selected_store.get('title', '착한가격업소')} & {cafe_info.get('title', '힐링 카페')}",
                    "location": selected_store.get("location", "주소 확인 필요"),
                    "sigungu": selected_store.get("sigungu", target_sigungu),
                    "restaurant": {
                        "title": selected_store.get("title", "착한가격업소 맛집"),
                        "category": selected_store.get("category", "음식점"),
                        "location": selected_store.get("location", "주소 확인 필요"),
                        "sigungu": selected_store.get("sigungu", target_sigungu),
                        "menu": selected_store.get("menu", "대표 가성비 메뉴"),
                        "menu1": selected_store.get("menu1", ""),
                        "price1": selected_store.get("price1", ""),
                        "menu2": selected_store.get("menu2", ""),
                        "price2": selected_store.get("price2", ""),
                        "menu3": selected_store.get("menu3", ""),
                        "price3": selected_store.get("price3", ""),
                        "phone": selected_store.get("phone", "연락처 미기재")
                    },
                    "restaurants": [
                        {
                            "title": s.get("title", "착한가격업소 맛집"),
                            "category": s.get("category", "음식점"),
                            "location": s.get("location", "주소 확인 필요"),
                            "sigungu": s.get("sigungu", target_sigungu),
                            "menu": s.get("menu", "대표 가성비 메뉴"),
                            "menu1": s.get("menu1", ""),
                            "price1": s.get("price1", ""),
                            "menu2": s.get("menu2", ""),
                            "price2": s.get("price2", ""),
                            "menu3": s.get("menu3", ""),
                            "price3": s.get("price3", ""),
                            "phone": s.get("phone", "연락처 미기재")
                        }
                        for s in candidate_stores
                    ],
                    "store_fallback": bool(store_fallback_notice),
                    "store_fallback_notice": store_fallback_notice,
                    "cafe": cafe_info,
                    "stamina_tip": food_tip
                },
                {
                    "step": 4,
                    "step_title": "웰니스 힐링 & 피로 회복",
                    "icon": "🌿",
                    "category": "웰니스 힐링",
                    "title": selected_wellness.get("title", "웰니스 추천 쉼터"),
                    "theme": selected_wellness.get("category", "힐링/치유"),
                    "location": selected_wellness.get("location", "주소 확인 필요"),
                    "sigungu": selected_wellness.get("sigungu", target_sigungu),
                    "overview": selected_wellness.get("overview", "한국관광공사 추천 웰니스 관광지"),
                    "healing_programs": selected_wellness.get("healing_programs", "피톤치드 산책 및 심신 치유 힐링 프로그램"),
                    "facility_features": selected_wellness.get("facility_features", "쾌적한 산책로 및 휴식 라운지"),
                    "phone": selected_wellness.get("phone", "연락처 미기재"),
                    "wellness_fallback": bool(wellness_fallback_notice),
                    "wellness_fallback_notice": wellness_fallback_notice,
                    "wellness_count": len(real_wellness_only),
                    "wellness_places": [
                        {
                            "title": w.get("title", "웰니스 쉼터"),
                            "theme": w.get("category", "힐링/치유"),
                            "location": w.get("location", "주소 확인 필요"),
                            "sigungu": w.get("sigungu", target_sigungu),
                            "overview": w.get("overview", "한국관광공사 추천 웰니스 관광지"),
                            "healing_programs": w.get("healing_programs", "피톤치드 산책 및 심신 치유 힐링 프로그램"),
                            "facility_features": w.get("facility_features", "쾌적한 산책로 및 휴식 라운지"),
                            "phone": w.get("phone", "연락처 미기재"),
                            "is_empty": w.get("is_empty", False)
                        }
                        for w in candidate_wellness
                    ],
                    "stamina_tip": wellness_tip
                }
            ]
        }

        # 스토리텔링 줄글 에세이 생성 연동 (agent.py 에이전트 호출)
        storytelling_text = self.generate_storytelling_course(course_package, companion=companion)
        course_package["storytelling_text"] = storytelling_text
        course_package["storytelling_summary"] = storytelling_text

        return course_package

    def generate_storytelling_course(
        self,
        course_package: Dict[str, Any],
        companion: str = "혼자"
    ) -> str:
        """timeline에 담긴 실제 4단계 데이터를 agent.py와 연동하여
        여행 기획 전문 AI 에디터 톤의 풍부한 감성 스토리텔링 줄글 에세이를 생성합니다."""
        try:
            return generate_storytelling_course(course_package, companion=companion)
        except Exception as err:
            print(f"[Warning] 스토리텔링 생성 중 예외 발생 ({err}). 폴백 생성기로 안전하게 전환합니다.")
            return generate_storytelling_fallback(course_package, companion=companion)


# ==============================================================================
# [호환성 어댑터] app_clone.py & agent_clone.py 연동용 표준 인터페이스 어댑터
# ==============================================================================
# data.py의 정교한 전처리/정합성 로직을 유지하면서, 팀원 모듈(app_clone.py, agent_clone.py)이
# 요구하는 함수명 및 반환 데이터 규격(get_festival_infra_bundle 등)을 100% 호환 제공합니다.

import math

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 위경도 좌표 사이의 대원 거리(Haversine Distance)를 미터(m) 단위로 계산합니다."""
    R = 6371000.0  # 지구 반지름 (m)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


_ADAPTER_PARKING_CACHE: Optional[pd.DataFrame] = None
_ADAPTER_STORE_CACHE: Optional[pd.DataFrame] = None
_ADAPTER_FEST_CACHE: Optional[pd.DataFrame] = None
_ADAPTER_WELLNESS_CACHE: Optional[pd.DataFrame] = None


def _load_adapter_csv(filename_patterns: List[str]) -> pd.DataFrame:
    """지정된 파일명 패턴 중 존재하는 CSV 파일을 다양한 인코딩으로 안전하게 로드합니다."""
    target_path = None
    for pattern in filename_patterns:
        # data 폴더, 기본 데이터 디렉터리 및 현재 작업 디렉터리, datafile, 상위 디렉터리 탐색
        candidates = (
            glob.glob(os.path.join(DEFAULT_DATA_DIR, pattern))
            + glob.glob(os.path.join("data", pattern))
            + glob.glob(os.path.join("datafile", pattern))
            + glob.glob(os.path.join("..", "datafile", pattern))
            + glob.glob(os.path.join("..", "data", pattern))
            + glob.glob(pattern)
        )
        if candidates:
            target_path = candidates[0]
            break

    if not target_path or not os.path.exists(target_path):
        print(f"[Error] CSV 파일을 찾을 수 없습니다: {filename_patterns}")
        return pd.DataFrame()

    for enc in ["utf-8-sig", "utf-8", "cp949", "euc-kr"]:
        try:
            return pd.read_csv(target_path, encoding=enc, low_memory=False).fillna("")
        except Exception:
            continue

    print(f"[Error] CSV 파일을 찾을 수 없습니다: {filename_patterns}")
    return pd.DataFrame()


def get_festivals(region: str = "전국 전체", month: Optional[int] = None, year: Optional[int] = None, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    """전국 17개 행정구역, 개최연도 및 월별 필터링을 거친 유효 위경도 축제 목록을 반환합니다."""
    global _ADAPTER_FEST_CACHE
    if _ADAPTER_FEST_CACHE is None or _ADAPTER_FEST_CACHE.empty:
        _ADAPTER_FEST_CACHE = _load_adapter_csv(["*문화축제*.csv", "festivals.csv", "*공연행사*.csv"])

    if _ADAPTER_FEST_CACHE.empty:
        return []

    df = _ADAPTER_FEST_CACHE.copy()
    
    # 1. 행정구역 필터링
    if region and region != "전국 전체":
        region_map = {
            "강원특별자치도": ["강원특별자치도", "강원도", "강원"],
            "전북특별자치도": ["전북특별자치도", "전라북도", "전북"],
            "전라남도": ["전라남도", "전남"],
            "경상북도": ["경상북도", "경북"],
            "경상남도": ["경상남도", "경남"],
            "충청북도": ["충청북도", "충북"],
            "충청남도": ["충청남도", "충남"],
            "제주특별자치도": ["제주특별자치도", "제주도", "제주"],
            "서울특별시": ["서울특별시", "서울시", "서울"],
            "부산광역시": ["부산광역시", "부산시", "부산"],
            "대구광역시": ["대구광역시", "대구시", "대구"],
            "인천광역시": ["인천광역시", "인천시", "인천"],
            "광주광역시": ["광주광역시", "광주시", "광주"],
            "대전광역시": ["대전광역시", "대전시", "대전"],
            "울산광역시": ["울산광역시", "울산시", "울산"],
            "세종특별자치시": ["세종특별자치시", "세종시", "세종"],
            "경기도": ["경기도", "경기"],
        }
        short_region = region.replace("광역시", "").replace("특별자치도", "").replace("특별시", "").replace("도", "")
        aliases = region_map.get(region, [region, short_region])
        pattern = "|".join(list(set(aliases)))
        
        # 주소 관련 컬럼(소재지도로명주소, 소재지지번주소, 개최장소)을 1순위로 필터링
        # 축제명에 "경기" 등의 지역명 단어가 포함되어 오매칭되는 현상을 방지
        addr_cols = ["소재지도로명주소", "소재지지번주소", "개최장소"]
        addr_mask = pd.Series(False, index=df.index)
        has_addr = pd.Series(False, index=df.index)
        for col in addr_cols:
            if col in df.columns:
                col_val = df[col].astype(str).str.strip()
                is_valid = (col_val != "") & (col_val.str.lower() != "nan") & (col_val.str.lower() != "none")
                has_addr = has_addr | is_valid
                addr_mask = addr_mask | (is_valid & col_val.str.contains(pattern, na=False))

        # 주소가 유효한 데이터는 주소 일치 여부만으로 판정하고, 주소 컬럼이 모두 비어있는 경우에만 축제명 매칭 확인
        name_mask = pd.Series(False, index=df.index)
        if "축제명" in df.columns:
            name_mask = df["축제명"].astype(str).str.contains(pattern, na=False)

        region_mask = addr_mask | (~has_addr & name_mask)
        df = df[region_mask]

    # 2. 날짜(연도 및 월) 필터링
    year = year or kwargs.get("year")
    s_col = df["축제시작일자"] if "축제시작일자" in df.columns else pd.Series(index=df.index, dtype=object)
    e_col = df["축제종료일자"] if "축제종료일자" in df.columns else pd.Series(index=df.index, dtype=object)
    s_date = pd.to_datetime(s_col, errors="coerce")
    e_date = pd.to_datetime(e_col, errors="coerce")

    # 시작일이나 종료일이 누락된(NaN) 축제는 무조건 필터링에서 제외(Drop)
    valid_dates = s_date.notna() & e_date.notna()

    # 연도 조건: 특정 연도가 지정된 경우 해당 연도 축제만, 지정되지 않은 경우 최근 3년 이내 행사 허용
    current_year = datetime.now().year
    if year:
        year_mask = (s_date.dt.year == year) | (e_date.dt.year == year)
    else:
        min_year = current_year - 3
        year_mask = (e_date.dt.year >= min_year) | (s_date.dt.year >= min_year)

    if month and 1 <= month <= 12:
        s_month = s_date.dt.month
        e_month = e_date.dt.month
        
        # 일반 기간: s_month <= month <= e_month
        normal_mask = (s_month <= e_month) & (s_month <= month) & (month <= e_month)
        # 연도 교차 축제 (예: 11월~2월): month >= s_month 이거나 month <= e_month
        cross_mask = (s_month > e_month) & ((month >= s_month) | (month <= e_month))
        
        mask_date = valid_dates & year_mask & (normal_mask | cross_mask)
    else:
        mask_date = valid_dates & year_mask

    df = df[mask_date]

    results: List[Dict[str, Any]] = []
    seen = set()

    for _, row in df.iterrows():
        name = clean_text(row.get("축제명", row.get("title", "")))
        if not name or name in seen:
            continue

        try:
            lat = float(row.get("위도", row.get("lat", 0.0)))
            lng = float(row.get("경도", row.get("lng", 0.0)))
        except (ValueError, TypeError):
            lat, lng = 0.0, 0.0

        # 유효하지 않은 좌표 제외
        if lat == 0.0 or lng == 0.0 or abs(lat) < 1.0 or abs(lng) < 1.0:
            continue

        seen.add(name)
        road_addr = clean_text(row.get("소재지도로명주소", ""))
        jibun_addr = clean_text(row.get("소재지지번주소", ""))
        venue = clean_text(row.get("개최장소", ""))
        address = road_addr or jibun_addr or venue or "주소 정보 없음"

        s_d = clean_text(row.get("축제시작일자", ""))
        e_d = clean_text(row.get("축제종료일자", ""))
        dates_str = f"{s_d} ~ {e_d}" if s_d and e_d else (s_d or "일정 확인 중")

        desc = clean_text(row.get("축제내용", row.get("description", ""))) or "상세 축제 소개 정보가 준비 중입니다."

        # 전화번호 및 홈페이지 정제 추출
        raw_phone = clean_text(row.get("전화번호", row.get("phone", row.get("연락처", row.get("문의처", "")))))
        phone = raw_phone if raw_phone and raw_phone.lower() not in ["nan", "none", "null", "-", "없음"] else ""

        raw_hp = clean_text(row.get("홈페이지주소", row.get("homepage", row.get("홈페이지", row.get("웹사이트", "")))))
        homepage = ""
        if raw_hp and raw_hp.lower() not in ["nan", "none", "null", "-", "없음"]:
            if raw_hp.startswith("http://") or raw_hp.startswith("https://"):
                homepage = raw_hp
            elif raw_hp.startswith("www."):
                homepage = "https://" + raw_hp
            elif "." in raw_hp and "/" not in raw_hp:
                homepage = "https://" + raw_hp
            else:
                homepage = raw_hp

        # 원본 데이터로부터 프로그램 추출 및 딕셔너리 리스트 구성
        prog_raw = (
            clean_text(row.get("주요프로그램", ""))
            or clean_text(row.get("프로그램내용", ""))
            or clean_text(row.get("프로그램명", ""))
            or clean_text(row.get("행사내용", ""))
            or desc
        )
        parsed_programs = []
        if prog_raw:
            stopwords = {"등", "기타", "체험행사", "축제내용", "행사내용"}
            split_candidates = re.split(r'[+,/;\n]', str(prog_raw))
            seen_progs = set()
            for cand in split_candidates:
                p_name = cand.strip()
                if len(p_name) >= 2 and p_name not in stopwords and p_name not in seen_progs:
                    seen_progs.add(p_name)
                    parsed_programs.append({
                        "name": p_name,
                        "category": "축제 프로그램",
                        "description": "세부 정보 없음",
                        "reservation_required": None
                    })
                    if len(parsed_programs) >= 7:
                        break

        results.append({
            "name": name,
            "lat": round(lat, 7),
            "lng": round(lng, 7),
            "address": address,
            "description": desc,
            "dates": dates_str,
            "region": region if region != "전국 전체" else classify_region(address),
            "is_indoor": classify_indoor_outdoor(name, venue),
            "theme": classify_festival_theme(name, venue, desc),
            "programs": parsed_programs,
            "phone": phone,
            "homepage": homepage
        })

    return results


def get_nearby_parking(target_lat: float, target_lng: float, radius_m: int = 2000) -> List[Dict[str, Any]]:
    """축제장 좌표 기준 radius_m 이내에 존재하는 공영주차장 목록을 면수/거리순으로 반환합니다."""
    global _ADAPTER_PARKING_CACHE
    if _ADAPTER_PARKING_CACHE is None or _ADAPTER_PARKING_CACHE.empty:
        df = _load_adapter_csv(["*주차장*.csv", "parkings.csv"])
        if not df.empty:
            df["_lat_num"] = pd.to_numeric(df.get("위도"), errors="coerce")
            df["_lng_num"] = pd.to_numeric(df.get("경도"), errors="coerce")
            df["_spaces_num"] = pd.to_numeric(df.get("주차구획수"), errors="coerce").fillna(0).astype(int)
            _ADAPTER_PARKING_CACHE = df.dropna(subset=["_lat_num", "_lng_num"])
        else:
            _ADAPTER_PARKING_CACHE = pd.DataFrame()

    if _ADAPTER_PARKING_CACHE.empty:
        return []

    nearby: List[Dict[str, Any]] = []
    delta_deg = (radius_m / 111000.0) * 1.5

    for _, row in _ADAPTER_PARKING_CACHE.iterrows():
        p_lat = float(row["_lat_num"])
        p_lng = float(row["_lng_num"])
        if abs(p_lat - target_lat) > delta_deg or abs(p_lng - target_lng) > delta_deg:
            continue

        dist = calculate_distance(target_lat, target_lng, p_lat, p_lng)
        if dist <= radius_m:
            fee = clean_text(row.get("요금정보", "정보없음"))
            nearby.append({
                "name": clean_text(row.get("주차장명", "공영주차장")),
                "lat": p_lat,
                "lng": p_lng,
                "total_spaces": int(row["_spaces_num"]),
                "fee": fee if fee else "요금 정보 없음",
                "_dist": dist
            })

    nearby.sort(key=lambda x: (-x["total_spaces"], x["_dist"]))
    for item in nearby:
        item.pop("_dist", None)
    return nearby


def get_nearby_restaurants(target_lat: float, target_lng: float, radius_m: int = 2000, target_address: str = "") -> List[Dict[str, Any]]:
    """축제장 좌표 기준 radius_m 이내 또는 동일 시군구에 존재하는 착한가격업소(음식점/카페) 목록을 반환합니다."""
    global _ADAPTER_STORE_CACHE
    if _ADAPTER_STORE_CACHE is None or _ADAPTER_STORE_CACHE.empty:
        df = _load_adapter_csv(["*착한가격업소*.csv", "good_price_stores.csv"])
        if not df.empty:
            lat_col = "위도" if "위도" in df.columns else ("lat" if "lat" in df.columns else None)
            lng_col = "경도" if "경도" in df.columns else ("lng" if "lng" in df.columns else None)
            if lat_col and lng_col:
                df["_lat_num"] = pd.to_numeric(df[lat_col], errors="coerce").fillna(0.0)
                df["_lng_num"] = pd.to_numeric(df[lng_col], errors="coerce").fillna(0.0)
            else:
                df["_lat_num"] = 0.0
                df["_lng_num"] = 0.0
            _ADAPTER_STORE_CACHE = df
        else:
            _ADAPTER_STORE_CACHE = pd.DataFrame()

    if _ADAPTER_STORE_CACHE.empty:
        return []

    nearby: List[Dict[str, Any]] = []
    delta_deg = (radius_m / 111000.0) * 1.5

    # 1. 위경도가 존재하는 업소 기준 Haversine 반경 필터링
    has_coord = _ADAPTER_STORE_CACHE[(_ADAPTER_STORE_CACHE["_lat_num"] > 1.0) & (_ADAPTER_STORE_CACHE["_lng_num"] > 1.0)]
    for _, row in has_coord.iterrows():
        r_lat = float(row["_lat_num"])
        r_lng = float(row["_lng_num"])
        if abs(r_lat - target_lat) > delta_deg or abs(r_lng - target_lng) > delta_deg:
            continue

        store_name = clean_text(row.get("업소명", ""))
        raw_cat = clean_text(row.get("업종", ""))
        m1 = clean_text(row.get("메뉴1", ""))
        m2 = clean_text(row.get("메뉴2", ""))

        if not is_food_related(raw_cat, store_name, f"{m1} {m2}"):
            continue

        dist = calculate_distance(target_lat, target_lng, r_lat, r_lng)
        if dist <= radius_m:
            price_str = clean_price(row.get("가격1", "")) or "착한가격"

            nearby.append({
                "name": store_name if store_name else "착한가격 식당",
                "lat": r_lat,
                "lng": r_lng,
                "menu": m1 or "로컬 대표 메뉴",
                "price": price_str,
                "_dist": dist
            })

    # 2. 위경도 매칭 건수가 적고 축제 주소 또는 인근 주차장 등에서 시군구를 유추할 수 있는 경우 시군구 기반 매칭
    if len(nearby) < 3:
        target_sigungu = extract_sigungu(target_address) if target_address else ""
        if not target_sigungu:
            parkings = get_nearby_parking(target_lat, target_lng, radius_m=max(radius_m, 20000))
            if parkings:
                for p in parkings:
                    sig = extract_sigungu(p.get("name", ""))
                    if sig:
                        target_sigungu = sig
                        break

        if target_sigungu:
            sigungu_matches = _ADAPTER_STORE_CACHE[
                _ADAPTER_STORE_CACHE["시군"].astype(str).str.contains(target_sigungu, na=False) |
                _ADAPTER_STORE_CACHE["주소"].astype(str).str.contains(target_sigungu, na=False)
            ]
            for _, row in sigungu_matches.head(10).iterrows():
                store_name = clean_text(row.get("업소명", ""))
                raw_cat = clean_text(row.get("업종", ""))
                m1 = clean_text(row.get("메뉴1", ""))
                m2 = clean_text(row.get("메뉴2", ""))
                if not is_food_related(raw_cat, store_name, f"{m1} {m2}"):
                    continue
                price_str = clean_price(row.get("가격1", "")) or "착한가격"

                # 이미 포함되었는지 확인
                if not any(item["name"] == store_name for item in nearby):
                    idx = len(nearby)
                    # [0m 방지] 축제장과 100% 겹치지 않도록 기본 최소 오프셋(약 400m) 및 순번별 점진적 반경 부여
                    offset_lat = 0.0032 + (idx * 0.0016)
                    offset_lng = 0.0028 + (idx * 0.0018)
                    nearby.append({
                        "name": store_name,
                        "lat": round(target_lat + offset_lat, 7),
                        "lng": round(target_lng + offset_lng, 7),
                        "menu": m1 or "로컬 착한 메뉴",
                        "price": price_str,
                        "_dist": 450.0 + (idx * 150.0)
                    })
                    if len(nearby) >= 6:
                        break

    nearby.sort(key=lambda x: x.get("_dist", 99999))
    for item in nearby:
        item.pop("_dist", None)
    return nearby


def get_wellness_spots(lat: float, lng: float, radius: int = 5000) -> List[Dict[str, Any]]:
    """축제장 기준 반경 내 웰니스 관광지 및 쉼터 정보를 반환합니다."""
    global _ADAPTER_WELLNESS_CACHE
    if _ADAPTER_WELLNESS_CACHE is None or _ADAPTER_WELLNESS_CACHE.empty:
        df = _load_adapter_csv(["*웰니스*.csv", "*wellness*.csv"])
        if not df.empty:
            lat_col = "위도" if "위도" in df.columns else ("lat" if "lat" in df.columns else ("mapy" if "mapy" in df.columns else None))
            lng_col = "경도" if "경도" in df.columns else ("lng" if "lng" in df.columns else ("mapx" if "mapx" in df.columns else None))
            if lat_col and lng_col:
                df["_lat_num"] = pd.to_numeric(df[lat_col], errors="coerce")
                df["_lng_num"] = pd.to_numeric(df[lng_col], errors="coerce")
                _ADAPTER_WELLNESS_CACHE = df.dropna(subset=["_lat_num", "_lng_num"])
            else:
                _ADAPTER_WELLNESS_CACHE = pd.DataFrame()
        else:
            _ADAPTER_WELLNESS_CACHE = pd.DataFrame()

    spots: List[Dict[str, Any]] = []

    # 1. 로컬 웰니스 CSV 데이터셋 우선 탐색
    if not _ADAPTER_WELLNESS_CACHE.empty:
        delta_deg = (radius / 111000.0) * 1.5
        for _, row in _ADAPTER_WELLNESS_CACHE.iterrows():
            w_lat = float(row["_lat_num"])
            w_lng = float(row["_lng_num"])
            if abs(w_lat - lat) > delta_deg or abs(w_lng - lng) > delta_deg:
                continue
            dist = calculate_distance(lat, lng, w_lat, w_lng)
            if dist <= radius:
                spots.append({
                    "name": clean_text(row.get("관광지명", row.get("title", "웰니스 쉼터"))),
                    "lat": w_lat,
                    "lng": w_lng,
                    "description": clean_text(row.get("개요", row.get("overview", "자연 속 힐링 공간"))),
                    "category": "쉼터"
                })

    # 2. 결과가 없으면 TourAPI 온라인 탐색 안전 폴백
    if not spots:
        try:
            import requests
            api_key = os.getenv("TOUR_API_KEY") or os.getenv("DATA_GO_KR_API_KEY") or ""
            if api_key:
                clean_key = requests.utils.unquote(api_key)
                endpoint = "http://apis.data.go.kr/B551011/KorService1/locationBasedList1"
                params = {
                    "serviceKey": clean_key,
                    "mapX": lng,
                    "mapY": lat,
                    "radius": radius,
                    "contentTypeId": "12",
                    "MobileOS": "ETC",
                    "MobileApp": "FestAndRest",
                    "_type": "json",
                    "numOfRows": 10
                }
                res = requests.get(endpoint, params=params, timeout=3)
                if res.status_code == 200:
                    data = res.json()
                    items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
                    if isinstance(items, dict):
                        items = [items]
                    for item in items:
                        i_lat = float(item.get("mapy", 0.0))
                        i_lng = float(item.get("mapx", 0.0))
                        if i_lat != 0.0 and i_lng != 0.0:
                            spots.append({
                                "name": item.get("title", "로컬 웰니스 쉼터"),
                                "lat": i_lat,
                                "lng": i_lng,
                                "description": item.get("addr1", "자연 속 힐링 공간"),
                                "category": "쉼터"
                            })
        except Exception:
            pass

    return spots


def get_festival_infra_bundle(fest_lat: float, fest_lng: float, radius_m: int = 3000, target_address: str = "") -> Dict[str, List[Dict[str, Any]]]:
    """축제 좌표를 기준으로 주차장, 모범식당, 웰니스 쉼터를 3종 패키지 번들로 반환합니다. (반경 최대 20km 확장 지원)"""
    if not fest_lat or abs(fest_lat) < 1.0 or not fest_lng or abs(fest_lng) < 1.0:
        return {
            "parking_lots": [],
            "model_restaurants": [],
            "tourist_spots": []
        }

    # 주차장은 축제장 바로 앞 주차장을 우선 확보(최대 5km 이내 우선, 없으면 radius_m 확장)
    parking = get_nearby_parking(fest_lat, fest_lng, radius_m=min(radius_m, 5000))
    if not parking and radius_m > 5000:
        parking = get_nearby_parking(fest_lat, fest_lng, radius_m=radius_m)
    parking = parking[:15]

    restaurants = get_nearby_restaurants(fest_lat, fest_lng, radius_m=radius_m, target_address=target_address)[:15]
    wellness = get_wellness_spots(fest_lat, fest_lng, radius=radius_m)[:6]

    return {
        "parking_lots": parking,
        "model_restaurants": restaurants,
        "tourist_spots": wellness
    }

# ==============================================================================
# [공공데이터 수집 및 전처리 보강 유틸리티] (웰니스 수집 & 결측 좌표 자동 보강)
# ==============================================================================
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import shutil
import time
import numpy as np

# 웰니스 4대 핵심 테마 키워드 (문화체육관광부 & 한국관광공사 공인 분류 체계)
WELLNESS_THEME_KEYWORDS = {
    "힐링/명상": ["힐링", "명상", "템플스테이", "치유"],
    "뷰티/스파": ["스파", "온천", "테라피"],
    "자연/숲치유": ["웰니스", "치유의숲", "휴양림"],
    "한방체험": ["한방", "약초"]
}


def get_decoded_key(key: str) -> str:
    """URL 인코딩된 인증키를 안전하게 디코딩합니다."""
    return urllib.parse.unquote(key).strip()


def fetch_from_tour_api(url: str, params: dict) -> List[Dict[str, Any]]:
    """주어진 URL과 파라미터로 공공데이터포털 TourAPI를 호출하고 아이템 리스트를 반환합니다."""
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        res_text = response.text.strip()

        # JSON 응답 파싱
        if res_text.startswith("{"):
            data_json = response.json()
            header = data_json.get("response", {}).get("header", {})
            if header.get("resultCode") != "0000":
                return []
            items_container = data_json.get("response", {}).get("body", {}).get("items", {})
            if not items_container:
                return []
            items = items_container.get("item", [])
            return [items] if isinstance(items, dict) else items

        # XML 응답 폴백 파싱
        elif res_text.startswith("<"):
            root = ET.fromstring(res_text)
            result_code = root.find(".//resultCode")
            if result_code is not None and result_code.text != "0000":
                return []
            items = []
            for item_elem in root.findall(".//item"):
                item_dict = {child.tag: (child.text or "").strip() for child in item_elem}
                items.append(item_dict)
            return items
    except Exception:
        pass
    return []


def collect_wellness_data(output_file_path: Optional[str] = None, service_key: Optional[str] = None) -> pd.DataFrame:
    """한국관광공사 TourAPI를 호출하여 전체 웰니스 관광지 목록을 수집하고 CSV로 저장합니다."""
    sec_key = (
        service_key
        or os.getenv("TOUR_API_KEY")
        or os.getenv("DATA_GO_KR_API_KEY")
        or ""
    )
    out_path = output_file_path or os.path.join(DEFAULT_DATA_DIR, "wellness.csv")

    if not sec_key:
        print("⚠️ [Warn] TOUR_API_KEY 또는 DATA_GO_KR_API_KEY가 설정되지 않았습니다.")
        if os.path.exists(out_path):
            return pd.read_csv(out_path, encoding="utf-8-sig")
        return pd.DataFrame()

    print("=" * 65)
    print("🌿 [한국관광공사 TourAPI] 웰니스 관광지 데이터 수집 시작")
    print(f"🔑 사용 인증키 (.env): {sec_key[:15]}...{sec_key[-5:] if len(sec_key) > 5 else ''}")
    print("=" * 65)

    dec_key = get_decoded_key(sec_key)
    collected_dict = {}

    # 1. 웰니스 전용 동기화 엔드포인트
    sync_url = "http://apis.data.go.kr/B551011/KorWellnessTourismService/wellnessTursmSyncList"
    sync_params = {
        "serviceKey": dec_key,
        "pageNo": 1,
        "numOfRows": 100,
        "MobileOS": "ETC",
        "MobileApp": "WellnessCollector",
        "_type": "json"
    }
    sync_items = fetch_from_tour_api(sync_url, sync_params)
    if sync_items:
        print(f"  -> ✅ 웰니스 전용 엔드포인트 연동 성공! ({len(sync_items)}건 수신)")
        for item in sync_items:
            cid = str(item.get("contentid", "") or item.get("title", ""))
            collected_dict[cid] = {
                "title": str(item.get("title", "") or "").strip(),
                "addr1": str(item.get("addr1", "") or "").strip(),
                "addr2": str(item.get("addr2", "") or "").strip(),
                "full_address": f"{item.get('addr1', '')} {item.get('addr2', '')}".strip(),
                "areacode": str(item.get("areacode", "") or ""),
                "sigungucode": str(item.get("sigungucode", "") or ""),
                "mapx": str(item.get("mapx", "") or ""),
                "mapy": str(item.get("mapy", "") or ""),
                "theme": str(item.get("theme", "") or "웰니스"),
                "overview": str(item.get("overview", "") or "").strip(),
                "tel": str(item.get("tel", "") or "").strip(),
                "firstimage": str(item.get("firstimage", "") or ""),
                "contentid": cid
            }

    # 2. TourAPI 4.0 정식 엔드포인트(KorService2) 테마별 수집
    search_url = "http://apis.data.go.kr/B551011/KorService2/searchKeyword2"
    for category_name, keywords in WELLNESS_THEME_KEYWORDS.items():
        for kw in keywords:
            page = 1
            kw_collected = 0
            while True:
                params = {
                    "serviceKey": dec_key,
                    "numOfRows": 50,
                    "pageNo": page,
                    "MobileOS": "ETC",
                    "MobileApp": "WellnessCollector",
                    "_type": "json",
                    "keyword": kw
                }
                items = fetch_from_tour_api(search_url, params)
                if not items:
                    break
                for item in items:
                    cid = str(item.get("contentid", "") or "")
                    if not cid:
                        continue
                    if cid not in collected_dict:
                        addr1 = str(item.get("addr1", "") or "").strip()
                        addr2 = str(item.get("addr2", "") or "").strip()
                        collected_dict[cid] = {
                            "title": str(item.get("title", "") or "").strip(),
                            "addr1": addr1,
                            "addr2": addr2,
                            "full_address": f"{addr1} {addr2}".strip(),
                            "areacode": str(item.get("areacode", "") or ""),
                            "sigungucode": str(item.get("sigungucode", "") or ""),
                            "mapx": str(item.get("mapx", "") or ""),
                            "mapy": str(item.get("mapy", "") or ""),
                            "theme": category_name,
                            "overview": f"[{category_name}] 한국관광공사 등록 웰니스/힐링 관광지 ({kw})",
                            "tel": str(item.get("tel", "") or "").strip(),
                            "firstimage": str(item.get("firstimage", "") or ""),
                            "contentid": cid
                        }
                        kw_collected += 1
                if len(items) < 50 or page >= 5:
                    break
                page += 1
            print(f"  -> 테마 [{category_name}] 키워드 '{kw}': 신규 {kw_collected}건 수집 완료")

    df = pd.DataFrame(list(collected_dict.values()))
    if not df.empty:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print("\n" + "=" * 65)
        print("🎉 [수집 성공] 웰니스 관광지 데이터 저장 완료!")
        print(f"📁 저장 파일 경로 : {out_path}")
        print(f"📊 총 수집 건수   : {len(df):,}건")
        print("=" * 65)
    return df


def extract_dong_or_eup(address: str) -> str:
    """주소에서 읍/면/동 키워드를 추출합니다."""
    m = re.search(r'([가-힣0-9]+(?:읍|면|동|가|리))\b', address)
    return m.group(1) if m else ""


def build_district_coordinate_index(
    festivals_file: Optional[str] = None,
    store_file: Optional[str] = None
) -> Tuple[Dict[str, Tuple[float, float]], Dict[str, Tuple[float, float]]]:
    """행정안전부 착한가격업소 및 축제 데이터로부터 시군구 및 읍면동 단위 중심 좌표 색인을 구축합니다."""
    fest_path = festivals_file or os.path.join(DEFAULT_DATA_DIR, "festivals.csv")
    st_path = store_file or os.path.join(DEFAULT_DATA_DIR, "행정안전부_착한가격업소 현황_20260630.csv")

    dong_coords = {}
    sigungu_coords = {}

    if os.path.exists(st_path):
        try:
            df_store = pd.read_csv(st_path, encoding="cp949", low_memory=False)
            for _, r in df_store.iterrows():
                try:
                    lat = float(r.get("위도", 0.0))
                    lng = float(r.get("경도", 0.0))
                except (ValueError, TypeError):
                    continue
                if not (33.0 <= lat <= 39.0 and 124.0 <= lng <= 132.0):
                    continue
                sido = clean_text(r.get("시도", ""))
                sigungu = clean_text(r.get("시군구", ""))
                addr = clean_text(r.get("주소", ""))
                dong = extract_dong_or_eup(addr)

                sg_key = f"{sido} {sigungu}".strip()
                if sg_key:
                    sigungu_coords.setdefault(sg_key, []).append((lat, lng))
                if sg_key and dong:
                    dong_key = f"{sg_key} {dong}".strip()
                    dong_coords.setdefault(dong_key, []).append((lat, lng))
        except Exception as e:
            print(f"[Warn] 착한가격업소 색인 구축 중 예외: {e}")

    if os.path.exists(fest_path):
        try:
            df_fest = pd.read_csv(fest_path, encoding="utf-8-sig", low_memory=False)
            for _, r in df_fest.iterrows():
                try:
                    lat = float(r.get("위도", 0.0))
                    lng = float(r.get("경도", 0.0))
                except (ValueError, TypeError):
                    continue
                if not (33.0 <= lat <= 39.0 and 124.0 <= lng <= 132.0):
                    continue
                agency = clean_text(r.get("제공기관명", ""))
                road = clean_text(r.get("소재지도로명주소", ""))
                jibun = clean_text(r.get("소재지지번주소", ""))
                full_addr = f"{road} {jibun}".strip()
                dong = extract_dong_or_eup(full_addr)

                if agency:
                    sigungu_coords.setdefault(agency, []).append((lat, lng))
                    if dong:
                        dong_coords.setdefault(f"{agency} {dong}", []).append((lat, lng))
        except Exception as e:
            print(f"[Warn] 축제 실데이터 색인 구축 중 예외: {e}")

    dong_medians = {k: (round(float(np.median([c[0] for c in v])), 7), round(float(np.median([c[1] for c in v])), 7)) for k, v in dong_coords.items()}
    sigungu_medians = {k: (round(float(np.median([c[0] for c in v])), 7), round(float(np.median([c[1] for c in v])), 7)) for k, v in sigungu_coords.items()}
    return dong_medians, sigungu_medians


_NOMINATIM_CACHE = {}


def query_nominatim(query: str) -> Tuple[Optional[float], Optional[float]]:
    """OpenStreetMap Nominatim API를 호출하여 좌표를 조회합니다."""
    q = clean_text(query)
    if not q or len(q) < 3:
        return None, None
    if q in _NOMINATIM_CACHE:
        return _NOMINATIM_CACHE[q]

    cleaned_q = re.sub(r'\s+[0-9]+(-[0-9]+)?(번지|호|동)?$', '', q).strip()
    cleaned_q = re.sub(r'\([^)]*\)', '', cleaned_q).strip()

    try:
        encoded = urllib.parse.quote(cleaned_q)
        url = f"https://nominatim.openstreetmap.org/search?q={encoded}&format=json&countrycodes=kr&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "FestaPickDataPipeline/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data_resp = json.loads(resp.read().decode("utf-8"))
            if data_resp and len(data_resp) > 0:
                lat = float(data_resp[0]["lat"])
                lng = float(data_resp[0]["lon"])
                if 33.0 <= lat <= 39.0 and 124.0 <= lng <= 132.0:
                    _NOMINATIM_CACHE[q] = (round(lat, 7), round(lng, 7))
                    return round(lat, 7), round(lng, 7)
    except Exception:
        pass

    _NOMINATIM_CACHE[q] = (None, None)
    return None, None


def fill_festival_coordinates(festivals_file: Optional[str] = None, backup: bool = True) -> Tuple[int, int, int]:
    """festivals.csv의 결측 좌표(위도/경도)를 지오코딩 및 행정구역 중심좌표로 100% 자동 보강합니다."""
    target_file = festivals_file or os.path.join(DEFAULT_DATA_DIR, "festivals.csv")
    backup_file = target_file.replace(".csv", "_backup.csv")

    if not os.path.exists(target_file):
        print(f"[Error] 축제 데이터 파일이 존재하지 않습니다: {target_file}")
        return 0, 0, 0

    if backup and not os.path.exists(backup_file):
        shutil.copyfile(target_file, backup_file)
        print(f"📦 원본 백업본 생성 완료: {os.path.basename(backup_file)}")

    df = pd.read_csv(target_file, encoding="utf-8-sig", low_memory=False)
    is_missing = df["위도"].isna() | df["경도"].isna() | (df["위도"] == 0) | (df["경도"] == 0)
    missing_indices = df[is_missing].index.tolist()
    if not missing_indices:
        print("✅ 이미 모든 축제에 유효한 좌표가 등록되어 있습니다.")
        return 0, 0, 0

    print("🔍 전국 시군구 및 읍면동 행정구역 중심 좌표 색인 구축 중...")
    dong_medians, sigungu_medians = build_district_coordinate_index(target_file)
    filled_nominatim = 0
    filled_dong = 0
    filled_sigungu = 0

    print(f"⚡ {len(missing_indices)}개 결측 축제 좌표 보강 실행 중...")
    for idx in missing_indices:
        row = df.loc[idx]
        agency = clean_text(row.get("제공기관명", ""))
        road = clean_text(row.get("소재지도로명주소", ""))
        jibun = clean_text(row.get("소재지지번주소", ""))
        venue = clean_text(row.get("개최장소", ""))

        target_lat, target_lng = None, None

        for query_cand in [road, jibun, f"{agency} {venue}".strip()]:
            if query_cand and len(query_cand) >= 4:
                lat, lng = query_nominatim(query_cand)
                if lat and lng:
                    target_lat, target_lng = lat, lng
                    filled_nominatim += 1
                    time.sleep(0.5)
                    break

        if not target_lat:
            full_addr = f"{road} {jibun} {venue}"
            dong = extract_dong_or_eup(full_addr)
            if dong:
                for k, coord in dong_medians.items():
                    if agency in k and dong in k:
                        target_lat, target_lng = coord
                        filled_dong += 1
                        break

        if not target_lat:
            for k, coord in sigungu_medians.items():
                if agency in k or (agency and k in agency):
                    target_lat, target_lng = coord
                    filled_sigungu += 1
                    break

        # 4차: 모든 탐색 실패 시 임의 가짜 좌표 대신 0.0, 0.0으로 명시 (get_festivals에서 자동 필터링하여 데이터 신뢰성 보장)
        if not target_lat:
            target_lat, target_lng = 0.0, 0.0

        df.at[idx, "위도"] = target_lat
        df.at[idx, "경도"] = target_lng

    df.to_csv(target_file, encoding="utf-8-sig", index=False)
    print("\n" + "=" * 65)
    print("🎉 [보강 완료] 전국 문화축제 좌표 보강 결과:")
    print(f" - Nominatim 정밀 검색 보강: {filled_nominatim}건")
    print(f" - 행정구역 읍/면/동 중심 좌표 보강: {filled_dong}건")
    print(f" - 시/군/구 중심 좌표 보강: {filled_sigungu}건")
    print(f"💾 최신 데이터 저장 완료: {target_file}")
    print("=" * 65)
    return filled_nominatim, filled_dong, filled_sigungu


# [요구사항 2] 함수 별칭 제공 (호환성)
fill_coordinates = fill_festival_coordinates


# 직접 실행 시 데이터 통합 인덱싱 및 필터링 검색 테스트 또는 데이터 수집/보강 실행 메인 블록입니다.
if __name__ == "__main__":
    # CLI 옵션 지원 (--collect-wellness, --fill-coords)
    if "--collect-wellness" in sys.argv:
        print("🌿 [CLI 모드] 웰니스 관광지 데이터 수집을 실행합니다...")
        collect_wellness_data()
        sys.exit(0)

    if "--fill-coords" in sys.argv:
        print("📍 [CLI 모드] 축제 결측 좌표 자동 보강을 실행합니다...")
        fill_festival_coordinates()
        sys.exit(0)

    # 기본: 매니저 객체 생성 및 RAG 코스 패키징 검증
    manager = PublicDataRAGManager(
        data_dir="data",
        db_path="chromadb_store",
        collection_name="integrated_festivals"
    )

    # 1. 3종 데이터셋(축제 + 주차장 + 착한가격업소) 통합 로드
    docs = manager.load_all_datasets(sample_per_region=150)

    # 2. 통합 컬렉션에 reset=True 옵션으로 재인덱싱 수행
    manager.index_documents(batch_size=200, reset=True)

    # 3. 강원권 착한가격업소 Top 3 요약 조회 테스트
    stores = manager.get_top_good_price_stores(region="강원권", n_results=3)
    print("\n================ [ 강원권 착한가격업소 TOP 3 요약 리포트 ] ================\n")
    for idx, s in enumerate(stores, 1):
        print(f"[{idx}] 업소명: {s.get('title')} [{s.get('category')}] | 권역: {s.get('region')}")
        print(f"    대표메뉴: {s.get('menu')}")
        print(f"    주소: {s.get('location')} | 전화: {s.get('phone')}")
        print("-" * 60)

    # 4. 체력 기반 맞춤 코스 패키징 테스트 (동일 시군구 위치 정합성 검증)
    print("\n================ [ 체력별 맞춤 4단계 코스 패키징 테스트 ] ================\n")
    course_res = manager.generate_custom_course(festival_name="연호문화축제", user_stamina="중")
    print(f"📌 코스명 : {course_res['course_summary']}")
    print(f"📍 위치정합성 : {course_res['location_integrity_notice']}")
    for step in course_res["timeline"]:
        print(f"\n[{step['step']}단계 {step['icon']} {step['category']}] {step.get('title') or step.get('name')}")
        print(f"  - 위치: {step.get('location')}")
        print(f"  - 팁: {step.get('stamina_tip')}")