# -*- coding: utf-8 -*-
"""
[Audio Docent Engine] 에디토리얼 에세이 맞춤형 오디오 도슨트(나레이션) 플레이어 모듈
- 축제 종류에 구애받지 않는 '올라운드(범용) 감성 대본' 5종 매핑
- 혼자 / 가족 / 친구 / 커플 / 반려동물 맞춤형 대본 및 정적 음원 바인딩
- 실시간 축제 맞춤형 프롬프트 설계 지원
"""

import os
import base64
from typing import Optional

try:
    import streamlit as st
except ImportError:
    st = None

# 축제 종류에 구애받지 않는 '올라운드(범용) 감성 대본' 6종
# 순서: ["혼자", "부모님", "가족", "커플", "친구", "반려동물"]
GUIDE_DATA = {
    "혼자": {
        "title": "오롯이 나를 만나는 고요한 쉼표 가이드 (약 42초)",
        "audio_path": "audio/solo.mp3",
        "script": """잠시 화면에서 시선을 떼고, 편안하게 눈을 감아보세요.
페스타픽이 제안하는 쉼표 여정, 에디터의 감성 가이드와 함께 천천히 머물러봅니다.

세상의 분주한 소음은 잠시 내려두고, 오롯이 나만의 호흡과 리듬에 귀를 기울여보세요.
눈앞에 펼쳐진 축제의 풍경 속에서, 타인의 시선이나 간섭 없이 나만의 깊은 여유를 마주합니다.
바쁜 일상에 쫓기던 마음이 비워지고, 그 빈자리마다 온전한 평온과 영감이 차오릅니다.

오늘 이 시간만큼은 세상의 속도가 아닌, 당신만의 속도로 즐겨보세요.
페스타픽과 함께하는 이 순간이 마음에 따뜻한 쉼표가 되기를 바랍니다."""
    },
    "부모님": {
        "title": "부모님과 함께하는 다정한 효도 쉼표 가이드 (약 42초)",
        "audio_path": "audio/parents.mp3",
        "script": """잠시 화면에서 시선을 떼고, 부모님의 편안한 숨결과 느긋한 발걸음에 귀 기울여보세요.
페스타픽이 제안하는 쉼표 여정, 에디터의 감성 가이드와 함께 천천히 발을 맞춰봅니다.

늘 앞장서 우리를 이끌어주시던 부모님의 손을 잡고, 이제는 우리가 그 걸음에 보폭을 맞추어 걷습니다.
축제의 활기 속에서도 번잡하지 않은 아늑한 풍경을 마주하며,
평소 쑥스러워 마음에만 담아두었던 고마움과 다정한 진심들이 잔잔하게 오갑니다.

오늘 이 시간만큼은 세상의 빠른 속도는 잊어두고, 부모님의 편안한 쉼과 미소에만 집중해 보세요.
페스타픽과 함께하는 이 순간이 부모님의 마음에 오래도록 따뜻하고 든든한 쉼표가 되기를 바랍니다."""
    },
    "가족": {
        "title": "온 가족이 함께 에디터의 감성 가이드 (약 42초)",
        "audio_path": "audio/family.mp3",
        "script": """잠시 화면에서 시선을 떼고, 곁에 있는 소중한 사람들의 표정을 바라보세요.
페스타픽이 제안하는 따뜻한 여정, 에디터의 감성 가이드와 함께 천천히 걸어가 봅니다.

바쁜 일상 속에선 미처 나누지 못했던 다정한 눈맞춤과 소소한 웃음들이 피어납니다.
서로의 발걸음에 보폭을 맞추며 걷는 이 시간 속에서,
함께 머무는 온기만으로도 마음속 빈자리가 든든하게 채워집니다.

오늘 이 시간만큼은 서두르지 말고, 우리 가족만의 다정한 속도로 즐겨보세요.
페스타픽과 함께하는 이 순간이 사랑하는 이들에게 오래도록 머무는 기억이 되기를 바랍니다."""
    },
    "커플": {
        "title": "너와 나, 둘만의 낭만 가이드 (약 42초)",
        "audio_path": "audio/couple.mp3",
        "script": """잠시 화면에서 시선을 떼고, 맞잡은 손끝의 따스한 온기를 느껴보세요.
페스타픽이 제안하는 낭만 여정, 에디터의 감성 가이드와 함께 나란히 머물러봅니다.

복잡한 일상의 소음은 저 멀리 물러나고, 오직 서로의 목소리와 눈빛만이 선명해집니다.
눈앞에 반짝이는 축제의 장면들 속에서, 둘만의 나직한 이야기들이 겹겹이 쌓여가며
메말랐던 마음에 포근한 설렘과 다정한 평온이 차오릅니다.

오늘 이 시간만큼은 다른 누구도 아닌, 우리 둘만의 속도로 이 순간을 즐겨보세요.
페스타픽과 함께하는 이 순간이 두 사람의 마음에 오래도록 번지는 로맨틱한 쉼표가 되기를 바랍니다."""
    },
    "친구": {
        "title": "우리들의 빛나는 계절, 감성 가이드 (약 42초)",
        "audio_path": "audio/friend.mp3",
        "script": """잠시 화면에서 시선을 떼고, 함께 나누는 유쾌한 웃음소리에 귀 기울여보세요.
페스타픽이 제안하는 설레는 여정, 에디터의 감성 가이드와 함께 출발해 봅니다.

반복되던 일상의 무게는 잠시 털어내고, 우리만의 리듬으로 축제의 활기 속을 누벼봅니다.
눈만 마주쳐도 터져 나오는 이야기와 프레임마다 담기는 반짝이는 순간들이
지친 일상에 다시 나아갈 생생한 에너지를 채워줍니다.

오늘 이 시간만큼은 세상의 기준에서 벗어나, 가장 우리다운 즐거움으로 채워보세요.
페스타픽과 함께하는 이 순간이 두고두고 꺼내볼 빛나는 한 페이지가 되기를 바랍니다."""
    },
    "반려동물": {
        "title": "소중한 털뭉치와 함께하는 힐링 가이드 (약 42초)",
        "audio_path": "audio/pet.mp3",
        "script": """잠시 화면에서 시선을 떼고, 곁에서 경쾌하게 움직이는 작은 발걸음을 바라보세요.
페스타픽이 제안하는 다정한 동행, 에디터의 감성 가이드와 함께 발맞춰봅니다.

복잡한 고민은 잠시 내려두고, 호기심 가득 찬 맑은 눈망울과 따스한 숨결에 집중해 보세요.
말하지 않아도 전해지는 순수한 온기 속에서, 불필요한 긴장은 흩어지고
지친 마음에 몽글몽글한 행복과 무해한 위로가 가득 차오릅니다.

오늘 이 시간만큼은 세상의 바쁜 시계 대신, 우리 아이의 편안한 발걸음에 맞춰 즐겨보세요.
페스타픽과 함께하는 이 순간이 둘 사이에 가장 따뜻한 교감의 쉼표가 되기를 바랍니다."""
    }
}
GUIDE_DATA["연인"] = GUIDE_DATA["커플"]
GUIDE_DATA["효도"] = GUIDE_DATA["부모님"]


