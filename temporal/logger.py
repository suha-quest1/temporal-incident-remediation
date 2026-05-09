import logging

# config
logging.basicConfig(
    # filename='app.log',
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

logger = logging.getLogger("incident-logger")
