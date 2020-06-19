#! /usr/bin/env python
import numpy as np
import matplotlib
matplotlib.use('TkAgg') # do this before importing pylab

from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Slider, Button, RadioButtons, CheckButtons

# install pyserial with sudo pip install pyserial
import serial

MyPort='/dev/tty.usbmodem1421'


class Scope:
	def __init__(self, ax, maxt=20, dt=0.1):
		self.ax = ax
		self.dt = dt
		self.maxt = maxt
		self.tdata = [0]
		self.ydata = [0]
		self.line = Line2D(self.tdata, self.ydata)
		self.ax.add_line(self.line)
		self.ax.set_ylim(-1, 1000)
		self.ax.set_xlim(0, self.maxt)

	def update(self, y):
		lastt = self.tdata[-1]
		if lastt > self.tdata[0] + self.maxt: # reset the arrays
			self.tdata = [self.tdata[-1]]
			self.ydata = [self.ydata[-1]]
			self.ax.set_xlim(self.tdata[0], self.tdata[0] + self.maxt)
			self.ax.figure.canvas.draw()

		t = self.tdata[-1] + self.dt
		self.tdata.append(t)
		self.ydata.append(y)
		self.line.set_data(self.tdata, self.ydata)
		return self.line,

	def reset(self):
		self.tdata=[0]
		self.ydata=[0]
		self.line.set_data(self.tdata, self.ydata)
		return self.line,


# def emitter(p=0.03):
# 	'return a random value with probability p, else 0'
# 	while True:
# 		v = np.random.rand(1)
# 		if v > p:
# 			yield 0.
# 		else:
# 			yield np.random.rand(1)

fig, ax = plt.subplots()
scope = Scope(ax)
Ser = serial.Serial(MyPort, 9600, timeout=1)

def emitterSerial():
	if Ser:
		Line = Ser.readline()	# read a '\n' terminated line 
		if Line:
			# print Line.strip()
			yield(float(Line))


# pass a generator in "emitter" to produce data for the update func
ani = animation.FuncAnimation(fig, scope.update, emitterSerial, interval=10,
	blit=True)
	
	
###### Radio buttons for color

rax = plt.axes([0.825, 0.8, 0.1, 0.12], axisbg='gray')
radio = RadioButtons(rax, ('blue', 'red','green'), active=0)
def colorfunc(label):
	scope.line.set_color(label)
	# fig.canvas.draw_idle()
radio.on_clicked(colorfunc)

## end radio

## Reset button	
resetax = plt.axes([0.8, 0.025, 0.1, 0.04])
button = Button(resetax, 'Reset', color='gray', hovercolor='0.975')
def reset(event):
	scope.reset()
	yvals=[]
button.on_clicked(reset)

## Save button	
resetax = plt.axes([0.6, 0.025, 0.1, 0.04])
button = Button(resetax, 'Save', color='green', hovercolor='0.975')
def savefile(event):
	print scope.tdata[1:]
	print scope.ydata[1:]
	
button.on_clicked(savefile)


plt.show()