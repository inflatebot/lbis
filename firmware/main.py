import gc, json, time
from machine import Pin, idle
from network import WLAN
import lbis as lbis

gc.enable()

### wifi stuff
wlan = WLAN(WLAN.IF_STA)
wlan.active(True)
wlan.config(pm=WLAN.PM_NONE)
try:
    with open("/wifi.json") as f:
        network = json.load(f)
        ssid = network["ssid"]
        key = network["key"]
except FileNotFoundError:
    print(f'wifi.json not found')

print('network config:', wlan.ipconfig('addr4'))
print(f'trying to connect to wifi network {ssid}...')
try:
    wlan.connect(ssid,key)
    while not wlan.isconnected():
        idle()
except RuntimeError:
    print(f'Couldn\'t connect to {ssid}. Bad password?')

print('network config:', wlan.ipconfig('addr4'))
gc.collect() # my thinking is that this'll free the memory used by the json object
### end wifi stuff

# allocating pin 0 for testing things on the breadboard. should maybe remove later?
p0 = Pin(0, Pin.OUT)
pumpPin = 6

lbis.run(pumpPin,host="0.0.0.0",port=80)
