import streamlit as st
import CoolProp.CoolProp as CP
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ==========================================
# 1. SET UP STREAMLIT PAGE
# ==========================================
st.set_page_config(page_title="Advanced Two-Stage VCR with Control Loops", layout="wide")
st.title("🎛️ Controlled Two-Stage VCR with Flash Tank Simulation")
st.write("ระบบจำลองเทอร์โมไดนามิกส์ร่วมกับเลเยอร์การควบคุมกระบวนการ (Process Control) 3 Loops ตามมาตรฐาน ISA-5.1")

# ==========================================
# 2. SIDEBAR - CONTROL PANEL (INPUTS)
# ==========================================
st.sidebar.header("🎛️ แผงควบคุมระบบ (Control Panel)")

if 'disturb_T' not in st.session_state:
    st.session_state.disturb_T = 0.0
if 'disturb_P' not in st.session_state:
    st.session_state.disturb_P = 0.0
if 'disturb_y' not in st.session_state:
    st.session_state.disturb_y = 0.0

st.sidebar.subheader("🎯 Setpoints (SP)")
sp_T_evap = st.sidebar.slider("TIC-101: T_set ห้องเย็น (°C)", -40.0, -5.0, -10.0, 1.0)
sp_P_cond = st.sidebar.slider("PIC-101: P_set คอนเดนเซอร์ (kPa)", 800.0, 1400.0, 1000.0, 50.0)
sp_y_flash = st.sidebar.slider("FIC-101: y_set สัดส่วนไอในถัง Flash", 0.05, 0.25, 0.10, 0.01)

st.sidebar.subheader("📡 Sensor Readings (PV)")
col_sb1, col_sb2 = st.sidebar.columns(2)

with col_sb1:
    pv_T_evap = st.sidebar.number_input("TT-101: T_actual (°C)", value=float(sp_T_evap + st.session_state.disturb_T), step=0.5)
    pv_P_cond = st.sidebar.number_input("PT-101: P_actual (kPa)", value=float(sp_P_cond + st.session_state.disturb_P), step=10.0)
    pv_y_flash = st.sidebar.number_input("FT-101: y_actual", value=float(sp_y_flash + st.session_state.disturb_y), step=0.01, format="%.2f")

st.sidebar.subheader("⚙️ System Configurations")
refrigerant = st.sidebar.selectbox("Refrigerant Spec", ["R134a", "R410A", "R32"])
eta_c = st.sidebar.slider("Compressor Isentropic Efficiency (η)", 0.50, 1.00, 0.85, 0.05)
superheat = st.sidebar.slider("Superheat at Evap Exit (ΔT_sh, K)", 0.0, 10.0, 5.0, 1.0)
subcool = st.sidebar.slider("Subcool at Cond Exit (ΔT_sc, K)", 0.0, 10.0, 5.0, 1.0)

st.sidebar.subheader("🎮 Interactive Actions")
col_btn1, col_btn2 = st.sidebar.columns(2)

if col_btn1.button("⇄ Match SP/PV"):
    st.session_state.disturb_T = 0.0
    st.session_state.disturb_P = 0.0
    st.session_state.disturb_y = 0.0
    st.rerun()

if col_btn2.button("⚠ Inject Disturbance"):
    st.session_state.disturb_T = np.random.uniform(-3.0, 3.0)
    st.session_state.disturb_P = np.random.uniform(-80.0, 80.0)
    st.session_state.disturb_y = np.random.uniform(-0.04, 0.04)
    st.rerun()

# ==========================================
# 3. CONTROL LOGIC & THERMO CORE ENGINE
# ==========================================
def controller_logic(sp, pv, loop_type):
    error = sp - pv
    if loop_type == "TIC":
        bias = 50.0
        kp = -10.0 
        output = bias + (kp * error)
    elif loop_type == "PIC":
        bias = 80.0
        kp = 0.05
        output = bias + (kp * error)
    elif loop_type == "FIC":
        bias = 50.0
        kp = 200.0
        output = bias + (kp * error)
    return max(0.0, min(100.0, output))

