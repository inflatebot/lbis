# Leg-worn Belly Inflation System (lBIS)

### The lBIS Discord bot is now being developed in [its own repo.](https://github.com/inflatebot/lbis_discord)

The Leg-worn Belly Inflation System, or lBIS (lowercase L, read like "ibis" [^1]) is a discreet wearable air pump that inflates the user at a gentle, safe(-ish) pace. It is designed to be worn casually, as one would a plug or ring, and be easy to maintain. It is controlled remotely using a WiFi-enabled microcontroller. The components are assembled onto a simple webbing legband which is worn under the clothes.

The source code and plans for lBIS are distributed under the [MIT License.](LICENSE.MD)

> [!IMPORTANT]
> - While this repository does not contain any explicit content, the device and the activities it enables are for adults ONLY. Support WILL NOT BE PROVIDED if there is reason to believe the one requesting said support is a minor.
> - The lBIS prototype is a reference design that uses off-the-shelf components. This is the designer's first major electronics project. It should not be taken as gospel on the best way to execute this concept. The purpose of open-sourcing lBIS is for the interest and curiosity of the kink community and as a public document of the project. Take the advice herein with a grain of salt and use your own judgement. The prototype was built with a... we'll say *lax* attitude for the builder's well-being. The builder however does care about *your* well-being, and will try to steer you towards doing this better than they did.

> [!CAUTION]
> - lBIS inflates the user via air enema, a process which carries an inherent risk. lBIS is not intended for users who are not already comfortable and experienced inflating themselves. While the pump utilized *shouldn't* be capable of causing severe injury, by building and using lBIS, you agree to do so at your own risk. See [Safety](#safety) for recommended practice. 
> - lBIS opens up the possibility of public play. Ensure that your usage of lBIS is compliant with regional laws, public decency, and common sense. Don't Be That Guy™.

# Materials

