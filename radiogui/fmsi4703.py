"""
    Userspace Driver for FM Radio Chip Si4703 for Raspberry Pi
    Written by: Miroslav Hájek <mirkousko@gmail.com>
    Date: 2016-11-08

    Thanks to many library implementers that came before
    Especially to: 
        1. Matthias Hertel, http://www.mathertel.de/Arduino
            2014-08-05, BSD style licence
        2. Ryan Edwards <ryan.edwards@gmail.com> 2016-03-27 
            Ported from his Arduino library which was modified 
            from Aaron Weiss @ SparkFun's original library
    
    Licence: GNU GPLv2
"""

import time
import smbus
import RPi.GPIO as GPIO

# Define the register names
DEVICEID =       0x00
CHIPID   =       0x01
POWERCFG =       0x02
CHANNEL  =       0x03
SYSCONFIG1 =     0x04
SYSCONFIG2 =     0x05
SYSCONFIG3 =     0x06
TEST1 =          0x07
TEST2 =          0x08 #Reserved - if modified should be read before writing
BOOTCONFIG =     0x09 #Reserved - if modified should be read before writing
STATUSRSSI =     0x0A
READCHAN =       0x0B
RDSA =           0x0C
RDSB =           0x0D
RDSC =           0x0E
RDSD =           0x0F

# Register 0x02 - POWERCFG 
DSMUTE =         15
DMUTE  =         14
SETMONO =        13
SKMODE =         10
SEEKUP =         9
SEEK =           8
ENABLE =         0

# Register 0x03 - CHANNEL 
TUNE =           15

# Register 0x04 - SYSCONFIG1 
RDSIEN =         15
STCIEN =         14
RDS =            12
DE =             11
BLNDADJ =        6
GPIO3 =          4
GPIO2 =          2
GPIO1 =          0

# Register 0x05 - SYSCONFIG2 
SEEKTH_MASK =    0xFF00
SEEKTH_MIN  =    0x0000
SEEKTH_MID  =    0x1000
SEEKTH_MAX  =    0x7F00

SPACE1 =         5
SPACE0 =         4

# Register 0x06 - SYSCONFIG3 
SKSNR_MASK =     0x00F0
SKSNR_OFF =      0x0000
SKSNR_MIN =      0x0010
SKSNR_MID =      0x0030
SKSNR_MAX =      0x0070

SKCNT_MASK =     0x000F
SKCNT_OFF  =     0x0000
SKCNT_MIN  =     0x000F
SKCNT_MID  =     0x0003
SKCNT_MAX  =     0x0001

# Register 0x0A - STATUSRSSI 
RDSR =          0x8000  # RDS ready 
STC  =          0x4000  # Seek Tune Complete 
SFBL =          0x2000  # Seek Fail Band Limit 
AFCRL =         0x1000
RDSS =          0x0800  # RDS syncronized  
SI   =          0x0100  # Stereo Indicator 
RSSI =          0x00FF


