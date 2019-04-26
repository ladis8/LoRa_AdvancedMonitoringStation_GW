import threading
import logging
#import time
import datetime
from queue import Queue, Empty
from threading import Timer
import enum



import radio_packet as rp
import config as cfg
import params as prm
from packet_forwarder import Gateway
import tools

import socket
import requests
import json
import datetime



IP = "127.0.0.1"
PORT = 8888
URL_STATUSINFO = "http://127.0.0.1:1880/lora_nodered/statusinfo"

APPLICATION_MODE = 0 #status mode


class States(enum.IntEnum):
    STOPPED = 0
    JOINING = 10
    JOINED = 20
    EXPECTING_CHUNK = 30

    ERROR = 100

FFT_NUM_OF_CHUNKS = 32



class NodeWorker:
    """Communication with lora node"""

    TIMEOUT = 1000
    MAIN_LOOP_SLEEP = 0.1
    DEBUG = True

    def get_id(self):
        return self.params.idloranode

    def __init__(self, tx_queue, nat):
        self.name = "LORA_WORKER ??"
        self.rx_queue = Queue()
        self.tx_queue = tx_queue
        self.nat = nat

        #config
        self.config = cfg.Config()

        #params
        self.params = prm.Params()


        self.start_time = 0
        self.fft_buffer = [0] * 1024
        self.last_temperature = 0

        self.shouldRun = True
        self.worker_thread = threading.Thread(target=self.worker)
        self.worker_thread.setDaemon(True)

        self.statusInfoPeriod = NodeWorker.TIMEOUT

        #socket connection
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        #http connection

        self.cntNet = 0
        self.cntNetErr = 0
        self.cntRadio = 0
        self.cntRadioErr = 0
        self.lastStatusInfo = None
        self.statusInfo = None
        self.uptime = 0
        self.state = 0
        self.nextTimeout = None
        self.nextStatusInfo = None
        if NodeWorker.DEBUG:
            logging.info("+++ New lora node worker...")

    def HTTP_send_data(self, statusinfo_rp):
        message = {}
        message['idloranode'] = self.get_id()
        message['battery'] = statusinfo_rp.battery
        message['rms'] = statusinfo_rp.rms
        message['vpp'] = statusinfo_rp.vpp
        message['temperature'] = statusinfo_rp.temperature
        message['fftPeaks'] = json.dumps(statusinfo_rp.get_fft_peaks())
        message['fs'] = self.config.get_fft_params()[0]
        message['N'] = self.config.get_fft_params()[1]
        message['rsii'] = statusinfo_rp.snr
        message['snr'] = statusinfo_rp.rsii
        message['timestamp'] = str(datetime.datetime.now().replace(microsecond=0))

        req = requests.post(url=URL_STATUSINFO, data=message)
        out = (req.status_code, req.reason)
        logging.debug("Data was successfully sent to node-red server %s", out)



    def UDP_send_data(self, statusinfo_rp):
        message = {}
        message['idloranode'] = self.get_id()
        message['battery'] = statusinfo_rp.battery
        message['rms'] = statusinfo_rp.rms
        message['vpp'] = statusinfo_rp.vpp
        message['temperature'] = statusinfo_rp.temperature
        message['fftPeaks'] = json.dumps(statusinfo_rp.get_fft_peaks())
        message['fs'] = self.config.get_fft_params()[0]
        message['N'] = self.config.get_fft_params()[1]
        message['rsii'] = statusinfo_rp.snr
        message['snr'] = statusinfo_rp.rsii
        message['timestamp'] = str(datetime.datetime.now().replace(microsecond=0))

        self.socket.sendto(json.dumps(message).encode('ascii'), (IP, PORT))
        logging.debug("Data was successfully sent to node-red server")


    def send_fft_req(self):
        req = rp.FFTChunkRequest()
        req.sessionid = self.params.sessionid
        req.data_type = rp.FFTChunkRequest.DATA_TYPE
        self.tx_queue.put(req)
        self.state = States.EXPECTING_CHUNK

    def send_join_reply(self):

        if APPLICATION_MODE == 0:
            jr = rp.JoinReplyStatusMode()
            jr.sessionid = self.params.sessionid
            jr.result = 1

        cfg.Config.store_config_to_radio_packet(self.config, jr)
        self.tx_queue.put(jr)







    def extendTimeout(self, timeout=None):
        if not timeout:
            timeout = NodeWorker.TIMEOUT
        self.nextTimeout = datetime.datetime.now() + datetime.timedelta(seconds=timeout)

    def start(self):
        """Start lora node worker thread"""
        logging.warning("%s:Starting lora node worker threads.", self.name)
        try:
            #connect to internet
            #self.ms.connect()
            self.extendTimeout()
            self.state = States.JOINING
        except:
            self.state = States.ERROR.value
            raise

        self.worker_thread.start()

    def stop(self):
        """
        Stop lora node worker thread
        Do nonblocking join so threads can start stopping simultaneously.
        It is necessary to check if threads terminated using is_alive() method
        """
        logging.debug("%s: Stopping lora node: %s")
        self.shouldRun = False
        self.state = States.STOPPED
        self.worker_thread.join(0.1)

    def is_alive(self):
        return self.worker_thread.is_alive()




