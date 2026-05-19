# Scanning Field Control

Python GUI and controllers for acoustic field scanning with a motorized XY stage, Tektronix AFG, and PicoScope 5442D.

This project is used to scan acoustic fields point by point. At each XY point, the software can trigger one or more excitation frequencies while keeping voltage and burst cycles unchanged. The acquired waveforms and metadata are saved for later pressure/phase reconstruction and signal inspection.

## Hardware

- XY stage controller: SIGMA KOKI GSC-02C
- XY stage model: HPS80-50X-M5
- Function generator: Tektronix AFG3022B
- Oscilloscope: PicoScope 5442D
- Optional Z stage: LabJack-based Z stage controller

## Main Entry

Run the main control GUI:

```bash
python Main_gui.py
```

The GUI contains these panels:

- `AFG Control`: connect/configure the Tektronix AFG, set sine waveform, burst settings, trigger source, output on/off.
- `Stage Control`: connect the XY stage, move axes, home/set zero, set speed, refresh status.
- `Scan`: configure scan grid, frequency sweep, hydrophone distance estimate, scan preview, readiness checklist, and live scan monitor.
- `PicoScope`: connect/configure PicoScope, select channels, resolution, sample rate, trigger, capture test, save folder, and waveform display.
- `Log`: runtime messages.

The GUI uses a scrollable adaptive layout so it can be used on smaller remote-desktop screens.

## Installation

Recommended Python version:

- Python 3.9 or newer

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

PicoScope control also requires the PicoSDK driver and the `pypicosdk` Python package to be correctly installed on the measurement computer.

## Typical Workflow

1. Start `Main_gui.py`.
2. Connect AFG.
3. Configure AFG sine amplitude, offset, burst cycles, burst mode, trigger output, and trigger source.
4. Connect Stage.
5. Home/set zero for the stage axes.
6. Connect PicoScope.
7. In PicoScope panel:
   - Choose capture channels.
   - Choose save channels.
   - Select input range.
   - Select `8-bit` or `12-bit` resolution.
   - Set sample rate.
   - Set duration, pre-trigger, trigger source, threshold, and direction.
   - Click `Apply Config`.
   - Choose save folder.
8. Use `Capture Test` to verify trigger and waveform.
9. In Scan panel:
   - Set `X0`, `X1`, `dX`.
   - Set `Y0`, `Y1`, `dY`.
   - Set dwell time.
   - Set frequency start/stop in MHz and frequency step in kHz.
   - Check the readiness checklist and XY preview.
10. Move the stage to `(X0, Y0)` before starting.
11. Click `Start Scan`.

## Multi-Frequency Scan Behavior

At each scan point:

1. The stage stays at the same XY position.
2. AFG voltage, offset, burst cycles, and burst settings stay unchanged.
3. Only the excitation frequency changes.
4. PicoScope captures one waveform for each requested frequency.
5. All frequency waveforms for that point are saved into one NPZ file per saved channel.

Repeated sampling at one point is currently disabled. The old repeated-trigger logic is kept as comments in the code for future restoration.

## Scan Panel

### Frequency Sweep

Inputs:

- `Freq MHz`: start frequency in MHz.
- `to`: stop frequency in MHz.
- `step kHz`: frequency interval in kHz.

Example:

- Start: `2.0 MHz`
- Stop: `2.1 MHz`
- Step: `5 kHz`

This produces 21 frequencies:

```text
2.000, 2.005, 2.010, ..., 2.100 MHz
```

### Scan Monitor

The Scan panel displays live scan progress:

- Current scan status.
- Current XY position.
- Current point index and total point count.
- Current frequency index and total frequency count.
- Progress bar.
- Elapsed time.
- Estimated remaining time.

### Readiness / XY Preview

The Scan panel also shows:

- Stage ready state.
- AFG ready state.
- Pico ready state.
- Pico config state.
- Save folder state.
- XY scan grid preview.
- Current point and completed points during scan.
- `Open Save Folder` button.

For dense grids such as `101 x 101`, the preview switches to a compact pixel-style display so points do not overlap.

### Hydrophone Distance Estimate

After `Capture Test`, the Scan panel can estimate hydrophone distance from trigger-to-received-signal delay.

Inputs:

- Hydrophone channel.
- Sound speed, default `1500 m/s`.
- Threshold sigma.

Method:

1. Detect trigger onset from the trigger channel.
2. Detect hydrophone onset from the selected hydrophone channel.
3. Onset is defined as a signal clearly above the background noise threshold.
4. Compute:

```text
distance = delay_time * sound_speed
```

The detected onset times are marked on the Pico waveform plot with dashed vertical lines and time labels in microseconds.

## PicoScope Panel

### Resolution

The GUI supports:

- `8-bit`
- `12-bit`

### Sample Rate Limit Check

The controller checks the requested sample rate against expected PicoScope 5442D limits.

Approximate limits currently used:

- 8-bit:
  - 1 enabled channel: up to 1000 MHz
  - 2 enabled channels: up to 500 MHz
  - 3-4 enabled channels: up to 250 MHz
