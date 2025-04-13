def connect_to_wifi():
    import network
    import time

    print("Connecting to WiFi", end="")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect("Wokwi-GUEST", "")
    while not wlan.isconnected():
        print(".", end="")
        time.sleep(0.1)
    print(" Connected!")
    print(wlan.ifconfig())