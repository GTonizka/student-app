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

    st.title("🏫 학급 올인원 관리시스템")

    students_df = get_data(student_sheet)
    records_df = get_data(record_sheet)

    tab1, tab_att, tab2, tab3 = st.tabs(["🔍 학생 지도", "⏰ 출결 관리", "📋 학급 명렬표", "📊 통계 및 다운로드"])

    # ==========================================
    # --- 탭 1: 학생 지도 및 기록 ---
    # ==========================================
    with tab1:
        search_guide = st.text_input("지도가 필요한 학생 이름 검색", placeholder="이름 입력 후 엔터", key="g_search")
        
        if search_guide:
            st_info = students_df[students_df['이름'] == search_guide]
            
            if not st_info.empty:
                info = st_info.iloc[0]
                st.success(f"📍 {info['학년']}학년 {info['반']}반 {info['번호']}번 {info['이름']} (상태: {info['학적상태']})")
                
                if not records_df.empty and '이름' in records_df.columns:
                    st_records = records_df[records_df['이름'] == search_guide]
                else:
                    st_records = pd.DataFrame()

                if not st_records.empty:
                    c_o1 = len(st_records[st_records['분류'] == '외출증 사용(공식)'])
                    c_o2 = len(st_records[st_records['분류'] == '외출증 사용(포상)'])
                    c_o3 = len(st_records[st_records['분류'] == '무단 외출 적발'])
                    c_sm = len(st_records[st_records['분류'].str.contains('흡연', na=False)])
                    c_ri = len(st_records[st_records['분류'].str.contains('교권', na=False)])
                else:
                    c_o1 = c_o2 = c_o3 = c_sm = c_ri = 0

                st.subheader("📌 학생 지도 현황")
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("외출(공식)", c_o1)
                c2.metric("외출(포상)", c_o2)
                c3.metric("무단 외출", c_o3)
                c4.metric("흡연(교내/외)", c_sm)
                c5.metric("🚨 교권 침해", c_ri)

                st.divider()
                st.subheader("📝 신규 지도 내용 작성")
                g_cat = st.radio("기록 종류 선택", ["일반 지도", "교권 침해", "생활교육위원회 징계"], horizontal=True)
                
                with st.form("guide_form", clear_on_submit=True):
                    if g_cat == "일반 지도":
                        rtype = st.selectbox("항목", ["외출증 사용(공식)", "외출증 사용(포상)", "무단 외출 적발", "교외 흡연 적발", "교내 흡연 적발", "기타"])
                        content = st.text_area("상세 내용")
                    elif g_cat == "교권 침해":
                        rtype = st.selectbox("항목", ["교권침해(수업 방해)", "교권침해(폭언 및 욕설)", "교권침해(정당한 지도 불응)", "교권침해(기타)"])
                        content = st.text_area("사안 상세 내용 (육하원칙에 의거하여 작성)")
                    else:
                        level = st.selectbox("징계 단계", ["교내봉사", "사회봉사", "특별교육", "출석정지(5일)", "출석정지(10일)", "퇴학"])
                        rtype = "생활교육위원회 징계"
                        content = f"[{level}] " + st.text_area("징계 사유")
                    
                    col_l, col_a = st.columns(2)
                    loc = col_l.text_input("장소")
                    aut = col_a.text_input("작성자(교사명)")
                    
                    col_d, col_t = st.columns(2)
                    r_date = col_d.date_input("📅 발생 일자", datetime.now().date(), key="gd")
                    r_time = col_t.time_input("⏰ 발생 시간", datetime.now().time(), key="gt")
                    
                    if st.form_submit_button("기록 저장하기"):
                        if not aut or not loc:
                            st.error("장소와 작성자를 입력해주세요.")
                        else:
                            sel_dt = datetime.combine(r_date, r_time).strftime("%Y-%m-%d %H:%M:%S")
                            record_sheet.append_row([search_guide, rtype, content, loc, aut, sel_dt])
                            st.success("지도 데이터가 안전하게 저장되었습니다.")
                            st.rerun()

            else:
                st.warning("해당 이름의 학생을 찾을 수 없습니다.")

    # ==========================================
    # --- 탭 2: 출결 관리 (명단 출력/빠른 입력) ---
    # ==========================================
    with tab_att:
        st.subheader("⏰ 학급별 출석부 빠른 입력")
        
        if not students_df.empty and '학년' in students_df.columns and '반' in students_df.columns:
            col_ag, col_ac = st.columns(2)
            
            with col_ag:
                a_grades = sorted(students_df['학년'].astype(str).unique())
                a_sel_grade = st.selectbox("학년 선택", a_grades, key="ag")
                
            with col_ac:
                a_classes_in = students_df[students_df['학년'].astype(str) == a_sel_grade]['반'].astype(str).unique()
                a_classes = sorted(a_classes_in)
                a_sel_class = st.selectbox("반 선택", a_classes, key="ac")
                
            st.divider()
            
            a_df = students_df[(students_df['학년'].astype(str) == a_sel_grade) & (students_df['반'].astype(str) == a_sel_class)].copy()
            
            if not a_df.empty:
                a_df['번호_숫자'] = pd.to_numeric(a_df['번호'], errors='coerce')
                a_df = a_df.sort_values('번호_숫자')
                
                st.info("💡 위쪽에 **작성자**와 **날짜**를 한 번만 적어두시고, 아래 명단에서 **출결 특이사항이 있는 학생만 바로 [저장]**을 누르세요!")
                
                c_top1, c_top2 = st.columns(2)
                global_aut = c_top1.text_input("👨‍🏫 작성자(담임/교사명)", key="g_aut")
                global_date = c_top2.date_input("📅 출결 해당 일자", datetime.now().date(), key="g_date")
                
                st.markdown("### 📋 출석부 명단")
                
                hc1, hc2, hc3, hc4 = st.columns([1.5, 3, 4, 1.5])
                hc1.markdown("**이름**")
                hc2.markdown("**출결 항목**")
                hc3.markdown("**사유**")
                hc4.markdown("**기록**")
                
                for index, row in a_df.iterrows():
                    s_name = row['이름']
                    s_num = row['번호']
                    
                    with st.form(key=f"att_form_{a_sel_grade}_{a_sel_class}_{s_num}_{s_name}", clear_on_submit=True):
                        c1, c2, c3, c4 = st.columns([1.5, 3, 4, 1.5])
                        
                        c1.markdown(f"**{s_num}번** {s_name}")
                        
                        # ★ 수정됨: '결과' 항목 4가지가 모두 추가되었습니다!
                        a_type = c2.selectbox(
                            "항목", 
                            ["질병결석", "미인정결석", "출석인정결석", "기타결석",
                             "질병조퇴", "미인정조퇴", "출석인정조퇴", "기타조퇴",
                             "질병지각", "미인정지각", "출석인정지각", "기타지각",
                             "질병결과", "미인정결과", "출석인정결과", "기타결과"],
                            label_visibility="collapsed"
                        )
                        
                        a_content = c3.text_input("사유", placeholder="사유 (감기 등)", label_visibility="collapsed")
                        
                        if c4.form_submit_button("저장"):
                            if not global_aut:
                                st.error("☝️ 위쪽에 작성자 이름을 먼저 입력해주세요!")
                            else:
                                sel_dt_a = datetime.combine(global_date, datetime.now().time()).strftime("%Y-%m-%d %H:%M:%S")
                                record_sheet.append_row([s_name, a_type, a_content, "출결처리", global_aut, sel_dt_a])
                                st.success(f"✅ {s_name} ({a_type}) 저장 완료!")
            else:
                st.info("해당 학급에 등록된 학생이 없습니다.")
        else:
            st.warning("학생명부 데이터가 올바르게 구성되지 않았습니다.")

    # ==========================================
    # --- 탭 3: 학급별 명렬표 ---
    # ==========================================
    with tab2:
        st.header("📋 학급별 명렬표 및 세부 현황")
        
        if not students_df.empty and '학년' in students_df.columns and '반' in students_df.columns:
            col_g, col_c = st.columns(2)
            
            with col_g:
                grades = sorted(students_df['학년'].astype(str).unique())
                sel_grade = st.selectbox("명렬표 - 학년 선택", grades, key="mg")
                
            with col_c:
                classes_in = students_df[students_df['학년'].astype(str) == sel_grade]['반'].astype(str).unique()
                classes = sorted(classes_in)
                sel_class = st.selectbox("명렬표 - 반 선택", classes, key="mc")
                
            st.divider()
            
            c_df = students_df[(students_df['학년'].astype(str) == sel_grade) & (students_df['반'].astype(str) == sel_class)].copy()
            
            if not c_df.empty:
                c_df['번호_숫자'] = pd.to_numeric(c_df['번호'], errors='coerce')
                c_df = c_df.sort_values('번호_숫자')
                
                st.success(f"✅ {sel_grade}학년 {sel_class}반 (총 {len(c_df)}명)")
                
                for index, row in c_df.iterrows():
                    s_name = row['이름']
                    
                    if not records_df.empty and '이름' in records_df.columns:
                        s_rec = records_df[records_df['이름'] == s_name]
                    else:
                        s_rec = pd.DataFrame()
                        
                    # ★ 수정됨: '결과' 단어도 출결 기록으로 완벽히 인식합니다!
                    is_att = s_rec['분류'].str.contains('결석|조퇴|지각|결과', na=False) if not s_rec.empty else pd.Series(dtype=bool)
                    has_guide = not s_rec[~is_att].empty
                    has_only_att = not s_rec[is_att].empty and not has_guide
                    
                    if has_guide:
                        ex_title = f"💖 [지도] {row['번호']}번 {s_name} (상태: {row['학적상태']})"
                    elif has_only_att:
                        ex_title = f"🗓️ [출결] {row['번호']}번 {s_name} (상태: {row['학적상태']})"
                    else:
                        ex_title = f"⬜ {row['번호']}번 {s_name} (상태: {row['학적상태']})"
                    
                    with st.expander(ex_title):
                        if s_rec.empty:
                            st.info("기록이 없습니다.")
                        else:
                            if has_guide:
                                st.markdown("<div style='background-color: #FFF0F5; padding: 15px; border-radius: 8px; border-left: 5px solid #FF69B4; margin-bottom: 15px;'><span style='color: #C71585; font-weight: bold;'>📌 이 학생은 누적된 [생활지도] 기록이 있습니다.</span></div>", unsafe_allow_html=True)
                            elif has_only_att:
                                st.markdown("<div style='background-color: #F0F8FF; padding: 15px; border-radius: 8px; border-left: 5px solid #4682B4; margin-bottom: 15px;'><span style='color: #4682B4; font-weight: bold;'>🗓️ 이 학생은 누적된 [출결] 기록이 있습니다.</span></div>", unsafe_allow_html=True)
                            
                            st.markdown("**🔍 상세 기록 내역**")
                            d_rec = s_rec.drop(columns=['이름'], errors='ignore')
                            st.dataframe(d_rec.sort_values('작성일시', ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("해당 학급에 등록된 학생이 없습니다.")

    # ==========================================
    # --- 탭 4: 분리형 통계 및 다운로드 (자동 피벗 추가) ---
    # ==========================================
    with tab3:
        st.header("📈 학교 전체 통계 및 다운로드")
        
        if not records_df.empty and '작성일시' in records_df.columns:
            st.subheader("📂 전체 원본 데이터 다운로드")
            
            output_all = io.BytesIO()
            with pd.ExcelWriter(output_all, engine='openpyxl') as writer:
                records_df.to_excel(writer, index=False, sheet_name='전체기록_원본')
            excel_data_all = output_all.getvalue()
            
            st.download_button(
                label="📁 전체 기록 원본 엑셀 다운로드 (지도+출결)",
                data=excel_data_all,
                file_name=f"학생통합기록_원본_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            st.divider()
            
            try:
                stats_df = records_df.copy()
                stats_df['변환된일시'] = pd.to_datetime(stats_df['작성일시'], errors='coerce')
                stats_df = stats_df.dropna(subset=['변환된일시'])
                stats_df['월'] = stats_df['변환된일시'].dt.strftime('%Y년 %m월')
                
                # ★ 수정됨: '결과' 단어도 출결 통계로 완벽히 분리됩니다!
                mask_att = stats_df['분류'].str.contains('결석|조퇴|지각|결과', na=False)
                df_att = stats_df[mask_att].copy()
                df_guide = stats_df[~mask_att]
                
                # --- 차트 영역 ---
                col_st1, col_st2 = st.columns(2)
                with col_st1:
                    st.markdown("### 📊 월별 **생활지도** 건수")
                    guide_mon = df_guide['월'].value_counts().sort_index()
                    if not guide_mon.empty:
                        st.bar_chart(guide_mon)
                    else:
                        st.info("생활지도 통계 데이터가 없습니다.")
                        
                with col_st2:
                    st.markdown("### ⏰ 월별 **학생출결** 건수")
                    att_mon = df_att['월'].value_counts().sort_index()
                    if not att_mon.empty:
                        st.bar_chart(att_mon)
                    else:
                        st.info("출결 통계 데이터가 없습니다.")

                st.divider()
                
                # --- 월별/학급별/학생별 출결 자동 요약(피벗) ---
                st.subheader("📑 월별 학급/학생 출결 요약 통계 (자동 계산)")
                
                if not df_att.empty and not students_df.empty:
                    stu_info = students_df[['학년', '반', '번호', '이름']].copy()
                    merged_att = pd.merge(df_att, stu_info, on='이름', how='left')
                    
                    pivot_df = pd.pivot_table(
                        merged_att, 
                        index=['월', '학년', '반', '번호', '이름'], 
                        columns='분류', 
                        aggfunc='size', 
                        fill_value=0
                    ).reset_index()
                    
                    pivot_df['학년'] = pd.to_numeric(pivot_df['학년'], errors='coerce')
                    pivot_df['반'] = pd.to_numeric(pivot_df['반'], errors='coerce')
                    pivot_df['번호'] = pd.to_numeric(pivot_df['번호'], errors='coerce')
                    pivot_df = pivot_df.sort_values(by=['월', '학년', '반', '번호'])
                    
                    st.dataframe(pivot_df, use_container_width=True, hide_index=True)
                    
                    output_att = io.BytesIO()
                    with pd.ExcelWriter(output_att, engine='openpyxl') as writer:
                        pivot_df.to_excel(writer, index=False, sheet_name='학생별_출결통계')
                    excel_data_att = output_att.getvalue()
                    
                    st.download_button(
                        label="📥 [자동계산] 월별/학생별 출결 통계표 엑셀 다운로드",
                        data=excel_data_att,
                        file_name=f"자동출결통계_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info("아직 누적된 출결 기록이 없어 요약 통계를 생성할 수 없습니다.")
                        
            except Exception as e:
                st.info(f"통계 처리 중 오류가 발생했습니다: {e}")
        else:
            st.info("아직 등록된 기록이 없습니다.")

except Exception as e:
    st.error("🚨 치명적인 에러가 발생하여 화면이 멈췄습니다! 범인은 바로 아래에 있습니다.")
    st.code(traceback.format_exc())