- 12-bit:
  - 1 enabled channel: up to 500 MHz
  - 2 enabled channels: up to 250 MHz
  - 3-4 enabled channels: up to 125 MHz

Enabled channel count includes the trigger source and all capture channels.

If the requested sample rate is too high, the GUI shows an error instead of applying the configuration.

### Connection State

PicoScope connection is verified using `open_unit()` and `ping_unit()`. If no PicoScope is connected, the GUI should show:

```text
Disconnected | Not connected
```

## Saved Data

Scan data is saved as NPZ files. For multi-frequency scans, each point/channel file contains:

- `time_s`
- channel waveform array
- `x_mm`
- `y_mm`
- `point_index`
- `frequency_count`
- `excitation_frequencies_hz`
- `excitation_frequencies_mhz`
- `signal_shape = frequency_count x samples`
- per-frequency metadata

The waveform shape for multi-frequency capture is:

```text
frequency_count x samples
```

## Main Code Files

- `Main_gui.py`: main GUI entry point and layout.
- `app_context.py`: shared runtime state between panels/controllers.
- `afg_controller.py`: Tektronix AFG control.
- `pico_controller.py`: PicoScope control, configuration, capture, saving.
- `stage_controller.py`: XY stage control.
- `scan_controller.py`: raster scan logic and multi-frequency triggering.
- `gui_afg_panel.py`: AFG GUI panel.
- `gui_stage_panel.py`: Stage GUI panel.
- `gui_pico_panel.py`: PicoScope GUI panel and waveform display.
- `gui_scan_panel.py`: Scan GUI panel, monitor, preview, hydrophone distance estimate.
- `gui_log_panel.py`: log panel.
- `labjack_zstage_controller.py`: optional Z stage controller.
- `testafg.py`: AFG test script.

## Postprocessing Tools

Postprocessing scripts are stored in:

```text
F:\Jianqing\Project lead-free piezo in holography\postprocessscan
```

Important tools:

- `postprocess_pressure_fft.py`: process older single-frequency scans.
- `postprocess_multifrequency_pressure_fft.py`: process multi-frequency scans.
- `gui_multifrequency_pressure_maps.py`: GUI for multi-frequency pressure/voltage/phase maps.
- `gui_singlefrequency_pressure_maps.py`: GUI for older single-frequency pressure/voltage/phase maps.
- `inspect_point_frequency_signal.py`: inspect one XY point at one frequency from multi-frequency raw data.
- `inspect_singlefrequency_signal.py`: inspect one XY point from older single-frequency raw data.
- `plot_utils.py`: shared plotting helpers.

### Multi-Frequency Map GUI

Run:

```bash
python gui_multifrequency_pressure_maps.py
```

Usage:

1. Select the raw input folder.
2. Select output folder.
3. Enter channel, frequency count, start/stop/step.
4. Enter hydrophone sensitivity.
5. Enter gate window in microseconds.
6. Click `Process`.
7. Use `View` to show all frequencies or one frequency.
8. Select `pressure`, `voltage`, or `phase`.
9. Click `Save figure` if needed.

Pressure/voltage maps use amplitude from the Fourier component at each excitation frequency. Phase maps use the phase at that frequency.

### Point Signal Inspection

Use these tools to inspect raw time-domain signals:

- Multi-frequency raw data:

```bash
python inspect_point_frequency_signal.py
```

- Single-frequency raw data:

```bash
python inspect_singlefrequency_signal.py
```

The GUI uses map coordinates. Raw scan coordinate conversion is handled internally.

`Analyze` and `Save` are separate:

- `Analyze`: load and plot the selected signal.
- `Save`: save the current analysis result to the output folder.

## Stage Conversion Notes

For HPS80-50X-M5:

Half step:

```text
1 pulse = 1 um = 0.001 mm
```

Full step:

```text
1 pulse = 2 um = 0.002 mm
```

The current stage controller uses mm-based commands and software-tracked positions.

## Troubleshooting

### PicoScope shows disconnected

Check:

- PicoScope USB cable.
- PicoSDK driver installation.
- Whether another program is using the PicoScope.
- Whether `pypicosdk` can open the device.

### Save folder is missing

Use the PicoScope panel `Save` section and click `Browse`. The Scan panel also has `Open Save Folder` after a folder is selected.

### Scan cannot start

Check:

- Stage connected and positioned at `(X0, Y0)`.
- AFG connected.
- PicoScope connected.
- PicoScope config applied.
- Save folder selected.
- Save channels selected.
- AFG trigger source and burst settings applied.

### Process failed in postprocessing GUI

Check:

- Input folder contains raw scan NPZ files.
- Processed NPZ path is valid.
- Output folder exists or can be created.
- Frequency count/start/stop/step match the actual raw data.
- Gate window is inside the captured time range.

## Notes

- During scan, the software assumes the stage is already at `(X0, Y0)` before `Start Scan`.
- The scan path is `X+`, return X to row start, then `Y+`.
- Multi-frequency scans save all frequencies for a point in one file.
- Voltage and burst cycles do not change inside a multi-frequency point; only frequency changes.
