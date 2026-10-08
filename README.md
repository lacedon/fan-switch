# fan-switch

MicroPython script for a Raspberry Pi Pico that learns and replays the radio signal of a fan remote. It records a raw pulse train from a receiver module and plays it back through a transmitter module, so two buttons on the Pico can stand in for two buttons on the original remote.

## Wiring

| Pin  | Role                                                                 |
|------|----------------------------------------------------------------------|
| GP22 | RF receiver data in (`RX_PIN`)                                       |
| GP21 | RF transmitter data out (`TX_PIN`)                                   |
| GP16 | Button 1 (to GND, internal pull-up)                                  |
| GP17 | Button 2 (to GND, internal pull-up)                                  |
| GP18 | Record button (to GND, internal pull-up)                             |

## Usage

- **Record:** hold GP18 together with GP16 or GP17, then press the key on the original remote. The first complete frame caught is stored in the slot for that button. Release the buttons to finish.
- **Send:** press GP16 or GP17 alone. The saved frame for that button is transmitted, repeated `TX_REPEATS` times (the way real remotes repeat while a key is held). It sends once per press.

Saved frames are kept in RAM only, so they are lost on reset and you need to record them again.

## How it works

1. **Capture:** while recording, an interrupt on every rising and falling edge of the receiver pin stores the time since the previous edge in a ring buffer (`on_edge`).
2. **Framing:** `next_frame()` drains the buffer. Pulses shorter than `MIN_PULSE_US` are dropped as glitches. A pulse longer than `GAP_US` is treated as the gap between frames and closes the current frame. Frames with fewer than `MIN_PULSES` pulses are discarded as noise.
3. **Report:** a caught frame is printed over serial as raw durations, plus a best-guess bit string and hex value (`decode`, where a longer high than low means 1). This is only for debugging, and replay uses the raw durations.
4. **Replay:** `send()` toggles the TX pin, starting high, and holds each level for the recorded duration. It waits `TX_GAP_US` between repeats.

The tunable constants (`TX_REPEATS`, `TX_GAP_US`, `GAP_US`, `MIN_PULSES`, `MIN_PULSE_US`, `BUF_SIZE`) are at the top of [main.py](main.py).

## Upload

Copy `main.py` to the board with `mpremote`, for example `mpremote cp main.py :main.py + reset`.
