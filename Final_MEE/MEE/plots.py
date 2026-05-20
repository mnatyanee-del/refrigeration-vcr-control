"""
plots.py
========
Interactive Plotly diagrams: P-h, T-s, and P&ID.
"""

import numpy as np
import plotly.graph_objects as go
from CoolProp.CoolProp import PropsSI



# =========================================================================
# Saturation dome generator
# =========================================================================
def _saturation_dome(fluid, n=80):
    """Return (h_f, h_g, s_f, s_g, T, P) along saturation dome."""
    T_min = PropsSI("T_triple", fluid)
    T_crit = PropsSI("T_critical", fluid)
    T_range = np.linspace(max(T_min + 1, T_crit - 200), T_crit - 0.5, n)
    h_f, h_g, s_f, s_g, P_arr, T_arr = [], [], [], [], [], []
    for T in T_range:
        try:
            h_f.append(PropsSI("H", "T", T, "Q", 0, fluid) / 1000)
            h_g.append(PropsSI("H", "T", T, "Q", 1, fluid) / 1000)
            s_f.append(PropsSI("S", "T", T, "Q", 0, fluid) / 1000)
            s_g.append(PropsSI("S", "T", T, "Q", 1, fluid) / 1000)
            P_arr.append(PropsSI("P", "T", T, "Q", 0, fluid) / 1000)
            T_arr.append(T - 273.15)
        except Exception:
            continue
    return (np.array(h_f), np.array(h_g),
            np.array(s_f), np.array(s_g),
            np.array(T_arr), np.array(P_arr))


# =========================================================================
# P-h Diagram
# =========================================================================
def plot_ph_diagram(result):
    states = result["states"]
    fluid = result["fluid"]

    h_f, h_g, s_f, s_g, T_arr, P_arr = _saturation_dome(fluid)

    fig = go.Figure()
    # Saturation dome
    fig.add_trace(go.Scatter(
        x=h_f, y=P_arr, mode="lines", name="Sat. liquid",
        line=dict(color="black", width=1.5),
        hovertemplate="h=%{x:.1f}<br>P=%{y:.0f}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=h_g, y=P_arr, mode="lines", name="Sat. vapor",
        line=dict(color="black", width=1.5),
        hovertemplate="h=%{x:.1f}<br>P=%{y:.0f}<extra></extra>"
    ))

    # Low side: 11 → 1 → 2 → 3 → 4 → 5
    low_order = [11, 1, 2, 3, 4, 5]
    h_low = [states[i]["h"] for i in low_order]
    P_low = [states[i]["P_kPa"] for i in low_order]
    text_low = [f"{i}" for i in low_order]
    hover_low = [
        f"<b>State {i}</b> ({states[i]['label']})<br>"
        f"T={states[i]['T_C']:.2f}°C<br>"
        f"P={states[i]['P_kPa']:.1f} kPa<br>"
        f"h={states[i]['h']:.2f} kJ/kg<br>"
        f"s={states[i]['s']:.4f} kJ/kg·K"
        for i in low_order
    ]
    fig.add_trace(go.Scatter(
        x=h_low, y=P_low, mode="lines+markers+text",
        text=text_low, textposition="top center",
        marker=dict(size=10, color="blue"),
        line=dict(color="blue", width=2.5),
        name="Low side", hovertext=hover_low, hoverinfo="text"
    ))

    # High side: 6 → 7 → 8 → 9 → 10
    high_order = [6, 7, 8, 9, 10]
    h_high = [states[i]["h"] for i in high_order]
    P_high = [states[i]["P_kPa"] for i in high_order]
    text_high = [f"{i}" for i in high_order]
    hover_high = [
        f"<b>State {i}</b> ({states[i]['label']})<br>"
        f"T={states[i]['T_C']:.2f}°C<br>"
        f"P={states[i]['P_kPa']:.1f} kPa<br>"
        f"h={states[i]['h']:.2f} kJ/kg<br>"
        f"s={states[i]['s']:.4f} kJ/kg·K"
        for i in high_order
    ]
    fig.add_trace(go.Scatter(
        x=h_high, y=P_high, mode="lines+markers+text",
        text=text_high, textposition="top center",
        marker=dict(size=10, color="red", symbol="square"),
        line=dict(color="red", width=2.5),
        name="High side", hovertext=hover_high, hoverinfo="text"
    ))

    # Interfaces
    fig.add_trace(go.Scatter(
        x=[states[5]["h"], states[6]["h"]],
        y=[states[5]["P_kPa"], states[6]["P_kPa"]],
        mode="lines", line=dict(color="green", width=2, dash="dash"),
        name="5→6 interface", showlegend=True
    ))
    fig.add_trace(go.Scatter(
        x=[states[10]["h"], states[11]["h"]],
        y=[states[10]["P_kPa"], states[11]["P_kPa"]],
        mode="lines", line=dict(color="purple", width=2, dash="dash"),
        name="10→11 (EV-2)", showlegend=True
    ))

    fig.update_layout(
        title=f"P-h Diagram — {result['fluid']} | COP = {result['COP']:.2f}",
        xaxis_title="Enthalpy h [kJ/kg]",
        yaxis_title="Pressure P [kPa]",
        yaxis_type="log",
        hovermode="closest",
        template="plotly_white",
        height=550,
    )
    return fig


