import requests
import json
import sys
import os
import time
from datetime import datetime
import itertools
from concurrent import futures
from utils import get_logger
from factory import ProviderFactory
import threading
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError


LOG_FORMAT = "%(levelname)s | %(asctime)s | %(threadName)s | %(name)s | %(message)s"
LOG_FILEPATH = "/tmp/sumoapiclient.log"
ROTATION_TYPE = "D"  # use H for hourly W6 for weekly(ie Sunday)
ROTATION_INTERVAL = 10  # in hours

log = get_logger(__name__, LOG_FORMAT, LOG_FILEPATH, ROTATION_TYPE, ROTATION_INTERVAL)
ENVIRONMENT = "onprem"  # os.getenv("ENVIRONMENT")
op_cli = ProviderFactory.get_provider(ENVIRONMENT)
kvstore = op_cli.get_storage("keyvalue", name='netskope')

SUMO_ENDPOINT = "https://collectors.sumologic.com/receiver/v1/http/ZaVnC4dhaV3c2lXpQUdTVmhZCuUgXipErle8SCQ3A65JMSi2NpJLDKtYK6107eTlymPSYGokSpGvgQ1l2iyss3UIju8r6mwWVhTIglF25kJQZaoG4LzJUg=="   # os.getenv('SUMO_ENDPOINT')
TOKEN = "a6d1091edf887e9960f18078a439e364"  # os.getenv('TOKEN')
NETSKOPE_EVENT_ENDPOINT = "https://partners.goskope.com/api/v1/events"
NETSKOPE_ALERT_ENDPOINT = "https://partners.goskope.com/api/v1/alerts"
NUM_WORKERS = 8
PAGINATION_LIMIT = 100
MAX_RETRY = 3
BACKOFF_FACTOR = 1
TIMEOUT = 5
OUTPUTHANDLER = "HTTP" # HTTP/CONSOLE
EVENT_TYPES = ['page', 'application', 'audit', 'infrastructure']
ALERT_TYPES = ['Malware', "Malsite", "Compromised Credential", "Anomaly", "DLP", "Watchlist", "Quarantine", "Policy"]
FETCH_METHOD = "get"


def get_current_timestamp():
    return int(time.time())


DEFAULT_START_TIME_EPOCH = get_current_timestamp() - 360*24*60*60


class ClientMixin(object):

    @classmethod
    def get_new_session(cls):
        sess = requests.Session()
        retries = Retry(total=MAX_RETRY, backoff_factor=BACKOFF_FACTOR, status_forcelist=[502, 503, 504, 429])
        sess.mount('https://', HTTPAdapter(max_retries=retries))
        sess.mount('http://', HTTPAdapter(max_retries=retries))
        return sess

    @classmethod
    def make_request(cls, url, method="get", session=None, **kwargs):

        start_time = datetime.now()
        try:
            sess = session if session else self.get_new_session()
            resp = getattr(sess, method)(url, timeout=TIMEOUT, **kwargs)
            if 400 <= resp.status_code < 600:
                resp.reason = resp.text
            resp.raise_for_status()
            log.info(f'''fetched url: {url} status_code: {resp.status_code}''')
            if resp.status_code == 200:
                data = resp.json() if len(resp.content) > 0 else {}
                return True, data
            else:
                return False, resp.content
                log.error(f'''Request Failed: {resp.content} url: {url} status_code: {resp.status_code}''')
        except JSONDecodeError as err:
            log.error(f'''Error in Decoding response {err}''', exc_info=True)
        except requests.exceptions.HTTPError as err:
            log.error(f'''Http Error: {err} {resp.content} {resp.status_code} {params}''', exc_info=True)
        except requests.exceptions.ConnectionError as err:
            log.error(f'''Connection Error:{err} {resp.content} {resp.status_code} {params}''', exc_info=True)
        except requests.exceptions.Timeout as err:
            time_elapsed = datetime.datetime.now() - start_time
            log.error(f'''Timeout Error:{err} {resp.content} {resp.status_code} {params} {time_elapsed}''', exc_info=True)
        except requests.exceptions.RequestException as err:
            log.error(f'''Error: {err} {resp.content} {resp.status_code} {params}''', exc_info=True)

        return False, None


class SessionPool(object):
    # by default request library will not timeout for any request
    # session is not thread safe hence each thread gets new session
    def __init__(self, max_retry, backoff):
        self.sessions = {}
        self.max_retry = max_retry
        self.backoff = backoff

    def get_request_session(self):
        thread_id = threading.get_ident()
        if thread_id in self.sessions:
            return self.sessions[thread_id]
        else:
            log.info(f'''Creating session for {thread_id}''')
            sess = ClientMixin.get_new_session()
            self.sessions[thread_id] = sess
            return sess

    def closeall(self):
        log.info("Closing all sessions")
        for _, v in self.sessions.items():
            v.close()

    def close(self):
        thread_id = threading.get_ident()
        log.info(f'Deleting session for {thread_id}')
        if thread_id in self.sessions:
            self.sessions[thread_id].close()
            del self.sessions[thread_id]


conn = SessionPool(MAX_RETRY, BACKOFF_FACTOR)
sumoconn = SessionPool(MAX_RETRY, BACKOFF_FACTOR)


def http_send(data):
    if isinstance(data, list):
        out = [json.dumps(d) for d in data]
        out = '\n'.join(out)
    else:
        out = data
    log.info(f'posting size {sys.getsizeof(out)}')
    sess = sumoconn.get_request_session()
    headers = {'content-type': 'application/json', 'accept': 'application/json'}
    fetch_success, respjson = ClientMixin.make_request(SUMO_ENDPOINT, method="post",
                                                       session=sess, data=out,
                                                       headers=headers)
    if not fetch_success:
        log.error(f'''Error in Sending to Sumo {respjson.content}''')
        return False
    return True


