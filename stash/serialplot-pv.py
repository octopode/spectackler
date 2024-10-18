#!/usr/bin/python3

file_data = "data/20200712_viscotest.tsv"

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import pandas as pd

# Create figure for plotting
fig = plt.figure()
ax = fig.add_subplot(1, 1, 1)
temp = []
pres = []

# This function is called periodically from FuncAnimation
def animate(i, temp, pres):
	
    data = pd.read_csv(file_data, sep='\t')

    temp = data['temp_act']
    pres = data['pres_act']

    # Draw x and y lists
    ax.clear()
    ax.plot(temp, pres, linestyle='-', marker='o', c="black")

    # Format plot
    #plt.xticks(rotation=45, ha='right')
    #plt.subplots_adjust(bottom=0.30)
    #plt.title('TMP102 Temperature over Time')
    plt.xlabel('Temperature (deg C)')
    plt.ylabel('Pressure (bar)')

# Set up plot to call animate() function periodically
ani = animation.FuncAnimation(fig, animate, fargs=(temp, pres), interval=1000)
plt.show()