# GUI FM Radio SI4703 app 
Application created primarily for Raspberry Pi 3 (You can adapt it for
other versions). It uses PySide (QT) to achieve native look even though 
realistically you cannot run it anywhere else. Hardware acess is done with
smbus (for I2C) and RPi.GPIO, by default project use BCM pin 5 for Radio 
RST.


### Build and run
Run: 
```bash
python3 setup.py install
```
If that doesn't work you can install requirements manually and run
`radiogui/fmgui.py` in the interpreter


### Sceenshots
![alt text](https://github.com/https://github.com/etakerim/fmradio-rpi3qt/tree/master/assets/sshscreenshot.png
"Log on Raspberry Pi through SSH")
