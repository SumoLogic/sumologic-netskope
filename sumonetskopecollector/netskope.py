# -*- coding: future_fstrings -*-
import os
import traceback
import sys
import time
import itertools
import copy
from concurrent import futures
from sumoappclient.sumoclient.base import BaseCollector
from sumoappclient.omnistorage.factory import ProviderFactory
from sumoappclient.sumoclient.factory import OutputHandlerFactory
from sumoappclient.sumoclient.httputils import ClientMixin, SessionPool
from sumoappclient.common.utils import get_current_timestamp, convert_epoch_to_utc_date


class NetskopeCollector(BaseCollector):

    SINGLE_PROCESS_LOCK_KEY = 'is_netskopecollector_running'
    CONFIG_FILENAME = "netskope.yaml"

    def __init__(self):
        self.project_dir = self.get_current_dir()
        super(NetskopeCollector, self).__init__(self.project_dir)
        self.api_config = self.config['Netskope']
        self.netskope_conn = SessionPool(self.collection_config['MAX_RETRY'], self.collection_config['BACKOFF_FACTOR'], logger=self.log)
        self.DEFAULT_START_TIME_EPOCH = get_current_timestamp() - self.collection_config['BACKFILL_DAYS']*24*60*60

    def get_current_dir(self):
        cur_dir = os.path.dirname(__file__)
        return cur_dir

    def get_endpoint_url(self, event_type):
        if event_type in self.api_config['ALERT_TYPES']:
            return self.api_config['NETSKOPE_ALERT_ENDPOINT']
        else:
            return self.api_config['NETSKOPE_EVENT_ENDPOINT']

    def set_fetch_state(self, event_type, start_time_epoch, end_time_epoch, last_record_epoch=None, skip=0):
        if end_time_epoch:  # end time epoch could be none in cases where no event is present
            assert start_time_epoch <= end_time_epoch
        obj = {
            "skip": skip,
            'url': self.get_endpoint_url(event_type),
            "event_type": event_type,
            "start_time_epoch": start_time_epoch,
            "end_time_epoch": end_time_epoch,
            "last_record_epoch": last_record_epoch
        }

        self.kvstore.set(event_type, obj)
        return obj

    def set_new_end_epoch_time(self, event_type, start_time_epoch):
        params = {
            'token': self.api_config['TOKEN'],
            'limit': 1,
            'starttime': start_time_epoch,
            'endtime': get_current_timestamp(),
            'skip': 0,
            'type': event_type
        }
        url = self.get_endpoint_url(event_type)
        sess = self.netskope_conn.get_request_session()
        success, respjson = ClientMixin.make_request(url, method=self.api_config['FETCH_METHOD'], session=sess, params=params, logger=self.log, TIMEOUT=self.collection_config['TIMEOUT'], MAX_RETRY=self.collection_config['MAX_RETRY'], BACKOFF_FACTOR=self.collection_config['BACKOFF_FACTOR'])
        self.netskope_conn.close()
        start_date = convert_epoch_to_utc_date(params['starttime'])
        end_date = convert_epoch_to_utc_date(params['endtime'])
        if success and respjson["status"] == "success" and len(respjson["data"]) > 0:
            obj = self.set_fetch_state(event_type, start_time_epoch, respjson["data"][0]["timestamp"], respjson["data"][0]["timestamp"])
            self.log.info(f'''Creating task for {event_type} from {start_date} to {end_date}''')
            return obj
        else:
            self.log.info(f'''No events are available for {event_type} from {start_date} to {end_date}''')
            return None

    def is_running(self):
        self.log.info("Acquiring single instance lock")
        return self.kvstore.acquire_lock(self.SINGLE_PROCESS_LOCK_KEY)

    def stop_running(self):
        self.log.info("Releasing single instance lock")
        return self.kvstore.release_lock(self.SINGLE_PROCESS_LOCK_KEY)

    def transform_data(self, data):
        return data

    def get_last_record_epoch(self, old_request_params):
        params = copy.copy(old_request_params)
        params['skip'] -= 1
        url = self.get_endpoint_url(params['type'])
        sess = self.netskope_conn.get_request_session()
        success, respjson = ClientMixin.make_request(url, method=self.api_config['FETCH_METHOD'], session=sess, params=params, logger=self.log, TIMEOUT=self.collection_config['TIMEOUT'], MAX_RETRY=self.collection_config['MAX_RETRY'], BACKOFF_FACTOR=self.collection_config['BACKOFF_FACTOR'])
        self.netskope_conn.close()
        start_date = convert_epoch_to_utc_date(params['starttime'])
        end_date = convert_epoch_to_utc_date(params['endtime'])
        if success and respjson["status"] == "success" and len(respjson["data"]) > 0:
            last_record_epoch = respjson["data"][0]["timestamp"]
            last_record_date = convert_epoch_to_utc_date(last_record_epoch)
            self.log.info(f'''last record for {event_type} from {start_date} to {end_date} skip: {params['skip']} is {last_record_date}''')
            return last_record_epoch
        else:
            raise Exception(f'''last record for {event_type} from {start_date} to {end_date} skip: {params['skip']} not found''')

    def reset_skip(self, params, last_record_epoch):
        NETSKOPE_SKIP_MAX_LIMIT = 500000
        if params['skip'] + params['limit'] >= NETSKOPE_SKIP_MAX_LIMIT:
            if not last_record_epoch:
                last_record_epoch = self.get_last_record_epoch(params)
            params['skip'] = 0
            params['endtime'] = last_record_epoch
            last_record_date = convert_epoch_to_utc_date(last_record_epoch)
            self.log.info(f'''Resetting skip to {last_record_date}''')
        return last_record_epoch

    def fetch(self, url, event_type, start_time_epoch, end_time_epoch, last_record_epoch, skip):

        params = {
            'token': self.api_config['TOKEN'],
            'limit': self.api_config['PAGINATION_LIMIT'],
            'starttime': start_time_epoch,
            'endtime': end_time_epoch,
            'skip': skip,
            'type': event_type
        }
        output_handler = OutputHandlerFactory.get_handler(self.config['Collection']['OUTPUT_HANDLER'], config=self.config)
        next_request = send_success = True
        page_count = total_records = 0
        move_window = False
        sess = self.netskope_conn.get_request_session()
        try:
            while next_request:
                last_record_epoch = self.reset_skip(params, last_record_epoch)
                page_count += 1
                fetch_success, respjson = ClientMixin.make_request(url, method=self.api_config['FETCH_METHOD'], session=sess, params=params, logger=self.log, TIMEOUT=self.collection_config['TIMEOUT'], MAX_RETRY=self.collection_config['MAX_RETRY'], BACKOFF_FACTOR=self.collection_config['BACKOFF_FACTOR'])
                fetch_success = fetch_success and respjson["status"] == "success"  # netskope sends 200 for errors
                if fetch_success:
                    data = respjson["data"]
                    if len(data) > 0:
                        data = self.transform_data(data)
                        send_success = output_handler.send(data)
                        if send_success:
                            params['skip'] += len(data)
                            total_records += len(data)
                            last_record_epoch = data[-1]["timestamp"]
                            self.log.info(f'''Successfully Sent Page: {page_count} Event Type: {event_type} Datalen: {len(
                                data)} starttime: {convert_epoch_to_utc_date(
                                params['starttime'])} endtime: {convert_epoch_to_utc_date(params['endtime'])} skip: {params['skip']} last_record_epoch: {convert_epoch_to_utc_date(last_record_epoch)}''')

                    else:  # no data so moving window
                        move_window = True

                next_request = fetch_success and send_success and (not move_window)
                if move_window:
                    self.log.debug(
                        f'''Moving starttime window for {event_type} to {convert_epoch_to_utc_date(params["endtime"] + 1)}''')
                    self.set_fetch_state(event_type, end_time_epoch+1, None, None)
                elif not (fetch_success and send_success):  # saving skip in casee of failures for restarting in future
                    self.set_fetch_state(event_type, params["starttime"], params["endtime"], last_record_epoch, params["skip"])
                    self.log.error(
                        f'''Failed to send Event Type: {event_type} Page: {page_count} starttime: {convert_epoch_to_utc_date(params['starttime'])} endtime: {convert_epoch_to_utc_date(params['endtime'])} fetch_success: {fetch_success} send_success: {send_success} skip: {params['skip']} last_record_epoch: {last_record_epoch}''')
        except Exception as e:
            self.set_fetch_state(event_type, params["starttime"], params["endtime"], last_record_epoch, params["skip"])
            raise e
        finally:
            self.netskope_conn.close()
            output_handler.close()
        self.log.info(f''' Total messages fetched {total_records} for Event Type: {event_type} starttime: {convert_epoch_to_utc_date(params['starttime'])} endtime: {convert_epoch_to_utc_date(params['endtime'])}''')

    def build_task_params(self):

        tasks = []

        for et in itertools.chain(self.api_config['ALERT_TYPES'], self.api_config['EVENT_TYPES']):
            if self.kvstore.has_key(et):
                obj = self.kvstore.get(et)
                if obj["end_time_epoch"] is None:
                    obj = self.set_new_end_epoch_time(et, obj["start_time_epoch"])
            else:
                self.set_fetch_state(et, self.DEFAULT_START_TIME_EPOCH, None) # setting start time initially otherwise it always fetches in range(cur time, cur time)
                obj = self.set_new_end_epoch_time(et, self.DEFAULT_START_TIME_EPOCH)
            if obj is None:  # no new events so continue
                continue
            if "last_record_epoch" not in obj:
                # for backward compatibility
                obj["last_record_epoch"] = None

            tasks.append(obj)
        self.log.info(f'''Building tasks {len(tasks)}''')
        return tasks

    def run(self):
        if self.is_running():
            try:
                self.log.info('Starting Netskope Event Forwarder...')
                task_params = self.build_task_params()
                all_futures = {}
                log_types = ",".join([t['event_type'] for t in task_params])
                self.log.info("spawning %d workers for log types: %s" % (self.config['Collection']['NUM_WORKERS'], log_types))
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
            finally:
                self.stop_running()
                self.netskope_conn.closeall()
        else:
            if not self.is_process_running(["sumonetskopecollector", "netskope.py"]):
                self.kvstore.release_lock_on_expired_key(self.SINGLE_PROCESS_LOCK_KEY)

    def test(self):
        params = {
            "start_time_epoch": 1505228760,
            "end_time_epoch": int(time.time()),
            'url': self.api_config['NETSKOPE_EVENT_ENDPOINT'],
            "event_type": "Application",
            "skip": 0
        }

        self.fetch(**params)


def main(*args, **kwargs):
    try:
        ns = NetskopeCollector()
        ns.run()
        # ns.test()
    except BaseException as e:
        traceback.print_exc()


if __name__ == '__main__':
    main()

