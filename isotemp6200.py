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
import io
from re import sub

def str2float(string):
	return sub("[^0123456789\.]", "", string)

class IsotempController:
	def __init__(self, port, baud=9600, timeout=1):
		"""
		Open serial interface, return fault status.
		The serial handle becomes a public instance object.
		"""
		ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)
		# IO wrapper gets readline() to work right
		self.__sio__ = io.TextIOWrapper(io.BufferedRWPair(ser, ser))
		#self.__sio__.write("RSUM\r".encode())
		self.__sio__.write("RSUM\r")
		self.__sio__.flush()
		rsum = str(self.__sio__.readline()).strip()
		print(rsum) #TEST
		if len(rsum) != 4: # need additional criteria here for acceptable rsum
			self.__sio__.close()
			raise Exception("{} is not behaving like an Isotemp 6200".format(port))
			
	def disconnect():
		self.__sio__.close()
		
	"""
	## SET COMMANDS ##
	Acceptable types and ranges vary; see Isotemp 6200 user manual for serial
	command table. Success returns the string "OK". Failure results in an
	error string from hardware.
	"""
		
	def set_displayed_setpoint(self, val):
		self.__sio__.write("SS {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_setpoint_x(self, val):
		self.__sio__.write("SSX {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_high_temperature_fault(self, val):
		self.__sio__.write("SHTF {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_high_temperature_warning(self, val):
		self.__sio__.write("SHTW {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_low_temperature_fault(self, val):
		self.__sio__.write("SLTF {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_low_temperature_warning(self, val):
		self.__sio__.write("SLTW {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_proportional_heat_band_setting(self, val):
		self.__sio__.write("SPH {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_proportional_cool_band_setting(self, val):
		self.__sio__.write("SPC {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_integral_heat_band_setting(self, val):
		self.__sio__.write("SIH {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_integral_cool_band_setting(self, val):
		self.__sio__.write("SIC {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_derivative_heat_band_setting(self, val):
		self.__sio__.write("SDH {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_derivative_cool_band_setting(self, val):
		self.__sio__.write("SDC {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_temperature_resolution(self, val):
		self.__sio__.write("STR {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_temperature_units(self, val):
		self.__sio__.write("STU {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_unit_on_status(self, val):
		self.__sio__.write("SO {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_external_probe_on_status(self, val):
		self.__sio__.write("SE {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_auto_restart_enabled(self, val):
		self.__sio__.write("SAR {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_energy_saving_mode(self, val):
		self.__sio__.write("SEN {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()

	def set_pump_speed(self, val):
		self.__sio__.write("SPS {}\r".format(val))
		self.__sio__.flush()
		return self.__sio__.readline()
		
	"""
	## READ COMMANDS ##
	Units are stripped from the hardware return. See the manual for units,
	or in case of temperature, query with read_temperature_units().
	"""

	def read_firmware_checksum(self):
		self.__sio__.write("RSUM\r").encode()
		self.__sio__.flush()
		return self.__sio__.readline()

	def read_temperature_internal(self):
		self.__sio__.write("RT\r").encode()
		return str2float(self.__sio__.readline())

	def read_temperature_external(self):
		self.__sio__.write("RT2\r").encode()
		return str2float(self.__sio__.readline())

	def read_displayed_setpoint(self):
		self.__sio__.write("RS\r").encode()
		return str2float(self.__sio__.readline())

	def read_setpoint_x(self):
		self.__sio__.write("RSX\r").encode()
		return str2float(self.__sio__.readline())

	def read_high_temperature_fault(self):
		self.__sio__.write("RHTF\r").encode()
		return str2float(self.__sio__.readline())

	def read_high_temperature_warn(self):
		self.__sio__.write("RHTW\r").encode()
		return str2float(self.__sio__.readline())

	def read_low_temperature_fault(self):
		self.__sio__.write("RLTF\r").encode()
		return str2float(self.__sio__.readline())

	def read_low_temperature_warn(self):
		self.__sio__.write("RLTW\r").encode()
		return str2float(self.__sio__.readline())

	def read_proportional_heat_band_setting(self):
		self.__sio__.write("RPH\r").encode()
		return str2float(self.__sio__.readline())

	def read_proportional_cool_band_setting(self):
		self.__sio__.write("RPC\r").encode()
		return str2float(self.__sio__.readline())

	def read_integral_heat_band_setting(self):
		self.__sio__.write("RIH\r").encode()
		return str2float(self.__sio__.readline())

	def read_integral_cool_band_setting(self):
		self.__sio__.write("RIC\r").encode()
		return str2float(self.__sio__.readline())

	def read_derivative_heat_band_setting(self):
		self.__sio__.write("RDH\r").encode()
		return str2float(self.__sio__.readline())

	def read_derivative_cool_band_setting(self):
		self.__sio__.write("RDC\r").encode()
		return str2float(self.__sio__.readline())

	def read_temperature_precision(self):
		self.__sio__.write("RTP\r").encode()
		self.__sio__.flush()
		return self.__sio__.readline()

	def read_temperature_units(self):
		self.__sio__.write("RTU\r").encode()
		self.__sio__.flush()
		return self.__sio__.readline()

	def read_unit_on(self):
		self.__sio__.write("RO\r").encode()
		self.__sio__.flush()
		return self.__sio__.readline()

	def read_external_probe_enabled(self):
		self.__sio__.write("RE\r").encode()
		self.__sio__.flush()
		return self.__sio__.readline()

	def read_auto_restart_enabled(self):
		self.__sio__.write("RAR\r").encode()
		self.__sio__.flush()
		return self.__sio__.readline()

	def read_energy_saving_mode(self):
		self.__sio__.write("REN\r").encode()
		self.__sio__.flush()
		return self.__sio__.readline()

	def read_time(self):
		self.__sio__.write("RCK\r").encode()
		self.__sio__.flush()
		return self.__sio__.readline()

	def read_date(self):
		self.__sio__.write("RDT\r").encode()
		self.__sio__.flush()
		return self.__sio__.readline()

	def read_date_format(self):
		self.__sio__.write("RDF\r").encode()
		self.__sio__.flush()
		return self.__sio__.readline()

	def read_firmware_version(self):
		self.__sio__.write("RVER\r").encode()
		self.__sio__.flush()
		return self.__sio__.readline()
