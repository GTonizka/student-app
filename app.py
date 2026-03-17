import streamlit as st
import traceback

# 1. 페이지 설정
st.set_page_config(page_title="학생생활지도 및 출결 관리시스템", layout="wide")

# ==========================================
# 🔒 로그인 (자물쇠) 기능
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 학생생활지도 및 출결 관리시스템")
    st.info("학생 개인정보 보호를 위해 비밀번호를 입력해 주세요.")
    
    with st.form("login_form"):
        pwd_input = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        submit_button = st.form_submit_button("접속하기")
        
        if submit_button:
            try:
                if pwd_input == st.secrets["app_password"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("❌ 비밀번호가 일치하지 않습니다.")
            except KeyError:
                st.error("🚨 스트림릿 Secrets(금고)에 'app_password' 설정이 빠져있습니다!")
    st.stop()

# ==========================================
# 🔓 로그인 성공 후 화면
# ==========================================
try:
    import gspread
    from google.oauth2.service_account import Credentials
    import pandas as pd
    from datetime import datetime
    import io

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
        headers = data.pop(0)
        return pd.DataFrame(data, columns=headers)

    st.title("🏫 학급 올인원 관리시스템 (생활지도 & 출결)")

    students_df = get_data(student_sheet)
    records_df = get_data(record_sheet)

    tab1, tab2, tab3 = st.tabs(["🔍 학생 기록 및 작성", "📋 학급별 명렬표", "📊 통계 및 다운로드"])

    # --- 탭 1: 학생 조회 및 기록 ---
    with tab1:
        search_name = st.text_input("학생 이름을 입력하세요", placeholder="이름 입력 후 엔터")
        
        if search_name:
            student_info = students_df[students_df['이름'] == search_name]
            
            if not student_info.empty:
                info = student_info.iloc[0]
                st.success(f"📍 {info['학년']}학년 {info['반']}반 {info['번호']}번 {info['이름']} (상태: {info['학적상태']})")
                
                if not records_df.empty and '이름' in records_df.columns:
                    student_records = records_df[records_df['이름'] == search_name]
                else:
                    student_records = pd.DataFrame()

                # 데이터 분리 (출결 vs 지도)
                attendance_mask = student_records['분류'].str.contains('결석|조
