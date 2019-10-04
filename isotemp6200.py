#!/usr/bin/python3

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
from re import sub

def str2float(string):
	return sub("[^0123456789\.]", "", string)

class IsotempController:
	def __init__(self, port, baud=9600, timeout=1):
		"""
		Open serial interface, return fault status.
		The serial handle becomes a public instance object.
		"""
		self.__ser__ = serial.Serial(port, baud, timeout)
		self.__ser__.write(b"RSUM\r")
		rsum = str(self.__ser__.readline()).split()
		if len(rsum) == 5:
			return rsum
		else:
			self.__ser__.close()
			raise Exception("{} is not behaving like an Isotemp 6200".format(port))
			
	def disconnect():
		self.__ser__.close()
		
	"""
	## SET COMMANDS ##
	Acceptable types and ranges vary; see Isotemp 6200 user manual for serial
	command table. Success returns the string "OK". Failure results in an
	error string from hardware.
	"""
		
	def set_displayed_setpoint(self, val):
		self.__ser__.write(b"SS {}\r".format(val))
		return self.__ser__.readline()

	def set_setpoint_x(self, val):
		self.__ser__.write(b"SSX {}\r".format(val))
		return self.__ser__.readline()

	def set_high_temperature_fault(self, val):
		self.__ser__.write(b"SHTF {}\r".format(val))
		return self.__ser__.readline()

	def set_high_temperature_warning(self, val):
		self.__ser__.write(b"SHTW {}\r".format(val))
		return self.__ser__.readline()

	def set_low_temperature_fault(self, val):
		self.__ser__.write(b"SLTF {}\r".format(val))
		return self.__ser__.readline()

	def set_low_temperature_warning(self, val):
		self.__ser__.write(b"SLTW {}\r".format(val))
		return self.__ser__.readline()

	def set_proportional_heat_band_setting(self, val):
		self.__ser__.write(b"SPH {}\r".format(val))
		return self.__ser__.readline()

	def set_proportional_cool_band_setting(self, val):
		self.__ser__.write(b"SPC {}\r".format(val))
		return self.__ser__.readline()

	def set_integral_heat_band_setting(self, val):
		self.__ser__.write(b"SIH {}\r".format(val))
		return self.__ser__.readline()

	def set_integral_cool_band_setting(self, val):
		self.__ser__.write(b"SIC {}\r".format(val))
		return self.__ser__.readline()

	def set_derivative_heat_band_setting(self, val):
		self.__ser__.write(b"SDH {}\r".format(val))
		return self.__ser__.readline()

	def set_derivative_cool_band_setting(self, val):
		self.__ser__.write(b"SDC {}\r".format(val))
		return self.__ser__.readline()

	def set_temperature_resolution(self, val):
		self.__ser__.write(b"STR {}\r".format(val))
		return self.__ser__.readline()

	def set_temperature_units(self, val):
		self.__ser__.write(b"STU {}\r".format(val))
		return self.__ser__.readline()

	def set_unit_on_status(self, val):
		self.__ser__.write(b"SO {}\r".format(val))
		return self.__ser__.readline()

	def set_external_probe_on_status(self, val):
		self.__ser__.write(b"SE {}\r".format(val))
		return self.__ser__.readline()

	def set_auto_restart_enabled(self, val):
		self.__ser__.write(b"SAR {}\r".format(val))
		return self.__ser__.readline()

	def set_energy_saving_mode(self, val):
		self.__ser__.write(b"SEN {}\r".format(val))
		return self.__ser__.readline()

	def set_pump_speed(self, val):
		self.__ser__.write(b"SPS {}\r".format(val))
		return self.__ser__.readline()
		
	"""
	## READ COMMANDS ##
	Units are stripped from the hardware return. See the manual for units,
	or in case of temperature, query with read_temperature_units().
	"""

	def read_firmware_checksum(self):
		self.__ser__.write(b"RSUM\r")
		return self.__ser__.readline()

	def read_temperature_internal(self):
		self.__ser__.write(b"RT\r")
		return str2float(self.__ser__.readline())

	def read_temperature_external(self):
		self.__ser__.write(b"RT2\r")
		return str2float(self.__ser__.readline())

	def read_displayed_setpoint(self):
		self.__ser__.write(b"RS\r")
		return str2float(self.__ser__.readline())

	def read_setpoint_x(self):
		self.__ser__.write(b"RSX\r")
		return str2float(self.__ser__.readline())

	def read_high_temperature_fault(self):
		self.__ser__.write(b"RHTF\r")
		return str2float(self.__ser__.readline())

	def read_high_temperature_warn(self):
		self.__ser__.write(b"RHTW\r")
		return str2float(self.__ser__.readline())

	def read_low_temperature_fault(self):
		self.__ser__.write(b"RLTF\r")
		return str2float(self.__ser__.readline())

	def read_low_temperature_warn(self):
		self.__ser__.write(b"RLTW\r")
		return str2float(self.__ser__.readline())

	def read_proportional_heat_band_setting(self):
		self.__ser__.write(b"RPH\r")
		return str2float(self.__ser__.readline())

	def read_proportional_cool_band_setting(self):
		self.__ser__.write(b"RPC\r")
		return str2float(self.__ser__.readline())

	def read_integral_heat_band_setting(self):
		self.__ser__.write(b"RIH\r")
		return str2float(self.__ser__.readline())

	def read_integral_cool_band_setting(self):
		self.__ser__.write(b"RIC\r")
		return str2float(self.__ser__.readline())

	def read_derivative_heat_band_setting(self):
		self.__ser__.write(b"RDH\r")
		return str2float(self.__ser__.readline())

	def read_derivative_cool_band_setting(self):
		self.__ser__.write(b"RDC\r")
		return str2float(self.__ser__.readline())

	def read_temperature_precision(self):
		self.__ser__.write(b"RTP\r")
		return self.__ser__.readline()

	def read_temperature_units(self):
		self.__ser__.write(b"RTU\r")
		return self.__ser__.readline()

	def read_unit_on(self):
		self.__ser__.write(b"RO\r")
		return self.__ser__.readline()

	def read_external_probe_enabled(self):
		self.__ser__.write(b"RE\r")
		return self.__ser__.readline()

	def read_auto_restart_enabled(self):
		self.__ser__.write(b"RAR\r")
		return self.__ser__.readline()

	def read_energy_saving_mode(self):
		self.__ser__.write(b"REN\r")
		return self.__ser__.readline()

	def read_time(self):
		self.__ser__.write(b"RCK\r")
		return self.__ser__.readline()

	def read_date(self):
		self.__ser__.write(b"RDT\r")
		return self.__ser__.readline()

	def read_date_format(self):
		self.__ser__.write(b"RDF\r")
		return self.__ser__.readline()

	def read_firmware_version(self):
		self.__ser__.write(b"RVER\r")
		return self.__ser__.readline()
