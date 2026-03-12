import streamlit as st
import traceback

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

    st.title("🏫 학생생활지도 관리시스템")

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

                st.subheader("📌 학생 지도 현황")
                c1, c2, c3, c4, c5 = st.columns(5)
                if not student_records.empty:
                    c1.metric("외출(공식)", len(student_records[student_records['분류'] == '외출증 사용(공식)']))
                    c2.metric("외출(포상)", len(student_records[student_records['분류'] == '외출증 사용(포상)']))
                    c3.metric("무단 외출", len(student_records[student_records['분류'] == '무단 외출 적발']))
                    c4.metric("흡연(교내/외)", len(student_records[student_records['분류'].str.contains('흡연', na=False)]))
                    c5.metric("🚨 교권 침해", len(student_records[student_records['분류'].str.contains('교권', na=False)]))
                else:
                    for c, title in zip([c1, c2, c3, c4, c5], ["외출(공식)", "외출(포상)", "무단 외출", "흡연(교내/외)", "🚨 교권 침해"]): 
                        c.metric(title, 0)

                st.divider()
                
                st.subheader("📝 신규 지도 내용 작성")
                category = st.radio("기록 종류 선택", ["일반 지도", "교권 침해", "생활교육위원회 징계"], horizontal=True)
                
                with st.form("input_form", clear_on_submit=True):
                    if category == "일반 지도":
                        rtype = st.selectbox("항목", ["외출증 사용(공식)", "외출증 사용(포상)", "무단 외출 적발", "교외 흡연 적발", "교내 흡연 적발", "기타"])
                        content = st.text_area("상세 내용")
                    elif category == "교권 침해":
                        rtype = st.selectbox("항목", ["교권침해(수업 방해)", "교권침해(폭언 및 욕설)", "교권침해(정당한 지도 불응)", "교권침해(기타)"])
                        content = st.text_area("사안 상세 내용 (육하원칙에 의거하여 작성)")
                    else:
                        level = st.selectbox("징계 단계", ["교내봉사", "사회봉사", "특별교육", "출석정지(5일)", "출석정지(10일)", "퇴학"])
                        rtype = "생활교육위원회 징계"
                        content = f"[{level}] " + st.text_area("징계 사유")
                    
                    col_l, col_a = st.columns(2)
                    loc = col_l.text_input("장소")
                    aut = col_a.text_input("작성자(교사명)")
                    
                    if st.form_submit_button("기록 저장하기"):
                        if not aut or not loc:
                            st.error("장소와 작성자를 입력해주세요.")
                        else:
                            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            record_sheet.append_row([search_name, rtype, content, loc, aut, now])
                            st.success("데이터가 구글 시트에 안전하게 저장되었습니다.")
                            st.rerun()

                st.divider()
                st.subheader("📜 학생 기록")
                if not student_records.empty:
                    st.dataframe(student_records.sort_values('작성일시', ascending=False), use_container_width=True, hide_index=True)
                else:
                    st.info("이 학생에 대한 이전 기록이 없습니다.")
            else:
                st.warning("해당 이름의 학생을 찾을 수 없습니다.")

    # --- ★ 탭 2: 학급별 명렬표 (수정된 부분) ---
    with tab2:
        st.header("📋 학급별 명렬표 및 세부 현황")
        
        if not students_df.empty and '학년' in students_df.columns and '반' in students_df.columns:
            col_g, col_c = st.columns(2)
            
            with col_g:
                grades = sorted(students_df['학년'].astype(str).unique())
                selected_grade = st.selectbox("학년 선택", grades)
                
            with col_c:
                classes_in_grade = students_df[students_df['학년'].astype(str) == selected_grade]['반'].astype(str).unique()
                classes = sorted(classes_in_grade)
                selected_class = st.selectbox("반 선택", classes)
                
            st.divider()
            
            class_df = students_df[(students_df['학년'].astype(str) == selected_grade) & (students_df['반'].astype(str) == selected_class)].copy()
            
            if not class_df.empty:
                class_df['번호_숫자'] = pd.to_numeric(class_df['번호'], errors='coerce')
                class_df = class_df.sort_values('번호_숫자')
                
                st.success(f"✅ {selected_grade}학년 {selected_class}반 (총 {len(class_df)}명)")
                
                # ★ 단순 표 대신, 학생별로 클릭하면 열리는 아코디언 메뉴 생성
                for index, row in class_df.iterrows():
                    student_name = row['이름']
                    
                    # 아코디언 메뉴 (클릭하면 아래 내용이 펼쳐짐)
                    with st.expander(f"🧑‍🎓 {row['번호']}번 {student_name} (상태: {row['학적상태']})"):
                        
                        # 이 학생의 기록만 쏙 뽑아오기
                        if not records_df.empty and '이름' in records_df.columns:
                            s_records = records_df[records_df['이름'] == student_name]
                        else:
                            s_records = pd.DataFrame()

                        if s_records.empty:
                            st.info("이 학생에 대한 지도 기록이 없습니다.")
                        else:
                            # 1. 요약 통계 보여주기
                            c1, c2, c3 = st.columns(3)
                            
                            cnt_gyogwon = len(s_records[s_records['분류'].str.contains('교권', na=False)])
                            cnt_jinggye = len(s_records[s_records['분류'] == '생활교육위원회 징계'])
                            cnt_normal = len(s_records) - cnt_gyogwon - cnt_jinggye
                            
                            c1.metric("📝 일반 지도", cnt_normal)
                            c2.metric("🚨 교권 침해", cnt_gyogwon)
                            c3.metric("⚖️ 위원회 징계", cnt_jinggye)
                            
                            # 2. 세부 기록 내역 표 보여주기
                            st.markdown("**🔍 상세 기록 내역**")
                            display_records = s_records.drop(columns=['이름'], errors='ignore') # 이미 본인 창이므로 이름 열은 숨김
                            st.dataframe(display_records.sort_values('작성일시', ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("해당 학급에 등록된 학생이 없습니다.")
        else:
            st.warning("학생명부 데이터가 올바르게 구성되지 않았습니다.")

    # --- 탭 3: 통계 및 다운로드 ---
    with tab3:
        st.header("📈 학교 전체 통계 및 다운로드")
        
        if not records_df.empty and '작성일시' in records_df.columns:
            st.subheader("📂 엑셀(.xlsx) 파일 다운로드")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                records_df.to_excel(writer, index=False, sheet_name='지도기록')
            excel_data = output.getvalue()
            
            st.download_button(
                label="📊 전체 지도기록 엑셀 다운로드",
                data=excel_data,
                file_name=f"학생지도기록_전체_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            st.divider()
            st.subheader("📅 월별 누적 지도 건수 그래프")
            try:
                stats_df = records_df.copy()
                stats_df['변환된일시'] = pd.to_datetime(stats_df['작성일시'], errors='coerce')
                stats_df = stats_df.dropna(subset=['변환된일시'])
                stats_df['월'] = stats_df['변환된일시'].dt.strftime('%Y년 %m월')
                monthly_data = stats_df['월'].value_counts().sort_index()
                
                if not monthly_data.empty:
                    st.bar_chart(monthly_data)
                else:
                    st.info("그래프를 그릴 정상적인 날짜 데이터가 없습니다.")
            except Exception as e:
                st.info(f"통계 처리 중 오류가 발생했습니다: {e}")
        else:
            st.info("아직 등록된 전체 기록이 없어 통계 및 다운로드를 제공할 수 없습니다.")

except Exception as e:
    st.error("🚨 치명적인 에러가 발생하여 화면이 멈췄습니다! 범인은 바로 아래에 있습니다.")
    st.code(traceback.format_exc())
