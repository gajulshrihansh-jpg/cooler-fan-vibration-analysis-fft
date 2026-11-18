"""
Interactive Vibration Analysis Dashboard Generator (Version 2 Update)
----------------------------------------------------------------------
Updates include:
1. Measurement Limitations & Interpretation section (Fs=50Hz, Nyquist=25Hz, aliasing >=80%,
   sensor +/-8g clipping, caution on high-speed interpretation, neutral engineering language).
2. Improved FFT Graph Explanatory Note (dominant peak != rotational frequency, separate reporting).
3. Theoretical vs Measured Frequency Table (dynamically updating with selection).
4. Configuration Comparison Graph (RMS vs fan speed for Normal, Perpendicular, Opposite,
   selectable X, Y, Z, Total RMS).
5. Numerical Configuration Comparison Table (Normal, Perpendicular, Opposite across RMS & P2P).
6. Client-side CSV Download Button (generates and downloads selected condition CSV).
7. Preserved all dynamic warnings (Nyquist Aliasing, Sensor Saturation/Clipping).
8. Preserved all original Plotly interactions, dropdowns, and existing CSV calculations.
"""

import sys
import os
import json
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
import plotly

# ---------------------------------------------------------
# CONSTANTS & PATHS
# ---------------------------------------------------------
DATASET_PATH = Path("accelerometer (1).csv")
OUTPUT_DIR = Path("outputs")
HTML_OUTPUT_PATH = OUTPUT_DIR / "interactive_vibration_analysis.html"
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


def copy_local_plotly():
    """Copy plotly.min.js from package to outputs for offline standalone viewing."""
    try:
        pkg_dir = Path(plotly.__file__).parent
        bundled_js = pkg_dir / "package_data" / "plotly.min.js"
        if bundled_js.exists():
            shutil.copyfile(bundled_js, LOCAL_PLOTLY_JS)
            print(f"[INIT] Bundled offline plotly.min.js copied to {LOCAL_PLOTLY_JS.name}")
        else:
            print("[INIT] Bundled plotly.min.js not found in package; will rely on CDN.")
    except Exception as e:
        print(f"[WARN] Could not copy local plotly.min.js: {e}")


