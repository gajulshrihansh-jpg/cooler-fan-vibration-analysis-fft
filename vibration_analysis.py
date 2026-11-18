"""
Vibration Analysis Pipeline - Phase 2 & Phase 3
------------------------------------------------
Dataset: accelerometer (1).csv
Sampling Frequency (Fs): 50 Hz
Number of Samples per Condition (N): 3000
Duration: 60 seconds
Nyquist Frequency: 25 Hz
Maximum Fan Speed: 1900 RPM

Configurations:
  1 = Normal / Red
  2 = Perpendicular / Blue
  3 = Opposite / Green
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ---------------------------------------------------------
# CONSTANTS & CONFIGURATIONS
# ---------------------------------------------------------
DATASET_PATH = Path("accelerometer (1).csv")
OUTPUT_DIR = Path("outputs")
FIGURES_DIR = OUTPUT_DIR / "figures"

FS = 50.0  # Sampling frequency in Hz
N_SAMPLES = 3000  # Number of samples per condition
DURATION_SEC = 60.0  # Recording duration in seconds
NYQUIST_HZ = FS / 2.0  # Nyquist frequency: 25 Hz
FREQ_RESOLUTION_HZ = FS / N_SAMPLES  # Resolution: 50 / 3000 = 0.0166667 Hz
MAX_RPM = 1900.0  # Fan maximum speed in RPM

CONFIG_NAMES = {
    1: "Normal",
    2: "Perpendicular",
    3: "Opposite"
}

CONFIG_COLORS = {
    1: "#d62728",  # Red
    2: "#1f77b4",  # Blue
    3: "#2ca02c"   # Green
}

AXES = ["x", "y", "z"]


def ensure_directories():
    """Ensure output directories exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INIT] Output directories confirmed: {OUTPUT_DIR.resolve()} and {FIGURES_DIR.resolve()}")


def load_dataset() -> pd.DataFrame:
    """Load dataset without modifying the original file."""
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATASET_PATH.resolve()}")
    print(f"[DATA] Loading dataset from {DATASET_PATH.name}...")
    df = pd.read_csv(DATASET_PATH)
    print(f"[DATA] Loaded {len(df):,} rows and {len(df.columns)} columns.")
    return df