def compose_live_docent_prompt(festival_name: str, companion_type: str) -> str:
    """
    [실시간 축제 맞춤형 프롬프트 설계 함수]
    """
    return f"""당신은 여행 도슨트 에디터입니다.
축제 이름: {festival_name}
동행자 유형: {companion_type}
위 정보를 바탕으로, 해당 축제의 매력과 동행자의 정서가 어우러지는 3줄 감성 오디오 가이드 대본을 작성해줘."""


def resolve_companion_key(companion_label: str) -> str:
    comp_str = str(companion_label or "").strip()
    if any(k in comp_str for k in ["혼자", "홀로", "솔로", "1인", "사색"]):
        return "혼자"
    elif any(k in comp_str for k in ["부모", "어르신", "효도", "시부모"]):
        return "부모님"
    elif any(k in comp_str for k in ["가족", "자녀", "아이"]):
        return "가족"
    elif any(k in comp_str for k in ["커플", "연인", "데이트", "둘만"]):
        return "커플"
    elif any(k in comp_str for k in ["친구", "우정"]):
        return "친구"
    elif any(k in comp_str for k in ["반려", "강아지", "애견", "털뭉치"]):
        return "반려동물"
    else:
        return "혼자"


def get_docent_intro_audio_bytes(target_festival_name: str = "", companion_label: str = "혼자", custom_mp3_path: Optional[str] = None) -> Optional[bytes]:
    """
    [동행인별 정적 음원 바이트 탐색 및 반환]
    """
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(cur_dir)

    comp_key = resolve_companion_key(companion_label)
    guide_info = GUIDE_DATA.get(comp_key, GUIDE_DATA["혼자"])
    rel_audio_path = guide_info.get("audio_path", "audio/solo.mp3")

    candidate_paths = [
        custom_mp3_path,
        os.path.join(root_dir, rel_audio_path),
        os.path.join(cur_dir, os.path.basename(rel_audio_path)),
        os.path.join(root_dir, "festapick", rel_audio_path),
        os.path.join(root_dir, "assets", rel_audio_path),
        os.path.join(root_dir, "audio", f"{comp_key}.mp3"),
    ]

    for p in candidate_paths:
        if p and os.path.isfile(p) and os.path.getsize(p) > 1000:
            try:
                with open(p, "rb") as f:
                    return f.read()
            except Exception:
                pass
    return None