- A diaphragm air pump capable of running on 5V
	- The prototype uses an off-the-shelf USB-powered aquarium pump from Amazon, based on a PYP370 pump module, which appears to be the standard. [DFRobot also carries it directly.](https://www.dfrobot.com/product-2374.html)
- A WiFi-enabled microcontroller
	- The prototype uses a Raspberry Pi Pico 2 W but any Micropython-capable controller could work
- A DC motor driver capable of switching 5V and being signalled by 3.3V (or 5V if that's what your I/O pins use)
	- This should be most of them, but a MOSFET-based driver module is recommended, as relays can wear or become damaged.
- A power supply configured to provide 5V to two loads
	- The prototype uses an off-the-shelf USB battery bank with 2 USB-A output ports, but a solution could be built with simpler components
- (If not using a battery bank with a power-off button) A basic 5V-capable on/off switch
- An enclosure for the components (may be 3D-printed, assembled manually, or [James Channel-ed](https://www.youtube.com/watch?v=sbvp3kuU2ak), depending on your gumption and level of experience
- Solder, iron, (possibly) heatshrink insulation
- Webbing made of a meltable fabric, at least an inch wide, buckles
	- The prototype uses 1.5-inch nylon webbing as it was on hand. 
- A way to robustly join pieces of webbing
	- The prototype was sewn together by hand using thick upholstery needles. It may also be feasible to heat-weld the nylon together, but it won't be as nice, and heating nylon irreversibly softens it.
- Lighter
	- For melting the ends of webbing and airline tubing
- Heat gun
	- For heatshrink; lighter could also work but do this properly if you can)
- Soft aquarium airline tubing
- (Optional) Aquarium check valve (to keep the pump end of the airline tubing clean, and enable easy cleaning and replacement of the user end)
- (Optional) Enema nozzle
	- An inflatable CleanStream-style plug was used in the prototype, for the possibility of interopterating with the Edge-o-Matic 3000, but if you have a preference, use that. The bore should either be capable of accepting standard 3/16" (4mm) airline tubing directly, or be easily adaptable.

# Construction

## Microcontroller Preparation
1. Flash the latest MicroPython firmware onto your microcontroller.
2. Alter `wifi.json` with the name and password for your Wi-Fi. (For public/fully remote play, use a phone hotspot, and see section Fully Remote below to set up Tailscale.)
3. Alter the `pumpPin` variable in `main.py` to the pin you will use for triggering the relay. (TODO: put this into `wifi.json` and name it something more sensible)
4. Mount the microcontroller's filesystem and place `main.py`, `lbis.py` and `wifi.json` into the root.

## Pre-Assembly, Testing
1. Wire the battery, microcontroller, pump and relay according to the [schematic.](schematic/Scheme-it-export-lBIS-2025-04-17-08-44.pdf) (The GPIO pin you select doesn't matter, as long as you set it properly in `main.py`.)

2. Power the microcontroller and use `mpremote` (ensure it's available on PATH; the easiest way to do this is with `uv`: `uv tool install mpremote`) to connect to the REPL

3. Use `Ctrl-D` to soft-reboot the microcontroller; as of right now, it doesn't always properly start the web server on a cold boot. When you see lines like the following, it's started correctly:
```md
network config: ('[MCU-IP]', '255.255.255.0')
2021-01-01 00:04:36 [info     / 424kB] > starting web server on port 80
```

If the IP address is `0.0.0.0`, then the microcontroller has had an issue with getting an IP address from your access point. (The second address is the subnet mask; this is okay as it is.)

4. From a device which can reach the IP address, use `curl` to test the API:
`curl --request GET [MCU-IP]/api/marco`
If it returns `Polo!` then the API is functional.

5. Use `curl` again to test the relay over the API:
`curl -XPOST -H "Content-type: application/json" -d '{ "pump": 1 }' '10.105.23.145/api/setPumpState'`
If the wiring is correct and the API is functional, your pump should turn on. Repeat with `'{ "pump": 0 }'` to turn it off again.

## Post-Assembly
Currently the lBIS prototype is simply taped to the battery bank. When a proper enclosure has been made, files and instructions will be provided, as with the legband.


## Discord Bot
To enable use with a wide variety of Wi-Fi enabled MCUs, lBIS's MCU component is designed to be as minimal as possible, with features being built on the frontend. This repo provides a reference implementation for a Discord bot that communicates with the lBIS API. To use it:
- Create a venv, install the bot's dependencies in it (`discord`, `aiohttp`), and run it once. It will create `bot.json` for you. If it doesn't automatically close, stop it for now.
- In `bot.json`, set:
    - `discord_token` to a valid bot token obtained from the Discord Developer Portal,
    - `api_base_url` to the URL of your API, in the following format: `http://[IP]:[PORT]`,
    - `wearer_secret` to an arbitrary value (that you should store securely; wearer_id can be left blank as there is a command to set it up),
    - (optionally) `max_pump_duration`, `max_session_time` and `max_session_extension` to sensible values. The first shows how long (in seconds) the `/pump_timed` command can run at maximum, the second determines how long the pump can run, over multiple instances of `/pump_timed`, without wearer intervention, and the third determines how much time can be added with the `/add_time` command before the session must be reset. These limits are present for your own safety, but it's your body and your rules. If you trust the people you'll be giving access to the bot, set them however you like.
    - Add the bot to your apps with an Install Link that has the `applications.commands` and `bot` scopes under User Install and Guild Install as applicable. (I gave it no additional permissions and it functions as intended.)
    - In a channel you control (or populated with people you will use the app with), do /marco to test the bot's connection. You can then DM the bot to do the rest of the testing there. (I'm not sure how to DM an app that you haven't added to a server yet.)
    - Assuming all goes well, you can now do `/set_wearer`, providing the secret you set earlier, to enable arbitrary pump control, latching and session control.
    - You can now add the bot to any server you trust for anybody to use.
    (TODO: make this all a little friendlier.)

## Fully-Remote
If you're using a phone hotspot, you can run your lBIS without being tethered to home Wi-Fi. This technique will cause drain on your phone's battery. To communicate with a frontend (like the Discord bot below) hosted on your main PC, we can use Tailscale's subnet routing feature.

1. Sign up for Tailscale and install it on the PC hosting the frontend and the phone providing the hotspot.
2. [Follow Tailscale's guidance for setting up a subnet router.](https://tailscale.com/kb/1019/subnets) Something that tripped me up: The route advertised by the phone should be the address block that the phone is giving to devices on its hotspot, in CIDR notation. For example, if your MCU's IP address is `10.105.23.145`, the route should look like `10.105.23.0/24`.
3. You should now be able to host a frontend for the lBIS API on any device on your tailnet; that frontend can live on your home PC, and you can take lBIS out with you providing its Internet connection from your phone.

Almost definitely, there is an easier/safer way of doing all of this, but I am limited by my own knowledge and capabilities here. Please, if you have the knowledge, build on this.

# Safety

The following could go wrong when using lBIS.
- The microcontroller could hang or fail to respond, becoming stuck on.
- The lBIS prototype uses a MOSFET driver to control power to the pump; a competently-made driver should "fail safe" (shut off power when no voltage is present) but the possibility exists that the driver fails to close when the GPIO pin is pulled low. This should be verified before use.
- The API may be used erroneously (or maliciously!)
- You (or a partner!) may misjudge your limits, or your body may respond in an unexpected way (EVEN IF YOU HAVE INFLATED MANY TIMES BEFORE)

The following points are advised when building and using lBIS to mitigate these risks.

- Building:
	- Ensure that power to lBIS' pump can be cut at a moment's notice. The prototype does not include a manual switch in the circuit because the battery bank used has an on/off button. Your implementation should.
	- If a plug is used, ensure that said plug and/or the hose leading into it can be swiftly removed.
	- If a plug is *not* used, ensure the end of the hose has been blunted; the easiest way to do this is to use a lighter to melt the ends. This not only helps comfort, but mitigates the risk of laceration which can lead to embolism.
	- If you will wear lBIS outdoors, ensure that the electronic components are enclosed, and the enclosure is reasonably water and shock-resistant.
	- If your lBIS uses an unenclosed battery/battery module, the above is *extra* important. Lithium batteries are scary. Don't fuck with them.

- Programming:
	- The reference source code for the prototype, when the prototype is built, will implement a time limit for the pump. Leaving this enabled is recommended. Get to know the pump you're using and how long it takes to bring you to your usual maximum, and set your time limit accordingly.
	- If the pump will be controlled by a third party, implementing this time limit as a "session length" which will lock out the pump when exceeded is a prudent idea.
	- Your remote control implementation should operate over a secure connection.

- Usage:
	- If providing control to a third party, ensure they are able to check on you and know how to get help to you if required.
	- Exercise extreme caution when using lBIS alongside any sort of electrical stimulation device (TENS, e-stim, etc.)
	- Do not:
		- use lBIS while asleep.
		- use lBIS while under the influence of any substance which may impair your ability to make sound judgements or quick reactions.
		- give control to anybody you do not trust to behave safely.

# WIP
- Draw The Rest Of The Owl
- Buttplug support?? (dependent on buttplug-py working with Micropython and me being able to decipher it, tl;dr We'll See)

# Thanks
- My wife, Brokenxana, and a fourth individual (whose consent to be named here is pending) - ~being filthy enablers~ Funding my broke ass
- Fizz, Toaster, my other play-partners not mentioned above, the Trashpanda Discord server - Moral support
- The KinkyMakers Discord server - Technical advice, leading me away from a path of ruin
- MausTec, The buttplug.io Project - Inspiration

[^1]: if LaTeX can get away with That, I can get away with this. I understand that it's a chi, I don't care.
