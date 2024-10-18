#!/usr/bin/python3

file_data = "/Applications/spectackler/20200714_t-log.tsv"

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import pandas as pd

# Create figure for plotting
fig = plt.figure()
ax = fig.add_subplot(1, 1, 1)
t = []
temp_ext = []
temp_int = []
temp_set = []

# This function is called periodically from FuncAnimation
def animate(i, t, temp_ext, temp_int, temp_set):
	
    data = pd.read_csv(file_data, sep='\t')

    t = data['watch']
    temp_ext = data['T_ext']
    temp_int = data['T_int']
    temp_set = data['T_set']

    # Draw x and y lists
    ax.clear()
    ax.plot(t, temp_ext, c="red")
    ax.plot(t, temp_int, c="green")
    ax.plot(t, temp_set, c="yellow")

    # Format plot
    plt.xticks(rotation=45, ha='right')
    plt.subplots_adjust(bottom=0.30)
    #plt.title('TMP102 Temperature over Time')
    plt.ylabel('Temperature (deg C)')

# Set up plot to call animate() function periodically
ani = animation.FuncAnimation(fig, animate, fargs=(t, temp_ext, temp_int, temp_set), interval=1000)
plt.show()