def get_audio_data_uri(
    fest_name: str = "",
    companion_label: str = "혼자",
    narration_text: str = "",
    custom_mp3_path: Optional[str] = None,
    audio_bytes: Optional[bytes] = None,
    preferred_voice: str = "onyx"
) -> str:
    """
    [고품질 나레이션 로컬 MP3 base64 변환]
    """
    if not audio_bytes:
        audio_bytes = get_docent_intro_audio_bytes(target_festival_name=fest_name, companion_label=companion_label, custom_mp3_path=custom_mp3_path)

    if audio_bytes:
        try:
            b64 = base64.b64encode(audio_bytes).decode("utf-8")
            return f"data:audio/mp3;base64,{b64}"
        except Exception:
            pass
    return ""


def render_audio_docent(companion_text="혼자"):
    """
    [표준 Streamlit 여행 유형별 오디오 도슨트 렌더링 함수]
    """
    if st is None:
        return

    cur_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(cur_dir)

    comp_key = resolve_companion_key(companion_text)
    guide_info = GUIDE_DATA.get(comp_key, GUIDE_DATA["혼자"])
    rel_audio_path = guide_info["audio_path"]
    guide_title = guide_info["title"]
    guide_script = guide_info["script"]

    candidates = [
        os.path.join(root_dir, rel_audio_path),
        os.path.join(cur_dir, os.path.basename(rel_audio_path)),
        os.path.join(root_dir, "festapick", rel_audio_path),
        os.path.join(root_dir, "backup_my_work", rel_audio_path),
        os.path.join(root_dir, "assets", rel_audio_path),
        os.path.join(root_dir, "audio", f"{comp_key}.mp3"),
    ]

    target_audio = next((p for p in candidates if os.path.exists(p) and os.path.getsize(p) > 1000), None)

    # 1. 상단 가이드 헤더
    st.markdown("**오디오 도슨트로 듣기** `감성 도슨트 보이스`")
    st.caption(f"{guide_title}")

    # 2. 오디오 플레이어 (다른 요소 클릭 시 즉시 중단)
    if target_audio:
        with open(target_audio, "rb") as f:
            audio_bytes = f.read()
        st.audio(audio_bytes, format="audio/mp3")
        st.html("""
        <script>
        (function() {
            function stopAllAudios() {
                try {
                    const doc = (window.parent && window.parent.document) ? window.parent.document : document;
                    const audios = doc.querySelectorAll('audio');
                    audios.forEach(function(a) {
                        if (!a.paused) {
                            a.pause();
                            a.currentTime = 0;
                        }
                    });
                } catch(e) {}
            }

            const doc = (window.parent && window.parent.document) ? window.parent.document : document;
            doc.addEventListener('click', function(e) {
                if (!e.target.closest('audio')) {
                    const interactive = e.target.closest('button, [role="tab"], [data-baseweb="tab"], .stSelectbox, .stRadio, a, .story-card, .festival-card, [data-testid^="stBaseButton"], input, select');
                    if (interactive) {
                        stopAllAudios();
                    }
                }
            }, true);

            doc.addEventListener('play', function(e) {
                try {
                    const audios = doc.querySelectorAll('audio');
                    audios.forEach(function(other) {
                        if (other !== e.target && !other.paused) {
                            other.pause();
                            other.currentTime = 0;
                        }
                    });
                } catch(e) {}
            }, true);
        })();
        </script>
        """)
    else:
        st.warning(f"⚠️ `{rel_audio_path}` 음원 파일을 준비 중입니다.")

    # 3. 음원 내용과 100% 일치하는 아코디언 전문 텍스트
    with st.expander("📜 에디터의 감성 가이드 나레이션 전문 읽어보기"):
        st.markdown(f"""
        <div style="font-family: 'Pretendard', 'Noto Sans KR', -apple-system, sans-serif; font-size: 0.9rem; line-height: 1.85; color: #2B2F2C; background: #F8F6F0; padding: 16px 20px; border-radius: 10px; border-left: 3.5px solid #1B4332; white-space: pre-line;">
        {guide_script}
        </div>
        """, unsafe_allow_html=True)
