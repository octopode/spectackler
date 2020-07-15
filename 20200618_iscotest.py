#!/usr/bin/python3

"""
initialize ISCO pump, then provide user with an interactive console for debugging
"""

import isco260D as isco
from time import sleep

def gg2psi(gg_str):
	"get PSI value from G& get all status string"
	return float(gg_str.decode("utf-8").split('=')[1].split(',')[0]) / 5

pump = isco.ISCOController(port="/dev/cu.usbserial-FTV5C58R1",source=0,dest=1)

pump.remote()
print(pump.gg())

while True:
	cmd = input("pump.")
	try:
		ret = eval("pump.{}".format(cmd))
		print(ret)
	except:
		pump.disconnect()
