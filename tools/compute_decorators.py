import inspect

from monster import util
from monster.config import Config
from monster.deployments.chef_deployment import Chef as ChefDeployment
from monster.provisioners.util import get_provisioner


def __load_deployment(function):
    def wrap_function(args):
        util.config = Config(args.config, args.secret_path)
        args.deployment = ChefDeployment.from_chef_environment(args.name)
        util.logger.debug("Loading deployment {0}".format(args.deployment))
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
        except TypeError:
            util.logger.critical(
                "ChefDeployment.fromfile was called with \n{0},\n but "
                "expects at least the following non-none : {1}."
                .format(vars(args),
                        inspect.getargspec(ChefDeployment.fromfile)[0][1:]))
            exit(1)
        else:
            util.logger.info(args.deployment)
        return function(args.deployment, args)
            util.info(args.deployment)
        expected_arguments = inspect.getargspec(function)[0]
        arguments_to_pass = {k: v for k, v in vars(args).iteritems()
                             if k in expected_arguments}
        return function(**arguments_to_pass)
    return wrap_function

