import threading
import logging
#import time
import datetime
from queue import Queue, Empty
from threading import Timer
import enum

import radio_packet as rp
from packet_forwarder import Gateway
import tools


class States(enum.IntEnum):
    STOPPED = 0
    JOINING = 10
    JOINED = 20
    EXPECTING_CHUNK = 30

    ERROR = 100

FFT_NUM_OF_CHUNKS = 32

#TODO: Question prideleni id
class NodeWorker:
    """Communication with lora node"""

    TIMEOUT = 1000
    MAIN_LOOP_SLEEP = 0.1
    DEBUG = True

    def __init__(self, tx_queue):
        self.id = None
        self.name = "LORA_WORKER ??"
        self.state = States.JOINING
        self.rx_queue = Queue()
        self.tx_queue = tx_queue

        self.start_time = 0
        self.fft_buffer = [0] * 1024
        self.last_temperature = 0

        self.shouldRun = True
        self.worker_thread = threading.Thread(target=self.worker)
        self.worker_thread.setDaemon(True)

        self.statusInfoPeriod = NodeWorker.TIMEOUT

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

        self.t = Timer(5.0, self.request_fft)

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



    def send_fft_req(self):
        req = rp.FFTChunkRequest()
        req.id = self.id
        req.data_type = rp.FFTChunkRequest.DATA_TYPE
        self.tx_queue.put(req)
        self.state = States.EXPECTING_CHUNK

    def send_join_reply(self):
        jr = rp.JoinReply()
        jr.id = self.id
        jr.result = 1
        jr.status_interval = 30000
        self.tx_queue.put(jr)
        self.state = States.JOINED






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
            if self.state == States.JOINING:
                if isinstance(rec, rp.JoinRequest):
                    self.id = rec.id
                    self.start_time = rec.time
                    self.name = "LORA_WORKER " + str(self.id)
                    self.send_join_reply()
                    logging.info("%s: Joining LoRa node success - %s\n", self.name, self.start_time)
                    self.state = States.JOINED

                    self.t.start()
                else:
                    logging.error("%s: Joining failed, unexpected packet %s\n", self.name, rec.name())
                    self.state = States.ERROR

            elif self.state == States.JOINED:
                pass
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
                    logging.error("%s:Unexpected packet:%s", self.name, rec.name)

            else:
                logging.error("%s:Unexpected condition :%s", self.name, rec.packet)
            #End of packet processing routine

        self.state = States.ERROR
        logging.info("%s:Main loop stopped.", self.name)




    def processStatusInfo(self, statusInfo):
        pass

    def request_fft(self):
        print("FFT callback called...")
        self.send_fft_req()


