# Cooler Fan Vibration Analysis Using Accelerometer Measurements and FFT

## Project Overview

This project investigates the vibration characteristics of a variable-speed cooler fan using triaxial accelerometer measurements and Fast Fourier Transform (FFT) techniques.

The analysis evaluates the effect of fan speed and blade weight configurations on vibration behaviour through time-domain statistical analysis, frequency-domain analysis, and interactive data visualization.

## Project Objectives

- Analyze vibration acceleration along X, Y, and Z axes.
- Calculate time-domain statistical parameters.
- Perform FFT-based frequency-domain analysis.
- Investigate the effect of different blade weight configurations.
- Examine dominant vibration frequencies and amplitudes.
- Evaluate Nyquist frequency limitations and aliasing.
- Identify sensor saturation and measurement limitations.
- Compare vibration characteristics across different operating speeds.

## Experimental Dataset

The dataset contains 153,000 observations across 51 experimental conditions.

| Parameter                | Value      |
| ------------------------ | ---------- |
| Number of configurations | 3          |
| Fan speed range          | 20%–100%   |
| Maximum fan speed        | 1900 RPM   |
| Number of speed settings | 17         |
| Sampling frequency       | 50 Hz      |
| Sampling interval        | 20 ms      |
| Samples per condition    | 3000       |
| Recording duration       | 60 seconds |
| Accelerometer axes       | X, Y, Z    |
| Nyquist frequency        | 25 Hz      |

### Blade Weight Configurations

1. Normal
2. Perpendicular
3. Opposite

## Methodology

### 1. Data Processing

Loading and organizing the accelerometer dataset according to fan speed and blade weight configuration.

### 2. Time-Domain Analysis

Calculation of:

- Mean
- Standard deviation
- Root Mean Square (RMS)
- Minimum and maximum acceleration
- Peak-to-peak amplitude
- Absolute peak acceleration

### 3. Frequency-Domain Analysis

FFT analysis using:

- Mean centering
- Hann window
- Real Fast Fourier Transform (rFFT)
- One-sided amplitude spectrum
- Dominant frequency identification

### 4. Performance Evaluation

Comparison of vibration behaviour across different speeds and configurations, including investigation of aliasing and sensor clipping.

## Interactive Dashboard

The project includes interactive HTML dashboards for exploring vibration analysis results and comparing different operating conditions.

Open the HTML dashboard files inside the `outputs` folder using a web browser.

## Visualizations

The project includes:

- Dominant amplitude vs. fan speed
- Dominant frequency vs. fan speed
- Peak-to-peak acceleration vs. fan speed
- Representative FFT spectrum
- Representative time-domain waveform
- RMS acceleration vs. fan speed

## Technologies Used

- Python
- NumPy
- Pandas
- Matplotlib
- Plotly
- Fast Fourier Transform (FFT)
- CSV Data Processing
- HTML, CSS and JavaScript

## Project Files

| File                               | Description                              |
| ---------------------------------- | ---------------------------------------- |
| `accelerometer (1).csv`            | Original accelerometer dataset           |
| `vibration_analysis.py`            | Main analysis pipeline                   |
| `interactive_dashboard.py`         | Interactive dashboard script             |
| `generate_redesigned_dashboard.py` | Redesigned dashboard generator           |
| `check_manual_output.py`           | Manual calculation verification          |
| `PROJECT_REPORT.md`                | Detailed technical report                |
| `outputs/`                         | Analysis results, figures and dashboards |

## Limitations

The analysis is subject to the sampling frequency and accelerometer measurement range.

The 25 Hz Nyquist limit restricts the directly observable frequency range. Higher rotational frequencies may produce aliasing effects. Sensor saturation may also affect measured vibration amplitudes and FFT results.

## Author

**Author:** Shrihansh H. Gajul

**Department:** Mechanical Engineering

**Institution:** Fr. Conceicao Rodrigues College of Engineering

## Acknowledgements

This project was developed as an engineering vibration analysis study using accelerometer measurements and computational signal processing techniques.
