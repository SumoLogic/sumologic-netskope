# -*- coding: future_fstrings -*-
import json
import sys
from base import BaseOutputHandler
from client import SessionPool, ClientMixin


class HTTPHandler(BaseOutputHandler):

    def setUp(self, config, *args, **kwargs):
        self.sumo_config = config["SumoLogic"]
        self.collection_config = config['Collection']
        self.sumoconn = SessionPool(self.collection_config['MAX_RETRY'], self.collection_config['BACKOFF_FACTOR'])

    def send(self, data):
        if isinstance(data, list):
            out = [json.dumps(d) for d in data]
            out = '\n'.join(out)
        else:
            out = data
        self.log.info(f'posting size {sys.getsizeof(out)}')
        sess = self.sumoconn.get_request_session()
        headers = {'content-type': 'application/json', 'accept': 'application/json'}
        fetch_success, respjson = ClientMixin.make_request(self.sumo_config['SUMO_ENDPOINT'], method="post",
                                                           session=sess, data=out,
                                                           headers=headers)
        if not fetch_success:
            self.log.error(f'''Error in Sending to Sumo {respjson.content}''')
            return False
        return True


class STDOUTHandler(BaseOutputHandler):

    def setUp(self, config, *args, **kwargs):
        pass

    def send(self, data):
        if isinstance(data, list):
            out = [json.dumps(d) for d in data]
            out = '\n'.join(out)
        else:
            out = data
        self.log.info(f'posting size {sys.getsizeof(out)}')
        print(out)
        return True

