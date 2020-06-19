#!/usr/bin/python3

"""
run a set number of program reps on the ISCO pump
"""

import isco260D as isco
from time import sleep

def gg2psi(gg_str):
	"get PSI value from G& get all status string"
	return float(gg_str.decode("utf-8").split('=')[1].split(',')[0]) / 5

n = 4 # number of cycles
t = 100 # length of program, in sec. Add some wiggle time.

pump = isco.ISCOController(port="/dev/tty.usbserial-FTV5C58R0",source=0,dest=1)

print("starting test")
pump.run()

for i in range(n):
	# start ramp up
	pump.run()
	psi_hi = 0
	maxed = False
	# monitor pressure every second
	for j in range(t):
		psi = gg2psi(pump.gg())
		if psi > psi_hi:
			psi_hi = psi
		elif (maxed == False) and (psi < (psi_hi - 5)):
			print ("max pressure: {} PSI".format(psi_hi))
			maxed = True
		sleep(1)
	# re-arm pump
	pump.run()
	print("cycle {} complete".format(i+1))
	print(pump.gg())
	sleep(15)
	
pump.run()
pump.stop()
pump.disconnect()
print("finished test")