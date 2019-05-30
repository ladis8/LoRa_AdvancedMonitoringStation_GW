"""
\file       json_packet.py
\author     Ladislav Stefka
\brief      Definition of UDP protocol in JSON between Node-RED server and central unit 
\copyright
"""

import datetime
import logging
import json


import config as cfg


class JsonPacket:
    """General JSON packet class"""

    def __init__(self, data=None):
        #received packet
        if data:
            self.cmd = data["cmd"]

            for x in JsonPacket.__subclasses__():
                if x.CMD == self.cmd:
                    self.__class__ = x
                    self.fill(data["data"])
                    return
            msg = "JSON packet cmd " + str(data["cmd"]) + " not found."
            logging.error(msg)
            raise NameError("Packet class not found for command ", self.cmd)

        else:
            self.cmd = self.CMD

    def __str__(self):
        return "Json packet {} data: {}".format(self.getName(), str(self.__dict__))

    def fill(self, data):
        if not len(data.keys()):
            raise ("Do DB items for Server request {}".format(self.getName()))
        for key in data.keys():
            self.__dict__[key] = data[key]

    def getName(self):
        return self.__class__.__name__

    def get_json(self):
        return json.loads(self.__dict__)

class NodeinfoRequest (JsonPacket):
    CMD = 0x10

    def __init__(self, address):
        super().__init__()
        self.topic = "getInfo"
        self.address = address

class NodeInfoReply (JsonPacket):
    CMD = 0x01

    def __init__(self):
        super().__init__()

class ConfigRequest (JsonPacket):
    CMD = 0x20

    def __init__(self, idloranode):
        self.topic = "getConfig"
        self.idloranode= idloranode
        super().__init__()

class NodeConfigReply(JsonPacket):
    CMD = 0x02

    def __init__(self):
        super().__init__()

    def fill(self, data):
        self.settings = data


class StatusinfoPostRequest(JsonPacket):
    CMD = 0x30

    def __init__(self, idloranode):
        self.idloranode = idloranode
        self.topic = "postData"
        self.rsii = self.snr = 0
        self.timestamp = ""
        self.battery = self.rms = self.vpp = self.ringdowncounts = 0
        self.temperature = self.kurtosisratio = self.krestfactor = self.risetime = self.thresholdduration = 0.0
        self.fs = self.thresholdvoltage = 0.0
        self.N = 0
        self.fftPeaks = ""
        super().__init__()

    def prepare_from_statusinfo_radio_packet(self, statusinfo_rp, config):

        fs, N = config.get_fft_params()
        self.rsii = statusinfo_rp.snr
        self.snr = statusinfo_rp.rsii
        self.timestamp = str(datetime.datetime.now().replace(microsecond=0))

        self.battery = statusinfo_rp.battery * 100 / cfg.Config.BATTERY_FULL
        self.temperature = statusinfo_rp.temperature * config.temperature_calibration_const

        vpp = statusinfo_rp.vpp / config.adc_resolution * cfg.Config.VOLTAGE
        rms = statusinfo_rp.rms / config.adc_resolution * cfg.Config.VOLTAGE
        rise_time = statusinfo_rp.rise_time * 1.0/fs if statusinfo_rp.rise_time != 65535 else 0
        threshold_duration = statusinfo_rp.threshold_duration * 1.0/fs if statusinfo_rp.threshold_duration != 65535 else 0
        self.rms = rms
        self.vpp = vpp
        self.krestfactor = vpp/rms
        self.kurtosisratio = statusinfo_rp.kurtosis_ratio
        self.ringdowncounts = statusinfo_rp.ringdown_counts
        self.risetime = rise_time
        self.thresholdduration = threshold_duration
        self.fftPeaks = json.dumps(statusinfo_rp.get_fft_peaks())

        self.fs = fs
        self.N = N
        self.thresholdvoltage = config.dsp_threshold_voltage

class StatusinfoACK(JsonPacket):
    CMD = 0x03

    def __init__(self):
        super().__init__()


class ResetNodeHard(JsonPacket):
    CMD = 0x04

class ResetNodeConfig(JsonPacket):
    CMD = 0x05

    def __init__(self):
        super().__init__()



