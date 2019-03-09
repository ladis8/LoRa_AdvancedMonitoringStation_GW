#TODO: Read version
#TODO: Refactor set_mode

#works only in LoRa mode

from enum import Enum
import datetime

from rpi_board import *
from tools import *

RSSI_COOR = 139

class REG_LORA:
    FIFO = 0x00
    OP_MODE = 0x01
    #frequency select
    FR_MSB = 0x06
    FR_MID = 0x07
    FR_LSB = 0x08

    PA_CONFIG = 0x09
    PA_RAMP = 0x0A
    OCP = 0x0B
    LNA = 0x0C

    FIFO_ADDR_PTR = 0x0D
    FIFO_TX_BASE_ADDR = 0x0E
    FIFO_RX_BASE_ADDR = 0x0F
    FIFO_RX_CURR_ADDR = 0x10

    IRQ_FLAGS_MASK = 0x11
    IRQ_FLAGS = 0x12
    RX_NB_BYTES = 0x13
    RX_HEADER_CNT_MSB = 0x14
    RX_PACKET_CNT_MSB = 0x16
    MODEM_STAT = 0x18
    PKT_SNR_VALUE = 0x19
    PKT_RSSI_VALUE = 0x1A
    RSSI_VALUE = 0x1B
    HOP_CHANNEL = 0x1C
    MODEM_CONFIG_1 = 0x1D
    MODEM_CONFIG_2 = 0x1E
    SYMB_TIMEOUT_LSB = 0x1F
    PREAMBLE_MSB = 0x20
    PAYLOAD_LENGTH = 0x22
    MAX_PAYLOAD_LENGTH = 0x23
    HOP_PERIOD = 0x24
    FIFO_RX_BYTE_ADDR = 0x25
    MODEM_CONFIG_3 = 0x26
    PPM_CORRECTION = 0x27
    FEI_MSB = 0x28
    DETECT_OPTIMIZE = 0X31
    INVERT_IQ = 0x33
    DETECTION_THRESH = 0X37
    SYNC_WORD = 0X39
    DIO_MAPPING_1 = 0x40
    DIO_MAPPING_2 = 0x41
    VERSION = 0x42
    TCXO = 0x4B
    PA_DAC = 0x4D
    AGC_REF = 0x61
    AGC_THRESH_1 = 0x62
    AGC_THRESH_2 = 0x63
    AGC_THRESH_3 = 0x64
    PLL = 0x70

#8 for LoRa mode
class MODE (Enum):
    SLEEP    = 0x80
    STDBY    = 0x81
    FSTX     = 0x82
    TX       = 0x83
    FSRX     = 0x84
    RXCONT   = 0x85
    RXSINGLE = 0x86
    CAD      = 0x87

class BW (Enum):
    BW7_8   = 0
    BW10_4  = 1
    BW15_6  = 2
    BW20_8  = 3
    BW31_25 = 4
    BW41_7  = 5
    BW62_5  = 6
    BW125   = 7
    BW250   = 8
    BW500   = 9


class CODING_RATE (Enum):
    CR_ERROR = 0
    CR4_5 = 1
    CR4_6 = 2
    CR4_7 = 3
    CR4_8 = 4


#LOW NOISE AMPLIFIER
LNA_MAX_GAIN =               0x23
LNA_OFF_GAIN =               0x00
LNA_LOW_GAIN =		    	0x20





def getter(register_address):
    """ The getter decorator reads the register content and calls the decorated function to do
        post-processing.
    :param register_address: Register address
    :return: Register value
    :rtype: int
    """
    def decorator(func):
        def wrapper(self):
            return func(self, self.rpi_board.SPI_read_register(register_address))
        return wrapper
    return decorator


def setter(register_address):
    """ The setter decorator calls the decorated function for pre-processing and
        then writes the result to the register
    :param register_address: Register address
    :return: New register value
    :rtype: int
    """
    def decorator(func):
        def wrapper(self, val):
            return self.rpi_board.SPI_write_register(register_address, func(self, val))
        return wrapper
    return decorator

