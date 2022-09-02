#!/usr/bin/env python3

"Damn simple stripcharter"

datafile = "/Applications/spectackler/fusiondata.dat"
handin = open(datafile, 'r')

refresh = 0.1 # refresh time in s

import os
from time import sleep
from subprocess import check_output
from oscilloscope import Osc

# strip chart width in seconds
osc = Osc(window_sec=300)

# get column names from data file
with open(datafile, 'r') as handin:
	cols = handin.readline().rstrip().split('\t')

@osc.signal
def fluor_trace(state):
	row = ""
	while True:
		row_prev = row
		# read last line in with bash tail
		row = check_output(["tail", "-1", datafile]).decode().rstrip()
		# if it's not redundant, plot it!
		if row != row_prev:
			#print(row.split('\t')[2])
			state.draw(float(row.split('\t')[cols.index("intensity")])) # fluor hardcoded for now
			sleep(refresh)

osc.start()