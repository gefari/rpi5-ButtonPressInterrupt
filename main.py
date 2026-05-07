"""
Button Press Interrupt Handler for Raspberry Pi 5
==================================================
Monitors GPIO 17 for falling-edge events (button presses) using the
Linux GPIO character device interface via the `gpiod` library.

Hardware setup:
    - Connect one leg of a momentary push-button to GPIO 17 (physical pin 11).
    - Connect the other leg to GND (e.g. physical pin 9).
    - The internal or external pull-up resistor keeps the line HIGH at rest;
      pressing the button pulls it LOW, producing a falling edge.

Software requirements:
    - libgpiod  (system library):  sudo apt install libgpiod-dev
    - python3-gpiod (Python binding): sudo apt install python3-gpiod
      or: pip install gpiod

Usage:
    python3 main.py

    Press Ctrl-C or send SIGTERM to exit cleanly.

GPIO line model (gpiod v1 API used here):
    Chip  -> represents /dev/gpiochipN (the GPIO controller)
    Line  -> represents a single GPIO pin on that chip
    Event -> a timestamped record of a rising or falling edge
"""

import gpiod   # Linux GPIO character device library (python3-gpiod)
import signal  # UNIX signal handling — used to catch SIGTERM
import time    # Wall-clock time used for software debouncing


# ---------------------------------------------------------------------------
# Debounce configuration
# ---------------------------------------------------------------------------
# Mechanical buttons "bounce" — they produce multiple rapid transitions when
# pressed or released.  Any event that arrives within DEBOUNCE_TIME seconds
# of the previous valid event is silently discarded.
DEBOUNCE_TIME = 0.5  # seconds

# Tracks the wall-clock time of the last accepted event.
# Initialised to 0 so the very first press is always accepted.
last_event_time = 0


# ---------------------------------------------------------------------------
# GPIO chip / line initialisation
# ---------------------------------------------------------------------------
# 'gpiochip0' is the primary GPIO controller on the Raspberry Pi.
# On RPi 5 this maps to /dev/gpiochip0 (RP1 south-bridge GPIO controller).
chip = gpiod.Chip('gpiochip0')

# Print chip metadata — useful for confirming the correct controller is open.
print(f"Chip name: {chip.name()}")      # e.g. "gpiochip0"
print(f"Chip label: {chip.label()}")    # e.g. "pinctrl-rp1" on RPi 5
print(f"Number of lines: {chip.num_lines()}")  # total GPIO lines on this chip

# Obtain a handle to GPIO line 17 (BCM numbering).
# No kernel resource is allocated yet — that happens in line.request() below.
line = chip.get_line(17)  # GPIO 17 — physical pin 11 on the 40-pin header


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------
# Map SIGTERM (sent by systemd / `kill`) to a KeyboardInterrupt so the same
# cleanup path (the `except KeyboardInterrupt` block) handles both Ctrl-C
# and process termination signals gracefully.
signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))


# ---------------------------------------------------------------------------
# Request exclusive access to the GPIO line
# ---------------------------------------------------------------------------
# consumer  : identifies this process in /sys/kernel/debug/gpio and `gpioinfo`
# type      : LINE_REQ_EV_FALLING_EDGE — the kernel will queue an event each
#             time the line transitions from HIGH (3.3 V) to LOW (0 V), i.e.
#             when the button is pressed (assuming active-low wiring).
line.request(consumer="button", type=gpiod.LINE_REQ_EV_FALLING_EDGE)


# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------
print("Waiting for falling edge events...")
try:
    while True:
        # Block for up to 1 second waiting for an edge event.
        # Returns True if an event is ready, False on timeout.
        # Using a timeout (rather than blocking indefinitely) keeps the loop
        # alive and responsive to KeyboardInterrupt / SIGTERM.
        if line.event_wait(sec=1):

            # Consume one event from the kernel queue.
            # event.sec  : seconds component of the event timestamp (CLOCK_MONOTONIC)
            # event.nsec : nanoseconds component of the event timestamp
            event = line.event_read()

            # Wall-clock time used for debounce comparison.
            # (event timestamps are monotonic and not directly comparable
            #  to time.time(), so we use time.time() for the debounce window.)
            current_time = time.time()

            if (current_time - last_event_time) > DEBOUNCE_TIME:
                # Enough time has elapsed — treat this as a genuine button press.
                print(f"Valid event detected at {event.sec}.{event.nsec}")
                last_event_time = current_time

                # -------------------------------------------------------
                # Insert application logic here, e.g.:
                #   toggle_led()
                #   send_mqtt_message()
                #   increment_counter()
                # -------------------------------------------------------

            else:
                # Event arrived too soon after the last one — likely bounce.
                print("Event ignored (debounce)")

except KeyboardInterrupt:
    # Raised by Ctrl-C in the terminal or by the SIGTERM handler above.
    print("Exiting...")

finally:
    # Always release the GPIO line and close the chip, even if an unexpected
    # exception occurs.  Failing to do so leaves the line reserved and the
    # next run (or gpioset/gpioget) will get a "Device or resource busy" error.
    line.release()
    chip.close()