# =========================================================================
# T-s Diagram
# =========================================================================
def plot_ts_diagram(result):
    states = result["states"]
    fluid = result["fluid"]

    h_f, h_g, s_f, s_g, T_arr, P_arr = _saturation_dome(fluid)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=s_f, y=T_arr, mode="lines", name="Sat. liquid",
        line=dict(color="black", width=1.5)
    ))
    fig.add_trace(go.Scatter(
        x=s_g, y=T_arr, mode="lines", name="Sat. vapor",
        line=dict(color="black", width=1.5)
    ))

    low_order = [11, 1, 2, 3, 4, 5]
    s_low = [states[i]["s"] for i in low_order]
    T_low = [states[i]["T_C"] for i in low_order]
    text_low = [f"{i}" for i in low_order]
    hover_low = [
        f"<b>State {i}</b> ({states[i]['label']})<br>"
        f"T={states[i]['T_C']:.2f}°C<br>"
        f"s={states[i]['s']:.4f} kJ/kg·K"
        for i in low_order
    ]
    fig.add_trace(go.Scatter(
        x=s_low, y=T_low, mode="lines+markers+text",
        text=text_low, textposition="top center",
        marker=dict(size=10, color="blue"),
        line=dict(color="blue", width=2.5),
        name="Low side", hovertext=hover_low, hoverinfo="text"
    ))

    high_order = [6, 7, 8, 9, 10]
    s_high = [states[i]["s"] for i in high_order]
    T_high = [states[i]["T_C"] for i in high_order]
    text_high = [f"{i}" for i in high_order]
    hover_high = [
        f"<b>State {i}</b> ({states[i]['label']})<br>"
        f"T={states[i]['T_C']:.2f}°C<br>"
        f"s={states[i]['s']:.4f} kJ/kg·K"
        for i in high_order
    ]
    fig.add_trace(go.Scatter(
        x=s_high, y=T_high, mode="lines+markers+text",
        text=text_high, textposition="top center",
        marker=dict(size=10, color="red", symbol="square"),
        line=dict(color="red", width=2.5),
        name="High side", hovertext=hover_high, hoverinfo="text"
    ))

    fig.add_trace(go.Scatter(
        x=[states[5]["s"], states[6]["s"]],
        y=[states[5]["T_C"], states[6]["T_C"]],
        mode="lines", line=dict(color="green", width=2, dash="dash"),
        name="5→6 interface"
    ))
    fig.add_trace(go.Scatter(
        x=[states[10]["s"], states[11]["s"]],
        y=[states[10]["T_C"], states[11]["T_C"]],
        mode="lines", line=dict(color="purple", width=2, dash="dash"),
        name="10→11 (EV-2)"
    ))

    fig.update_layout(
        title=f"T-s Diagram — {result['fluid']} | COP = {result['COP']:.2f}",
        xaxis_title="Entropy s [kJ/kg·K]",
        yaxis_title="Temperature T [°C]",
        hovermode="closest",
        template="plotly_white",
        height=550,
    )
    return fig
import plotly.graph_objects as go

# =========================================================================
# P&ID Diagram
# =========================================================================
import os
import plotly.graph_objects as go
from PIL import Image

