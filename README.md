# scanning-field

Automated scanning project for acoustic field measurement.

## Devices

- Stage controller: SIGMA KOKI GSC-02C
- Stage model: HPS80-50X-M5
- Function generator: Tektronix AFG3022B
- Receiver: PicoScope 5442D

## Current development status

### Computer A
- Stage control development
- Relative motion test finished
- mm conversion added
- Stable motion verified at low speed

### Computer B
- Function generator development
- PicoScope development
- AFG + Pico linkage under testing

## Python version

Recommended:

- Python 3.9

## Main files

- `stage_controller.py`: stage control
- `afg_controller.py`: function generator control
- `pico_controller.py`: PicoScope control
- `scan_controller.py`: scan workflow
- `Main.py`: main entry
- `test_stage.py`: pulse-based stage test
- `test_stage_mm.py`: mm-based stage test

## Notes

For HPS80-50X-M5:
half step
- 1 pulse = 1 um = 0.001 mm
full step
- 1 pulse = 2 um = 0.002 mm
## Install dependencies

```bash
python -m pip install -r requirements.txt