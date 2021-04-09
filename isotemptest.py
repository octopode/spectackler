#!/usr/bin/python3

"""
initialize Isotemp water bath, then provide user with an interactive console for debugging
"""

import isotemp6200 as isotemp
import traceback

bath = isotemp.IsotempController(port="/dev/cu.usbserial-AL01M1X9")

while True:
	cmd = input("bath.")
	try:
		ret = eval("bath.{}".format(cmd))
		print(ret)
	except:
		traceback.print_exc()
		bath.disconnect()