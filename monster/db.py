import subprocess
import logging
import redis

logger = logging.getLogger(__name__)


def start_db():
    logger.debug("Attempting to start db.")
    subprocess.call("redis-server")


def ping_db():
    logger.debug("Pinging redis...")
    ping = "redis-cli -p 6379 ping".split()
    if subprocess.check_output(ping) == "PONG\n":
        logger.debug("Redis responded normally.")
    else:
        logger.debug("Redis did not respond normally.")
        raise AssertionError()


def get_connection():
    """:rtype: redis.StrictRedis """
    return db

try:
    ping_db()
except:
    logger.warning("Database not responding normally to pings.")
    try:
        start_db()
        ping_db()
    except:
        logger.exception("Database still not responsive.  Exiting.")


db = redis.StrictRedis(host='localhost', port=6379, db=0)