# ---------------------------------------------------------
# PHASE 2: TIME-DOMAIN ANALYSIS
# ---------------------------------------------------------
def run_time_domain_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Perform time-domain statistical analysis for every combination of
    wconfid and pctid, for x, y, and z axes separately.
    """
    print("[PHASE 2] Executing time-domain statistical analysis...")
    records = []

    wconf_vals = sorted(df["wconfid"].unique())
    pctid_vals = sorted(df["pctid"].unique())

    for wconf in wconf_vals:
        conf_name = CONFIG_NAMES.get(wconf, f"Config_{wconf}")
        for pct in pctid_vals:
            rpm = MAX_RPM * pct / 100.0
            subset = df[(df["wconfid"] == wconf) & (df["pctid"] == pct)]

            for axis in AXES:
                sig = subset[axis].values
                n_count = len(sig)

                mean_val = float(np.mean(sig))
                std_val = float(np.std(sig, ddof=1))
                rms_val = float(np.sqrt(np.mean(sig ** 2)))
                min_val = float(np.min(sig))
                max_val = float(np.max(sig))
                p2p_val = float(max_val - min_val)
                peak_abs_val = float(np.max(np.abs(sig)))

                records.append({
                    "wconfid": int(wconf),
                    "configuration_name": conf_name,
                    "pctid": int(pct),
                    "rpm": round(rpm, 2),
                    "axis": axis,
                    "sample_count": n_count,
                    "duration_sec": DURATION_SEC,
                    "mean_g": round(mean_val, 6),
                    "std_g": round(std_val, 6),
                    "rms_g": round(rms_val, 6),
                    "min_g": round(min_val, 6),
                    "max_g": round(max_val, 6),
                    "peak_to_peak_g": round(p2p_val, 6),
                    "peak_abs_g": round(peak_abs_val, 6)
                })

    stats_df = pd.DataFrame(records)
    stats_out_path = OUTPUT_DIR / "vibration_statistics.csv"
    stats_df.to_csv(stats_out_path, index=False)
    print(f"[PHASE 2] Generated: {stats_out_path.name} with {len(stats_df)} records.")
    return stats_df


# ---------------------------------------------------------
# PHASE 3: FFT ANALYSIS
# ---------------------------------------------------------
def run_fft_analysis(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Perform FFT frequency-domain analysis:
    - Detrend signal (signal - mean)
    - Apply Hann window
    - Compute single-sided spectrum via rfft
    - Properly normalize amplitude
    - Exclude 0 Hz to determine dominant frequency and amplitude
    - Calculate theoretical rotational frequency & aliasing
    """
    print("[PHASE 3] Executing FFT spectral analysis...")
    records = []
    spectrum_cache = {}

    wconf_vals = sorted(df["wconfid"].unique())
    pctid_vals = sorted(df["pctid"].unique())

    # Hann window for N samples
    win = np.hanning(N_SAMPLES)
    win_sum = np.sum(win)
    freqs = np.fft.rfftfreq(N_SAMPLES, d=1.0 / FS)

    for wconf in wconf_vals:
        conf_name = CONFIG_NAMES.get(wconf, f"Config_{wconf}")
        for pct in pctid_vals:
            rpm = MAX_RPM * pct / 100.0
            f_rot = rpm / 60.0
            is_above_nyquist = bool(f_rot > NYQUIST_HZ)
            aliased_f_rot = round(abs(FS - f_rot), 6) if is_above_nyquist else np.nan

            subset = df[(df["wconfid"] == wconf) & (df["pctid"] == pct)]

            for axis in AXES:
                sig = subset[axis].values
                sig_detrended = sig - np.mean(sig)

                # Windowed FFT
                fft_complex = np.fft.rfft(sig_detrended * win)

                # Normalized one-sided amplitude spectrum
                amplitude = (2.0 / win_sum) * np.abs(fft_complex)
                amplitude[0] /= 2.0  # DC normalization
                if len(amplitude) == len(freqs) and (N_SAMPLES % 2 == 0):
                    amplitude[-1] /= 2.0  # Nyquist bin normalization

                # Cache spectrum for plotting representative figures
                spectrum_cache[(wconf, pct, axis)] = (freqs, amplitude)

                # Exclude 0 Hz (DC) for dominant frequency identification
                nonzero_mask = freqs > 0.0
                search_freqs = freqs[nonzero_mask]
                search_amps = amplitude[nonzero_mask]

                dom_idx = int(np.argmax(search_amps))
                dom_freq = float(search_freqs[dom_idx])
                dom_amp = float(search_amps[dom_idx])

                records.append({
                    "wconfid": int(wconf),
                    "configuration_name": conf_name,
                    "pctid": int(pct),
                    "rpm": round(rpm, 2),
                    "axis": axis,
                    "dominant_freq_hz": round(dom_freq, 6),
                    "dominant_amplitude_g": round(dom_amp, 6),
                    "theoretical_f_rot_hz": round(f_rot, 6),
                    "nyquist_limit_hz": round(NYQUIST_HZ, 1),
                    "is_above_nyquist": is_above_nyquist,
                    "aliased_f_rot_hz": aliased_f_rot,
                    "freq_resolution_hz": round(FREQ_RESOLUTION_HZ, 7)
                })

    fft_df = pd.DataFrame(records)
    fft_out_path = OUTPUT_DIR / "fft_results.csv"
    fft_df.to_csv(fft_out_path, index=False)
    print(f"[PHASE 3] Generated: {fft_out_path.name} with {len(fft_df)} records.")
    return fft_df, spectrum_cache


