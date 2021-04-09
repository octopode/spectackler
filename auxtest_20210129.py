#!/usr/bin/python3

"""
initialize Arduino, then provide user with an interactive console for debugging
"""

import auxmcu
import traceback

amcu = auxmcu.AuxMCU(port="/dev/cu.usbmodem142201", filt_ex=('0','V','H'), filt_em=('0','V','H'))

while True:
    cmd = input("amcu.")
    try:
        ret = eval("amcu.{}".format(cmd))
        print(ret)
    except:
        amcu.__ser__.flush()
        traceback.print_exc()