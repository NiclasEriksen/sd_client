import os
import logging
import datetime

log_level = logging.INFO
log_level_env = os.environ.get("SD_LOG_LEVEL", "info")

PROGRESS_LEVEL = 9
if log_level_env == "debug":
    log_level = PROGRESS_LEVEL


logging.addLevelName(PROGRESS_LEVEL, "PROGRESS")
def progressv(self, message, *args, **kws):
    if self.isEnabledFor(PROGRESS_LEVEL):
        # Yes, logger takes its '*args' as 'args'.
        self._log(PROGRESS_LEVEL, message, args, **kws)

logging.Logger.progress = progressv

logger = logging.getLogger(__name__)
logger.setLevel(PROGRESS_LEVEL)


# Define format for logs
fmt_1 = "%(asctime)s"
fmt_2 = "%(levelname)s"
fmt_3 = "%(message)s"
fmt = fmt_1 + "| " + "%(levelname)8s" + " |" + fmt_3

# Create file handler for logging to a file (logs all five levels)
today = datetime.date.today()
file_handler = logging.FileHandler(os.path.join("logs", "client_{}.log".format(today.strftime("%Y_%m_%d"))))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(fmt))


class CustomFormatter(logging.Formatter):
    """Logging colored formatter, adapted from https://stackoverflow.com/a/56944256/3638629"""

    black = '\x1b[30;1m'
    grey = '\x1b[38;21m'
    blue = '\x1b[38;5;39m'
    yellow = '\x1b[38;5;226m'
    red = '\x1b[38;5;196m'
    bold_red = '\x1b[31;1m'
    reset = '\x1b[0m'

    def __init__(self, fmt1, fmt2, fmt3):
        super().__init__()
        self.fmt = fmt1 + "|" + fmt2 + "|" + fmt3
        self.FORMATS = {
            PROGRESS_LEVEL: fmt2 + "|" + fmt3,
            logging.DEBUG: self.grey + fmt1 + "|" + self.grey + fmt2 + self.reset + "| " + fmt3,
            logging.INFO: self.grey + fmt1 + "|" + self.blue + fmt2 + self.reset + "| " + fmt3,
            logging.WARNING: self.grey + fmt1 + "|" + self.yellow + fmt2 + self.reset + " |" + fmt3,
            logging.ERROR: self.grey + fmt1 + "|" + self.red + fmt2 + self.reset + "| " + fmt3,
            logging.CRITICAL: self.grey + fmt1 + "|" + self.bold_red + fmt2 + self.reset + "| " + fmt3,
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, "%H:%M:%S")
        return formatter.format(record)

stdout_handler = logging.StreamHandler()
stdout_handler.setLevel(PROGRESS_LEVEL)
stdout_handler.setFormatter(CustomFormatter(fmt_1, fmt_2, fmt_3))

logger.addHandler(stdout_handler)
logger.addHandler(file_handler)
