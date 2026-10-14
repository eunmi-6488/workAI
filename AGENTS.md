# Project Working Guidelines

## Automatic Backup Rule
- Whenever any code files in `festapick/` (such as `festapick/data.py`, `festapick/prompt.py`, `festapick/app.py`, etc.) or the root directory are modified, updated, or refactored for the user:
  - ALWAYS automatically copy the updated files to `backup_my_work/` immediately without requiring the user to ask.
  - Inform the user that the backup has been automatically synchronized.

## Push Confirmation Rule
- NEVER push to remote (`git push`) automatically.
- ALWAYS show the modified changes and verification checklist to the user first.
- ONLY execute `git push` after the user reviews and explicitly confirms (e.g., "푸시해줘", "확인 완료").

## Git Commit & Naming Rule
- Write Git commit messages in clear, professional **Korean** (e.g. `feat: 축제 카드 실내외 뱃지 표시`, `fix: 점심 1택 비교 가이드 프롬프트 개선`).
- NEVER include personal names (e.g. "은미", "은미님") in Git commit messages, PRs, branch names, code comments, or repository documentation.
- ALWAYS maintain strictly professional, technical developer language.
