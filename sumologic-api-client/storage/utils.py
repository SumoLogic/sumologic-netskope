import sys
import logging
import logging.handlers as handlers

#Todo make these in parameter
EXCLUDED_MODULE_LOGGING = ("requests", "urllib3")
LOG_FORMAT = "%(levelname)s | %(asctime)s | %(threadName)s | %(name)s | %(message)s"
LOG_FILEPATH = "/tmp/sumoapiclient.log"
ROTATION_TYPE = "D"  # use H for hourly W6 for weekly(ie Sunday)
ROTATION_INTERVAL = 10  # in hours


def get_logger(name, log_format=LOG_FORMAT, log_filepath=LOG_FILEPATH, rotation_type=ROTATION_TYPE,rotation_interval= ROTATION_INTERVAL, filehdlr=True, consolehdlr=False):
    name = name or __name__
    log = logging.getLogger(name)
    if not log.handlers:

        log.setLevel(logging.DEBUG)
        logFormatter = logging.Formatter(log_format)

        if consolehdlr:
            consoleHandler = logging.StreamHandler(sys.stdout)
            consoleHandler.setFormatter(logFormatter)
            log.addHandler(consoleHandler)
        if filehdlr:
            filehandler = handlers.TimedRotatingFileHandler(
                log_filepath, backupCount=5,
                when=rotation_type, interval=rotation_interval,
                # encoding='bz2',  # uncomment for bz2 compression
            )
            # filehandler = logging.FileHandler()
            filehandler.setFormatter(logFormatter)
            log.addHandler(filehandler)

        #disabling logging for requests/urllib3
        for module_name in EXCLUDED_MODULE_LOGGING:
            logging.getLogger(module_name).setLevel(logging.WARNING)
    return log
