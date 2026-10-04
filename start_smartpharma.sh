#!/bin/bash
# SmartPharma launcher for the Raspberry Pi.
# The camera is NOT started here any more: the app switches it on by itself
# when a "Scan QR" screen opens, and off again when that screen closes.

cd ~/SmartPharma/uipharma-main || exit 1

# Clean up a scanner left over from a crash, so the camera is free.
pkill -f pi_scanner.py 2>/dev/null

./build/linux/arm64/release/bundle/pj
