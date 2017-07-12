#TODO  Štýly - lepší výzor
#      RDS - cez INT
import sys
import os
import fmsi4703
from PySide.QtGui import (QWidget, QMainWindow, QLabel, QPushButton, QVBoxLayout,
                          QHBoxLayout, QSlider, QIcon, QPixmap, QFont, QApplication) 
from PySide.QtCore import Qt, QTimer


dev_radio = fmsi4703.FMSi4703()
script_path = os.path.dirname(os.path.realpath(__file__)) 

def map_range(oldval, oldmin, oldmax, newmin, newmax):
    oldrange = (oldmin - oldmax)  
    newrange = (newmin - newmax)  
    return (((oldval - oldmin) * newrange) / oldrange) + newmin

class RadioApp(QWidget):
    
    def __init__(self):
        super().__init__()
        self.edit = False

        self.left_dock_create()
        self.middle_dock_create()
        self.right_dock_create()
        self.slotans_create()

        self.box = QHBoxLayout()
        self.box.addLayout(self.volbalayout)
        self.box.addLayout(self.middlelayout)
        self.box.addLayout(self.rightlayout)
        
        self.mainlayout = QVBoxLayout()
        self.mainlayout.addLayout(self.box)
        self.setLayout(self.mainlayout)
    

    def left_dock_create(self):
        self.statlabel = QLabel("RSSI: --")
        self.logolabel = QLabel()
        self.logolabel.setPixmap(QPixmap(os.path.join(script_path, "../assets/logo.png")))
        self.statlabel.setFont(QFont("DejaVu Sans", 12))
        
        self.btnvolba = []
        for i in range(1,5):
            self.btnvolba.append(QPushButton("Voľba {}".format(i)))
            
        self.presetaddbtn = QPushButton()
        self.presetaddbtn.setIcon(QIcon(QPixmap("../assets/add.png")))
        
        self.volbalayout = QVBoxLayout()
        self.volbalayout.addWidget(self.logolabel)
        self.volbalayout.addWidget(self.statlabel)
        for btn in self.btnvolba:
            self.volbalayout.addWidget(btn)
        self.volbalayout.addWidget(self.presetaddbtn)
        

    def middle_dock_create(self):
        self.frekv = QLabel()
        self.frekv.setFont(QFont("DejaVu Sans", 26))
        self.write_frekv()

        self.btnstepleft = QPushButton("<")
        self.btnseekdown = QPushButton("<<")
        self.btnseekup = QPushButton(">>")
        self.btnstepright = QPushButton(">")
        
        self.laybtnmv = QHBoxLayout()
        self.laybtnmv.addWidget(self.btnseekdown)
        self.laybtnmv.addWidget(self.btnstepleft)
        self.laybtnmv.addWidget(self.btnstepright)
        self.laybtnmv.addWidget(self.btnseekup)
       
        self.labelrdsdt = QLabel("RDS")
        self.labelrdsdt.setFont(QFont("DejaVu Sans", 12))
       
        self.frekvlayout = QHBoxLayout()
        self.frekvlayout.addWidget(self.frekv)
        self.frekvlayout.setAlignment(Qt.AlignCenter)
        
        self.middlelayout = QVBoxLayout()
        self.middlelayout.addLayout(self.frekvlayout)
        self.middlelayout.addLayout(self.laybtnmv)
        self.middlelayout.addWidget(self.labelrdsdt)


    def right_dock_create(self):
        self.btnonoff = QPushButton("Reset")
        self.slidvol = QSlider(Qt.Vertical)
        self.slidvol.setMinimum(0)
        self.slidvol.setMaximum(100)
        self.slidvol.setValue(50)
        self.labspeaker = QLabel()
        self.labspeaker.setPixmap(QPixmap(os.path.join(script_path, "../assets/speaker.png")))
        self.sndvolumelabel = QLabel()

        self.rightlayout = QVBoxLayout()
        self.rightlayout.addWidget(self.btnonoff)
        self.rightlayout.addWidget(self.slidvol)
        self.rightlayout.addWidget(self.sndvolumelabel)
        self.rightlayout.addWidget(self.labspeaker)

    def slotans_create(self):
        self.slidvol.valueChanged.connect(self.set_radiovolume)
        self.btnstepleft.clicked.connect(lambda: self.step_frekv("d"))
        self.btnstepright.clicked.connect(lambda: self.step_frekv("u"))
        self.btnseekdown.clicked.connect(lambda: self.set_seek("d"))
        self.btnseekup.clicked.connect(lambda: self.set_seek("u"))
        
        self.presetaddbtn.clicked.connect(self.preset_editmode)
        self.btnonoff.clicked.connect(self.reset_radio)
        for btn in self.btnvolba:
            btn.clicked.connect(self.preset_choose)
        self.timerrssi = QTimer()
        self.timerrssi.timeout.connect(self.write_stats)
        self.timerrssi.start(3000) # ms

    def reset_radio(self):
        dev_radio.shutdown()
        dev_radio.poweron()

    def preset_editmode(self):
        if self.edit == True:
            # Chceme sa vrátiť do normálneho režimu -> zvrátime editačný
            for btn in self.btnvolba:
                btn.setStyleSheet("")
                btn.clicked.disconnect()
                btn.clicked.connect(self.preset_choose)
        else:
            # Vstupujeme do editačného režimu
            for btn in self.btnvolba:
                btn.setStyleSheet("background-color: #30f030;")
                btn.clicked.disconnect()
                btn.clicked.connect(self.preset_set)
        self.edit = not self.edit
    
    def preset_set(self):
        button = self.sender()
        if isinstance(button, QPushButton):
            button.setText("{:.2f}".format(dev_radio.getfrequency() / 100))
            self.preset_editmode()

    def preset_choose(self):        
        button = self.sender()
        if isinstance(button, QPushButton):
            try:
                frekv = int(float(button.text()) * 100)
            except ValueError:
                return
            dev_radio.setfrequency(frekv)
            self.write_frekv()

    def preset_save(self):
        with open("preset.txt", mode="w") as fw:
            for btn in self.btnvolba:
                try:
                    fw.write("{},".format(int(float(btn.text()) * 100)))
                except ValueError:
                    fw.write(" ,")

    def preset_restore(self):
        try:
            fr = open("preset.txt", mode="r")
            pres_list = fr.read().split(",")
        except FileNotFoundError:
            return
        
        fr.close()
        if len(pres_list) - 1 < len(self.btnvolba):
            print("Chyba: Zoznam predvolieb je krátky")
            return

        for i, btn in enumerate(self.btnvolba):
            try:
                btn.setText("{:.2f}".format(int(pres_list[i])/100))
            except ValueError:
                continue

    def set_seek(self, direction):
        if direction == "u":
            dev_radio.seekup()
        elif direction == "d":
            dev_radio.seekdown()
        self.write_frekv()

    def step_frekv(self, direction):
        curr_frekv = dev_radio.getfrequency()
        if direction == "u":
            curr_frekv += 10
            if curr_frekv > dev_radio.freqhigh:
                curr_frekv = dev_radio.freqlow
        elif direction == "d":
            curr_frekv -= 10
            if curr_frekv < dev_radio.freqlow:
                curr_frekv = dev_radio.freqhigh
        dev_radio.setfrequency(curr_frekv)
        self.write_frekv()    

    def write_frekv(self): 
        self.frekv.setText("<b>{:.2f} MHz</b>".format(dev_radio.getfrequency() / 100))

    def write_stats(self):
        self.statlabel.setText("<b>RSSI: {}</b>".format(dev_radio.getrssi()))

    def set_radiovolume(self):
        vol_percent = self.slidvol.value()
        self.sndvolumelabel.setText("{}%".format(vol_percent))
        new_volume = int(map_range(vol_percent, 0, 100, 0, 15))
        dev_radio.setvolume(new_volume)    
    
    def rds_psshow(self, station):
        print("Stanica: {}".format(station))

    def rds_txtshow(self, text):
        print("Text: {}".format(text))

    def rds_tmshow(self, hodiny, minuty):
        print("{}:{}".format(hodiny, minuty))


class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FM Rádio")
        self.setMinimumSize(400, 250)
        self.app = RadioApp()
        self.setCentralWidget(self.app)
        self.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    okno = MyWindow()
    dev_radio.poweron()
    dev_radio.setfrequency(10180)
    dev_radio.rds_setcallback(psname=okno.app.rds_psshow, 
                              text=okno.app.rds_txtshow,
                              time=okno.app.rds_tmshow)
    okno.app.write_frekv()
    okno.app.set_radiovolume()
    okno.app.preset_restore()

    app.exec_()
    okno.app.preset_save()
    dev_radio.shutdown()
    sys.exit()
