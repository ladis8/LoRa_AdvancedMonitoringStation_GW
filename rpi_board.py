#import wiringpi
import time
import logging
from RPLCD import CharLCD
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

    SPI = None


    def __init__(self):
        self.io_setup()
        #self.lcd = CharLCD(cols = 16, rows = 2, pin_rs = 33, pin_e = 35, pins_data=[37, 36, 40, 38], numbering_mode=GPIO.BCM)
        #self.lcd.write_string(u"LoRa node id=5 connected!")


    @staticmethod
    def io_setup():
        #wiringpi.wiringPiSetup()
        #wiringpi.wiringPiSPISetup(SPI_channel, SPI_speed)
        #wiringpi.pinMode(dio0_pin, 0)
        #wiringpi.pinMode(RST_pin, 1)
        GPIO.setmode(GPIO.BCM)
        #SPI
        RPI_BOARD.spi_setup()
        # LED
        GPIO.setup(RPI_BOARD.LED, GPIO.OUT)
        GPIO.output(RPI_BOARD.LED, 0)
        GPIO.setup(RPI_BOARD.DIO0, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        #RST, DIO
        GPIO.setup(RPI_BOARD.RST, GPIO.OUT)
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
        #return wiringpi.digitalRead(pin)

    @staticmethod
    def pin_reset(pin):
        #wiringpi.digitalWrite(pin, 1)
        RPI_BOARD.pin_write(pin, 1)
        time.sleep(0.1)
        #wiringpi.digitalWrite(pin, 0)
        RPI_BOARD.pin_write(pin, 0)
        time.sleep(0.1)


    @staticmethod
    def SPI_write_buffer(reg_addr, buffer):
        if type(buffer) is str:
            buffer = list(map(ord, buffer))
        if reg_addr > 0xFF or any(el > 0xFF for el in buffer):
            logging.error("Address not within range or values overflow")
        reg_addr |= 0x80
        RPI_BOARD.SPI.xfer2([reg_addr] + buffer)[1]

    @staticmethod
    def SPI_read_buffer(reg_addr, length):
        if reg_addr > 0xFF:
            logging.error("Address not within range")
            return None
        reg_addr &= 0x7F
        return RPI_BOARD.SPI.xfer2([reg_addr] + [0x00] * length)

    @staticmethod
    def SPI_write_register(reg_addr, value):
        if reg_addr > 0xFF or value > 0xFF:
            logging.error("Address not within range or values overflow")
        reg_addr |= 0x80
        RPI_BOARD.SPI.xfer([reg_addr, value])[1]

    @staticmethod
    def SPI_read_register(reg_addr):
        if reg_addr > 0xFF:
            logging.error("Address not within range")
            return None
        reg_addr &= 0x7F
        return RPI_BOARD.SPI.xfer([reg_addr, 0x00])




    def SPI_read_register_deprecated(self, addr):
        if addr > 0xFF:
            logging.error("SPI writes only one byte")
            return -1
        #wiringpi.digitalWrite(ss_pin, 1)
        addr &= 0x7F
        buf = bytes([addr, 0x00])
        retlen, retdata = wiringpi.wiringPiSPIDataRW(SPI_channel, buf)
        #logging.debug("RetData = 0x%s(hex), %s(dec), len %d",
        #              "".join("{:02X}".format(i) for i in retdata),
        #              "".join(str(i) + " " for i in retdata),
        #              retlen)
        #wiringpi.digitalWrite(ss_pin, 0)
        return retdata

    def SPI_write_register_deprecated(self, addr, val):
        if addr > 0xFF or val > 0xFF:
            logging.error("SPI writes only one byte")

        #wiringpi.digitalWrite(ss_pin, 1)
        addr |= 0x80
        buf = bytes([addr, val])
        retlen, retdata = wiringpi.wiringPiSPIDataRW(SPI_channel, buf)
        #logging.debug("RetData = 0x%s(hex), %s(dec), len %d",
        #              "".join("{:02X}".format(i) for i in retdata),
        #              "".join(str(i) + " " for i in retdata),
        #              retlen)
        #wiringpi.digitalWrite(ss_pin, 0)

    #takes buffer in bytes or array of values
    def SPI_write_buffer_deprecated(self, addr, buffer):
        if addr > 0xFF:
            logging.error("Address not within range")
        addr |= 0x80
        buffer = bytes([addr]) + bytes(buffer)
        retlen, retdata = wiringpi.wiringPiSPIDataRW(SPI_channel, buffer)