tic_out = controller_logic(sp_T_evap, pv_T_evap, "TIC")
pic_out = controller_logic(sp_P_cond, pv_P_cond, "PIC")
fic_out = controller_logic(sp_y_flash, pv_y_flash, "FIC")

try:
    # 📌 คำนวณความดันใช้งานตามกฎอุณหพลศาสตร์ตรงตามภาพ P&ID
    P_evap_act = CP.PropsSI('P', 'T', pv_T_evap + 273.15, 'Q', 1, refrigerant)
    P_cond_act = pv_P_cond * 1000.0
    P_mid_act = np.sqrt(P_evap_act * P_cond_act) # ความดันถัง Flash Tank (PI-102)
    
    # 🔹 STATE 1: ขาออกจาก Evaporator เข้าสู่คอมเพรสเซอร์สเตจความดันต่ำ (Comp 1 / K-102)
    T1 = (pv_T_evap + 273.15) + superheat
    h1 = CP.PropsSI('H', 'P', P_evap_act, 'T', T1, refrigerant)
    s1 = CP.PropsSI('S', 'P', P_evap_act, 'T', T1, refrigerant)
    
    # 🔹 STATE 2: ทางออกจากคอมเพรสเซอร์สเตจต่ำ (K-102 Exit) ก่อนเข้าอินเตอร์คูลเลอร์
    h2_s = CP.PropsSI('H', 'P', P_mid_act, 'S', s1, refrigerant)
    h2 = h1 + (h2_s - h1) / eta_c
    
    # 🔹 STATE 3 & 4: ออกจาก Intercooler (E-102) มุ่งหน้าไปจุดผสม M-101
    h3 = CP.PropsSI('H', 'P', P_mid_act, 'Q', 1, refrigerant)
    h4 = h3
    
    # 🔹 STATE 8: ทางออกจากคอนเดนเซอร์ (E-101 Exit)
    T8 = CP.PropsSI('T', 'P', P_cond_act, 'Q', 0, refrigerant) - subcool
    h8 = CP.PropsSI('H', 'P', P_cond_act, 'T', T8, refrigerant)
    
    # 🔹 STATE 9: สารผสมความดันปานกลางหลังผ่านวาล์วลดความดันตัวแรก (V-101) เข้าสู่ถัง Flash Tank
    h9 = h8
    
    # 🔹 STATE 6: ไออิ่มตัวด้านบนถัง Flash Tank (T-101) มุ่งหน้าไปผสมสเตจสูง
    h6 = CP.PropsSI('H', 'P', P_mid_act, 'Q', 1, refrigerant)
    
    # 🔹 STATE 10: ของเหลวอิ่มตัวก้นถัง Flash Tank ส่งต่อไปวาล์ว V-102
    h10 = CP.PropsSI('H', 'P', P_mid_act, 'Q', 0, refrigerant)
    
    # คำนวณหาปริมาณไอแยกส่วนจริง (y) ภายในถังแยกสเตจ
    y_calc = (h9 - h10) / (h6 - h10)
    
    # 🔹 STATE 5 & 5-6: ทางออกจาก Mixing Chamber (M-101) วิ่งเข้าคอมเพรสเซอร์สเตจสูง (Comp 2 / K-101)
    h5 = (1 - y_calc) * h4 + y_calc * h6
    s5 = CP.PropsSI('S', 'P', P_mid_act, 'H', h5, refrigerant)
    
    # 🔹 STATE 7: ทางออกจากคอมเพรสเซอร์สเตจความดันสูง (K-101 Exit)
    h7_s = CP.PropsSI('H', 'P', P_cond_act, 'S', s5, refrigerant)
    h7 = h5 + (h7_s - h5) / eta_c
    T7 = CP.PropsSI('T', 'P', P_cond_act, 'H', h7, refrigerant)
    
    # 🔹 STATE 11: ทางเข้าหลักของ Evaporator หลังผ่านวาล์วลดความดันชิ้นที่สอง (V-102)
    h11 = h10
    T11 = CP.PropsSI('T', 'P', P_evap_act, 'H', h11, refrigerant)
    
    # คำนวณประสิทธิภาพระบบตามหลักเทอร์โมไดนามิกส์
    q_evap = (h1 - h11) / 1000.0
    w_c1 = (h2 - h1) / 1000.0
    w_c2 = (1 / (1 - y_calc)) * ((h7 - h5) / 1000.0)
    w_total = w_c1 + w_c2
    cop = q_evap / w_total
    
    q_cond = (1 / (1 - y_calc)) * ((h7 - h8) / 1000.0)
    q_inter = (h2 - h3) / 1000.0
    energy_check = (q_evap + w_total) - (q_cond + q_inter)