# ---------------------------------------------------------
# COMPARISON TABLES GENERATION
# ---------------------------------------------------------
def generate_comparison_csvs(stats_df: pd.DataFrame, fft_df: pd.DataFrame):
    """
    Generate speed_comparison.csv and configuration_comparison.csv.
    """
    print("[ANALYSIS] Generating comparison CSVs...")

    # Merge time-domain and FFT results
    merged = pd.merge(
        stats_df,
        fft_df,
        on=["wconfid", "configuration_name", "pctid", "rpm", "axis"]
    )

    # 1. SPEED COMPARISON: Progression across speeds for each configuration
    speed_records = []
    for (wconf, conf_name, pct, rpm), group in merged.groupby(["wconfid", "configuration_name", "pctid", "rpm"]):
        f_rot = group["theoretical_f_rot_hz"].iloc[0]
        above_nyq = group["is_above_nyquist"].iloc[0]
        alias_f = group["aliased_f_rot_hz"].iloc[0]

        row_dict = {
            "wconfid": wconf,
            "configuration_name": conf_name,
            "pctid": pct,
            "rpm": rpm,
            "theoretical_f_rot_hz": f_rot,
            "is_above_nyquist": above_nyq,
            "aliased_f_rot_hz": alias_f,
        }

        # Axis-specific metrics
        rms_vals = []
        for ax in AXES:
            ax_data = group[group["axis"] == ax].iloc[0]
            row_dict[f"rms_{ax}_g"] = ax_data["rms_g"]
            row_dict[f"p2p_{ax}_g"] = ax_data["peak_to_peak_g"]
            row_dict[f"dom_freq_{ax}_hz"] = ax_data["dominant_freq_hz"]
            row_dict[f"dom_amp_{ax}_g"] = ax_data["dominant_amplitude_g"]
            rms_vals.append(ax_data["rms_g"])

        # Vector total RMS: sqrt(x_rms^2 + y_rms^2 + z_rms^2)
        row_dict["rms_total_g"] = round(float(np.sqrt(np.sum(np.array(rms_vals) ** 2))), 6)
        speed_records.append(row_dict)

    speed_comp_df = pd.DataFrame(speed_records)
    speed_comp_df = speed_comp_df.sort_values(by=["wconfid", "pctid"]).reset_index(drop=True)
    speed_out_path = OUTPUT_DIR / "speed_comparison.csv"
    speed_comp_df.to_csv(speed_out_path, index=False)
    print(f"[ANALYSIS] Generated: {speed_out_path.name} with {len(speed_comp_df)} records.")

    # 2. CONFIGURATION COMPARISON: Comparison between configurations at each speed
    config_records = []
    for (pct, rpm), group in merged.groupby(["pctid", "rpm"]):
        f_rot = group["theoretical_f_rot_hz"].iloc[0]

        # Total RMS and max peak-to-peak for each config
        normal_data = group[group["wconfid"] == 1]
        perp_data = group[group["wconfid"] == 2]
        opp_data = group[group["wconfid"] == 3]

        norm_rms_tot = float(np.sqrt(np.sum(normal_data["rms_g"].values ** 2)))
        perp_rms_tot = float(np.sqrt(np.sum(perp_data["rms_g"].values ** 2)))
        opp_rms_tot = float(np.sqrt(np.sum(opp_data["rms_g"].values ** 2)))

        norm_p2p_max = float(np.max(normal_data["peak_to_peak_g"]))
        perp_p2p_max = float(np.max(perp_data["peak_to_peak_g"]))
        opp_p2p_max = float(np.max(opp_data["peak_to_peak_g"]))

        norm_dom_amp_max = float(np.max(normal_data["dominant_amplitude_g"]))
        perp_dom_amp_max = float(np.max(perp_data["dominant_amplitude_g"]))
        opp_dom_amp_max = float(np.max(opp_data["dominant_amplitude_g"]))

        config_records.append({
            "pctid": pct,
            "rpm": rpm,
            "theoretical_f_rot_hz": f_rot,
            "normal_rms_total_g": round(norm_rms_tot, 6),
            "perp_rms_total_g": round(perp_rms_tot, 6),
            "opp_rms_total_g": round(opp_rms_tot, 6),
            "normal_p2p_max_g": round(norm_p2p_max, 6),
            "perp_p2p_max_g": round(perp_p2p_max, 6),
            "opp_p2p_max_g": round(opp_p2p_max, 6),
            "normal_dom_amp_max_g": round(norm_dom_amp_max, 6),
            "perp_dom_amp_max_g": round(perp_dom_amp_max, 6),
            "opp_dom_amp_max_g": round(opp_dom_amp_max, 6),
            "perp_to_normal_rms_ratio": round(perp_rms_tot / norm_rms_tot, 4) if norm_rms_tot > 0 else np.nan,
            "opp_to_normal_rms_ratio": round(opp_rms_tot / norm_rms_tot, 4) if norm_rms_tot > 0 else np.nan,
        })

    config_comp_df = pd.DataFrame(config_records)
    config_comp_df = config_comp_df.sort_values(by="pctid").reset_index(drop=True)
    config_out_path = OUTPUT_DIR / "configuration_comparison.csv"
    config_comp_df.to_csv(config_out_path, index=False)
    print(f"[ANALYSIS] Generated: {config_out_path.name} with {len(config_comp_df)} records.")

    return speed_comp_df, config_comp_df


