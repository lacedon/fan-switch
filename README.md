# fan-switch
A small project for Raspberry Pi Pico and 433mhz Transmitter

The Pico listens to 433 MHz remotes and fires **event 1** or **event 2**
depending on which button was pressed. Any number of remotes can be mapped,
and one button can fire both events.

## Wiring

| Receiver | Pico                                   |
|----------|----------------------------------------|
| VCC      | 3V3 (pin 36), or VBUS (pin 40) if 5 V-only |
| GND      | GND                                    |
| DATA     | GP22 (pin 29)                          |

- Pico GPIOs are **not 5 V tolerant**. Modules like RXB6 / SRX882 run fine at
  3.3 V. If yours needs 5 V (e.g. MX-RM-5V / XY-MK-5V), put a divider on DATA
  (10 kΩ in series, 20 kΩ to GND).
- Solder a 17.3 cm wire to the ANT pad for decent range.
- Event outputs: GP16 (event 1) and GP17 (event 2). The onboard LED blinks on
  every recognized press.

## Setup

1. Flash MicroPython onto the Pico (hold BOOTSEL, plug in, drop the `.uf2`).
2. Copy `main.py` to the Pico, e.g. `mpremote cp main.py :main.py`.
3. Open the REPL (`mpremote` or Thonny) and press each remote button. Unknown
   codes are printed:
   ```
   Unknown code 0xA1B2C1 (24 bits, protocol 1) - add to CODES:
       0xA1B2C1: (1,),
   ```
4. Add the codes to `CODES` in `main.py` with the event(s) they should fire,
   copy the file again and reset the Pico.

Each event can `pulse` its pin (for `pulse_ms`) or `toggle` it on every press;
see `EVENTS` in `main.py`.