except Exception as e:
    st.error(f"❌ ระบบหลุดขอบเขตทางฟิสิกส์: {e} กรุณากดปุ่ม 'Match SP/PV' เพื่อรีเซ็ตโครงสร้างความดัน")
    st.stop()

# ==========================================
# 4. DASHBOARD PANELS DISPLAY
# ==========================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🎯 Control Status", "📐 ISA P&ID Map", "📊 System Summary", 
    "📋 State Tables", "📈 P-h Diagram", "📉 T-s Diagram"
])

with tab1:
    st.subheader("📡 ตรวจสอบสถานะและพฤติกรรมวงจรควบคุม")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("🌡️ Loop 1: TIC-101 (Temperature)")
        st.metric("Setpoint (ห้องเย็น)", f"{sp_T_evap} °C")
        st.metric("Process Value (TT-101)", f"{pv_T_evap:.1f} °C", f"Error: {sp_T_evap - pv_T_evap:.1f} °C")
        st.progress(int(tic_out))
        st.metric("Valve V-102 Action", f"{tic_out:.1f} % เปิด")
    with c2:
        st.info("📊 Loop 2: PIC-101 (Pressure)")
        st.metric("Setpoint (Condenser)", f"{sp_P_cond} kPa")
        st.metric("Process Value (PT-101)", f"{pv_P_cond:.1f} kPa", f"Error: {sp_P_cond - pv_P_cond:.1f} kPa")
        st.progress(int(pic_out))
        st.metric("Comp K-101 Speed (VSD)", f"{pic_out:.1f} % Speed")
    with c3:
        st.info("🌊 Loop 3: FIC-101 (Flow/Quality)")
        st.metric("Setpoint (Flash Tank)", f"{sp_y_flash:.2f}")
        st.metric("Process Value (FT-101)", f"{pv_y_flash:.2f}", f"Error: {sp_y_flash - pv_y_flash:.2f}")
        st.progress(int(fic_out))
        st.metric("Valve V-101 Action", f"{fic_out:.1f} % เปิด")

with tab2:
    st.subheader("🗺️ ผังเครื่องมือวัดและสัญลักษณ์ระบบตามมาตรฐาน ISA-5.1")
    st.markdown(f"""
    ```
    [E-101 CONDENSER] <────── (PT-101) <────── [K-101 COMP 2 (High)] ◄── [M-101 MIXING]
           │                                             ▲                        ▲
         (⓼)                                       (PIC-101 Control)              │(⓹)
           ▼                                             │                        │
     [V-101 VALVE (EV-1)] ◄── (FIC-101 Control)          │             [E-102 INTERCOOLER]
           │                                             │                        ▲
         (⓽)                                             │                        │(⓶)
           ▼                                             │                        │
    ┌──────────────┐ ─── (Vapor: ⓺) ─────────────────────┼───────────────► [K-102 COMP 1 (Low)]
    │ T-101 FLASH  │                                     │                        ▲
    │    TANK      │ ─── (Liquid: ⓾) ──► [V-102 VALVE] ───┘                        │(⓵)
    └──────────────┘                    (TIC-101 Control)                         │
                                                 │                                │
                                               (⓫) ──► [E-103 EVAPORATOR] ──► (TT-101)
    ```
    """)

