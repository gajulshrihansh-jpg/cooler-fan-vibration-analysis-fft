"""
Professional Light-Theme Engineering Analytics Dashboard Generator
===================================================================
Produces a high-contrast, faculty-presentation-ready, research-grade engineering
analytics website for the Cooler Fan Vibration Analysis project.

Visual Direction & Tokens:
- Page background: #EEF2F6 (crisp light slate-grey, gives real surface separation)
- Main cards: #FFFFFF (with defined 1px solid #CBD5E1 borders & soft ambient shadows)
- Secondary panels: #F7F9FC
- Primary text: #182230 (deep charcoal slate, 12:1 contrast against white)
- Secondary text: #475569 (solid slate grey, 7:1 contrast)
- Muted labels: #596579 (solid contrast, never washed out)
- Borders: #CBD5E1 (crisp, clearly separating cards from page canvas)
- Primary teal: #0F766E | Light teal surface: #CCFBF1
- Warning surface: #FEF3C7 | Warning text: #854D0E | Warning border: #FCD34D
- Error surface: #FEE2E2 | Error text: #991B1B | Error border: #FCA5A5
- Chart gridlines: #DCE3EB | Zero lines & axes: #94A3B8
- Configuration colors:
  Normal: #C83E54 | Perpendicular: #2864B4 | Opposite: #21865B

Target Output: outputs/interactive_vibration_analysis_professional.html
"""

import sys
import os
import json
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
import plotly

DATASET_PATH = Path("accelerometer (1).csv")
OUTPUT_DIR = Path("outputs")
FINAL_HTML_OUTPUT_PATH = OUTPUT_DIR / "interactive_vibration_analysis_professional.html"
LOCAL_PLOTLY_JS = OUTPUT_DIR / "plotly.min.js"

STATS_CSV = OUTPUT_DIR / "vibration_statistics.csv"
FFT_CSV = OUTPUT_DIR / "fft_results.csv"
SPEED_CSV = OUTPUT_DIR / "speed_comparison.csv"
CONFIG_CSV = OUTPUT_DIR / "configuration_comparison.csv"

FS = 50.0
N_SAMPLES = 3000
DURATION_SEC = 60.0
NYQUIST_HZ = 25.0
MAX_RPM = 1900.0

AXES = ["x", "y", "z"]


def ensure_plotly_js():
    """Ensure local plotly.min.js exists in outputs/ for offline fallback."""
    if not LOCAL_PLOTLY_JS.exists():
        try:
            pkg_dir = Path(plotly.__file__).parent
            bundled_js = pkg_dir / "package_data" / "plotly.min.js"
            if bundled_js.exists():
                shutil.copyfile(bundled_js, LOCAL_PLOTLY_JS)
                print(f"[INIT] Offline plotly.min.js copied to {LOCAL_PLOTLY_JS.name}")
        except Exception as e:
            print(f"[WARN] Local plotly.min.js copy skipped: {e}")


def build_data_payload():
    """Precompute and assemble complete JSON telemetry payload."""
    print("[DATA] Loading raw accelerometer observations & analytical outputs...")
    df = pd.read_csv(DATASET_PATH)
    stats_df = pd.read_csv(STATS_CSV)
    fft_df = pd.read_csv(FFT_CSV)

    time_vec = [round(float(t), 3) for t in (np.arange(N_SAMPLES) / FS)]

    win = np.hanning(N_SAMPLES)
    win_sum = float(np.sum(win))
    freqs = np.fft.rfftfreq(N_SAMPLES, d=1.0 / FS)
    freq_vec = [round(float(f), 4) for f in freqs]

    print("[COMPUTE] Precomputing high-resolution FFT spectra and time vectors for 51 conditions...")
    conditions = {}
    for (wconf, pct), grp in df.groupby(["wconfid", "pctid"]):
        key = f"{wconf}_{pct}"
        cond_dict = {}
        for ax in AXES:
            sig = grp[ax].values
            cond_dict[ax] = [round(float(v), 3) for v in sig]

            sig_d = sig - np.mean(sig)
            fft_v = np.fft.rfft(sig_d * win)
            amp = (2.0 / win_sum) * np.abs(fft_v)
            amp[0] /= 2.0
            amp[-1] /= 2.0
            cond_dict[f"fft_{ax}"] = [round(float(a), 5) for a in amp]

        conditions[key] = cond_dict

    stats_dict = {}
    for _, row in stats_df.iterrows():
        k = f"{int(row['wconfid'])}_{int(row['pctid'])}_{row['axis']}"
        stats_dict[k] = row.to_dict()

    fft_dict = {}
    for _, row in fft_df.iterrows():
        k = f"{int(row['wconfid'])}_{int(row['pctid'])}_{row['axis']}"
        rc = row.to_dict()
        if pd.isna(rc.get("aliased_f_rot_hz")):
            rc["aliased_f_rot_hz"] = None
        fft_dict[k] = rc

    trends = {}
    pct_list = sorted(list(df["pctid"].unique()))
    speeds_rpm = [round(MAX_RPM * p / 100.0, 1) for p in pct_list]
    theo_frots = [round(r / 60.0, 3) for r in speeds_rpm]
    aliased_frots = [round(abs(FS - f), 3) if f > NYQUIST_HZ else None for f in theo_frots]

    trends["pct_list"] = pct_list
    trends["rpm_list"] = speeds_rpm
    trends["theo_frot"] = theo_frots
    trends["aliased_frot"] = aliased_frots

    for wconf in [1, 2, 3]:
        trends[f"wconf_{wconf}"] = {}
        for ax in AXES:
            sub_stats = stats_df[(stats_df["wconfid"] == wconf) & (stats_df["axis"] == ax)].sort_values("pctid")
            sub_fft = fft_df[(fft_df["wconfid"] == wconf) & (fft_df["axis"] == ax)].sort_values("pctid")
            trends[f"wconf_{wconf}"][f"rms_{ax}"] = [round(float(v), 5) for v in sub_stats["rms_g"].tolist()]
            trends[f"wconf_{wconf}"][f"p2p_{ax}"] = [round(float(v), 5) for v in sub_stats["peak_to_peak_g"].tolist()]
            trends[f"wconf_{wconf}"][f"dom_freq_{ax}"] = [round(float(v), 5) for v in sub_fft["dominant_freq_hz"].tolist()]
            trends[f"wconf_{wconf}"][f"dom_amp_{ax}"] = [round(float(v), 5) for v in sub_fft["dominant_amplitude_g"].tolist()]

        rx = np.array(trends[f"wconf_{wconf}"]["rms_x"])
        ry = np.array(trends[f"wconf_{wconf}"]["rms_y"])
        rz = np.array(trends[f"wconf_{wconf}"]["rms_z"])
        r_tot = np.sqrt(rx ** 2 + ry ** 2 + rz ** 2)
        trends[f"wconf_{wconf}"]["rms_total"] = [round(float(v), 5) for v in r_tot.tolist()]

    payload = {
        "metadata": {
            "title": "Cooler Fan Vibration Analysis",
            "subtitle": "Time-Domain & Frequency-Domain Analysis",
            "total_samples": 153000,
            "weight_configurations": 3,
            "fan_speeds_count": 17,
            "fs_hz": FS,
            "nyquist_hz": NYQUIST_HZ,
            "samples_per_condition": N_SAMPLES,
            "duration_sec": DURATION_SEC,
            "max_rpm": MAX_RPM
        },
        "time": time_vec,
        "fft_freqs": freq_vec,
        "conditions": conditions,
        "stats": stats_dict,
        "fft_results": fft_dict,
        "trends": trends
    }
    return payload


