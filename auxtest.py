#!/usr/bin/python3

"""
initialize Arduino, then provide user with an interactive console for debugging
"""

import auxmcu
import traceback
from time import sleep

amcu = auxmcu.AuxMCU(port="/dev/cu.usbmodem142201")

i=0
while True:
	amcu.ex('V')
	amcu.em('V')
	amcu.ex('H')
	amcu.em('H')
	i += 1
	print(i)
    #cmd = input("amcu.")
    #try:
    #    ret = eval("amcu.{}".format(cmd))
    #    print(ret)
    #except:
    #    amcu.__ser__.flush()
    #    traceback.print_exc()