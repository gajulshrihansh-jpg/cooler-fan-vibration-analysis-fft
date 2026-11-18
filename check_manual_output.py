"""
Manual Output & Verification Tool
=================================
Vibration Analysis of a Cooler Fan Using Accelerometer Measurements and FFT
Pure Python Standard Library (no external dependencies required)

Usage:
  python check_manual_output.py
  python check_manual_output.py --config 1 --speed 20 --axis x
  python check_manual_output.py --interactive
"""

import sys
import math
import csv
from pathlib import Path
import argparse

DATASET_PATH = Path("accelerometer (1).csv")
OUTPUT_DIR = Path("outputs")
STATS_CSV = OUTPUT_DIR / "vibration_statistics.csv"
FFT_CSV = OUTPUT_DIR / "fft_results.csv"

CONFIG_NAMES = {1: "Normal", 2: "Perpendicular", 3: "Opposite"}
FS = 50.0
MAX_RPM = 1900.0
NYQUIST_HZ = FS / 2.0  # 25.0 Hz
N_SAMPLES = 3000
DURATION = 60.0
DELTA_F = FS / N_SAMPLES  # 0.0166667 Hz


def load_subset(wconfid: int, pctid: int, axis: str):
    """Load the 3000 data points for a specific condition from the raw CSV."""
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset file '{DATASET_PATH}' not found!")
    
    col_idx = {"x": 2, "y": 3, "z": 4}.get(axis.lower(), 2)
    values = []
    
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if not row or len(row) < 5:
                continue
            if int(row[0]) == wconfid and int(row[1]) == pctid:
                values.append(float(row[col_idx]))
    
    return values


def load_all_axes_subset(wconfid: int, pctid: int):
    """Load x, y, z series for a specific condition."""
    data = {"x": [], "y": [], "z": []}
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if not row or len(row) < 5:
                continue
            if int(row[0]) == wconfid and int(row[1]) == pctid:
                data["x"].append(float(row[2]))
                data["y"].append(float(row[3]))
                data["z"].append(float(row[4]))
    return data


