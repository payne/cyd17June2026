import time

print("Hello from MicroPython on CYD!")
for i in range(5):
    print("tick", i)
    time.sleep(0.2)

import machine
print("Free heap:", __import__("gc").mem_free())
print("CPU freq:", machine.freq())
