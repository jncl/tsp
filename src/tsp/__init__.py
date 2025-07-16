""" Setup logging for all modules """
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(filename='/var/log/tsp/tsp.log', level=logging.DEBUG)

# Set version
__version__ =  "2.0"
