#!/usr/bin/python3

"""
generate state matrix for a landscape of laurdan GP measurements
modified 20210207 to go easy on samples with low Tbh
"""

import sys
from math import ceil

def floatrange(beg, end, inc):
	return [beg+i*inc for i in range(ceil((end-beg)/inc))]
	
def printstate():
	print('\t'.join([str(dict_state[var]) for var in list_head]))

p_range = (0, 501, 62.5)
t_range = (5, 25.1, 2.5)
pols = ('V', 'H')
rep_aniso = 3 # repeat each state three times!

p_min = 1 # don't want pump to draw a vacuum!

p_levels = [max(p_min, p) for p in floatrange(*p_range)]
t_levels = floatrange(*t_range)
print(p_levels, file=sys.stderr)
print(t_levels, file=sys.stderr)

list_head = ["P_set", "T_set", "wl_ex", "wl_em", "pol_ex", "pol_em", "msg"]

print('\t'.join(list_head))

dict_state = {}
# state constants
dict_state["wl_ex"]  = 350
dict_state["wl_em"]  = 428

p_levels.sort(reverse=True) # start at high pressure
t_levels.sort(reverse=False) # start at low temp
for cyc in range(1):
    for tdir in ("up",): # temp only sweeps up
    	for t in t_levels:
    		dict_state["T_set"] = t
    		for pdir in ("dn", "up"): # hi->lo->hi pressure before raising temp
    			for p in p_levels:
    				dict_state["P_set"] = p
    				# measure both Laurdan emissions
    				for rep in range(rep_aniso):
    					dict_state["msg"] = "tdir:{tdir}_pdir:{pdir}_rep:{rep}_cyc:{cyc}".format(tdir=tdir, pdir=pdir, rep=rep, cyc=cyc)
    					dict_state["pol_ex"] = 'V'
    					dict_state["pol_em"] = 'V'
    					printstate()
    					dict_state["pol_em"] = 'H'
    					printstate()
    					dict_state["pol_ex"] = 'H'
    					printstate()
    					dict_state["pol_em"] = 'V'
    					printstate()
    			p_levels.reverse()
    	t_levels.reverse()