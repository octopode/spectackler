#!/usr/bin/env python2

"""
Basic interface script for 2-bath control
"""

# requires pyfirmata as well as spectackler
from pyfirmata import Arduino, util
import neslabrte as rte
import time
from collections import deque
from multiprocessing import  active_children
from sys import stdout
from serial import SerialException
import os
import threading
import traceback
import __future__

# peripheral COM ports
port_arduino = "COM10"
port_bathA = "COM14"
port_bathB = "COM11"

# data log file path
logfile = "C:/Users/chess_id7a/Desktop/20241018a_templog.tsv"
#print(logfile)

# settings for the switchover valves
pin_valve1 = 7
pin_valve2 = 6
# switchover delay in seconds
#delay = 7.5
delay = 0 # not needed bc of bridge tube?
# refresh (sample cycle) time in s
refresh = 1

# init hardware
ardui = Arduino(port_arduino)
bathA = rte.NeslabController(port=port_bathA)
bathB = rte.NeslabController(port=port_bathB)
# start both baths
bathA.status_set(unit_on=1)
bathB.status_set(unit_on=1)

def pollreport(free, status, handout, newfile):
	"poll the baths and report temperatures"
	while True:
		try:
			#if True:
			# retrieve data
			status.update(
				{
					"clock"      : time.strftime("%Y%m%dT%H%M%S"),
					"temp_set_a" : bathA.temp_set(),
                    "temp_set_b" : bathB.temp_set(),
                    "temp_int_a" : bathA.temp_get_int(),
                    "temp_int_b" : bathB.temp_get_int(),
                    "temp_ext_a" : bathA.temp_get_ext(),
                    "temp_ext_b" : bathB.temp_get_ext()
				}
			)
			# print it to console
			print(
				"""
###      TWO-BATH CONTROL      ###
valves to bath {}
A set: {}	B set: {} deg C
A int: {}	B int: {} deg C
A ext: {}	B ext: {} deg C
logging to {}
set temp: 'a' or 'b' - switch valves: 'v' - EPO: 'o' - exit: ^C
				""".format(
					status["whichbath"],
					status["temp_set_a"],
					status["temp_set_b"],
					status["temp_int_a"],
					status["temp_int_b"],
					status["temp_ext_a"],
					status["temp_ext_b"],
					handout.name
				)
			)
			# print header if necessary (just once)
			if newfile: 
				handout.write('\t'.join(sorted(status.keys())) + '\n')
				newfile = False
			# log data to file
			handout.write('\t'.join([str(status[key]) for key in sorted(status.keys())]) + '\n')
			time.sleep(refresh)
			free.wait()
			os.system("cls") # clear console for reprint
		except SerialException:
		#	#time.sleep(refresh)  # in case need to kill
			print("comm error!")

# init whichbath and valves
if not ardui.digital[pin_valve1].read(): status = {"whichbath": 'A'}
else: status = {"whichbath": 'B'}
ardui.digital[pin_valve2].write(ardui.digital[pin_valve1].read())
# open log file
newfile = not os.path.isfile(logfile)
if newfile: print("creating {}".format(logfile))
else: print("appending to {}".format(logfile))
with open(logfile, 'a', buffering=1) as handout:
	#if not newfile: handout.write('\n') # in case a line is fragmented

	# start updater thread
	hardware_free = threading.Event()
	hardware_free.set()
	threading.Thread(name="update", target=pollreport, args=(hardware_free, status, handout, newfile)).start()

	# intervention loop
	while True:
		cmd = raw_input()
		hardware_free.clear()
		if cmd.lower() == 'v':
			print("switching valve 1")
			ardui.digital[pin_valve1].write(not ardui.digital[pin_valve1].read())
			time_1 = time.time() # mark time
			while (time.time() - time_1) < delay:
				stdout.write("delaying {}/{} s\r".format(round(time.time() - time_1, 1), delay))
				time.sleep(0.05)
			print("                  \rswitching valve 2")
			ardui.digital[pin_valve2].write(not ardui.digital[pin_valve2].read())
			if status["whichbath"] == 'A': status["whichbath"] = 'B'
			else: status["whichbath"] = 'A'
		#20240317 note kludge where entered setpoints are multiplied by 10
		elif cmd.lower() == 'a':
			try: bathA.temp_set(10*float(raw_input("set temp for bath A: ")))
			except: pass
		elif cmd.lower() == 'b':
			try: bathB.temp_set(10*float(raw_input("set temp for bath B: ")))
			except: pass
		elif cmd.lower() == 'x':
			handout.close()
			break
                elif cmd.lower() == 'o':
			bathA.status_set(unit_on=0)
                        bathB.status_set(unit_on=0)
		hardware_free.set()
		children = active_children()
		for child in children: child.kill()
