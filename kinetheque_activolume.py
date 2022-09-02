#!/usr/bin/python3

"""
Perform continuous-ramp activation volume measurement.
Log data to TSV in real time.
"""

import threading
from collections import deque
import isco260D
import rf5301
import time
import sys
import traceback
from serial.serialutil import SerialException

def poll(dev, free, meas, pid=None):
	while True:
		try:
			"Poll the passed devices all at once. Free is a threading event, meas a deque"
			free.wait()
			devclass = dev.__class__.__name__
			if devclass == "IsotempController":
				# get reference and actual temps with just one query
				temp_ext = dev.temp_get_ext()
				temp_act = dev.cal_ext.ref2act(temp_ext)
				# update topside PID (setpoint change should not persist)
				# quick limit to avoid oversetting on high end
				#dev.temp_set(min(dev.cal_ext.act2ref(temp_act + pid(temp_act)), 100))
				dev.temp_set(dev.cal_ext.act2ref(temp_act + pid(temp_act)))
				vals_dict = {
					"T_int" : dev.temp_get_int(),
					"T_ext" : temp_ext,
					"T_act" : round(temp_act, 2),
					"P"	 : round(pid.components[0], 2),
					"I"	 : round(pid.components[1], 2),
					"D"	 : round(pid.components[2], 2)
				}
			elif devclass == "ISCOController":
				vals_dict = {
					"vol"   : dev.vol_get(),
					"P_act" : dev.press_get(),
					#"air"   : dev.digital(0),
					"flow"	: dev.flow_get(),
					"status": dev.status()["STATUS"]
				}
			elif devclass == "RF5301":
				vals_dict = {
					"intensity" : dev.fluor_get(),
					"wl_ex"	 : dev.wl_ex(),
					"wl_em"	 : dev.wl_em(),
					"slit_ex"   : dev.slit_ex(),
					"slit_em"   : dev.slit_em()
				}
			elif devclass == "AuxMCU":
				# be persistent!
				while True:
					temp_amb = dev.temp_get()
					if temp_amb: break
				while True:
					hum_amb = dev.hum_get()
					if hum_amb: break
				vals_dict = {
					"pol_ex": 0,
					"pol_em": 0,
					"H_amb" : hum_amb,
					"T_amb" : temp_amb,
					"dewpt" : round(dewpt(hum_amb, temp_amb), 2)
				}
			meas.append(vals_dict)
		except SerialException:
			print("{} has been disconnected".format(dev.__ser__))
			# do anything else?
		except: 
			print("Data read failure!", end='\r')
			pass
			
def log_data(logfile, deques):
	time_start = time.time()
	data_dict = {"clock": '', "watch": ''}
	with open(logfile, 'w', buffering=1) as handout:
		# first line:
		for dq in deques:
			while True:
				# ensure that *something* gets popped out so the dict is complete
				try:
					data_dict.update(dq.popleft())
					break
				except:
					pass
		handout.write('\t'.join(sorted(data_dict.keys())) + '\n')
		# and from then on
		while True:
			# store prev data row (copying explicitly)
			data_prev = dict(data_dict)
			# get data
			for dq in deques:
				try: data_dict.update(dq.popleft())
				except: pass
			# if any of the data have changed
			if data_dict != data_prev:
				# mark time
				data_dict.update({
					"clock": time.strftime("%Y%m%d %H%M%S"),
					"watch": time.time() - time_start
				})
				# save the line of data
				handout.write('\t'.join([str(data_dict[key]) for key in sorted(data_dict.keys())]) + '\n')
				handout.flush()

# declare async queues
queue_bath = deque(maxlen=1)
queue_pump = deque(maxlen=1)
queue_spec = deque(maxlen=1)
queue_amcu = deque(maxlen=1)

# init hardware
pump = isco260D.ISCOController(port="/dev/cu.usbserial-FT4IVKAO0",source=0,dest=1)
spec = rf5301.RF5301(port="/dev/cu.usbserial-FTV5C58R0", exslit=15, emslit=15)

# set up the spec appropriately
# fill in more here later
while not spec.shutter(True): pass

# data to where?
logfile = "/Applications/spectackler/kinetheque_test.dat"

# pump should be in PGa mode
pump.remote()

# establish initial pressure
input("press ENTER to start data collection at initial pressure")
pump.run()
# start polling threads
# all device instances have RLocks!
#bath_free = threading.Event()
pump_free = threading.Event()
spec_free = threading.Event()
#amcu_free = threading.Event()
[event.set() for event in (
#	bath_free, 
	pump_free, 
	spec_free, 
#	amcu_free
)]
#threading.Thread(name="pollbath", target=poll, args=(bath, bath_free, queue_bath, pid)).start()
threading.Thread(name="pollpump", target=poll, args=(pump, pump_free, queue_pump)).start()
threading.Thread(name="pollspec", target=poll, args=(spec, spec_free, queue_spec)).start()
#threading.Thread(name="pollamcu", target=poll, args=(amcu, amcu_free, queue_amcu)).start()
# the logging thread
threading.Thread(name="log", target=log_data, args=(logfile, [queue_pump, queue_spec])).start()

# start sweep
input("press ENTER to start sweep")
pump_free.clear()
pump.run()
pump_free.set()

# intervention loop
while True:
	input("press ENTER to pause")
	pump_free.clear()
	pump.pause()
	pump_free.set()
	input("press ENTER to run")
	pump_free.clear()
	pump.run()
	pump_free.set()