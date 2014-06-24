import inspect
import logging

import dill as pickle
from decorator import decorator

import monster.db as database


logger = logging.getLogger(__name__)
db = database.get_connection()


def remove_key(build_name):
    logger.info("Removing %s from redis..." % build_name)
    db.delete(build_name)
    logger.info("Redis no longer has a %s key." % build_name)


@decorator
def store_build_params(f, *args):
    arg_names = inspect.getargspec(f).args
    db_hash = {k: v for k, v in zip(arg_names, args)}
    db.hmset(db_hash['name'], db_hash)
    return f(*args)


@decorator
def store_upgrade_params(f, *args):
    arg_names = inspect.getargspec(f).args
    db_hash = {k: v for k, v in zip(arg_names, args)}
    db.hmset(db_hash['name'], db_hash)
    return f(*args)


def ping_db():
    database.ping_db()


def store(deployment):
    return db.hset(deployment.name, "deployment-obj", pickle.dumps(deployment))


def list_deployments():
    temp = {}
    for key in db.keys():
        if 'deployment-obj' in db.hgetall(key):
            temp[key] = pickle.loads(db.hget(key, "deployment-obj"))
    return temp


def fetch_deployment(name):
    deployment = pickle.loads(db.hget(name, "deployment-obj"))
    assert deployment != {}
    return deployment


def fetch_config_params(name):
    config, secret = db.hmget(name, ['config', 'secret'])
    return config, secret


def fetch_template_params(name):
    branch, template = db.hmget(name, ['branch', 'template'])
    return branch, template


def fetch_build_args(name):
    return db.hgetall(name)