PROFESSIONAL_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cooler Fan Vibration Analysis | Professional Engineering Analytics</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <!-- Plotly CDN with offline local fallback -->
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <script>
        if (typeof Plotly === 'undefined') {
            document.write('<script src="plotly.min.js"><\\/script>');
        }
    </script>
    <style>
        :root {
            /* High-Contrast Light Engineering Analytics Design Tokens */
            --bg-page: #EEF2F6;          /* Crisp light slate canvas, distinct from white */
            --bg-card: #FFFFFF;          /* Pure white card surface */
            --bg-panel: #F7F9FC;         /* Light grey-blue secondary panel */
            --bg-subtle: #F1F5F9;        /* Subtle control/header tint */
            
            --border-crisp: #CBD5E1;     /* High-definition 1px boundary */
            --border-subtle: #E2E8F0;    /* Internal row/item dividers */
            --border-focus: #0F766E;     /* Deep teal focus ring */
            
            --text-primary: #182230;     /* Deep charcoal slate, 12:1 contrast */
            --text-secondary: #475569;   /* Solid slate grey, 7:1 contrast */
            --text-muted: #596579;       /* Solid readable muted text, 5.5:1 contrast */
            
            /* Primary Brand Accents */
            --teal-primary: #0F766E;
            --teal-light: #CCFBF1;
            --teal-border: #99F6E4;
            --teal-hover: #115E59;
            
            /* Warning System (Pale Amber) */
            --warning-bg: #FEF3C7;
            --warning-text: #854D0E;
            --warning-border: #FCD34D;
            --warning-accent: #D97706;
            
            /* Error / Saturation Limit System (Pale Red) */
            --error-bg: #FEE2E2;
            --error-text: #991B1B;
            --error-border: #FCA5A5;
            --error-accent: #DC2626;
            
            /* Configuration Colors */
            --color-normal: #C83E54;     /* Normal (Crimson Red) */
            --color-perp: #2864B4;       /* Perpendicular (Engineering Blue) */
            --color-opp: #21865B;        /* Opposite (Forest Emerald) */
            
            --bg-normal-tint: #FFE8EC;
            --border-normal-tint: #F8B4BF;
            --text-normal-tint: #9E1F35;
            
            --bg-perp-tint: #EBF3FC;
            --border-perp-tint: #B9D7F9;
            --text-perp-tint: #1A4B8C;
            
            --bg-opp-tint: #E8F7F0;
            --border-opp-tint: #A3E2C4;
            --text-opp-tint: #136340;

            --font-ui: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            --font-mono: "Fira Code", "JetBrains Mono", Consolas, monospace;
            
            --shadow-card: 0 2px 6px rgba(15, 23, 42, 0.05), 0 1px 2px rgba(15, 23, 42, 0.04);
            --shadow-header: 0 2px 8px rgba(15, 23, 42, 0.06);
            --shadow-button: 0 2px 4px rgba(15, 118, 110, 0.25);
            
            --radius-sm: 6px;
            --radius-md: 8px;
            --radius-lg: 12px;
        }

        *, *::before, *::after {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-page);
            color: var(--text-primary);
            font-family: var(--font-ui);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
            padding: 24px 32px 64px 32px;
        }

        .dashboard-container {
            max-width: 1560px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .icon {
            display: inline-block;
            vertical-align: middle;
            flex-shrink: 0;
            stroke-width: 2;
        }

        /* -------------------------------------------------------------
           HEADER SECTION (White with crisp border & subtle shadow)
        ------------------------------------------------------------- */
        header.dashboard-header {
            background-color: var(--bg-card);
            border: 1px solid var(--border-crisp);
            border-radius: var(--radius-lg);
            padding: 22px 28px;
            box-shadow: var(--shadow-header);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }

        .header-brand {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .brand-icon-box {
            width: 46px;
            height: 46px;
            border-radius: var(--radius-md);
            background-color: var(--teal-light);
            border: 1.5px solid var(--teal-border);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--teal-primary);
        }

        .header-title-block h1 {
            font-size: 26px;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.5px;
            line-height: 1.2;
        }

        .header-title-block p {
            font-size: 14px;
            color: var(--text-secondary);
            font-weight: 500;
            margin-top: 3px;
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            background-color: var(--bg-subtle);
            border: 1px solid var(--border-crisp);
            padding: 7px 16px;
            border-radius: 9999px;
            font-size: 12.5px;
            font-weight: 600;
            color: var(--text-secondary);
            font-family: var(--font-mono);
        }

        .status-dot {
            width: 9px;
            height: 9px;
            background-color: var(--teal-primary);
            border-radius: 50%;
        }

        /* -------------------------------------------------------------
           DATASET SUMMARY SECTION (Light Grey-Blue Distinct Panel)
        ------------------------------------------------------------- */
        .dataset-summary-panel {
            background-color: var(--bg-panel);
            border: 1px solid var(--border-crisp);
            border-radius: var(--radius-lg);
            padding: 16px 20px;
            box-shadow: var(--shadow-card);
        }

        .dataset-summary-header {
            font-size: 11.5px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            color: var(--text-secondary);
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .summary-cards-grid {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 12px;
        }

        @media (max-width: 1200px) {
            .summary-cards-grid {
                grid-template-columns: repeat(3, 1fr);
            }
        }

        @media (max-width: 680px) {
            .summary-cards-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        .summary-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-crisp);
            border-radius: var(--radius-md);
            padding: 12px 14px;
            display: flex;
            align-items: center;
            gap: 12px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        }

        .summary-icon-box {
            width: 36px;
            height: 36px;
            border-radius: var(--radius-sm);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }

        .summary-text-col {
            display: flex;
            flex-direction: column;
            min-width: 0;
        }

        .summary-label {
            font-size: 11.5px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .summary-value {
            font-size: 15px;
            font-weight: 700;
            color: var(--text-primary);
            font-family: var(--font-mono);
            margin-top: 1px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        /* -------------------------------------------------------------
           FILTER TOOLBAR
        ------------------------------------------------------------- */
        .filter-panel {
            background-color: var(--bg-card);
            border: 1px solid var(--border-crisp);
            border-radius: var(--radius-lg);
            padding: 20px 26px;
            display: flex;
            flex-wrap: wrap;
            align-items: flex-end;
            gap: 20px;
            box-shadow: var(--shadow-card);
        }

        .filter-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
            flex: 1 1 210px;
        }

        .filter-group label {
            font-size: 12.5px;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .select-wrapper {
            position: relative;
            display: flex;
            align-items: center;
        }

        select.filter-select {
            width: 100%;
            background-color: var(--bg-card);
            color: var(--text-primary);
            border: 1.5px solid var(--border-crisp);
            border-radius: var(--radius-md);
            padding: 10px 38px 10px 14px;
            font-size: 14px;
            font-weight: 500;
            font-family: var(--font-ui);
            cursor: pointer;
            outline: none;
            appearance: none;
            transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }

        select.filter-select:hover {
            border-color: #94A3B8;
        }

        select.filter-select:focus {
            border-color: var(--teal-primary);
            box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.18);
        }

        .select-wrapper .chevron {
            position: absolute;
            right: 14px;
            pointer-events: none;
            color: var(--text-secondary);
        }

        /* Speed Presets */
        .preset-buttons-row {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            margin-top: 4px;
        }

        .preset-btn {
            background-color: var(--bg-subtle);
            border: 1px solid var(--border-crisp);
            color: var(--text-secondary);
            font-size: 11.5px;
            font-family: var(--font-mono);
            font-weight: 600;
            padding: 4px 10px;
            border-radius: var(--radius-sm);
            cursor: pointer;
            transition: all 0.15s ease;
        }

        .preset-btn:hover {
            color: var(--text-primary);
            border-color: #94A3B8;
            background-color: #E2E8F0;
        }

        .preset-btn.active {
            background-color: var(--teal-light);
            border-color: var(--teal-primary);
            color: var(--teal-primary);
            font-weight: 700;
        }

        /* Export Button */
        .btn-primary-export {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            background-color: var(--teal-primary);
            color: #FFFFFF;
            border: 1px solid var(--teal-primary);
            border-radius: var(--radius-md);
            padding: 10px 22px;
            font-size: 13.5px;
            font-weight: 600;
            font-family: var(--font-ui);
            cursor: pointer;
            height: 42px;
            box-shadow: var(--shadow-button);
            transition: background-color 0.15s ease, transform 0.1s ease;
            white-space: nowrap;
        }

        .btn-primary-export:hover {
            background-color: var(--teal-hover);
            transform: translateY(-1px);
        }

        .btn-primary-export:active {
            transform: translateY(0);
        }

        /* -------------------------------------------------------------
           WARNING BANNERS
        ------------------------------------------------------------- */
        .warning-stack {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .alert-strip {
            display: flex;
            align-items: flex-start;
            gap: 14px;
            padding: 14px 20px;
            border-radius: var(--radius-md);
            font-size: 13.5px;
            line-height: 1.55;
            box-shadow: var(--shadow-card);
        }

        .alert-strip-warning {
            background-color: var(--warning-bg);
            border: 1px solid var(--warning-border);
            border-left: 5px solid var(--warning-accent);
            color: var(--warning-text);
        }

        .alert-strip-error {
            background-color: var(--error-bg);
            border: 1px solid var(--error-border);
            border-left: 5px solid var(--error-accent);
            color: var(--error-text);
        }

        .alert-strip-icon {
            margin-top: 1px;
            flex-shrink: 0;
        }

        .alert-strip-warning .alert-strip-icon { color: var(--warning-accent); }
        .alert-strip-error .alert-strip-icon { color: var(--error-accent); }

        .alert-strip strong {
            font-weight: 700;
        }

        /* -------------------------------------------------------------
           KPI METRIC CARDS (8 Cards with clear width & prominent values)
        ------------------------------------------------------------- */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
        }

        @media (max-width: 1200px) {
            .kpi-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 640px) {
            .kpi-grid {
                grid-template-columns: 1fr;
            }
        }

        .kpi-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-crisp);
            border-top: 3px solid var(--teal-primary);
            border-radius: var(--radius-md);
            padding: 16px 18px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            box-shadow: var(--shadow-card);
            transition: border-color 0.15s ease, transform 0.15s ease;
        }

        .kpi-card:hover {
            border-color: #94A3B8;
            transform: translateY(-1px);
        }

        .kpi-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }

        .kpi-title {
            font-size: 12.5px;
            font-weight: 600;
            color: var(--text-secondary);
            letter-spacing: 0.2px;
        }

        .kpi-icon {
            color: var(--text-muted);
        }

        .kpi-value-row {
            display: flex;
            align-items: baseline;
            gap: 5px;
            margin-bottom: 6px;
        }

        .kpi-value {
            font-family: var(--font-mono);
            font-size: 26px;
            font-weight: 700;
            color: var(--text-primary);
            font-variant-numeric: tabular-nums;
            letter-spacing: -0.5px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .kpi-unit {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-muted);
            font-family: var(--font-ui);
        }

        .kpi-footer-tag {
            font-size: 12px;
            font-family: var(--font-mono);
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 4px;
        }

        .badge-pill {
            display: inline-block;
            padding: 2px 8px;
            border-radius: var(--radius-sm);
            font-size: 11px;
            font-weight: 600;
        }

        .badge-pill-ok {
            background-color: var(--bg-opp-tint);
            color: var(--text-opp-tint);
            border: 1px solid var(--border-opp-tint);
        }

        .badge-pill-warn {
            background-color: var(--warning-bg);
            color: var(--warning-text);
            border: 1px solid var(--warning-border);
        }

        /* -------------------------------------------------------------
           THEORETICAL VS MEASURED FREQUENCY TABLE CARD
        ------------------------------------------------------------- */
        .card-table {
            background-color: var(--bg-card);
            border: 1px solid var(--border-crisp);
            border-radius: var(--radius-lg);
            padding: 20px 24px;
            box-shadow: var(--shadow-card);
        }

        .section-header-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-subtle);
        }

        .section-header-title {
            font-size: 18px;
            font-weight: 700;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .section-header-title .icon {
            color: var(--teal-primary);
        }

        .section-tag-badge {
            font-size: 12px;
            font-family: var(--font-mono);
            font-weight: 600;
            background-color: var(--bg-subtle);
            color: var(--text-secondary);
            border: 1px solid var(--border-crisp);
            border-radius: var(--radius-sm);
            padding: 4px 12px;
        }

        .clean-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            font-size: 13.5px;
            text-align: left;
        }

        .clean-table th {
            background-color: #E2E8F0;
            color: var(--text-primary);
            font-weight: 700;
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 0.6px;
            padding: 12px 16px;
            border-bottom: 2px solid #94A3B8;
        }

        .clean-table th:first-child { border-top-left-radius: var(--radius-sm); }
        .clean-table th:last-child { border-top-right-radius: var(--radius-sm); }

        .clean-table td {
            padding: 11px 16px;
            border-bottom: 1px solid var(--border-subtle);
            color: var(--text-primary);
            font-family: var(--font-mono);
            font-variant-numeric: tabular-nums;
        }

        .clean-table tr:nth-child(even) td {
            background-color: #F8FAFC;
        }

        .clean-table tr:hover td {
            background-color: #F1F5F9;
        }

        .table-label-cell {
            font-family: var(--font-ui);
            font-weight: 600;
            color: var(--text-secondary);
        }

        /* -------------------------------------------------------------
           PRIMARY 2x2 GRAPHS GRID
        ------------------------------------------------------------- */
        .graphs-grid-2x2 {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }

        @media (max-width: 1100px) {
            .graphs-grid-2x2 {
                grid-template-columns: 1fr;
            }
        }

        .chart-box {
            background-color: var(--bg-card);
            border: 1px solid var(--border-crisp);
            border-radius: var(--radius-lg);
            padding: 20px;
            display: flex;
            flex-direction: column;
            box-shadow: var(--shadow-card);
        }

        .chart-header-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-subtle);
        }

        .chart-title {
            font-size: 16px;
            font-weight: 700;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .chart-title .icon {
            color: var(--teal-primary);
        }

        .chart-tag {
            font-size: 11.5px;
            font-family: var(--font-mono);
            font-weight: 600;
            padding: 4px 10px;
            border-radius: var(--radius-sm);
            background-color: var(--bg-subtle);
            border: 1px solid var(--border-crisp);
            color: var(--text-secondary);
        }

        .plotly-graph-viewport {
            width: 100%;
            height: 380px;
        }

        /* Explanatory Note inside FFT Card */
        .fft-note-box {
            background-color: #F0FDFA;
            border: 1px solid #99F6E4;
            border-left: 4px solid var(--teal-primary);
            border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
            padding: 14px 18px;
            margin-top: 14px;
            font-size: 13px;
            color: var(--text-primary);
            line-height: 1.6;
        }

        .fft-note-title {
            font-weight: 700;
            color: var(--teal-primary);
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 6px;
            font-size: 13.5px;
        }

        .fft-note-box ul {
            margin-left: 20px;
            margin-top: 4px;
        }

        .fft-note-box li {
            margin-bottom: 3px;
            color: var(--text-secondary);
        }

        /* -------------------------------------------------------------
           CONFIGURATION COMPARISON SECTION
        ------------------------------------------------------------- */
        .section-title-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 14px;
            margin-top: 10px;
        }

        .section-heading {
            font-size: 19px;
            font-weight: 700;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .section-heading .icon {
            color: var(--teal-primary);
        }

        .segmented-controls {
            display: inline-flex;
            background-color: #E2E8F0;
            border: 1px solid var(--border-crisp);
            border-radius: var(--radius-md);
            padding: 4px;
            gap: 4px;
        }

        .segment-tab {
            background: none;
            border: none;
            color: var(--text-secondary);
            padding: 6px 16px;
            font-size: 12.5px;
            font-weight: 600;
            border-radius: var(--radius-sm);
            cursor: pointer;
            transition: all 0.15s ease;
            font-family: var(--font-ui);
        }

        .segment-tab:hover {
            color: var(--text-primary);
        }

        .segment-tab.active {
            background-color: var(--teal-primary);
            color: #FFFFFF;
            font-weight: 700;
            box-shadow: 0 1px 3px rgba(15, 118, 110, 0.3);
        }

        /* Badges for weight configs */
        .cfg-chip {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: var(--radius-sm);
            font-weight: 700;
            font-size: 12px;
            font-family: var(--font-ui);
        }

        .cfg-chip-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        .cfg-chip-normal {
            background-color: var(--bg-normal-tint);
            color: var(--text-normal-tint);
            border: 1px solid var(--border-normal-tint);
        }
        .cfg-chip-normal .cfg-chip-dot { background-color: var(--color-normal); }

        .cfg-chip-perp {
            background-color: var(--bg-perp-tint);
            color: var(--text-perp-tint);
            border: 1px solid var(--border-perp-tint);
        }
        .cfg-chip-perp .cfg-chip-dot { background-color: var(--color-perp); }

        .cfg-chip-opp {
            background-color: var(--bg-opp-tint);
            color: var(--text-opp-tint);
            border: 1px solid var(--border-opp-tint);
        }
        .cfg-chip-opp .cfg-chip-dot { background-color: var(--color-opp); }

        /* -------------------------------------------------------------
           ENGINEERING REFERENCE & CONCEPT CARDS (7 CARDS)
        ------------------------------------------------------------- */
        .educational-panel {
            background-color: var(--bg-card);
            border: 1px solid var(--border-crisp);
            border-radius: var(--radius-lg);
            padding: 22px 26px;
            box-shadow: var(--shadow-card);
        }

        .concepts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }

        .concept-card {
            background-color: var(--bg-panel);
            border: 1px solid var(--border-crisp);
            border-radius: var(--radius-md);
            padding: 16px 18px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
            transition: border-color 0.15s ease;
        }

        .concept-card:hover {
            border-color: #94A3B8;
        }

        .concept-title {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            font-weight: 700;
            color: var(--teal-primary);
        }

        .concept-title .icon {
            color: var(--teal-primary);
        }

        .concept-text {
            font-size: 13.5px;
            color: #334155;
            line-height: 1.6;
        }

        .concept-text strong {
            color: var(--text-primary);
        }

        /* -------------------------------------------------------------
           MEASUREMENT LIMITATIONS & INTERPRETATION PANEL
        ------------------------------------------------------------- */
        .limitations-box {
            background-color: var(--bg-card);
            border: 1px solid var(--border-crisp);
            border-left: 5px solid var(--warning-accent);
            border-radius: var(--radius-lg);
            padding: 24px 28px;
            box-shadow: var(--shadow-card);
        }

        .limitations-header {
            font-size: 17px;
            font-weight: 700;
            color: #78350F;
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 16px;
        }

        .limitations-ol {
            list-style: none;
            counter-reset: lim-counter;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .limitations-ol li {
            counter-increment: lim-counter;
            position: relative;
            padding-left: 38px;
            font-size: 13.5px;
            color: #334155;
            line-height: 1.65;
        }

        .limitations-ol li::before {
            content: counter(lim-counter);
            position: absolute;
            left: 0;
            top: 2px;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background-color: var(--warning-bg);
            border: 1.5px solid var(--warning-border);
            color: var(--warning-text);
            font-family: var(--font-mono);
            font-size: 12px;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .limitations-ol strong {
            color: var(--text-primary);
        }

        .limitations-advisory-callout {
            background-color: var(--warning-bg);
            border: 1px solid var(--warning-border);
            border-radius: var(--radius-md);
            padding: 16px 20px;
            margin-top: 18px;
            display: flex;
            align-items: flex-start;
            gap: 14px;
            font-size: 13px;
            color: var(--warning-text);
            line-height: 1.6;
        }

        .limitations-advisory-callout .icon {
            color: var(--warning-accent);
            margin-top: 2px;
        }

        /* -------------------------------------------------------------
           FOOTER
        ------------------------------------------------------------- */
        footer.dashboard-footer {
            margin-top: 20px;
            border-top: 1px solid var(--border-crisp);
            padding-top: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            font-size: 12.5px;
            color: var(--text-secondary);
            font-family: var(--font-mono);
        }

        /* Toast notification */
        .toast-notification {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background-color: var(--teal-primary);
            color: #FFFFFF;
            padding: 12px 22px;
            border-radius: var(--radius-md);
            box-shadow: 0 4px 14px rgba(15, 118, 110, 0.35);
            font-size: 13.5px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.25s ease, transform 0.25s ease;
            transform: translateY(10px);
            z-index: 9999;
        }

        .toast-notification.show {
            opacity: 1;
            pointer-events: auto;
            transform: translateY(0);
        }
    </style>
</head>
<body>
<div class="dashboard-container">

    <!-- HEADER SECTION -->
    <header class="dashboard-header">
        <div class="header-brand">
            <div class="brand-icon-box">
                <!-- Clean Waveform Vector SVG -->
                <svg class="icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M2 12h3l2-7 4 14 4-10 2 5h5"/>
                </svg>
            </div>
            <div class="header-title-block">
                <h1>Cooler Fan Vibration Analysis</h1>
                <p>Time-Domain & Frequency-Domain Analysis</p>
            </div>
        </div>
        <div class="status-badge">
            <span class="status-dot"></span>
            <span>Fs = 50.0 Hz &bull; Nyquist = 25.0 Hz</span>
        </div>
    </header>

    <!-- DATASET SUMMARY SECTION -->
    <section class="dataset-summary-panel">
        <div class="dataset-summary-header">
            <svg class="icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/>
            </svg>
            Experimental Benchmark Dataset Summary
        </div>
        <div class="summary-cards-grid">
            <div class="summary-card">
                <div class="summary-icon-box" style="background-color: #E0F2FE; color: #0284C7;">
                    <svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <ellipse cx="12" cy="5" rx="9" ry="3"/>
                        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
                        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
                    </svg>
                </div>
                <div class="summary-text-col">
                    <span class="summary-label">Observations</span>
                    <span class="summary-value">153,000</span>
                </div>
            </div>

            <div class="summary-card">
                <div class="summary-icon-box" style="background-color: #EDE9FE; color: #7C3AED;">
                    <svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <polygon points="12 2 2 7 12 12 22 7 12 2"/>
                        <polygon points="2 17 12 22 22 17"/>
                        <polygon points="2 12 12 17 22 12"/>
                    </svg>
                </div>
                <div class="summary-text-col">
                    <span class="summary-label">Blade Weights</span>
                    <span class="summary-value">3 States</span>
                </div>
            </div>

            <div class="summary-card">
                <div class="summary-icon-box" style="background-color: #CCFBF1; color: #0F766E;">
                    <svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                    </svg>
                </div>
                <div class="summary-text-col">
                    <span class="summary-label">Sampling Rate</span>
                    <span class="summary-value">50.0 Hz</span>
                </div>
            </div>

            <div class="summary-card">
                <div class="summary-icon-box" style="background-color: #FEF3C7; color: #D97706;">
                    <svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                    </svg>
                </div>
                <div class="summary-text-col">
                    <span class="summary-label">Nyquist Limit</span>
                    <span class="summary-value">25.00 Hz</span>
                </div>
            </div>

            <div class="summary-card">
                <div class="summary-icon-box" style="background-color: #DBEAFE; color: #2563EB;">
                    <svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M3.34 19a10 10 0 1 1 17.32 0"/><path d="M12 14v-4"/>
                    </svg>
                </div>
                <div class="summary-text-col">
                    <span class="summary-label">Speed Levels</span>
                    <span class="summary-value">17 Speeds</span>
                </div>
            </div>

            <div class="summary-card">
                <div class="summary-icon-box" style="background-color: #D1FAE5; color: #059669;">
                    <svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <rect width="18" height="18" x="3" y="3" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/>
                    </svg>
                </div>
                <div class="summary-text-col">
                    <span class="summary-label">Window Length</span>
                    <span class="summary-value">60.0 s</span>
                </div>
            </div>
        </div>
    </section>

    <!-- FILTER TOOLBAR -->
    <section class="filter-panel">
        <div class="filter-group">
            <label for="select-wconf">
                <svg class="icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <polygon points="12 2 2 7 12 12 22 7 12 2"/>
                    <polygon points="2 17 12 22 22 17"/>
                    <polygon points="2 12 12 17 22 12"/>
                </svg>
                Weight Configuration
            </label>
            <div class="select-wrapper">
                <select id="select-wconf" class="filter-select">
                    <option value="1">Normal (Red)</option>
                    <option value="2">Perpendicular (Blue)</option>
                    <option value="3">Opposite (Green)</option>
                    <option value="all">All Configurations</option>
                </select>
                <svg class="icon chevron" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <polyline points="6 9 12 15 18 9"/>
                </svg>
            </div>
        </div>

        <div class="filter-group" style="flex: 1.5 1 290px;">
            <label for="select-speed">
                <svg class="icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M3.34 19a10 10 0 1 1 17.32 0"/><path d="M12 14v-4"/>
                </svg>
                Fan Speed Percentage & RPM
            </label>
            <div class="select-wrapper">
                <select id="select-speed" class="filter-select">
                    <!-- Populated dynamically 20% to 100% -->
                </select>
                <svg class="icon chevron" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <polyline points="6 9 12 15 18 9"/>
                </svg>
            </div>
            <div class="preset-buttons-row" id="speed-presets-bar">
                <button class="preset-btn" data-speed="20">20% Min</button>
                <button class="preset-btn" data-speed="40">40%</button>
                <button class="preset-btn active" data-speed="50">50% Mid</button>
                <button class="preset-btn" data-speed="60">60%</button>
                <button class="preset-btn" data-speed="80">80% Nyquist</button>
                <button class="preset-btn" data-speed="100">100% Max</button>
            </div>
        </div>

        <div class="filter-group">
            <label for="select-axis">
                <svg class="icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/>
                </svg>
                Acceleration Axis
            </label>
            <div class="select-wrapper">
                <select id="select-axis" class="filter-select">
                    <option value="x">Axis X</option>
                    <option value="y">Axis Y</option>
                    <option value="z">Axis Z</option>
                </select>
                <svg class="icon chevron" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <polyline points="6 9 12 15 18 9"/>
                </svg>
            </div>
        </div>

        <div>
            <button id="btn-export-csv" class="btn-primary-export" title="Export CSV for selected operating condition">
                <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                Export Analysis CSV
            </button>
        </div>
    </section>

    <!-- WARNING BANNERS -->
    <div class="warning-stack" id="warning-stack">
        <div class="alert-strip alert-strip-warning" id="alert-aliasing" style="display: none;">
            <svg class="icon alert-strip-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            <div>
                <strong>Nyquist Aliasing Advisory:</strong> The theoretical rotational frequency exceeds the 25.0 Hz Nyquist boundary. High-frequency vibration folds into the baseband at the calculated alias frequency. Interpret spectral peaks with caution.
            </div>
        </div>

        <div class="alert-strip alert-strip-error" id="alert-clipping" style="display: none;">
            <svg class="icon alert-strip-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <div>
                <strong>Sensor Dynamic Range Limitation:</strong> Acceleration peaks approach the sensor's approximately &plusmn;8.0 g span limit. Peak truncation introduces spurious harmonic noise into the FFT spectrum. Note: this reflects sensor measurement dynamic range saturation, not mechanical failure.
            </div>
        </div>
    </div>

    <!-- KPI METRIC CARDS (8 Cards) -->
    <section class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-title">Fan Speed</span>
                <svg class="icon kpi-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M3.34 19a10 10 0 1 1 17.32 0"/><path d="M12 14v-4"/>
                </svg>
            </div>
            <div class="kpi-value-row">
                <span class="kpi-value" id="kpi-speed">--</span>
                <span class="kpi-unit">%</span>
            </div>
            <div class="kpi-footer-tag" id="kpi-speed-tag">
                <span class="badge-pill badge-pill-ok">Nominal</span>
            </div>
        </div>

        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-title">Motor Speed</span>
                <svg class="icon kpi-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                </svg>
            </div>
            <div class="kpi-value-row">
                <span class="kpi-value" id="kpi-rpm">--</span>
                <span class="kpi-unit">RPM</span>
            </div>
            <div class="kpi-footer-tag">
                Max: 1900 RPM
            </div>
        </div>

        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-title">Theoretical f_rot</span>
                <svg class="icon kpi-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M2 12h3l2-7 4 14 4-10 2 5h5"/>
                </svg>
            </div>
            <div class="kpi-value-row">
                <span class="kpi-value" id="kpi-frot">--</span>
                <span class="kpi-unit">Hz</span>
            </div>
            <div class="kpi-footer-tag" id="kpi-frot-tag">
                f_rot = RPM / 60
            </div>
        </div>

        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-title">Nyquist Limit</span>
                <svg class="icon kpi-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
            </div>
            <div class="kpi-value-row">
                <span class="kpi-value">25.00</span>
                <span class="kpi-unit">Hz</span>
            </div>
            <div class="kpi-footer-tag">
                Fs / 2 = 50 / 2
            </div>
        </div>

        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-title">RMS Acceleration</span>
                <svg class="icon kpi-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/>
                </svg>
            </div>
            <div class="kpi-value-row">
                <span class="kpi-value" id="kpi-rms">--</span>
                <span class="kpi-unit">g</span>
            </div>
            <div class="kpi-footer-tag">
                Effective Energy
            </div>
        </div>

        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-title">Peak-to-Peak</span>
                <svg class="icon kpi-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>
                </svg>
            </div>
            <div class="kpi-value-row">
                <span class="kpi-value" id="kpi-p2p">--</span>
                <span class="kpi-unit">g</span>
            </div>
            <div class="kpi-footer-tag">
                Maximum Swing
            </div>
        </div>

        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-title">Dominant Frequency</span>
                <svg class="icon kpi-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                </svg>
            </div>
            <div class="kpi-value-row">
                <span class="kpi-value" id="kpi-dom-freq">--</span>
                <span class="kpi-unit">Hz</span>
            </div>
            <div class="kpi-footer-tag">
                Spectral Peak Bin
            </div>
        </div>

        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-title">Dominant Amplitude</span>
                <svg class="icon kpi-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/>
                </svg>
            </div>
            <div class="kpi-value-row">
                <span class="kpi-value" id="kpi-dom-amp">--</span>
                <span class="kpi-unit">g</span>
            </div>
            <div class="kpi-footer-tag">
                Harmonic Magnitude
            </div>
        </div>
    </section>

    <!-- THEORETICAL VS MEASURED FREQUENCY TABLE -->
    <section class="card-table">
        <div class="section-header-row">
            <div class="section-header-title">
                <svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M9 3v18"/><path d="M15 3v18"/>
                </svg>
                Theoretical vs Measured Frequency Verification
            </div>
            <span class="section-tag-badge" id="tag-theo-table">Condition Summary</span>
        </div>
        <div style="overflow-x: auto;">
            <table class="clean-table">
                <thead>
                    <tr>
                        <th style="width: 42%;">Parameter</th>
                        <th style="width: 58%;">Analytical Value</th>
                    </tr>
                </thead>
                <tbody id="tbody-theo-measured">
                    <!-- Populated dynamically -->
                </tbody>
            </table>
        </div>
    </section>

    <!-- 2x2 PRIMARY CHARTS GRID -->
    <main class="graphs-grid-2x2">
        <!-- GRAPH 1: TIME DOMAIN -->
        <div class="chart-box">
            <div class="chart-header-row">
                <div class="chart-title">
                    <svg class="icon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M2 12h3l2-7 4 14 4-10 2 5h5"/>
                    </svg>
                    Graph 1: Time-Domain Waveform
                </div>
                <div class="chart-tag" id="tag-graph1">Time (s) vs Acceleration (g)</div>
            </div>
            <div id="chart-timedomain" class="plotly-graph-viewport"></div>
        </div>

        <!-- GRAPH 2: FFT SPECTRUM -->
        <div class="chart-box">
            <div class="chart-header-row">
                <div class="chart-title">
                    <svg class="icon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/>
                    </svg>
                    Graph 2: FFT Amplitude Spectrum (0 – 25 Hz)
                </div>
                <div class="chart-tag" id="tag-graph2">Frequency (Hz) vs Amplitude (g)</div>
            </div>
            <div id="chart-fft" class="plotly-graph-viewport"></div>
            
            <div class="fft-note-box">
                <div class="fft-note-title">
                    <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
                    </svg>
                    Spectral Peak Engineering Interpretation:
                </div>
                The measured dominant spectral peak does not necessarily equal the fan rotational frequency.
                <ul>
                    <li>Theoretical rotational frequency is calculated strictly from RPM: <code>f_rot = RPM / 60</code>.</li>
                    <li>The measured dominant peak is the highest amplitude discrete non-DC spectral bin.</li>
                    <li>These metrics are tracked and reported separately.</li>
                    <li>When rotational speed exceeds 25 Hz Nyquist (≥ 80% speed), the expected aliased frequency <code>|50 - f_rot|</code> is displayed as a dotted reference line.</li>
                </ul>
            </div>
        </div>

        <!-- GRAPH 3: SPEED TREND (RMS vs FAN SPEED) -->
        <div class="chart-box">
            <div class="chart-header-row">
                <div class="chart-title">
                    <svg class="icon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>
                    </svg>
                    Graph 3: RMS Acceleration vs Fan Speed
                </div>
                <div class="chart-tag">All Weight Configurations</div>
            </div>
            <div id="chart-speedtrend" class="plotly-graph-viewport"></div>
        </div>

        <!-- GRAPH 4: DOMINANT FREQUENCY TREND -->
        <div class="chart-box">
            <div class="chart-header-row">
                <div class="chart-title">
                    <svg class="icon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                    Graph 4: Dominant Frequency vs Fan Speed
                </div>
                <div class="chart-tag">Measured vs Theoretical & Aliasing</div>
            </div>
            <div id="chart-domfreq" class="plotly-graph-viewport"></div>
        </div>
    </main>

    <!-- CONFIGURATION COMPARISON SECTION -->
    <section>
        <div class="section-title-bar">
            <div class="section-heading">
                <svg class="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <polygon points="12 2 2 7 12 12 22 7 12 2"/>
                    <polygon points="2 17 12 22 22 17"/>
                    <polygon points="2 12 12 17 22 12"/>
                </svg>
                Weight Configuration Comparative Analysis
            </div>
            <div class="segmented-controls" id="toggle-config-comp">
                <button class="segment-tab active" data-axis="x">Axis X</button>
                <button class="segment-tab" data-axis="y">Axis Y</button>
                <button class="segment-tab" data-axis="z">Axis Z</button>
                <button class="segment-tab" data-axis="total">Total RMS</button>
            </div>
        </div>

        <!-- Comparative Chart -->
        <div class="chart-box" style="margin-top: 14px; margin-bottom: 20px;">
            <div class="chart-header-row">
                <div class="chart-title">
                    <svg class="icon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
                    </svg>
                    RMS Acceleration Across Configurations
                </div>
                <div class="chart-tag" id="tag-config-chart">Axis X RMS (g)</div>
            </div>
            <div id="chart-config-comp" class="plotly-graph-viewport" style="height: 360px;"></div>
        </div>

        <!-- Numerical Comparison Table -->
        <div class="card-table">
            <div class="section-header-row">
                <div class="section-header-title">
                    <svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M9 3v18"/><path d="M15 3v18"/>
                    </svg>
                    Numerical Configuration Performance Comparison
                </div>
                <span class="section-tag-badge" id="tag-comp-table">Operating State: 50% Speed</span>
            </div>
            <div style="overflow-x: auto;">
                <table class="clean-table" id="table-config-comp">
                    <thead>
                        <tr>
                            <th>Configuration</th>
                            <th>RPM</th>
                            <th>RMS X (g)</th>
                            <th>RMS Y (g)</th>
                            <th>RMS Z (g)</th>
                            <th>Total RMS (g)</th>
                            <th>P2P X (g)</th>
                            <th>P2P Y (g)</th>
                            <th>P2P Z (g)</th>
                        </tr>
                    </thead>
                    <tbody id="tbody-config-comp">
                        <!-- Populated dynamically -->
                    </tbody>
                </table>
            </div>
        </div>
    </section>

    <!-- ENGINEERING REFERENCE & CONCEPT EXPLANATIONS -->
    <section class="educational-panel">
        <div class="section-header-row">
            <div class="section-header-title">
                <svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
                </svg>
                Engineering Fundamentals & Technical Reference
            </div>
            <span class="section-tag-badge">7 Diagnostic Principles</span>
        </div>
        <div class="concepts-grid">
            <div class="concept-card">
                <div class="concept-title">
                    <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                    </svg>
                    1. Root Mean Square (RMS) Vibration
                </div>
                <div class="concept-text">
                    <strong>RMS Acceleration</strong> quantifies the true continuous destructive vibration energy transmitted through the bearing housing. While transient peaks can be erratic, RMS correlates directly with fatigue wear and structural stress.
                </div>
            </div>

            <div class="concept-card">
                <div class="concept-title">
                    <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/>
                    </svg>
                    2. FFT Spectral Decomposition
                </div>
                <div class="concept-text">
                    The <strong>Fast Fourier Transform (FFT)</strong> decomposes complex time-domain acceleration into its constituent sinusoidal frequency components, isolating unbalance, blade passes, and mounting resonances.
                </div>
            </div>

            <div class="concept-card">
                <div class="concept-title">
                    <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                    3. Dominant Spectral Peak
                </div>
                <div class="concept-text">
                    The <strong>Dominant FFT Frequency</strong> marks the discrete non-zero frequency bin bearing the highest kinetic amplitude in the one-sided spectrum, indicating the primary cyclic excitation mode along that axis.
                </div>
            </div>

            <div class="concept-card">
                <div class="concept-title">
                    <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="12" cy="12" r="10"/><path d="m4.93 4.93 4.24 4.24"/><path d="m14.83 9.17 4.24-4.24"/><path d="m14.83 14.83 4.24 4.24"/><path d="m9.17 14.83-4.24 4.24"/>
                    </svg>
                    4. Theoretical f_rot vs Measured Peak
                </div>
                <div class="concept-text">
                    Theoretical rotational speed (<code>f_rot = RPM / 60</code>) represents the shaft rotation rate. The measured peak may differ due to aerodynamic turbulence, structural resonance, or motor poles; hence both are logged independently.
                </div>
            </div>

            <div class="concept-card">
                <div class="concept-title">
                    <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                    </svg>
                    5. Nyquist-Shannon Sampling Criterion
                </div>
                <div class="concept-text">
                    With sampling frequency <code>Fs = 50.0 Hz</code>, the maximum uniquely reconstructible vibration frequency is <code>f_nyq = Fs / 2 = 25.0 Hz</code>. All valid spectral bins reside strictly within 0 to 25 Hz.
                </div>
            </div>

            <div class="concept-card">
                <div class="concept-title">
                    <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                    </svg>
                    6. High-Speed Aliasing Fold-Back
                </div>
                <div class="concept-text">
                    At fan speeds ≥ 80% (1520–1900 RPM), shaft speed exceeds 25 Hz (up to 31.67 Hz). High-frequency motion folds across the Nyquist mirror, re-appearing as a phantom low-frequency peak at <code>|50 - f_rot| Hz</code>.
                </div>
            </div>

            <div class="concept-card">
                <div class="concept-title">
                    <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    7. Sensor Saturation & Clipping Distortion
                </div>
                <div class="concept-text">
                    The accelerometer has a dynamic measurement span of ±8.0 g. Amplitudes approaching this ceiling clip, distorting sinusoidal peaks into square waves and generating artificial harmonic noise across the FFT spectrum.
                </div>
            </div>
        </div>
    </section>

    <!-- MEASUREMENT LIMITATIONS & INTERPRETATION SECTION -->
    <section class="limitations-box">
        <div class="limitations-header">
            <svg class="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            Measurement Limitations & Interpretation
        </div>
        <ol class="limitations-ol">
            <li><strong>Sampling Frequency:</strong> Accelerometer data was captured at a fixed rate of <code>Fs = 50.0 Hz</code> (sampling interval <code>Δt = 20.0 ms</code>).</li>
            <li><strong>Nyquist Frequency Boundary:</strong> The corresponding Nyquist limit is <code>Fs / 2 = 25.0 Hz</code>. Reliable spectral reconstruction is strictly bounded between 0.0 Hz and 25.0 Hz.</li>
            <li><strong>Rotational Frequency Exceedance:</strong> At fan speeds of 80% and above (1520 to 1900 RPM), theoretical rotational frequency <code>f_rot</code> reaches 25.33 to 31.67 Hz, exceeding the 25.0 Hz Nyquist ceiling.</li>
            <li><strong>Baseband Spectral Aliasing:</strong> Rotational vibrations above 25.0 Hz fold over into the measured baseband (e.g. 31.67 Hz at 100% speed appears as an aliased peak at <code>|50.0 - 31.67| = 18.33 Hz</code>).</li>
            <li><strong>Accelerometer Span Saturation:</strong> At higher operating speeds, vibration excursions for Normal and Perpendicular configurations approach the sensor's approximately &plusmn;8.0 g hardware saturation limit.</li>
            <li><strong>Harmonic Distortion via Clipping:</strong> Peak clipping truncates true sinusoidal motion, artificially injecting odd harmonic components and elevating the FFT spectral noise floor.</li>
            <li><strong>Analytical Caution & Verification:</strong> Spectral conclusions at ≥ 80% fan speed must be evaluated with caution. Sensor saturation reflects measurement dynamic range limits and does not prove mechanical motor or bearing failure.</li>
        </ol>
        <div class="limitations-advisory-callout">
            <svg class="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
            <div>
                <strong>Engineering Diagnostic Notice:</strong> Sensor saturation indicates dynamic range clipping of the accelerometer instrument, not mechanical bearing breakdown. Independent validation with wide-bandwidth instrumentation (≥ 1,000 Hz Fs) and ±50 g dynamic range is recommended for comprehensive failure diagnosis.
            </div>
        </div>
    </section>

    <!-- FOOTER -->
    <footer class="dashboard-footer">
        <div>
            Cooler Fan Vibration Analysis &bull; Research Analytics Edition &bull; Fs = 50.0 Hz &bull; Nyquist = 25.0 Hz
        </div>
        <div>
            Source: <code>accelerometer (1).csv</code> (153,000 observations) &bull; Standalone Plotly Runtime
        </div>
    </footer>

</div>

<!-- TOAST MESSAGE -->
<div id="toast" class="toast-notification">
    <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <polyline points="20 6 9 17 4 12"/>
    </svg>
    <span id="toast-text">CSV File Generated Successfully</span>
</div>

<!-- EMBEDDED DASHBOARD DATA -->
<script>
    const DASHBOARD_DATA = __JSON_DATA__;
</script>

<!-- CLIENT-SIDE APPLICATION CONTROLLER -->
<script>
    // Configuration Colors
    const CONFIG_COLORS = {
        1: "#C83E54", // Normal (Crimson Red)
        2: "#2864B4", // Perpendicular (Engineering Blue)
        3: "#21865B"  // Opposite (Forest Emerald)
    };

    const CONFIG_LABELS = {
        1: "Normal (Red)",
        2: "Perpendicular (Blue)",
        3: "Opposite (Green)"
    };

    const CONFIG_BADGES = {
        1: '<span class="cfg-chip cfg-chip-normal"><span class="cfg-chip-dot"></span>Normal</span>',
        2: '<span class="cfg-chip cfg-chip-perp"><span class="cfg-chip-dot"></span>Perpendicular</span>',
        3: '<span class="cfg-chip cfg-chip-opp"><span class="cfg-chip-dot"></span>Opposite</span>'
    };

    // DOM Elements
    const selWconf = document.getElementById("select-wconf");
    const selSpeed = document.getElementById("select-speed");
    const selAxis = document.getElementById("select-axis");
    const btnExportCsv = document.getElementById("btn-export-csv");
    const speedPresetsBar = document.getElementById("speed-presets-bar");

    const alertAliasing = document.getElementById("alert-aliasing");
    const alertClipping = document.getElementById("alert-clipping");

    // KPI DOM Elements
    const kpiSpeed = document.getElementById("kpi-speed");
    const kpiSpeedTag = document.getElementById("kpi-speed-tag");
    const kpiRpm = document.getElementById("kpi-rpm");
    const kpiFrot = document.getElementById("kpi-frot");
    const kpiFrotTag = document.getElementById("kpi-frot-tag");
    const kpiRms = document.getElementById("kpi-rms");
    const kpiP2p = document.getElementById("kpi-p2p");
    const kpiDomFreq = document.getElementById("kpi-dom-freq");
    const kpiDomAmp = document.getElementById("kpi-dom-amp");

    // Table DOM Elements
    const tbodyTheoMeasured = document.getElementById("tbody-theo-measured");
    const tagTheoTable = document.getElementById("tag-theo-table");
    const tbodyConfigComp = document.getElementById("tbody-config-comp");
    const tagCompTable = document.getElementById("tag-comp-table");

    // Configuration comparison toggles
    let configCompAxis = "x";
    const segmentButtons = document.querySelectorAll("#toggle-config-comp .segment-tab");
    const tagConfigChart = document.getElementById("tag-config-chart");

    // Toast
    const toast = document.getElementById("toast");
    const toastText = document.getElementById("toast-text");

    function showToast(msg) {
        toastText.textContent = msg;
        toast.classList.add("show");
        setTimeout(() => toast.classList.remove("show"), 3200);
    }

    // Populate Fan Speeds
    const pctList = DASHBOARD_DATA.trends.pct_list;
    pctList.forEach((pct, idx) => {
        const rpm = DASHBOARD_DATA.trends.rpm_list[idx];
        const opt = document.createElement("option");
        opt.value = pct;
        opt.textContent = `${pct}% Speed (${rpm} RPM)`;
        if (pct === 50) opt.selected = true;
        selSpeed.appendChild(opt);
    });

    // Preset Speed Buttons
    speedPresetsBar.addEventListener("click", (e) => {
        const btn = e.target.closest(".preset-btn");
        if (!btn) return;
        const targetSpeed = btn.getAttribute("data-speed");
        selSpeed.value = targetSpeed;
        syncSpeedPresets();
        updateDashboard();
    });

    function syncSpeedPresets() {
        const currentSpeed = selSpeed.value;
        const btns = speedPresetsBar.querySelectorAll(".preset-btn");
        btns.forEach(b => {
            if (b.getAttribute("data-speed") === currentSpeed) {
                b.classList.add("active");
            } else {
                b.classList.remove("active");
            }
        });
    }

    // Professional High-Contrast Light Theme Plotly Base Layout
    const baseLayout = {
        paper_bgcolor: "#ffffff",
        plot_bgcolor: "#ffffff",
        font: { family: "Inter, -apple-system, sans-serif", color: "#182230", size: 11 },
        margin: { l: 60, r: 25, t: 30, b: 50 },
        hovermode: "closest",
        hoverlabel: {
            bgcolor: "#ffffff",
            bordercolor: "#0f766e",
            font: { family: "Fira Code, monospace", size: 11.5, color: "#182230" }
        },
        legend: {
            orientation: "h",
            yanchor: "bottom",
            y: 1.02,
            xanchor: "right",
            x: 1,
            font: { size: 11.5, color: "#182230" }
        },
        xaxis: {
            gridcolor: "#DCE3EB",
            zerolinecolor: "#94A3B8",
            zerolinewidth: 1.5,
            showline: true,
            linecolor: "#CBD5E1",
            tickfont: { family: "Fira Code, monospace", size: 10.5, color: "#475569" },
            titlefont: { size: 12.5, color: "#182230" }
        },
        yaxis: {
            gridcolor: "#DCE3EB",
            zerolinecolor: "#94A3B8",
            zerolinewidth: 1.5,
            showline: true,
            linecolor: "#CBD5E1",
            tickfont: { family: "Fira Code, monospace", size: 10.5, color: "#475569" },
            titlefont: { size: 12.5, color: "#182230" }
        }
    };

    const plotlyConfig = {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        displaylogo: false
    };

    // UPDATE DASHBOARD STATE
    function updateDashboard() {
        syncSpeedPresets();
        const wconfVal = selWconf.value; // "1", "2", "3", or "all"
        const pctVal = parseInt(selSpeed.value);
        const axisVal = selAxis.value; // "x", "y", "z"

        const speedIdx = pctList.indexOf(pctVal);
        const rpmVal = DASHBOARD_DATA.trends.rpm_list[speedIdx];
        const theoFrot = DASHBOARD_DATA.trends.theo_frot[speedIdx];
        const isAboveNyquist = theoFrot > DASHBOARD_DATA.metadata.nyquist_hz;
        const aliasedFrot = DASHBOARD_DATA.trends.aliased_frot[speedIdx];

        // 1. Warning Strips
        alertAliasing.style.display = isAboveNyquist ? "flex" : "none";

        let clippingDetected = false;
        const activeConfigs = (wconfVal === "all") ? [1, 2, 3] : [parseInt(wconfVal)];
        for (const wc of activeConfigs) {
            const key = `${wc}_${pctVal}_${axisVal}`;
            const st = DASHBOARD_DATA.stats[key];
            if (st && (Math.abs(st.min_g) >= 7.8 || Math.abs(st.max_g) >= 7.8 || st.peak_abs_g >= 7.8)) {
                clippingDetected = true;
                break;
            }
        }
        alertClipping.style.display = clippingDetected ? "flex" : "none";

        // 2. KPI Cards
        kpiSpeed.textContent = pctVal;
        kpiSpeedTag.innerHTML = isAboveNyquist
            ? '<span class="badge-pill badge-pill-warn">Aliased (≥80%)</span>'
            : '<span class="badge-pill badge-pill-ok">Sub-Nyquist</span>';

        kpiRpm.textContent = rpmVal.toFixed(1);
        kpiFrot.textContent = theoFrot.toFixed(2);
        kpiFrotTag.innerHTML = isAboveNyquist
            ? `<span style="color:#854D0E; font-weight:700;">Alias: ${aliasedFrot.toFixed(2)} Hz</span>`
            : '<span style="color:#136340; font-weight:600;">Within Nyquist Band</span>';

        if (wconfVal !== "all") {
            const key = `${wconfVal}_${pctVal}_${axisVal}`;
            const st = DASHBOARD_DATA.stats[key];
            const fft = DASHBOARD_DATA.fft_results[key];

            kpiRms.textContent = st ? st.rms_g.toFixed(3) : "--";
            kpiP2p.textContent = st ? st.peak_to_peak_g.toFixed(3) : "--";
            kpiDomFreq.textContent = fft ? fft.dominant_freq_hz.toFixed(2) : "--";
            kpiDomAmp.textContent = fft ? fft.dominant_amplitude_g.toFixed(4) : "--";
        } else {
            const st1 = DASHBOARD_DATA.stats[`1_${pctVal}_${axisVal}`];
            const st2 = DASHBOARD_DATA.stats[`2_${pctVal}_${axisVal}`];
            const st3 = DASHBOARD_DATA.stats[`3_${pctVal}_${axisVal}`];

            const fft1 = DASHBOARD_DATA.fft_results[`1_${pctVal}_${axisVal}`];
            const fft2 = DASHBOARD_DATA.fft_results[`2_${pctVal}_${axisVal}`];
            const fft3 = DASHBOARD_DATA.fft_results[`3_${pctVal}_${axisVal}`];

            kpiRms.innerHTML = `<span style="color:#C83E54;">${st1.rms_g.toFixed(2)}</span> | <span style="color:#2864B4;">${st2.rms_g.toFixed(2)}</span> | <span style="color:#21865B;">${st3.rms_g.toFixed(2)}</span>`;
            kpiP2p.innerHTML = `<span style="color:#C83E54;">${st1.peak_to_peak_g.toFixed(2)}</span> | <span style="color:#2864B4;">${st2.peak_to_peak_g.toFixed(2)}</span> | <span style="color:#21865B;">${st3.peak_to_peak_g.toFixed(2)}</span>`;
            kpiDomFreq.innerHTML = `<span style="color:#C83E54;">${fft1.dominant_freq_hz.toFixed(1)}</span> | <span style="color:#2864B4;">${fft2.dominant_freq_hz.toFixed(1)}</span> | <span style="color:#21865B;">${fft3.dominant_freq_hz.toFixed(1)}</span>`;
            kpiDomAmp.innerHTML = `<span style="color:#C83E54;">${fft1.dominant_amplitude_g.toFixed(3)}</span> | <span style="color:#2864B4;">${fft2.dominant_amplitude_g.toFixed(3)}</span> | <span style="color:#21865B;">${fft3.dominant_amplitude_g.toFixed(3)}</span>`;
        }

        // 3. Theoretical vs Measured Table
        renderTheoreticalVsMeasuredTable(wconfVal, pctVal, axisVal, rpmVal, theoFrot, aliasedFrot, isAboveNyquist);

        // 4. Render Graphs
        renderTimeDomainGraph(activeConfigs, pctVal, axisVal);
        renderFFTGraph(activeConfigs, pctVal, axisVal, theoFrot, isAboveNyquist, aliasedFrot);
        renderSpeedTrendGraph(axisVal, pctVal);
        renderDominantFreqTrendGraph(axisVal, pctVal);
        renderConfigComparisonGraph(pctVal);
        renderConfigComparisonTable(pctVal, rpmVal);
    }

    // THEORETICAL VS MEASURED TABLE
    function renderTheoreticalVsMeasuredTable(wconfVal, pctVal, axisVal, rpmVal, theoFrot, aliasedFrot, isAboveNyquist) {
        const configLabel = (wconfVal === "all") ? "All Configurations" : CONFIG_LABELS[wconfVal];
        tagTheoTable.textContent = `${configLabel} • ${pctVal}% Speed • Axis ${axisVal.toUpperCase()}`;

        const aliasDisplay = isAboveNyquist ? `${aliasedFrot.toFixed(2)} Hz` : "N/A (Theoretical f_rot < 25 Hz)";

        let rowsHtml = "";

        if (wconfVal !== "all") {
            const key = `${wconfVal}_${pctVal}_${axisVal}`;
            const fft = DASHBOARD_DATA.fft_results[key];
            const domFreq = fft ? `${fft.dominant_freq_hz.toFixed(2)} Hz` : "--";
            const domAmp = fft ? `${fft.dominant_amplitude_g.toFixed(4)} g` : "--";

            rowsHtml = `
                <tr><td class="table-label-cell">Operating Fan Speed</td><td><strong>${pctVal}%</strong></td></tr>
                <tr><td class="table-label-cell">Fan Rotational Speed (RPM)</td><td><strong>${rpmVal.toFixed(1)} RPM</strong></td></tr>
                <tr><td class="table-label-cell">Theoretical Rotational Frequency (f_rot)</td><td><strong style="color:var(--teal-primary);">${theoFrot.toFixed(2)} Hz</strong></td></tr>
                <tr><td class="table-label-cell">Nyquist Frequency Limit (Fs / 2)</td><td><strong>25.00 Hz</strong></td></tr>
                <tr><td class="table-label-cell">Expected Aliased Frequency (|50 - f_rot|)</td><td><strong style="color:${isAboveNyquist ? '#854D0E' : 'inherit'};">${aliasDisplay}</strong></td></tr>
                <tr><td class="table-label-cell">Measured Dominant FFT Peak Frequency</td><td><strong style="color: ${CONFIG_COLORS[wconfVal]};">${domFreq}</strong></td></tr>
                <tr><td class="table-label-cell">Measured Dominant FFT Amplitude</td><td><strong>${domAmp}</strong></td></tr>
                <tr><td class="table-label-cell">FFT Frequency Resolution (Δf)</td><td><strong>0.0167 Hz</strong> (50 Hz / 3,000 bins)</td></tr>
            `;
        } else {
            const fft1 = DASHBOARD_DATA.fft_results[`1_${pctVal}_${axisVal}`];
            const fft2 = DASHBOARD_DATA.fft_results[`2_${pctVal}_${axisVal}`];
            const fft3 = DASHBOARD_DATA.fft_results[`3_${pctVal}_${axisVal}`];

            const dom1 = fft1 ? `${fft1.dominant_freq_hz.toFixed(2)} Hz` : "--";
            const dom2 = fft2 ? `${fft2.dominant_freq_hz.toFixed(2)} Hz` : "--";
            const dom3 = fft3 ? `${fft3.dominant_freq_hz.toFixed(2)} Hz` : "--";

            const amp1 = fft1 ? `${fft1.dominant_amplitude_g.toFixed(4)} g` : "--";
            const amp2 = fft2 ? `${fft2.dominant_amplitude_g.toFixed(4)} g` : "--";
            const amp3 = fft3 ? `${fft3.dominant_amplitude_g.toFixed(4)} g` : "--";

            rowsHtml = `
                <tr><td class="table-label-cell">Operating Fan Speed</td><td><strong>${pctVal}%</strong></td></tr>
                <tr><td class="table-label-cell">Fan Rotational Speed (RPM)</td><td><strong>${rpmVal.toFixed(1)} RPM</strong></td></tr>
                <tr><td class="table-label-cell">Theoretical Rotational Frequency (f_rot)</td><td><strong style="color:var(--teal-primary);">${theoFrot.toFixed(2)} Hz</strong></td></tr>
                <tr><td class="table-label-cell">Nyquist Frequency Limit (Fs / 2)</td><td><strong>25.00 Hz</strong></td></tr>
                <tr><td class="table-label-cell">Expected Aliased Frequency (|50 - f_rot|)</td><td><strong style="color:${isAboveNyquist ? '#854D0E' : 'inherit'};">${aliasDisplay}</strong></td></tr>
                <tr><td class="table-label-cell">Measured Dominant Peak Frequencies</td><td>
                    <span style="color:#C83E54;">Normal: <strong>${dom1}</strong></span> &bull; 
                    <span style="color:#2864B4;">Perp: <strong>${dom2}</strong></span> &bull; 
                    <span style="color:#21865B;">Opposite: <strong>${dom3}</strong></span>
                </td></tr>
                <tr><td class="table-label-cell">Measured Dominant Peak Amplitudes</td><td>
                    <span style="color:#C83E54;">Normal: <strong>${amp1}</strong></span> &bull; 
                    <span style="color:#2864B4;">Perp: <strong>${amp2}</strong></span> &bull; 
                    <span style="color:#21865B;">Opposite: <strong>${amp3}</strong></span>
                </td></tr>
                <tr><td class="table-label-cell">FFT Frequency Resolution (Δf)</td><td><strong>0.0167 Hz</strong> (50 Hz / 3,000 bins)</td></tr>
            `;
        }

        tbodyTheoMeasured.innerHTML = rowsHtml;
    }

    // CONFIGURATION COMPARISON TABLE
    function renderConfigComparisonTable(pctVal, rpmVal) {
        tagCompTable.textContent = `Operating State: ${pctVal}% Speed (${rpmVal.toFixed(1)} RPM)`;
        let rowsHtml = "";

        [1, 2, 3].forEach(wc => {
            const stX = DASHBOARD_DATA.stats[`${wc}_${pctVal}_x`];
            const stY = DASHBOARD_DATA.stats[`${wc}_${pctVal}_y`];
            const stZ = DASHBOARD_DATA.stats[`${wc}_${pctVal}_z`];

            const rx = stX ? stX.rms_g : 0;
            const ry = stY ? stY.rms_g : 0;
            const rz = stZ ? stZ.rms_g : 0;
            const rTot = Math.sqrt(rx*rx + ry*ry + rz*rz);

            const p2pX = stX ? stX.peak_to_peak_g.toFixed(3) : "--";
            const p2pY = stY ? stY.peak_to_peak_g.toFixed(3) : "--";
            const p2pZ = stZ ? stZ.peak_to_peak_g.toFixed(3) : "--";

            rowsHtml += `
                <tr>
                    <td>${CONFIG_BADGES[wc]}</td>
                    <td>${rpmVal.toFixed(1)}</td>
                    <td>${rx.toFixed(3)}</td>
                    <td>${ry.toFixed(3)}</td>
                    <td>${rz.toFixed(3)}</td>
                    <td><strong style="color:var(--teal-primary); font-size:14px;">${rTot.toFixed(3)}</strong></td>
                    <td>${p2pX}</td>
                    <td>${p2pY}</td>
                    <td>${p2pZ}</td>
                </tr>
            `;
        });

        tbodyConfigComp.innerHTML = rowsHtml;
    }

    // GRAPH 1: TIME DOMAIN WAVEFORM
    function renderTimeDomainGraph(activeConfigs, pctVal, axisVal) {
        const timeVec = DASHBOARD_DATA.time;
        const traces = [];

        activeConfigs.forEach(wc => {
            const key = `${wc}_${pctVal}`;
            const cond = DASHBOARD_DATA.conditions[key];
            if (cond) {
                traces.push({
                    x: timeVec,
                    y: cond[axisVal],
                    type: "scatter",
                    mode: "lines",
                    name: CONFIG_LABELS[wc],
                    line: { color: CONFIG_COLORS[wc], width: 1.5 },
                    hovertemplate: `<b>${CONFIG_LABELS[wc]}</b><br>Time: %{x:.2f} s<br>Accel: %{y:.3f} g<extra></extra>`
                });
            }
        });

        const layout = JSON.parse(JSON.stringify(baseLayout));
        layout.xaxis.title = "Time (seconds)";
        layout.yaxis.title = `Axis ${axisVal.toUpperCase()} Acceleration (g)`;
        layout.xaxis.range = [0, 5.0];

        Plotly.react("chart-timedomain", traces, layout, plotlyConfig);
    }

    // GRAPH 2: FFT AMPLITUDE SPECTRUM
    function renderFFTGraph(activeConfigs, pctVal, axisVal, theoFrot, isAboveNyquist, aliasedFrot) {
        const freqs = DASHBOARD_DATA.fft_freqs;
        const traces = [];

        activeConfigs.forEach(wc => {
            const key = `${wc}_${pctVal}`;
            const cond = DASHBOARD_DATA.conditions[key];
            const resKey = `${wc}_${pctVal}_${axisVal}`;
            const res = DASHBOARD_DATA.fft_results[resKey];
            if (cond) {
                traces.push({
                    x: freqs,
                    y: cond[`fft_${axisVal}`],
                    type: "scatter",
                    mode: "lines",
                    name: `${CONFIG_LABELS[wc]} Spectrum`,
                    line: { color: CONFIG_COLORS[wc], width: 1.6 },
                    hovertemplate: `<b>${CONFIG_LABELS[wc]}</b><br>Frequency: %{x:.3f} Hz<br>Amplitude: %{y:.4f} g<extra></extra>`
                });

                if (res) {
                    traces.push({
                        x: [res.dominant_freq_hz],
                        y: [res.dominant_amplitude_g],
                        type: "scatter",
                        mode: "markers",
                        name: `${CONFIG_LABELS[wc]} Dominant Peak`,
                        marker: { color: CONFIG_COLORS[wc], size: 9, symbol: "diamond", line: { color: "#ffffff", width: 1.5 } },
                        hovertemplate: `<b>${CONFIG_LABELS[wc]} Dominant Peak</b><br>Freq: %{x:.2f} Hz<br>Amp: %{y:.4f} g<extra></extra>`
                    });
                }
            }
        });

        const layout = JSON.parse(JSON.stringify(baseLayout));
        layout.xaxis.title = "Frequency (Hz)";
        layout.yaxis.title = "FFT Amplitude (g)";
        layout.xaxis.range = [0, 25.0];

        const shapes = [];
        const annotations = [];

        if (!isAboveNyquist) {
            shapes.push({
                type: "line",
                x0: theoFrot,
                x1: theoFrot,
                y0: 0,
                y1: 1,
                yref: "paper",
                line: { color: "#1E293B", width: 1.8, dash: "dash" }
            });
            annotations.push({
                x: theoFrot,
                y: 0.95,
                yref: "paper",
                text: `Theoretical f_rot: ${theoFrot.toFixed(2)} Hz`,
                showarrow: true,
                arrowhead: 2,
                ax: 50,
                ay: -25,
                font: { color: "#0F172A", size: 10.5, family: "Fira Code, monospace" },
                bgcolor: "#F1F5F9",
                bordercolor: "#94A3B8"
            });
        } else {
            shapes.push({
                type: "line",
                x0: aliasedFrot,
                x1: aliasedFrot,
                y0: 0,
                y1: 1,
                yref: "paper",
                line: { color: "#B45309", width: 2.0, dash: "dot" }
            });
            annotations.push({
                x: aliasedFrot,
                y: 0.95,
                yref: "paper",
                text: `Expected Alias f_rot: ${aliasedFrot.toFixed(2)} Hz`,
                showarrow: true,
                arrowhead: 2,
                ax: 50,
                ay: -25,
                font: { color: "#78350F", size: 10.5, family: "Fira Code, monospace" },
                bgcolor: "#FEF3C7",
                bordercolor: "#FCD34D"
            });
        }

        layout.shapes = shapes;
        layout.annotations = annotations;

        Plotly.react("chart-fft", traces, layout, plotlyConfig);
    }

    // GRAPH 3: SPEED TREND (RMS vs FAN SPEED)
    function renderSpeedTrendGraph(axisVal, selectedPct) {
        const pctList = DASHBOARD_DATA.trends.pct_list;
        const traces = [];

        [1, 2, 3].forEach(wc => {
            const rmsValues = DASHBOARD_DATA.trends[`wconf_${wc}`][`rms_${axisVal}`];
            traces.push({
                x: pctList,
                y: rmsValues,
                type: "scatter",
                mode: "lines+markers",
                name: CONFIG_LABELS[wc],
                line: { color: CONFIG_COLORS[wc], width: 2.4 },
                marker: { size: 6.5 },
                hovertemplate: `<b>${CONFIG_LABELS[wc]}</b><br>Speed: %{x}%<br>RMS: %{y:.3f} g<extra></extra>`
            });
        });

        const layout = JSON.parse(JSON.stringify(baseLayout));
        layout.xaxis.title = "Fan Speed (%)";
        layout.yaxis.title = `Axis ${axisVal.toUpperCase()} RMS Acceleration (g)`;
        layout.xaxis.range = [18, 102];

        layout.shapes = [{
            type: "line",
            x0: selectedPct,
            x1: selectedPct,
            y0: 0,
            y1: 1,
            yref: "paper",
            line: { color: "#0F766E", width: 1.8, dash: "dot" }
        }];

        Plotly.react("chart-speedtrend", traces, layout, plotlyConfig);
    }

    // GRAPH 4: DOMINANT FREQUENCY TREND
    function renderDominantFreqTrendGraph(axisVal, selectedPct) {
        const pctList = DASHBOARD_DATA.trends.pct_list;
        const traces = [];

        [1, 2, 3].forEach(wc => {
            const domFreqs = DASHBOARD_DATA.trends[`wconf_${wc}`][`dom_freq_${axisVal}`];
            traces.push({
                x: pctList,
                y: domFreqs,
                type: "scatter",
                mode: "lines+markers",
                name: `${CONFIG_LABELS[wc]} Dominant`,
                line: { color: CONFIG_COLORS[wc], width: 2.0 },
                marker: { size: 6 },
                hovertemplate: `<b>${CONFIG_LABELS[wc]} Dominant</b><br>Speed: %{x}%<br>Freq: %{y:.2f} Hz<extra></extra>`
            });
        });

        traces.push({
            x: pctList,
            y: DASHBOARD_DATA.trends.theo_frot,
            type: "scatter",
            mode: "lines",
            name: "Theoretical f_rot",
            line: { color: "#1E293B", width: 1.8, dash: "dash" },
            hovertemplate: "<b>Theoretical f_rot</b><br>Speed: %{x}%<br>f_rot: %{y:.2f} Hz<extra></extra>"
        });

        traces.push({
            x: pctList,
            y: DASHBOARD_DATA.trends.aliased_frot,
            type: "scatter",
            mode: "lines",
            name: "Expected Alias f_rot",
            line: { color: "#B45309", width: 2.0, dash: "dot" },
            hovertemplate: "<b>Expected Aliased f_rot</b><br>Speed: %{x}%<br>Alias: %{y:.2f} Hz<extra></extra>"
        });

        const layout = JSON.parse(JSON.stringify(baseLayout));
        layout.xaxis.title = "Fan Speed (%)";
        layout.yaxis.title = "Frequency (Hz)";
        layout.yaxis.range = [0, 35];

        layout.shapes = [
            {
                type: "line",
                x0: 18,
                x1: 102,
                y0: 25.0,
                y1: 25.0,
                line: { color: "#DC2626", width: 1.8, dash: "dashdot" }
            },
            {
                type: "line",
                x0: selectedPct,
                x1: selectedPct,
                y0: 0,
                y1: 1,
                yref: "paper",
                line: { color: "#0F766E", width: 1.8, dash: "dot" }
            }
        ];

        layout.annotations = [{
            x: 95,
            y: 25.8,
            text: "Nyquist Boundary (25.0 Hz)",
            showarrow: false,
            font: { color: "#991B1B", size: 10.5, family: "Fira Code, monospace" }
        }];

        Plotly.react("chart-domfreq", traces, layout, plotlyConfig);
    }

    // COMPARISON CHART
    function renderConfigComparisonGraph(selectedPct) {
        const pctList = DASHBOARD_DATA.trends.pct_list;
        const traces = [];

        const metricKey = configCompAxis === "total" ? "rms_total" : (`rms_${configCompAxis}`);
        const yAxisTitle = configCompAxis === "total"
            ? "Total Vector RMS Acceleration (g)"
            : `Axis ${configCompAxis.toUpperCase()} RMS Acceleration (g)`;

        tagConfigChart.textContent = yAxisTitle;

        [1, 2, 3].forEach(wc => {
            const values = DASHBOARD_DATA.trends[`wconf_${wc}`][metricKey];
            traces.push({
                x: pctList,
                y: values,
                type: "scatter",
                mode: "lines+markers",
                name: CONFIG_LABELS[wc],
                line: { color: CONFIG_COLORS[wc], width: 2.6 },
                marker: { size: 7 },
                hovertemplate: `<b>${CONFIG_LABELS[wc]}</b><br>Speed: %{x}%<br>RMS: %{y:.3f} g<extra></extra>`
            });
        });

        const layout = JSON.parse(JSON.stringify(baseLayout));
        layout.xaxis.title = "Fan Speed (%)";
        layout.yaxis.title = yAxisTitle;
        layout.xaxis.range = [18, 102];

        layout.shapes = [{
            type: "line",
            x0: selectedPct,
            x1: selectedPct,
            y0: 0,
            y1: 1,
            yref: "paper",
            line: { color: "#0F766E", width: 1.8, dash: "dot" }
        }];

        Plotly.react("chart-config-comp", traces, layout, plotlyConfig);
    }

    // Segment Toggle Event Listeners
    segmentButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            segmentButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            configCompAxis = btn.getAttribute("data-axis");
            const pctVal = parseInt(selSpeed.value);
            renderConfigComparisonGraph(pctVal);
        });
    });

    // CSV Export Event Listener
    btnExportCsv.addEventListener("click", () => {
        const wconfVal = selWconf.value;
        const pctVal = parseInt(selSpeed.value);
        const axisVal = selAxis.value;

        const speedIdx = pctList.indexOf(pctVal);
        const rpmVal = DASHBOARD_DATA.trends.rpm_list[speedIdx];
        const theoFrot = DASHBOARD_DATA.trends.theo_frot[speedIdx];
        const isAboveNyquist = theoFrot > DASHBOARD_DATA.metadata.nyquist_hz;
        const aliasedFrot = isAboveNyquist ? DASHBOARD_DATA.trends.aliased_frot[speedIdx] : "N/A";

        const configsToExport = (wconfVal === "all") ? [1, 2, 3] : [parseInt(wconfVal)];

        const headers = [
            "Configuration",
            "Fan Speed (%)",
            "RPM",
            "Axis",
            "RMS (g)",
            "Peak-to-Peak (g)",
            "Peak (g)",
            "Dominant Frequency (Hz)",
            "Dominant Amplitude (g)",
            "Theoretical Rotational Frequency (Hz)",
            "Expected Alias Frequency (Hz)",
            "Nyquist Frequency (Hz)"
        ];

        const rows = [headers.join(",")];

        configsToExport.forEach(wc => {
            const key = `${wc}_${pctVal}_${axisVal}`;
            const st = DASHBOARD_DATA.stats[key];
            const fft = DASHBOARD_DATA.fft_results[key];

            const row = [
                CONFIG_LABELS[wc],
                pctVal,
                rpmVal.toFixed(1),
                axisVal.toUpperCase(),
                st ? st.rms_g : "",
                st ? st.peak_to_peak_g : "",
                st ? st.peak_abs_g : "",
                fft ? fft.dominant_freq_hz : "",
                fft ? fft.dominant_amplitude_g : "",
                theoFrot.toFixed(2),
                aliasedFrot,
                25.0
            ];
            rows.push(row.join(","));
        });

        const csvContent = rows.join("\\n");
        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const configStr = (wconfVal === "all") ? "AllConfigs" : CONFIG_LABELS[wconfVal].split(" ")[0];
        const filename = `vibration_analysis_${configStr}_${pctVal}pct_${axisVal.toUpperCase()}.csv`;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showToast(`Exported: ${filename}`);
    });

    // Control Listeners
    selWconf.addEventListener("change", updateDashboard);
    selSpeed.addEventListener("change", updateDashboard);
    selAxis.addEventListener("change", updateDashboard);

    window.addEventListener("DOMContentLoaded", () => {
        updateDashboard();
    });
