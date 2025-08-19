# logging_config.py
import logging
import sys

def setup_logging(level=logging.DEBUG):
    handler = logging.StreamHandler(sys.stderr)  # <--- stderr so we don't break MCP
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"
    )
    handler.setFormatter(formatter)

    logging.basicConfig(level=level, handlers=[handler])
