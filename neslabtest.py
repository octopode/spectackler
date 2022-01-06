#!/usr/bin/env python3

"""
initialize Neslab water bath, then provide user with an interactive console for debugging
"""

import neslabrte as rte
import traceback
import __future__

bath = rte.NeslabController(port="/dev/cu.usbserial-FT4IVKAO1")
#bath = rte.NeslabController(port="/dev/cu.Bluetooth-Incoming-Port")

while True:
	cmd = input("bath.")
	try:
	    print(eval("bath.{}".format(cmd)))
	except:
		traceback.print_exc()
		bath.disconnect()