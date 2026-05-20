"""
plots.py
========
Interactive Plotly diagrams: P-h, T-s, and P&ID.
"""

import os
import numpy as np
import plotly.graph_objects as go
from CoolProp.CoolProp import PropsSI
from PIL import Image


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
# Helpers: state hover, critical point, isotherms/isobars, state marker
# =========================================================================
def _state_hover(states, i):
    """Hovertext for a state point."""
    return (
        f"<b>State {i}</b> ({states[i]['label']})<br>"
        f"T = {states[i]['T_C']:.2f} °C<br>"
        f"P = {states[i]['P_kPa']:.1f} kPa<br>"
        f"h = {states[i]['h']:.2f} kJ/kg<br>"
        f"s = {states[i]['s']:.4f} kJ/kg·K"
    )


def _critical_point(fluid):
    """Return (T_crit [°C], P_crit [kPa], h_crit [kJ/kg], s_crit [kJ/kg·K])."""
    T_crit = PropsSI("Tcrit", fluid)
    P_crit = PropsSI("pcrit", fluid) / 1000
    try:
        h_crit = PropsSI("H", "T", T_crit - 0.5, "Q", 0.5, fluid) / 1000
        s_crit = PropsSI("S", "T", T_crit - 0.5, "Q", 0.5, fluid) / 1000
    except Exception:
        h_crit = None
        s_crit = None
    return T_crit - 273.15, P_crit, h_crit, s_crit


