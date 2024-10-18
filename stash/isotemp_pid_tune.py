#!/usr/bin/python3

"PID tuning script, optimizes params across a temperature range."

temp_start = 10
temp_end   = 30
temp_step  = 5

# tolerance goes for change in oscillation amplitude,
# as well as absolute set temperature
dec_pts    = 2
temp_tol   = 0.1
num_osc    = 4
timeout    = 1200

band_step = 0.1

file_log = "/Applications/spectackler/20200712_t-log.tsv"

import sys
import traceback
import time
import configparser
import numpy as np
from math import isclose
import isotemp6200 as isotemp

# get all temperature steps
temps = np.arange(*[float(x) for x in (temp_start, temp_end, temp_step)]).tolist()

# open unbuffered output file
with open(file_log, 'w') as hand_log:

    # write header
    hand_log.write("\t".join(["t", "T_int", "T_ext", "p", "i", "d"])+'\n')
    hand_log.flush()
    
    # now we're opening serial connections, which need to be closed cleanly on exit
    try:
        # init water bath
        bath = isotemp.IsotempController(port="/dev/cu.usbserial-AL01M1X9")
        
        ## run experiment
        
        # start experiment timer (i.e. stopwatch)
        time_start = time.time()
        
        # start circulator
        while not bath.on():
            bath.on(True)
            
        # set precision
        while not bath.temp_prec(dec_pts):
            pass
            
        # initialize all bands
        p = 1 # so we can get somewhere!
        i = d = 0
        for drive in ('H', 'C'):
            while not all(bath.pid(drive, p, i, d)):
                pass
        
        # scan across temp
        for temp_set in temps:
            
            # set temp persistently
            while not isclose(bath.temp_set(), temp_set):
                bath.temp_set(temp_set)
                
            # wait to blow pass it (under current PID params)
            temp_ext = bath.temp_get_ext()
            if round(temp_ext, 1) > temp_set:
                while temp_ext > temp_set:
                    time_act = time.time() - time_start
                    temp_int = bath.temp_get_int()
                    temp_ext = bath.temp_get_ext()
                    hand_log.write("\t".join([str(x) for x in [round(time_act, 3), temp_int, temp_ext, p, i, d]])+'\n')
                    hand_log.flush()
            else:
                while round(temp_ext, 1) < temp_set:
                    time_act = time.time() - time_start
                    temp_int = bath.temp_get_int()
                    temp_ext = bath.temp_get_ext()
                    hand_log.write("\t".join([str(x) for x in [round(time_act, 3), temp_int, temp_ext, p, i, d]])+'\n')
                    hand_log.flush()
                    
            # reset all bands
            i = d = 0
            for drive in ('H', 'C'):
                while not all(bath.pid(drive, p, i, d)):
                    pass
            
            ## tune proportional band
            for p in np.arange(band_step, 1, band_step):
                for drive in ('H', 'C'):
                    while not all(bath.pid(drive, p, i, d)):
                        pass
                peaks = []
                valleys = []
                trail = [bath.temp_get_ext()] * 3
                start_tune = time.time()
                while True:
                    time_act = time.time() - time_start
                    temp_int = bath.temp_get_int()
                    temp_ext = bath.temp_get_ext()
                    # log the data
                    hand_log.write("\t".join([str(x) for x in [round(time_act, 3), temp_int, temp_ext, p, i, d]])+'\n')
                    hand_log.flush()
                    
                    if temp_ext != trail[-1]:
                        # temp must have changed detectably
                        trail = trail[1:] + [temp_ext]
                        print("trace: {}".format(trail), file=sys.stderr)
                        
                        # store each peak and valley
                        if trail[-1] < trail[-2] and trail[-3] < trail[-2]:
                            peaks.append(trail[-2])
                            print("peaks: {}\nvalleys: {}".format(peaks, valleys), file=sys.stderr)
                        elif trail[-1] > trail[-2] and trail[-3] > trail[-2]:
                            valleys.append(trail[-2])
                            print("peaks: {}\nvalleys: {}".format(peaks, valleys), file=sys.stderr)
                        
                        if (min(len(peaks), len(valleys)) == num_osc):
                        	# if enough oscillations have happened
                            if ((max(peaks) - min(peaks) <= temp_tol) and
                                (max(valleys) - min(valleys) <= temp_tol)):
                                # they are either regular within tolerance
                                good = True
                                # break out of p-tune
                                break
                            elif (time_act - start_tune) > timeout:
                            # or we're just out of time
                                good = False
                                break
                            # limit trail to num_osc
                            peaks = peaks[1:]
                            valleys = valleys[1:]
                if good: 
                    # if p is adequate, move on
                    break
                        
            ## tune derivative preact
            amp = [] # init list of oscillation amplitudes
            for d in np.arange(band_step, 1, band_step):
                for drive in ('H', 'C'):
                    while not all(bath.pid(drive, p, i, d)):
                        pass
                peaks = valleys = []
                trail = [0] * 3
                start_tune = time.time()
                while True:
                    time_act = time.time() - time_start
                    temp_int = bath.temp_get_int()
                    temp_ext = bath.temp_get_ext()
                    # log the data
                    hand_log.write("\t".join([str(x) for x in [round(time_act, 3), temp_int, temp_ext, p, i, d]])+'\n')
                    hand_log.flush()
                    
                    if temp_ext != trail[-1]:
                        # temp must have changed detectably
                        trail = trail[1:] + [temp_ext]
                        
                    # log each peak and valley
                    if trail[-1] < trail[-2] and trail[-3] < trail[-2]:
                        peaks.append(temp_ext)
                    elif trail[-1] > trail[-2] and trail[-3] > trail[-2]:
                        peaks.append(temp_int)
                    
                    if (min(len(peaks), len(valleys)) == num_osc):
                        if ((max(peaks) - min(peaks) <= temp_tol) and
                            (max(valleys) - min(valleys) <= temp_tol)):
                            # if enough oscillations are regular within tolerance,
                            # store oscillation amplitude
                            amp.append(mean(peaks) - mean(valleys))
                            break
                        elif (time_act - start_tune) > timeout:
                            amp.append(mean(peaks) - mean(valleys))
                            break
                        # limit trail to num_osc
                        peaks = peaks[1:]
                        valleys = valleys[1:]
                try:
                    if (amp[2] > amp[1]) and (amp[3] > amp [1]):
                        # if the first setting was stablest of 3,
                        # revert to it
                        d = band_step
                    elif (amp[-2] < amp[-1]) and (amp[-2] < amp[-3]):
                        # if the previous setting was a stability peak,
                        # revert to it
                        d -= band_step
                    for drive in ('H', 'C'):
                        while not all(bath.pid(drive, p, i, d)):
                            pass
                    # and move on
                    break
                except:
                    # if there aren't enough amplitude readings, keep stepping d
                    pass
            
            ## tune integral reset
            amp = [] # init list of oscillation amplitudes
            for i in np.arange(band_step, 1, band_step):
                for drive in ('H', 'C'):
                    while not all(bath.pid(drive, p, i, d)):
                        pass
                peaks = valleys = []
                trail = [0] * 3
                start_tune = time.time()
                while True:
                    time_act = time.time() - time_start
                    temp_int = bath.temp_get_int()
                    temp_ext = bath.temp_get_ext()
                    # log the data
                    hand_log.write("\t".join([str(x) for x in [round(time_act, 3), temp_int, temp_ext, p, i, d]])+'\n')
                    hand_log.flush()
                    
                    if temp_ext != trail[-1]:
                        # temp must have changed detectably
                        trail = trail[1:] + [temp_ext]
                        
                    # log each peak and valley
                    if trail[-1] < trail[-2] and trail[-3] < trail[-2]:
                        peaks.append(temp_ext)
                    elif trail[-1] > trail[-2] and trail[-3] > trail[-2]:
                        peaks.append(temp_int)
                    
                    if (min(len(peaks), len(valleys)) == num_osc):
                        if (mean(peaks) - mean(valleys) <= 2*temp_tol):
                            # if enough oscillations are regular within tolerance,
                            # store oscillation amplitude
                            amp.append(mean(peaks) - mean(valleys))
                            break
                        elif (time_act - start_tune) > timeout:
                            amp.append(mean(peaks) - mean(valleys))
                            break
                        # limit trail to num_osc
                        peaks = peaks[1:]
                        valleys = valleys[1:]
                try:
                    if (amp[2] > amp[1]) and (amp[3] > amp [1]):
                        # if the first setting was stablest of 3,
                        # revert to it
                        i = band_step
                    elif (amp[-2] < amp[-1]) and (amp[-2] < amp[-3]):
                        # if the previous setting was a stability peak,
                        # revert to it
                        i -= band_step
                    for drive in ('H', 'C'):
                        while not all(bath.pid(drive, p, i, d)):
                            pass
                    # and move on
                    break
                except:
                    # if there aren't enough amplitude readings, keep stepping d
                    pass

        # shut down when done
        bath.on(False)
        bath.disconnect()

    except:
        bath.disconnect()
        traceback.print_exc()