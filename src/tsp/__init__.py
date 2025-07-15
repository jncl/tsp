""" Setup logging for all modules """
import logging
import sys
logger = logging.getLogger(__name__)

# logging.basicConfig(filename='tsp.log', level=logging.INFO)

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
                    level=logging.DEBUG,
                    stream=sys.stdout)

# Set version
__version__ =  "2.0"


print("__init__.py run")
