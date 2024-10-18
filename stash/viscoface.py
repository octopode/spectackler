#!/usr/bin/python3

"""
viscoface.py

Plotting module for viscotheque. Generates a filled contour plot of 
anisotropy values across simultaneous sweeps of temperature and pressure.

Offers methods to draw a dynamically updating plot, and also to save
that plot to a file.
"""

import matplotlib.pyplot as plt

"""
class LiveContour:
	"contour plot with a live update method"
	
	def __init__(self, 
		levels=(0, 0.2, 0.4, 0.6, 0.8, 1.0),
		cmap = plt.get_cmap("plasma"))
		):
		
		# the thing itself!
		plot, = plt.contourf([], [], [], levels=levels, cmap=cmap)
		
		return plot
		
	def add_point(x, y, z):
		plot.set_xdata(np.append(plot.get_xdata(), x))
		plot.set_ydata(np.append(plot.get_ydata(), y))
		plot.set_zdata(np.append(plot.get_xdata(), z))
		
		return plot
"""