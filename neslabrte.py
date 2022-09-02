#!/usr/bin/env python3

"""
neslabrte.py

driver module for controlling NESLAB RTE series circulator
v0.5 (c) JRW 2021 - jwinnikoff@mbari.org

# NOTE 20211023 - as yet this only works properly in python 2

GNU PUBLIC LICENSE DISCLAIMER:
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""

import __future__ # supposed to be 2/3 compatible
import serial # pip install pyserial
import time
import io
import struct
from re import sub
from itertools import chain
from warnings import warn

## binary encode/decode functions
    
def bytestr2bytelist(bytestr):
    "Get ordinal values from bytestring."
    #return [ord(i) for i in bytestr]
    return [i for i in bytestr] #python 3
    
def checksum(bytelist):
    "Calculate checksum: bitwise inversion of sum of bytestring."
    return (sum(bytelist) ^ 0xff) % 256
    
def int2int16(inval):
    "Convert Python int to 2-byte signed int."
    return bytestr2bytelist(struct.pack('>h', inval))
    
def int162int(inbytes):
    "Convert 2-byte signed into regular Python int."
    return struct.unpack('>h', bytearray(inbytes))[0]
    
def threebyte2float(bytelist):
    "Take Neslab's three-byte data format, return float"
    if bytelist[0] in (0x10, 0x11): return float(int162int(bytelist[1:]))/10
    else: return float(int162int(bytelist[1:]))/100
    
def decode_status_array(fivebytes):
    "Decode RTE-7 controller's 5-byte status array to Python dict"
    fortybits = [bool(int(bit)) for bit in ''.join(bin(byte).split('b')[1] for byte in fivebytes).zfill(40)]
    # identifiers for the bits, per Table 2 in manual
    stati = [
        "rtd1_open_fault",
        "rtd1_short_fault",
        "rtd1_open",
        "rtd1_short",
        "rtd3_open_fault",
        "rtd3_short_fault",
        "rtd3_open",
        "rtd3_short",
        "rtd2_open_fault",
        "rtd2_short_fault",
        "rtd2_open_warn",
        "rtd2_short_warn",
        "rtd2_open",
        "rtd2_short",
        "refrig_hi_temp",
        "htc_fault",
        "hi_fixed_temp_fault",
        "lo_fixed_temp_fault",
        "hi_temp_fault",
        "lo_temp_fault",
        "lo_level_fault",
        "hi_temp_warn",
        "lo_temp_warn",
        "lo_level_warn",
        "buzzer_on",
        "alarm_muted",
        "unit_faulted",
        "unit_stopping",
        "unit_on",
        "pump_on",
        "comp_on",
        "heat_on",
        "rtd2_controlling",
        "heat_led_flashing",
        "heat_led_on",
        "cool_led_flashing",
        "cool_led_on"
    ]
    return dict(zip(stati, fortybits))
    
def enframe(cmd, dat=[], multidrop=False, addr=1):
    "Enframe query for NESLAB serial protocol, return bytelist."
    
    if not isinstance(cmd, list): cmd = [cmd]
    
    if not multidrop: 
        leadchar = 0xca # RS-232
        addr = [0x00, 0x01]
    else: 
        leadchar = 0xcc # RS-485/422
        if addr in range(1, 64): addr = [0x00, addr] # prepend MSB
        else: raise Exception("Multidrop address must be in range [1,64]")
        
    # build the bytelist
    frame = [leadchar] + addr + cmd + [len(dat)] + dat
        
    # append checksum, excluding lead char
    return frame + [checksum(frame[1:])]
    
class TCal:
    "Class for digital linear calibration"
    def __init__(self, slope, xcept):
        "Slope and intercept convert from reference to actual"
        self.__slope__ = slope
        self.__xcept__ = xcept
    reset = __init__ # alias
    def ref2act(self, temp_ref):
        return ((temp_ref * self.__slope__) + self.__xcept__)
    def act2ref(self, temp_act):
        return ((temp_act - self.__xcept__) / self.__slope__)

class NeslabController(TCal):
    "Class for a waterbath controller"
    def __init__(self, port, multidrop=False, addr=1, baud=9600, timeout=1, parity=serial.PARITY_NONE, rtscts=False):
        """
        Open serial interface, return fault status.
        The serial handle becomes a public instance object.
        """
        self.__ser__ = serial.Serial(port=port, baudrate=baud, timeout=timeout, parity=parity)
        self.__ser__.flush()
        self.__multidrop__ = multidrop
        self.__addr__ = addr
        # initialize calibrations at unity
        # these can be adjusted by bath.cal_ext.reset(slope, xcept)
        self.cal_int = TCal(1, 0)
        self.cal_ext = TCal(1, 0)
        
    def query(self, cmd, dat=[]):
        "Send a query and return response bytes; throw warning and try again if checksum fails."
        
        tries = 0
        while not tries or not ((leader == query) and (ckbyte == chksum)):
            tries += 1
            # send query
            query = enframe(cmd, dat, multidrop = self.__multidrop__, addr = self.__addr__)
            #print(query) #TEST
            self.__ser__.write(query)
            self.__ser__.flush()
            
            # read full response
            # starting with 4-byte leader and manifest byte
            reply = []
            reply += bytestr2bytelist(self.__ser__.read(5))
            # the last one is the number of data bytes
            # (plus the checkbyte)
            reply += bytestr2bytelist(self.__ser__.read(reply[-1]+1))
            
            # parse the reply
            leader = reply[:4] # lead char, address, and command
            dbytes = reply[5:-1] # data bytes
            ckbyte = reply[-1] # checksum
            #print(list(reply)) #TEST
            # and calc correct checksum
            chksum = checksum(reply[1:-1])
            
            # check that leader matches
            if leader == query[:4]:
                # and that checksum is valid
                if ckbyte == chksum:
                    return dbytes
                else: warn("Checksum mismatch: should be {}; read {}. Attempt #{}".format(chksum, ckbyte, tries))
            else: warn("Command mismatch: should be {}; read {}. Attempt #{}".format(query[:4], leader, tries))
        
    def disconnect(self):
        "Close serial interface."
        self.__ser__.reset_input_buffer()
        self.__ser__.reset_output_buffer()
        self.__ser__.close()
        
    # register setters/getters
    ## these are for static values that are changeable only by user command
    ## i.e. not dynamic measured values
        
    def status_set(self, 
        unit_on = None, 
        probe_ext = None, 
        faults = None, 
        mute = None, 
        auto_restart = None,
        prec_hi = None,
        fullrange_cool = None,
        remote = None
    ):
        # make sure bytes are in order
        switches = ["unit_on", "probe_ext", "faults", "mute", "auto_restart", "prec_hi", "fullrange_cool", "remote"]
        allvars = locals()
        dat = [0x02 if allvars[i] is None else int(allvars[i]) for i in switches]
        return self.query([0x81], dat=dat) == dat # True if successful
    
    def status_get(self):
        "Get full status array."
        # send get status command, decode 5-byte reply
        return decode_status_array(self.query([0x09]))
            
    def on(self, status=None):
        "Get or set on-status of the circulator."
        # 20220105 hack fix, status reads incorrectly
        # get
        if status is None: self.status_get()["unit_on"]; return True
        # set
        else: self.status_set(unit_on = status); return True
            
    def probe_ext(self, status=None):
        "Get or set status of external probe (used for control, or not?)"
        # get
        if status is None: return self.status_get()["rtd2_controlling"]
        # set
        else: return self.status(probe_ext=status)
        
    def temp_set(self, temp=None):
        "Set or get temperature setpoint."
        # get
        if temp is None: return threebyte2float(self.query([0x70]))
        # set
        # temp*10 if in 0.1 mode, *100 if 0.01 mode. #TODO: make less dumb
        else: return threebyte2float(self.query([0xf0], dat=int2int16(int(round(temp, 2)*100)))) == temp
            
    def fault_lo(self, limit=None):
        "Set or get low-temp fault limit."
        # get
        if limit is None: return threebyte2float(self.query([0x40]))
        # set
        else: return threebyte2float(self.query([0xc0], dat=int2int16(limit*10))) == limit
            
    def fault_hi(self, limit=None):
        "Set or get low-temp fault limit."
        # get
        if limit is None: return threebyte2float(self.query([0x60]))
        # set
        else: return threebyte2float(self.query([0xe0], dat=int2int16(limit*10))) == limit
            
    # method aliases for back-compat w/Thermo Isotemp
    warn_lo = fault_lo
    warn_hi = fault_hi
            
    # RTE-7 only; leave for later
    #def temp_prec(self, prec=None):
    #    "Get or set temperature precision (# decimal places)."
    #    if prec is None:
    #        # get precision
    #        self.__ser__.write("RTP\r".encode())
    #        self.__ser__.flush()
    #        return(str2float(self.__ser__.read_until('\r')))
    #    else:
    #        # set precision
    #        self.__ser__.write("STR {}\r".format(prec).encode())
    #        self.__ser__.flush()
    #        return(self.rcvd_ok())
            
    def pid(self, drive, p=None, i=None, d=None):
        """
        Get or set PID bandwidths for heater or chiller drive (H/C).
        p in %           (0.1-99.9)
        i in repeats/min (0-9.99)
        d in min         (0-5.0)
        """
        # bit shift register for heat/cool drive
        drive_shift = {'H': 0, 'C': 3}
        # get proportional band
        if p is None: p = threebyte2float(self.query([0x71+drive_shift]))
        # set proportional band
        else: p = (threebyte2float(self.query([0xF1+drive_shift], dat=int2int16(p*10))) == p)
        # get integral band
        if i is None: i = threebyte2float(self.query([0x72+drive_shift]))
        # set integral band
        else: i = (threebyte2float(self.query([0xF2+drive_shift], dat=int2int16(i*100))) == i)
        # get derivative band
        if d is None: d = threebyte2float(self.query([0x73+drive_shift]))
        # set derivative band
        else: d = (threebyte2float(self.query([0xF3+drive_shift], dat=int2int16(d*10))) == d)
        return((p, i, d))
                    
    # not NESLAB-supported
    #def units(self, unit=None):
    #    "Get or set temperature unit (C/F/K)."
    #    if not unit:
    #        # get unit
    #        self.__ser__.write("RTU\r".encode())
    #        self.__ser__.flush()
    #        return(self.__ser__.read_until('\r').decode().strip())
    #    else:
    #        # set unit
    #        self.__ser__.write("STU {}\r".format(unit).encode())
    #        self.__ser__.flush()
    #        return(self.rcvd_ok())
    
    # data requests
    ## for data measured in real time
            
    def temp_get_int(self):
        "Get current temp at internal sensor."
        return threebyte2float(self.query([0x20]))
        
    def temp_get_ext(self):
        "Get current temp at external sensor."
        return threebyte2float(self.query([0x21]))
            
    def temp_get_act(self, ext=None):
        "Get calibrated temp, by default from active sensor."
        # if sensor not specified, use the active one
        if ext is None: ext = self.probe_ext()
        if not ext: return(cal_int.ref2act(self.temp_get_int()))
        else: return(cal_ext.ref2act(self.temp_get_ext()))