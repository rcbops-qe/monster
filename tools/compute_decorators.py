import inspect
import sys

from monster import util
from monster.config import Config
from monster.deployments.chef_deployment import Chef as ChefDeployment
from monster.provisioners.util import get_provisioner

logger = util.get_logger("{0}.log".format(__name__))

def __load_deployment(function):
    def wrap_function(args):
        util.config = Config(args.config, args.secret_path)
        args.deployment = ChefDeployment.from_chef_environment(args.name)
        logger.debug("Loading deployment {0}".format(args.deployment))
        expected_arguments = inspect.getargspec(function)[0]
        arguments_to_pass = {k: v for k, v in vars(args).iteritems()
                             if k in expected_arguments}
        return function(**arguments_to_pass)
    return wrap_function


def __provision_for_deployment(function):
    def wrap_function(args):
        util.config = Config(args.config, args.secret_path)
        args.provisioner = get_provisioner(args.provisioner)
        return function(args)

    return wrap_function


def __log(function):
    def wrap_function(args):
        logger.setLevel(args.log_level)
        log_to_file(args.logfile_path)
        return function(args)

    return wrap_function


def __build_deployment(function):
    def wrap_function(args):
        if not args.template_file:
            args.template_file = __get_template_filename(args.branch)

        logger.info("Building deployment object for %s" % args.name)
        logger.debug("Creating ChefDeployment with dict %s" % args)
        try:
            args.deployment = ChefDeployment.fromfile(**vars(args))
        except TypeError:
            logger.critical(
                "ChefDeployment.fromfile was called with \n{0},\n but "
                "expects at least the following non-none : {1}."
                .format(vars(args),
                        inspect.getargspec(ChefDeployment.fromfile)[0][1:]))
            sys.exit(1)
        else:
            logger.info(args.deployment)
        names_of_arguments_to_pass = inspect.getargspec(function)[0]
        arguments_to_pass = vars(args).fromkeys(names_of_arguments_to_pass)
        return function(**arguments_to_pass)
    return wrap_function


def __get_template_filename(branch):
    if branch == "master":
        filename = "default"
    else:
        filename = branch.lstrip('v').rstrip("rc").replace('.', '_')
    return filename
