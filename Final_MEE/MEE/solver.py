"""
solver.py
=========
Thermodynamic solver for 2-stage VCR with flash tank + intercooler + mixing.
Uses CoolProp for refrigerant properties (NIST-grade accuracy).

State numbering:
  Low side (1..5, 11):
    1  Evaporator outlet (superheated vapor at P_evap)
    2  Compressor 1 exit (P_mid, superheated)
    3  Intercooler exit  (P_mid, sat vapor)
    4  Mixing chamber inlet (= state 3)
    5  Mixing chamber exit  (P_mid, sat vapor) → becomes state 6 of high side
    11 EV-2 exit (P_evap, two-phase)
  High side (6..10):
    6  Comp 2 inlet  (= state 5)
    7  Comp 2 exit   (P_cond, superheated)
    8  Condenser exit (subcooled liquid)
    9  EV-1 exit  (P_mid, two-phase)
    10 Flash tank liquid out (P_mid, sat liquid)
"""

from CoolProp.CoolProp import PropsSI

# Refrigerant CoolProp names
REFRIG_MAP = {
    "R-134a": "R134a",
    "R-410A": "R410A",
    "R-717 (NH3)": "Ammonia",
    "R-32":   "R32",
    "R-1234yf": "R1234yf",
}


def _Psat(T_C, fluid):
    """Saturation pressure at given T [°C]."""
    return PropsSI("P", "T", T_C + 273.15, "Q", 0, fluid) / 1000  # kPa


def _Tsat(P_kPa, fluid):
    """Saturation T [°C] at given P [kPa]."""
    return PropsSI("T", "P", P_kPa * 1000, "Q", 0, fluid) - 273.15


def _state_dict(T_C, P_kPa, h, s, x=None, label=""):
    return {
        "label": label,
        "T_C": T_C,
        "P_kPa": P_kPa,
        "h": h / 1000,   # J/kg → kJ/kg
        "s": s / 1000,   # J/kg·K → kJ/kg·K
        "x": x,
    }


