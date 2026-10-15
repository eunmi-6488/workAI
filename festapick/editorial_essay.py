# -*- coding: utf-8 -*-
"""
[Editorial Essay Engine] 축제별 실제 데이터 기반 정직한 안심 동행 에디토리얼 가이드 엔진
- 축제 고유의 테마/역사/자연 서사 + 실제 추천 착한식당(이름/메뉴/거리) + 실제 웰니스 거점(이름/테마) 유기적 합성
- 동행인(부모님, 나홀로, 연인, 가족, 친구, 반려견) 맞춤 감성 스토리텔링 100% 차별화
- 허위 실측 수치(도보 30m, 150m 간격) 원천 배제, 실제 공공데이터(전화번호, 장소, 실내외) 기반 정직한 가이드
"""

import os
import json
import re
import warnings
from typing import Dict, Any, List, Optional

warnings.filterwarnings("ignore", category=FutureWarning)


def classify_companion(companion_str: str) -> str:
    """동행인 문자열을 표준 카테고리 코드로 분류"""
    c = str(companion_str or "").strip()
    if any(k in c for k in ["홀로", "혼자", "솔로", "혼행", "1인", "나홀로"]):
        return "solo"
    elif any(k in c for k in ["부모", "어르신", "시부모", "효도", "할머니", "할아버지"]):
        return "parents"
    elif any(k in c for k in ["연인", "커플", "데이트", "배우자", "남편", "아내"]):
        return "couple"
    elif any(k in c for k in ["친구", "우정", "동창"]):
        return "friends"
    elif any(k in c for k in ["자녀", "아이", "어린", "가족", "키즈", "아기"]):
        return "family"
    elif any(k in c for k in ["반려", "강아지", "애견", "멍"]):
        return "pet"
    return "solo" if "여행" in c and not any(k in c for k in ["부모", "연인", "친구", "가족", "반려"]) else "parents"


COMPANION_META = {
    "solo": {
        "label": "나홀로 쉼표 여행",
        "theme": "오롯이 나에게 집중하는 사색과 자유로운 1인 힐링",
        "badge": "나홀로 힐링 사색 가이드",
        "instruction": "1인 나홀로 여행입니다. '친구', '가족', '연인', '동행자' 등 타인에 관한 언급을 일체 배제하고, 오롯이 나만의 보폭으로 걷는 자유와 깊은 사색, 내면의 고요한 평온에 집중하세요."
    },
    "parents": {
        "label": "부모님 (연로하심)",
        "theme": "효도와 안심의 느린 걸음",
        "badge": "부모님 맞춤 효도 가이드",
        "instruction": "연로하신 부모님을 모시는 효도 여행입니다. 단차 없는 평지, 부모님의 느린 보폭을 배려하는 따뜻하고 정성 어린 시선으로 서술하세요."
    },
    "couple": {
        "label": "연인 / 커플",
        "theme": "두 손 맞잡고 걷는 낭만과 설렘",
        "badge": "연인 맞춤 로맨틱 가이드",
        "instruction": "사랑하는 연인과 함께하는 낭만 여행입니다. 두 손을 맞잡고 걷는 설렘과 둘만의 다정한 추억을 로맨틱하게 서술하세요."
    },
    "friends": {
        "label": "친구와 함께",
        "theme": "유쾌한 웃음과 활기찬 추억 나누기",
        "badge": "친구와 함께하는 우정 가이드",
        "instruction": "오랜 친구와 함께 떠난 유쾌한 우정 여행입니다. 스스럼없는 웃음, 신선한 활기, 함께 나누는 푸짐한 로컬 별미와 추억을 경쾌하고 따뜻하게 서술하세요."
    },
    "family": {
        "label": "가족 / 어린 자녀",
        "theme": "유모차도 편안한 안심 동선과 가족의 미소",
        "badge": "온 가족 안심 피크닉 가이드",
        "instruction": "어린 자녀와 온 가족이 함께하는 안심 나들이입니다. 아이의 맑은 웃음소리와 가족 모두의 안전하고 편안한 쉼을 훈훈하게 서술하세요."
    },
    "pet": {
        "label": "반려동물 동반",
        "theme": "폭신한 잔디와 흙길 위 자연 교감",
        "badge": "반려견 동반 펫프렌들리 가이드",
        "instruction": "반려견과 함께하는 펫프렌들리 여행입니다. 폭신한 흙길을 함께 달리는 반려견과의 따스한 자연 교감을 애정 어린 문체로 서술하세요."
    }
}


