#!/usr/bin/env python

"""
initialize Neslab water bath, then provide user with an interactive console for debugging
"""

import neslabrte as rte
import traceback
import __future__

comport = raw_input("Which port? ")
bath = rte.NeslabController(port=comport)

while True:
	cmd = raw_input("bath.")
	try:
	    print(eval("bath.{}".format(cmd)))
	except:
		traceback.print_exc()
		bath.disconnect()