def solve_full_system(params: dict) -> dict:
    """
    Solve 2-stage VCR with flash tank + intercooler + mixing.

    Parameters (dict):
      refrigerant   : key from REFRIG_MAP
      P_evap        : kPa
      P_mid         : kPa
      P_cond        : kPa
      dT_superheat  : K (evaporator exit superheat)
      dT_subcool    : K (condenser exit subcooling)
      eta_c1        : Compressor 1 isentropic efficiency
      eta_c2        : Compressor 2 isentropic efficiency

    Returns dict with:
      states      : dict of state dicts keyed 1..11
      y           : vapor fraction at flash tank
      W_c1_total, W_c2_total, W_total
      Q_evap, Q_cond, Q_intercool
      COP
      energy_balance : check value (≈0 if correct)
    """
    fluid = REFRIG_MAP[params["refrigerant"]]
    P_evap = params["P_evap"]
    P_mid  = params["P_mid"]
    P_cond = params["P_cond"]
    dT_sh  = params["dT_superheat"]
    dT_sc  = params["dT_subcool"]
    eta_c1 = params["eta_c1"]
    eta_c2 = params["eta_c2"]

    # Validation
    if not (P_evap < P_mid < P_cond):
        raise ValueError(f"Need P_evap < P_mid < P_cond  (got {P_evap}, {P_mid}, {P_cond})")

    # ---------- Iterate: high side ↔ low side ----------
    # Initial guess: state 6 = sat vapor at P_mid
    h6_guess = PropsSI("H", "P", P_mid * 1000, "Q", 1, fluid)
    converged = False
    iter_count = 0

    for it in range(30):
        iter_count = it + 1
        # ===== HIGH SIDE =====
        # State 6 from previous iteration
        T_sat_mid = _Tsat(P_mid, fluid)
        h6 = h6_guess
        # Compute s6 - if h6 > hg, superheated; else use quality
        h_g_mid = PropsSI("H", "P", P_mid * 1000, "Q", 1, fluid)
        if h6 >= h_g_mid - 1.0:
            s6 = PropsSI("S", "H", h6, "P", P_mid * 1000, fluid)
            T6 = PropsSI("T", "H", h6, "P", P_mid * 1000, fluid) - 273.15
            x6 = None
        else:
            h_f_mid = PropsSI("H", "P", P_mid * 1000, "Q", 0, fluid)
            x6 = (h6 - h_f_mid) / (h_g_mid - h_f_mid)
            s_f_mid = PropsSI("S", "P", P_mid * 1000, "Q", 0, fluid)
            s_g_mid = PropsSI("S", "P", P_mid * 1000, "Q", 1, fluid)
            s6 = s_f_mid + x6 * (s_g_mid - s_f_mid)
            T6 = T_sat_mid

        # State 7: Compressor 2
        h7s = PropsSI("H", "S", s6, "P", P_cond * 1000, fluid)
        h7  = h6 + (h7s - h6) / eta_c2
        T7  = PropsSI("T", "H", h7, "P", P_cond * 1000, fluid) - 273.15
        s7  = PropsSI("S", "H", h7, "P", P_cond * 1000, fluid)

        # State 8: condenser exit (subcooled)
        T_sat_cond = _Tsat(P_cond, fluid)
        T8 = T_sat_cond - dT_sc
        h8 = PropsSI("H", "T", T8 + 273.15, "P", P_cond * 1000, fluid)
        s8 = PropsSI("S", "T", T8 + 273.15, "P", P_cond * 1000, fluid)

        # State 9: throttle V-1 (isenthalpic)
        h9 = h8
        h_f_mid = PropsSI("H", "P", P_mid * 1000, "Q", 0, fluid)
        h_g_mid = PropsSI("H", "P", P_mid * 1000, "Q", 1, fluid)
        x9 = (h9 - h_f_mid) / (h_g_mid - h_f_mid)
        x9 = max(0, min(1, x9))
        s_f_mid = PropsSI("S", "P", P_mid * 1000, "Q", 0, fluid)
        s_g_mid = PropsSI("S", "P", P_mid * 1000, "Q", 1, fluid)
        s9 = s_f_mid + x9 * (s_g_mid - s_f_mid)
        T9 = T_sat_mid

        # State 10: flash tank liquid out
        h10 = h_f_mid
        s10 = s_f_mid
        T10 = T_sat_mid

        # y = vapor fraction at flash tank
        y = x9

        # ===== LOW SIDE =====
        # State 1: evaporator outlet (superheated)
        T_sat_evap = _Tsat(P_evap, fluid)
        T1 = T_sat_evap + dT_sh
        h1 = PropsSI("H", "T", T1 + 273.15, "P", P_evap * 1000, fluid)
        s1 = PropsSI("S", "T", T1 + 273.15, "P", P_evap * 1000, fluid)

        # State 2: Comp 1 exit
        h2s = PropsSI("H", "S", s1, "P", P_mid * 1000, fluid)
        h2  = h1 + (h2s - h1) / eta_c1
        T2  = PropsSI("T", "H", h2, "P", P_mid * 1000, fluid) - 273.15
        s2  = PropsSI("S", "H", h2, "P", P_mid * 1000, fluid)

        # State 3: intercooler exit (sat vapor at P_mid)
        h3 = h_g_mid
        s3 = s_g_mid
        T3 = T_sat_mid

        # State 4 = State 3
        h4, s4, T4 = h3, s3, T3

        # State 5: mixing chamber exit (1-y) from state 4 + y from flash vapor
        # In this config flash vapor = sat vapor at P_mid → same enthalpy as state 4
        # but if intercooler differs we'd have h_mix = (1-y)*h4 + y*h_g_mid
        h_vapor_flash = h_g_mid
        h5 = (1 - y) * h4 + y * h_vapor_flash
        # state 5 might be saturated or superheated
        if h5 >= h_g_mid - 1.0:
            T5 = PropsSI("T", "H", h5, "P", P_mid * 1000, fluid) - 273.15
            s5 = PropsSI("S", "H", h5, "P", P_mid * 1000, fluid)
            x5 = None
        else:
            x5 = (h5 - h_f_mid) / (h_g_mid - h_f_mid)
            s5 = s_f_mid + x5 * (s_g_mid - s_f_mid)
            T5 = T_sat_mid

        # State 11: V-2 throttle
        h11 = h10
        h_f_evap = PropsSI("H", "P", P_evap * 1000, "Q", 0, fluid)
        h_g_evap = PropsSI("H", "P", P_evap * 1000, "Q", 1, fluid)
        x11 = (h11 - h_f_evap) / (h_g_evap - h_f_evap)
        x11 = max(0, min(1, x11))
        s_f_evap = PropsSI("S", "P", P_evap * 1000, "Q", 0, fluid)
        s_g_evap = PropsSI("S", "P", P_evap * 1000, "Q", 1, fluid)
        s11 = s_f_evap + x11 * (s_g_evap - s_f_evap)
        T11 = T_sat_evap

        # Check convergence on h6
        h6_new = h5
        if abs(h6_new - h6_guess) < 100:  # 0.1 kJ/kg
            converged = True
            h6_guess = h6_new
            break
        h6_guess = h6_new

    # ---------- Performance ----------
    W_c1_per_kg = (h2 - h1) / 1000     # kJ/kg of state-1 flow
    W_c1_total  = (1 - y) * W_c1_per_kg
    W_c2_total  = (h7 - h6) / 1000     # kJ/kg of state-6 flow
    W_total     = W_c1_total + W_c2_total

    Q_evap_per_kg = (h1 - h11) / 1000
    Q_evap_total  = (1 - y) * Q_evap_per_kg

    Q_intercool_total = (1 - y) * (h2 - h3) / 1000
    Q_cond_total      = (h7 - h8) / 1000

    COP = Q_evap_total / W_total if W_total > 0 else float("nan")

    # Energy balance: heat in = heat out  →  Q_evap + W = Q_cond + Q_intercool
    energy_balance = (Q_cond_total + Q_intercool_total) - (Q_evap_total + W_total)

    # ---------- Build state dictionary ----------
    states = {
        1:  _state_dict(T1, P_evap, h1, s1, None, "Evaporator outlet"),
        2:  _state_dict(T2, P_mid,  h2, s2, None, "Comp 1 exit"),
        3:  _state_dict(T3, P_mid,  h3, s3, 1.0,  "Intercooler exit"),
        4:  _state_dict(T4, P_mid,  h4, s4, 1.0,  "Mixing inlet"),
        5:  _state_dict(T5, P_mid,  h5, s5, x5,   "Mixing exit"),
        6:  _state_dict(T6, P_mid,  h6, s6, x6,   "Comp 2 inlet"),
        7:  _state_dict(T7, P_cond, h7, s7, None, "Comp 2 exit"),
        8:  _state_dict(T8, P_cond, h8, s8, -1,   "Condenser exit (subcool)"),
        9:  _state_dict(T9, P_mid,  h9, s9, x9,   "EV-1 exit"),
        10: _state_dict(T10, P_mid, h10, s10, 0.0, "Flash liquid out"),
        11: _state_dict(T11, P_evap, h11, s11, x11, "EV-2 exit"),
    }

    return {
        "states": states,
        "y": y,
        "W_c1_total": W_c1_total,
        "W_c2_total": W_c2_total,
        "W_total":    W_total,
        "Q_evap_total":     Q_evap_total,
        "Q_cond_total":     Q_cond_total,
        "Q_intercool_total": Q_intercool_total,
        "COP": COP,
        "energy_balance": energy_balance,
        "converged": converged,
        "iter": iter_count,
        "fluid": fluid,
        "params": params,
    }


