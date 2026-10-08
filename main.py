from machine import Pin
import time

RX_PIN = 22
BUTTON_PINS = (16, 17)  # wired to GND, internal pull-up (pressed = 0)
RECORD_PIN = 18         # held together with one of BUTTON_PINS = record; alone = send
TX_PIN = 21
TX_REPEATS = 8          # remotes repeat the frame while a key is pressed
TX_GAP_US = 10000       # low time between repeats
BUF_SIZE = 512          # max edges buffered between main loop passes
GAP_US = 4000           # a pulse longer than this ends a frame (sync/idle gap)
MIN_PULSES = 24         # shorter frames are treated as noise
MIN_PULSE_US = 80       # shorter pulses are treated as glitches

rx = Pin(RX_PIN, Pin.IN)
buttons = [Pin(p, Pin.IN, Pin.PULL_UP) for p in BUTTON_PINS]
record_button = Pin(RECORD_PIN, Pin.IN, Pin.PULL_UP)
tx = Pin(TX_PIN, Pin.OUT, value=0)

# saved[0] is the frame caught while button 1 (GP16) and the record button (GP18)
# were held, saved[1] the one for button 2 (GP17) and the record button
saved = [None, None]

buf = [0] * BUF_SIZE  # pulse durations in us
head = 0
tail = 0
last_edge = time.ticks_us()
dropped = 0
edges = 0
seen = []  # every pulse read this session, for debugging
cur = []  # frame being assembled across next_frame() calls


def on_edge(pin):
    global head, last_edge, dropped, edges
    edges += 1
    now = time.ticks_us()
    dur = time.ticks_diff(now, last_edge)
    last_edge = now
    nxt = (head + 1) % BUF_SIZE
    if nxt == tail:
        dropped += 1
        return
    buf[head] = dur
    head = nxt


def start_listening():
    global head, tail, last_edge, dropped, edges, cur, seen
    seen = []
    head = tail = 0
    dropped = 0
    edges = 0
    cur = []
    last_edge = time.ticks_us()
    rx.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=on_edge)


def stop_listening():
    rx.irq(handler=None)


def decode(pulses):
    """Guess bits from (high, low) pairs: longer high = 1, longer low = 0."""
    bits = ""
    for i in range(0, len(pulses) - 1, 2):
        bits += "1" if pulses[i] > pulses[i + 1] else "0"
    value = int(bits, 2) if bits else 0
    return bits, value


def report(frame):
    print("frame: %d pulses, min=%dus max=%dus" % (len(frame), min(frame), max(frame)))
    print("  raw:", frame)
    bits, value = decode(frame)
    print("  bits(%d): %s  hex=0x%X" % (len(bits), bits, value))


def next_frame():
    """Return the next complete frame from the buffer, or None if there isn't one yet."""
    global tail, cur
    while tail != head:
        dur = buf[tail]
        tail = (tail + 1) % BUF_SIZE
        if len(seen) < 300:
            seen.append(dur)
        if dur >= GAP_US:
            frame, cur = cur, []
            if len(frame) >= MIN_PULSES:
                return frame
        elif dur >= MIN_PULSE_US:
            cur.append(dur)
            if len(cur) > BUF_SIZE:
                cur = []
    return None


def pressed_index():
    for i, b in enumerate(buttons):
        if b.value() == 0:
            return i
    return None


def capture(index):
    """Listen while button `index` and the record button are held; save the first frame caught."""
    print("button %d + record pressed, listening..." % (index + 1))
    start_listening()
    caught = False
    while buttons[index].value() == 0 and record_button.value() == 0:
        if not caught:
            frame = next_frame()
            if frame:
                saved[index] = frame
                caught = True
                stop_listening()
                print("saved[%d] =" % index)
                report(frame)
        time.sleep_ms(5)
    stop_listening()
    if dropped:
        print("warning: buffer overflow, dropped edges:", dropped)
    if not caught:
        print("button %d released, nothing caught (%d edges seen)" % (index + 1, edges))
        print("  pulses (us):", seen)
    time.sleep_ms(50)  # debounce


def wait_us(us):
    start = time.ticks_us()
    while time.ticks_diff(time.ticks_us(), start) < us:
        pass


def send(index):
    """Replay saved[index] on the transmitter while the button is held."""
    frame = saved[index]
    if frame is None:
        print("button %d: nothing saved yet" % (index + 1))
        return
    print("button %d pressed, sending saved[%d] x%d" % (index + 1, index, TX_REPEATS))
    for _ in range(TX_REPEATS):
        level = 1
        for dur in frame:
            tx.value(level)
            wait_us(dur)
            level ^= 1
        tx.value(0)
        wait_us(TX_GAP_US)


def main():
    print("Hold GP%d + (GP%d or GP%d) to record from GP%d; GP%d or GP%d alone sends on GP%d" % (RECORD_PIN, BUTTON_PINS[0], BUTTON_PINS[1], RX_PIN, BUTTON_PINS[0], BUTTON_PINS[1], TX_PIN))
    while True:
        index = pressed_index()
        if index is not None:
            time.sleep_ms(50)  # let GP18 settle when both are pressed together
            if record_button.value() == 0:
                capture(index)
            else:
                send(index)
                while buttons[index].value() == 0:  # send once per press
                    time.sleep_ms(10)
                time.sleep_ms(50)  # debounce
        time.sleep_ms(10)


main()