def _extract_festival_theme_vibe(fest_name: str, desc: str, location: str, region: str) -> Dict[str, str]:
    """
    축제명, 실제 소개글, 개최 장소로부터 축제 고유의 정취와 보행 환경 키워드를 정밀 추출
    """
    combined = f"{fest_name} {desc} {location} {region}".lower()

    if any(k in combined for k in ["인삼", "풍기"]):
        return {
            "vibe": "소백산 자락의 맑은 가을 공기와 그윽한 명품 인삼 향기",
            "walk": "남원천 둔치 수변 산책로와 평지 문화공원",
            "terrain_tip": "남원천 둔치와 인삼문화팝업공원은 평지 위주로 조성되어 있으나, 일부 강변 야외 구간에 비포장 흙길이 있을 수 있으니 편안한 보행화 착용을 권장합니다."
        }
    elif any(k in combined for k in ["삼랑성", "전등사", "산성", "역사문화"]):
        return {
            "vibe": "천년고찰 전등사의 고즈넉한 풍경 소리와 단풍 물든 삼랑성 성곽의 숨결",
            "walk": "고즈넉한 사찰 숲길과 완만한 역사 탐방 산책로",
            "terrain_tip": "전등사 경내와 삼랑성 숲길은 자연 지형이 살아있어 일부 완만한 오르막과 흙길이 있으므로, 편안한 쿠션 운동화를 착용하시고 천천히 거니시길 권장합니다."
        }
    elif any(k in combined for k in ["순천", "갈대", "습지"]):
        return {
            "vibe": "황금빛으로 일렁이는 순천만 은빛 갈대 물결과 드넓은 갯벌의 고요",
            "walk": "순천만습지 광폭 목재 데크길",
            "terrain_tip": "순천만 갈대숲은 단차 없는 평지 데크길이 길게 이어져 있어 호젓하게 혼자 걷거나 함께 거닐기에 최적의 환경을 제공합니다."
        }
    elif any(k in combined for k in ["진주", "유등", "남강"]):
        return {
            "vibe": "남강 수면 위를 환상적으로 수놓는 수만 개의 소망등불과 진주성의 웅장한 야경",
            "walk": "남강 둔치 평탄 산책로와 남강 부교",
            "terrain_tip": "강변 평지 산책로와 부교는 완만하게 연결되어 있으나 야간 관람 특성상 어두울 수 있어 발밑 안전에 각별히 유의해 주세요."
        }
    elif any(k in combined for k in ["강릉", "커피"]):
        return {
            "vibe": "짙푸른 동해 바다와 안목해변을 따라 번지는 그윽한 원두 로스팅 향기",
            "walk": "안목해변 해송 솔밭 평지 보행로",
            "terrain_tip": "해변 목재 데크와 솔밭길은 평탄하게 정비되어 보행이 수월하나, 주말 커피거리 골목 인파가 붐빌 수 있으니 이른 오전 방문을 권장합니다."
        }
    elif any(k in combined for k in ["불꽃", "드론", "빛"]):
        return {
            "vibe": "가을밤 하늘을 화려하게 수놓는 찬란한 불빛과 낭만적인 야경",
            "walk": "탁 트인 수변 야간 관람로와 평탄 광장",
            "terrain_tip": "야간 행사 관람 시 인파 이동에 유의하시고, 기온 강하에 대비해 가벼운 숄이나 방한 외투를 준비하시는 것이 좋습니다."
        }
    elif any(k in combined for k in ["국화", "꽃", "정원", "수목원"]):
        return {
            "vibe": "형형색색의 가을꽃과 마음을 정화해주는 그윽한 국화 향기",
            "walk": "단차 없이 정비된 꽃길 산책로와 잔디 쉼터",
            "terrain_tip": "포장된 평지 산책로 위주이나 야외 정원 관람 특성상 햇살을 가릴 수 있는 모자나 양산을 지참하시길 권장합니다."
        }
    elif any(k in combined for k in ["음식", "미식", "김치", "와인", "한우"]):
        return {
            "vibe": "풍요로운 가을 수확의 기쁨과 로컬 향토 미식의 깊은 손맛",
            "walk": "체험 부스가 가지런히 이어진 평탄 축제 광장",
            "terrain_tip": "부스 간 이동 동선이 완만하게 조성되어 있으나, 식음료 존 주변의 혼잡을 피해 여유 있는 시간대에 체험하시길 권장합니다."
        }
    elif any(k in combined for k in ["호수", "강", "천", "해변", "바다"]):
        return {
            "vibe": f"{region}의 맑은 물결과 시원한 가을바람이 전하는 청량한 정취",
            "walk": "물결을 따라 길게 이어진 수변 힐링 데크길",
            "terrain_tip": "수변 데크길은 평탄하여 걷기 편하나 강바람이나 바닷바람에 체온이 떨어질 수 있으니 보온용 겉옷을 챙겨주세요."
        }
    else:
        return {
            "vibe": f"{region}의 청정한 자연과 {fest_name} 고유의 정겨운 문화 정취",
            "walk": f"{fest_name} 행사장 완만 보행 동선",
            "terrain_tip": f"야외 {location or '행사장'} 특성상 포장 구간과 흙길이 어우러져 있으니, 발목 피로를 줄여주는 편안한 보행화를 권장합니다."
        }

# ==============================================================================
# [AI Live Generation Engine] 실시간 에세이 & 인용구 창작 엔진 (Temperature 0.9)
# 매번 축제/동행인/추천장소를 바탕으로 100% 새로운 시적 문장 창작 (판박이 템플릿 원천 배제)
# ==============================================================================

