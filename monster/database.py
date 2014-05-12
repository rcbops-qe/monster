import subprocess
import inspect

from decorator import decorator
import redis

assert subprocess.check_output("redis-cli -p 6379 ping") == "PONG"

db = redis.StrictRedis(host='localhost', port=6379, db=0)


def get_connection():
    """:rtype: redis.StrictRedis """
    return db


@decorator
def store_build_params(f, *args):
    arg_names = inspect.getargspec(f).args
    data = {k: v for k, v in zip(arg_names, args)}
    db.hmset(data['name'], data)
    return f(*args)
