import inspect

from monster import util
from monster.config import Config
from monster.deployments.chef_deployment import Chef as ChefDeployment
from monster.provisioners.util import get_provisioner


def __load_deployment(function):
    def wrap_function(args):
        util.config = Config(args.config, args.secret_path)
        deployment = ChefDeployment.from_chef_environment(args.name)
        util.logger.debug("Loading deployment {0}".format(deployment))
        return function(deployment, args)
    return wrap_function

def __provision_for_deployment(function):
    def wrap_function(args):
        util.config = Config(args.config, args.secret_path)
        args.provisioner=get_provisioner(args.provisioner)
        return function(args)
    return wrap_function


def __log(function):
    def wrap_function(args):
        util.logger.setLevel(args.log_level)
        util.log_to_file(args.logfile_path)
        return function(args)
    return wrap_function

def __build_deployment(function):
    def wrap_function(args):
        util.logger.info("Building deployment object for %s" % args.name)
        util.logger.debug("Creating ChefDeployment with dict %s" % args)
        try:
            args.deployment = ChefDeployment.fromfile(**vars(args))
        except TypeError as error:
            util.logger.critical(
                str(error) +
                "ChefDeployment.fromfile was called with \n{0},\n but "
                "expects at least the following non-none : {1}."
                .format(vars(args),
                        inspect.getargspec(ChefDeployment.fromfile)[0][1:]))
            exit(1)
        return function(args)
    return wrap_function