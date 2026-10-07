# fan-switch: 433 MHz remote -> two events, for Raspberry Pi Pico (MicroPython).
#
# The receiver's DATA pin is sampled with an edge interrupt; frames are decoded
# with the same protocol table as the Arduino rc-switch library (covers EV1527,
# PT2262, HT6P20B and most cheap 433 MHz remotes).

import time
from array import array
from machine import Pin

# ---------------------------------------------------------------- config ----

RX_PIN = 22          # receiver DATA
LED_PIN = "LED"      # onboard LED, blinks on every recognized press

# Output events. mode "pulse": pin goes high for pulse_ms on each press.
#                mode "toggle": pin flips state on each press.
EVENTS = {
    1: {"pin": 16, "mode": "pulse", "pulse_ms": 300},
    2: {"pin": 17, "mode": "pulse", "pulse_ms": 300},
}

# Remote button code -> events to fire. Press a button with the REPL open to
# see its code. Any number of remotes/buttons can be listed here, and a button
# can fire both events, e.g.  0x123456: (1, 2),
CODES = {
    # 0xA1B2C1: (1,),
    # 0xA1B2C2: (2,),
}

CONFIRM_FRAMES = 2   # identical frames needed before a press counts (noise filter)
RELEASE_MS = 250     # silence after which the button is considered released
TOLERANCE = 60       # pulse length tolerance, percent


def on_event(event):
    """Called for every fired event; put custom actions here."""
    print("Event", event)


# ------------------------------------------------------------- receiver ----

# rc-switch protocols: (pulse_us, sync, zero, one, inverted)
# Protocol 4's sync gap is shorter than _SEPARATOR_US, so (as in rc-switch) it
# is listed only to keep the numbering.
PROTOCOLS = (
    (350, (1, 31), (1, 3), (3, 1), False),
    (650, (1, 10), (1, 2), (2, 1), False),
    (100, (30, 71), (4, 11), (9, 6), False),
    (380, (1, 6), (1, 3), (3, 1), False),
    (500, (6, 14), (1, 2), (2, 1), False),
    (450, (23, 1), (1, 2), (2, 1), True),
    (150, (2, 62), (1, 6), (6, 1), False),
)

_MAX_CHANGES = 67    # 32 bits * 2 edges + separator + sync
_SEPARATOR_US = 4300 # gaps longer than this end a frame

_timings = array("I", [0] * _MAX_CHANGES)
_frame = array("I", [0] * _MAX_CHANGES)
_frame_len = 0
_frame_ready = False
_count = 0
_last_edge = 0


def _on_edge(pin):
    # Hard IRQ: no allocation allowed, keep it short.
    global _timings, _frame, _frame_len, _frame_ready, _count, _last_edge
    now = time.ticks_us()
    duration = time.ticks_diff(now, _last_edge)
    _last_edge = now

    if duration > _SEPARATOR_US:
        # A separator closes the frame collected since the previous one.
        if _count > 7 and not _frame_ready:
            _timings, _frame = _frame, _timings
            _frame_len = _count
            _frame_ready = True
        _count = 0

    if _count >= _MAX_CHANGES:
        _count = 0
    _timings[_count] = duration
    _count += 1


def decode(timings, n, protocol):
    """Decode n timings (timings[0] = leading separator). Returns (code, bits) or None."""
    _, sync, zero, one, inverted = protocol
    delay = timings[0] // (sync[0] if inverted else sync[1])
    if delay == 0:
        return None
    tol = delay * TOLERANCE // 100
    zero_hi, zero_lo = delay * zero[0], delay * zero[1]
    one_hi, one_lo = delay * one[0], delay * one[1]

    code = 0
    bits = 0
    for i in range(2 if inverted else 1, n - 1, 2):
        hi, lo = timings[i], timings[i + 1]
        code <<= 1
        if abs(hi - zero_hi) < tol and abs(lo - zero_lo) < tol:
            pass
        elif abs(hi - one_hi) < tol and abs(lo - one_lo) < tol:
            code |= 1
        else:
            return None
        bits += 1
    if bits < 4:
        return None
    return code, bits


def read_frame():
    """Return (code, bits, protocol_number) for a newly received frame, or None."""
    global _frame_ready
    if not _frame_ready:
        return None
    result = None
    for number, protocol in enumerate(PROTOCOLS, 1):
        decoded = decode(_frame, _frame_len, protocol)
        if decoded:
            result = decoded + (number,)
            break
    _frame_ready = False
    return result


# --------------------------------------------------------------- outputs ----

class Output:
    def __init__(self, pin, mode="pulse", pulse_ms=300):
        self.pin = Pin(pin, Pin.OUT, value=0)
        self.mode = mode
        self.pulse_ms = pulse_ms
        self.off_at = None

    def fire(self):
        if self.mode == "toggle":
            self.pin.toggle()
        else:
            self.pin.value(1)
            self.off_at = time.ticks_add(time.ticks_ms(), self.pulse_ms)

    def update(self, now):
        if self.off_at is not None and time.ticks_diff(now, self.off_at) >= 0:
            self.pin.value(0)
            self.off_at = None


# ------------------------------------------------------------------ main ----

def main():
    outputs = {event: Output(**cfg) for event, cfg in EVENTS.items()}
    led = Output(LED_PIN, "pulse", 100)

    rx = Pin(RX_PIN, Pin.IN)
    rx.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_on_edge, hard=True)
    print("fan-switch listening on GP%d" % RX_PIN)

    current = None   # code of the button being held
    seen = 0         # frames received for it
    last_seen = 0

    while True:
        now = time.ticks_ms()
        frame = read_frame()

        if frame:
            code, bits, protocol = frame
            if code == current:
                seen += 1
            else:
                current, seen = code, 1
            last_seen = now

            # Fire once per press; remotes repeat the frame while held.
            if seen == CONFIRM_FRAMES:
                led.fire()
                events = CODES.get(code)
                if events:
                    for event in events:
                        outputs[event].fire()
                        on_event(event)
                else:
                    print("Unknown code 0x%X (%d bits, protocol %d) - add to CODES:"
                          % (code, bits, protocol))
                    print("    0x%X: (1,)," % code)

        elif current is not None and time.ticks_diff(now, last_seen) > RELEASE_MS:
            current = None

        for output in outputs.values():
            output.update(now)
        led.update(now)
        time.sleep_ms(1)


main()