def solve_controlled(setpoints: dict, sensors: dict, config: dict) -> dict:
    """
    Solve the system using sensor readings + setpoints + config.

    setpoints: T_evap_set [°C], P_cond_set [kPa], y_set [-]
    sensors:   T_evap_actual [°C], P_cond_actual [kPa], y_actual [-]
    config:    P_mid, dT_subcool, dT_superheat, eta_c1, eta_c2, refrigerant
    """
    fluid = REFRIG_MAP[config["refrigerant"]]
    # Convert sensor T_evap → P_evap (saturation pressure)
    P_evap = _Psat(sensors["T_evap_actual"], fluid)

    params = {
        "refrigerant":  config["refrigerant"],
        "P_evap":       P_evap,
        "P_mid":        config["P_mid"],
        "P_cond":       sensors["P_cond_actual"],
        "dT_superheat": config["dT_superheat"],
        "dT_subcool":   config["dT_subcool"],
        "eta_c1":       config["eta_c1"],
        "eta_c2":       config["eta_c2"],
    }
    result = solve_full_system(params)

    # Add controller outputs
    result["controllers"] = compute_controllers(setpoints, sensors)
    result["setpoints"] = setpoints
    result["sensors"]   = sensors
    return result


def compute_controllers(setpoints: dict, sensors: dict) -> dict:
    """Compute 3 P-controller outputs."""
    # TIC-101 — Temperature
    err_T = setpoints["T_evap_set"] - sensors["T_evap_actual"]
    Kp_T = -10.0
    out_T = max(0, min(100, 50 + Kp_T * err_T))

    # PIC-101 — Pressure (reverse-acting)
    err_P = setpoints["P_cond_set"] - sensors["P_cond_actual"]
    Kp_P = 0.05
    out_P = max(0, min(100, 80 + Kp_P * err_P))

    # FIC-101 — Flow (y)
    err_y = setpoints["y_set"] - sensors["y_actual"]
    Kp_y = 200.0
    out_y = max(0, min(100, 50 + Kp_y * err_y))

    def status(err, tol):
        if abs(err) <= tol:
            return "OK"
        return "HIGH" if err < 0 else "LOW"

    return {
        "TIC": {"tag": "TIC-101", "SP": setpoints["T_evap_set"],
                "PV": sensors["T_evap_actual"], "err": err_T,
                "output": out_T, "unit": "% V-102",
                "Kp": Kp_T, "status": status(err_T, 0.5)},
        "PIC": {"tag": "PIC-101", "SP": setpoints["P_cond_set"],
                "PV": sensors["P_cond_actual"], "err": err_P,
                "output": out_P, "unit": "% K-101 speed",
                "Kp": Kp_P, "status": status(err_P, 20)},
        "FIC": {"tag": "FIC-101", "SP": setpoints["y_set"],
                "PV": sensors["y_actual"], "err": err_y,
                "output": out_y, "unit": "% V-101",
                "Kp": Kp_y, "status": status(err_y, 0.02)},
    }
