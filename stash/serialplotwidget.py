#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""serialplotwidget"""

import numpy as np
import matplotlib
matplotlib.use('TkAgg') # do this before importing pylab
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button, RadioButtons, CheckButtons

import serial


# fig = plt.figure()
# ax = fig.add_subplot(111)
#
# x = range(30)
# y = [random.random() for i in x]
# line, = ax.plot(x,y)
#
# def animateSerial(*args):
#     n = len(y)
#     for 1:
#         data = random.random()
#         y.append(data)
#
#         n += 1
#         line.set_data(range(n-30, n), y[-30:])
#         ax.set_xlim(n-31, n-1)
#         fig.canvas.draw()
#
# fig.canvas.manager.window.after(100, animate)
# plt.show()
#



import matplotlib.pyplot as plt
MyPort='/dev/tty.usbmodem1421'
Ser = serial.Serial(MyPort, 19200, timeout=1)


fig, ax = plt.subplots()
plt.subplots_adjust(left=0.25, bottom=0.25)
t = np.arange(0.0, 1.0, 0.001)
a0 = 5
f0 = 3
s = a0*np.sin(2*np.pi*f0*t)
l, = plt.plot(t,s, lw=2, color='red')
plt.axis([0, 20, 0, 1000])

axcolor = 'lightgoldenrodyellow'
axfreq = plt.axes([0.25, 0.1, 0.65, 0.03], axisbg=axcolor)
axamp  = plt.axes([0.25, 0.15, 0.65, 0.03], axisbg=axcolor)

sfreq = Slider(axfreq, 'Freq', 0.1, 30.0, valinit=f0)
samp = Slider(axamp, 'Amp', 0.1, 10.0, valinit=a0)
yvals = np.array([])

def update(val):
	amp = samp.val
	freq = sfreq.val
	l.set_ydata(amp*np.sin(2*np.pi*freq*t))
	fig.canvas.draw_idle()

def updateSerial(yvals):
	if Ser:
		Line = Ser.readline()	# read a '\n' terminated line 
		if Line:
			# print Line.strip()
			current = float(Line)
			yvals = np.append(yvals,current)
			l.set_ydata(yvals)
			fig.canvas.draw_idle()
			# yield(float(Line))

sfreq.on_changed(update)
samp.on_changed(update)

# Checkboxes from other demo
t = np.arange(0.0, 2.0, 0.01)
s0 = np.sin(2*np.pi*t)
s1 = np.sin(4*np.pi*t)
s2 = np.sin(6*np.pi*t)

l0, = ax.plot(t, s0, visible=False, lw=2)
l1, = ax.plot(t, s1, lw=2)
l2, = ax.plot(t, s2, lw=2)

rax = plt.axes([0.05, 0.3, 0.1, 0.15])
check = CheckButtons(rax, ('2 Hz', '4 Hz', '6 Hz'), (False, True, True))
def checkfunc(label):
    if label == '2 Hz': l0.set_visible(not l0.get_visible())
    elif label == '4 Hz': l1.set_visible(not l1.get_visible())
    elif label == '6 Hz': l2.set_visible(not l2.get_visible())
    plt.draw()
check.on_clicked(checkfunc)



## Reset button	
resetax = plt.axes([0.8, 0.025, 0.1, 0.04])
button = Button(resetax, 'Reset', color=axcolor, hovercolor='0.975')
def reset(event):
	sfreq.reset()
	samp.reset()
	yvals=[]
button.on_clicked(reset)

# Radio buttons for color
rax = plt.axes([0.025, 0.5, 0.15, 0.15], axisbg=axcolor)
radio = RadioButtons(rax, ('red', 'blue', 'green'), active=0)
def colorfunc(label):
	l.set_color(label)
	fig.canvas.draw_idle()
radio.on_clicked(colorfunc)

plt.show()