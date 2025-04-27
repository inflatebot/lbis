import json
from microdot import Microdot
#from phew import server
from machine import Pin, PWM, soft_reset

server = Microdot()
# PWM stuff
pump_pwm = None
PWM_MAX_DUTY = 65535
# TODO: explore encapsulating this stuff in an object

def run(pin,host,port):
    global pump_pwm
    pump_pin = Pin(pin or 7, Pin.OUT)
    pump_pwm = PWM(pump_pin)
    pump_pwm.freq(1000)
    pump_pwm.duty_u16(0) # (0% duty cycle = off)
    server.run(host=host or "0.0.0.0", port=port or 80)

@server.get("/api/marco")
async def ping(request):
  response_body = json.dumps({"message": "Polo!"})
  return response_body, 200, {"Content-Type": "application/json"}

@server.post("/api/restart")
async def restart(request):
    # restart the server
    print("Restarting...")
    soft_reset()
    response_body = json.dumps({"message": "Restarting..."})
    return response_body, 200, {"Content-Type": "application/json"}

@server.post("/api/setPumpState")
async def set_pump_state(request):
  global pump_pwm
  try:
    # PORT: Use request.json instead of request.data
    reqState = float(request.json["pump"])
    if 0.0 <= reqState <= 1.0:
        duty_cycle = int(reqState * PWM_MAX_DUTY)
        pump_pwm.duty_u16(duty_cycle)
        print(f"setPumpState called: state={reqState:.2f}, duty={duty_cycle}") # Added logging
        response_body = json.dumps({"state": reqState})
        return response_body, 200, {"Content-Type": "application/json"}
    else:
        response_body = json.dumps({"error": "Invalid state value. Must be between 0.0 and 1.0."})
        return response_body, 400, {"Content-Type": "application/json"}
  except (KeyError, ValueError, TypeError) as e:
      response_body = json.dumps({"error": f"Invalid request data: {e}"})
      return response_body, 400, {"Content-Type": "application/json"}

@server.get("/api/getPumpState")
async def get_pump_state(request):
  global pump_pwm
  current_duty = pump_pwm.duty_u16()
  current_state = current_duty / PWM_MAX_DUTY
  #print(f"getPumpState called: duty={current_duty}, state={current_state:.2f}") # old debug call
  # Return JSON object with state
  response_body = json.dumps({"state": current_state})
  return response_body, 200, {"Content-Type": "application/json"}

@server.errorhandler(404)
async def catchall(request):
  response_body = json.dumps({"error": "Not Found"})
  return response_body, 404, {"Content-Type": "application/json"}
