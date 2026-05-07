import gpiod
import signal
import time

DEBOUNCE_TIME = 0.5
last_event_time = 0

# Open the chip
chip = gpiod.Chip('gpiochip0')

# Get chip information
print(f"Chip name: {chip.name()}")
print(f"Chip label: {chip.label()}")
print(f"Number of lines: {chip.num_lines()}")

line = chip.get_line(17)  # GPIO 17

signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))

# Request falling edge events
line.request(consumer="button", type=gpiod.LINE_REQ_EV_FALLING_EDGE)

print("Waiting for falling edge events...")
try:
    while True:
        if line.event_wait(sec=1):
            
            event = line.event_read()
            current_time = time.time()
            
            # Check if enough time has passed since last event
            if (current_time - last_event_time) > DEBOUNCE_TIME:
                print(f"Valid event detected at {event.sec}.{event.nsec}")
                last_event_time = current_time
                # Process your event here
            else:
                print("Event ignored (debounce)")
except KeyboardInterrupt:
    print("Exiting...")
    
finally:
    line.release()
    chip.close()
