#!/usr/bin/python3

"script to test overriding the Isotemp onboard PID controller"

#temp_setp = 20.0
time_step = 3000 # 50 min/step

file_log = "/Applications/spectackler/20210112_topside_tempscan.tsv"

import sys
import traceback
import time
from simple_pid import PID
import isotemp6200 as isotemp

# the parameter to scan
parvals = [30, 25, 25, 20, 15]
parvals.reverse()
print("parameter values: " + str(parvals))

kp = 1
ki = 0
kd = 85

# init the PID
pid = PID(kp, ki, kd, setpoint=parvals[0])
# windup preventer
pid.output_limits = (-20, 20)

# open unbuffered output file
with open(file_log, 'a') as hand_log:

    # write header
    hand_log.write("\t".join(["t", "T_set", "T_int", "T_ext", "p", "i", "d", "Kp", "Ki", "Kd"])+'\n')
    hand_log.flush()
    
    # now we're opening serial connections, which need to be closed cleanly on exit
    try:
        # init water bath
        bath = isotemp.IsotempController(port="/dev/cu.usbserial-AL01M1X9")
        
        ## run experiment
        
        # start experiment timer (i.e. stopwatch)
        time_start = time.time()
        # initialize
        time_act = time_start
        
        # put the onboard controller in proportional mode
        while not all(bath.pid('H', .8, 0, 0)):
            pass
        while not all(bath.pid('C', 1, 0, 0)):
            pass
        
        # start circulator
        while not bath.on():
            bath.on(True)
            
        # enable external RTD
        while not bath.probe_ext():
            bath.probe_ext(True)
            
        for step, par in enumerate(parvals):
        
            # set tunings
            #ki = par
            #pid.tunings = (kp, ki, kd)
            temp_set = par
            pid.setpoint = temp_set
                    
            print(time.strftime("%H%M")+" - step "+str(step)+": PID = "+str((kp,ki,kd)))
            
            # collect data
            while time_act < time_start + ((step+1) * time_step):
                
                # read values
                time_act = time.time()
                temp_int = bath.temp_get_int()
                temp_ext = bath.temp_get_ext()
                
                # update the PID
                op = pid(temp_ext) # should be positive or negative?
                print("OP = "+str(round(op,2)), end='\r')
                
                # get the components
                p, i, d = pid.components
                
                # adjust the bath setpoint, but not persistently
                bath.temp_set(temp_ext + op)
                
                # log the data
                hand_log.write("\t".join([str(x) for x in [round(time_act, 3), temp_set, temp_int, temp_ext, p, i, d, kp, ki, kd]])+'\n')
                hand_log.flush()

        # shut down when done
        bath.on(False)
        bath.disconnect()

    except:
        bath.disconnect()
        traceback.print_exc()