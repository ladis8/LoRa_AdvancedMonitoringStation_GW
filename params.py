import requests

URL_PARAMS = "http://127.0.0.1:1880/lora_nodered/node_params"

#TODO setter attitude

class Params:

    def __init__(self):
        #loranode_params
        self.idloranode = None
        self.address = None
        self.sessionid= None
        self.code = None
        self.name = None
        self.fwver = None


    def __str__(self):
        print("Params of lora node {}".format(self.idloranode))
        print(self.__dict__)

    @staticmethod
    def HTTP_get_params_fromDB(params, address):

        http_params = {'address': address}
        req = requests.get(url=URL_PARAMS, params=http_params)
        out = req.json()

        if not len(out):
            raise Exception("No DB item for loranode with address {}".format(address))

        for row in out:
            assert len(out) == 1
            for key in row:
                params.__dict__[key] = row[key]
        params.sessionid = int(params.sessionid, 16)
