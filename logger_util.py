import logging
import os
from datetime import datetime

class GUILogger(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        if self.callback:
            self.callback(msg)

def setup_logger(gui_callback=None):
    logger = logging.getLogger("ScraperAgent")
    logger.setLevel(logging.DEBUG)

    # File handler
    file_handler = logging.FileHandler("workflow_logs.txt", mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Remove existing handlers to avoid duplicate logs if setup_logger is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.addHandler(file_handler)

    # GUI callback handler
    if gui_callback:
        gui_handler = GUILogger(gui_callback)
        gui_handler.setLevel(logging.INFO)
        logger.addHandler(gui_handler)
        
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(file_formatter)
    logger.addHandler(console_handler)

    return logger
