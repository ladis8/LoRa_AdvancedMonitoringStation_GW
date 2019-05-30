"""
\file       lora_node_worker.py
\author     Ladislav Stefka
\brief      Object represents connected measuring unit
            - 3 threads for handling radio and UDP communication
            - state machine description 
\copyright
"""

import threading
import logging
from queue import Queue, Empty
import enum
import socket
import requests
import json
import datetime


import radio_packet as rp
import json_packet as jp
import config as cfg
import params as prm
import tools



#TODO: move server ip and urls to separate file
SERVER_IP = "127.0.0.1"
SERVER_PORT = 12344
URL_STATUSINFO = "http://127.0.0.1:1880/lora_nodered/statusinfo"

APPLICATION_MODE = 0 #status mode


class States(enum.IntEnum):
    STOPPED = 0
    JOINING = 10
    JOINED = 20
    CONFIGURED = 30
    EXPECTING_CHUNK = 40
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
        self.state = 0

        self.rx_common_queue = Queue()
        self.tx_radio_queue = tx_queue
        self.tx_udp_queue = Queue()
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
        self.receive_thread = threading.Thread(target=self.receiver)
        self.sending_thread = threading.Thread(target=self.sender)

        self.statusInfoPeriod = NodeWorker.TIMEOUT

        #socket connection
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("127.0.0.1", prm.Params.CFG_DEFAULT_PORT))

        #http connection

        self.cntNet = 0
        self.cntNetErr = 0
        self.cntRadio = 0
        self.cntRadioErr = 0


        self.lastStatusInfo = None
        self.statusInfo = None
        self.uptime = 0
        self.nextTimeout = None
        self.nextStatusInfo = None
        if NodeWorker.DEBUG:
            logging.info("+++ New lora node worker...")


    def _prepare_message (self, statusinfo_rp):

        fs, N = self.config.get_fft_params()
        message = {}
        message['idloranode'] = self.get_id()
        message['rsii'] = statusinfo_rp.snr
        message['snr'] = statusinfo_rp.rsii
        message['timestamp'] = str(datetime.datetime.now().replace(microsecond=0))

        message['battery'] = statusinfo_rp.battery * 100 / cfg.Config.BATTERY_FULL
        message['temperature'] = statusinfo_rp.temperature * self.config.temperature_calibration_const

        vpp = statusinfo_rp.vpp / self.config.adc_resolution * cfg.Config.VOLTAGE
        rms = statusinfo_rp.rms / self.config.adc_resolution * cfg.Config.VOLTAGE
        rise_time = statusinfo_rp.rise_time * 1.0/fs if statusinfo_rp.rise_time != 65535 else 0
        threshold_dduration = statusinfo_rp.threshold_duration * 1.0/fs if statusinfo_rp.threshold_duration != 65535 else 0
        message['rms'] = rms
        message['vpp'] = vpp
        message['krestfactor'] = vpp/rms
        message['kurtosisratio'] = statusinfo_rp.kurtosis_ratio
        message['ringdowncounts'] = statusinfo_rp.ringdown_counts
        message['risetime'] = rise_time
        message['thresholdduration'] = threshold_dduration
        message['fftPeaks'] = json.dumps(statusinfo_rp.get_fft_peaks())

        message['fs'] = fs
        message['N'] = N
        message['thresholdvoltage'] = self.config.dsp_threshold_voltage

        print("DEBUG", statusinfo_rp.threshold_duration, statusinfo_rp.rise_time)
        print(message)

        return message

    def HTTP_send_data(self, statusinfo_rp):
        message = self._prepare_message(statusinfo_rp)
        req = requests.post(url=URL_STATUSINFO, data=message)
        out = (req.status_code, req.reason)
        logging.debug("Data was successfully sent to node-red server %s", out)

    def UDP_send_data(self, statusinfo_rp):
        message = self._prepare_message(statusinfo_rp)
        self.socket.sendto(json.dumps(message).encode('ascii'), (SERVER_IP, SERVER_PORT))
        logging.debug("Data was successfully sent to node-red server")



    def send_fft_req(self):
        req = rp.FFTChunkRequest()
        req.sessionid = self.params.sessionid
        req.data_type = rp.FFTChunkRequest.DATA_TYPE
        self.tx_radio_queue.put(req)
        self.state = States.EXPECTING_CHUNK

    def send_join_reply(self):

        jr = rp.JoinReply()
        jr.sessionid = self.params.sessionid
        jr.result = 1
        jr.bw = cfg.Bandwidth[cfg.Config.CFG_DEFAULT_BW]
        jr.sf = cfg.SpreadingFactor[cfg.Config.CFG_DEFAULT_SF]
        jr.cr = cfg.CodingRate[cfg.Config.CFG_DEFAULT_CR]
        jr.app_mode = APPLICATION_MODE
        jr.join_interval = cfg.Config.CFG_DEFAULT_JOIN_INTERVAL
        self.tx_radio_queue.put(jr)

    def send_config_reply(self):
        cr = rp.ConfigReply()
        cfg.Config.store_config_to_radio_packet(cr=cr, config=self.config)
        self.tx_radio_queue.put(cr)

    def send_restart (self, resetConfig=False):
        resp = rp.Restart()
        resp.resetConfig = resetConfig
        self.tx_radio_queu.put(resp)



    def extendTimeout(self, timeout=None):
        if not timeout:
            timeout = NodeWorker.TIMEOUT
        self.nextTimeout = datetime.datetime.now() + datetime.timedelta(seconds=timeout)

    def start(self):
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
        self.receive_thread.start()
        self.sending_thread.start()

        #self.tx_udp_queue.put({"topic": "getInfo", "address": "0x0D473533"})

    def stop(self):
        logging.debug("%s: Stopping lora node: %s")
        self.shouldRun = False
        self.state = States.STOPPED
        self.worker_thread.join(0.1)
        self.receive_thread.join(0.1)
        self.sending_thread.join(0.1)

    def is_alive(self):
        if self.worker_thread.is_alive() or self.receive_thread.is_alive() or self.sending_thread.is_alive():
            return True
        else:
            return False



    #Main stauts worker Thread
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
                rec = self.rx_common_queue.get(True, NodeWorker.MAIN_LOOP_SLEEP)
            except Empty:
                continue

            #packet processing routine
            self.extendTimeout()

            #STETE_01: Join request is pending...
            if self.state == States.JOINING:

                if isinstance(rec, rp.JoinRequest):
                    assert rec.sessionid == 0x00

                    self.start_time = rec.time

                    logging.info("%s: Received JOIN REQUEST RP from address %s, start time %s...",
                                 self.name, rec.unique_id, self.start_time)
                    #get params
                    #prm.Params.HTTP_get_params_fromDB(self.params, rec.unique_id)
                    nr = jp.NodeinfoRequest(rec.unique_id)
                    self.tx_udp_queue.put(nr)


                elif isinstance(rec, jp.NodeInfoReply):

                    #get params object
                    self.params.set_from_json_packet(rec)

                    #set NAT
                    self.nat[self.params.sessionid] = self.params.address

                    #bind port
                    try:
                        #self.socket.close()
                        pass
                        #self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        #self.socket.bind(("127.0.0.1", int(self.params.port)))
                    except:
                        logging.error("Receiver port bind failed...")
                        raise

                    #change state
                    self.state = States.JOINED

                    self.name = "LORA_WORKER 0x{:02X}".format(self.params.sessionid)
                    logging.info("%s: Received NODE INFO JP, relation (%s - %s), fwver %s",
                                  self.name, self.params.address, self.params.sessionid, self.params.fwver)
                    #send reply
                    self.send_join_reply()

                else:
                    logging.error("%s: Received unexpected packet %s, STATE=JOINING\n", self.name, rec.getName())
                    self.state = States.ERROR

            #STETE_02: Node is joined, waiting for another packets...
            elif self.state == States.JOINED:

                if isinstance(rec, rp.ConfigRequest):
                    assert self.config.config_fetched is False

                    logging.info("%s: Received CONFIG REQUEST RP", self.name)

                    # #get config
                    # cfg.Config.HTTP_get_config_fromDB(self.config, self.params.idloranode)
                    cr = jp.ConfigRequest(self.get_id())
                    self.tx_udp_queue.put(cr)


                elif isinstance(rec, jp.NodeConfigReply):

                    #get config object
                    self.config.set_from_json_packet(rec)

                    #change state
                    self.state = States.CONFIGURED

                    logging.info("%s: Received NODE CONFIG JP \n %s", self.name, self.config)

                    #send reply
                    self.send_config_reply()

                elif isinstance(rec, jp.ResetNodeHard):
                    logging.info("%s: Received HARD RESTART JP", self.name)
                    self.state = States.JOINING
                    self.send_restart(resetConfig=False)


                elif isinstance(rec, jp.StatusinfoACK):
                    pass


                elif isinstance(rec, rp.StatusInfo):
                    assert rec.sessionid == self.params.sessionid
                    logging.warning("%s: Received STATUS INFO packet for unknown configuration!!!\n", self.name)
                    #TODO: send reset packet

                else:
                    logging.error("%s: Received unexpected packet %s, STATE=JOINED\n", self.name, rec.getName())


            #STETE_03: Node is configured, waiting for status info packets...
            elif self.state == States.CONFIGURED:
                assert self.config.config_fetched is True

                if isinstance(rec, rp.StatusInfo):
                    assert rec.sessionid == self.params.sessionid

                    logging.info("%s: Received STATUS INFO RP\n"
                                 "     temp: %.3f bat: %u rms: %.3f vpp: %.3f\n"
                                 "     kurtosis ratio: %.3f ringdown counts: %u, risetime: %u th.duration: %u\n"
                                 "     peaks (%u): %s",
                                 self.name, rec.temperature, rec.battery, rec.rms, rec.vpp,
                                 rec.kurtosis_ratio, rec.ringdown_counts, rec.rise_time, rec.threshold_duration,
                                 rec.fft_peaks_num, rec.get_fft_peaks()
                                 )
                    #post data
                    #self.UDP_send_data(rec)
                    #self.HTTP_send_data(rec)
                    pr = jp.StatusinfoPostRequest(self.get_id())
                    pr.prepare_from_statusinfo_radio_packet(rec, self.config)
                    self.tx_udp_queue.put(pr)

                elif isinstance(rec, jp.ResetNodeHard):
                    logging.info("%s: Received HARD RESTART JP", self.name)
                    self.state = States.JOINING
                    self.send_restart(resetConfig=False)

                elif isinstance(rec, jp.ResetNodeConfig):
                    logging.info("%s: Received CONFIG RESET JP", self.name)
                    self.state = States.JOINED
                    self.send_restart(resetConfig=True)

                elif isinstance(rec, jp.StatusinfoACK):
                    pass

                else:
                    logging.error("%s: Received unexpected packet %s, STATE=CONFIGURED\n", self.name, rec.getName())

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
                    logging.error("%s:unexpected packet:%s", self.name, rec.getName)

            else:
                logging.error("%s:Unexpected condition :%s", self.name, rec.packet)
            #End of packet processing routine

        self.state = States.ERROR
        logging.info("%s:Main loop stopped.", self.name)

    #Receiver Thread
    def receiver(self):
        while self.shouldRun:
            packet = self.socket.recvfrom(2048)
            if packet:
                if NodeWorker.DEBUG: logging.debug("%s - receiver: Received packet %s", self.name, packet)
                try:
                    self.cntNet += 1
                    data = json.loads(packet[0].decode())
                    try:
                        rec = jp.JsonPacket(data)
                    except:
                        raise
                    self.rx_common_queue.put(rec)
                    if NodeWorker.DEBUG: logging.debug("%s - receiver: Json packet %s put in rx_queue", self.name, rec.getName())
                except:
                    raise
                    logging.error("%s - receiver: Invalid JSON... ", self.getName)
                    self.cntNetErr += 1

    #Sender Thread
    def sender(self):
        while self.shouldRun:
            try:
                packet = self.tx_udp_queue.get(block=True, timeout=10)  # blokujici get
                data = json.dumps(packet.__dict__).encode('ascii')
                if NodeWorker.DEBUG: logging.debug("%s - sender: Sending json %s", self.name,  data)
                self.socket.sendto(data, (SERVER_IP, SERVER_PORT))
            except Empty:
                if NodeWorker.DEBUG: logging.debug("%s - sender:No JSON to send", self.name)
                pass