</script>
</body>
</html>
"""


def default_json_converter(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    elif isinstance(o, (np.floating,)):
        return float(o)
    elif isinstance(o, (np.ndarray,)):
        return o.tolist()
    elif pd.isna(o):
        return None
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")


def generate_professional_html(payload: dict):
    """Generate the professional light-theme self-contained HTML file."""
    print("[HTML] Formatting and embedding telemetry payload into professional dashboard template...")
    json_str = json.dumps(payload, default=default_json_converter)
    final_html = PROFESSIONAL_HTML_TEMPLATE.replace("__JSON_DATA__", json_str)

    with open(FINAL_HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(final_html)

    size_mb = os.path.getsize(FINAL_HTML_OUTPUT_PATH) / (1024 * 1024)
    print(f"[COMPLETE] Professional Analytics Dashboard generated: {FINAL_HTML_OUTPUT_PATH.resolve()}")
    print(f"[METRIC] HTML file size: {size_mb:.2f} MB")
    return FINAL_HTML_OUTPUT_PATH


def main():
    print("=" * 70)
    print("PROFESSIONAL ENGINEERING VIBRATION DASHBOARD GENERATOR")
    print("=" * 70)
    try:
        ensure_plotly_js()
        payload = build_data_payload()
        out_path = generate_professional_html(payload)
        print("\n" + "=" * 70)
        print("PROFESSIONAL DASHBOARD GENERATION SUCCEEDED!")
        print(f"Target: {out_path.resolve()}")
        print("=" * 70)
        return 0
    except Exception as e:
        print(f"[ERROR] Professional dashboard generation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