def build_dashboard_data():
    """Extract and package all data needed for the interactive dashboard into JSON."""
    print("[DATA] Loading raw CSV and computed metrics...")
    df = pd.read_csv(DATASET_PATH)
    stats_df = pd.read_csv(STATS_CSV)
    fft_df = pd.read_csv(FFT_CSV)
    speed_df = pd.read_csv(SPEED_CSV)
    config_df = pd.read_csv(CONFIG_CSV)

    # Time vector (length 3000)
    time_vec = [round(float(t), 3) for t in (np.arange(N_SAMPLES) / FS)]

    # FFT frequency vector (length 1501, 0 to 25 Hz)
    win = np.hanning(N_SAMPLES)
    win_sum = float(np.sum(win))
    freqs = np.fft.rfftfreq(N_SAMPLES, d=1.0 / FS)
    freq_vec = [round(float(f), 4) for f in freqs]

    # Precompute per-condition time waveforms & FFT spectra
    print("[COMPUTE] Precomputing time series and FFT spectra for dashboard...")
    conditions = {}
    for (wconf, pct), grp in df.groupby(["wconfid", "pctid"]):
        key = f"{wconf}_{pct}"
        cond_dict = {}
        for ax in AXES:
            sig = grp[ax].values
            # Round time series to 3 decimals (native sensor precision)
            cond_dict[ax] = [round(float(v), 3) for v in sig]

            # Compute normalized one-sided FFT spectrum
            sig_d = sig - np.mean(sig)
            fft_v = np.fft.rfft(sig_d * win)
            amp = (2.0 / win_sum) * np.abs(fft_v)
            amp[0] /= 2.0
            amp[-1] /= 2.0
            cond_dict[f"fft_{ax}"] = [round(float(a), 5) for a in amp]

        conditions[key] = cond_dict

    # Convert tables to easy lookup dictionaries
    stats_dict = {}
    for _, row in stats_df.iterrows():
        k = f"{int(row['wconfid'])}_{int(row['pctid'])}_{row['axis']}"
        stats_dict[k] = row.to_dict()

    fft_dict = {}
    for _, row in fft_df.iterrows():
        k = f"{int(row['wconfid'])}_{int(row['pctid'])}_{row['axis']}"
        row_clean = row.to_dict()
        if pd.isna(row_clean.get("aliased_f_rot_hz")):
            row_clean["aliased_f_rot_hz"] = None
        fft_dict[k] = row_clean

    # Precompute trend lines (RMS, P2P, Total RMS, and Dominant Frequency vs Speed)
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

        # Precompute Total RMS: sqrt(rms_x^2 + rms_y^2 + rms_z^2)
        rx = np.array(trends[f"wconf_{wconf}"]["rms_x"])
        ry = np.array(trends[f"wconf_{wconf}"]["rms_y"])
        rz = np.array(trends[f"wconf_{wconf}"]["rms_z"])
        r_tot = np.sqrt(rx ** 2 + ry ** 2 + rz ** 2)
        trends[f"wconf_{wconf}"]["rms_total"] = [round(float(v), 5) for v in r_tot.tolist()]

    payload = {
        "metadata": {
            "title": "Cooler Fan Vibration Analysis",
            "subtitle": "Interactive Time-Domain and FFT Analysis",
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

    print("[PACK] JSON data payload built successfully.")
    return payload


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cooler Fan Vibration Analysis | Interactive Dashboard (v2)</title>
    <!-- Plotly CDN with local fallback -->
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <script>
        if (typeof Plotly === 'undefined') {
            document.write('<script src="plotly.min.js"><\\/script>');
        }
    </script>
    <style>
        :root {
            --bg-body: #0d1117;
            --bg-card: #161b22;
            --bg-card-subtle: #21262d;
            --border-color: #30363d;
            --text-primary: #f0f6fc;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-red: #f85149;
            --accent-orange: #d29922;
            --color-normal: #f85149;
            --color-perp: #58a6ff;
            --color-opp: #3fb950;
            --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-body);
            color: var(--text-primary);
            font-family: var(--font-family);
            line-height: 1.5;
            padding: 20px 24px 60px 24px;
        }

        .container {
            max-width: 1480px;
            margin: 0 auto;
        }

        /* Header Section */
        header.dashboard-header {
            background: linear-gradient(180deg, #1f242c 0%, #161b22 100%);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px 28px;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }

        .header-titles {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 16px;
            margin-bottom: 16px;
        }

        h1.title {
            font-size: 26px;
            font-weight: 700;
            letter-spacing: -0.5px;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .subtitle {
            font-size: 14px;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        .metadata-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background-color: var(--bg-card-subtle);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 500;
            color: var(--text-primary);
        }

        .badge-accent {
            border-color: #388bfd40;
            background-color: #388bfd15;
            color: var(--accent-blue);
        }

        /* Control Panel */
        .controls-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 18px 24px;
            margin-bottom: 20px;
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            align-items: flex-end;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }

        .control-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
            flex: 1 1 200px;
        }

        .control-group label {
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
        }

        select.form-select {
            background-color: var(--bg-card-subtle);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 14px;
            font-weight: 500;
            outline: none;
            cursor: pointer;
            transition: border-color 0.2s, box-shadow 0.2s;
        }

        select.form-select:hover, select.form-select:focus {
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.2);
        }

        .btn-download {
            background-color: #238636;
            color: #ffffff;
            border: 1px solid rgba(240, 246, 252, 0.1);
            border-radius: 8px;
            padding: 10px 18px;
            font-size: 13.5px;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: background-color 0.2s, transform 0.1s;
            height: 42px;
        }

        .btn-download:hover {
            background-color: #2ea043;
            transform: translateY(-1px);
        }

        .btn-download:active {
            transform: translateY(0);
        }

        /* Alert Banners */
        .alerts-wrapper {
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-bottom: 20px;
        }

        .alert-banner {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 18px;
            border-radius: 8px;
            font-size: 13.5px;
            font-weight: 500;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }

        .alert-warning {
            background-color: rgba(210, 153, 34, 0.15);
            border: 1px solid rgba(210, 153, 34, 0.4);
            color: #f0c674;
        }

        .alert-danger {
            background-color: rgba(248, 81, 73, 0.15);
            border: 1px solid rgba(248, 81, 73, 0.4);
            color: #ff7b72;
        }

        .alert-icon {
            font-size: 18px;
            flex-shrink: 0;
        }

        /* Metrics Cards Grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 14px;
            margin-bottom: 20px;
        }

        .metric-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 14px 16px;
            transition: transform 0.15s ease, border-color 0.15s ease;
        }

        .metric-card:hover {
            border-color: var(--accent-blue);
            transform: translateY(-2px);
        }

        .metric-label {
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }

        .metric-value {
            font-size: 19px;
            font-weight: 700;
            color: #ffffff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .metric-unit {
            font-size: 12px;
            font-weight: 400;
            color: var(--text-muted);
            margin-left: 3px;
        }

        /* Table Card */
        .table-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 18px 22px;
            margin-bottom: 22px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.2);
        }

        .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border-color);
        }

        .table-title {
            font-size: 15px;
            font-weight: 700;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }

        .data-table th {
            background-color: var(--bg-card-subtle);
            color: var(--text-secondary);
            font-weight: 600;
            padding: 10px 12px;
            border-bottom: 1px solid var(--border-color);
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.4px;
        }

        .data-table td {
            padding: 9px 12px;
            border-bottom: 1px solid rgba(48, 54, 61, 0.6);
            color: var(--text-primary);
        }

        .data-table tr:hover td {
            background-color: rgba(56, 139, 253, 0.05);
        }

        .badge-config {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 11.5px;
        }

        .badge-normal { background-color: rgba(248, 81, 73, 0.15); color: #f85149; border: 1px solid rgba(248, 81, 73, 0.3); }
        .badge-perp { background-color: rgba(88, 166, 255, 0.15); color: #58a6ff; border: 1px solid rgba(88, 166, 255, 0.3); }
        .badge-opp { background-color: rgba(63, 185, 80, 0.15); color: #3fb950; border: 1px solid rgba(63, 185, 80, 0.3); }

        /* Graphs Grid */
        .graphs-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 24px;
        }

        @media (max-width: 1024px) {
            .graphs-grid {
                grid-template-columns: 1fr;
            }
        }

        .graph-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            box-shadow: 0 4px 16px rgba(0,0,0,0.25);
        }

        .graph-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border-color);
        }

        .graph-title {
            font-size: 15px;
            font-weight: 600;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .graph-tag {
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 4px;
            background-color: var(--bg-card-subtle);
            color: var(--text-secondary);
        }

        .plotly-chart {
            width: 100%;
            height: 380px;
        }

        /* Explanatory Note inside FFT Card */
        .fft-note-box {
            background-color: var(--bg-card-subtle);
            border-left: 3px solid var(--accent-orange);
            border-radius: 0 6px 6px 0;
            padding: 10px 14px;
            margin-top: 10px;
            font-size: 12px;
            color: var(--text-secondary);
            line-height: 1.5;
        }

        .fft-note-title {
            font-weight: 700;
            color: #f0c674;
            margin-bottom: 3px;
        }

        /* Configuration Comparison Section */
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 28px 0 14px 0;
        }

        .section-title {
            font-size: 20px;
            font-weight: 700;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .toggle-group {
            display: inline-flex;
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 3px;
            gap: 4px;
        }

        .toggle-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 600;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.15s;
        }

        .toggle-btn:hover {
            color: var(--text-primary);
        }

        .toggle-btn.active {
            background-color: var(--accent-blue);
            color: #ffffff;
        }

        /* Engineering & Limitations Sections */
        .explanation-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 22px 24px;
            margin-top: 20px;
        }

        .explanation-title {
            font-size: 17px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .explanation-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 14px;
        }

        .info-box {
            background-color: var(--bg-card-subtle);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 14px 16px;
        }

        .info-box-header {
            font-size: 13.5px;
            font-weight: 600;
            color: var(--accent-blue);
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .info-box p {
            font-size: 12.5px;
            color: var(--text-secondary);
            line-height: 1.55;
        }

        .limitations-list {
            list-style: none;
            counter-reset: lim-counter;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .limitations-list li {
            counter-increment: lim-counter;
            position: relative;
            padding-left: 28px;
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.6;
        }

        .limitations-list li::before {
            content: counter(lim-counter);
            position: absolute;
            left: 0;
            top: 2px;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background-color: var(--bg-card-subtle);
            border: 1px solid var(--border-color);
            color: var(--accent-blue);
            font-size: 11px;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .caution-box {
            background-color: rgba(210, 153, 34, 0.1);
            border: 1px solid rgba(210, 153, 34, 0.3);
            border-radius: 8px;
            padding: 12px 16px;
            margin-top: 14px;
            font-size: 12.5px;
            color: #f0c674;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        footer {
            margin-top: 36px;
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
        }
    </style>
</head>
<body>
<div class="container">

    <!-- Top Section -->
    <header class="dashboard-header">
        <div class="header-titles">
            <div>
                <h1 class="title">
                    <span>🌀</span> Cooler Fan Vibration Analysis
                </h1>
                <div class="subtitle">Interactive Time-Domain and FFT Spectral Analysis</div>
            </div>
            <div class="metadata-badges">
                <span class="badge badge-accent"><span class="badge-icon">📊</span> 153,000 Total Samples</span>
                <span class="badge"><span class="badge-icon">⚖️</span> 3 Weight Configs</span>
                <span class="badge"><span class="badge-icon">⚡</span> 17 Fan Speeds (20% – 100%)</span>
                <span class="badge"><span class="badge-icon">⏱️</span> 50 Hz Sampling Frequency</span>
                <span class="badge"><span class="badge-icon">🎯</span> 25 Hz Nyquist Limit</span>
                <span class="badge"><span class="badge-icon">📦</span> 3,000 Samples / Condition</span>
                <span class="badge"><span class="badge-icon">⏳</span> 60s / Condition</span>
            </div>
        </div>
    </header>

    <!-- Controls Panel -->
    <section class="controls-card">
        <div class="control-group">
            <label for="select-wconf">Weight Configuration</label>
            <select id="select-wconf" class="form-select">
                <option value="1">Normal (Red)</option>
                <option value="2">Perpendicular (Blue)</option>
                <option value="3">Opposite (Green)</option>
                <option value="all">All Configurations</option>
            </select>
        </div>
        <div class="control-group">
            <label for="select-speed">Fan Speed (%)</label>
            <select id="select-speed" class="form-select">
                <!-- Dynamically populated 20% to 100% -->
            </select>
        </div>
        <div class="control-group">
            <label for="select-axis">Acceleration Axis</label>
            <select id="select-axis" class="form-select">
                <option value="x">Axis X</option>
                <option value="y">Axis Y</option>
                <option value="z">Axis Z</option>
            </select>
        </div>
        <div>
            <button id="btn-export-csv" class="btn-download" title="Download selected operating condition as CSV">
                <span>📥</span> Download Selected Analysis CSV
            </button>
        </div>
    </section>

    <!-- Dynamic Warning Banners -->
    <div class="alerts-wrapper" id="alerts-container">
        <div class="alert-banner alert-warning" id="alert-aliasing" style="display: none;">
            <span class="alert-icon">⚠</span>
            <div><strong>Nyquist Aliasing Warning:</strong> Rotational frequency is above the 25 Hz Nyquist limit. The measured spectrum may contain aliasing.</div>
        </div>
        <div class="alert-banner alert-danger" id="alert-clipping" style="display: none;">
            <span class="alert-icon">⚠</span>
            <div><strong>Sensor Range Limit:</strong> Possible sensor saturation/clipping detected (accelerometer readings close to ±8.0 g limit). Note: this indicates sensor dynamic range saturation, not mechanical failure.</div>
        </div>
    </div>

    <!-- Metrics Cards Grid -->
    <section class="metrics-grid">
        <div class="metric-card">
            <div class="metric-label">Fan Speed</div>
            <div class="metric-value" id="metric-speed">--<span class="metric-unit">%</span></div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Theoretical RPM</div>
            <div class="metric-value" id="metric-rpm">--<span class="metric-unit">RPM</span></div>
        </div>
        <div class="metric-card">
            <div class="metric-label">RMS Acceleration</div>
            <div class="metric-value" id="metric-rms">--<span class="metric-unit">g</span></div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Peak-to-Peak</div>
            <div class="metric-value" id="metric-p2p">--<span class="metric-unit">g</span></div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Dominant Frequency</div>
            <div class="metric-value" id="metric-dom-freq">--<span class="metric-unit">Hz</span></div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Dominant Amplitude</div>
            <div class="metric-value" id="metric-dom-amp">--<span class="metric-unit">g</span></div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Theoretical f_rot</div>
            <div class="metric-value" id="metric-frot">--<span class="metric-unit">Hz</span></div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Nyquist Frequency</div>
            <div class="metric-value" id="metric-nyquist">25.0<span class="metric-unit">Hz</span></div>
        </div>
    </section>

    <!-- UPDATE 3: Theoretical vs Measured Frequency Table -->
    <section class="table-card">
        <div class="table-header">
            <div class="table-title"><span>📋</span> Theoretical vs Measured Frequency</div>
            <span class="graph-tag" id="tag-theo-table">Selected Condition</span>
        </div>
        <div style="overflow-x: auto;">
            <table class="data-table" id="table-theo-measured">
                <thead>
                    <tr>
                        <th style="width: 45%;">Parameter</th>
                        <th style="width: 55%;">Value</th>
                    </tr>
                </thead>
                <tbody id="tbody-theo-measured">
                    <!-- Populated dynamically -->
                </tbody>
            </table>
        </div>
    </section>

    <!-- Graphs Grid (2x2) -->
    <main class="graphs-grid">
        <!-- Graph 1: Time Domain -->
        <div class="graph-card">
            <div class="graph-header">
                <div class="graph-title"><span>📈</span> Graph 1: Time-Domain Waveform</div>
                <div class="graph-tag" id="tag-graph1">Time (s) vs Acceleration (g)</div>
            </div>
            <div id="chart-timedomain" class="plotly-chart"></div>
        </div>

        <!-- Graph 2: FFT Spectrum -->
        <div class="graph-card">
            <div class="graph-header">
                <div class="graph-title"><span>📊</span> Graph 2: FFT Amplitude Spectrum (0–25 Hz)</div>
                <div class="graph-tag" id="tag-graph2">Frequency (Hz) vs Amplitude (g)</div>
            </div>
            <div id="chart-fft" class="plotly-chart"></div>
            <!-- UPDATE 2: FFT Explanatory Note -->
            <div class="fft-note-box">
                <div class="fft-note-title">ℹ Interpretation Note:</div>
                Measured dominant spectral peak is not necessarily the fan rotational frequency.
                <ul style="margin: 4px 0 0 18px;">
                    <li>Theoretical rotational frequency is calculated from RPM ($f_{rot} = \text{RPM}/60$).</li>
                    <li>Measured dominant frequency is the largest non-DC FFT peak.</li>
                    <li>These are reported separately.</li>
                    <li>When rotational frequency exceeds Nyquist (25 Hz), the expected aliased frequency is shown separately.</li>
                </ul>
            </div>
        </div>

        <!-- Graph 3: Speed Trend (RMS vs Fan Speed) -->
        <div class="graph-card">
            <div class="graph-header">
                <div class="graph-title"><span>⚡</span> Graph 3: RMS Acceleration vs Fan Speed</div>
                <div class="graph-tag">Comparing All Configurations</div>
            </div>
            <div id="chart-speedtrend" class="plotly-chart"></div>
        </div>

        <!-- Graph 4: Dominant Frequency Trend -->
        <div class="graph-card">
            <div class="graph-header">
                <div class="graph-title"><span>🎯</span> Graph 4: Dominant Frequency vs Fan Speed</div>
                <div class="graph-tag">Measured vs Theoretical f_rot & Aliasing</div>
            </div>
            <div id="chart-domfreq" class="plotly-chart"></div>
        </div>
    </main>

    <!-- UPDATE 4 & 5: Configuration Comparison Section -->
    <section>
        <div class="section-header">
            <div class="section-title">
                <span>⚖️</span> Configuration Comparison
            </div>
            <div class="toggle-group" id="toggle-config-comp">
                <button class="toggle-btn active" data-axis="x">Axis X</button>
                <button class="toggle-btn" data-axis="y">Axis Y</button>
                <button class="toggle-btn" data-axis="z">Axis Z</button>
                <button class="toggle-btn" data-axis="total">Total RMS</button>
            </div>
        </div>

        <!-- Configuration Comparison Graph -->
        <div class="graph-card" style="margin-bottom: 20px;">
            <div class="graph-header">
                <div class="graph-title"><span>📊</span> RMS Acceleration vs Fan Speed Across Weight Configurations</div>
                <div class="graph-tag" id="tag-config-chart">Axis X RMS (g)</div>
            </div>
            <div id="chart-config-comp" class="plotly-chart" style="height: 360px;"></div>
        </div>

        <!-- Numerical Configuration Comparison Table -->
        <div class="table-card">
            <div class="table-header">
                <div class="table-title"><span>🔢</span> Numerical Configuration Comparison at Selected Fan Speed</div>
                <span class="graph-tag" id="tag-comp-table">Fan Speed: 50% (950 RPM)</span>
            </div>
            <div style="overflow-x: auto;">
                <table class="data-table" id="table-config-comp">
                    <thead>
                        <tr>
                            <th>Configuration</th>
                            <th>RPM</th>
                            <th>RMS X (g)</th>
                            <th>RMS Y (g)</th>
                            <th>RMS Z (g)</th>
                            <th>Total RMS (g)</th>
                            <th>Peak-to-Peak X (g)</th>
                            <th>Peak-to-Peak Y (g)</th>
                            <th>Peak-to-Peak Z (g)</th>
                        </tr>
                    </thead>
                    <tbody id="tbody-config-comp">
                        <!-- Populated dynamically -->
                    </tbody>
                </table>
            </div>
        </div>
    </section>

    <!-- Concept Explanations Section -->
    <section class="explanation-card">
        <div class="explanation-title">
            <span>💡</span> Engineering Reference & Concept Explanations
        </div>
        <div class="explanation-grid">
            <div class="info-box">
                <div class="info-box-header">1. What RMS Means</div>
                <p><strong>Root Mean Square (RMS)</strong> quantifies the effective continuous vibration energy of the signal. Unlike peak values which can be driven by a single transient spike, RMS reflects the sustained structural stress and fatigue experienced by the cooler fan assembly.</p>
            </div>
            <div class="info-box">
                <div class="info-box-header">2. What FFT Shows</div>
                <p>The <strong>Fast Fourier Transform (FFT)</strong> converts the raw time-domain accelerometer signal into the frequency domain. It shows the constituent sinusoidal frequencies present in the vibration and their corresponding amplitudes in units of <em>g</em>.</p>
            </div>
            <div class="info-box">
                <div class="info-box-header">3. Dominant FFT Frequency</div>
                <p>The <strong>Dominant FFT Frequency</strong> is the discrete non-DC frequency bin with the largest amplitude in the one-sided spectrum. It represents the predominant cyclical oscillation mode measured along that accelerometer axis.</p>
            </div>
            <div class="info-box">
                <div class="info-box-header">4. Theoretical f_rot vs Measured Dominant Peak</div>
                <p>The <strong>theoretical rotational frequency</strong> ($f_{rot} = \text{RPM} / 60$) is the fundamental shaft rotation speed. The measured dominant peak does <strong>not</strong> necessarily equal $f_{rot}$; it may correspond to harmonics, blade-pass frequencies, structural resonances, or sensor non-linearities. They are reported separately without assuming fault without independent verification.</p>
            </div>
            <div class="info-box">
                <div class="info-box-header">5. Nyquist Frequency ($f_{nyq} = 25\text{ Hz}$)</div>
                <p>The <strong>Nyquist frequency</strong> is half of the sampling frequency ($F_s/2 = 50/2 = 25\text{ Hz}$). By the Nyquist-Shannon theorem, it defines the highest vibration frequency that can be faithfully reconstructed without ambiguity.</p>
            </div>
            <div class="info-box">
                <div class="info-box-header">6. Why Frequencies Above 25 Hz Alias</div>
                <p>When the fan runs at $\ge 80\%$ speed ($1520\text{--}1900\text{ RPM}$), its rotational frequency ($25.33\text{--}31.67\text{ Hz}$) exceeds $25\text{ Hz}$. Because the sensor samples at 50 Hz, high-frequency oscillations fold back into the baseband at $f_{alias} = |50 - f_{rot}|$, appearing as false low-frequency peaks.</p>
            </div>
            <div class="info-box">
                <div class="info-box-header">7. Sensor Saturation / Clipping Distortion</div>
                <p>The onboard accelerometer has a finite dynamic range of $\pm 8.0\text{ g}$. When peak vibrations exceed this range, the waveform flat-tops (clips). Clipping acts like an aggressive non-linear square wave, injecting spurious odd harmonics and elevating low-frequency FFT noise. This reflects sensor range limits, not mechanical failure.</p>
            </div>
        </div>
    </section>

    <!-- UPDATE 1: Measurement Limitations & Interpretation Section -->
    <section class="explanation-card" style="border-left: 4px solid var(--accent-orange);">
        <div class="explanation-title" style="color: #f0c674;">
            <span>🔬</span> Measurement Limitations & Interpretation
        </div>
        <ul class="limitations-list">
            <li><strong>Sampling Frequency:</strong> The accelerometer acquired data at a fixed sampling frequency of $F_s = 50\text{ Hz}$ (sampling interval $\Delta t = 20\text{ ms}$).</li>
            <li><strong>Nyquist Frequency:</strong> The corresponding Nyquist limit is $F_s / 2 = 25\text{ Hz}$. Discrete spectral analysis is strictly bounded within the $0\text{ to }25\text{ Hz}$ band.</li>
            <li><strong>High-Speed Rotational Exceedance:</strong> At fan speeds of $80\%$ and above ($1520\text{ to }1900\text{ RPM}$), the theoretical rotational frequency $f_{rot}$ reaches $25.33\text{ to }31.67\text{ Hz}$, exceeding the $25\text{ Hz}$ Nyquist limit.</li>
            <li><strong>Spectral Aliasing:</strong> Rotational frequencies and harmonics above $25\text{ Hz}$ cannot be uniquely resolved at $F_s = 50\text{ Hz}$ and fold back (alias) into the measured baseband (e.g. $31.67\text{ Hz} \rightarrow 18.33\text{ Hz}$ at 100% speed).</li>
            <li><strong>Sensor Dynamic Range Saturation:</strong> At high operating speeds, vibration amplitudes for the Normal and Perpendicular configurations approach the sensor's approximately $\pm 8.0\text{ g}$ measurement span.</li>
            <li><strong>Harmonic Distortion from Clipping:</strong> Sensor saturation/clipping distorts the true time-domain acceleration waveform by truncating sinusoidal peaks, artificially introducing elevated noise floors and spurious harmonic components into the FFT spectrum.</li>
            <li><strong>Analytical Caution:</strong> High-speed FFT spectral results affected by aliasing or clipping must be interpreted with caution. Sensor saturation reflects measurement hardware dynamic range limits and does not prove mechanical failure.</li>
        </ul>
        <div class="caution-box">
            <span style="font-size: 18px;">ℹ</span>
            <div><strong>Engineering Note:</strong> Always evaluate spectral peaks in conjunction with time-domain waveforms and hardware specifications. Never attribute clipped signals to motor failure without calibrated high-range vibration instrumentation.</div>
        </div>
    </section>

    <footer>
        Cooler Fan Vibration Analysis Dashboard (Version 2) • Standalone Plotly Engine • Sampling Frequency: 50 Hz • Generated from accelerometer (1).csv
    </footer>

</div>

<!-- EMBEDDED DASHBOARD DATA -->
<script>
    const DASHBOARD_DATA = __JSON_DATA__;
</script>

<!-- DASHBOARD CONTROLLER SCRIPT -->
<script>
    // Configuration details
    const CONFIG_COLORS = {
        1: "#f85149", // Normal (Red)
        2: "#58a6ff", // Perpendicular (Blue)
        3: "#3fb950"  // Opposite (Green)
    };

    const CONFIG_LABELS = {
        1: "Normal",
        2: "Perpendicular",
        3: "Opposite"
    };

    const CONFIG_BADGES = {
        1: '<span class="badge-config badge-normal">Normal (Red)</span>',
        2: '<span class="badge-config badge-perp">Perpendicular (Blue)</span>',
        3: '<span class="badge-config badge-opp">Opposite (Green)</span>'
    };

    // DOM Elements
    const selWconf = document.getElementById("select-wconf");
    const selSpeed = document.getElementById("select-speed");
    const selAxis = document.getElementById("select-axis");
    const btnExportCsv = document.getElementById("btn-export-csv");

    const alertAliasing = document.getElementById("alert-aliasing");
    const alertClipping = document.getElementById("alert-clipping");

    // Metrics DOM
    const elSpeed = document.getElementById("metric-speed");
    const elRpm = document.getElementById("metric-rpm");
    const elRms = document.getElementById("metric-rms");
    const elP2p = document.getElementById("metric-p2p");
    const elDomFreq = document.getElementById("metric-dom-freq");
    const elDomAmp = document.getElementById("metric-dom-amp");
    const elFrot = document.getElementById("metric-frot");

    // Table DOMs
    const tbodyTheoMeasured = document.getElementById("tbody-theo-measured");
    const tagTheoTable = document.getElementById("tag-theo-table");
    const tbodyConfigComp = document.getElementById("tbody-config-comp");
    const tagCompTable = document.getElementById("tag-comp-table");

    // Config Comp chart toggle
    let configCompAxis = "x"; // "x", "y", "z", "total"
    const toggleButtons = document.querySelectorAll("#toggle-config-comp .toggle-btn");
    const tagConfigChart = document.getElementById("tag-config-chart");

    // Populate Fan Speed Dropdown (20% to 100%)
    const pctList = DASHBOARD_DATA.trends.pct_list;
    pctList.forEach((pct, idx) => {
        const rpm = DASHBOARD_DATA.trends.rpm_list[idx];
        const opt = document.createElement("option");
        opt.value = pct;
        opt.textContent = pct + "% (" + rpm + " RPM)";
        if (pct === 50) opt.selected = true; // Default 50%
        selSpeed.appendChild(opt);
    });

    // Common Plotly Layout Theme
    const baseLayout = {
        paper_bgcolor: "#161b22",
        plot_bgcolor: "#0d1117",
        font: { family: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif", color: "#8b949e", size: 11 },
        margin: { l: 55, r: 25, t: 30, b: 45 },
        legend: { orientation: "h", yanchor: "bottom", y: 1.02, xanchor: "right", x: 1, font: { size: 10 } },
        xaxis: { gridcolor: "#21262d", zerolinecolor: "#30363d" },
        yaxis: { gridcolor: "#21262d", zerolinecolor: "#30363d" }
    };

    const plotlyConfig = {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        displaylogo: false
    };

    // Update Dashboard State
    function updateDashboard() {
        const wconfVal = selWconf.value; // "1", "2", "3", or "all"
        const pctVal = parseInt(selSpeed.value);
        const axisVal = selAxis.value; // "x", "y", "z"

        const speedIdx = pctList.indexOf(pctVal);
        const rpmVal = DASHBOARD_DATA.trends.rpm_list[speedIdx];
        const theoFrot = DASHBOARD_DATA.trends.theo_frot[speedIdx];
        const isAboveNyquist = theoFrot > DASHBOARD_DATA.metadata.nyquist_hz;
        const aliasedFrot = DASHBOARD_DATA.trends.aliased_frot[speedIdx];

        // 1. Update Warnings
        if (isAboveNyquist) {
            alertAliasing.style.display = "flex";
        } else {
            alertAliasing.style.display = "none";
        }

        // Check for clipping
        let clippingDetected = false;
        const activeConfigs = (wconfVal === "all") ? [1, 2, 3] : [parseInt(wconfVal)];
        for (const wc of activeConfigs) {
            const key = wc + "_" + pctVal + "_" + axisVal;
            const st = DASHBOARD_DATA.stats[key];
            if (st && (Math.abs(st.min_g) >= 7.8 || Math.abs(st.max_g) >= 7.8 || st.peak_abs_g >= 7.8)) {
                clippingDetected = true;
                break;
            }
        }
        alertClipping.style.display = clippingDetected ? "flex" : "none";

        // 2. Update Metrics Cards
        elSpeed.innerHTML = pctVal + '<span class="metric-unit">%</span>';
        elRpm.innerHTML = rpmVal + '<span class="metric-unit">RPM</span>';
        elFrot.innerHTML = theoFrot.toFixed(2) + '<span class="metric-unit">Hz</span>';

        if (wconfVal !== "all") {
            const key = wconfVal + "_" + pctVal + "_" + axisVal;
            const st = DASHBOARD_DATA.stats[key];
            const fft = DASHBOARD_DATA.fft_results[key];

            elRms.innerHTML = (st ? st.rms_g.toFixed(3) : "--") + '<span class="metric-unit">g</span>';
            elP2p.innerHTML = (st ? st.peak_to_peak_g.toFixed(3) : "--") + '<span class="metric-unit">g</span>';
            elDomFreq.innerHTML = (fft ? fft.dominant_freq_hz.toFixed(2) : "--") + '<span class="metric-unit">Hz</span>';
            elDomAmp.innerHTML = (fft ? fft.dominant_amplitude_g.toFixed(4) : "--") + '<span class="metric-unit">g</span>';
        } else {
            const st1 = DASHBOARD_DATA.stats["1_" + pctVal + "_" + axisVal];
            const st2 = DASHBOARD_DATA.stats["2_" + pctVal + "_" + axisVal];
            const st3 = DASHBOARD_DATA.stats["3_" + pctVal + "_" + axisVal];

            const fft1 = DASHBOARD_DATA.fft_results["1_" + pctVal + "_" + axisVal];
            const fft2 = DASHBOARD_DATA.fft_results["2_" + pctVal + "_" + axisVal];
            const fft3 = DASHBOARD_DATA.fft_results["3_" + pctVal + "_" + axisVal];

            elRms.innerHTML = '<span style="font-size: 13px; color:#f85149;">' + st1.rms_g.toFixed(2) + '</span> | <span style="font-size: 13px; color:#58a6ff;">' + st2.rms_g.toFixed(2) + '</span> | <span style="font-size: 13px; color:#3fb950;">' + st3.rms_g.toFixed(2) + '</span><span class="metric-unit">g</span>';
            elP2p.innerHTML = '<span style="font-size: 13px; color:#f85149;">' + st1.peak_to_peak_g.toFixed(2) + '</span> | <span style="font-size: 13px; color:#58a6ff;">' + st2.peak_to_peak_g.toFixed(2) + '</span> | <span style="font-size: 13px; color:#3fb950;">' + st3.peak_to_peak_g.toFixed(2) + '</span><span class="metric-unit">g</span>';
            elDomFreq.innerHTML = '<span style="font-size: 13px; color:#f85149;">' + fft1.dominant_freq_hz.toFixed(1) + '</span> | <span style="font-size: 13px; color:#58a6ff;">' + fft2.dominant_freq_hz.toFixed(1) + '</span> | <span style="font-size: 13px; color:#3fb950;">' + fft3.dominant_freq_hz.toFixed(1) + '</span><span class="metric-unit">Hz</span>';
            elDomAmp.innerHTML = '<span style="font-size: 13px; color:#f85149;">' + fft1.dominant_amplitude_g.toFixed(3) + '</span> | <span style="font-size: 13px; color:#58a6ff;">' + fft2.dominant_amplitude_g.toFixed(3) + '</span> | <span style="font-size: 13px; color:#3fb950;">' + fft3.dominant_amplitude_g.toFixed(3) + '</span><span class="metric-unit">g</span>';
        }

        // 3. UPDATE 3: Theoretical vs Measured Frequency Table
        renderTheoreticalVsMeasuredTable(wconfVal, pctVal, axisVal, rpmVal, theoFrot, aliasedFrot, isAboveNyquist);

        // 4. GRAPH 1: TIME DOMAIN WAVEFORM
        renderTimeDomainGraph(activeConfigs, pctVal, axisVal);

        // 5. GRAPH 2: FFT AMPLITUDE SPECTRUM
        renderFFTGraph(activeConfigs, pctVal, axisVal, theoFrot, isAboveNyquist, aliasedFrot);

        // 6. GRAPH 3: SPEED TREND (RMS vs SPEED)
        renderSpeedTrendGraph(axisVal, pctVal);

        // 7. GRAPH 4: DOMINANT FREQUENCY TREND
        renderDominantFreqTrendGraph(axisVal, pctVal);

        // 8. UPDATE 4: Configuration Comparison Chart
        renderConfigComparisonGraph(pctVal);

        // 9. UPDATE 5: Numerical Configuration Comparison Table
        renderConfigComparisonTable(pctVal, rpmVal);
    }

    // UPDATE 3: Render Theoretical vs Measured Frequency Table
    function renderTheoreticalVsMeasuredTable(wconfVal, pctVal, axisVal, rpmVal, theoFrot, aliasedFrot, isAboveNyquist) {
        tagTheoTable.textContent = (wconfVal === "all" ? "All Configurations" : CONFIG_LABELS[wconfVal]) + " | " + pctVal + "% Speed | Axis " + axisVal.toUpperCase();

        const aliasDisplay = isAboveNyquist ? (aliasedFrot.toFixed(2) + " Hz") : "N/A (Below Nyquist)";

        let rowsHtml = "";

        if (wconfVal !== "all") {
            const key = wconfVal + "_" + pctVal + "_" + axisVal;
            const fft = DASHBOARD_DATA.fft_results[key];
            const domFreq = fft ? fft.dominant_freq_hz.toFixed(2) + " Hz" : "--";
            const domAmp = fft ? fft.dominant_amplitude_g.toFixed(4) + " g" : "--";

            rowsHtml = `
                <tr><td><strong>Fan Speed</strong></td><td>${pctVal} %</td></tr>
                <tr><td><strong>RPM</strong></td><td>${rpmVal} RPM</td></tr>
                <tr><td><strong>Theoretical Rotational Frequency</strong></td><td><strong>${theoFrot.toFixed(2)} Hz</strong></td></tr>
                <tr><td><strong>Nyquist Frequency</strong></td><td>25.0 Hz</td></tr>
                <tr><td><strong>Expected Aliased Frequency</strong></td><td>${aliasDisplay}</td></tr>
                <tr><td><strong>Measured Dominant FFT Frequency</strong></td><td><strong style="color: ${CONFIG_COLORS[wconfVal]};">${domFreq}</strong></td></tr>
                <tr><td><strong>Dominant FFT Amplitude</strong></td><td>${domAmp}</td></tr>
            `;
        } else {
            // For All Configurations: show comparison
            const fft1 = DASHBOARD_DATA.fft_results["1_" + pctVal + "_" + axisVal];
            const fft2 = DASHBOARD_DATA.fft_results["2_" + pctVal + "_" + axisVal];
            const fft3 = DASHBOARD_DATA.fft_results["3_" + pctVal + "_" + axisVal];

            const dom1 = fft1 ? fft1.dominant_freq_hz.toFixed(2) + " Hz" : "--";
            const dom2 = fft2 ? fft2.dominant_freq_hz.toFixed(2) + " Hz" : "--";
            const dom3 = fft3 ? fft3.dominant_freq_hz.toFixed(2) + " Hz" : "--";

            const amp1 = fft1 ? fft1.dominant_amplitude_g.toFixed(4) + " g" : "--";
            const amp2 = fft2 ? fft2.dominant_amplitude_g.toFixed(4) + " g" : "--";
            const amp3 = fft3 ? fft3.dominant_amplitude_g.toFixed(4) + " g" : "--";

            rowsHtml = `
                <tr><td><strong>Fan Speed</strong></td><td>${pctVal} %</td></tr>
                <tr><td><strong>RPM</strong></td><td>${rpmVal} RPM</td></tr>
                <tr><td><strong>Theoretical Rotational Frequency</strong></td><td><strong>${theoFrot.toFixed(2)} Hz</strong></td></tr>
                <tr><td><strong>Nyquist Frequency</strong></td><td>25.0 Hz</td></tr>
                <tr><td><strong>Expected Aliased Frequency</strong></td><td>${aliasDisplay}</td></tr>
                <tr><td><strong>Measured Dominant FFT Frequency</strong></td><td>
                    <span style="color:#f85149;">Normal: ${dom1}</span><br>
                    <span style="color:#58a6ff;">Perpendicular: ${dom2}</span><br>
                    <span style="color:#3fb950;">Opposite: ${dom3}</span>
                </td></tr>
                <tr><td><strong>Dominant FFT Amplitude</strong></td><td>
                    <span style="color:#f85149;">Normal: ${amp1}</span><br>
                    <span style="color:#58a6ff;">Perpendicular: ${amp2}</span><br>
                    <span style="color:#3fb950;">Opposite: ${amp3}</span>
                </td></tr>
            `;
        }

        tbodyTheoMeasured.innerHTML = rowsHtml;
    }

    // UPDATE 5: Render Numerical Configuration Comparison Table
    function renderConfigComparisonTable(pctVal, rpmVal) {
        tagCompTable.textContent = "Fan Speed: " + pctVal + "% (" + rpmVal + " RPM)";
        let rowsHtml = "";

        [1, 2, 3].forEach(wc => {
            const stX = DASHBOARD_DATA.stats[wc + "_" + pctVal + "_x"];
            const stY = DASHBOARD_DATA.stats[wc + "_" + pctVal + "_y"];
            const stZ = DASHBOARD_DATA.stats[wc + "_" + pctVal + "_z"];

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
                    <td>${rpmVal}</td>
                    <td>${rx.toFixed(3)}</td>
                    <td>${ry.toFixed(3)}</td>
                    <td>${rz.toFixed(3)}</td>
                    <td><strong>${rTot.toFixed(3)}</strong></td>
                    <td>${p2pX}</td>
                    <td>${p2pY}</td>
                    <td>${p2pZ}</td>
                </tr>
            `;
        });

        tbodyConfigComp.innerHTML = rowsHtml;
    }

    // UPDATE 4: Render Configuration Comparison Graph
    function renderConfigComparisonGraph(selectedPct) {
        const pctList = DASHBOARD_DATA.trends.pct_list;
        const traces = [];

        const metricKey = configCompAxis === "total" ? "rms_total" : ("rms_" + configCompAxis);
        const yAxisTitle = configCompAxis === "total"
            ? "Total RMS Acceleration (g)"
            : ("Axis " + configCompAxis.toUpperCase() + " RMS Acceleration (g)");

        tagConfigChart.textContent = yAxisTitle;

        [1, 2, 3].forEach(wc => {
            const values = DASHBOARD_DATA.trends["wconf_" + wc][metricKey];
            traces.push({
                x: pctList,
                y: values,
                type: "scatter",
                mode: "lines+markers",
                name: CONFIG_LABELS[wc],
                line: { color: CONFIG_COLORS[wc], width: 2.2 },
                marker: { size: 6 },
                hovertemplate: "<b>" + CONFIG_LABELS[wc] + "</b><br>Speed: %{x}%<br>RMS: %{y:.3f} g<extra></extra>"
            });
        });

        const layout = JSON.parse(JSON.stringify(baseLayout));
        layout.xaxis.title = "Fan Speed (%)";
        layout.yaxis.title = yAxisTitle;
        layout.xaxis.range = [18, 102];

        // Vertical highlight line at current speed
        layout.shapes = [{
            type: "line",
            x0: selectedPct,
            x1: selectedPct,
            y0: 0,
            y1: 1,
            yref: "paper",
            line: { color: "#8b949e", width: 1.5, dash: "dot" }
        }];

        Plotly.react("chart-config-comp", traces, layout, plotlyConfig);
    }

    // Toggle event for Configuration Comparison Axis
    toggleButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            toggleButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            configCompAxis = btn.getAttribute("data-axis");
            const pctVal = parseInt(selSpeed.value);
            renderConfigComparisonGraph(pctVal);
        });
    });

    // GRAPH 1: Time Domain Waveform
    function renderTimeDomainGraph(activeConfigs, pctVal, axisVal) {
        const timeVec = DASHBOARD_DATA.time;
        const traces = [];

        activeConfigs.forEach(wc => {
            const key = wc + "_" + pctVal;
            const cond = DASHBOARD_DATA.conditions[key];
            if (cond) {
                traces.push({
                    x: timeVec,
                    y: cond[axisVal],
                    type: "scatter",
                    mode: "lines",
                    name: CONFIG_LABELS[wc],
                    line: { color: CONFIG_COLORS[wc], width: 1.2 },
                    hovertemplate: "<b>" + CONFIG_LABELS[wc] + "</b><br>Time: %{x:.2f} s<br>Accel: %{y:.3f} g<extra></extra>"
                });
            }
        });

        const layout = JSON.parse(JSON.stringify(baseLayout));
        layout.xaxis.title = "Time (s)";
        layout.yaxis.title = "Axis " + axisVal.toUpperCase() + " Acceleration (g)";
        layout.xaxis.range = [0, 5.0]; // Zoom first 5s by default, user can pan/zoom to full 60s

        Plotly.react("chart-timedomain", traces, layout, plotlyConfig);
    }

    // GRAPH 2: FFT Amplitude Spectrum
    function renderFFTGraph(activeConfigs, pctVal, axisVal, theoFrot, isAboveNyquist, aliasedFrot) {
        const freqs = DASHBOARD_DATA.fft_freqs;
        const traces = [];

        activeConfigs.forEach(wc => {
            const key = wc + "_" + pctVal;
            const cond = DASHBOARD_DATA.conditions[key];
            const resKey = wc + "_" + pctVal + "_" + axisVal;
            const res = DASHBOARD_DATA.fft_results[resKey];
            if (cond) {
                traces.push({
                    x: freqs,
                    y: cond["fft_" + axisVal],
                    type: "scatter",
                    mode: "lines",
                    name: CONFIG_LABELS[wc] + " Spectrum",
                    line: { color: CONFIG_COLORS[wc], width: 1.4 },
                    hovertemplate: "<b>" + CONFIG_LABELS[wc] + "</b><br>Freq: %{x:.3f} Hz<br>Amp: %{y:.4f} g<extra></extra>"
                });

                // Mark measured dominant peak
                if (res) {
                    traces.push({
                        x: [res.dominant_freq_hz],
                        y: [res.dominant_amplitude_g],
                        type: "scatter",
                        mode: "markers",
                        name: CONFIG_LABELS[wc] + " Dominant Peak",
                        marker: { color: CONFIG_COLORS[wc], size: 8, symbol: "diamond" },
                        hovertemplate: "<b>" + CONFIG_LABELS[wc] + " Measured Dominant Peak</b><br>Freq: %{x:.2f} Hz<br>Amp: %{y:.4f} g<extra></extra>"
                    });
                }
            }
        });

        const layout = JSON.parse(JSON.stringify(baseLayout));
        layout.xaxis.title = "Frequency (Hz)";
        layout.yaxis.title = "Amplitude (g)";
        layout.xaxis.range = [0, 25.0];

        // Shapes for Theoretical f_rot and Aliased f_rot
        const shapes = [];
        const annotations = [];

        if (!isAboveNyquist) {
            // Theoretical rotational frequency vertical reference line
            shapes.push({
                type: "line",
                x0: theoFrot,
                x1: theoFrot,
                y0: 0,
                y1: 1,
                yref: "paper",
                line: { color: "#f0f6fc", width: 1.8, dash: "dash" }
            });
            annotations.push({
                x: theoFrot,
                y: 0.95,
                yref: "paper",
                text: "Theoretical rotational frequency: " + theoFrot.toFixed(2) + " Hz",
                showarrow: true,
                arrowhead: 2,
                ax: 40,
                ay: -20,
                font: { color: "#f0f6fc", size: 10 },
                bgcolor: "#21262d",
                bordercolor: "#30363d"
            });
        } else {
            // Above Nyquist: Expected Aliased rotational frequency vertical reference line
            shapes.push({
                type: "line",
                x0: aliasedFrot,
                x1: aliasedFrot,
                y0: 0,
                y1: 1,
                yref: "paper",
                line: { color: "#d29922", width: 2.0, dash: "dot" }
            });
            annotations.push({
                x: aliasedFrot,
                y: 0.95,
                yref: "paper",
                text: "Expected aliased rotational frequency: " + aliasedFrot.toFixed(2) + " Hz",
                showarrow: true,
                arrowhead: 2,
                ax: 40,
                ay: -25,
                font: { color: "#d29922", size: 10 },
                bgcolor: "#21262d",
                bordercolor: "#d29922"
            });
        }

        layout.shapes = shapes;
        layout.annotations = annotations;

        Plotly.react("chart-fft", traces, layout, plotlyConfig);
    }

    // GRAPH 3: Speed Trend (RMS vs Fan Speed)
    function renderSpeedTrendGraph(axisVal, selectedPct) {
        const pctList = DASHBOARD_DATA.trends.pct_list;
        const traces = [];

        [1, 2, 3].forEach(wc => {
            const rmsValues = DASHBOARD_DATA.trends["wconf_" + wc]["rms_" + axisVal];
            traces.push({
                x: pctList,
                y: rmsValues,
                type: "scatter",
                mode: "lines+markers",
                name: CONFIG_LABELS[wc],
                line: { color: CONFIG_COLORS[wc], width: 2 },
                marker: { size: 6 },
                hovertemplate: "<b>" + CONFIG_LABELS[wc] + "</b><br>Speed: %{x}%<br>RMS: %{y:.3f} g<extra></extra>"
            });
        });

        const layout = JSON.parse(JSON.stringify(baseLayout));
        layout.xaxis.title = "Fan Speed (%)";
        layout.yaxis.title = "Axis " + axisVal.toUpperCase() + " RMS Acceleration (g)";
        layout.xaxis.range = [18, 102];

        // Highlight selected fan speed with vertical reference line
        layout.shapes = [{
            type: "line",
            x0: selectedPct,
            x1: selectedPct,
            y0: 0,
            y1: 1,
            yref: "paper",
            line: { color: "#8b949e", width: 1.5, dash: "dot" }
        }];

        Plotly.react("chart-speedtrend", traces, layout, plotlyConfig);
    }

    // GRAPH 4: Dominant Frequency Trend
    function renderDominantFreqTrendGraph(axisVal, selectedPct) {
        const pctList = DASHBOARD_DATA.trends.pct_list;
        const traces = [];

        // Measured dominant frequencies
        [1, 2, 3].forEach(wc => {
            const domFreqs = DASHBOARD_DATA.trends["wconf_" + wc]["dom_freq_" + axisVal];
            traces.push({
                x: pctList,
                y: domFreqs,
                type: "scatter",
                mode: "lines+markers",
                name: CONFIG_LABELS[wc] + " Dominant",
                line: { color: CONFIG_COLORS[wc], width: 1.8 },
                marker: { size: 5 },
                hovertemplate: "<b>" + CONFIG_LABELS[wc] + " Dominant Freq</b><br>Speed: %{x}%<br>Freq: %{y:.2f} Hz<extra></extra>"
            });
        });

        // Theoretical Rotational Frequency reference curve
        traces.push({
            x: pctList,
            y: DASHBOARD_DATA.trends.theo_frot,
            type: "scatter",
            mode: "lines",
            name: "Theoretical f_rot",
            line: { color: "#f0f6fc", width: 1.8, dash: "dash" },
            hovertemplate: "<b>Theoretical f_rot</b><br>Speed: %{x}%<br>f_rot: %{y:.2f} Hz<extra></extra>"
        });

        // Expected Aliased Rotational Frequency reference curve
        traces.push({
            x: pctList,
            y: DASHBOARD_DATA.trends.aliased_frot,
            type: "scatter",
            mode: "lines",
            name: "Expected Aliased f_rot",
            line: { color: "#d29922", width: 2.0, dash: "dot" },
            hovertemplate: "<b>Expected Aliased f_rot</b><br>Speed: %{x}%<br>Alias: %{y:.2f} Hz<extra></extra>"
        });

        const layout = JSON.parse(JSON.stringify(baseLayout));
        layout.xaxis.title = "Fan Speed (%)";
        layout.yaxis.title = "Frequency (Hz)";
        layout.yaxis.range = [0, 35];

        // 25 Hz Nyquist Limit line & selected speed indicator
        layout.shapes = [
            {
                type: "line",
                x0: 18,
                x1: 102,
                y0: 25.0,
                y1: 25.0,
                line: { color: "#f85149", width: 1.5, dash: "dashdot" }
            },
            {
                type: "line",
                x0: selectedPct,
                x1: selectedPct,
                y0: 0,
                y1: 1,
                yref: "paper",
                line: { color: "#8b949e", width: 1.5, dash: "dot" }
            }
        ];

        layout.annotations = [{
            x: 95,
            y: 25.8,
            text: "Nyquist Limit (25 Hz)",
            showarrow: false,
            font: { color: "#f85149", size: 10 }
        }];

        Plotly.react("chart-domfreq", traces, layout, plotlyConfig);
    }

    // UPDATE 6: Client-Side CSV Export Functionality
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
            const key = wc + "_" + pctVal + "_" + axisVal;
            const st = DASHBOARD_DATA.stats[key];
            const fft = DASHBOARD_DATA.fft_results[key];

            const row = [
                CONFIG_LABELS[wc],
                pctVal,
                rpmVal,
                axisVal.toUpperCase(),
                st ? st.rms_g : "",
                st ? st.peak_to_peak_g : "",
                st ? st.peak_abs_g : "",
                fft ? fft.dominant_freq_hz : "",
                fft ? fft.dominant_amplitude_g : "",
                theoFrot,
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
        const configStr = (wconfVal === "all") ? "AllConfigs" : CONFIG_LABELS[wconfVal];
        a.download = `vibration_analysis_${configStr}_${pctVal}pct_${axisVal.toUpperCase()}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });

    // Event Listeners for Dropdowns
    selWconf.addEventListener("change", updateDashboard);
    selSpeed.addEventListener("change", updateDashboard);
    selAxis.addEventListener("change", updateDashboard);

    // Initial render
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


def generate_html(payload: dict):
    """Generate the self-contained HTML file."""
    print("[HTML] Generating standalone interactive dashboard HTML...")
    json_str = json.dumps(payload, default=default_json_converter)

    final_html = HTML_TEMPLATE.replace("__JSON_DATA__", json_str)

    with open(HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(final_html)

    file_size_mb = os.path.getsize(HTML_OUTPUT_PATH) / (1024 * 1024)
    print(f"[COMPLETE] Dashboard generated: {HTML_OUTPUT_PATH.resolve()}")
    print(f"[METRIC] HTML file size: {file_size_mb:.2f} MB")
    return HTML_OUTPUT_PATH


def main():
    print("=" * 65)
    print("INTERACTIVE VIBRATION ANALYSIS DASHBOARD GENERATOR (VERSION 2)")
    print("=" * 65)
    try:
        copy_local_plotly()
        payload = build_dashboard_data()
        out_path = generate_html(payload)
        print("\n" + "=" * 65)
        print("DASHBOARD V2 GENERATION COMPLETED SUCCESSFULLY!")
        print(f"File Path: {out_path.resolve()}")
        print("=" * 65)
        return 0
    except Exception as e:
        print(f"[ERROR] Failed to generate dashboard: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
