import logging
import time
import lora_module as lm
import rpi_board as rb



#TODO repair bugs in config1 register
#TODO config file in JSON

#modem parameters
#define LORA_PREAMBLE_LENGTH                        8         // Same for Tx and Rx
#define LORA_SYMBOL_TIMEOUT                         5         // Symbols
#define LORA_FIX_LENGTH_PAYLOAD_ON                  false
#define LORA_FHSS_ENABLED                           false
#define LORA_NB_SYMB_HOP                            4
#define LORA_IQ_INVERSION_ON                        false
#define LORA_CRC_ENABLED                            true
config = {}
config["freq"] = 868.5
config["spreading_factor"] = 12
config["coding_rate"] = lm.CODING_RATE.CR4_5.value
config["bandwidth"] = lm.BW.BW7_8.value
config["implicit_header_mode"] = 0
config["rx_crc"] = 1
config["tx_cont_mode"] = 0
config["symbol_timeout"] = 0x08
config["max_payload_len"] = 0xFF
config["payload_len"] = 0x40        #not needed when implicit header mode 0
config["hop_period"] = 0x00
config["sync_word"] = 0x34
config["lr_optimize"] = 1

#location
lat = 0
lon = 0
alt = 0

#server
server_ip = "0.0.0.0"
server_port = 0

module = None


from struct import unpack
from array import array
from enum import Enum

class States(Enum):
    STDBY = 0
    RX = 1
    RX_TIMEOUT = 2
    RX_ERROR = 3
    TX = 4
    TX_TIMEOUT = 5
init_state = States.STDBY

def dio0_irq_handler(channel):
    print(channel, "IRQ called...")

def on_tx_done():
    logging.info("On TX Done")

def on_rx_done():
    logging.info("On RX Done")

def on_rx_timeout():
    logging.info("On RX Timeout")



def unpack_packet_float(payload):
    float_buffer = []
    assert len(payload) % 4 == 0
    for i in range(len(payload)//4):
        float_buffer.append(unpack("f", bytes(payload[i*4:i*4+4]))[0])
        #print(unpack("f", bytes(payload[i*4 :i*4+4]))[0])
    return float_buffer

def unpack_packet_short(payload):
    short_buffer = []
    assert len(payload) % 2 == 0
    for i in range(len(payload)//2):
        short_buffer.append(unpack("H", bytes(payload[i*2:i*2+2]))[0])
    return short_buffer

def write_payload_tofile (payload, file, dtype):
    f = open (file, "ab")
    logging.info("Writing data %s as binary to file %s...", "".join(str(payload[i]) + " " for i in range(5)), file)
    float_array = array(dtype, payload)
    float_array.tofile(f)
    f.close()



def setup():
    global module
    #setup board
    board = rb.RPI_BOARD()
    board.io_setup(dio0_irq_handler)
    board.add_irq_handlers(dio0_irq_handler=dio0_irq_handler)

    #setup config of lora module
    module = lm.SX1272_Module(board)
    module.SX1272_is_alive()
    module.SX1272_module_setup(config)


def loop():
    global module

    while True:

        #receive join
        rec = module.receive_packet()


        #receive ffft values
        buffer = []
        counter = 0
        while counter < 32:
            rec = module.receive_packet()
            if rec is not None:
                counter += 1
                rec_val = unpack_packet_float(rec)
                print("".join(str(rec_val[i]) + " " for i in range(5)))
                buffer.extend(rec_val)
        write_payload_tofile(buffer, "fft_values", "f")

        #receive adc readings
        buffer = []
        counter = 0
        while counter < 16:
            rec = module.receive_packet()
            if rec is not None:
                counter += 1
                buffer.extend(unpack_packet_short(rec))
            time.sleep(0.01)
        write_payload_tofile(buffer, "adc_values", "H")










if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    setup()
    loop()






