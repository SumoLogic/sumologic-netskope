import time
from datetime import datetime
from logger import get_logger


def get_current_timestamp():

    return int(time.time())


def convert_epoch_to_date(timestamp):
    log = get_logger(__name__)
    try:
        date_str = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        log.error(f'''Error in converting timestamp {timestamp}''', exc_info=True)
        date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    return date_str