def lookup_csv_results(wconfid: int, pctid: int, axis: str):
    """Lookup the pipeline-generated values from CSVs for comparison."""
    stats_row = None
    fft_row = None
    
    if STATS_CSV.exists():
        with open(STATS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if int(row["wconfid"]) == wconfid and int(row["pctid"]) == pctid and row["axis"].lower() == axis.lower():
                    stats_row = row
                    break
                    
    if FFT_CSV.exists():
        with open(FFT_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if int(row["wconfid"]) == wconfid and int(row["pctid"]) == pctid and row["axis"].lower() == axis.lower():
                    fft_row = row
                    break
                    
    return stats_row, fft_row


def print_manual_calculation_report(wconfid=1, pctid=20, axis="x", n_demo_points=5):
    """Generate a comprehensive manual calculation verification output."""
    conf_name = CONFIG_NAMES.get(wconfid, f"Configuration {wconfid}")
    axis = axis.lower()
    
    print("\n" + "=" * 90)
    print(f"       MANUAL CALCULATION & VERIFICATION REPORT")
    print(f"       Condition: {conf_name} (wconfid={wconfid}) | Fan Speed: {pctid}% | Axis: {axis.upper()}")
    print("=" * 90)
    
    # -------------------------------------------------------------
    # STEP 1: THEORETICAL ROTATIONAL DYNAMICS (MANUAL CALCULATION)
    # -------------------------------------------------------------
    print("\n" + "-" * 90)
    print(" STEP 1: THEORETICAL ROTATIONAL DYNAMICS (MANUAL HAND CALCULATION)")
    print("-" * 90)
    
    rpm = MAX_RPM * (pctid / 100.0)
    f_rot = rpm / 60.0
    is_aliased = f_rot > NYQUIST_HZ
    f_alias = abs(FS - f_rot) if is_aliased else None
    
    print(f"1. Fan Maximum Rated Speed (Max_RPM) : 1900.0 RPM")
    print(f"2. Fan Speed Control Setting (pctid) : {pctid}%")
    print(f"3. Theoretical Shaft RPM:")
    print(f"   Formula: RPM = Max_RPM * (pctid / 100)")
    print(f"   Manual : RPM = 1900 * ({pctid} / 100) = {rpm:.2f} RPM")
    print(f"\n4. Fundamental Rotational Frequency (f_rot):")
    print(f"   Formula: f_rot = RPM / 60")
    print(f"   Manual : f_rot = {rpm:.2f} / 60 = {f_rot:.6f} Hz")
    print(f"\n5. Nyquist Sampling Limit:")
    print(f"   Formula: f_nyquist = Fs / 2")
    print(f"   Manual : f_nyquist = 50.0 / 2 = {NYQUIST_HZ:.1f} Hz")
    print(f"\n6. Nyquist Exceedance & Aliasing Test:")
    if is_aliased:
        print(f"   Result : f_rot ({f_rot:.4f} Hz) > Nyquist Limit ({NYQUIST_HZ:.1f} Hz)  --> [ABOVE NYQUIST!]")
        print(f"   Aliasing Mechanism: The rotational frequency folds back into the [0, 25 Hz] baseband.")
        print(f"   Formula: f_alias = |Fs - f_rot|")
        print(f"   Manual : f_alias = |50.0 - {f_rot:.6f}| = {f_alias:.6f} Hz")
    else:
        print(f"   Result : f_rot ({f_rot:.4f} Hz) <= Nyquist Limit ({NYQUIST_HZ:.1f} Hz) --> [BELOW NYQUIST]")
        print(f"   Status : Resolvable without aliasing. Aliased Frequency = N/A")

    # -------------------------------------------------------------
    # STEP 2: RAW SAMPLES & TIME-DOMAIN STATISTICAL HAND CALCULATION
    # -------------------------------------------------------------
    print("\n" + "-" * 90)
    print(f" STEP 2: RAW SAMPLES & TIME-DOMAIN STATISTICAL HAND CALCULATION (Axis {axis.upper()})")
    print("-" * 90)
    
    sig = load_subset(wconfid, pctid, axis)
    N = len(sig)
    
    print(f"Total number of recorded samples (N) : {N} samples")
    print(f"Sampling interval (Δt)               : 20 ms = 0.02 s")
    print(f"Total recording time duration (T)    : N * Δt = {N} * 0.02 s = {N * 0.02:.1f} seconds")
    
    print(f"\nFirst {n_demo_points} raw accelerometer samples recorded for this condition:")
    for idx in range(min(n_demo_points, N)):
        print(f"   x[{idx}] = {sig[idx]:+.4f} g")
        
    # Manual calculation formulas demonstrated on sample subset:
    demo_slice = sig[:n_demo_points]
    slice_sum = sum(demo_slice)
    slice_mean = slice_sum / n_demo_points
    slice_sq_sum = sum(x ** 2 for x in demo_slice)
    slice_rms = math.sqrt(slice_sq_sum / n_demo_points)
    
    print(f"\n--- Demonstrative Manual Calculation on the first {n_demo_points} points ---")
    print(f"  Sum(x[0..{n_demo_points-1}]) = " + " + ".join([f"({x:+.4f})" for x in demo_slice]) + f" = {slice_sum:+.4f}")
    print(f"  Mean_demo   = {slice_sum:+.4f} / {n_demo_points} = {slice_mean:+.6f} g")
    print(f"  Sum(x^2)    = " + " + ".join([f"({x:+.4f})^2" for x in demo_slice]) + f" = {slice_sq_sum:.6f}")
    print(f"  RMS_demo    = sqrt({slice_sq_sum:.6f} / {n_demo_points}) = sqrt({slice_sq_sum/n_demo_points:.6f}) = {slice_rms:.6f} g")
    
    # Full dataset exact calculations:
    mean_full = sum(sig) / N
    variance_full = sum((x - mean_full) ** 2 for x in sig) / (N - 1)
    std_full = math.sqrt(variance_full)
    rms_full = math.sqrt(sum(x ** 2 for x in sig) / N)
    min_full = min(sig)
    max_full = max(sig)
    p2p_full = max_full - min_full
    peak_abs_full = max(abs(x) for x in sig)
    
    print(f"\n--- Full Dataset ({N} samples) Exact Manual Calculations ---")
    print(f"1. Arithmetic Mean (μ):")
    print(f"   Formula: μ = (1/N) * Σ(x[n])")
    print(f"   Manual : μ = {sum(sig):.4f} / {N} = {mean_full:.6f} g")
    if axis == "x":
        print(f"   Note   : Mean is near ~1.0 g due to static gravitational acceleration on vertical axis.")
    else:
        print(f"   Note   : Mean is near 0.0 g (dynamic axis without permanent 1g gravity offset).")
        
    print(f"\n2. Sample Standard Deviation (σ):")
    print(f"   Formula: σ = sqrt( (1 / (N - 1)) * Σ(x[n] - μ)^2 )")
    print(f"   Manual : σ = sqrt( {variance_full:.8f} ) = {std_full:.6f} g")
    
    print(f"\n3. Root Mean Square (RMS):")
    print(f"   Formula: RMS = sqrt( (1/N) * Σ(x[n]^2) )")
    print(f"   Manual : RMS = sqrt( {sum(x**2 for x in sig)/N:.8f} ) = {rms_full:.6f} g")
    
    print(f"\n4. Minimum & Maximum:")
    print(f"   Min = {min_full:+.6f} g")
    print(f"   Max = {max_full:+.6f} g")
    
    print(f"\n5. Peak-to-Peak (P2P):")
    print(f"   Formula: P2P = Max - Min")
    print(f"   Manual : P2P = {max_full:+.4f} - ({min_full:+.4f}) = {p2p_full:.6f} g")
    
    print(f"\n6. Absolute Peak (Peak_abs):")
    print(f"   Formula: Peak_abs = max(|x[n]|)")
    print(f"   Manual : Peak_abs = {peak_abs_full:.6f} g")
    if peak_abs_full >= 7.99:
        print(f"   WARNING: Value hits sensor dynamic limits (±8.0 g rail clipping)!")

    # -------------------------------------------------------------
    # STEP 3: VECTOR TOTAL RMS (ACROSS X, Y, Z)
    # -------------------------------------------------------------
    print("\n" + "-" * 90)
    print(" STEP 3: SPATIAL VECTOR TOTAL RMS CALCULATION")
    print("-" * 90)
    all_data = load_all_axes_subset(wconfid, pctid)
    rms_x = math.sqrt(sum(x ** 2 for x in all_data["x"]) / N)
    rms_y = math.sqrt(sum(y ** 2 for y in all_data["y"]) / N)
    rms_z = math.sqrt(sum(z ** 2 for z in all_data["z"]) / N)
    rms_total = math.sqrt(rms_x ** 2 + rms_y ** 2 + rms_z ** 2)
    
    print(f"RMS_x = {rms_x:.6f} g")
    print(f"RMS_y = {rms_y:.6f} g")
    print(f"RMS_z = {rms_z:.6f} g")
    print(f"\nFormula: RMS_total = sqrt( RMS_x^2 + RMS_y^2 + RMS_z^2 )")
    print(f"Manual : RMS_total = sqrt( ({rms_x:.4f})^2 + ({rms_y:.4f})^2 + ({rms_z:.4f})^2 )")
    print(f"       = sqrt( {rms_x**2:.6f} + {rms_y**2:.6f} + {rms_z**2:.6f} )")
    print(f"       = sqrt( {rms_total**2:.6f} ) = {rms_total:.6f} g")

    # -------------------------------------------------------------
    # STEP 4: FREQUENCY-DOMAIN & FFT MATHEMATICS
    # -------------------------------------------------------------
    print("\n" + "-" * 90)
    print(" STEP 4: FREQUENCY-DOMAIN SPECIFICATIONS & FFT HAND CALCULATION")
    print("-" * 90)
    print(f"1. Sampling Frequency (Fs)        : {FS:.1f} Hz (Δt = 0.02 s)")
    print(f"2. Record Length (N)              : {N_SAMPLES} samples")
    print(f"3. Discrete Frequency Resolution  : Δf = Fs / N = 50 / 3000 = {DELTA_F:.6f} Hz")
    print(f"4. Observable Nyquist Bandwidth   : 0 Hz to {NYQUIST_HZ:.1f} Hz (N/2 + 1 = 1501 discrete spectral lines)")
    
    print("\n5. Step-by-Step FFT Preprocessing Pipeline:")
    print("   a. Mean Centering (DC Offset Removal):")
    print("      x_detrended[n] = x[n] - μ")
    print("      (Eliminates the 0 Hz DC spike caused by static gravity)")
    print("   b. Hann Window Application:")
    print("      w[n] = 0.5 * (1 - cos(2 * π * n / (N - 1)))")
    print("      x_w[n] = x_detrended[n] * w[n]")
    print("      (Suppresses spectral leakage sidelobes by >31 dB)")
    print("   c. Discrete Fourier Transform (DFT / rFFT):")
    print("      X[k] = Σ (n=0 to N-1) x_w[n] * e^(-j * 2 * π * k * n / N)")
    print("   d. Coherent Amplitude Normalization:")
    print("      Sum of Hann window weights: S1 = Σ w[n] ≈ N / 2 = 1500.0")
    print("      A[k] = (2 / S1) * |X[k]| = (4 / N) * |X[k]|  (for 0 < k < N/2)")
    
    # -------------------------------------------------------------
    # STEP 5: 4-POINT MANUAL DFT WORKED EXAMPLE DEMONSTRATION
    # -------------------------------------------------------------
    print("\n" + "-" * 90)
    print(" STEP 5: WORKED EXAMPLE: 4-POINT MANUAL DFT (MATHEMATICAL PROOF)")
    print("-" * 90)
    print("To demonstrate how the Fourier Transform works manually, let's calculate a 4-point DFT:")
    print("Given 4 samples: x = [1.0, 0.0, -1.0, 0.0] (a clean 1 Hz sinusoid sampled at 4 Hz)")
    print("DFT Formula: X[k] = Σ_{n=0}^{3} x[n] * e^(-j * 2 * π * k * n / 4)")
    print("Where e^(-j * θ) = cos(θ) - j * sin(θ), and W_4 = e^(-j * 2π/4) = -j")
    
    demo_x = [1.0, 0.0, -1.0, 0.0]
    for k in range(3):  # k = 0, 1, 2
        terms_real = []
        terms_imag = []
        for n in range(4):
            angle = 2 * math.pi * k * n / 4
            c = math.cos(angle)
            s = math.sin(angle)
            terms_real.append(demo_x[n] * c)
            terms_imag.append(-demo_x[n] * s)
        re_sum = sum(terms_real)
        im_sum = sum(terms_imag)
        mag = math.sqrt(re_sum ** 2 + im_sum ** 2)
        norm_amp = (2.0 / 4.0) * mag if k > 0 else (1.0 / 4.0) * mag
        freq_k = k * (4.0 / 4.0)
        print(f"\n   k = {k} (Freq = {freq_k:.1f} Hz):")
        print(f"     Real Part X_re[{k}] = " + " + ".join([f"{r:+.2f}" for r in terms_real]) + f" = {re_sum:.2f}")
        print(f"     Imag Part X_im[{k}] = " + " + ".join([f"{m:+.2f}" for m in terms_imag]) + f" = {im_sum:.2f}")
        print(f"     Magnitude |X[{k}]|   = sqrt(({re_sum:.2f})^2 + ({im_sum:.2f})^2) = {mag:.2f}")
        print(f"     Normalized Amp A[{k}] = {norm_amp:.2f} g  {'<-- PEAK DETECTED AT 1.0 Hz!' if norm_amp == 1.0 else ''}")

    # -------------------------------------------------------------
    # STEP 6: VERIFICATION AGAINST PIPELINE CSV RESULTS
    # -------------------------------------------------------------
    print("\n" + "-" * 90)
    print(" STEP 6: CROSS-VERIFICATION AGAINST PIPELINE CSV DATABASE")
    print("-" * 90)
    stats_row, fft_row = lookup_csv_results(wconfid, pctid, axis)
    
    if stats_row:
        print("Comparison: Manual Python Standard Math vs. Pipeline CSV Output:")
        print(f"{'Metric':<20} | {'Manual Calculation':<20} | {'Pipeline CSV':<20} | {'Agreement':<10}")
        print("-" * 75)
        
        comps = [
            ("Mean (g)", mean_full, float(stats_row["mean_g"])),
            ("Std Dev (g)", std_full, float(stats_row["std_g"])),
            ("RMS (g)", rms_full, float(stats_row["rms_g"])),
            ("Min (g)", min_full, float(stats_row["min_g"])),
            ("Max (g)", max_full, float(stats_row["max_g"])),
            ("Peak-to-Peak (g)", p2p_full, float(stats_row["peak_to_peak_g"])),
            ("Peak Abs (g)", peak_abs_full, float(stats_row["peak_abs_g"])),
        ]
        
        for name, m_val, c_val in comps:
            diff = abs(m_val - c_val)
            status = "MATCH (100%)" if diff < 1e-4 else f"Diff={diff:.6f}"
            print(f"{name:<20} | {m_val:<20.6f} | {c_val:<20.6f} | {status:<10}")
    else:
        print("Note: outputs/vibration_statistics.csv not found to cross-reference.")
        
    if fft_row:
        print("\nFFT Pipeline Output for this Condition:")
        print(f"  Dominant Frequency Measured : {fft_row['dominant_freq_hz']} Hz")
        print(f"  Dominant Amplitude Measured : {fft_row['dominant_amplitude_g']} g")
        print(f"  Theoretical Shaft Freq      : {fft_row['theoretical_f_rot_hz']} Hz")
        print(f"  Above Nyquist Status        : {fft_row['is_above_nyquist']}")
        if fft_row['aliased_f_rot_hz']:
            print(f"  Expected Aliased Frequency  : {fft_row['aliased_f_rot_hz']} Hz")
            
    print("=" * 90 + "\n")


def interactive_menu():
    print("\n" + "=" * 60)
    print("   MANUAL OUTPUT CHECKER - INTERACTIVE SELECTION")
    print("=" * 60)
    print("Available Weight Configurations:")
    print("  1 = Normal Configuration (Red)")
    print("  2 = Perpendicular Configuration (Blue)")
    print("  3 = Opposite Configuration (Green)")
    
    try:
        w_in = input("Enter configuration (1, 2, or 3) [default: 1]: ").strip()
        wconfid = int(w_in) if w_in in ["1", "2", "3"] else 1
        
        speed_in = input("Enter fan speed percentage (20 to 100 in steps of 5) [default: 20]: ").strip()
        pctid = int(speed_in) if speed_in.isdigit() and int(speed_in) in range(20, 105, 5) else 20
        
        axis_in = input("Enter axis (x, y, or z) [default: x]: ").strip().lower()
        axis = axis_in if axis_in in ["x", "y", "z"] else "x"
        
        print_manual_calculation_report(wconfid, pctid, axis)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Check manual calculation output for any test condition.")
    parser.add_argument("--config", "-c", type=int, default=None, choices=[1, 2, 3], help="Weight configuration: 1 (Normal), 2 (Perpendicular), 3 (Opposite)")
    parser.add_argument("--speed", "-s", type=int, default=None, help="Fan speed percentage: 20 to 100 (in 5% steps)")
    parser.add_argument("--axis", "-a", type=str, default="x", choices=["x", "y", "z"], help="Measurement axis: x, y, or z")
    parser.add_argument("--demo_points", "-d", type=int, default=5, help="Number of demo points to display in hand calculation")
    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive menu")
    
    args = parser.parse_args()
    
    if args.interactive:
        interactive_menu()
    elif args.config is None and args.speed is None and len(sys.argv) == 1:
        # Default run with sample condition Config 1, 20%, x
        print_manual_calculation_report(wconfid=1, pctid=20, axis="x", n_demo_points=args.demo_points)
        print("Tip: To check any other condition, run:")
        print("     python check_manual_output.py --config <1|2|3> --speed <20..100> --axis <x|y|z>")
        print("     python check_manual_output.py --interactive")
    else:
        cfg = args.config if args.config is not None else 1
        spd = args.speed if args.speed is not None else 20
        print_manual_calculation_report(
            wconfid=cfg,
            pctid=spd,
            axis=args.axis,
            n_demo_points=args.demo_points
        )


if __name__ == "__main__":
    main()