class SX1272_Module:

    def __init__(self, rpi_board):
        self.rpi_board = rpi_board
        self.mode = None
        self.received_packets = 0
        self.received_packets_ok = 0

    def SX1272_is_alive(self):

        #check version
        version = self.get_version()
        assert version == 0x22
        logging.debug("SX1272 detected...")

    def SX1272_module_setup(self, config):

        #reset lora module
        self.rpi_board.pin_reset(self.rpi_board.RST)

        #set sleepmode
        self.SX1272_set_mode(MODE.SLEEP)


        #set frequency
        self.SX1272_set_frequency(config["freq"])
        freq_a = self.SX1272_get_frequency()
        logging.debug("Frequency set up: %d MHz", freq_a)

        #set config
        self.SX1272_set_modem_config1(config["bandwidth"], config["coding_rate"], config["implicit_header_mode"], config["rx_crc"], config["lr_optimize"])
        self.SX1272_set_modem_config2(spreading_factor=config["spreading_factor"], tx_cont_mode=config["tx_cont_mode"])

        #set timout
        #self.SX1272_set_symb_timeout(config["symbol_timeout"])

        #set sync word
        self.SX1272_set_syncword(config["sync_word"])
        self.SX1272_set_max_payload_length(config["max_payload_len"])
        self.SX1272_set_payload_length(config["payload_len"])
        self.SX1272_set_hop_period(config["hop_period"])

        #set pointer addr
        self.rpi_board.SPI_write_register(REG_LORA.FIFO_ADDR_PTR, self.rpi_board.SPI_read_register(REG_LORA.FIFO_RX_BASE_ADDR)[1])

        #set amplifier gain
        self.rpi_board.SPI_write_register(REG_LORA.LNA, LNA_MAX_GAIN)  #max lna gain

        print(self)



    def read_rx_payload(self):
            current_addr = self.rpi_board.SPI_read_register(REG_LORA.FIFO_RX_CURR_ADDR)[1]
            received_bytes = self.rpi_board.SPI_read_register(REG_LORA.RX_NB_BYTES)[1]
            self.rpi_board.SPI_write_register(REG_LORA.FIFO_ADDR_PTR, current_addr)
            return self.rpi_board.SPI_read_buffer(REG_LORA.FIFO, received_bytes)[1:received_bytes+1]

    #In RX_CONTINUOUS mode RX Timout flag is never rised
    def set_rx_continuous(self, rx_done_handler):

        if self.mode == MODE.RXCONT:
            return

        assert self.mode == MODE.STDBY or self.mode == MODE.SLEEP
        print("\nSetting rx...")
        self.SX1272_set_dio1_mapping(dio0=0, dio3=3)
        self.rpi_board.add_irq_handlers(dio0_irq_handler=rx_done_handler)
        #self.SX1272_set_symb_timeout(timeout)

        #set mode
        self.SX1272_set_mode(MODE.RXCONT)

        #timestamp = datetime.datetime.now().replace(microsecond=0)
        #time_start = time.time()
        # while time.time() - time_start < timeout:
        #     if self.rpi_board.pin_read(self.rpi_board.DIO0):
        #         logging.info("%s : Receiver active...", timestamp)
        #         self.received_packets += 1
        #         payload = self.check_packet()
        #
        #         if payload is not None:
        #             self.received_packets_ok += 1
        #             paket_SNR = self.get_paket_snr_value()
        #             paket_RSII = self.get_packet_rssi_value()
        #             RSII = self.SX1272_get_rsii_value()
        #             #logging.info("Packet CRC OK: SNR= %s, packet RSII= %s, RSII= %s, length = %d, message = %s",
        #             #             paket_SNR, paket_RSII, RSII, len(payload), "".join(chr(char) for char in payload) )
        #             logging.info("Packet CRC OK: SNR= %s, packet RSII= %s, RSII= %s, length = %d, message = %s",
        #                          paket_SNR, paket_RSII, RSII, len(payload), bytes(payload))
        #             return payload
        #
        #         time.sleep(0.001)
        # logging.debug("%s: Receiver inactive, timeout expired...", timestamp)
        # return None

    #TODO: CAD check
    def set_tx(self, tx_done_handler, radio_packet):
        print("\nSetting tx...")
        assert len(radio_packet) < 256
        self.SX1272_set_dio1_mapping(dio0=1, dio1=0, dio3=3)
        self.rpi_board.add_irq_handlers(dio0_irq_handler=tx_done_handler)
        self.rpi_board.SPI_write_register(REG_LORA.PAYLOAD_LENGTH, len(radio_packet))
        self.rpi_board.SPI_write_register(REG_LORA.FIFO_TX_BASE_ADDR, 0)
        self.rpi_board.SPI_write_register(REG_LORA.FIFO_ADDR_PTR, 0)

        #set mode
        self.SX1272_set_mode(MODE.STDBY)
        self.rpi_board.SPI_write_buffer(REG_LORA.FIFO, list(radio_packet.rawdata))

        #set mode for TX
        self.SX1272_set_mode(MODE.TX)
        logging.debug("Transmit packet prepared for sending...")

    def send_packet_deprecated(self, payload):

        assert len(payload) < 256
        #SX1272Write(REG_LR_PAYLOADLENGTH, size);
        self.rpi_board.SPI_write_register(REG_LORA.PAYLOAD_LENGTH, len(payload))
        #SX1272Write(REG_LR_FIFOTXBASEADDR, 0);
        #SX1272Write(REG_LR_FIFOADDRPTR, 0);
        self.rpi_board.SPI_write_register(REG_LORA.FIFO_TX_BASE_ADDR, 0)
        self.rpi_board.SPI_write_register(REG_LORA.FIFO_ADDR_PTR, 0)

        #if ((SX1272Read(REG_OPMODE) & ~RF_OPMODE_MASK) == RF_OPMODE_SLEEP){SX1272SetStby();

        if self.mode == MODE.SLEEP:
            self.SX1272_set_mode(MODE.STDBY.value)
            self.mode = MODE.STDBY

        #SX1272WriteFifo(buffer, size);
        self.rpi_board.SPI_write_buffer(REG_LORA.FIFO, payload)
        #SX1272Write(REG_DIOMAPPING1,(SX1272Read(REG_DIOMAPPING1) & RFLR_DIOMAPPING1_DIO0_MASK) | RFLR_DIOMAPPING1_DIO0_01);
        #SX1272SetOpMode(RF_OPMODE_TRANSMITTER);

        #!!! set txDone as dio0
        self.SX1272_set_dio1_mapping(dio0=1)
        self.SX1272_set_mode(MODE.TX.value)
        self.mode = MODE.TX
        logging.debug("Transmit packet prepared for sending...")



    def reset_ptr_rx(self):
        self.SX1272_set_mode(MODE.STDBY)
        self.rpi_board.SPI_write_register(REG_LORA.FIFO_ADDR_PTR, self.rpi_board.SPI_read_register(REG_LORA.FIFO_RX_BASE_ADDR)[1])












    def SX1272_set_frequency(self, freq):
        assert self.mode == MODE.SLEEP or self.mode == MODE.STDBY or self.mode == MODE.FSK_STDBY
        freq = int(freq * 16384.)
        self.rpi_board.SPI_write_register(REG_LORA.FR_MSB, to_uint8t(freq >> 16))
        self.rpi_board.SPI_write_register(REG_LORA.FR_MID, to_uint8t(freq >> 8))
        self.rpi_board.SPI_write_register(REG_LORA.FR_LSB, to_uint8t(freq))

    def SX1272_get_frequency(self):
        msb = self.rpi_board.SPI_read_register(REG_LORA.FR_MSB)[1]
        mid = self.rpi_board.SPI_read_register(REG_LORA.FR_MID)[1]
        lsb = self.rpi_board.SPI_read_register(REG_LORA.FR_LSB)[1]
        f = lsb + 256 * (mid + 256 * msb)
        return f / 16384


    def SX1272_get_modem_config1(self):
        val = self.rpi_board.SPI_read_register(REG_LORA.MODEM_CONFIG_1)[1]
        d = dict(
            bandwidth=val >> 6 & 0x03,
            coding_rate=val >> 3 & 0x07,
            implicit_header_mode=val >> 2 & 0x01,
            rx_crc=val >> 1 & 0x01,
            lr_optimize=val & 0x01,
        )
        #print("modem config1 is ", val, d)
        return d

    def SX1272_set_modem_config1(self, bandwidth=None, coding_rate=None, implicit_header_mode=None, rx_crc=None, lr_optimize=None):
        var = locals()
        current = self.SX1272_get_modem_config1()
        new = {s: current[s] if var[s] is None else var[s] for s in var}
        val = new['lr_optimize'] | (new['rx_crc'] << 1) | (new['implicit_header_mode'] << 2) | (new['coding_rate'] << 3) | (new['bandwidth'] << 6)
        self.rpi_board.SPI_write_register(REG_LORA.MODEM_CONFIG_1, val)

    def SX1272_get_modem_config2(self, include_symb_timout_lsb=False):
        val = self.rpi_board.SPI_read_register(REG_LORA.MODEM_CONFIG_2)[1]
        d = dict(
            spreading_factor= val >> 4 & 0x0F,
            tx_cont_mode=val >> 3 & 0x01,
        )
        if include_symb_timout_lsb:
            d['symb_timout_lsb'] = val & 0x03
        #print("modem config2 is: ", val, d)
        return d

    def SX1272_set_modem_config2(self, spreading_factor=None, tx_cont_mode=None):
        var = locals()
        # RegModemConfig2 contains the SymbTimout MSB bits. We tack the back on when writing this register.
        current = self.SX1272_get_modem_config2(include_symb_timout_lsb=True)
        new = {s: current[s] if var[s] is None else var[s] for s in var}
        val = (new['spreading_factor'] << 4) | (new['tx_cont_mode'] << 3) | current['symb_timout_lsb']
        self.rpi_board.SPI_write_register(REG_LORA.MODEM_CONFIG_2, val)

    def SX1272_get_dio1_mapping(self):
        val = self.rpi_board.SPI_read_register(REG_LORA.DIO_MAPPING_1)[1]
        d = dict(
            dio0=val >> 6 & 0x03,
            dio1=val >> 4 & 0x03,
            dio2=val >> 2 & 0x03,
            dio3=val & 0x03,
        )
        return d

    def SX1272_set_dio1_mapping(self, dio0=0, dio1=0, dio2=0, dio3=0):
        assert dio0 < 4 and dio1 < 4 and dio2 < 4 and dio3 < 4
        var = locals()
        current = self.SX1272_get_dio1_mapping()
        new = {s: current[s] if var[s] is None else var[s] for s in var}
        val = (new['dio0'] << 6) | (new['dio1'] << 4) | (new['dio2'] << 2) | new['dio3']
        self.rpi_board.SPI_write_register(REG_LORA.DIO_MAPPING_1, val)


    def SX1272_get_symb_timeout(self):
        SYMB_TIMEOUT_MSB = REG_LORA.MODEM_CONFIG_2
        msb = self.rpi_board.SPI_read_register(SYMB_TIMEOUT_MSB)[1] & 0x3
        lsb = self.rpi_board.SPI_read_register(REG_LORA.SYMB_TIMEOUT_LSB)[1]
        return (msb << 8) | lsb

    def SX1272_set_symb_timeout(self, symb_timeout):
        SYMB_TIMEOUT_MSB = REG_LORA.MODEM_CONFIG_2
        confreg = self.rpi_board.SPI_read_register(REG_LORA.MODEM_CONFIG_2)[1]
        msb = symb_timeout >> 8 & 0b11  # bits 8-9
        lsb = symb_timeout - 256 * msb  # bits 0-7
        self.rpi_board.SPI_write_register(SYMB_TIMEOUT_MSB, confreg | msb)
        self.rpi_board.SPI_write_register(REG_LORA.SYMB_TIMEOUT_LSB, lsb)


    def SX1272_set_mode(self, mode):
        self.mode = mode
        self.rpi_board.SPI_write_register(REG_LORA.OP_MODE, mode.value)

    def SX1272_get_mode(self, assertion=True):
        if assertion:
            assert self.rpi_board.SPI_read_register(REG_LORA.OP_MODE)[1] == self.mode.value
        return self.mode.value


    def SX1272_get_irq_flags(self):
        v = self.rpi_board.SPI_read_register(REG_LORA.IRQ_FLAGS)[1]
        return dict(
            rx_timeout=v >> 7 & 0x01,
            rx_done=v >> 6 & 0x01,
            crc_error=v >> 5 & 0x01,
            valid_header=v >> 4 & 0x01,
            tx_done=v >> 3 & 0x01,
            cad_done=v >> 2 & 0x01,
            fhss_change_ch=v >> 1 & 0x01,
            cad_detected=v >> 0 & 0x01,
        )


    def SX1272_clear_irq_flags(self,
                               rx_timeout=None, rx_done=None, crc_error=None, valid_header=None, tx_done=None,
                               cad_done=None, fhss_change_ch=None, cad_detected=None):

        reg = self.rpi_board.SPI_read_register(REG_LORA.IRQ_FLAGS)[1]
        for i, s in enumerate(['cad_detected', 'fhss_change_ch', 'cad_done', 'tx_done', 'valid_header',
                               'crc_error', 'rx_done', 'rx_timeout']):
            val = locals()[s]
            if val is not None:
                reg = set_bit(reg, i, val)
        return self.rpi_board.SPI_write_register(REG_LORA.IRQ_FLAGS, reg)


    def SX1272_get_modem_status(self):
        status = self.rpi_board.SPI_read_register(REG_LORA.MODEM_STAT)[1]
        return dict(
            rx_coding_rate=status >> 5 & 0x03,
            modem_clear=status >> 4 & 0x01,
            header_info_valid=status >> 3 & 0x01,
            rx_ongoing=status >> 2 & 0x01,
            signal_sync=status >> 1 & 0x01,
            signal_detected=status >> 0 & 0x01
        )

    def get_packet_snr_value(self):
        value = self.rpi_board.SPI_read_register(REG_LORA.PKT_SNR_VALUE)[1]
        return -float(~value + 1)/4. if value & 0x80 else float(value)/4.

    def get_packet_rssi_value(self):
        value = self.rpi_board.SPI_read_register(REG_LORA.PKT_RSSI_VALUE)[1]
        return value - RSSI_COOR

    @getter(REG_LORA.VERSION)
    def get_version(self, val):
        return val[1]

    @getter(REG_LORA.RSSI_VALUE)
    def SX1272_get_rsii_value(self, val):
        return val[1] - RSSI_COOR

    @setter(REG_LORA.SYNC_WORD)
    def SX1272_set_syncword(self, sync_word):
        return sync_word

    @getter(REG_LORA.SYNC_WORD)
    def SX1272_get_syncword(self, val):
        return val[1]

    @getter(REG_LORA.PAYLOAD_LENGTH)
    def SX1272_get_payload_length(self, val):
        return val[1]

    @setter(REG_LORA.PAYLOAD_LENGTH)
    def SX1272_set_payload_length(self, payload_length):
        return payload_length

    @getter(REG_LORA.MAX_PAYLOAD_LENGTH)
    def SX1272_get_max_payload_length(self, val):
        return val[1]

    @setter(REG_LORA.MAX_PAYLOAD_LENGTH)
    def SX1272_set_max_payload_length(self, max_payload_length):
        return max_payload_length

    @getter(REG_LORA.HOP_PERIOD)
    def SX1272_get_hop_period(self, val):
        return val[1]

    @setter(REG_LORA.HOP_PERIOD)
    def SX1272_set_hop_period(self, hop_period):
        return hop_period



    def __str__(self):
        # don't use __str__ while in any mode other that SLEEP or STDBY
        assert (self.mode == MODE.SLEEP or self.mode == MODE.STDBY)

        onoff = lambda i: 'ON' if i else 'OFF'
        f = self.SX1272_get_frequency()
        cfg1 = self.SX1272_get_modem_config1()
        cfg2 = self.SX1272_get_modem_config2()
        #pa_config = self.get_pa_config(convert_dBm=True)
        #ocp = self.get_ocp(convert_mA=True)
        #lna = self.get_lna()
        s = "SX127x LoRa registers:\n"
        s += " mode               %s\n" % MODE(self.SX1272_get_mode()).name

        s += " freq               %f MHz\n" % f
        s += " coding_rate        %s\n" % CODING_RATE(cfg1['coding_rate']).name
        s += " bw                 %s\n" % BW(cfg1['bandwidth']).name
        s += " spreading_factor   %s chips/symb\n" % (1 << cfg2['spreading_factor'])
        s += " implicit_hdr_mode  %s\n" % onoff(cfg1['implicit_header_mode'])
        s += " rx_payload_crc     %s\n" % onoff(cfg1['rx_crc'])
        s += " tx_cont_mode       %s\n" % onoff(cfg2['tx_cont_mode'])
        #s += " preamble           %d\n" % self.get_preamble()
        #s += " low_data_rate_opti %s\n" % onoff(cfg3['low_data_rate_optim'])
        #s += " agc_auto_on        %s\n" % onoff(cfg3['agc_auto_on'])
        s += " symb_timeout       %s\n" % self.SX1272_get_symb_timeout()
        s += " freq_hop_period    %s\n" % self.SX1272_get_hop_period()
        #s += " hop_channel        %s\n" % self.get_hop_channel()
        s += " payload_length     %s\n" % self.SX1272_get_payload_length()
        s += " max_payload_length %s\n" % self.SX1272_get_max_payload_length()
        s += " irq_flags          %s\n" % self.SX1272_get_irq_flags()
        #s += " rx_nb_byte         %d\n" % self.get_rx_nb_bytes()
        #s += " rx_header_cnt      %d\n" % self.get_rx_header_cnt()
        #s += " rx_packet_cnt      %d\n" % self.get_rx_packet_cnt()
        #s += " pkt_snr_value      %f\n" % self.get_pkt_snr_value()
        #s += " pkt_rssi_value     %d\n" % self.get_pkt_rssi_value()
        #s += " rssi_value         %d\n" % self.get_rssi_value()
        #s += " fei                %d\n" % self.get_fei()
        #s += " pa_select          %s\n" % PA_SELECT.lookup[pa_config['pa_select']]
        #s += " max_power          %f dBm\n" % pa_config['max_power']
        #s += " output_power       %f dBm\n" % pa_config['output_power']
        #s += " ocp                %s\n" % onoff(ocp['ocp_on'])
        #s += " ocp_trim           %f mA\n" % ocp['ocp_trim']
        #s += " lna_gain           %s\n" % GAIN.lookup[lna['lna_gain']]
        #s += " lna_boost_lf       %s\n" % bin(lna['lna_boost_lf'])
        #s += " lna_boost_hf       %s\n" % bin(lna['lna_boost_hf'])
        #s += " detect_optimize    %#02x\n" % self.get_detect_optimize()
        #s += " detection_thresh   %#02x\n" % self.get_detection_threshold()
        s += " sync_word          %#02x\n" % self.SX1272_get_syncword()
        #s += " dio_mapping 0..5   %s\n" % self.get_dio_mapping()
        #s += " tcxo               %s\n" % ['XTAL', 'TCXO'][self.get_tcxo()]
        #s += " pa_dac             %s\n" % ['default', 'PA_BOOST'][self.get_pa_dac()]
        #s += " fifo_addr_ptr      %#02x\n" % self.get_fifo_addr_ptr()
        #s += " fifo_tx_base_addr  %#02x\n" % self.get_fifo_tx_base_addr()
        #s += " fifo_rx_base_addr  %#02x\n" % self.get_fifo_rx_base_addr()
        #s += " fifo_rx_curr_addr  %#02x\n" % self.get_fifo_rx_current_addr()
        #s += " fifo_rx_byte_addr  %#02x\n" % self.get_fifo_rx_byte_addr()
        s += " status             %s\n" % self.SX1272_get_modem_status()
        s += " version            %#02x\n" % self.get_version()
        return s







