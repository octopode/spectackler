#!/usr/bin/python3

"""
viscomap.py

Interface module for viscotheque. 
Commands spec, chiller, and syringe pump, collects data.
"""

# pip modules
import serial
import numpy as np
import pandas as pd
import timeit

# bundled modules
import isotemp6200
import isco260D
import rf5301PC
import filterswapper

# poll serial
devs = poll_serial()

def poll_serial():
	"""
	Find ports for the bath, pump, spec, and swapper. 
	Connect and return their objects in a dict.
	"""
	
	# returns ListPortInfo object, which is a tuple of tuples
	# where [0] of inner tuple is port name
	ports = serial.tools.list_ports.comports(include_links=True)
	
	devs = dict()
	num_devs = 4
	
	for port in ports:
		# try to connect bath
		try:
			devs["bath"] = isotemp6200.IsotempController(port[0], baud=9600, timeout=1)
		except:
			pass
		# try to connect pump
		try:
			devs["pump"] = isco260D.ISCOController(port[0], baud=9600, timeout=1, source=0, dest=1)
		except:
			pass
		# try to connect spec
		try:
			devs["spec"] = rf5301PC.IsotempController(port[0], baud=9600, timeout=1)
		except:
			pass
		# try to connect filter swapper
		try:
			devs["swap"] = filterswapper.FilterController(port[0], baud=9600, timeout=1)
		except:
			pass
			
	# report all the devices connected
	print(devs)
	
	# Throw an error if any device is missing
	if len(devs.keys() < num_devs):
		raise DeviceNotFoundError()
		
	return devs
		

def measure_anisotropy(temp, pressure, t, stab, bath, pump, spec):
	"""
	Take a fluorescence anisotropy measurement at passed T, P.
	Measurements are averaged over earliest time window t (s)
	with adequate stability.
	"""
	
	


def wait4temp(bath, temp, timeout=3600):
	"""
	Wait for bath to reach passed temp.
	Yield time/temp pairs, then finally return elapsed time.
	"""
	
	


print(isco260D.str2dasnet("REMOTE"))



