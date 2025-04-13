# Leg-worn Belly Inflation System (lBIS)

The Leg-worn Belly Inflation System, or lBIS (lowercase L, read like "ibis" [^1]) is a discreet wearable air pump that inflates the user at a gentle, safe(-ish) pace. It is designed to be worn casually, as one would a plug or ring, and be easy to maintain. It is controlled remotely using a WiFi-enabled microcontroller. The components are assembled onto a simple webbing legband which is worn under the clothes.

The source code and plans for lBIS are distributed under the [MIT License.](LICENSE.MD)

> [!IMPORTANT]
> The lBIS prototype is a reference design that uses off-the-shelf components. This is the designer's first major electronics project. It should not be taken as gospel on the best way to execute this concept. The purpose of open-sourcing lBIS is for the interest and curiosity of the kink community and as a public document of the project. Take the advice herein with a grain of salt and use your own judgement. The prototype was built with a... we'll say *lax* attitude for the builder's well-being. The builder however does care about *your* well-being, and will try to steer you towards doing this better than they did.

> [!WARNING]
> lBIS inflates the user via air enema, a process which carries an inherent risk. lBIS is not intended for users who are not already comfortable and experienced inflating themselves. While the pump utilized *shouldn't* be capable of causing severe injury, by building and using lBIS, you agree to do so at your own risk. See [Safety](#safety) for recommended practice.

> [!CAUTION]
> lBIS opens up the possibility of public play. Ensure that your usage of lBIS is compliant with regional laws, public decency, and common sense. Don't Be That Guy™.

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

TODO

# Safety

The following could go wrong when using lBIS.
- The microcontroller could hang or fail to respond, becoming stuck on.
- The lBIS prototype uses a MOSFET driver to control power to the pump; a competently-made driver should "fail safe" (shut off power when no voltage is present) but the possibility exists that the driver fails to close when the GPIO pin is pulled low. This should be verified before use.
- The API may be used erroneously (or maliciously!)
- You may misjudge your limits, or your body may respond in an unexpected way.

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
- My wife
- Fizz
- Toaster
- Brokenxana
- An individual whom I should confirm that they're okay with me mentioning their name here
- The KinkyMakers Discord server

[^1]: if LaTeX can get away with That, I can get away with this. I understand that it's a chi, I don't care.