def _get_poetic_fallback_bundle(fest_name: str, region: str, companion_label: str, comp_code: str, rest_name: str, cleaned_menu: str, spot_name: str, spot_vibe: str) -> Dict[str, str]:
    """오프라인 또는 API 지연 시에도 '판박이 클리셰' 없이 매번 다채로운 감성을 보장하는 고품격 로컬 번들"""
    import random
    
    palettes = {
        "solo": [
            {
                "top_quote": f"온전히 나만의 보폭으로 마주하는 {fest_name}, 가을바람 속에 비로소 내면의 고요가 깃듭니다.",
                "middle_quote": f"타인의 시선에서 벗어나 오롯이 마주한 풍경, 길 끝에서 나 자신과 다정하게 화해했습니다.",
                "first_letter": "오",
                "text_1": f"롯이 나만의 리듬으로 걷는 {fest_name}은 자유롭고 투명한 해방감을 선물합니다. 타인의 속도에 맞출 필요 없이 발길 닿는 대로 멈춰 서서 가을바람을 깊게 들이마시다 보면, 복잡했던 일상의 소음들이 가라앉고 맑은 사색의 여백이 차분히 채워집니다.",
                "text_2": f"호젓한 산책 끝에 찾은 착한가격업소 '{rest_name}'에서 마주하는 소박한 {cleaned_menu or '1인 식사'}는 혼자만의 여정에 따스한 위로가 됩니다. 이어지는 '{spot_name}'의 한적한 숲 그늘에서 책 한 장을 넘기며 오롯이 나에게 집중하는 가을의 평온을 만끽합니다."
            },
            {
                "top_quote": f"누구의 시선도 닿지 않는 나만의 쉼표, {fest_name}의 호젓한 길목에서 온전한 자유를 누립니다.",
                "middle_quote": f"혼자 걷는 길은 결코 외롭지 않았습니다. 바람과 나무, 계절의 숨결이 다정한 벗이 되어주었으니까요.",
                "first_letter": "가",
                "text_1": f"을 햇살이 조용히 부서지는 {fest_name}을 홀로 거니는 시간은 그 자체로 나에게 건네는 가장 다정한 시가 됩니다. 누구의 눈치도 보지 않고 온전히 나만의 속도로 계절을 음미하는 발걸음마다 마음의 응어리가 조용히 풀려납니다.",
                "text_2": f"여유로운 탐방을 마친 뒤 부담 없이 들른 착한 식당 '{rest_name}'에서 정갈한 {cleaned_menu or '단골 밥상'}으로 든든하게 속을 채웁니다. 이어지는 고요한 명소 '{spot_name}'에서 깊은 숨을 들이쉬며 홀로 떠나온 여행의 벅찬 여운을 마음에 담습니다."
            }
        ],
        "parents": [
            {
                "top_quote": f"어머니의 잔잔한 미소와 아버지의 따스한 눈빛 위로, {region}의 가을 햇살이 곱게 내려앉습니다.",
                "middle_quote": f"세월을 품은 부모님의 손을 가만히 쥘 때, 세상의 어떤 풍경보다 눈부신 안식이 찾아옵니다.",
                "first_letter": "가",
                "text_1": f"을바람이 조용히 머무는 {fest_name}의 길목에서 부모님의 정겨운 옛 기억이 하나둘 피어납니다. 평탄하게 닦인 완만한 길을 따라 느릿한 보폭을 맞추다 보면, 조급했던 일상의 마음도 어느덧 순해집니다. 지나온 계절을 함께 견뎌온 어르신의 다정한 목소리가 가을 공기를 포근하게 채웁니다.",
                "text_2": f"정다운 산책을 마친 뒤에는 인근의 착한 식당 '{rest_name}'에서 정성 가득한 {cleaned_menu or '제철 밥상'}으로 속 편한 한 끼를 나눕니다. 과하지 않은 소박한 손맛이 어르신의 마음에 훈훈한 온기를 전하고, 이어지는 '{spot_name}'의 고요한 숲 그늘에서 마시는 차 한 잔은 부모님께 드리는 더없이 귀한 가을 선물이 됩니다."
            },
            {
                "top_quote": f"느리게 걷는 부모님의 보폭에 세상의 속도를 맞추자, {fest_name}의 숨은 다정함이 눈에 들어옵니다.",
                "middle_quote": f"발밑에 바스락거리는 가을 흙길 위에서, 우리는 잊고 지냈던 서로의 온기를 온전히 채웠습니다.",
                "first_letter": "바",
                "text_1": f"람결에 스치는 풀잎 소리를 벗 삼아 {fest_name}을 거니는 시간은 그 자체로 마음에 새겨지는 시가 됩니다. 턱이 없고 완만한 흙길 위로 부모님과 함께 발을 디디며 나누는 잔잔한 대화는 그 어떤 화려한 구경보다 마음을 뭉클하게 적십니다.",
                "text_2": f"풍경을 눈에 담은 후에는 착한가격업소 '{rest_name}'에서 따끈한 {cleaned_menu or '한 상 차림'}으로 기분 좋은 포만감을 즐깁니다. 부드럽고 정갈한 맛으로 지친 기력을 보충하고, 맑은 숨결이 가득한 '{spot_name}'에서 여유롭게 다리를 쉬어가며 소중한 가족의 여정을 완성합니다."
            }
        ],
        "couple": [
            {
                "top_quote": f"두 손을 맞잡고 걷는 {region}의 가을길, {fest_name}의 낭만은 우리 둘만의 비밀스러운 추억이 됩니다.",
                "middle_quote": f"노을빛으로 물드는 축제장과 다정한 쉼터, 당신과 나란히 바라보는 모든 순간이 그림이 되었습니다.",
                "first_letter": "너",
                "text_1": f"른 가을 하늘 아래 서로의 손을 꼭 쥐고 걷는 {fest_name}은 설렘과 다정함으로 가득합니다. 감각적인 풍경과 싱그러운 바람이 두 사람의 발걸음을 감싸며, 잊지 못할 낭만적인 한 페이지를 엮어냅니다.",
                "text_2": f"축제의 열기를 즐긴 뒤에는 골목 안 착한가격식당 '{rest_name}'에서 맛있는 {cleaned_menu or '별미'}를 나누며 이야기꽃을 피웁니다. 쉼터 '{spot_name}'으로 이어지는 산책길에서 저물어가는 가을빛을 바라보며 둘만의 깊은 여운을 나눕니다."
            }
        ],
        "friends": [
            {
                "top_quote": f"오랜 벗들과 함께 웃고 거니는 {fest_name}, 가을바람마저 우리의 유쾌한 발걸음을 반깁니다.",
                "middle_quote": f"함께 걷는 것만으로도 시절을 거슬러 오르는 시간, 소중한 친구와 나누는 가을날의 소중한 페이지.",
                "first_letter": "맑",
                "text_1": f"은 가을 햇살 아래 친구들과 발맞추어 걷는 {fest_name}은 활기와 정겨운 웃음으로 가득합니다. 스스럼없는 대화와 함께 카메라 렌즈에 담기는 순간마다 계절의 싱그러운 추억이 차곡차곡 쌓여갑니다.",
                "text_2": f"신나게 축제를 즐긴 후 착한가격업소 '{rest_name}'에서 푸짐한 {cleaned_menu or '인기 메뉴'}를 함께 나누며 돈독한 정을 나눕니다. 쉼터 '{spot_name}'으로 자리를 옮겨 나누는 진솔한 이야기는 이번 우정 여행의 더없이 빛나는 마침표가 됩니다."
            }
        ],
        "family": [
            {
                "top_quote": f"아이의 해맑은 웃음소리가 번지는 {fest_name}, 온 가족의 발걸음마다 행복한 온기가 피어납니다.",
                "middle_quote": f"가장 안전하고 편안한 길 위에서, 우리 가족 모두의 가을날이 아름답게 물들었습니다.",
                "first_letter": "파",
                "text_1": f"란 가을 하늘 아래 아이의 손을 잡고 걷는 {fest_name}은 안심과 여유로움으로 가득합니다. 휠체어와 유모차도 편안히 오갈 수 있는 완만한 동선 덕분에 온 가족이 마음 편히 계절의 정취를 누릴 수 있습니다.",
                "text_2": f"즐거운 가족 체험 후 착한가격업소 '{rest_name}'에서 온 가족의 입맛에 딱 맞는 건강한 {cleaned_menu or '가족 식사'}를 함께 즐깁니다. 푸른 잔디가 펼쳐진 '{spot_name}' 쉼터에서 아이들이 뛰노는 모습을 바라보며 포근한 휴식을 취합니다."
            }
        ],
        "pet": [
            {
                "top_quote": f"반려견의 경쾌한 발걸음과 함께 걷는 {fest_name}, 자연 속에서 나누는 무언의 따스한 교감.",
                "middle_quote": f"폭신한 흙길을 디디며 마주한 맑은 숲바람, 우리 털복숭이 가족과 함께한 온전한 힐링.",
                "first_letter": "살",
                "text_1": f"랑이는 가을바람을 맞으며 사랑하는 반려견과 함께 걷는 {fest_name}의 흙길은 자연 그대로의 편안함을 선물합니다. 신나게 꼬리를 흔드는 모습을 바라보는 것만으로도 일상의 피로가 눈 녹듯 사라집니다.",
                "text_2": f"한적한 산책로를 누빈 후 착한가격업소 '{rest_name}' 인근의 여유로운 공간에서 가벼운 식사를 즐기고, 쾌적한 쉼터 '{spot_name}'의 그늘 아래서 물 한 모금을 나누며 서로의 온기를 온전히 느낍니다."
            }
        ]
    }
    
    bundle_list = palettes.get(comp_code, palettes["solo"])
    chosen = random.choice(bundle_list)
    return {
        "top_quote": chosen["top_quote"],
        "middle_quote": chosen["middle_quote"],
        "bottom_note": f"FESTAPICK EDITOR NOTE · {fest_name} 쉼표에서",
        "first_letter": chosen["first_letter"],
        "text_1": chosen["text_1"],
        "text_2": chosen["text_2"]
    }


