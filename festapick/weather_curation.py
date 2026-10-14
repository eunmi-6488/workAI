"""
festapick/weather_curation.py - 전국 날씨 연동 지역 축제 & 여행 코스 큐레이션 모듈
================================================================================
1. 상단: 날짜 선택 영역(이전/다음, 오늘/이번 주말 퀵버튼) + 6대 권역 미니 날씨 카드
2. 중단: 선택 권역 상세 날씨 뱃지 (기온, 습도, 강수확률, 여행 옷차림/나들이 팁)
3. 하단: 추천 축제 & 당일 여행 코스 카드 리스트 (인근 주차 정보 Expander 포함)
================================================================================
"""

import os
import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Any

# ------------------------------------------------------------------------------
# 1. Mock Data (6대 권역 날씨 & 추천 축제 & 여행 코스 & 주차 인프라)
# ------------------------------------------------------------------------------
REGIONS_INFO = {
    "수도권": {
        "icon": "☀️",
        "weather": "맑음",
        "temp_min": 12,
        "temp_max": 23,
        "rain_prob": 10,
        "dust": "좋음 (18㎍/㎥)",
        "wind": "1.8 m/s",
        "clothing_tip": "낮에는 온화하나 해 질 녘 강바람이 쌀쌀하니 가벼운 바람막이나 카디건을 챙기세요.",
        "outing_tip": "야외 축제와 산책로를 즐기기에 최적의 청명한 가을 날씨입니다. 돗자리와 선글라스를 추천합니다.",
        "festivals": [
            {
                "name": "2026 서울세계불꽃축제",
                "dates": "2026.10.10 ~ 2026.10.10",
                "location": "서울특별시 영등포구 여의도 한강공원 일원",
                "theme": "야경/불꽃 · 가을 밤 로맨틱 힐링",
                "image": "https://images.unsplash.com/photo-1531306728370-e2ebd9d7bb99?auto=format&fit=crop&w=800&q=80",
                "course_summary": [
                    {"time": "14:00", "spot": "더현대 서울 쇼핑 & 카페", "desc": "실내 쾌적한 휴식 및 가을 간식 준비"},
                    {"time": "17:00", "spot": "여의도 한강공원 명당 선점", "desc": "선선한 강바람 맞으며 돗자리 피크닉"},
                    {"time": "19:30", "spot": "불꽃쇼 본 행사 관람", "desc": "음악과 함께 펼쳐지는 초대형 불꽃 파노라마"}
                ],
                "parking_info": {
                    "name": "여의도 한강공원 1~3주차장 & 63빌딩 앞 주차장",
                    "fee": "기본 30분 2,000원 (초과 10분당 300원 / 일 최대 15,000원)",
                    "capacity": "총 1,820면",
                    "tip": "행사 당일 14시 이후 인근 도로 통제되므로 여의나루역/샛강역 대중교통 이용을 적극 권장합니다."
                }
            },
            {
                "name": "제63회 수원화성문화제",
                "dates": "2026.10.09 ~ 2026.10.12",
                "location": "경기도 수원시 팔달구 화성행궁 및 수원화성 일원",
                "theme": "역사/문화 · 정조대왕 능행차 재현",
                "image": "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=800&q=80",
                "course_summary": [
                    {"time": "11:00", "spot": "화성행궁 관람 & 궁중문화체험", "desc": "행궁 정원 산책 및 전통 한복 체험"},
                    {"time": "13:00", "spot": "행궁동 공방거리 & 행리단길 맛집", "desc": "수원 통닭거리 왕갈비통닭 점심 식사"},
                    {"time": "16:00", "spot": "방화수류정 성곽길 산책", "desc": "억새풀과 용연 연못을 배경으로 인생샷 촬영"}
                ],
                "parking_info": {
                    "name": "화성행궁 노상주차장 & 연무대 공영주차장",
                    "fee": "1회 3시간 2,000원 (10분당 200원)",
                    "capacity": "총 480면",
                    "tip": "연무대 공영주차장이 회차 및 주차 공간이 가장 여유롭습니다."
                }
            }
        ]
    },
    "강원": {
        "icon": "⛅",
        "weather": "구름조금",
        "temp_min": 9,
        "temp_max": 19,
        "rain_prob": 20,
        "dust": "좋음 (12㎍/㎥)",
        "wind": "2.5 m/s",
        "clothing_tip": "산간과 바닷가 기온이 10도 미만으로 떨어지니 도톰한 니트와 머플러를 준비하세요.",
        "outing_tip": "청량한 동해 바다와 맑은 공기가 어우러지는 날입니다. 야외 드라이브 코스로 제격입니다.",
        "festivals": [
            {
                "name": "2026 강릉 커피축제",
                "dates": "2026.10.10 ~ 2026.10.13",
                "location": "강원특별자치도 강릉시 안목해변 및 강릉스피디움",
                "theme": "커피/미식 · 100인 바리스타 핸드드립 쇼",
                "image": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=800&q=80",
                "course_summary": [
                    {"time": "10:30", "spot": "안목 커피거리 솔숲 산책", "desc": "파도 소리 들으며 스페셜티 모닝 커피"},
                    {"time": "13:00", "spot": "강릉 중앙시장 로컬 투어", "desc": "오징어순대 & 장칼국수 든든한 점심"},
                    {"time": "15:30", "spot": "축제장 커피 어워드 관람", "desc": "전국 로스터리 부스 무료 시음 및 원두 마켓"}
                ],
                "parking_info": {
                    "name": "안목해변 공영주차장 & 강릉항 여객터미널 주차장",
                    "fee": "무료 개방",
                    "capacity": "총 650면",
                    "tip": "주말 11시 이후 만차 시 강릉역 셔틀버스 환승 주차장을 이용하세요."
                }
            },
            {
                "name": "제51회 정선아리랑제",
                "dates": "2026.10.08 ~ 2026.10.11",
                "location": "강원특별자치도 정선군 정선공설운동장 일원",
                "theme": "유네스코 인류무형문화유산 · 소리 축제",
                "image": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=800&q=80",
                "course_summary": [
                    {"time": "11:00", "spot": "정선 5일장 장터 난장 구경", "desc": "곤드레밥과 메밀전병 로컬 푸드 체험"},
                    {"time": "14:00", "spot": "아리랑 센터 뮤지컬 공연", "desc": "감동적인 아리랑 소리극 무료 관람"},
                    {"time": "16:30", "spot": "병방치 스카이워크 조망", "desc": "한반도 지형 밤섬 굽어보는 아찔한 절경"}
                ],
                "parking_info": {
                    "name": "정선 종합운동장 임시주차장",
                    "fee": "무료",
                    "capacity": "총 1,200면",
                    "tip": "셔틀버스가 15분 간격으로 축제장 입구까지 순환 운행됩니다."
                }
            }
        ]
    },
    "충청": {
        "icon": "🌤️",
        "weather": "맑고 쾌청",
        "temp_min": 11,
        "temp_max": 22,
        "rain_prob": 15,
        "dust": "보통 (34㎍/㎥)",
        "wind": "1.5 m/s",
        "clothing_tip": "낮 기온이 22도까지 올라 나들이하기 편한 긴팔 셔츠에 얇은 겉옷 조합이 좋습니다.",
        "outing_tip": "가을 백제 역사 유적지와 야간 빛 축제를 모두 즐길 수 있는 이상적인 날씨입니다.",
        "festivals": [
            {
                "name": "2026 백제문화제 (공주·부여)",
                "dates": "2026.10.03 ~ 2026.10.12",
                "location": "충청남도 공주시 금강신관공원 및 공산성 일원",
                "theme": "백제 역사 부흥 · 웅진판타지아 실경공연",
                "image": "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=800&q=80",
                "course_summary": [
                    {"time": "13:00", "spot": "무령왕릉과 왕릉원 탐방", "desc": "백제 고분군 숲길 산책 및 디지털 전시관"},
                    {"time": "15:30", "spot": "공주 공산성 성곽 트레킹", "desc": "금강변을 굽어보는 가을 유네스코 유산 걷기"},
                    {"time": "18:30", "spot": "금강 유등 & 부교 건너기", "desc": "물 위에 띄운 백제 수백 개 유등 야경 감상"}
                ],
                "parking_info": {
                    "name": "금강신관공원 둔치주차장 & 백제체육관 주차장",
                    "fee": "무료",
                    "capacity": "총 2,100면",
                    "tip": "백제체육관에 주차 후 축제 전용 셔틀열차(고마열차)를 타면 정체 없이 이동 가능합니다."
                }
            },
            {
                "name": "2026 태안 가을꽃박람회",
                "dates": "2026.09.20 ~ 2026.11.01",
                "location": "충청남도 태안군 안면읍 꽃지해안로 400 코리아플라워파크",
                "theme": "가을 국화 · 핑크뮬리 & 낙조 명소",
                "image": "https://images.unsplash.com/photo-1490750967868-88aa4486c946?auto=format&fit=crop&w=800&q=80",
                "course_summary": [
                    {"time": "11:30", "spot": "안면도 게국지 로컬 맛집", "desc": "얼큰하고 시원한 안면도 명물 게국지 점심"},
                    {"time": "13:30", "spot": "꽃지해수욕장 플라워파크", "desc": "국화, 핑크뮬리, 버베나 정원 산책"},
                    {"time": "17:30", "spot": "할미·할아비 바위 낙조", "desc": "서해 3대 일몰 명소에서 붉은 노을 감상"}
                ],
                "parking_info": {
                    "name": "꽃지해수욕장 제1·2 공영주차장",
                    "fee": "승용차 당일 5,000원",
                    "capacity": "총 1,500면",
                    "tip": "일몰 1시간 전 입차 시 혼잡하므로 15시 이전 여유 있게 입차를 추천합니다."
                }
            }
        ]
    },
    "전라": {
        "icon": "☀️",
        "weather": "화창함",
        "temp_min": 13,
        "temp_max": 24,
        "rain_prob": 10,
        "dust": "좋음 (15㎍/㎥)",
        "wind": "1.2 m/s",
        "clothing_tip": "햇살이 따사로우나 평야 지대 그늘은 서늘하니 자외선 차단 모자와 경량 재킷을 권장합니다.",
        "outing_tip": "순천만의 황금빛 갈대밭과 남도 미식을 탐방하기에 한 해 중 가장 완벽한 시즌입니다.",
        "festivals": [
            {
                "name": "제26회 순천만 갈대축제",
                "dates": "2026.10.15 ~ 2026.10.19",
                "location": "전라남도 순천시 순천만습지 및 국가정원 일원",
                "theme": "생태 웰니스 · 황금빛 갈대숲 걷기",
                "image": "https://images.unsplash.com/photo-1473448912268-2022ce9509d8?auto=format&fit=crop&w=800&q=80",
                "course_summary": [
                    {"time": "11:00", "spot": "순천만 국가정원 관람", "desc": "스카이큐브 모노레일 타고 습지로 이동"},
                    {"time": "13:30", "spot": "순천 꼬막정식 & 짱뚱어탕 점심", "desc": "남도 20첩 반상으로 든든한 식사"},
                    {"time": "16:00", "spot": "용산전망대 갈대밭 낙조", "desc": "S자 수로에 비치는 붉은 칠면초와 황금 갈대"}
                ],
                "parking_info": {
                    "name": "순천만습지 주차장 & 순천만국가정원 동문 주차장",
                    "fee": "소형차 3,000원 (정원 입장객 주차 지원)",
                    "capacity": "총 2,300면",
                    "tip": "국가정원 동문 주차장에 주차 후 스카이큐브를 타고 습지로 넘어가면 주차 스트레스가 전혀 없습니다."
                }
            },
            {
                "name": "2026 전주 페스타 (비빔밥축제)",
                "dates": "2026.10.09 ~ 2026.10.12",
                "location": "전북특별자치도 전주시 완산구 전주종합경기장 및 한옥마을",
                "theme": "K-미식 · 대형 비빔밥 퍼포먼스",
                "image": "https://images.unsplash.com/photo-1590301157890-4810ed352733?auto=format&fit=crop&w=800&q=80",
                "course_summary": [
                    {"time": "10:30", "spot": "전주 한옥마을 경기전 산책", "desc": "대나무 숲 태조 어진 관람 및 한복 체험"},
                    {"time": "13:00", "spot": "전주 남부시장 청년몰 투어", "desc": "피순대 국밥 및 막걸리 골목 맛 기행"},
                    {"time": "15:30", "spot": "비빔밥 퍼포먼스 및 쿠킹 클래스", "desc": "유네스코 음식창의도시 미식 페스티벌 참가"}
                ],
                "parking_info": {
                    "name": "전주 한옥마을 1·2 공영주차장",
                    "fee": "기본 30분 1,000원 (초과 15분당 500원)",
                    "capacity": "총 890면",
                    "tip": "기린대로 노상주차장 또는 대성공영주차장(무료 셔틀)을 이용하시는 것이 훨씬 빠릅니다."
                }
            }
        ]
    },
    "경상": {
        "icon": "🌤️",
        "weather": "맑고 쾌청",
        "temp_min": 14,
        "temp_max": 24,
        "rain_prob": 10,
        "dust": "좋음 (20㎍/㎥)",
        "wind": "1.7 m/s",
        "clothing_tip": "낮 시간대에는 반팔도 가능할 정도로 온화하나, 야간 강변 축제는 겉옷이 필수입니다.",
        "outing_tip": "남강을 수놓는 화려한 유등과 역사의 숨결을 만끽하기 최상의 가을 날씨입니다.",
        "festivals": [
            {
                "name": "2026 진주 남강유등축제",
                "dates": "2026.10.04 ~ 2026.10.18",
                "location": "경상남도 진주시 남강 및 진주성 일원",
                "theme": "빛과 사랑 · 대한민국 글로벌 육성축제",
                "image": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=800&q=80",
                "course_summary": [
                    {"time": "14:00", "spot": "국립진주박물관 & 촉석루 탐방", "desc": "임진왜란 진주대첩 역사 유적지 답사"},
                    {"time": "16:30", "spot": "진주 중앙시장 육회비빔밥", "desc": "70년 전통 하연옥 진주냉면 & 비빔밥"},
                    {"time": "19:00", "spot": "남강 부교 배다리 건너기 & 유등 소원띄우기", "desc": "7만 개 유등 파노라마와 불꽃놀이 감상"}
                ],
                "parking_info": {
                    "name": "진주종합경기장 & 정촌초 임시주차장",
                    "fee": "무료",
                    "capacity": "총 3,500면",
                    "tip": "시내 진입로 통제 시 무료 셔틀버스(5분 간격) 전용 차로를 이용해 축제장 직행이 가능합니다."
                }
            },
            {
                "name": "2026 안동 국제탈춤페스티벌",
                "dates": "2026.10.02 ~ 2026.10.11",
                "location": "경상북도 안동시 탈춤공원 및 하회마을 일원",
                "theme": "신명나는 탈춤 · 세계 유산의 울림",
                "image": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
                "course_summary": [
                    {"time": "10:30", "spot": "안동 하회마을 만송정 숲길", "desc": "부용대 절벽과 낙동강 섶다리 걷기"},
                    {"time": "13:00", "spot": "안동 구시장 찜닭 골목", "desc": "푸짐한 안동찜닭과 간고등어 점심"},
                    {"time": "15:30", "spot": "탈춤공원 국내외 탈춤 갈라쇼", "desc": "하회별신굿탈놀이 마당극 관람 및 탈 만들기"}
                ],
                "parking_info": {
                    "name": "안동 탈춤공원 지하주차장 & 강변둔치주차장",
                    "fee": "무료",
                    "capacity": "총 1,800면",
                    "tip": "강변둔치주차장에서 도보 5분 거리의 징검다리를 건너면 축제장 메인 게이트에 바로 도착합니다."
                }
            }
        ]
    },
    "제주": {
        "icon": "🌤️",
        "weather": "선선한 바람",
        "temp_min": 16,
        "temp_max": 24,
        "rain_prob": 15,
        "dust": "매우좋음 (8㎍/㎥)",
        "wind": "3.8 m/s",
        "clothing_tip": "제주 특유의 바람이 다소 강하게 부니 모자가 날아가지 않도록 유의하고 윈드브레이커를 입으세요.",
        "outing_tip": "억새풀이 파도치는 오름과 핑크빛 가을 정원을 걷기에 눈부시게 아름다운 날씨입니다.",
        "festivals": [
            {
                "name": "2026 휴애리 핑크뮬리 축제",
                "dates": "2026.09.15 ~ 2026.11.15",
                "location": "제주특별자치도 서귀포시 남원읍 신례동로 256 휴애리 자연생활공원",
                "theme": "핑크빛 가을 힐링 · 감귤 따기 체험",
                "image": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
                "course_summary": [
                    {"time": "10:30", "spot": "사려니숲길 삼나무 트레킹", "desc": "피톤치드 마시며 숲속 힐링 보행"},
                    {"time": "13:00", "spot": "서귀포 흑돼지 & 보말칼국수", "desc": "제주 로컬 식재료 미식 탐방"},
                    {"time": "15:00", "spot": "휴애리 핑크뮬리 하늘정원", "desc": "한라산 배경 핑크빛 물결 인생사진 & 흑돼지 교감"}
                ],
                "parking_info": {
                    "name": "휴애리 전용 대형 주차장",
                    "fee": "무료",
                    "capacity": "총 600면",
                    "tip": "전기차 완속/급속 충전소 8기가 완비되어 있어 여행 중 충전하기에 매우 편리합니다."
                }
            },
            {
                "name": "제32회 서귀포 칠십리축제",
                "dates": "2026.10.16 ~ 2026.10.18",
                "location": "제주특별자치도 서귀포시 칠십리시공원 일원",
                "theme": "칠십리 바당의 노래 · 천지연 폭포 야경",
                "image": "https://images.unsplash.com/photo-1544644181-1484b3fdfc62?auto=format&fit=crop&w=800&q=80",
                "course_summary": [
                    {"time": "11:00", "spot": "새연교 & 새섬 산책로", "desc": "바다 위 다리 건너 솔숲길 바다 조망"},
                    {"time": "13:00", "spot": "서귀포 매일올레시장 먹거리", "desc": "모닥치기 떡볶이 & 마늘통닭 & 귤 디저트"},
                    {"time": "16:00", "spot": "칠십리시공원 전통 퍼레이드", "desc": "서귀포 17개 읍면동 거리 퍼레이드 및 천지연 음악회"}
                ],
                "parking_info": {
                    "name": "천지연폭포 주차장 & 칠십리시공원 주차장",
                    "fee": "기본 무료",
                    "capacity": "총 750면",
                    "tip": "새연교 공영주차장에 주차 후 도보로 이동하면 천지연 해안 도로 정체를 피할 수 있습니다."
                }
            }
        ]
    }
}


