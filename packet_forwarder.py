"""
\file       packet_forwarder.py
\author     Ladislav Stefka
\brief      Main module for controlling radio communication and moving radio packets to appropriate LoRaNode workers
            - main loop of application
            - loading default radio configuration
            - setup, loop structure
\copyright
"""



import logging
import time
import sys
from queue import Queue
from enum import Enum

import lora_module as lm
import rpi_board as rb
import radio_packet
import lora_node_worker as lnw


# HIGH PRIORITY
# TODO: send Status request

# LOW PRIORITY
# TODO config file in JSON

# DEFAULT LORA MODULE CONFIGURATION
config = {}
config["freq"] = 868.5
config["spreading_factor"] = 12
config["coding_rate"] = lm.CODING_RATE.CR4_6.value
config["bandwidth"] = lm.SX1276_BW.BW125.value
config["implicit_header_mode"] = 0
config["rx_crc"] = 1
config["tx_cont_mode"] = 0
config["symbol_timeout"] = 0x08     #not needed when RX continuous mode
config["max_payload_len"] = 0xFF
config["payload_len"] = 0x0B        #not needed when implicit header mode 0
config["hop_period"] = 0x00
config["sync_word"] = 0x34
config["lr_optimize"] = 1
config["agc_auto_on"] = 0
config["pa_select"] = 1             #pa_boost
config["pa_output_power"] = 0x0F    #Pout = 17 dB/m


class States(Enum):
    """States of application"""
    IDLE = 0
    RX_RUNNING = 1
    TX_RUNNING = 2
    CAD = 3


class Gateway:
    """Gateway object holding main references"""
    board = None
    module = None
    state = States.IDLE
    tx_queue = Queue()
    nodes = {}
    nat = {}
    RX_TIMEOUT = 10


def on_tx_done(channel):
    irq_flags = Gateway.module.SX1272_get_irq_flags()
    #logging.debug("DIO0 IRQ ON TX DONE handler - Flags: %s", irq_flags)
    Gateway.module.SX1272_clear_irq_flags(tx_done=1)
    #Gateway.module.SX1272_set_mode(lm.MODE.SLEEP)
    Gateway.state = States.IDLE


def on_rx_done(channel=None):
    m = Gateway.module
    logging.info("On RX Done")
    irq_flags = m.SX1272_get_irq_flags()
    logging.debug("DIO0 IRQ ON RX DONE handler - Flags: %s", irq_flags)
    m.received_packets += 1

    if m.mode == lm.MODE.RXCONT:
        m.SX1272_clear_irq_flags(rx_done=1)
        if irq_flags['crc_error']:
            logging.error("CRC ERROR WAS DETECTED!!!")
            Gateway.state = States.IDLE
            return

        #output received raw data
        payload = m.read_rx_payload()
        packet_SNR = m.SX127X_get_packet_snr_value()
        packet_RSII = m.SX127X_get_packet_rssi_value()
        RSII = m.SX127X_get_rssi_value()
        logging.debug("Packet CRC OK: SNR= %s, packet RSII= %s, RSII= %s, length = %d, message = %s",
                     packet_SNR, packet_RSII, RSII, len(payload), "".join("\\x{:02x}".format(x) for x in payload))

        #convert payload to appropriate radio packet
        rp = radio_packet.RadioPacket(payload)
        rp.snr = packet_SNR
        rp.rsii = packet_RSII

        #create new node if it is join request
        if rp.sessionid == 0x00:
            node_worker = lnw.NodeWorker(Gateway.tx_queue, Gateway.nat)
            node_worker.rx_common_queue.put(rp)
            node_worker.start()

            Gateway.nodes[rp.unique_id] = node_worker
        #filter packet if it is from node that is not joined
        elif rp.sessionid not in Gateway.nat:
            logging.error("Packed filterd, received packet with unknown seassion id %s", rp.sessionid)
        else:
            logging.debug("Received packet with seassion id 0x%02x", rp.sessionid)
            address = Gateway.nat[rp.sessionid]
            node = Gateway.nodes[address]
            node.rx_common_queue.put(rp)

        Gateway.state = States.IDLE


def on_rx_timeout(channel=None):
    #logging.debug("ON RX TIMEOUT handler...")
    irq_flags = Gateway.module.SX1272_get_irq_flags()
    #logging.debug("DIO0 IRQ ON RX TIMEOUT handler - Flags: %s", irq_flags)
    #Gateway.module.SX1272_clear_irq_flags(rx_timeout=1)
    #Gateway.module.SX1272_set_mode(lm.MODE.STDBY)
    Gateway.state = States.IDLE



def setup(type):
    # setup board
    board = rb.RPI_BOARD()
    Gateway.board = board

    # setup config of lora module
    module = lm.SX127X_Module(board, type)
    module.SX127X_module_setup(config)
    Gateway.module = module


def loop():

    timeout = None

    while True:
        try:
            #TODO: check channel detection
            if (Gateway.state == States.IDLE or Gateway.state == States.RX_RUNNING) and not Gateway.tx_queue.empty():
                Gateway.module.set_tx(on_tx_done, Gateway.tx_queue.get())
                Gateway.state = States.TX_RUNNING

            elif Gateway.state == States.IDLE:
                Gateway.module.set_rx_continuous(on_rx_done)
                Gateway.state = States.RX_RUNNING
                timeout = time.time() + Gateway.RX_TIMEOUT

            elif Gateway.state == States.RX_RUNNING and time.time() > timeout:
                on_rx_timeout()

            time.sleep(0.1)

        except KeyboardInterrupt:
            print("Cleaning...")
            Gateway.board.clean()
            break
        except AssertionError:
            print("Cleaning...")
            Gateway.board.clean()
            break


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    if sys.argv[1] == "SX1272" or sys.argv[1] == "SX1276":
        setup(sys.argv[1])
        loop()
    else:
        print("Wrong module name")
