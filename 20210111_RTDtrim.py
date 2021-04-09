#!/usr/bin/python3

"for manual trimming of RTD bridge circuit"

import sys
import traceback
import isotemp6200 as isotemp

with open("/Applications/spectackler/20210111_exttrim.tsv", 'a') as handout:
    # now we're opening serial connections, which need to be closed cleanly on exit
    try:
        # init water bath
        bath = isotemp.IsotempController(port="/dev/cu.usbserial-AL01M1X9")
        
        print("int\text")
        while True:
        	t_int = bath.temp_get_int()
        	t_ext = bath.temp_get_ext()
        	print("{}\t{}".format(t_int, t_ext), end='\r', file=sys.stderr)
        	handout.write("{}\t{}".format(t_int, t_ext))
    
    except:
        bath.disconnect()
        traceback.print_exc()