def stdout_send(data):
    if isinstance(data, list):
        out = [json.dumps(d) for d in data]
        out = '\n'.join(out)
    else:
        out = data
    log.info(f'posting size {sys.getsizeof(out)}')
    print(out)
    return True


def get_endpoint_url(event_type):
    if event_type in ALERT_TYPES:
        return NETSKOPE_ALERT_ENDPOINT
    else:
        return NETSKOPE_EVENT_ENDPOINT


def set_fetch_state(event_type, start_time_epoch, end_time_epoch, skip=0):
    obj = {
        "skip": skip,
        'url': get_endpoint_url(event_type),
        "event_type": event_type,
        "start_time_epoch": start_time_epoch,
        "end_time_epoch": end_time_epoch
    }

    kvstore.set(event_type, obj)
    return obj


def set_new_end_epoch_time(event_type, start_time_epoch):
    params = {
        'token': TOKEN,
        'limit': 1,
        'starttime': start_time_epoch,
        'endtime': get_current_timestamp(),
        'skip': 0,
        'type': event_type
    }
    url = get_endpoint_url(event_type)
    sess = conn.get_request_session()
    success, respjson = ClientMixin.make_request(url, method=FETCH_METHOD, session=sess, params=params)
    if success and respjson["status"] == "success" and len(respjson["data"]) > 0:
        obj = set_fetch_state(event_type, start_time_epoch, respjson["data"][0]["timestamp"])
        return obj
    else:
        log.info(f'''No events are available from {convert_epoch_to_date(params['starttime'])} to {convert_epoch_to_date(params['endtime'])}''')
        return None


def output_handler(data, handler_type):
    handlers = {
        "HTTP": http_send,
        "CONSOLE": stdout_send
    }
    if handler_type in handlers:
        return handlers[handler_type](data)
    else:
        log.error(f"Invalid OUTPUTHANDLER {handler_type}")
        return False


def convert_epoch_to_date(timestamp):
    try:
        date_str = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        log.error(f'''Error in converting timestamp {timestamp}''', exc_info=True)
        date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    return date_str


def transform_data(data):
    # import random
    # srcip = ["216.161.180.148", "54.203.63.36"]
    # for d in data:
    #     d["timestamp"] = int(time.time())
    #     d["srcip"] = random.choice(srcip)
    return data


def fetch(url, event_type, start_time_epoch, end_time_epoch, skip):

    params = {
        'token': TOKEN,
        'limit': PAGINATION_LIMIT,
        'starttime': start_time_epoch,
        'endtime': end_time_epoch,
        'skip': skip,
        'type': event_type
    }

    next_request = fetch_success = send_success = True
    count = 0
    move_window = False
    while next_request:
        count += 1
        sess = conn.get_request_session()
        fetch_success, respjson = ClientMixin.make_request(url, method=FETCH_METHOD, session=sess, params=params)
        if fetch_success and respjson["status"] == "success":
            data = respjson["data"]
            if len(data) > 0:
                data = transform_data(data)
                send_success = output_handler(data, OUTPUTHANDLER)
                if send_success:
                    params['skip'] += len(data)
            else:     # no data so moving window
                move_window = True

        next_request = fetch_success and send_success and (not move_window)
        if move_window:
            log.info(f'''moving starttime window for {event_type} to {convert_epoch_to_date(params["endtime"]+1)}''')
            set_fetch_state(event_type, params["endtime"]+1, None)
        elif not (fetch_success and send_success):  # saving skip in casee of failures for restarting in future
            set_fetch_state(event_type, params["starttime"], params["endtime"], params["skip"])

        log.info(f'''Finished Fetching Page: {count} Event Type: {event_type} Datalen: {len(data)} Next_Request: {next_request} starttime: {convert_epoch_to_date(start_time_epoch)} endtime: {convert_epoch_to_date(end_time_epoch)}''')
    log.info(f''' Total messages fetched {params['skip'] - skip} for Event Type: {event_type}''')


def build_task_params():
    global kvstore
    tasks = []

    for et in itertools.chain(EVENT_TYPES, ALERT_TYPES):
        if kvstore.has_key(et):
            obj = kvstore.get(et)
            if obj["end_time_epoch"] is None:
                obj = set_new_end_epoch_time(et, obj["start_time_epoch"])
        else:
            obj = set_new_end_epoch_time(et, DEFAULT_START_TIME_EPOCH)
        if obj is None:  # no new events so continue
            continue
        tasks.append(obj)
    log.info(f'''building tasks {len(tasks)}''')
    return tasks


def run():
    log.info('Starting Netskope Event Forwarder...')
    task_params = build_task_params()
    all_futures = {}
    with futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        results = {executor.submit(fetch, **param): param for param in task_params}
        all_futures.update(results)
    for future in futures.as_completed(all_futures):
        param = all_futures[future]
        event_type = param["event_type"]
        try:
            future.result()
            obj = kvstore.get(event_type)
        except Exception as exc:
            log.error(f'''Event Type: {event_type} thread generated an exception: {exc}''', exc_info=True)
        else:
            log.info(f'''Event Type: {event_type} thread completed {obj}''')
        finally:
            conn.close()


def test():
    params = {
        "start_time_epoch": 1505228760,
        "end_time_epoch": int(time.time()),
        'url': NETSKOPE_EVENT_ENDPOINT,
        "event_type": "Application",
        "skip": 0
    }
    fetch(**params)


if __name__ == '__main__':
    run()
    # test()
