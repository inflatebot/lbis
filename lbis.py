from phew import server, logging
from machine import Pin, WDT, reset
import asyncio

ouppy = WDT(timeout=10000)

async def feed_async():
  while True:
    ouppy.feed()
    await asyncio.sleep(5)

def run(pin,host,port):
    global pumpSwitch
    pumpSwitch = Pin(pin or 0, Pin.OUT)
    pumpSwitch.value(0) # make sure it's off to start
    asyncio.create_task(feed_async())
    server.run(host or "0.0.0.0", port or 80)

@server.route("/api/marco", methods=["GET"])
def ping(request):
  return "Polo!", 200, {"Content-Type": "application/json"}

@server.route("/api/restart", methods=["POST"])
def restart(request):
    # restart the server
    print("Restarting...")
    reset()
    return "Restarting...", 200, {"Content-Type": "application/json"}

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
