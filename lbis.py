from phew import connect_to_wifi, server, logging
from machine import Pin,WDT # we have 512k so it's in our best interest to be choosy
import utime

# init stuff
#ouppy = WDT(timeout=5000) # 5 second timeout
ip = connect_to_wifi("Photon","eradelta") # we're just gonna trust that phew's connect_to_wifi() function works
print("Connected to WiFi, IP:", ip)
#utime.sleep(0.1) # wait for USB (although since power is coming from USB this might be redundant? look the example implementation had this)

pumpSwitch = Pin(7, Pin.OUT) # my schematic has pin 7 for the i/o but i may use a different one

@server.route("/api/setPumpState", methods=["POST"])
def switch(request):
  global pumpSwitch
  pumpState = pumpSwitch.value()
  reqState = request.data["pump"]
  # should no-op nicely if the value is already as requested, or if a value besides on/off is specified (i can futz with PWM later)
  if reqState in [0,1] and pumpState != reqState:
    pumpSwitch.value(reqState)
  return f"{pumpSwitch.value()}", 200, {"Content-Type": "application/json"}
  #return json.dumps({"message" : "OK"}), 200, {"Content-Type": "application/json"}

@server.route("/api/getPumpState", methods=["GET"])
def stateCheck():
  return f"{pumpSwitch.value()}", 200, {"Content-Type": "application/json"}
  #return json.dumps({"message" : pumpSwitch.value()}), 200, {"Content-Type": "application/json"}

@server.catchall()
def catchall(request):
  return f"Not Found", 404, {"Content-Type": "application/json"}
  #return json.dumps({"message" : "Not Found"}), 404, {"Content-Type": "application/json"}
