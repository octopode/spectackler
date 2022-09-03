#spectackler

Drivers and software for making spectrophotometric measurements under pressure.

**Teach your old spec new tricks!**

These drivers and interfaces provide an cross-platform, open-source interface for
instruments that previously required proprietary Windows software.

###Suggested use

The [below drivers](#hardware-drivers) are commented and I hope their methods will be self-explanatory. Use my [data collection suites](#data-collection-suites) as application examples. Go get 'em (data) and have fun!

##Hardware drivers

Each module implements one device class. You can connect as many instances of the device as you like.

* [(Teledyne) ISCO D-series high-pressure syringe pump `isco260D.py`](#isco260d.py)

* [(Thermo) NESLAB RTE series Digital Plus temperature controller `neslabrte.py`](#neslabrte.py)

* [Fisher Isotemp 6200 temperature controller `isotemp6200.py`](#isotemp6200.py)

* [Shimadzu RF-5301PC spectrofluorophotometer `rf5301.py`](#rf5301.py)

* [Auxiliary microcontroller for misc functions](#amcu.py)

> This hardware works fine 

##Data collection suites

Several higher-level scripts are included here that use some or all of the above drivers

* [Ratiometric fluorimetry (specifically, Laurdan)](#viscotheque_laurdan.py)

* [Kinetics](#kinetheque.py)

* [Calibration routines](#calibration-routines)

##Data visualization

* Laurdan GP (with `ggplot2`)

* Kinetic trace (in python)

###isco260d.py

Though I originally wrote this for a model 260D pump, I have been using it unmodified with an 100DM and have yet to experience any issues. 

`iscotest.py` can be used to test your setup with the driver.

The most common culprits for communication problems are:

1. Wrong serial port passed to driver. This is set in the calling script on the computer side.

2. Pump address mismatched between computer and controller. This is the `dest` arg in the `ISCOController` constructor.

3. Baudrate mismatched between computer and controller.

To change the pump address and baudrate on the pump side, [consult the manual](https://github.com/octopode/spectackler/blob/master/manuals/isco_man.pdf).

> Note: for unknown reasons, the `STOPALL` command issued by the `stop()` method does not work on either pump I have used. Recommend using `pause()`, which I built as a workaround. It stores the current setpoint, issues `CLEAR`, then restores the setpoint.

###neslabrte.py

`neslabtest.py` can be used to test your setup with the driver.

Some notes on this version of the driver (as of 20220902):

1. RS485 multidrop functionality is untested. Recommend direct RS232 connection if you
want to use it out of the box.

2. Decoding of the instrument status array (i.e. by `status_get()`) is not quite right. I just used the byte order in the manual. If you figure out the correct one, please share it! Meanwhile I have been getting by just fine in routine applications avoiding the use of `status_get()`.

And a general note on NESLAB waterbaths:

* Unlike some other makes, serial vs. front panel control on a NESLAB bath is __either/or__: once in serial the only button that will function on the temp controller is POWER. Conversely, outside of serial mode, the instrument will not respond to serial signals. To learn which buttons get you in (and if need be, out), of serial mode, see pp. 24 of [the manual.](https://github.com/octopode/spectackler/blob/master/manuals/Thermo-NESLAB_RTE-0series.pdf) The easiest way to hand control back to the front panel is to issue `status_set(remote=False)`.

###isotemp6200.py

`isotemptest.py` can be used to test your setup with the driver.

The isotemp line are solid budget waterbaths. Current models come with a built-in UART but are serial devices at heart. They have a straightforward, if nonstandard, ASCII-based com protocol.

The only issue I have ever had using this driver involves the UART dropping out when connected to an unpowered USB hub.

###rf5301.py

`spectest.py` can be used to test your setup with the driver.

The Shimadzu RF-5301 is not the most modern fluorospec, but these days it's fairly affordable, and its optical bench and noise reduction circuit are sturdy and effective.

The legacy Windows-based control software is `RFPC.exe`. It is a 16-bit program with some functions that rely on an [x87-compatible coprocessor](https://en.wikipedia.org/wiki/X87). You can apply [one of these fixes](https://stackoverflow.com/questions/10511506/old-16-bit-application-causing-gpf-in-win87em-dll-intermittently) to run it on a modern CPU or VM.

Note: Unlike the other instruments here, there is no serial comms protocol available for the RF5301. All the commands implemented here were reverse-engineered by [sniffing](#low-cost-serial-sniffer) RS232 transmissions between the `RFPC` software and the instrument. Two consequences of this:

1. `rf5301.py` cannot do everything `RFPC` can. I only took the time to reverse-engineer functions that I use.

2. As of 20220422, I have not figured out the checksum for this instrument. The helpful folks at Shimadzu couldn't get documentation either. So for now, checkbytes for all operations I use are hardcoded. If you need a wavelength other than those for DPH or Laurdan, or you want to use a function I have not, you have 3 options:

  1. Send the parameter (e.g. wavelengths) to the instrument using RFPC, then switch over to your Python script. Works if the parameter will be the same throughout experiement.
  
  2. [Sniff](#low-cost-serial-sniffer) the checkbyte sent by `RFPC` and hardcode it yourself.
  
  3. Use your superior math abilities to deduce the checksum algorithm. If you succeed, please share!
  
  > As of 20220902, I have a lead on `RFPC` internal documentation. Stay tuned!
  
###amcu.py

Auxiliary MicroController Unit (AMCU) is the fancy name for an Arduino I have hooked up to the system to do odd jobs. As of now, these consist of:

1. Monitoring the humidity and temperature inside the sample chamber for the purpose of estimating dewpoint. A DHT11 sensor package is used.

2. Controlling a tiny reed relay that shuts off the Xenon lamp in the fluorospec once a long-running experiment is complete. Automated lamp control is not a built-in feature of the spec.

`auxtest.py` can be used to test your setup with the driver. To test things on the hardware side, simple ASCII commands can also be sent via a serial console like the one in the Arduino IDE.

`20211230_CubetteAux.ino` is the latest version of the sketch I've been running on the Arduino.

###Low-cost serial sniffer

A byproduct of this project was a cheap and straightforward way to intercept bidirectional RS232 communications. It took me a couple hours to get this solution together, so I'm including it here in hopes it might help someone. A lot of RS232-based lab equipment is still around, and not all of it has well-documented comm protocols.

####Hardware

1. In addition to whatever's already in your setup, you are going to need __a pair of USB <-> RS232 adaptors__ to dedicate to sniffing. A dual-port adaptor (e.g. StarTech ICUSB2322I) is just as good.

2. _DB9 gender changer and additional cable._ Make sure neither is a [null modem](https://en.wikipedia.org/wiki/Null_modem); the adaptor being used for sniffing will be invisible to the software being sniffed and that software wants to talk to DCE.

Connect as follows:

```
------------------------------
| Computer running legacy SW |
------------------------------
  |
  | (RS232 w/gender changer; ends up F-F)
  |
  |---|-------------------|   (USB*)  |-------------------------------|
      | Dual-port adaptor |-----------| Sniffing computer (runs *NIX) |
  |---|-------------------|           |-------------------------------|
  |
  | (RS232)
  |
---------------------------
| Laboratory Instrument X |
---------------------------
*2x adaptors and 2x USB connections if you use twin single-port adaptors
```

####Software

This was the tricky bit for me. [`socat`](https://linux.die.net/man/1/socat) is a fantastic utility, but like many UNIX-compatible tools, it's not the most intuitive.

If you use `conda`, installation is as simple as `conda install -c conda-forge socat`.

Then run this magic command:
`socat -x -dd /dev/cu.usbserial-FT4IVKAO0,raw,echo=0,crnl /dev/cu.usbserial-FT4IVKAO1,raw,echo=0,crnl 2>&1`

This will render the sniffing machine "invisible" by relaying all signals through verbatim. It will also print all intercepted data to `stdout`.

Here is the incantation dissected:

+ `/dev/cu.usbserial-FT4IVKAO0`, `/dev/cu.usbserial-FT4IVKAO1`: device handles for the two ports on the sniffing adaptor(s). The setup is bidirectional and so should work even if you switch these addresses.

+ `crnl` is the line ending generally used by Windows.

+ `2>&1` moves `stderr` output to `stdout`. `socat` prints natively to `stderr`.

Once you start communicating with your instrument, the `socat` terminal will spit out bytes in hexadecimal. `socatrans.py` is a gizmo you can use to translate these to their corresponding ASCII characters. If the instrument in question uses an ASCII-based protocol, this can make the commands more intuitive (e.g. the RF5301 uses `SX` and `SM` to Set eX and eM wavelengths).

`socat -x -dd /dev/cu.usbserial-FT4IVKAO0,raw,echo=0,crnl /dev/cu.usbserial-FT4IVKAO1,raw,echo=0,crnl 2>&1 | tee hex.log | socatrans.py | asc.log`

Happy sniffing!