# ---------------------------------------------------------
# VISUALIZATION SUITE (FIGURES)
# ---------------------------------------------------------
def generate_figures(df: pd.DataFrame, stats_df: pd.DataFrame, fft_df: pd.DataFrame, spectrum_cache: dict):
    """
    Generate all required high-resolution vibration figures.
    """
    print("[FIGURES] Generating visualization figures...")
    plt.rcParams["font.sans-serif"] = "DejaVu Sans"
    plt.rcParams["axes.edgecolor"] = "#cccccc"
    plt.rcParams["axes.linewidth"] = 0.8

    # 1. RMS vs Fan Speed
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharex=True)
    fig.suptitle("Vibration RMS vs Fan Speed Across Configurations", fontsize=15, fontweight="bold", y=0.98)

    ax_map = {"x": axes[0, 0], "y": axes[0, 1], "z": axes[1, 0]}
    for ax_name, ax_obj in ax_map.items():
        for wconf, color in CONFIG_COLORS.items():
            conf_name = CONFIG_NAMES[wconf]
            sub = stats_df[(stats_df["wconfid"] == wconf) & (stats_df["axis"] == ax_name)]
            ax_obj.plot(sub["pctid"], sub["rms_g"], marker="o", color=color, label=f"{conf_name}", linewidth=1.8, markersize=5)
        ax_obj.set_title(f"Axis {ax_name.upper()} - RMS (g)", fontsize=12, fontweight="semibold")
        ax_obj.set_ylabel("RMS Acceleration (g)", fontsize=10)
        ax_obj.grid(True, linestyle="--", alpha=0.5)
        ax_obj.legend(loc="upper left", framealpha=0.9)

    # 4th subplot: Vector Total RMS
    ax_tot = axes[1, 1]
    for wconf, color in CONFIG_COLORS.items():
        conf_name = CONFIG_NAMES[wconf]
        sub = stats_df[stats_df["wconfid"] == wconf]
        pcts = sorted(sub["pctid"].unique())
        tot_rms = []
        for p in pcts:
            r = sub[sub["pctid"] == p]["rms_g"].values
            tot_rms.append(np.sqrt(np.sum(r ** 2)))
        ax_tot.plot(pcts, tot_rms, marker="s", color=color, label=f"{conf_name}", linewidth=2.0, markersize=5)
    ax_tot.set_title("Vector Total RMS (g)", fontsize=12, fontweight="semibold")
    ax_tot.set_xlabel("Fan Speed (%)", fontsize=11)
    ax_tot.set_ylabel("Total RMS Acceleration (g)", fontsize=10)
    ax_tot.grid(True, linestyle="--", alpha=0.5)
    ax_tot.legend(loc="upper left", framealpha=0.9)

    axes[1, 0].set_xlabel("Fan Speed (%)", fontsize=11)
    plt.tight_layout()
    p1 = FIGURES_DIR / "rms_vs_fan_speed.png"
    plt.savefig(p1, dpi=300)
    plt.close()
    print(f"[FIGURES] Saved: {p1.name}")

    # 2. Peak-to-Peak vs Fan Speed
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharex=True)
    fig.suptitle("Peak-to-Peak Vibration vs Fan Speed", fontsize=14, fontweight="bold", y=1.02)
    for i, ax_name in enumerate(AXES):
        ax_obj = axes[i]
        for wconf, color in CONFIG_COLORS.items():
            conf_name = CONFIG_NAMES[wconf]
            sub = stats_df[(stats_df["wconfid"] == wconf) & (stats_df["axis"] == ax_name)]
            ax_obj.plot(sub["pctid"], sub["peak_to_peak_g"], marker="o", color=color, label=f"{conf_name}", linewidth=1.8, markersize=5)
        ax_obj.set_title(f"Axis {ax_name.upper()} Peak-to-Peak", fontsize=12, fontweight="semibold")
        ax_obj.set_xlabel("Fan Speed (%)", fontsize=10)
        ax_obj.set_ylabel("Peak-to-Peak (g)", fontsize=10)
        ax_obj.grid(True, linestyle="--", alpha=0.5)
        ax_obj.legend(loc="upper left")
    plt.tight_layout()
    p2 = FIGURES_DIR / "peak_to_peak_vs_fan_speed.png"
    plt.savefig(p2, dpi=300)
    plt.close()
    print(f"[FIGURES] Saved: {p2.name}")

    # 3. Dominant Frequency vs Fan Speed
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), sharey=True)
    fig.suptitle("FFT Dominant Frequency vs Fan Speed (With Theoretical $f_{rot}$ & Nyquist Boundary)", fontsize=14, fontweight="bold", y=1.02)

    pct_range = np.linspace(20, 100, 100)
    theo_rpm = MAX_RPM * pct_range / 100.0
    theo_frot = theo_rpm / 60.0
    theo_alias = np.where(theo_frot > NYQUIST_HZ, np.abs(FS - theo_frot), np.nan)

    for i, ax_name in enumerate(AXES):
        ax_obj = axes[i]
        # Reference lines
        ax_obj.plot(pct_range, theo_frot, "--", color="black", alpha=0.6, label="Theoretical $f_{rot}$")
        ax_obj.plot(pct_range, theo_alias, ":", color="darkorange", linewidth=2.0, label="Theoretical Aliased $f_{rot}$")
        ax_obj.axhline(NYQUIST_HZ, color="crimson", linestyle="-.", alpha=0.7, label=f"Nyquist Limit ({NYQUIST_HZ:.0f} Hz)")

        for wconf, color in CONFIG_COLORS.items():
            conf_name = CONFIG_NAMES[wconf]
            sub = fft_df[(fft_df["wconfid"] == wconf) & (fft_df["axis"] == ax_name)]
            ax_obj.plot(sub["pctid"], sub["dominant_freq_hz"], marker="o", color=color, label=f"{conf_name} Dom Freq", linewidth=1.5, markersize=5)

        ax_obj.set_title(f"Axis {ax_name.upper()} Dominant Frequency", fontsize=12, fontweight="semibold")
        ax_obj.set_xlabel("Fan Speed (%)", fontsize=10)
        if i == 0:
            ax_obj.set_ylabel("Frequency (Hz)", fontsize=10)
        ax_obj.set_ylim(-1, 35)
        ax_obj.grid(True, linestyle="--", alpha=0.5)
        ax_obj.legend(loc="upper left", fontsize=8, framealpha=0.9)
    plt.tight_layout()
    p3 = FIGURES_DIR / "dominant_frequency_vs_fan_speed.png"
    plt.savefig(p3, dpi=300)
    plt.close()
    print(f"[FIGURES] Saved: {p3.name}")

    # 4. Dominant Amplitude vs Fan Speed
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    fig.suptitle("FFT Dominant Amplitude vs Fan Speed Across Configurations", fontsize=14, fontweight="bold", y=1.02)
    for i, ax_name in enumerate(AXES):
        ax_obj = axes[i]
        for wconf, color in CONFIG_COLORS.items():
            conf_name = CONFIG_NAMES[wconf]
            sub = fft_df[(fft_df["wconfid"] == wconf) & (fft_df["axis"] == ax_name)]
            ax_obj.plot(sub["pctid"], sub["dominant_amplitude_g"], marker="^", color=color, label=f"{conf_name}", linewidth=1.8, markersize=6)
        ax_obj.set_title(f"Axis {ax_name.upper()} Dominant Amplitude", fontsize=12, fontweight="semibold")
        ax_obj.set_xlabel("Fan Speed (%)", fontsize=10)
        if i == 0:
            ax_obj.set_ylabel("Amplitude (g)", fontsize=10)
        ax_obj.grid(True, linestyle="--", alpha=0.5)
        ax_obj.legend(loc="upper left")
    plt.tight_layout()
    p4 = FIGURES_DIR / "dominant_amplitude_vs_fan_speed.png"
    plt.savefig(p4, dpi=300)
    plt.close()
    print(f"[FIGURES] Saved: {p4.name}")

    # 5. Representative Time-Domain Waveforms (Showing 50% and 100% fan speed)
    fig, axes = plt.subplots(3, 2, figsize=(15, 9), sharex=True)
    fig.suptitle("Representative Time-Domain Waveforms (Detrended, First 3 Seconds)", fontsize=14, fontweight="bold", y=0.99)
    time_vec = np.arange(N_SAMPLES) / FS
    mask_3sec = time_vec <= 3.0
    t_plot = time_vec[mask_3sec]

    rep_speeds = [(50, "50% Fan Speed (950 RPM)"), (100, "100% Fan Speed (1900 RPM)")]
    for col_idx, (pct, speed_label) in enumerate(rep_speeds):
        for row_idx, ax_name in enumerate(AXES):
            ax_obj = axes[row_idx, col_idx]
            for wconf, color in CONFIG_COLORS.items():
                conf_name = CONFIG_NAMES[wconf]
                sub = df[(df["wconfid"] == wconf) & (df["pctid"] == pct)]
                sig = sub[ax_name].values[mask_3sec]
                sig_detrended = sig - np.mean(sig)
                ax_obj.plot(t_plot, sig_detrended, color=color, label=conf_name, alpha=0.75, linewidth=1.0)
            ax_obj.set_title(f"{speed_label} — Axis {ax_name.upper()}", fontsize=11)
            ax_obj.set_ylabel(f"{ax_name.upper()} Accel (g)", fontsize=9)
            ax_obj.grid(True, linestyle="--", alpha=0.4)
            if row_idx == 0:
                ax_obj.legend(loc="upper right", fontsize=8)
            if row_idx == 2:
                ax_obj.set_xlabel("Time (seconds)", fontsize=10)

    plt.tight_layout()
    p5 = FIGURES_DIR / "representative_time_domain.png"
    plt.savefig(p5, dpi=300)
    plt.close()
    print(f"[FIGURES] Saved: {p5.name}")

    # 6. Representative FFT Spectrum (0 to 25 Hz at 50% and 100% fan speed)
    fig, axes = plt.subplots(3, 2, figsize=(15, 9), sharex=True)
    fig.suptitle("Representative FFT Amplitude Spectra (0 to 25 Hz Nyquist Range)", fontsize=14, fontweight="bold", y=0.99)

    for col_idx, (pct, speed_label) in enumerate(rep_speeds):
        rpm_val = MAX_RPM * pct / 100.0
        f_rot_val = rpm_val / 60.0
        is_above = f_rot_val > NYQUIST_HZ
        alias_f = abs(FS - f_rot_val) if is_above else None

        for row_idx, ax_name in enumerate(AXES):
            ax_obj = axes[row_idx, col_idx]
            for wconf, color in CONFIG_COLORS.items():
                conf_name = CONFIG_NAMES[wconf]
                freqs, amps = spectrum_cache[(wconf, pct, ax_name)]
                ax_obj.plot(freqs, amps, color=color, label=f"{conf_name}", alpha=0.8, linewidth=1.2)

            # Mark theoretical rotational / aliased line
            if not is_above:
                ax_obj.axvline(f_rot_val, color="black", linestyle="--", linewidth=1.2, label=f"Theoretical $f_{{rot}}$ ({f_rot_val:.2f} Hz)")
            else:
                ax_obj.axvline(alias_f, color="darkorange", linestyle=":", linewidth=1.5, label=f"Aliased $f_{{rot}}$ ({alias_f:.2f} Hz)")

            ax_obj.set_title(f"{speed_label} — Axis {ax_name.upper()}", fontsize=11)
            ax_obj.set_ylabel("Amplitude (g)", fontsize=9)
            ax_obj.set_xlim(0, 25)
            ax_obj.grid(True, linestyle="--", alpha=0.4)
            if row_idx == 0 and col_idx == 0:
                ax_obj.legend(loc="upper right", fontsize=8)
            elif row_idx == 0 and col_idx == 1:
                ax_obj.legend(loc="upper right", fontsize=8)
            if row_idx == 2:
                ax_obj.set_xlabel("Frequency (Hz)", fontsize=10)

    plt.tight_layout()
    p6 = FIGURES_DIR / "representative_fft_spectrum.png"
    plt.savefig(p6, dpi=300)
    plt.close()
    print(f"[FIGURES] Saved: {p6.name}")


# ---------------------------------------------------------
# MAIN EXECUTION PIPELINE
# ---------------------------------------------------------
def main():
    print("=" * 60)
    print("STARTING VIBRATION ANALYSIS PIPELINE (PHASE 2 & 3)")
    print("=" * 60)
    try:
        ensure_directories()
        df = load_dataset()
        stats_df = run_time_domain_analysis(df)
        fft_df, spectrum_cache = run_fft_analysis(df)
        speed_comp_df, config_comp_df = generate_comparison_csvs(stats_df, fft_df)
        generate_figures(df, stats_df, fft_df, spectrum_cache)

        print("\n" + "=" * 60)
        print("PIPELINE COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed with error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