def plot_pid(result):
    """
    โหลดรูปภาพ P&ID ล่าสุดเป็นพื้นหลัง 
    และปักหมุดกล่อง Live Values พร้อมตัวเลข State 1-11 ตรงตามตำแหน่งในภาพเป๊ะๆ
    """
    states = result["states"]
    ctrl = result.get("controllers", None)

    fig = go.Figure()

    # =========================================================================
    # 1. การโหลดรูปภาพมาทำเป็น Background
    # =========================================================================
    # ใช้ absolute path เทียบจากตำแหน่งของ plots.py เพื่อให้ทำงานได้บน Streamlit Cloud
    img_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), "abc.png")
    
    if os.path.exists(img_filename):
        try:
            img = Image.open(img_filename)
            fig.add_layout_image(
                dict(
                    source=img,
                    xref="x",
                    yref="y",
                    x=0,
                    y=100,       # เริ่มต้นมุมซ้ายบนของแกนพล็อต
                    sizex=100,
                    sizey=100,   # กางเต็มพื้นที่ 100x100
                    sizing="stretch",
                    opacity=1.0,
                    layer="below" # อยู่ใต้ข้อความและมาร์กเกอร์ทั้งหมด
                )
            )
        except Exception as e:
            pass

    # =========================================================================
    # 2. ฟังก์ชันเสริมสำหรับกล่องข้อความและตัวเลข State
    # =========================================================================
    def add_live_box(x, y, text, bg_color="rgba(245, 248, 253, 0.95)", border_color="#1565c0"):
        """สร้างกล่องสี่เหลี่ยมแสดงค่าคอนโทรลเลอร์หรือเซนเซอร์ (สไตล์ SCADA)"""
        fig.add_annotation(
            x=x, y=y,
            text=text,
            showarrow=False,
            font=dict(size=9.5, family="Courier New, monospace", color="#111111"),
            align="left",
            bordercolor=border_color,
            borderwidth=1.5,
            borderpad=4,
            bgcolor=bg_color,
            opacity=0.95
        )

    def add_state_label(x, y, num):
        """สร้างวงกลมมาร์กเกอร์เลขสถานะสตรีม (State) สีม่วง/ครีม ลอยทับเส้นท่อ"""
        fig.add_annotation(
            x=x, y=y,
            text=f"<b>{num}</b>",
            showarrow=False,
            font=dict(size=9.5, color="#5e35b1"),
            bordercolor="#5e35b1",
            borderwidth=1.5,
            borderpad=3,
            bgcolor="#fffde7"
        )

    # =========================================================================
    # 3. ปักหมุดกล่องข้อมูลสด (Live Data Boxes) ทับลงบนกล่อง FIC/TIC/PIC ในรูป
    # =========================================================================
    # หมายเหตุ: ภาพ P&ID มี State 1-11 อยู่แล้ว จึงไม่ต้องวาดทับ
    if ctrl is not None:
        # กล่อง FIC-101 (Flash Ratio Valve) -> ทับกล่องสีเหลือง FIC-101 ในรูป (ซ้ายบน)
        fic_text = f"<b>FIC-101 (EV-1)</b><br>SP: {ctrl['FIC']['SP']:.3f}<br>PV: {ctrl['FIC']['PV']:.3f}<br>OUT: {ctrl['FIC']['output']:.0f}%"
        add_live_box(x=10, y=73, text=fic_text, border_color="#f9a825", bg_color="rgba(255, 249, 220, 0.95)")

        # กล่อง TIC-101 (Evaporator Temp) -> ทับกล่องสีชมพู TIC-101 ในรูป (กลางล่าง)
        tic_text = f"<b>TIC-101 (EV-2)</b><br>SP: {ctrl['TIC']['SP']:.1f}°C<br>PV: {ctrl['TIC']['PV']:.1f}<br>OUT: {ctrl['TIC']['output']:.0f}%"
        add_live_box(x=31, y=35, text=tic_text, border_color="#ef5350", bg_color="rgba(255, 235, 238, 0.95)")

        # กล่อง PIC-101 (Condenser Press) -> ทับกล่องสีฟ้า PIC-101 ในรูป (ขวาบน)
        pic_text = f"<b>PIC-101 (K-102)</b><br>SP: {ctrl['PIC']['SP']:.0f} kPa<br>PV: {ctrl['PIC']['PV']:.0f}<br>OUT: {ctrl['PIC']['output']:.0f}%"
        add_live_box(x=89, y=72, text=pic_text, border_color="#1e88e5", bg_color="rgba(220, 237, 250, 0.95)")

    # --- เซ็นเซอร์วัดค่าหน้างาน (Local Indicators) ---
    # TT-101: อุณหภูมิที่ออกจาก Evaporator (State 1) - ทับวงกลม TT-101 สีชมพูในรูป
    add_live_box(x=80, y=22, text=f"<b>TT-101</b><br>{states[1]['T_C']:.1f}°C", border_color="#ec407a", bg_color="rgba(252, 228, 236, 0.95)")
    
    # PT-101: ความดันก่อนเข้า Condenser (State 7) - ทับวงกลม PT-101 สีฟ้าในรูป
    add_live_box(x=72, y=82, text=f"<b>PT-101</b><br>{states[7]['P_kPa']:.0f} kPa", border_color="#42a5f5", bg_color="rgba(225, 245, 254, 0.95)")
    
    # FT-101: อัตราการไหลของเหลวออกจาก Flash Tank (State 10) - ทับวงกลม FT-101 สีเหลืองในรูป
    add_live_box(x=11, y=21, text=f"<b>FT-101</b><br>T={states[10]['T_C']:.1f}°C", border_color="#f9a825", bg_color="rgba(255, 249, 220, 0.95)")

    # =========================================================================
    # 5. การตั้งค่าหน้าแคนวาสพล็อต (Canvas Layout)
    # =========================================================================
    fig.update_layout(
        showlegend=False,
        template="plotly_white",
        # ล็อกพิกัดแกนและซ่อนสเกล Grid ทั้งหมดเพื่อให้แสดงผลภาพพื้นหลังได้เนียนตาที่สุด
        xaxis=dict(range=[0, 100], showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(range=[0, 100], showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1),
        height=680,
        margin=dict(l=5, r=5, t=50, b=5),
    )
    
    return fig
