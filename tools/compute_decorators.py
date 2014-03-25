import inspect
import sys

from functools import wraps

from monster import util
from monster.util import Logger
from monster.config import Config
from monster.deployments.chef_deployment import Chef as ChefDeployment
from monster.provisioners.util import get_provisioner

logger = Logger(__name__)


def __load_deployment(func):
    logger.set_log_level()
    @wraps(func)
    def wrap_function(args):
        util.config = Config(args.config, args.secret_path)
        args.deployment = ChefDeployment.from_chef_environment(args.name)
        logger.debug("Loading deployment {0}".format(args.deployment))
        expected_arguments = inspect.getargspec(func)[0]
        arguments_to_pass = {k: v for k, v in vars(args).iteritems()
                             if k in expected_arguments}
        return func(**arguments_to_pass)
    return wrap_function


def __provision_for_deployment(func):
    logger.set_log_level()
    @wraps(func)
    def wrap_function(args):
        util.config = Config(args.config, args.secret_path)
        args.provisioner = get_provisioner(args.provisioner)
        return func(args)
    return wrap_function


def __build_deployment(func):
    logger.set_log_level()
    @wraps(func)
    def wrap_function(args):
        if 'template_file' in args.__dict__:
            args.template_file = __get_template_filename(args.branch)

        logger.info("Building deployment object for %s" % args.name)
        logger.debug("Creating ChefDeployment with dict %s" % args)
        expected_arguments = inspect.getargspec(ChefDeployment.fromfile)[0]
        arguments_to_pass = {k: v for k, v in vars(args).iteritems()
                             if k in expected_arguments}
        try:
            args.deployment = ChefDeployment.fromfile(**arguments_to_pass)
        except TypeError as e:
            logger.error(
                "ChefDeployment.fromfile was called with \n{0},\n but "
                "expects at least the following non-none : {1}."
                .format(vars(args),
                        inspect.getargspec(ChefDeployment.fromfile)[0][1:]))
            logger.critical(e)
            sys.exit(1)
        else:
            logger.info(args.deployment)
        names_of_arguments_to_pass = inspect.getargspec(func)[0]
        arguments_to_pass = {k: v for k, v in vars(args).iteritems()
                             if k in names_of_arguments_to_pass}
        return func(**arguments_to_pass)
    return wrap_function


def __get_template_filename(branch):
    logger.set_log_level()
    if branch == "master":
        filename = "default"
    else:
        filename = branch.lstrip('v').rstrip("rc").replace('.', '_')
    return filename
