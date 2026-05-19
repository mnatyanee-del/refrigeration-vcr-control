"""Quick test of solver without UI."""
from solver import solve_controlled

setpoints = {"T_evap_set": -10, "P_cond_set": 1000, "y_set": 0.10}
sensors   = {"T_evap_actual": -10, "P_cond_actual": 1000, "y_actual": 0.10}
config    = {"refrigerant": "R-134a", "P_mid": 500,
             "dT_superheat": 5, "dT_subcool": 5,
             "eta_c1": 0.85, "eta_c2": 0.85}

result = solve_controlled(setpoints, sensors, config)

print(f"\n=== {result['fluid']} ===")
print(f"COP            = {result['COP']:.3f}")
print(f"W_total        = {result['W_total']:.2f}  kJ/kg")
print(f"Q_evap_total   = {result['Q_evap_total']:.2f}  kJ/kg")
print(f"Q_cond_total   = {result['Q_cond_total']:.2f}  kJ/kg")
print(f"Q_intercool    = {result['Q_intercool_total']:.2f}  kJ/kg")
print(f"y              = {result['y']:.4f}")
print(f"Energy balance = {result['energy_balance']:.4f}  (≈0 OK)")
print(f"Converged      = {result['converged']} in {result['iter']} iter\n")

print("State | T [°C]  | P [kPa] | h [kJ/kg] | s [kJ/kg·K] | x")
print("------+---------+---------+-----------+-------------+----")
for i in [1,2,3,4,5,6,7,8,9,10,11]:
    s = result["states"][i]
    x = f"{s['x']:.3f}" if isinstance(s['x'], float) else "  -  "
    print(f"  {i:2d}  | {s['T_C']:7.2f} | {s['P_kPa']:7.1f} | "
          f"{s['h']:9.2f} | {s['s']:11.4f} | {x}")

print("\nControllers:")
for key in ["TIC", "PIC", "FIC"]:
    c = result["controllers"][key]
    print(f"  {c['tag']}: SP={c['SP']:.3f} PV={c['PV']:.3f} "
          f"Err={c['err']:+.3f} Out={c['output']:.1f}% [{c['status']}]")

# Test with disturbance
print("\n\n=== WITH DISTURBANCE ===")
sensors = {"T_evap_actual": -8, "P_cond_actual": 1100, "y_actual": 0.13}
result = solve_controlled(setpoints, sensors, config)
print(f"COP = {result['COP']:.3f} (dropped from baseline)")
for key in ["TIC", "PIC", "FIC"]:
    c = result["controllers"][key]
    print(f"  {c['tag']}: PV={c['PV']:.3f} Err={c['err']:+.3f} Out={c['output']:.1f}% [{c['status']}]")
print(f"Energy balance = {result['energy_balance']:.4f}")