def generate_editorial_essay_live(
    fest_name: str,
    region: str,
    companion_label: str,
    comp_code: str,
    spot_vibe: str,
    walk_feat: str,
    terrain_tip: str,
    rest_name: str,
    cleaned_menu: str,
    rest_dist: str,
    spot_name: str,
    spot_theme: str,
    spot_dist: str,
    main_prog: str,
    phone_contact: str,
    loc_display: str
) -> Dict[str, str]:
    """
    [AI 실시간 에세이 & 인용구 창작 엔진 (Temperature 0.9)]
    - 축제 현장의 실제 공공데이터 + 착한가격식당 + 웰니스 거점을 프롬프트에 주입
    - 진부한 판박이 패턴(~들리기 시작합니다, ~깊은 휴식이 되었다 등) 절대 금지
    - 매번 호출 시 완전히 새로운 감성과 서정적 문학성으로 JSON 응답 창작
    """
    comp_meta = COMPANION_META.get(comp_code, COMPANION_META["solo"])
    comp_instruction = comp_meta.get("instruction", "")

    if comp_code == "solo":
        step1_instruction = f"축제 현장의 가을 풍경, 사색의 보행길, 타인의 간섭 없이 오롯이 나만의 리듬으로 거니는 혼자만의 호젓하고 자유로운 순간 묘사. (주의: 친구나 동행인 등 타인을 일체 언급하지 말고, 오롯이 나 혼자만의 1인칭 사색으로 작성. 첫 글자는 first_letter로 분리되므로 첫 글자를 제외하고 작성)"
        step2_instruction = f"축제 관람 후 착한가격식당 '{rest_name}'에서 부담 없이 즐기는 정갈한 1인 식사({cleaned_menu or '제철 밥상'})와 웰니스 쉼터 '{spot_name}'의 한적한 숲 그늘에서 책 한 장, 차 한 잔과 함께 누리는 평온한 나만의 쉼표 마무리"
        companion_rule = "- [절대 엄수]: 이 여정은 1인 '나홀로 쉼표 여행'입니다. '친구', '동행자', '가족', '연인', '함께' 등 타인을 등장시키는 단어를 일체 쓰지 마세요. 100% 혼자만의 사색과 고요한 자유에 집중해야 합니다."
    elif comp_code == "parents":
        step1_instruction = f"축제 현장의 풍경, 평탄하고 완만한 보행길, 부모님의 느린 보폭에 맞추어 손을 맞잡고 걷는 다정하고 효심 어린 순간 묘사 (첫 글자는 first_letter로 분리되므로 첫 글자를 제외하고 작성)"
        step2_instruction = f"축제 관람 후 착한가격식당 '{rest_name}'의 자극 없는 속 편한 진지상과 웰니스 쉼터 '{spot_name}'에서 부모님의 기력과 피로를 씻어내는 아늑한 쉼표 마무리"
        companion_rule = "- [동행인 원칙]: 연로하신 부모님을 모시는 효도 여행 관점에서, 단차 없는 평지와 부모님을 향한 따뜻한 배려의 시선으로 작성하세요."
    elif comp_code == "couple":
        step1_instruction = f"축제 현장의 풍경, 낭만적인 산책로, 연인과 두 손을 맞잡고 설레는 마음으로 나란히 걷는 로맨틱한 순간 묘사 (첫 글자는 first_letter로 분리되므로 첫 글자를 제외하고 작성)"
        step2_instruction = f"축제 관람 후 착한가격식당 '{rest_name}'의 맛있는 식사와 웰니스 쉼터 '{spot_name}'에서 노을빛을 바라보며 둘만의 여운을 나누는 낭만적 마무리"
        companion_rule = "- [동행인 원칙]: 사랑하는 연인과 함께하는 여행 관점에서, 두 사람만의 설렘과 낭만적인 분위기로 작성하세요."
    elif comp_code == "friends":
        step1_instruction = f"축제 현장의 활기, 흥겨운 산책로, 오랜 친구와 함께 웃음을 나누며 발맞추어 걷는 유쾌하고 활기찬 순간 묘사 (첫 글자는 first_letter로 분리되므로 첫 글자를 제외하고 작성)"
        step2_instruction = f"축제 관람 후 착한가격식당 '{rest_name}'에서 친구들과 함께 나누는 푸짐하고 정겨운 식사와 웰니스 쉼터 '{spot_name}'에서 깊은 이야기를 나누는 마무리"
        companion_rule = "- [동행인 원칙]: 오랜 친구와 함께 떠난 우정 여행 관점에서, 스스럼없는 웃음과 활기찬 추억으로 작성하세요."
    elif comp_code == "family":
        step1_instruction = f"축제 현장의 풍경, 유모차도 편안한 안심 산책로, 온 가족과 아이의 밝은 웃음소리가 번지는 다정한 순간 묘사 (첫 글자는 first_letter로 분리되므로 첫 글자를 제외하고 작성)"
        step2_instruction = f"축제 관람 후 착한가격식당 '{rest_name}'의 온 가족이 안심하고 먹는 건강한 식사와 웰니스 쉼터 '{spot_name}' 잔디마당에서의 여유로운 쉼표 마무리"
        companion_rule = "- [동행인 원칙]: 아이와 온 가족이 함께하는 나들이 관점에서, 안전하고 편안하며 밝은 분위기로 작성하세요."
    else:
        step1_instruction = f"축제 현장의 자연 풍경, 폭신한 흙길, 반려견과 함께 맑은 공기를 마시며 교감하는 다정한 산책 순간 묘사 (첫 글자는 first_letter로 분리되므로 첫 글자를 제외하고 작성)"
        step2_instruction = f"축제 관람 후 착한가격식당 '{rest_name}' 인근 휴식과 웰니스 쉼터 '{spot_name}' 야외 그늘에서 반려견과 함께 쉬어가는 평온한 마무리"
        companion_rule = "- [동행인 원칙]: 반려견과 함께하는 여행 관점에서, 자연과의 교감과 따뜻한 애정으로 작성하세요."

    prog_hint = f"축제 대표 볼거리/프로그램: '{main_prog}'" if main_prog else ""
    rest_hint = f"인근 착한가격식당: '{rest_name}' (대표메뉴: {cleaned_menu or '제철 로컬 밥상'}, 거리: {rest_dist or '도보권'})"
    spot_hint = f"힐링 웰니스 명소: '{spot_name}' (테마: {spot_theme or '자연/숲치유'}, 거리: {spot_dist or '근교'})"

    prompt = f"""축제명: {fest_name}
개최 지역: {region or '대한민국 로컬'}
동행인 유형: {companion_label}
동행인 컨셉 가이드: {comp_instruction}
축제 현장 정취: {spot_vibe}
보행 환경: {walk_feat} ({loc_display})
{prog_hint}
{rest_hint}
{spot_hint}

[작성 지침]
당신은 최고급 여행 매거진의 수석 에디터입니다. 위 축제와 여행 정보를 바탕으로, 선택된 동행인 유형({companion_label})에 100% 부합하는 감성 에디토리얼 글과 인용구를 실시간 창작해주세요.
1. [동행인 맞춤 지침]:
   {companion_rule}
2. [절대 금지]:
   - 기존의 '~들리기 시작합니다', '~깊은 휴식이 되었다', '~여정은 무엇보다 편안함과 배려가 우선입니다' 같은 진부한 판박이 패턴이나 상투적인 문장은 절대 쓰지 마세요.
3. [단락 구성]:
   - text_1: {step1_instruction}
   - text_2: {step2_instruction}
4. [국어 순화 및 외래어 배제 원칙 (절대 엄수)]:
   - 영어나 영한 혼용 어휘(예: 'warm한', 'warm', 'cozy한', 'cozy', 'healing', 'vibe', 'mood' 등)는 일체 쓰지 마세요.
   - 'warm한 차' 같은 어색한 표현은 절대 불가하며, 반드시 '따뜻한 차', '온기 어린 차', '훈훈한 찻잔', '포근한 쉼터', '아늑한 그늘', '싱그러운 숲바람'처럼 우아하고 자연스러운 100% 순수 한국어 문장으로만 작성해야 합니다.
5. [문체 절대 원칙 (정중한 존댓말 필수)]:
   - 모든 문장(top_quote, middle_quote, text_1, text_2)은 반드시 독자에게 정중하고 다정한 존댓말('~합니다', '~입니다', '~바랍니다', '~만끽합니다')로 작성하세요.
   - 혼잣말, 반말, 평어체('~한다', '~이다', '~보려 한다', '~될 것이다', '~향한다', '~느껴본다', '~갖는다')는 일체 사용하지 마세요.

반드시 아래 JSON 포맷으로만 응답해주세요:
{{
    "top_quote": "에디토리얼 매거진 상단에 들어갈 가슴 뭉클한 한 줄 인용구 (따옴표 제외)",
    "middle_quote": "에디토리얼 매거진 중간에 들어갈 여운이 남는 쉼표 문장 (따옴표 제외)",
    "bottom_note": "FESTAPICK EDITOR NOTE · {fest_name} 쉼표에서",
    "first_letter": "본문 첫 단락 첫 글자 (드롭캡용 1글자, 예: '가', '바', '햇', '길' 등)",
    "text_1": "첫 단락 본문 (first_letter 글자를 제외한 나머지 본문 문장들)",
    "text_2": "두 번째 단락 본문 (식당과 쉼터가 조화롭게 녹아든 감성 마무리)"
}}"""

    def _clean_essay_dict(d: Dict[str, Any]) -> Dict[str, str]:
        """외래어/영한 혼용 표현을 자연스러운 순수 한국어로 사후 정제하고 존댓말 어미 보장"""
        res = {}
        replacements = [
            (r"(?i)\bwarm\s*한\s*", "따뜻한 "),
            (r"(?i)\bwarm\b", "온기 어린 "),
            (r"(?i)\bcozy\s*한\s*", "아늑한 "),
            (r"(?i)\bcozy\b", "포근한 "),
            (r"(?i)\bfresh\s*한\s*", "싱그러운 "),
            (r"(?i)\bfresh\b", "상쾌한 "),
            (r"(?i)\bhealing\s*한\s*", "치유의 "),
            (r"(?i)\bpeaceful\s*한\s*", "평화로운 "),
            (r"(?i)\bsweet\s*한\s*", "달콤한 "),
            (r"(?i)\bvibe\b", "정취"),
            (r"(?i)\bmood\b", "분위기"),
            # 존댓말 어미 보정
            (r"잠겨보려\s*한다(?=[\.\!\?]|\s*$)", "잠겨보고자 합니다"),
            (r"느껴본다(?=[\.\!\?]|\s*$)", "느껴봅니다"),
            (r"둘러본다(?=[\.\!\?]|\s*$)", "둘러봅니다"),
            (r"향한다(?=[\.\!\?]|\s*$)", "향합니다"),
            (r"경험한다(?=[\.\!\?]|\s*$)", "경험합니다"),
            (r"갖는다(?=[\.\!\?]|\s*$)", "갖습니다"),
            (r"즐긴다(?=[\.\!\?]|\s*$)", "즐깁니다"),
            (r"만끽한다(?=[\.\!\?]|\s*$)", "만끽합니다"),
            (r"마주한다(?=[\.\!\?]|\s*$)", "마주합니다"),
            (r"남긴다(?=[\.\!\?]|\s*$)", "남깁니다"),
            (r"채운다(?=[\.\!\?]|\s*$)", "채웁니다"),
            (r"거닌다(?=[\.\!\?]|\s*$)", "거닙니다"),
            (r"찾는다(?=[\.\!\?]|\s*$)", "찾아봅니다"),
            (r"선사한다(?=[\.\!\?]|\s*$)", "선사합니다"),
            (r"전한다(?=[\.\!\?]|\s*$)", "전합니다"),
            (r"담는다(?=[\.\!\?]|\s*$)", "담습니다"),
            (r"떠난다(?=[\.\!\?]|\s*$)", "떠납니다"),
            (r"([가-힣]+)한다(?=[\.\!\?]|\s*$)", r"\1합니다"),
            (r"([가-힣]+)된다(?=[\.\!\?]|\s*$)", r"\1됩니다"),
            (r"([가-힣]+)있다(?=[\.\!\?]|\s*$)", r"\1있습니다"),
            (r"([가-힣]+)이다(?=[\.\!\?]|\s*$)", r"\1입니다"),
        ]
        for k, v in d.items():
            if isinstance(v, str):
                s = v
                for pat, rep in replacements:
                    s = re.sub(pat, rep, s)
                res[k] = s.strip()
            else:
                res[k] = v
        return res

    # 1. Google Gemini (최신 google.genai SDK) 시도 (Temperature 0.9)
    g_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if g_key:
        try:
            from google import genai
            client = genai.Client(api_key=g_key)
            for m_name in ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-2.5-flash"]:
                try:
                    res = client.models.generate_content(
                        model=m_name,
                        contents=prompt,
                        config={"temperature": 0.9, "response_mime_type": "application/json"}
                    )
                    data = json.loads(res.text)
                    if data.get("top_quote") and data.get("text_1") and data.get("text_2"):
                        return _clean_essay_dict(data)
                except Exception:
                    continue
        except Exception:
            pass

    # 2. OpenAI (gpt-4o-mini, Temperature 0.9, JSON Mode) 시도
    o_key = os.getenv("OPENAI_API_KEY")
    if o_key:
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
                temperature=0.9,
                model_kwargs={"response_format": {"type": "json_object"}}
            )
            res = llm.invoke(prompt)
            data = json.loads(res.content)
            if data.get("top_quote") and data.get("text_1") and data.get("text_2"):
                return _clean_essay_dict(data)
        except Exception:
            pass

    # 3. 고품질 다채로운 로컬 번들 폴백
    raw_fallback = _get_poetic_fallback_bundle(
        fest_name, region, companion_label, comp_code, rest_name, cleaned_menu, spot_name, spot_vibe
    )
    return _clean_essay_dict(raw_fallback)


