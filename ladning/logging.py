import logging
import sys

# Create the ladning logger instance
log = logging.getLogger("ladning")
log.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(asctime)s (%(levelname)s): %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
log.addHandler(handler)

# Also log output from PyEasee for debugging purposes
pyeasee_logger = logging.getLogger("pyeasee")
pyeasee_logger.setLevel(logging.DEBUG)
pyeasee_logger.addHandler(handler)