class FMSi4703:

    def __init__(self, i2caddr=0x10, resetpin=5, rdsintpin=6 ,area="EU"):
        self.i2caddr = i2caddr
        self.i2cbus  = smbus.SMBus(1)
        self.rstpin  = resetpin
        self.area    = area
        self.freqlow = 8750
        self.freqhigh = 10800
        self.mono    = False
        self.rds_init() 
        self.rds_setcallback()
      
        if self.area == "EU":
            self.freqsteps = 10
        elif self.area == "US":
            self.freqsteps = 20

        self.__registers = [0] * 16

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.rstpin, GPIO.OUT)
        GPIO.setup(0, GPIO.OUT)

        if rdsintpin != None:
            self.rdsINT = rdsintpin
            self.rds_setinterrupt()
    
    def poweron(self):
        # To get the Si4703 inito 2-wire mode, SEN needs to be high and SDIO
        # needs to be low after a reset
        # The breakout board has SEN pulled high, but also has SDIO
        # pulled high. Therefore, after a normal power up
        # The Si4703 will be in an unknown state. RST must be controlled

        GPIO.output(0, GPIO.LOW) #or pin 2 (SDIO)
        time.sleep(0.1)
        GPIO.output(self.rstpin, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(self.rstpin, GPIO.HIGH)
        time.sleep(0.1)

        self.__readregisters()
        self.__registers[0x07] = 0x8100    # Enable the oscillator, from AN230 page 12, rev 0.9
        self.__writeregisters()

        time.sleep(0.5)                 # Wait for clock to settle - from AN230 page 12
        
        self.__readregisters()
        self.__registers[POWERCFG] = 0x4001               # Enable the IC 
        self.__registers[SYSCONFIG1] |= (1 << RDS)      # Enable RDS

        if self.area == "EU":
            self.__registers[SYSCONFIG1] |= (1 << DE)      # 50kHz Europe setup 
            self.__registers[SYSCONFIG2] |= (1 << SPACE0)  # 100kHz channel spacing
        elif self.area == "US":
            self.__registers[SYSCONFIG2] &= ~(1 << SPACE1 | 1 << SPACE0)

        self.__registers[SYSCONFIG2] &= 0xFFF0 # Clear volume bits
        self.__registers[SYSCONFIG2] |= 0x0001 # Set volume to lowest
        self.__registers[SYSCONFIG2] |= SEEKTH_MID;    


        # set seek parameters
        self.__registers[SYSCONFIG3] &= ~(SKSNR_MASK)  # Clear seek mask bits
        self.__registers[SYSCONFIG3] |= SKSNR_MID      # Set volume

        self.__registers[SYSCONFIG3] &= ~(SKCNT_MASK)  # Clear seek mask bits
        self.__registers[SYSCONFIG3] |= SKCNT_MID;     # Set volume

        self.__writeregisters()
        time.sleep(0.11)

    def shutdown(self):
        self.__readregisters()
        # Powerdown as defined in AN230 page 13 rev 0.9
        self.__registers[TEST1] = 0x7C04    # Power down the IC
        self.__registers[POWERCFG] = 0x002A # Power down the IC
        self.__registers[SYSCONFIG1] = 0x0041 # Power down the IC
        self.__writeregisters()

    def setvolume(self, volume):
        self.__readregisters()
        if (volume < 0): volume = 0
        if (volume > 15): volume = 15
        self.volume = volume

        self.__registers[SYSCONFIG2] &= 0xFFF0      # Clear volume bits
        self.__registers[SYSCONFIG2] |= volume      # Set new volume
        self.__writeregisters()
    
    def getvolume(self):
        self.__readregisters()
        return (self.__registers[SYSCONFIG2] & 0x000F)
    
    def setfrequency(self, newfreq): 
        """
        newchannel = channel * 10   # e.g. 973 * 10 = 9730
        newchannel -= 8750          # e.g. 9730 - 8750 = 980
        newchannel //= 10;           # e.g. 980 / 10 = 98
        """
        if newfreq < self.freqlow: 
            newfreq = self.freqlow
        elif newfreq > self.freqhigh:
            newfreq = self.freqhigh

        # These steps come from AN230 page 20 rev 0.9
        self.__readregisters()
        newchannel = (newfreq - self.freqlow) // self.freqsteps
        self.__registers[CHANNEL] &= 0xFE00     # Clear out the channel bits
        self.__registers[CHANNEL] |= newchannel # Mask in the new channel
        self.__registers[CHANNEL] |= (1 << TUNE) # Set the TUNE bit to start
        self.__writeregisters()
        self.__waitforset()

    def getfrequency(self):
        self.__readregisters()
        channel = self.__registers[READCHAN] & 0x03FF #Mask out everything but the lower 10 bits
        freq = (channel * self.freqsteps) + self.freqlow
        return (freq)

    def seekup(self):
        self.__seek(True)

    def seekdown(self):
        self.__seek(False)

    def __seek(self, seekup):
        self.__readregisters()
        reg = self.__registers[POWERCFG] & ~((1 << SKMODE) | (1 << SEEKUP))
        
        if (seekup == True):
            reg |= (1 << SEEKUP);  # Set the Seek-up bit

        reg |= (1 << SEEK);        # Start seek now

        # save the registers and start seeking...
        self.__registers[POWERCFG] = reg;
        self.__writeregisters();
        self.__waitforset()
  
    def setmono(self, state):
        self.mono = state
        self.__readregisters()
        if state == True:
            self.__registers[POWERCFG] |= (1 << SETMONO) # set force mono bit
        else:
            self.__registers[POWERCFG] &= ~(1 << SETMONO) # clear force mono bit
        self.__writeregisters()

    def setmute(self, state):
        self.__readregisters()
        if state == True:
            self.__registers[POWERCFG] &= ~(1 << DMUTE) # clear mute bit
        else:
            self.__registers[POWERCFG] |= (1 << DMUTE)  # set mute bit
        self.__writeregisters()

    def setsoftmute(self, state):
        self.__readregisters()
        if state == True:
            self.__registers[POWERCFG] &= ~(1 << DSMUTE) # clear mute bit
        else:
            self.__registers[POWERCFG] |= (1 << DSMUTE)  # set mute bit
        self.__writeregisters()

    def setrdsverbose(self, state):
        self.__readregisters()
        if state == True:
            self.__registers[POWERCFG] |= (1 << RDSM) 
        else:
            self.__registers[POWERCFG] &= ~(1 << RDSM) 
        self.__writeregisters()

    def getrdsstate(self):
        if (self.__registers[STATUSRSSI] & (RDSS)):
            return True
        else:
            return False

    def getrssi(self):
        return self.__registers[STATUSRSSI] & RSSI

    def __waitforset(self):
        #Poll to see if STC is set
        while True:
            self.__readregisters()
            if((self.__registers[STATUSRSSI] & STC) != 0):
                break       #tuning complete
        self.__readregisters()

        # end the seek mode
        self.__registers[POWERCFG] &= ~(1 << SEEK)
        self.__registers[CHANNEL]  &= ~(1 << TUNE) #Clear the tune after a tune has completed
        self.__writeregisters()

    def rds_init(self):
        self.__psname1 = [0] * 10
        self.__psname2 = [0] * 10
        self.__rtext   = [0] * 66
        self.__lasttextab = 0
        self.__lasttextidx = 0
        self.__lastRDSMinutes = 0

    def rds_setcallback(self, psname=None, text=None, time=None):
        self.send_psname = psname   # func(psname)
        self.send_rdstext = text    # func(text)
        self.send_rdstime = time    # func(hours, mins)

    def rds_interruptcall(self, ch):
        print("CALL INT")
        self.__readregisters()
        self.rds_process(self.__registers[RDSA], self.__registers[RDSB], 
                         self.__registers[RDSC], self.__registers[RDSD])

    def rds_setinterrupt(self):
        self.__readregisters()
        self.__registers[SYSCONFIG1] |= (1 << RDSIEN)
        self.__registers[SYSCONFIG1] |= (1 << GPIO2)
        self.__writeregisters()
        GPIO.setup(self.rdsINT, GPIO.IN)
        GPIO.add_event_detect(self.rdsINT, GPIO.FALLING, callback=self.rds_interruptcall) 


    def rds_check(self):
        self.__readregisters()
        # check for a RDS data set ready
        if self.__registers[STATUSRSSI] & RDSR: 
            self.rds_process(self.__registers[RDSA], self.__registers[RDSB], 
                             self.__registers[RDSC], self.__registers[RDSD])
            return True
        else: 
            return False

    def rds_process(self, block1, block2, block3, block4):
        # reset all rds info
        if block1 == 0:
            self.rds_init()
            # send empty data
            self.send_psname(str(self.__psname1))
            self.send_rdstext(str(self.__rtext))
            return 
        
        # analyze Block 2
        rdsgrouptype = 0x0A | ((block2 & 0xF000) >> 8) | ((block2 & 0x0800) >> 11)
        rdsTP = (block2 & 0x0400)
        rdsPTY = (block2 & 0x0400)

        if rdsgrouptype == 0x0A or rdsgrouptype == 0x0B:
            # The data received is part of the Service Station Name 
            idx = 2 * (block2 & 0x0003)

            # new data is 2 chars from block 4
            c1 = block4 >> 8
            c2 = block4 & 0x00FF

            # check that the data was received successfully twice
            # before publishing the station name
            if self.__psname1[idx] == c1 and self.__psname1[idx + 1] == c2:
                self.__psname2[idx] = c1
                self.__psname2[idx + 1] = c2
                if (idx == 6 and self.__psname1 == self.__psname2
                    and self.send_psname != None):
                    self.send_psname("".join([chr(z) for z in self.__psname2]))    # <<< publish station name

            if self.__psname1[idx] != c1 or self.__psname1[idx + 1] != c2:
                self.__psname1[idx] = c1
                self.__psname1[idx + 1] = c2
        
        elif rdsgrouptype == 0x2A:
            textab = (block2 & 0x0010)
            idx = 4 * (block2 & 0x000F)

            # the existing text might be complete because the index is starting at the beginning again.
            # now send it to the possible listener.
            if idx < self.__lasttextidx and self.send_rdstext != None:
                self.send_rdstext("".join([chr(z) for z in self.__rtext])) # <<<<<<<<<
            self.__lasttextidx = idx

            if textab != self.__lasttextab:
                self.__lasttextab = textab
                self.__rtext = [0] * 66 

            # new data is 2 chars from block 3
            self.__rtext[idx] = (block3 >> 8)
            idx += 1
            self.__rtext[idx] = (block3 & 0x00FF)
            idx += 1

            # new data is 2 chars from block 4
            self.__rtext[idx] = (block4 >> 8)
            idx += 1
            self.__rtext[idx] = (block4 & 0x00FF)
            idx += 1

        elif rdsgrouptype == 0x4A:
            # Clock time and date
            off = (block4) & 0x3F           # 6 bits
            mins = (block4 >> 6) & 0x3F     # 6 bits
            mins += 60 * (((block3 & 0x0001) << 4) | ((block4 >> 12) & 0x0F))

            # adjust offset
            if off & 0x20:
                mins -= 30 * (off & 0x1F)
            else:
                mins += 30 * (off & 0x1F)
            
            if self.send_rdstime != None and mins != self.__lastRDSMinutes:
                self.__lastRDSMinutes = mins
                self.send_rdstime(mins // 60, mins % 60)  #  <<<<<<<

        """
        elif rdsgrouptype == 0x6A:
            pass     # IH   
        elif rdsgrouptype == 0x8A:
            pass     # TMC
        elif rdsgrouptype == 0xAA:
            pass    # TMC
        elif rdsgrouptype == 0xCA:
            pass    # TMC
        elif rdsgrouptype == 0xEA:
            pass    # IH
        """
        
    def __readregisters(self):
        # Si4703 begins reading from register upper register of 0x0A and reads to 0x0F, then loops to 0x00.
        # SMBus requires an "address" parameter even though the 4703 doesn't need one
        # Need to send the current value of the upper byte of register 0x02 as command byte
        i2cread = [0] * 32
        cmdbyte = self.__registers[0x02] >> 8

        i2cread = self.i2cbus.read_i2c_block_data(self.i2caddr, cmdbyte, 32)
        regindex = 0x0A
        
        #Remember, register 0x0A comes in first so we have to shuffle the array around a bit
        for i in range(16):
            self.__registers[regindex] = (i2cread[i * 2] * 256) + i2cread[(i * 2) + 1]
            regindex += 1
            if regindex == 0x10:
                regindex = 0        


    def __writeregisters(self):
	# A write command automatically begins with register 0x02 so no need to send a write-to address
        # First we send the 0x02 to 0x07 control registers. We should not write to registers 0x08 and 0x09
        
        # only need a list that holds 0x02 - 0x07: 6 words or 12 bytes
        i2cwrite = [0] * 12
        # move the shadow copy into the write buffer
        for i in range(6):
            i2cwrite[i * 2], i2cwrite[(i * 2) + 1] = divmod(self.__registers[i+2], 0x100)

        # the "address" of the SMBUS write command is not used on the si4703 - need to use the first byte
        self.i2cbus.write_i2c_block_data(self.i2caddr, i2cwrite[0], i2cwrite[1:11])

if __name__ == "__main__":
    fm = FMSi4703()
    fm.poweron()
    volume = 12
    fm.setvolume(volume)
    fm.setfrequency(10180)

    fm.rds_setcallback(psname=print, text=print, time=print)

    while True:
        print(GPIO.input(fm.rdsINT))
        time.sleep(0.1)
    fm.shutdown()
    """
    try:
        while True:
                 
            key = input(">>>")
            if key == "q":
                raise KeyboardInterrupt
            elif key == "u":
                fm.seekup()
                print("FREQUENCY: %d" % fm.getfrequency())
            elif key == "d":
                fm.seekdown()
                print("FREQUENCY: %d" % fm.getfrequency())
            elif key == "+":
                volume += 1
                fm.setvolume(volume)
                print("VOLUME   : %d" % fm.getvolume())
            elif key == "-":
                volume -= 1
                fm.setvolume(volume)
                print("VOLUME   : %d" % fm.getvolume())

            fm.rds_check()
            time.sleep(.3)
    except KeyboardInterrupt:
        fm.shutdown()
     """
