# -*- coding: utf-8 -*-
"""
festapick/fallback_assets.py - 무결점 100% 엑박 방지 기본 그래픽 에셋 모듈
오프라인/네트워크 오류/403 차단 시 0ms 즉시 렌더링되는 가을 로컬 축제 공식 SVG Graphic Data URI
"""
import base64

_SVG_CONTENT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" width="800" height="500">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#08281B"/>
      <stop offset="45%" stop-color="#14422E"/>
      <stop offset="100%" stop-color="#1E543D"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="40%" r="50%">
      <stop offset="0%" stop-color="#FBBF24" stop-opacity="0.32"/>
      <stop offset="60%" stop-color="#F59E0B" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="#08281B" stop-opacity="0"/>
    </radialGradient>
  </defs>
  
  <!-- 배경 그라데이션 -->
  <rect width="800" height="500" fill="url(#bg)"/>
  
  <!-- 중앙 황금빛 조명 효과 -->
  <circle cx="400" cy="220" r="280" fill="url(#glow)"/>
  
  <!-- 은은한 축제 별빛 / 보케 장식 -->
  <circle cx="160" cy="120" r="3" fill="#FDE68A" opacity="0.6"/>
  <circle cx="240" cy="80" r="2" fill="#FDE68A" opacity="0.4"/>
  <circle cx="640" cy="110" r="3" fill="#FDE68A" opacity="0.7"/>
  <circle cx="710" cy="160" r="2" fill="#FDE68A" opacity="0.5"/>
  <circle cx="340" cy="60" r="1.5" fill="#FFFFFF" opacity="0.5"/>
  <circle cx="500" cy="70" r="2" fill="#FDE68A" opacity="0.6"/>
  <circle cx="120" cy="280" r="2" fill="#FFFFFF" opacity="0.3"/>
  <circle cx="680" cy="300" r="2.5" fill="#FDE68A" opacity="0.4"/>
  
  <!-- 가을 단풍 잎 실루엣 (좌우) -->
  <path d="M 60 400 C 90 360, 140 370, 160 390 C 140 420, 90 430, 60 400 Z" fill="#D97706" opacity="0.4"/>
  <path d="M 120 440 C 150 410, 190 420, 200 450 C 170 470, 130 460, 120 440 Z" fill="#B45309" opacity="0.3"/>
  <path d="M 720 390 C 690 350, 640 360, 630 390 C 650 420, 700 420, 720 390 Z" fill="#D97706" opacity="0.35"/>
  
  <!-- 한국 전통 청사초롱 / 축제 등불 아이콘 -->
  <g transform="translate(400, 135) scale(0.9)">
    <line x1="0" y1="-30" x2="0" y2="-10" stroke="#FDE68A" stroke-width="2" opacity="0.7"/>
    <path d="M -16 -10 L 16 -10 L 22 18 L -22 18 Z" fill="#EF4444" opacity="0.9"/>
    <path d="M -22 18 L 22 18 L 16 38 L -16 38 Z" fill="#3B82F6" opacity="0.85"/>
    <rect x="-18" y="-12" width="36" height="4" rx="2" fill="#F59E0B"/>
    <rect x="-18" y="36" width="36" height="4" rx="2" fill="#F59E0B"/>
    <line x1="0" y1="40" x2="0" y2="58" stroke="#F59E0B" stroke-width="2.5"/>
    <circle cx="0" cy="60" r="3" fill="#F59E0B"/>
    <circle cx="0" cy="14" r="28" fill="#FEF08A" opacity="0.2"/>
  </g>
  
  <!-- 상단 카테고리 뱃지 -->
  <rect x="280" y="225" width="240" height="32" rx="16" fill="rgba(255,255,255,0.12)" stroke="rgba(255,255,255,0.22)" stroke-width="1"/>
  <text x="400" y="246" fill="#FDE68A" font-size="12" font-family="'Pretendard', -apple-system, sans-serif" font-weight="700" text-anchor="middle" letter-spacing="1.2">🌿 FESTAPICK 가을 축제</text>
  
  <!-- 메인 타이틀 -->
  <text x="400" y="298" fill="#FFFFFF" font-size="24" font-family="'Pretendard', -apple-system, sans-serif" font-weight="800" text-anchor="middle" letter-spacing="-0.5">대한민국 로컬 문화 축제</text>
  
  <!-- 서브 타이틀 안내 -->
  <text x="400" y="328" fill="#A7D7BC" font-size="13.5" font-family="'Pretendard', -apple-system, sans-serif" font-weight="500" text-anchor="middle" letter-spacing="0.2">공공데이터 공식 축제 · 안심 힐링 여정</text>
  
  <!-- 하단 장식 라인 -->
  <line x1="280" y1="355" x2="520" y2="355" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>
</svg>"""

DEFAULT_FESTIVAL_GRAPHIC_DATA_URI = "data:image/svg+xml;base64," + base64.b64encode(_SVG_CONTENT.strip().encode('utf-8')).decode('utf-8')
