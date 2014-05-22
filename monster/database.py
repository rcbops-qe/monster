import subprocess
import inspect
import logging
import pickle

from decorator import decorator
import redis

logger = logging.getLogger(__name__)


def start_db():
    logger.info("Attempting to start db.")
    subprocess.call("redis-server")


def ping_db():
    logger.info("Pinging redis...")
    ping = "redis-cli -p 6379 ping".split()
    if subprocess.check_output(ping) == "PONG\n":
        logger.info("Redis responded normally.")
    else:
        raise AssertionError()


def remove_key(build_name):
    logger.info("Removing %s from redis..." % build_name)
    db.delete(build_name)
    logger.info("Redis no longer has a %s key." % build_name)


def get_connection():
    """:rtype: redis.StrictRedis """
    return db


@decorator
def store_build_params(f, *args):
    arg_names = inspect.getargspec(f).args
    data = {k: v for k, v in zip(arg_names, args)}
    db.hmset(data['name'], data)
    return f(*args)

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


def store(deployment):
    return db.hset(deployment.name, "deployment-obj", pickle.dumps(deployment))


def load_deployment(name):
    return pickle.loads(db.hget(name, "deployment-obj"))
