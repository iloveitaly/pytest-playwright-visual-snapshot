from structlog_config import configure_logger

logger = configure_logger()


def main():
    logger.info("Hello, Logs!")
