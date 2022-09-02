#!/usr/bin/python3

"""
initialize Isotemp water bath, then provide user with an interactive console for debugging
"""

import rf5301
import traceback

#spec = rf5301.RF5301(port="/dev/cu.usbserial-FTV5C58R0")
spec = rf5301.RF5301(port="/dev/cu.usbserial-FT4IVKAO0")

while True:
    cmd = input("spec.")
    try:
        ret = eval("spec.{}".format(cmd))
        print(ret)
    except:
        spec.__ser__.flush()
        traceback.print_exc()