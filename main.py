import asyncio, gc, json, time
from machine import Pin, idle
from network import WLAN

# allocating pin 0 for testing things on the breadboard. should maybe remove later?
p0 = Pin(0, Pin.OUT)

# allocate the LED pin
LED = Pin("LED",Pin.OUT)

# utility LED blinker
async def blink(pattern):
    while True:
        for i in pattern():
            LED.toggle()
            time.sleep_ms(pattern[i])

pattern_ready=[1000,1000]
pattern_badconfig=[500,500,250,250]
pattern_networkerror=[100,500,100,500]

pumpPin = 7
gc.enable()

wlan = WLAN(WLAN.IF_STA)
wlan.active(True)

try:
    with open("/wifi.json") as f:
        network = json.load(f)
        ssid = network["ssid"]
        key = network["key"]
except FileNotFoundError:
    asyncio.run(blink(pattern_badconfig))
else:
    print(f'trying to connect to wifi network {ssid}...')

if not wlan.isconnected:
    try:
        timer = time.ticks_ms()
        wlan.connect(ssid,key)
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(),timer) >= 60000:
                raise RuntimeError
            idle()
    except RuntimeError:
        print(f'Couldn\'t connect to {ssid}. Bad password?')
        asyncio.run(blink(pattern_badconfig))


print('network config:', wlan.ipconfig('addr4'))
gc.collect() # my thinking is that this'll free the memory used by the json object

def launch_server():
    import lbis
    lbis.run(pumpPin,host="0.0.0.0",port=80)

async def main():
    asyncio.create_task(blink(lambda: pattern_ready))
    launch_server()

asyncio.run(main())


