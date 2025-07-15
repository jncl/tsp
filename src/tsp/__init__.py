""" Setup logging for all modules """
import logging
logger = logging.getLogger(__name__)

logging.basicConfig(filename='tsp.log', level=logging.DEBUG)

# logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
#                     level=logging.DEBUG,
#                     stream=sys.stdout)

# Set version
__version__ =  "2.0"
