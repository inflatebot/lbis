# lBIS Discord Bot

The lBIS Discord Bot is a reference implementation of the lBIS API, demonstrating how to build a fully-featured asynchronous remote play experience around its very minimal features.

By keeping the implementation of features and tracking of state on the frontend side, the API can be kept extremely lean, capable of running on any Wi-Fi-enabled microcontroller.

The bot is designed to be run on the wearer's PC, with the IP address of lBIS being provided in `bot.json`.

## Features

- Enables the wearer's play partners to inflate the wearer remotely for brief periods, with minimal effort on their part
- Enforces a maximum "session" length, with the ability to add time to a session or restart it remotely
- Has a "time bank" which can hold time requested by users that failed due to session constraints, latching in the middle of a timer, or technical issues, to a configurable maximum
- Identifies the wearer with a password provided by a command over DMs to enable locking the pump, arbitrary pump control, and session management.
- Displays the pump state (on/off/locked/unreachable), along with session/bank time, in the bot's status

## TODO

- Enable the wearer to constrain the pump controls to specific users
- Enable the wearer to designate users who can control the pump arbitrarily
- Limit the amount of time an individual user can have banked
- Provide a webhook to dynamically show the pump's state

## Installation

The easiest way to use lbis-discord is to use [`uv`](https://docs.astral.sh/uv/). I've interacted with many Python package management systems and `uv` blows them all out of the water.
- `git clone https://github.org/inflatebot/lbis`
- `cd lbis/discord_bot`
- `uv run bot.py`