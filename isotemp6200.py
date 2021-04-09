#!/usr/bin/env python3

"""
isotemp6200.py

driver module for controlling Fisher Isotemp 6200 circulator
v0.5 (c) JRW 2019 - jwinnikoff@mbari.org

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

import serial
import time
import io
from re import sub

def str2float(bytestring):
    return float(sub("[^0123456789\.]", "", bytestring.decode()))
    
def str2bool(bytestring):
    "Convert b'0'/b'1' to Boolean. b'' also returns False."
    return bool(int('0'+bytestring.decode().strip()))
    
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

class IsotempController(TCal):
    def __init__(self, port, baud=9600, timeout=1, parity=serial.PARITY_NONE, rtscts=False):
        """
        Open serial interface, return fault status.
        The serial handle becomes a public instance object.
        """
        self.__ser__ = serial.Serial(port=port, baudrate=baud, timeout=timeout, parity=parity)
        self.__ser__.flush()
        # initialize calibrations at unity
        # these can be adjusted by bath.cal_ext.reset(slope, xcept)
        self.cal_int = TCal(1, 0)
        self.cal_ext = TCal(1, 0)
        
    def disconnect(self):
        "Close serial interface."
        self.__ser__.reset_input_buffer()
        self.__ser__.reset_output_buffer()
        self.__ser__.close()
        
    def rcvd_ok(self):
        "Readline and if OK code comes in, return True; else, False."
        return self.__ser__.read_until('\r') == b'OK\r'
        
    # register setters/getters
    ## these are for static values that are changeable only by user command
    ## i.e. not dynamic measured values
            
    def on(self, status=None):
        "Get or set on-status of the circulator."
        if status is None:
            # get status
            self.__ser__.write("RO\r".encode())
            self.__ser__.flush()
            return(str2bool(self.__ser__.read_until('\r')))
        elif status:
            # start circulator
            self.__ser__.write("SO 1\r".encode())
            self.__ser__.flush()
            return(self.rcvd_ok())
        else:
            # stop circulator
            self.__ser__.write("SO 0\r".encode())
            self.__ser__.flush()
            return(self.rcvd_ok())
            
    def pump_speed(self, speed=None):
        "Get or set pump speed (L/H)."
        if speed is None:
            # get speed
            self.__ser__.write("RPS\r".encode())
            self.__ser__.flush()
            return(self.__ser__.read_until('\r').decode().strip())
        else:
            # set speed low or high
            self.__ser__.write("SPS {}\r".format(speed).encode())
            self.__ser__.flush()
            return(self.rcvd_ok())
            
    def probe_ext(self, status=None):
        "Get or set status of external probe (used for control, or not?)"
        if status is None:
            # get status
            self.__ser__.write("RE\r".encode())
            self.__ser__.flush()
            return(str2bool(self.__ser__.read_until('\r')))
        elif status:
            # switch to external probe
            self.__ser__.write("SE 1\r".encode())
            self.__ser__.flush()
            return(self.rcvd_ok())
        else:
            # switch to internal probe
            self.__ser__.write("SE 0\r".encode())
            self.__ser__.flush()
            return(self.rcvd_ok())
        
    def temp_set(self, temp=None, x=""):
        "Set or get temperature setpoint x, or if x not specified, displayed setpoint."
        if not temp:
            # get setpoint
            self.__ser__.write("RS{}\r".format(x).encode())
            self.__ser__.flush()
            return(str2float(self.__ser__.read_until('\r')))
        else:
            # set setpoint
            self.__ser__.write("SS{} {}\r".format(x, temp).encode())
            self.__ser__.flush()
            return(self.rcvd_ok())
            
    def warn_lo(self, limit=None):
        "Set or get low-temp warning limit."
        if not limit:
            # get limit
            self.__ser__.write("RLTW\r".encode())
            self.__ser__.flush()
            return(str2float(self.__ser__.read_until('\r')))
        else:
            # set limit
            self.__ser__.write("SLTW {}\r".format(limit).encode())
            self.__ser__.flush()
            return(self.rcvd_ok())
            
    def fault_lo(self, limit=None):
        "Set or get low-temp fault limit."
        if limit is None:
            # get limit
            self.__ser__.write("RLTF\r".encode())
            self.__ser__.flush()
            return(str2float(self.__ser__.read_until('\r')))
        else:
            # set limit
            self.__ser__.write("SLTF {}\r".format(limit).encode())
            self.__ser__.flush()
            return(self.rcvd_ok())
            
    def warn_hi(self, limit=None):
        "Set or get low-temp warning limit."
        if not limit:
            # get limit
            self.__ser__.write("RHTW\r".encode())
            self.__ser__.flush()
            return(str2float(self.__ser__.read_until('\r')))
        else:
            # set limit
            self.__ser__.write("SHTW {}\r".format(limit).encode())
            self.__ser__.flush()
            return(self.rcvd_ok())
            
    def fault_hi(self, limit=None):
        "Set or get low-temp fault limit."
        if limit is None:
            # get limit
            self.__ser__.write("RHTF\r".encode())
            self.__ser__.flush()
            return(str2float(self.__ser__.read_until('\r')))
        else:
            # set limit
            self.__ser__.write("SHTF {}\r".format(limit).encode())
            self.__ser__.flush()
            return(self.rcvd_ok())
            
    def temp_prec(self, prec=None):
        "Get or set temperature precision (# decimal places)."
        if prec is None:
            # get precision
            self.__ser__.write("RTP\r".encode())
            self.__ser__.flush()
            return(str2float(self.__ser__.read_until('\r')))
        else:
            # set precision
            self.__ser__.write("STR {}\r".format(prec).encode())
            self.__ser__.flush()
            return(self.rcvd_ok())
            
    def pid(self, drive, p=None, i=None, d=None):
        """
        Get or set PID bandwidths for heater or chiller drive (H/C).
        p in %
        i in repeats/min
        d in min
        """
        if p is None:
            # get proportional band
            self.__ser__.write("RP{}\r".format(drive).encode())
            self.__ser__.flush()
            p = str2float(self.__ser__.read_until('\r'))
        else:
            # set proportional band
            self.__ser__.write("SP{} {}\r".format(drive, p).encode())
            self.__ser__.flush()
            p = self.rcvd_ok()
        if i is None:
            # get integral band
            self.__ser__.write("RI{}\r".format(drive).encode())
            self.__ser__.flush()
            i = str2float(self.__ser__.read_until('\r'))
        else:
            # set integral band
            self.__ser__.write("SI{} {}\r".format(drive, i).encode())
            self.__ser__.flush()
            i = self.rcvd_ok()
        if d is None:
            # get derivative band
            self.__ser__.write("RD{}\r".format(drive).encode())
            self.__ser__.flush()
            d = str2float(self.__ser__.read_until('\r'))
        else:
            # set derivative band
            self.__ser__.write("SD{} {}\r".format(drive, d).encode())
            self.__ser__.flush()
            d = self.rcvd_ok()
        return((p, i, d))
                    
    def units(self, unit=None):
        "Get or set temperature unit (C/F/K)."
        if not unit:
            # get unit
            self.__ser__.write("RTU\r".encode())
            self.__ser__.flush()
            return(self.__ser__.read_until('\r').decode().strip())
        else:
            # set unit
            self.__ser__.write("STU {}\r".format(unit).encode())
            self.__ser__.flush()
            return(self.rcvd_ok())
    
    # data requests
    ## for data measured in real time
            
    def temp_get_int(self):
        "Get current temp at internal sensor."
        self.__ser__.write("RT\r".encode())
        self.__ser__.flush()
        return(str2float(self.__ser__.read_until('\r')))
        
    def temp_get_ext(self):
        "Get current temp at external sensor."
        self.__ser__.write("RT2\r".encode())
        self.__ser__.flush()
        return(str2float(self.__ser__.read_until('\r')))
            
    def temp_get_act(self, ext=None):
        "Get calibrated temp, by default from active sensor."
        # if sensor not specified, use the active one
        if ext is None: ext = self.probe_ext()
        if not ext: return(cal_int.ref2act(self.temp_get_int()))
        else: return(cal_ext.ref2act(self.temp_get_ext()))