#!/usr/bin/python3

"""
This little script performs tests with multiple flowrates and assesses residual
pressure in the pump cylinder.
"""

import isco260D as isco
import time
import sys
import traceback

def gg2psi(gg_str):
    "get PSI value from G& get all status string"
    return float(gg_str.decode("utf-8").split('=')[1].split(',')[0]) / 5

# init hardware
pump = isco.ISCOController(port="/dev/cu.usbserial-FT4IVKAO0",source=0,dest=1)

# data to where?
logfile = "/Applications/spectackler/20211022_flowlog_3.tsv"

def log_data(handout):
	"Poll pump and write data to file handle"
	while True:
		try:
			data = {
				"clock": time.strftime("%Y%m%d %H%M%S"), 
				"watch": time.time() - time_start, 
				"flow": pump.flow_get(), 
				"press": pump.press_get(),
				"vol" : pump.vol_get(),
				"status": pump.status()["STATUS"]
			}
			break
		except: pass
	handout.write('\t'.join([str(data[key]) for key in sorted(data.keys())]) + '\n')
	return data

pump.remote()
print(pump.gg())

# absolute flowrates to test
frates = sorted([i/2 for i in range(1,13)], reverse=True)
# pressures to stop at
pstops = [1] + list(range(100, 501, 100))
# relaxation time in sec
trelax = 30

# open data log file
data = {
	"clock": None, 
	"watch": None, 
	"flow": None, 
	"press": None,
	"vol" : None,
	"status": None
}
with open(logfile, 'w', buffering=1) as handout:
	handout.write('\t'.join(sorted(data.keys())) + '\n')
	# NOTE: start at min pressure!
	# mark time
	time_start = time.time()
	# main flowrate loop
	for frate in frates:
		# set the flowrate
		pump.maxflow(frate)
		print("flowrate to {} mL/min".format(frate), file=sys.stderr)
		# set target pressure to final
		pump.press_set(pstops[-1])
		# pressure jump loop:
		data = log_data(handout)
		for pstop in pstops:
			print("pressurizing to {} bar".format(pstop), file=sys.stderr)
			# start the pump!
			pump.run()
			# log data while running
			while data["press"] < pstop:
				data = log_data(handout)
			# STOP!
			time_stop = data["watch"]
			pump.pause()
			# and log data for several seconds
			while data["watch"] < time_stop + trelax:
				print("equilibrating {}/{} s".format(round(data["watch"]-time_stop), trelax), file=sys.stderr, end='\r')
				data = log_data(handout)
			print('', file=sys.stderr)
		# when sweep is complete, reverse it
		pump.press_set(pstops[0])
		for pstop in sorted(pstops, reverse=True)[1:]:
			print("depressurizing to {} bar".format(pstop), file=sys.stderr)
			# start the pump!
			pump.run()
			# log data while running
			while data["press"] > pstop:
				data = log_data(handout)
			# STOP!
			time_stop = data["watch"]
			pump.pause()
			# and log data for several seconds
			while data["watch"] < time_stop + trelax:
				print("equilibrating {}/{} s".format(round(data["watch"]-time_stop), trelax), file=sys.stderr, end='\r')
				data = log_data(handout)
			print('', file=sys.stderr)
		
			
		