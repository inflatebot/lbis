from phew import server
from machine import Pin, PWM, soft_reset # Import PWM

# Rename global variable for clarity
pump_pwm = None
PWM_MAX_DUTY = 65535 # Maximum value for duty_u16

def run(pin,host,port):
    global pump_pwm
    pump_pin = Pin(pin or 7, Pin.OUT)
    pump_pwm = PWM(pump_pin) # Initialize PWM on the pin
    pump_pwm.freq(1000) # Set PWM frequency (e.g., 1kHz)
    pump_pwm.duty_u16(0) # Start with pump off (0% duty cycle)
    server.run(host or "0.0.0.0", port or 80)

@server.route("/api/marco", methods=["GET"])
def ping(request):
  return "Polo!", 200, {"Content-Type": "application/json"}

@server.route("/api/restart", methods=["POST"])
def restart(request):
    # restart the server
    print("Restarting...")
    soft_reset()
    return "Restarting...", 200, {"Content-Type": "application/json"}

@server.route("/api/setPumpState", methods=["POST"])
def set_pump_state(request): # Renamed function
  global pump_pwm
  try:
    reqState = float(request.data["pump"])
    # Validate input is between 0.0 and 1.0
    if 0.0 <= reqState <= 1.0:
        duty_cycle = int(reqState * PWM_MAX_DUTY)
        pump_pwm.duty_u16(duty_cycle)
        # Return the set state
        return f"{reqState:.2f}", 200, {"Content-Type": "application/json"}
    else:
        return "Invalid state value. Must be between 0.0 and 1.0.", 400, {"Content-Type": "application/json"}
  except (KeyError, ValueError, TypeError) as e:
      return f"Invalid request data: {e}", 400, {"Content-Type": "application/json"}

@server.route("/api/getPumpState", methods=["GET"])
def get_pump_state(request): # Renamed function
  global pump_pwm
  current_duty = pump_pwm.duty_u16()
  current_state = current_duty / PWM_MAX_DUTY
  return f"{current_state:.2f}", 200, {"Content-Type": "application/json"}

@server.catchall()
def catchall(request):
  return f"Not Found", 404, {"Content-Type": "application/json"}
  #return json.dumps({"message" : "Not Found"}), 404, {"Content-Type": "application/json"}
