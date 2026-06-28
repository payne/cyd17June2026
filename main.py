"""
CYD entry point: alternates between Chuck Norris quotes and the clock.
Starts with a 20-second Chuck Norris quote, then shows the clock for 5
seconds, then back to a (different) quote for 20 seconds, repeating.
"""
import time
import random
import chuck
import clock

CHUCK_SECONDS = 20
CLOCK_SECONDS = 5


def main():
    display = clock.setup_display()
    random.seed(time.ticks_us())

    display.text("Connecting WiFi...", 10, 10, 0xFFFF)
    wifi_ok = clock.connect_wifi()
    display.fill(clock.BG_COLOR)

    if wifi_ok:
        clock.sync_time()
    else:
        display.text("No WiFi - using", 10, 10, 0xF800)
        display.text("internal clock only", 10, 25, 0xF800)
        time.sleep(2)

    chuck.init()
    while True:
        chuck.step(display, CHUCK_SECONDS)
        clock.run_for(display, CLOCK_SECONDS)


main()
