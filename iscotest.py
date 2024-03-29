#!/opt/miniconda3/bin/python

"""
initialize ISCO pump, then provide user with an interactive console for debugging
"""

import isco260D as isco
from time import sleep
import traceback

def gg2psi(gg_str):
    "get PSI value from G& get all status string"
    return float(gg_str.decode("utf-8").split('=')[1].split(',')[0]) / 5

pump = isco.ISCOController(port="/dev/cu.usbserial-FT4IVKAO0",source=0,dest=1)

pump.remote()
print(pump.gg())

while True:
    cmd = input("pump.")
    try:
        ret = eval("pump.{}".format(cmd))
        print(ret)
    except:
        traceback.print_exc()
        pump.disconnect()