#Main stauts worker process
    def worker(self):

        while self.shouldRun:
            dt = datetime.datetime.now()
            if dt > self.nextTimeout:
                logging.error("%s:Timeout expecting data", self.name)
                self.shouldRun = False
                self.state = States.ERROR
            #if self.nextStatusInfo and dt > self.nextStatusInfo:
            #     self.objToSend.put(jsonPacket.StatusInfo())
            #     self.nextStatusInfo = datetime.datetime.now() + datetime.timedelta(seconds=self.STATUS_INFO_PERIOD)
            #     self.extendTimeout()
            try:
                rec = self.rx_queue.get(True, NodeWorker.MAIN_LOOP_SLEEP)
            except Empty:
                continue

            #packet processing routine
            self.extendTimeout()

            #STETE_01: Join request is pending...
            if self.state == States.JOINING:
                if isinstance(rec, rp.JoinRequest):
                    assert rec.sessionid == 0x00

                    #get params
                    prm.Params.HTTP_get_params_fromDB(self.params, rec.unique_id)

                    self.name = "LORA_WORKER " + str(self.params.sessionid)
                    self.start_time = rec.time


                    #change state
                    self.state = States.JOINED

                    #self relation sessionid -- address
                    self.nat[self.params.sessionid] = self.params.address

                    #get config
                    cfg.Config.HTTP_get_config_fromDB(self.config, self.params.idloranode)

                    #send join reply
                    self.send_join_reply()

                    logging.info("%s: Received JOIN PACKET:\n"
                                 "      relation: (%s-%s), fwver: %s, starttime: %s\n"
                                 "      config loaded, join reply sent",
                                 self.name, self.params.sessionid, self.params.address, self.params.fwver, self.start_time)

                else:
                    logging.error("%s: Received unexpected packet %s, STATE=JOINING\n", self.name, rec.name())
                    self.state = States.ERROR

            #STETE_02: Node is joined, waiting for another packets...
            elif self.state == States.JOINED:
                if isinstance(rec, rp.StatusInfo):
                    assert rec.sessionid == self.params.sessionid
                    logging.info("%s: Received STATUS INFO packet:\n"
                                 "      temp: %f bat: %d rms: %.3f vpp: %.3f peaks (%u): %s",
                                 self.name, rec.temperature, rec.battery, rec.rms, rec.vpp, rec.fft_peaks_num, rec.get_fft_peaks())
                    #self.UDP_send_data(rec)
                    self.HTTP_send_data(rec)

                else:
                    logging.error("%s: Received unexpected packet %s, STATE=JOINED\n", self.name, rec.name())

            elif self.state == States.EXPECTING_CHUNK:
                if isinstance(rec, rp.FFTChunkData):
                    self.fft_buffer[rec.seqnum * 32: rec.seqnum * 32 + 32] = rec.get_FFT_bins()
                    if rec.seqnum == FFT_NUM_OF_CHUNKS - 1: #32 fft chunks in total
                        tools.write_data_to_file(self.fft_buffer, "fft_values", "f")
                        logging.info("FFT spectrum was received...")
                        self.state = States.JOINED
                    logging.info("FFT chunk received...")
                elif isinstance(rec, rp.TemperatureData):
                    self.last_temperature = rec.temperature
                    logging.info("Temperature packet received...")
                else:
                    logging.error("%s:unexpected packet:%s", self.name, rec.name)

            else:
                logging.error("%s:Unexpected condition :%s", self.name, rec.packet)
            #End of packet processing routine

        self.state = States.ERROR
        logging.info("%s:Main loop stopped.", self.name)