def _isobar_in_Ts(fluid, P_kPa, T_min_C=-40, T_max_C=80, n=40):
    """Return (s, T) points along constant-P line for T-s diagram."""
    P_Pa = P_kPa * 1000
    try:
        T_sat = PropsSI("T", "P", P_Pa, "Q", 0, fluid)
    except Exception:
        return np.array([]), np.array([])
    s_list, T_list = [], []
    # Subcooled liquid section
    T_sub = np.linspace(T_min_C + 273.15, T_sat - 0.01, n // 3)
    for T in T_sub:
        try:
            s_list.append(PropsSI("S", "T", T, "P", P_Pa, fluid) / 1000)
            T_list.append(T - 273.15)
        except Exception:
            pass
    # Two-phase
    try:
        s_f = PropsSI("S", "P", P_Pa, "Q", 0, fluid) / 1000
        s_g = PropsSI("S", "P", P_Pa, "Q", 1, fluid) / 1000
        s_list.append(s_f); T_list.append(T_sat - 273.15)
        s_list.append(s_g); T_list.append(T_sat - 273.15)
    except Exception:
        pass
    # Superheat
    T_sup = np.linspace(T_sat + 0.01, T_max_C + 273.15, n // 2)
    for T in T_sup:
        try:
            s_list.append(PropsSI("S", "T", T, "P", P_Pa, fluid) / 1000)
            T_list.append(T - 273.15)
        except Exception:
            pass
    return np.array(s_list), np.array(T_list)


def _isotherm_in_Ph(fluid, T_C, P_low_kPa=50, P_high_kPa=5000, n=40):
    """Return (h, P) points along constant-T line for P-h diagram."""
    T_K = T_C + 273.15
    h_list, P_list = [], []
    try:
        P_sat = PropsSI("P", "T", T_K, "Q", 0, fluid)
    except Exception:
        P_sat = None
    if P_sat is not None and P_sat < P_high_kPa * 1000:
        P_sub = np.geomspace(P_sat + 1, P_high_kPa * 1000, n // 2)
        for P in P_sub:
            try:
                h_list.append(PropsSI("H", "T", T_K, "P", P, fluid) / 1000)
                P_list.append(P / 1000)
            except Exception:
                pass
        h_list = h_list[::-1]; P_list = P_list[::-1]
        try:
            h_list.append(PropsSI("H", "T", T_K, "Q", 0, fluid) / 1000)
            P_list.append(P_sat / 1000)
            h_list.append(PropsSI("H", "T", T_K, "Q", 1, fluid) / 1000)
            P_list.append(P_sat / 1000)
        except Exception:
            pass
    if P_sat is not None:
        P_sup = np.geomspace(P_sat - 1, P_low_kPa * 1000, n // 2)
    else:
        P_sup = np.geomspace(P_high_kPa * 1000, P_low_kPa * 1000, n)
    for P in P_sup:
        try:
            h_list.append(PropsSI("H", "T", T_K, "P", P, fluid) / 1000)
            P_list.append(P / 1000)
        except Exception:
            pass
    return np.array(h_list), np.array(P_list)


def _add_state_marker(fig, x, y, num, hover_text):
    """Add a state point marker with number label."""
    fig.add_trace(go.Scatter(
        x=[x], y=[y], mode="markers+text",
        marker=dict(size=10, color="yellow",
                    line=dict(color="black", width=1.5)),
        text=[f"<b>{num}</b>"], textposition="top right",
        textfont=dict(size=11, color="black"),
        hovertext=[hover_text], hoverinfo="text",
        showlegend=False
    ))


# =========================================================================
# P-h Diagram (with Critical Point + isotherms)
# =========================================================================
def plot_ph_diagram(result):
    states = result["states"]
    fluid  = result["fluid"]

    h_f, h_g, _, _, T_arr, P_arr = _saturation_dome(fluid)
    T_crit_C, P_crit, h_crit, _ = _critical_point(fluid)

    fig = go.Figure()

    # ---- Saturation dome ----
    fig.add_trace(go.Scatter(
        x=h_f, y=P_arr, mode="lines", name="Sat. liquid",
        line=dict(color="black", width=1.5), hoverinfo="skip"
    ))
    fig.add_trace(go.Scatter(
        x=h_g, y=P_arr, mode="lines", name="Sat. vapor",
        line=dict(color="black", width=1.5), hoverinfo="skip"
    ))

    # ---- Isotherms (constant T lines) ----
    T_evap = states[1]["T_C"]
    T_mid  = states[6]["T_C"]
    T_cond = states[7]["T_C"]
    T_choice = sorted({
        round(T_evap, 1),
        round(T_mid, 1),
        round(T_cond, 1),
        round((T_cond + T_crit_C) / 2, 1),
    })
    for j, T_C in enumerate(T_choice):
        h_iso, P_iso = _isotherm_in_Ph(fluid, T_C)
        if len(h_iso) > 2:
            fig.add_trace(go.Scatter(
                x=h_iso, y=P_iso, mode="lines",
                line=dict(color="rgba(150,150,150,0.6)",
                          width=1, dash="dot"),
                name=f"T = {T_C:.0f} °C",
                hoverinfo="skip",
                showlegend=(j < 3),
            ))

    # ---- Cycle: Low side (blue) ----
    low_order = [11, 1, 2, 3, 4, 5]
    h_low = [states[i]["h"] for i in low_order]
    P_low = [states[i]["P_kPa"] for i in low_order]
    fig.add_trace(go.Scatter(
        x=h_low, y=P_low, mode="lines",
        line=dict(color="blue", width=2.5),
        name="Low side", hoverinfo="skip"
    ))

    # ---- Cycle: High side (red) ----
    high_order = [6, 7, 8, 9, 10]
    h_high = [states[i]["h"] for i in high_order]
    P_high = [states[i]["P_kPa"] for i in high_order]
    fig.add_trace(go.Scatter(
        x=h_high, y=P_high, mode="lines",
        line=dict(color="red", width=2.5),
        name="High side", hoverinfo="skip"
    ))

    # Interface lines
    fig.add_trace(go.Scatter(
        x=[states[5]["h"], states[6]["h"]],
        y=[states[5]["P_kPa"], states[6]["P_kPa"]],
        mode="lines",
        line=dict(color="green", width=2, dash="dash"),
        name="5→6 interface", hoverinfo="skip"
    ))
    fig.add_trace(go.Scatter(
        x=[states[10]["h"], states[11]["h"]],
        y=[states[10]["P_kPa"], states[11]["P_kPa"]],
        mode="lines",
        line=dict(color="purple", width=2, dash="dash"),
        name="10→11 (EV-2)", hoverinfo="skip"
    ))

    # ---- State point markers ----
    for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]:
        _add_state_marker(fig, states[i]["h"], states[i]["P_kPa"],
                          i, _state_hover(states, i))

    # ---- Critical Point ----
    if h_crit is not None:
        fig.add_trace(go.Scatter(
            x=[h_crit], y=[P_crit], mode="markers+text",
            marker=dict(size=14, color="darkviolet", symbol="star",
                        line=dict(color="black", width=1.5)),
            text=["<b>CP</b>"], textposition="top right",
            textfont=dict(size=12, color="darkviolet"),
            name="Critical Point",
            hovertext=(f"<b>Critical Point</b><br>"
                       f"T = {T_crit_C:.2f} °C<br>"
                       f"P = {P_crit:.1f} kPa<br>"
                       f"h ≈ {h_crit:.1f} kJ/kg"),
            hoverinfo="text"
        ))

    fig.update_layout(
        title=f"P-h Diagram — {fluid} | COP = {result['COP']:.2f}",
        xaxis_title="Enthalpy h [kJ/kg]",
        yaxis_title="Pressure P [kPa]",
        yaxis_type="log",
        hovermode="closest",
        template="plotly_white",
        height=600,
        legend=dict(
            yanchor="top", y=0.99,
            xanchor="left", x=1.02,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="gray", borderwidth=1,
            font=dict(size=10)
        ),
    )
    return fig


# =========================================================================
# T-s Diagram (with Critical Point + isobars)
# =========================================================================
def plot_ts_diagram(result):
    states = result["states"]
    fluid  = result["fluid"]

    _, _, s_f, s_g, T_arr, _ = _saturation_dome(fluid)
    T_crit_C, P_crit, _, s_crit = _critical_point(fluid)

    fig = go.Figure()

    # ---- Saturation dome ----
    fig.add_trace(go.Scatter(
        x=s_f, y=T_arr, mode="lines", name="Sat. liquid",
        line=dict(color="black", width=1.5), hoverinfo="skip"
    ))
    fig.add_trace(go.Scatter(
        x=s_g, y=T_arr, mode="lines", name="Sat. vapor",
        line=dict(color="black", width=1.5), hoverinfo="skip"
    ))

    # ---- Isobars ----
    P_evap = states[1]["P_kPa"]
    P_mid  = states[6]["P_kPa"]
    P_cond = states[7]["P_kPa"]
    P_choice = sorted({
        round(P_evap, 1),
        round(P_mid, 1),
        round(P_cond, 1),
    })
    for j, P_kPa in enumerate(P_choice):
        s_iso, T_iso = _isobar_in_Ts(fluid, P_kPa)
        if len(s_iso) > 2:
            fig.add_trace(go.Scatter(
                x=s_iso, y=T_iso, mode="lines",
                line=dict(color="rgba(150,150,150,0.6)",
                          width=1, dash="dot"),
                name=f"P = {P_kPa:.0f} kPa",
                hoverinfo="skip",
                showlegend=True,
            ))

    # ---- Low side (blue) ----
    low_order = [11, 1, 2, 3, 4, 5]
    s_low = [states[i]["s"] for i in low_order]
    T_low = [states[i]["T_C"] for i in low_order]
    fig.add_trace(go.Scatter(
        x=s_low, y=T_low, mode="lines",
        line=dict(color="blue", width=2.5),
        name="Low side", hoverinfo="skip"
    ))

    # ---- High side (red) ----
    high_order = [6, 7, 8, 9, 10]
    s_high = [states[i]["s"] for i in high_order]
    T_high = [states[i]["T_C"] for i in high_order]
    fig.add_trace(go.Scatter(
        x=s_high, y=T_high, mode="lines",
        line=dict(color="red", width=2.5),
        name="High side", hoverinfo="skip"
    ))

    # Interfaces
    fig.add_trace(go.Scatter(
        x=[states[5]["s"], states[6]["s"]],
        y=[states[5]["T_C"], states[6]["T_C"]],
        mode="lines",
        line=dict(color="green", width=2, dash="dash"),
        name="5→6 interface", hoverinfo="skip"
    ))
    fig.add_trace(go.Scatter(
        x=[states[10]["s"], states[11]["s"]],
        y=[states[10]["T_C"], states[11]["T_C"]],
        mode="lines",
        line=dict(color="purple", width=2, dash="dash"),
        name="10→11 (EV-2)", hoverinfo="skip"
    ))

    # ---- State markers ----
    for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]:
        _add_state_marker(fig, states[i]["s"], states[i]["T_C"],
                          i, _state_hover(states, i))

    # ---- Critical Point ----
    if s_crit is not None:
        fig.add_trace(go.Scatter(
            x=[s_crit], y=[T_crit_C], mode="markers+text",
            marker=dict(size=14, color="darkviolet", symbol="star",
                        line=dict(color="black", width=1.5)),
            text=["<b>CP</b>"], textposition="top right",
            textfont=dict(size=12, color="darkviolet"),
            name="Critical Point",
            hovertext=(f"<b>Critical Point</b><br>"
                       f"T = {T_crit_C:.2f} °C<br>"
                       f"P = {P_crit:.1f} kPa<br>"
                       f"s ≈ {s_crit:.4f} kJ/kg·K"),
            hoverinfo="text"
        ))

    fig.update_layout(
        title=f"T-s Diagram — {fluid} | COP = {result['COP']:.2f}",
        xaxis_title="Entropy s [kJ/kg·K]",
        yaxis_title="Temperature T [°C]",
        hovermode="closest",
        template="plotly_white",
        height=600,
        legend=dict(
            yanchor="top", y=0.99,
            xanchor="left", x=1.02,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="gray", borderwidth=1,
            font=dict(size=10)
        ),
    )
    return fig


# =========================================================================
# P&ID Diagram
# =========================================================================
def plot_pid(result):
    """
    โหลดรูปภาพ P&ID เป็นพื้นหลัง และปักหมุดกล่อง Live Values
    """
    states = result["states"]
    ctrl = result.get("controllers", None)

    fig = go.Figure()

    # =========================================================================
    # 1. การโหลดรูปภาพมาทำเป็น Background
    # =========================================================================
    # ใช้ absolute path เทียบจากตำแหน่ง plots.py ให้ทำงานได้บน Streamlit Cloud
    base_dir = os.path.dirname(os.path.abspath(__file__))
    img_filename = None
    for fname in ("def.jpg", "abc.png"):
        candidate = os.path.join(base_dir, fname)
        if os.path.exists(candidate):
            img_filename = candidate
            break

    if img_filename:
        try:
            img = Image.open(img_filename)
            fig.add_layout_image(
                dict(
                    source=img,
                    xref="x",
                    yref="y",
                    x=0,
                    y=100,
                    sizex=100,
                    sizey=100,
                    sizing="stretch",
                    opacity=1.0,
                    layer="below"
                )
            )
        except Exception:
            pass

    # =========================================================================
    # 2. ฟังก์ชันเสริมสำหรับกล่องข้อความ
    # =========================================================================
    def add_live_box(x, y, text, bg_color="rgba(245, 248, 253, 0.95)", border_color="#1565c0"):
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

    # =========================================================================
    # 3. กล่อง Live Values (Controllers)
    # =========================================================================
    if ctrl is not None:
        fic_text = f"<b>FIC-101 (EV-1)</b><br>SP: {ctrl['FIC']['SP']:.3f}<br>PV: {ctrl['FIC']['PV']:.3f}<br>OUT: {ctrl['FIC']['output']:.0f}%"
        add_live_box(x=10, y=73, text=fic_text, border_color="#f9a825", bg_color="rgba(255, 249, 220, 0.95)")

        tic_text = f"<b>TIC-101 (EV-2)</b><br>SP: {ctrl['TIC']['SP']:.1f}°C<br>PV: {ctrl['TIC']['PV']:.1f}<br>OUT: {ctrl['TIC']['output']:.0f}%"
        add_live_box(x=31, y=35, text=tic_text, border_color="#ef5350", bg_color="rgba(255, 235, 238, 0.95)")

        pic_text = f"<b>PIC-101 (K-102)</b><br>SP: {ctrl['PIC']['SP']:.0f} kPa<br>PV: {ctrl['PIC']['PV']:.0f}<br>OUT: {ctrl['PIC']['output']:.0f}%"
        add_live_box(x=89, y=72, text=pic_text, border_color="#1e88e5", bg_color="rgba(220, 237, 250, 0.95)")

    # --- Local Indicators ---
    add_live_box(x=80, y=22, text=f"<b>TT-101</b><br>{states[1]['T_C']:.1f}°C",
                 border_color="#ec407a", bg_color="rgba(252, 228, 236, 0.95)")
    add_live_box(x=72, y=82, text=f"<b>PT-101</b><br>{states[7]['P_kPa']:.0f} kPa",
                 border_color="#42a5f5", bg_color="rgba(225, 245, 254, 0.95)")
    add_live_box(x=11, y=21, text=f"<b>FT-101</b><br>T={states[10]['T_C']:.1f}°C",
                 border_color="#f9a825", bg_color="rgba(255, 249, 220, 0.95)")

    # =========================================================================
    # 4. Layout — ไม่ใช้ scaleanchor เพื่อให้รูปกางเต็ม canvas
    # =========================================================================
    fig.update_layout(
        showlegend=False,
        template="plotly_white",
        xaxis=dict(range=[0, 100], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=True),
        yaxis=dict(range=[0, 100], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=True),
        height=600,
        autosize=True,
        margin=dict(l=5, r=5, t=20, b=5),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    return fig
