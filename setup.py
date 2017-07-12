from setuptools import setup, find_packages

setup(
    name="FMRadioApp",
    version="0.1",
    packages=find_packages(),
    install_requires=["smbus-cffi>=0.5.1", "RPi.GPIO>=0.6.2"],

    author="Miroslav Hájek",
    author_email="mirkousko@gmail.com",
    description="GUI application for Si4703 FM radio",
    licence="GNU GPLv2.0"
)
