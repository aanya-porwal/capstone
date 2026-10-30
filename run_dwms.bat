@echo off
cd /d "%~dp0"
python -m pip install -r requirements-prototype.txt
python -m streamlit run streamlit_app.py
