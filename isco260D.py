#!/usr/bin/python3

"""
isco260D.py

driver module for controlling [Teledyne] ISCO 260D syringe pump(s)
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

def dasnet_checksum(cmd):
    "Calculate 2-digit hex checksum for a DASNET command."
    #print([ord(char) for char in list(cmd)])
    tot = sum([ord(char) for char in list(cmd)])
    return format(256 - tot%256, '02x').upper()

def str2dasnet(msg, source='', dest=''):
    "Convert serial command to DASNET frame."
    cmd = "{}R{}{}{}".format(dest, source, format(len(msg), '02x'), msg).upper()
    frame = "{}{}\r".format(cmd, dasnet_checksum(cmd))
    return frame.encode()

class ISCOController:
    def __init__(self, port, baud=9600, timeout=1, source=1, dest=1):
        """
        Open serial interface, set remote status and baudrate.
        The serial handle becomes a public instance object.
        """
        self.__ser__ = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        self.__source__ = source
        self.__dest__ = dest
        print(self.remote())
        
    # action commands
    ## acknowledged over serial with b'R 8E\r'
        
    def remote(self):
        self.__ser__.write(str2dasnet("REMOTE", self.__source__, self.__dest__))
        return self.__ser__.readline()
        
    def local(self):
        self.__ser__.write(str2dasnet("LOCAL", self.__source__, self.__dest__))
        return self.__ser__.readline()
            
    def disconnect(self):
        self.local()
        self.__ser__.close()
        
    def run(self):
        self.__ser__.write(str2dasnet("RUN", self.__source__, self.__dest__))
        return self.__ser__.readline()
        
    def stop(self):
        self.__ser__.write(str2dasnet("STOPALL", self.__source__, self.__dest__))
        return self.__ser__.readline()
        
    def mode(self, mode, pump='A'):
	    "Set operating mode"
	    shortcuts = {
		    "const_press"	:	'P',
		    "const_flow"	:	'F',
		    "refill"		:	'R',
		    "press_grad"	:	'PG',
	    }
	    if mode not in shortcuts.values():
	    	mode = shortcuts[mode]
	    self.__ser__.write(str2dasnet("MODE {} {}".format(pump, mode))
	    return self.__ser__.readline()
	    
	def zero(self, pump='A'):
		"Zero the pressure sensor."
		self.__ser__.write(str2dasnet("ZERO{}".format(pump), self.__source__, self.__dest__))
	    return self.__ser__.readline()
        
    # register setters/getters
    ## these are for static values that are changeable only by user command
    ## i.e. not dynamic measured values
	
    def maxflow(self, flowrate=None, pump='A'):
	    "Setter if flowrate is specified; otherwise return max flow."
	    if flowrate is None:
	    	self.__ser__.write(str2dasnet("MAXFLOW{}".format(pump), self.__source__, self.__dest__))
	    	return self.__ser__.readline()
	    else:
	    	self.__ser__.write(str2dasnet("MAXFLOW{}={}".format(pump, flowrate), self.__source__, self.__dest__))
	    	return self.__ser__.readline()
	    	
    def minflow(self, flowrate=None, pump='A'):
	    "Setter if flowrate is specified; otherwise return max flow."
	    if flowrate is None:
	    	self.__ser__.write(str2dasnet("MINFLOW{}".format(pump), self.__source__, self.__dest__))
	    	return self.__ser__.readline()
	    else:
	    	self.__ser__.write(str2dasnet("MINFLOW{}={}".format(pump, flowrate), self.__source__, self.__dest__))
	    	return self.__ser__.readline()
	    	
	def maxpress(self, flowrate=None, pump='A'):
	    "Setter if flowrate is specified; otherwise return max flow."
	    if flowrate is None:
	    	self.__ser__.write(str2dasnet("MAXPRESS{}".format(pump), self.__source__, self.__dest__))
	    	return self.__ser__.readline()
	    else:
	    	self.__ser__.write(str2dasnet("MAXPRESS{}={}".format(pump, flowrate), self.__source__, self.__dest__))
	    	return self.__ser__.readline()
	    	
	def minpress(self, flowrate=None, pump='A'):
	    "Setter if flowrate is specified; otherwise return max flow."
	    if flowrate is None:
	    	self.__ser__.write(str2dasnet("MINPRESS{}".format(pump), self.__source__, self.__dest__))
	    	return self.__ser__.readline()
	    else:
	    	self.__ser__.write(str2dasnet("MINPRESS{}={}".format(pump, flowrate), self.__source__, self.__dest__))
	    	return self.__ser__.readline()
	    	
	def press_set(self, setpt=None, pump='A'):
		"""
		Set constant pressure setpoint if specified, else return existing setpoint.
		"""
		if setpt = None:
			# return the current setpoint
			self.__ser__.write(str2dasnet("SETPRESS{}".format(pump), self.__source__, self.__dest__))
	    	return self.__ser__.readline()
	    else:
	    	# change the setpoint
	    	if pump == 'A': pump = '' # an idiosyncrasy in the protocol
	    	self.__ser__.write(str2dasnet("PRESS{}={}".format(pump, setpt), self.__source__, self.__dest__))
	    	return self.__ser__.readline()
	    	
	def integral_enable(self, pump='A'):
		"Enable integral pressure control."
		self.__ser__.write(str2dasnet("IPUMP{}=1".format(pump), self.__source__, self.__dest__))
	    return self.__ser__.readline()
	    
	def integral_disable(self, pump='A'):
		"Disable integral pressure control."
		self.__ser__.write(str2dasnet("IPUMP{}=0".format(pump), self.__source__, self.__dest__))
	    return self.__ser__.readline()
	    
	def units(self, unit="PSI"):
		"Set pressure unit for all pumps."
		# case-insensitive
		self.__ser__.write(str2dasnet("UNITSA={}".format(unit.upper()), self.__source__, self.__dest__))
	    return self.__ser__.readline()
	
	## gradient programming
	
        
    # data requests
    ## for data measured in real time
        
    def gg(self):
        self.__ser__.write(str2dasnet("G&", self.__source__, self.__dest__))
        return self.__ser__.readline()
        
    def status(self, pump='A'):
		"Get operational status and problems."
		self.__ser__.write(str2dasnet("STATUS{}".format(pump), self.__source__, self.__dest__))
	    return self.__ser__.readline()
	    
	def press_get(self, pump='A'):
		"Get actual pressure of pump."
		self.__ser__.write(str2dasnet("PRESS{}".format(pump), self.__source__, self.__dest__))
	    return self.__ser__.readline()
	    
	def vol_get(self, pump='A'):
		"Get volume remaining in cylinder."
		self.__ser__.write(str2dasnet("VOL{}".format(pump), self.__source__, self.__dest__))
	    return self.__ser__.readline()
	    
	# higher-level routines
	## employ methods above
	
	def measure_maxflow(pump='A'):
		"""
		Measure the maximum flowrate that can be maintained without
		building residual pressure in the pump cylinder.
		"""
		
        