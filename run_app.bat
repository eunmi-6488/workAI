@echo off
chcp 65001 > nul
echo ===================================================
echo [FestaPick] 메인 애플리케이션 실행 (app.py)
echo ===================================================
call conda activate myenv
streamlit run app.py --server.port 8501
pause