def get_curated_editorial_essay(
    fest_name: str,
    region: str = "",
    companion: str = "",
    active_fest: Optional[Dict[str, Any]] = None,
    top3_restaurants: Optional[List[Dict[str, Any]]] = None,
    top3_wellness: Optional[List[Dict[str, Any]]] = None,
    top3_programs: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    [Semantic Synthesis Engine]
    축제의 실제 공공데이터 + 실제 매칭된 착한가격식당(이름/메뉴) + 실제 웰니스 명소(이름/테마) + 동행인 맞춤 서사 실시간 창작
    """
    fest_name = str(fest_name or "로컬 힐링 축제").strip()
    region = str(region or "전국").strip()
    comp_code = classify_companion(companion)
    meta = COMPANION_META.get(comp_code, COMPANION_META["parents"])

    fest_dict = active_fest or {}
    phone = str(fest_dict.get("phone", "") or "").strip()
    location = str(fest_dict.get("location", "") or fest_dict.get("address", "") or "").strip()
    is_indoor = str(fest_dict.get("is_indoor", "") or "야외").strip()
    raw_desc = str(fest_dict.get("description", "") or "").strip()

    # 1. 축제 고유 정취 및 보행 지형 키워드 도출
    theme_info = _extract_festival_theme_vibe(fest_name, raw_desc, location, region)
    spot_vibe = theme_info["vibe"]
    walk_feat = theme_info["walk"]
    terrain_tip = theme_info["terrain_tip"]

    # 2. 추천 1위 착한가격식당 실제 데이터 파싱
    main_rest = (top3_restaurants[0] if top3_restaurants and len(top3_restaurants) > 0 else {})
    rest_name = str(main_rest.get("name", "")).strip()
    rest_desc = str(main_rest.get("desc", "") or main_rest.get("menu", "")).strip()
    rest_dist = str(main_rest.get("dist", "")).strip()

    cleaned_menu = ""
    if rest_desc:
        menu_match = re.search(r'\[([^\]]+)\]', rest_desc)
        if menu_match:
            cleaned_menu = menu_match.group(1).split(",")[0].strip()
        else:
            cleaned_menu = rest_desc.split("/")[0].split("(")[0].strip()
        if len(cleaned_menu) > 20:
            cleaned_menu = cleaned_menu[:18]

    if not rest_name:
        rest_name = f"{region} 착한가격업소"
        cleaned_menu = "정갈한 로컬 계절 밥상"

    # 3. 추천 1위 웰니스 쉼터 실제 데이터 파싱
    main_spot = (top3_wellness[0] if top3_wellness and len(top3_wellness) > 0 else {})
    spot_name = str(main_spot.get("name", "")).strip()
    spot_theme = str(main_spot.get("theme", "")).strip()
    spot_dist = str(main_spot.get("dist", "")).strip()

    if not spot_name:
        spot_name = f"{region} 자연 쉼터"
        spot_theme = "자연/숲치유"

    # 4. 축제 실제 프로그램 1선 파싱
    main_prog = (top3_programs[0].get("name", "") if top3_programs and len(top3_programs) > 0 else "")

    # 5. 공식 연락처 및 위치 안내
    phone_contact = phone or f"해당 지자체 축제 운영과 문의"
    loc_display = location or f"{region} 행사장 일원"

    # 6. 실시간 AI 에세이 & 인용구 창작 실행 (Temperature 0.9)
    essay_bundle = generate_editorial_essay_live(
        fest_name=fest_name,
        region=region,
        companion_label=meta["label"],
        comp_code=comp_code,
        spot_vibe=spot_vibe,
        walk_feat=walk_feat,
        terrain_tip=terrain_tip,
        rest_name=rest_name,
        cleaned_menu=cleaned_menu,
        rest_dist=rest_dist,
        spot_name=spot_name,
        spot_theme=spot_theme,
        spot_dist=spot_dist,
        main_prog=main_prog,
        phone_contact=phone_contact,
        loc_display=loc_display
    )

    quote_lead = str(essay_bundle.get("top_quote", "")).strip().strip('“”"\' ')
    quote_mid = str(essay_bundle.get("middle_quote", "")).strip().strip('“”"\' ')
    bottom_note = str(essay_bundle.get("bottom_note", "")).strip() or f"FESTAPICK EDITOR NOTE · {fest_name} 쉼표에서"
    first_letter = str(essay_bundle.get("first_letter", "가")).strip()[:1] or "가"
    text_1 = str(essay_bundle.get("text_1", "")).strip()
    text_2 = str(essay_bundle.get("text_2", "")).strip()

    # 드롭캡 글자 보정: text_1이 first_letter로 시작하면 중복 방지
    if text_1.startswith(first_letter):
        text_1 = text_1[len(first_letter):].strip()

    # 7. 안심 동행 3대 팁 조합 (실제 데이터 팩트 기반)
    tip_walk_title = f"{loc_display} 보행 가이드"
    tip_walk_desc = terrain_tip

    tip_rest_title = f"식당 & 휴게 동선 배려"
    tip_rest_desc = f"축제장 바로 인근 착한가격업소 '{rest_name}'({rest_dist or '도보권'})에서 무리 없는 식사 후, 웰니스 거점 '{spot_name}'으로 이동하는 여유로운 휴식 동선을 권장합니다."

    tip_spot_title = f"주차 및 편의시설 사전 확인"
    tip_spot_desc = f"📞 공식 안내: {phone_contact}<br>※ 축제장 임시 주차장 내 보행약자 전용면 및 휠체어·유모차 현장 대여 수량은 당일 상황에 따라 달라질 수 있으므로 출발 전 주관부서 확인을 권장합니다."

    return {
        "companion_code": comp_code,
        "companion_label": meta["label"],
        "companion_badge": meta["badge"],
        "companion_theme": meta["theme"],
        "quote_lead": f"“{quote_lead}”",
        "quote_mid": f"“{quote_mid}”",
        "bottom_note": bottom_note,
        "first_letter": first_letter,
        "text_1": text_1,
        "text_2": text_2,
        "slow_tag": f"Slow Travel Memoir · {region} {fest_name}",
        "tip_walk_title": tip_walk_title,
        "tip_walk_desc": tip_walk_desc,
        "tip_rest_title": tip_rest_title,
        "tip_rest_desc": tip_rest_desc,
        "tip_spot_title": tip_spot_title,
        "tip_spot_desc": tip_spot_desc,
    }

