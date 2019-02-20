# -*- coding: future_fstrings -*-
import traceback
import sys
import time
import itertools
from concurrent import futures
from logger import get_logger
from factory import ProviderFactory, OutputHandlerFactory
from client import SessionPool, ClientMixin
from utils import get_current_timestamp, convert_epoch_to_date
from config import Config


class NetskopeCollector(object):

    def __init__(self):
        cfgpath = sys.argv[1] if len(sys.argv) > 1 else ''
        self.config = Config().get_config(cfgpath)
        self.log = get_logger(__name__, force_create=True, **self.config['Logging'])
        self.collection_config = self.config['Collection']
        self.netskope_conn = SessionPool(self.collection_config['MAX_RETRY'], self.collection_config['BACKOFF_FACTOR'])
        op_cli = ProviderFactory.get_provider(self.config['Collection']['ENVIRONMENT'])
        self.kvstore = op_cli.get_storage("keyvalue", name='netskope')
        self.ALERT_TYPES = self.config['Netskope']['ALERT_TYPES']
        self.EVENT_TYPES = self.config['Netskope']['EVENT_TYPES']
        self.NETSKOPE_ALERT_ENDPOINT = self.config['Netskope']['NETSKOPE_ALERT_ENDPOINT']
        self.NETSKOPE_EVENT_ENDPOINT = self.config['Netskope']['NETSKOPE_EVENT_ENDPOINT']
        self.TOKEN = self.config['Netskope']['TOKEN']
        self.FETCH_METHOD = self.config['Netskope']['FETCH_METHOD']
        self.DEFAULT_START_TIME_EPOCH = get_current_timestamp() - self.config['Netskope']['BACKFILL_DAYS']*24*60*60

    def get_endpoint_url(self, event_type):
        if event_type in self.ALERT_TYPES:
            return self.NETSKOPE_ALERT_ENDPOINT
        else:
            return self.NETSKOPE_EVENT_ENDPOINT

    def set_fetch_state(self, event_type, start_time_epoch, end_time_epoch, skip=0):
        if end_time_epoch:  # end time epoch could be none in cases where no event is present
            assert start_time_epoch <= end_time_epoch
        obj = {
            "skip": skip,
            'url': self.get_endpoint_url(event_type),
            "event_type": event_type,
            "start_time_epoch": start_time_epoch,
            "end_time_epoch": end_time_epoch
        }

        self.kvstore.set(event_type, obj)
        return obj

    def set_new_end_epoch_time(self, event_type, start_time_epoch):
        params = {
            'token': self.TOKEN,
            'limit': 1,
            'starttime': start_time_epoch,
            'endtime': get_current_timestamp(),
            'skip': 0,
            'type': event_type
        }
        url = self.get_endpoint_url(event_type)
        sess = self.netskope_conn.get_request_session()
        success, respjson = ClientMixin.make_request(url, method=self.FETCH_METHOD, session=sess, params=params)
        self.netskope_conn.close()
        start_date = convert_epoch_to_date(params['starttime'])
        end_date = convert_epoch_to_date(params['endtime'])
        if success and respjson["status"] == "success" and len(respjson["data"]) > 0:
            obj = self.set_fetch_state(event_type, start_time_epoch, respjson["data"][0]["timestamp"])
            self.log.info(f'''Creating task for {event_type} from {start_date} to {end_date}''')
            return obj
        else:
            self.log.info(f'''No events are available for {event_type} from {start_date} to {end_date}''')
            return None

    def transform_data(self, data):
        # import random
        # srcip = ["216.161.180.148", "54.203.63.36"]
        # for d in data:
        #     d["timestamp"] = int(time.time())
        #     d["srcip"] = random.choice(srcip)
        return data

    def fetch(self, url, event_type, start_time_epoch, end_time_epoch, skip):

        params = {
            'token': self.TOKEN,
            'limit': self.config['Netskope']['PAGINATION_LIMIT'],
            'starttime': start_time_epoch,
            'endtime': end_time_epoch,
            'skip': skip,
            'type': event_type
        }
        output_handler = OutputHandlerFactory.get_handler(self.config['Collection']['OUTPUT_HANDLER'], config=self.config)
        next_request = send_success = True
        count = 0
        move_window = False
        sess = self.netskope_conn.get_request_session()
        try:
            while next_request:
                count += 1
                fetch_success, respjson = ClientMixin.make_request(url, method=self.FETCH_METHOD, session=sess, params=params)
                if fetch_success and respjson["status"] == "success":
                    data = respjson["data"]
                    if len(data) > 0:
                        data = self.transform_data(data)
                        send_success = output_handler.send(data)
                        if send_success:
                            params['skip'] += len(data)
                    else:  # no data so moving window
                        move_window = True
                    self.log.info(f'''Finished Fetching Page: {count} Event Type: {event_type} Datalen: {len(
                        data)} Next_Request: {next_request} starttime: {convert_epoch_to_date(
                        start_time_epoch)} endtime: {convert_epoch_to_date(end_time_epoch)}''')

                next_request = fetch_success and send_success and (not move_window)
                if move_window:
                    self.log.info(
                        f'''Moving starttime window for {event_type} to {convert_epoch_to_date(params["endtime"] + 1)}''')
                    self.set_fetch_state(event_type, params["endtime"] + 1, None)
                elif not (fetch_success and send_success):  # saving skip in casee of failures for restarting in future
                    self.set_fetch_state(event_type, params["starttime"], params["endtime"], params["skip"])
        finally:
            self.netskope_conn.close()
            output_handler.close()
        self.log.info(f''' Total messages fetched {params['skip'] - skip} for Event Type: {event_type}''')

    def build_task_params(self):

        tasks = []

        for et in itertools.chain(self.EVENT_TYPES, self.ALERT_TYPES):
            if self.kvstore.has_key(et):
                obj = self.kvstore.get(et)
                if obj["end_time_epoch"] is None:
                    obj = self.set_new_end_epoch_time(et, obj["start_time_epoch"])
            else:
                obj = self.set_new_end_epoch_time(et, self.DEFAULT_START_TIME_EPOCH)
            if obj is None:  # no new events so continue
                continue
            tasks.append(obj)
        self.log.info(f'''Building tasks {len(tasks)}''')
        return tasks

    def run(self):
        self.log.info('Starting Netskope Event Forwarder...')
        task_params = self.build_task_params()
        all_futures = {}
        with futures.ThreadPoolExecutor(max_workers=self.config['Collection']['NUM_WORKERS']) as executor:
            results = {executor.submit(self.fetch, **param): param for param in task_params}
            all_futures.update(results)
        for future in futures.as_completed(all_futures):
            param = all_futures[future]
            event_type = param["event_type"]
            try:
                future.result()
                obj = self.kvstore.get(event_type)
            except Exception as exc:
                self.log.error(f'''Event Type: {event_type} thread generated an exception: {exc}''', exc_info=True)
            else:
                self.log.info(f'''Event Type: {event_type} thread completed {obj}''')

    def test(self):
        params = {
            "start_time_epoch": 1505228760,
            "end_time_epoch": int(time.time()),
            'url': self.NETSKOPE_EVENT_ENDPOINT,
            "event_type": "Application",
            "skip": 0
        }
        self.fetch(**params)


def main():
    try:
        ns = NetskopeCollector()
        ns.run()
        # ns.test()
    except BaseException as e:
        traceback.print_exc()


if __name__ == '__main__':
    main()

