#!/usr/bin/python3

"""
generate state matrix for a landscape of laurdan GP measurements
"""

import sys
from math import ceil

def floatrange(beg, end, inc):
	return [beg+i*inc for i in range(ceil((end-beg)/inc))]
	
def printstate():
	print('\t'.join([str(dict_state[var]) for var in list_head]))

p_range = (0, 501, 125)
t_range = (3, 29, 6.25)
rep_gp = 3 # repeat each state three times!

p_min = 1 # don't want pump to draw a vacuum!

p_levels = [max(p_min, p) for p in floatrange(*p_range)]
t_levels = floatrange(*t_range)
print(p_levels, file=sys.stderr)
print(t_levels, file=sys.stderr)

list_head = ["P_set", "T_set", "wl_ex", "wl_em", "pol_ex", "pol_em", "msg"]

print('\t'.join(list_head))

dict_state = {}
dict_state["pol_ex"] = '0'
dict_state["pol_em"] = '0'
dict_state["wl_ex"]  = 340

p_levels.sort(reverse=False)
t_levels.sort(reverse=True)
for cyc in range(1):
    for dir in ("tdn","tup"):
    	for t in t_levels:
    		dict_state["T_set"] = t
    		for p in p_levels:
    			dict_state["P_set"] = p
    			# measure both Laurdan emissions
    			for rep in range(rep_gp):
    				dict_state["msg"] = "dir:{dir}_rep:{rep}_cyc:{cyc}".format(dir=dir, rep=rep, cyc=cyc)
    				dict_state["wl_em"] = 440
    				printstate()
    				dict_state["wl_em"] = 490
    				printstate()
    		p_levels.reverse()
    	t_levels.reverse()