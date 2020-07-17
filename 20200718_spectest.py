#!/usr/bin/python3

"""
initialize Isotemp water bath, then provide user with an interactive console for debugging
"""

import rf5301

spec = rf5301.RF5301(port="/dev/cu.usbserial-FTV5C58R0")

while True:
	cmd = input("spec.")
	try:
		ret = eval("spec.{}".format(cmd))
		print(ret)
	except:
		spec.disconnect()