with tab3:
    st.subheader("📊 ผลสัมฤทธิ์ทางพลังงานและสัมประสิทธิ์สมรรถนะ")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Coefficient of Performance (COP)", f"{cop:.3f}")
    kpi2.metric("Cooling Capacity (q_evap)", f"{q_evap:.2f} kJ/kg")
    kpi3.metric("Total Work Input (w_total)", f"{w_total:.2f} kJ/kg")
    kpi4.metric("Energy Balance Check", f"{energy_check:.5f}")

with tab4:
    st.subheader("📋 ตารางแจกแจงค่าสภาวะทางอุณหพลศาสตร์ทั้ง 11 จุดสถานะ")
    state_names = [
        "1 (Evap Exit / Comp 1 In)", "2 (Comp 1 Exit)", "3 (Intercooler Exit)", 
        "4 (ก่อน Mixing Chamber)", "5 (Mixing Chamber Exit / Comp 2 In)", "6 (Flash Vapor Out)", 
        "7 (Comp 2 Exit)", "8 (Condenser Exit)", "9 (หลัง EV-1 Throttling)", 
        "10 (Flash Liquid Out)", "11 (หลัง EV-2 Throttling / Evap In)"
    ]
    pressures = [P_evap_act, P_mid_act, P_mid_act, P_mid_act, P_mid_act, P_mid_act, P_cond_act, P_cond_act, P_mid_act, P_mid_act, P_evap_act]
    enthalpies = [h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11]
    
    df_states = pd.DataFrame({
        "State Point": range(1, 12),
        "Description Location": state_names,
        "Pressure (kPa)": np.array(pressures) / 1000.0,
        "Enthalpy (kJ/kg)": np.array(enthalpies) / 1000.0
    })
    st.dataframe(df_states, use_container_width=True)

with tab5:
    st.subheader("📈 Pressure - Enthalpy (P-h) Diagram")
    fig_ph, ax_ph = plt.subplots(figsize=(9, 5))
    h_plot = np.array(enthalpies) / 1000.0
    p_plot = np.array(pressures) / 1000_000.0
    
    ax_ph.plot(h_plot[[0,1,2,0]], p_plot[[0,1,2,0]], 'bo--', label='Low Stage Loop')
    ax_ph.plot(h_plot[[4,6,7,8,4]], p_plot[[4,6,7,8,4]], 'ro-', label='High Stage Loop')
    ax_ph.scatter(h_plot, p_plot, color='black', zorder=5)
    
    for idx in range(11):
        ax_ph.annotate(f" {idx+1}", (h_plot[idx], p_plot[idx]), textcoords="offset points", xytext=(5,5), ha='left', fontsize=9, weight='bold')
        
    ax_ph.set_yscale('log')
    ax_ph.set_xlabel('Enthalpy (kJ/kg)')
    ax_ph.set_ylabel('Pressure (MPa)')
    ax_ph.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_ph.legend()
    st.pyplot(fig_ph)

with tab6:
    st.subheader("📉 Temperature - Entropy (T-s) Diagram")
    fig_ts, ax_ts = plt.subplots(figsize=(9, 5))
    s_list = []
    t_list = [T1, T1+30, T1+15, T1+15, T1+15, T1+15, T7, T8, T1+15, T1+15, T11]
    
    for p, h in zip(pressures, enthalpies):
        try:
            s_val = CP.PropsSI('S', 'P', p, 'H', h, refrigerant) / 1000.0
            s_list.append(s_val)
        except:
            s_list.append(1.5)
            
    ax_ts.plot(s_list, np.array(t_list) - 273.15, 'go-', label='Refrigerant Process')
    ax_ts.set_xlabel('Entropy (kJ/kg·K)')
    ax_ts.set_ylabel('Temperature (°C)')
    ax_ts.grid(True, linestyle="--", alpha=0.5)
    st.pyplot(fig_ts)