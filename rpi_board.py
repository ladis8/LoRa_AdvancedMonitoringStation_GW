"""
\file       rpi_board.py
\author     Ladislav Stefka
\brief      API for handling Raspberry Pi hardware 
            - defines GPIO pins operations
            - defines SPI operations
\copyright
"""

#import wiringpi
import time
import logging
import RPi.GPIO as GPIO
import spidev

SPI_speed = 500000
SPI_channel = 0
SPI_bus = 0




class RPI_BOARD:

    # ss_pin = 6
    #dio0_pin = 7  # BCM 4
    #RST_pin = 0

    DIO0 = 4
    DIO1 = 27
    DIO3 = 22
    RST = 17
    LED = 18
    NSS = 25

    SPI = None


    def __init__(self):
        self.io_setup()

    def clean(self):
        GPIO.cleanup()


    @staticmethod
    def io_setup():
        GPIO.setmode(GPIO.BCM)
        #SPI
        RPI_BOARD.spi_setup()
        # LED
        GPIO.setup(RPI_BOARD.LED, GPIO.OUT)
        GPIO.output(RPI_BOARD.LED, 0)
        GPIO.setup(RPI_BOARD.DIO0, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        #RST, DIO
        GPIO.setup(RPI_BOARD.RST, GPIO.OUT)
        GPIO.setup(RPI_BOARD.NSS, GPIO.OUT)
        GPIO.setup(RPI_BOARD.DIO0, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(RPI_BOARD.DIO1, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(RPI_BOARD.DIO3, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    @staticmethod
    def spi_setup():
        RPI_BOARD.SPI = spidev.SpiDev()
        RPI_BOARD.SPI.open(SPI_bus, SPI_channel)
        RPI_BOARD.SPI.max_speed_hz = SPI_speed  # SX127x can go up to 10MHz, pick half that to be safe

    @staticmethod
    def add_irq_handlers(dio0_irq_handler=None, dio1_irq_handler=None, dio3_irq_handler=None):
        if dio0_irq_handler is not None:
            try:
                GPIO.remove_event_detect(RPI_BOARD.DIO0)
            finally:
                GPIO.add_event_detect(RPI_BOARD.DIO0, GPIO.RISING, callback=dio0_irq_handler)

        if dio1_irq_handler is not None:
            try:
                GPIO.remove_event_detect(RPI_BOARD.DIO1)
            finally:
                GPIO.add_event_detect(RPI_BOARD.DIO1, GPIO.RISING, callback=dio1_irq_handler)

        if dio3_irq_handler is not None:
            try:
                GPIO.remove_event_detect(RPI_BOARD.DIO3)
            finally:
                GPIO.add_event_detect(RPI_BOARD.DIO3, GPIO.RISING, callback=dio3_irq_handler)

    @staticmethod
    def pin_write (pin, value):
        GPIO.output(pin, value)

    @staticmethod
    def pin_read (pin):
        return GPIO.input(pin)

    @staticmethod
    def pin_reset(pin):
        RPI_BOARD.pin_write(pin, 1)
        time.sleep(0.1)
        RPI_BOARD.pin_write(pin, 0)
        time.sleep(0.1)

    @staticmethod
    def pin_reset_inverse(pin):
        RPI_BOARD.pin_write(pin, 0)
        time.sleep(0.1)
        RPI_BOARD.pin_write(pin, 1)
        time.sleep(0.1)




    @staticmethod
    def SPI_write_buffer(reg_addr, buffer):
        if type(buffer) is str:
            buffer = list(map(ord, buffer))
        if reg_addr > 0xFF or any(el > 0xFF for el in buffer):
            logging.error("Address not within range or values overflow")

        RPI_BOARD.pin_write(RPI_BOARD.NSS, 0)
        reg_addr |= 0x80
        RPI_BOARD.SPI.xfer2([reg_addr] + buffer)[1]
        RPI_BOARD.pin_write(RPI_BOARD.NSS, 1)

    @staticmethod
    def SPI_read_buffer(reg_addr, length):
        if reg_addr > 0xFF:
            logging.error("Address not within range")
            return None
        RPI_BOARD.pin_write(RPI_BOARD.NSS, 0)
        reg_addr &= 0x7F
        ret = RPI_BOARD.SPI.xfer2([reg_addr] + [0x00] * length)
        RPI_BOARD.pin_write(RPI_BOARD.NSS, 1)
        return ret

    @staticmethod
    def SPI_write_register(reg_addr, value):
        if reg_addr > 0xFF or value > 0xFF:
            logging.error("Address not within range or values overflow")
        RPI_BOARD.pin_write(RPI_BOARD.NSS, 0)
        reg_addr |= 0x80
        RPI_BOARD.SPI.xfer([reg_addr, value])[1]
        RPI_BOARD.pin_write(RPI_BOARD.NSS, 1)

    @staticmethod
    def SPI_read_register(reg_addr):
        if reg_addr > 0xFF:
            logging.error("Address not within range")
            return None
        RPI_BOARD.pin_write(RPI_BOARD.NSS, 0)
        reg_addr &= 0x7F
        ret = RPI_BOARD.SPI.xfer([reg_addr, 0x00])
        RPI_BOARD.pin_write(RPI_BOARD.NSS, 1)
        return ret



