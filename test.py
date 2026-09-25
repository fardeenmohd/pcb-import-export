import logging
from processor import run_pipeline
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger("ScraperAgent")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

run_pipeline(["https://www.sahasraelectronics.com"], logger, "test_output.xlsx")