def render_weather_festival_curation_page():
    """전국 날씨 연동 지역 축제 & 여행 코스 큐레이션 전용 화면 렌더러"""

    # 1. 세션 상태 초기화
    if "cur_selected_region" not in st.session_state:
        st.session_state.cur_selected_region = "충청"

    if "cur_selected_date" not in st.session_state:
        st.session_state.cur_selected_date = datetime(2026, 10, 10)  # 가을 토요일 기준

    # 쿼리 파라미터 처리
    if "w_region" in st.query_params:
        r_p = st.query_params.get("w_region")
        if r_p in REGIONS_INFO:
            st.session_state.cur_selected_region = r_p
        del st.query_params["w_region"]
        st.rerun()

    active_region = st.session_state.cur_selected_region
    active_date = st.session_state.cur_selected_date

    # 2. 미니멀 모던 여행 스타일시트
    st.html("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    .curation-main-wrapper {
        max-width: 1200px;
        margin: 0 auto;
        padding: 16px 20px 80px 20px;
        font-family: 'Pretendard', -apple-system, sans-serif;
        color: #111827;
    }

    /* 상단 헤더 & 브랜딩 */
    .top-header-banner {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 20px;
        border-bottom: 1px solid #E5E7EB;
        margin-bottom: 24px;
        flex-wrap: wrap;
        gap: 16px;
    }
    .header-tag {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #ECFDF5;
        color: #065F46;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.02em;
    }
    .header-title-text {
        font-size: 1.65rem;
        font-weight: 900;
        color: #064E3B;
        letter-spacing: -0.03em;
        margin: 6px 0 2px 0;
    }
    .header-sub-text {
        font-size: 0.88rem;
        color: #6B7280;
    }

    /* 날짜 선택 알약 바 */
    .date-control-panel {
        background: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 16px;
        padding: 14px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
        flex-wrap: wrap;
        gap: 12px;
    }
    .date-display-box {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .date-current-badge {
        font-size: 1.15rem;
        font-weight: 800;
        color: #111827;
        background: #FFFFFF;
        padding: 6px 16px;
        border-radius: 10px;
        border: 1px solid #D1D5DB;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }

    /* 6대 권역 미니 날씨 바둑판 그리드 */
    .weather-grid-6 {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 12px;
        margin-bottom: 24px;
    }
    @media (max-width: 900px) {
        .weather-grid-6 {
            grid-template-columns: repeat(3, 1fr);
        }
    }
    @media (max-width: 540px) {
        .weather-grid-6 {
            grid-template-columns: repeat(2, 1fr);
        }
    }

    .weather-region-card {
        background: #FFFFFF;
        border: 1.5px solid #E5E7EB;
        border-radius: 16px;
        padding: 14px 12px;
        text-align: center;
        text-decoration: none !important;
        color: inherit;
        transition: all 0.2s ease;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
        cursor: pointer;
    }
    .weather-region-card:hover {
        transform: translateY(-3px);
        border-color: #10B981;
        box-shadow: 0 6px 16px rgba(16, 185, 129, 0.12);
    }
    .weather-region-card.active {
        background: #064E3B !important;
        border-color: #064E3B !important;
        color: #FFFFFF !important;
        box-shadow: 0 8px 20px rgba(6, 78, 59, 0.25);
    }
    .w-reg-name {
        font-size: 0.92rem;
        font-weight: 800;
        margin-bottom: 4px;
    }
    .w-icon {
        font-size: 1.8rem;
        margin: 4px 0;
    }
    .w-temp-line {
        font-size: 0.82rem;
        font-weight: 700;
    }
    .weather-region-card.active .w-temp-line {
        color: #FEF08A;
    }
    .w-status-sub {
        font-size: 0.70rem;
        color: #6B7280;
        margin-top: 2px;
    }
    .weather-region-card.active .w-status-sub {
        color: #A7F3D0;
    }

    /* 중단: 선택 권역 상세 날씨 뱃지 & 나들이 팁 브리핑 */
    .weather-detail-banner {
        background: linear-gradient(135deg, #064E3B 0%, #0F766E 100%);
        color: #FFFFFF;
        border-radius: 20px;
        padding: 24px 28px;
        margin-bottom: 32px;
        box-shadow: 0 12px 28px rgba(6, 78, 59, 0.18);
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 24px;
        align-items: center;
    }
    @media (max-width: 768px) {
        .weather-detail-banner {
            grid-template-columns: 1fr;
            padding: 20px;
        }
    }
    .weather-stat-badge-box {
        display: flex;
        align-items: center;
        gap: 16px;
        background: rgba(255, 255, 255, 0.12);
        padding: 16px 20px;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    .stat-huge-icon {
        font-size: 2.8rem;
    }
    .stat-temp-val {
        font-size: 2.2rem;
        font-weight: 900;
        line-height: 1;
        letter-spacing: -0.03em;
    }
    .stat-range-text {
        font-size: 0.82rem;
        color: #D1FAE5;
        margin-top: 4px;
    }

    .weather-tips-box {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .tip-title-row {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 1.15rem;
        font-weight: 800;
        color: #FEF08A;
    }
    .tip-desc-line {
        font-size: 0.92rem;
        line-height: 1.55;
        color: #F0FDF4;
        margin: 0;
    }
    .env-tag-row {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin-top: 4px;
    }
    .env-pill {
        background: rgba(0, 0, 0, 0.25);
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 0.74rem;
        color: #A7F3D0;
        border: 1px solid rgba(255, 255, 255, 0.15);
    }

    /* 하단: 추천 축제 & 여행 코스 카드 */
    .section-title-wrap {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        border-bottom: 2px solid #064E3B;
        padding-bottom: 10px;
    }
    .section-main-title {
        font-size: 1.35rem;
        font-weight: 900;
        color: #064E3B;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .section-count-tag {
        background: #D1FAE5;
        color: #065F46;
        font-size: 0.82rem;
        font-weight: 800;
        padding: 3px 10px;
        border-radius: 9999px;
    }

    .festival-course-card {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 20px;
        overflow: hidden;
        margin-bottom: 28px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
        transition: all 0.2s ease;
    }
    .festival-course-card:hover {
        border-color: #059669;
        box-shadow: 0 12px 30px rgba(6, 78, 59, 0.08);
    }

    .fest-card-top-grid {
        display: grid;
        grid-template-columns: 280px 1fr;
        gap: 24px;
        padding: 22px;
    }
    @media (max-width: 768px) {
        .fest-card-top-grid {
            grid-template-columns: 1fr;
        }
    }

    .fest-img-box {
        width: 100%;
        height: 190px;
        border-radius: 14px;
        overflow: hidden;
        position: relative;
    }
    .fest-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .fest-theme-badge {
        position: absolute;
        top: 10px;
        left: 10px;
        background: rgba(6, 78, 59, 0.85);
        color: #FFFFFF;
        font-size: 0.70rem;
        font-weight: 800;
        padding: 3px 8px;
        border-radius: 6px;
        backdrop-filter: blur(4px);
    }

    .fest-info-side {
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .fest-title {
        font-size: 1.30rem;
        font-weight: 900;
        color: #111827;
        margin: 0 0 8px 0;
    }
    .fest-meta-item {
        font-size: 0.85rem;
        color: #4B5563;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    /* 당일치기 코스 타임라인 요약 바 */
    .course-timeline-wrap {
        background: #F9FAFB;
        border-radius: 14px;
        padding: 14px 16px;
        margin-top: 12px;
        border: 1px solid #F3F4F6;
    }
    .timeline-title {
        font-size: 0.82rem;
        font-weight: 800;
        color: #065F46;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 5px;
    }
    .timeline-steps-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
    }
    @media (max-width: 600px) {
        .timeline-steps-grid {
            grid-template-columns: 1fr;
        }
    }
    .step-item-card {
        background: #FFFFFF;
        padding: 8px 10px;
        border-radius: 10px;
        border: 1px solid #E5E7EB;
    }
    .step-time-tag {
        font-size: 0.72rem;
        font-weight: 800;
        color: #059669;
        margin-bottom: 2px;
    }
    .step-spot-name {
        font-size: 0.85rem;
        font-weight: 800;
        color: #111827;
        margin-bottom: 2px;
    }
    .step-spot-desc {
        font-size: 0.74rem;
        color: #6B7280;
        line-height: 1.35;
    }

    /* 주차 정보 박스 */
    .parking-detail-box {
        background: #F0FDF4;
        border: 1px solid #BBF7D0;
        border-radius: 12px;
        padding: 14px 18px;
        margin-top: 8px;
        font-size: 0.84rem;
        line-height: 1.5;
        color: #064E3B;
    }
    .parking-detail-title {
        font-weight: 800;
        color: #065F46;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    </style>
    """)

    # 3. 상단 헤더
    st.html("""
    <div class="curation-main-wrapper">
        <div class="top-header-banner">
            <div>
                <span class="header-tag">🌦️ 실시간 기상청 & 공공데이터 융합 큐레이션</span>
                <h1 class="header-title-text">전국 날씨 연동 지역 축제 & 여행 코스</h1>
                <div class="header-sub-text">오늘의 하늘 상태와 체감 기온에 딱 맞는 최적의 로컬 축제와 1일 여행 코스를 추천합니다.</div>
            </div>
            <div>
                <a href="?view=main" style="
                    display:inline-flex; align-items:center; gap:6px; background:#111827; color:#FFFFFF;
                    font-size:0.85rem; font-weight:700; padding:8px 18px; border-radius:9999px; text-decoration:none;
                ">
                    ← 페스타픽 홈으로
                </a>
            </div>
        </div>
    """)

    # 4. 상단 날짜 컨트롤러
    col_d1, col_d2, col_d3 = st.columns([1.2, 2.2, 1.8])
    with col_d1:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("‹ 이전날", use_container_width=True, key="btn_prev_date"):
                st.session_state.cur_selected_date -= timedelta(days=1)
                st.rerun()
        with c2:
            if st.button("다음날 ›", use_container_width=True, key="btn_next_date"):
                st.session_state.cur_selected_date += timedelta(days=1)
                st.rerun()

    with col_d2:
        formatted_date = active_date.strftime("%Y.%m.%d (%a)")
        st.markdown(f"""
        <div style="text-align:center; padding:6px 0;">
            <strong style="font-size:1.15rem; color:#064E3B; background:#F0FDF4; border:1px solid #A7F3D0; padding:6px 20px; border-radius:12px;">
                📅 {formatted_date}
            </strong>
        </div>
        """, unsafe_allow_html=True)

    with col_d3:
        b1, b2 = st.columns(2)
        with b1:
            if st.button("📍 오늘 (당일)", use_container_width=True, key="btn_today"):
                st.session_state.cur_selected_date = datetime.now()
                st.rerun()
        with b2:
            if st.button("✨ 이번 주말", use_container_width=True, key="btn_weekend"):
                st.session_state.cur_selected_date = datetime(2026, 10, 10)
                st.rerun()

    st.write("")

    # 5. 전국 권역별 미니 날씨 카드 바둑판 (수도권, 강원, 충청, 전라, 경상, 제주)
    weather_cards_html = []
    for reg_key, reg_val in REGIONS_INFO.items():
        is_act = (reg_key == active_region)
        act_class = "active" if is_act else ""
        icon = reg_val["icon"]
        w_text = reg_val["weather"]
        t_max = reg_val["temp_max"]
        t_min = reg_val["temp_min"]
        r_prob = reg_val["rain_prob"]

        weather_cards_html.append(f"""
        <a href="?w_region={reg_key}" target="_self" class="weather-region-card {act_class}">
            <div class="w-reg-name">{reg_key}</div>
            <div class="w-icon">{icon}</div>
            <div class="w-temp-line">{t_min}° / {t_max}°</div>
            <div class="w-status-sub">{w_text} · 강수 {r_prob}%</div>
        </a>
        """)

    st.html(f"""
        <div class="weather-grid-6">
            {"".join(weather_cards_html)}
        </div>
    """)

    # 6. 중단: 선택 권역의 상세 날씨 뱃지 & 옷차림/나들이 추천 한 줄 팁
    cur_data = REGIONS_INFO[active_region]
    st.html(f"""
        <div class="weather-detail-banner">
            <div class="weather-stat-badge-box">
                <div class="stat-huge-icon">{cur_data['icon']}</div>
                <div>
                    <div class="stat-temp-val">{cur_data['temp_max']}°C</div>
                    <div class="stat-range-text">최저 {cur_data['temp_min']}°C · {cur_data['weather']}</div>
                </div>
            </div>

            <div class="weather-tips-box">
                <div class="tip-title-row">
                    <span>💡</span>
                    <span>{active_region}권역 가을 나들이 & 옷차림 맞춤 가이드</span>
                </div>
                <p class="tip-desc-line">
                    <strong>👗 옷차림 추천:</strong> {cur_data['clothing_tip']}
                </p>
                <p class="tip-desc-line">
                    <strong>🌿 나들이 꿀팁:</strong> {cur_data['outing_tip']}
                </p>
                <div class="env-tag-row">
                    <span class="env-pill">💧 강수확률 {cur_data['rain_prob']}%</span>
                    <span class="env-pill">💨 바람 {cur_data['wind']}</span>
                    <span class="env-pill">🍃 미세먼지 {cur_data['dust']}</span>
                </div>
            </div>
        </div>
    """)

    # 7. 하단: 해당 권역의 추천 축제 및 여행 코스 카드 리스트
    fest_list = cur_data.get("festivals", [])
    st.html(f"""
        <div class="section-title-wrap">
            <h2 class="section-main-title">
                <span>🎪</span>
                <span>{active_region}권역 추천 축제 & 1일 힐링 코스</span>
            </h2>
            <span class="section-count-tag">추천 축제 {len(fest_list)}곳</span>
        </div>
    """)

    for idx, fest in enumerate(fest_list):
        f_name = fest["name"]
        f_dates = fest["dates"]
        f_loc = fest["location"]
        f_theme = fest["theme"]
        f_img = fest["image"]
        f_course = fest["course_summary"]
        f_parking = fest["parking_info"]

        # 3단계 코스 HTML
        course_steps_html = []
        for c in f_course:
            course_steps_html.append(f"""
            <div class="step-item-card">
                <div class="step-time-tag">⏰ {c['time']}</div>
                <div class="step-spot-name">{c['spot']}</div>
                <div class="step-spot-desc">{c['desc']}</div>
            </div>
            """)

        st.html(f"""
        <div class="festival-course-card">
            <div class="fest-card-top-grid">
                <div class="fest-img-box">
                    <img src="{f_img}" alt="{f_name}" class="fest-img" loading="lazy" />
                    <span class="fest-theme-badge">{f_theme}</span>
                </div>
                <div class="fest-info-side">
                    <div>
                        <h3 class="fest-title">{f_name}</h3>
                        <div class="fest-meta-item">
                            <span>📅</span>
                            <span>{f_dates}</span>
                        </div>
                        <div class="fest-meta-item">
                            <span>📍</span>
                            <span>{f_loc}</span>
                        </div>
                    </div>

                    <!-- 당일 코스 요약 -->
                    <div class="course-timeline-wrap">
                        <div class="timeline-title">
                            <span>🧭</span>
                            <span>에디터 추천 1일 여행 동선 코스</span>
                        </div>
                        <div class="timeline-steps-grid">
                            {"".join(course_steps_html)}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """)

        # Streamlit Expander: 인근 주차 정보 보기 접기/펼치기
        with st.expander(f"🅿️ '{f_name}' 인근 공영주차장 및 주차 꿀팁 보기", expanded=False):
            st.markdown(f"""
            <div class="parking-detail-box">
                <div class="parking-detail-title">
                    <span>🚘</span>
                    <strong>{f_parking['name']}</strong>
                </div>
                <div style="margin-top:6px; color:#374151;">
                    • <strong>주차 요금:</strong> {f_parking['fee']}<br/>
                    • <strong>주차 면수:</strong> {f_parking['capacity']}<br/>
                    • <strong>현장 꿀팁:</strong> {f_parking['tip']}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.write("")

    st.html("</div>")


if __name__ == "__main__":
    st.set_page_config(page_title="전국 날씨 연동 지역 축제 & 여행 코스", page_icon="🌦️", layout="wide")
    render_weather_festival_curation_page()
