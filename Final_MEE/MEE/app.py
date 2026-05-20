"""
app.py
======
Streamlit interactive web app for 2-stage VCR with flash tank + control.

Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from solver import solve_controlled, REFRIG_MAP
from plots  import plot_ph_diagram, plot_ts_diagram, plot_pid

# =========================================================================
# Page config
# =========================================================================
st.set_page_config(
    page_title="2-Stage VCR with Control",
    page_icon="❄️",
    layout="wide",
)

# =========================================================================
# Sidebar — inputs
# =========================================================================
with st.sidebar:
    st.header("Configuration")
    refrigerant = st.selectbox("Refrigerant", list(REFRIG_MAP.keys()), index=0, key="refrig_in_container")
    # 1. กลุ่มพารามิเตอร์พื้นฐานของระบบ (ยุบรวมไว้ใน Expander เพื่อความสะอาดตา)
    with st.expander("Cycle Parameters", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            P_mid       = st.number_input("P_mid [kPa]", 50, 3000, 500, step=25)
            dT_subcool  = st.number_input("ΔT_subcool [K]", 0, 30, 5, step=1)
            eta_c1      = st.slider("η_C1 (Low-Stage)", 0.50, 1.00, 0.85, step=0.01)
        with col2:
            dT_superheat = st.number_input("ΔT_superheat [K]", 0, 30, 5, step=1)
            eta_c2       = st.slider("η_C2 (High-Stage)", 0.50, 1.00, 0.85, step=0.01)
    st.markdown("""
        <style>
        /* ลูปอุณหภูมิ TIC - กรอบสีแดง/ส้มจางๆ */
        div[data-testid="stVerticalBlockBorderWrapper"]:nth-of-type(1) div[data-testid="stVerticalBlock"] {
            border-color: #ef5350 !important;
            background-color: #fffbfa;
        }
        /* ลูปความดัน PIC - กรอบสีน้ำเงิน/ฟ้า */
        div[data-testid="stVerticalBlockBorderWrapper"]:nth-of-type(2) div[data-testid="stVerticalBlock"] {
            border-color: #1e88e5 !important;
            background-color: #f7faff;
        }
        /* ลูปอัตราไหล FIC - กรอบสีเขียว */
        div[data-testid="stVerticalBlockBorderWrapper"]:nth-of-type(3) div[data-testid="stVerticalBlock"] {
            border-color: #43a047 !important;
            background-color: #fafdffa;
        }
        </style>
    """, unsafe_allow_html=True)

    # เพื่อให้ปุ่ม Reset/Random ทำงานผ่าน st.session_state ได้อย่างถูกต้อง
    if "dist_T" not in st.session_state: st.session_state.dist_T = 0.0
    if "dist_P" not in st.session_state: st.session_state.dist_P = 0
    if "dist_y" not in st.session_state: st.session_state.dist_y = 0.0

    with st.container(border=True):
        st.markdown("<h4 style='margin:0;color:#c62828;'>TIC-101</h4>", unsafe_allow_html=True)
        sub_col1, sub_col2 = st.columns([1, 1])
        with sub_col1:
            st.markdown("**Setpoint**")
            T_evap_set = st.number_input("T_evap [°C]", -40, 20, -10, step=1, key="input_tic_sp")
        with sub_col2:
            st.markdown("**Disturbance**")
            dist_T = st.number_input("ΔT_evap [°C]", -5.0, 5.0, step=0.1)
    with st.container(border=True):
        st.markdown("<h4 style='margin:0;color:#1e88e5;'>PIC-101</h4>", unsafe_allow_html=True)
        sub_col3, sub_col4 = st.columns([1, 1])
        with sub_col3:
            st.markdown("**Setpoint**")
            P_cond_set = st.number_input("P_cond [kPa]", 200, 3000, 1000, step=25)
        with sub_col4:
            st.markdown("**Disturbance**")
            dist_P = st.number_input("ΔP_cond [kPa]", -200, 200, )

    with st.container(border=True):
        st.markdown("<h4 style='margin:0;color:#43a047;'>FIC-101</h4>", unsafe_allow_html=True)
        sub_col5, sub_col6 = st.columns([1, 1])
        with sub_col5:
            st.markdown("**Setpoint**")
            y_set = st.number_input("Flash Ratio y [-]", 0.01, 0.50, 0.10, step=0.01)
        with sub_col6:
            st.markdown("**Disturbance**")
            dist_y = st.number_input("Δy disturbance [-]", -0.05, 0.05, )

    st.divider()
    st.markdown("🛠️ **Quick Simulation Actions**")
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("⇄ Clear Disturb", use_container_width=True, help="ล้างค่ารบกวนให้เป็น 0 ทั้งหมด"):
            st.session_state.dist_T = 0.0
            st.session_state.dist_P = 0
            st.session_state.dist_y = 0.0
            st.rerun()
    with col_btn2:
        if st.button("⚠️ Inject Random", use_container_width=True, help="สุ่มค่า Disturbance เพื่อทดสอบคอนโทรลเลอร์"):
            st.session_state.dist_T = float(np.random.uniform(-3, 3))
            st.session_state.dist_P = int(np.random.uniform(-100, 100))
            st.session_state.dist_y = float(np.random.uniform(-0.03, 0.03))
            st.rerun()

T_evap_actual = T_evap_set + dist_T
P_cond_actual = P_cond_set + dist_P
y_actual      = max(0.005, y_set + dist_y)
# =========================================================================
# Solve
# =========================================================================
setpoints = {"T_evap_set": T_evap_set, "P_cond_set": P_cond_set, "y_set": y_set}
sensors   = {"T_evap_actual": T_evap_actual, "P_cond_actual": P_cond_actual,
             "y_actual": y_actual}
config    = {"refrigerant": refrigerant, "P_mid": P_mid,
             "dT_superheat": dT_superheat, "dT_subcool": dT_subcool,
             "eta_c1": eta_c1, "eta_c2": eta_c2}

try:
    result = solve_controlled(setpoints, sensors, config)
except ValueError as e:
    st.error(f"⚠️ {e}")
    st.stop()
except Exception as e:
    st.error(f"❌ Solve failed: {e}")
    st.stop()

# =========================================================================
# KPI styles + custom bar styles
# =========================================================================
st.markdown("""
    <style>
    .kpi-container {
        display: flex;
        gap: 12px;
        margin-bottom: 10px;
    }
    .kpi-card {
        flex: 1;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px 16px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
        text-align: left;
    }
    .kpi-title {
        font-size: 0.85rem;
        color: #666666;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #111111;
        font-family: 'Segoe UI', Roboto, Helvetica, sans-serif;
    }
    .cop-card {
        border-left: 5px solid #1e88e5 !important;
        background-color: #f7faff;
    }
    .cop-value {
        color: #1565c0;
    }

    /* Custom colored progress bars (for %CO output) */
    .co-bar-wrap {
        background-color: #eeeeee;
        border-radius: 6px;
        height: 14px;
        width: 100%;
        overflow: hidden;
        margin-top: 4px;
        margin-bottom: 14px;
        border: 1px solid #d0d0d0;
    }
    .co-bar-fill {
        height: 100%;
        border-radius: 5px;
        transition: width 0.3s ease;
    }
    .co-bar-tic  { background: linear-gradient(90deg, #ef5350, #c62828); }
    .co-bar-pic  { background: linear-gradient(90deg, #42a5f5, #1565c0); }
    .co-bar-fic  { background: linear-gradient(90deg, #66bb6a, #2e7d32); }
    </style>
""", unsafe_allow_html=True)

bal = result["energy_balance"]
bal_status_html = ""
if abs(bal) < 0.5:
    bal_status_html = f"<span style='color:#2e7d32; font-weight:bold;'>✓ OK (Δ={bal:.4f})</span>"
else:
    bal_status_html = f"<span style='color:#c62828; font-weight:bold;'>⚠ OFF (Δ={bal:.4f})</span>"

st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-card cop-card">
            <div class="kpi-title">📈 System COP</div>
            <div class="kpi-value cop-value">{result['COP']:.2f}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">⚡ W_total</div>
            <div class="kpi-value">{result['W_total']:.1f} <span style='font-size:1rem; font-weight:normal; color:#666;'>kJ/kg</span></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">❄️ Q_evap</div>
            <div class="kpi-value">{result['Q_evap_total']:.1f} <span style='font-size:1rem; font-weight:normal; color:#666;'>kJ/kg</span></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">🔥 Q_cond</div>
            <div class="kpi-value">{result['Q_cond_total']:.1f} <span style='font-size:1rem; font-weight:normal; color:#666;'>kJ/kg</span></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">💨 Vapor Frac (y)</div>
            <div class="kpi-value">{result['y']:.3f}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">⚖️ Energy Balance</div>
            <div class="kpi-value" style="font-size: 1.15rem; margin-top: 8px;">{bal_status_html}</div>
        </div>
    </div>
""", unsafe_allow_html=True)

st.write("")
# =========================================================================
# Tabs
# =========================================================================
tab1, tab2 = st.tabs([
    "Control Status",
    "Summary"
])

# =========================================================================
# TAB 1 — Control Status
# =========================================================================
with tab1:
    ctrl = result["controllers"]
    df_ctrl = pd.DataFrame([
        {"Tag": ctrl["TIC"]["tag"], "Purpose": "T_evap control",
         "SP": f"{ctrl['TIC']['SP']:.2f}", "PV": f"{ctrl['TIC']['PV']:.2f}",
         "Error": f"{ctrl['TIC']['err']:+.3f}",
         "Output": f"{ctrl['TIC']['output']:.1f} %",
         "Final Element": "V-102 (EV-2)",
         "Status": ctrl["TIC"]["status"]},
        {"Tag": ctrl["PIC"]["tag"], "Purpose": "P_cond control",
         "SP": f"{ctrl['PIC']['SP']:.1f}", "PV": f"{ctrl['PIC']['PV']:.1f}",
         "Error": f"{ctrl['PIC']['err']:+.2f}",
         "Output": f"{ctrl['PIC']['output']:.1f} %",
         "Final Element": "K-101 speed",
         "Status": ctrl["PIC"]["status"]},
        {"Tag": ctrl["FIC"]["tag"], "Purpose": "Flash y control",
         "SP": f"{ctrl['FIC']['SP']:.4f}", "PV": f"{ctrl['FIC']['PV']:.4f}",
         "Error": f"{ctrl['FIC']['err']:+.4f}",
         "Output": f"{ctrl['FIC']['output']:.1f} %",
         "Final Element": "V-101 (EV-1)",
         "Status": ctrl["FIC"]["status"]},
    ])

    col_pid, col_ind, col_ctrl = st.columns([3, 1, 1])

    with col_pid:
        st.plotly_chart(plot_pid(result), use_container_width=True)

    with col_ind:
        st.subheader("Sensor")
        st.metric("TT-101 (T discharge K-101)", f"{result['states'][7]['T_C']:.2f} °C")
        st.markdown("<br>", unsafe_allow_html=True)
        st.metric("PT-101 (P at flash tank)", f"{result['states'][6]['P_kPa']:.0f} kPa")
        st.markdown("<br>", unsafe_allow_html=True)
        st.metric("FT-101 (T Comp 1 inlet)", f"{result['states'][1]['T_C']:.2f} °C")

    # ---- %CO column with custom-colored progress bars ----
    with col_ctrl:
        st.subheader("%CO")

        # mapping ของแต่ละลูป: (tag, error, output, css class สำหรับสีบาร์)
        bar_specs = [
            ("TIC", "co-bar-tic"),   # แดง
            ("PIC", "co-bar-pic"),   # น้ำเงิน
            ("FIC", "co-bar-fic"),   # เขียว
        ]
        for key, bar_class in bar_specs:
            out = ctrl[key]["output"]
            err = ctrl[key]["err"]
            tag = ctrl[key]["tag"]

            st.metric(
                f"{tag} output",
                f"{out:.1f} %",
                delta=f"err = {err:+.3f}"
            )
            # แสดงบาร์สีแบบกำหนดเอง แทน st.progress() ที่เปลี่ยนสีไม่ได้
            width_pct = max(0, min(100, out))
            st.markdown(
                f"""
                <div class="co-bar-wrap">
                    <div class="co-bar-fill {bar_class}" style="width:{width_pct}%;"></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

# =========================================================================
# TAB 2 — Summary
# =========================================================================
with tab2:
    states = result["states"]
    rows = []
    for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]:
        s = states[i]
        if s["x"] is None:
            ph = "superheat"
        elif s["x"] < 0:
            ph = "subcool"
        elif s["x"] == 0:
            ph = "sat. liquid"
        elif s["x"] == 1:
            ph = "sat. vapor"
        else:
            ph = f"x={s['x']:.3f}"
        side = "Low" if i in [1, 2, 3, 4, 5, 11] else "High"
        rows.append({
            "State": i,
            "Side":  side,
            "Description": s["label"],
            "T [°C]":  round(s["T_C"], 2),
            "P [kPa]": round(s["P_kPa"], 1),
            "h [kJ/kg]": round(s["h"], 2),
            "s [kJ/kg·K]": round(s["s"], 4),
            "Phase": ph,
        })
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 P-h Diagram")
        st.plotly_chart(plot_ph_diagram(result), use_container_width=True)

    with col2:
        st.subheader("📊 T-s Diagram")
        st.plotly_chart(plot_ts_diagram(result), use_container_width=True)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.subheader("Energy Balance Check")
    st.markdown(f"""
    ```
    Q_cond + Q_intercool  =  W_total + Q_evap
    {result['Q_cond_total']:.3f} + {result['Q_intercool_total']:.3f}  =  {result['W_total']:.3f} + {result['Q_evap_total']:.3f}
    {result['Q_cond_total']+result['Q_intercool_total']:.3f}  ≈  {result['W_total']+result['Q_evap_total']:.3f}
    Δ = {result['energy_balance']:.4f}  ✓
    ```
    """)

    csv_data = pd.DataFrame(rows).to_csv(index=False)
    st.download_button(
        "💾 Download Summary as CSV",
        csv_data,
        file_name=f"states_{result['fluid']}.csv",
        mime="text/csv",
    )

# =========================================================================
# Footer
# =========================================================================
st.divider()
with st.expander("ℹ️ About this simulator"):
    st.markdown(f"""
    **System:** Two-stage vapor compression refrigeration with flash tank, intercooler, and mixing chamber.

    **Property data:** [CoolProp](http://www.coolprop.org/) — NIST-grade accuracy.

    **Current refrigerant:** `{result['fluid']}`  
    **Convergence:** {result['converged']} (in {result['iter']} iterations)

    **Equipment tags (ISA):**
    - K-101, K-102 — Compressors
    - E-101, E-102, E-103 — Heat exchangers (Condenser, Intercooler, Evaporator)
    - V-101, V-102 — Expansion valves
    - T-101 — Flash tank
    - M-101 — Mixing chamber
    
    **Instrument tags (ISA-5.1):**
    - TT/PT/FT — Transmitters (sensors)
    - TIC/PIC/FIC — Indicating controllers
    - TI/PI — Indicators (read-only)
    """)
