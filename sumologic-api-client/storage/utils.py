import sys
import logging
import logging.handlers as handlers

#Todo make these in parameter
LOG_FORMAT = "%(levelname)s | %(asctime)s | %(threadName)s | %(name)s | %(message)s"
LOG_FILEPATH = "/tmp/sumoapiclient.log"
ENABLE_FILEHANDLER = True
EXCLUDED_MODULE_LOGGING = ("requests", "urllib3")
ROTATION_TYPE = "D"  # use H for hourly W6 for weekly(ie Sunday)
ROTATION_INTERVAL = 10  # in hours


def get_logger(name=__name__):

    log = logging.getLogger(name)
    if not log.handlers:

        log.setLevel(logging.DEBUG)
        logFormatter = logging.Formatter(LOG_FORMAT)

        consoleHandler = logging.StreamHandler(sys.stdout)
        consoleHandler.setFormatter(logFormatter)
        log.addHandler(consoleHandler)
        if ENABLE_FILEHANDLER:
            filehandler = handlers.TimedRotatingFileHandler(
                LOG_FILEPATH, backupCount=5,
                when=ROTATION_TYPE, interval=ROTATION_INTERVAL,
                # encoding='bz2',  # uncomment for bz2 compression
            )
            # filehandler = logging.FileHandler()
            filehandler.setFormatter(logFormatter)
            log.addHandler(filehandler)

        #disabling logging for requests/urllib3
        for module_name in EXCLUDED_MODULE_LOGGING:
            logging.getLogger(module_name).setLevel(logging.WARNING)
    return log
