import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import io

# 1. 페이지 설정
st.set_page_config(page_title="학생생활지도 관리시스템", layout="wide")

# ==========================================
# 🔒 로그인 (자물쇠) 기능
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 학생생활지도 관리시스템")
    st.info("학생 개인정보 보호를 위해 비밀번호를 입력해 주세요.")
    
    with st.form("login_form"):
        pwd_input = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        submit_button = st.form_submit_button("접속하기")
        
        if submit_button:
            if pwd_input == st.secrets["app_password"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 일치하지 않습니다.")
    st.stop()

# ==========================================
# 🔓 로그인 성공 시 실행되는 메인 프로그램
# ==========================================
@st.cache_resource
def init_connection():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    return client

client = init_connection()
sheet_url = st.secrets["spreadsheet_url"]
doc = client.open_by_url(sheet_url)

student_sheet = doc.worksheet("학생명부")
record_sheet = doc.worksheet("지도기록")

def get_data(sheet):
    data = sheet.get_all_values()
    if not data or len(data) < 1:
        return pd.DataFrame()
    headers
