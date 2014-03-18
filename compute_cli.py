#! /usr/bin/env python

from IPython import embed
import argparse
class CLI:
    @classmethod
    def parser(self, commands):
        parser=argparse.ArgumentParser(
            description="Monster deployment and testing tool. Developed"
                        " for Rackspace Private Cloud QE.")
        subparsers = parser.add_subparsers()

        build_parser=subparsers.add_parser('build')
        build_parser.add_argument('-t', '--template-name', default='ubuntu-ha')
        build_parser.add_argument('-T', '--template-file', default='default')
        build_parser.add_argument('-b', '--branch', default='master')
        build_parser.add_argument('-p', '--provisioner', default='rackspace')
        build_parser.add_argument('-d', '--dry', action='store_true')
        build_parser.set_defaults(func=commands['build'])

        retrofit_parser=subparsers.add_parser('retrofit')
        retrofit_parser.add_argument('-r', '--retro-branch')
        retrofit_parser.add_argument('-o', '--ovs-brige')
        retrofit_parser.add_argument('-x', '--x-bridge')
        retrofit_parser.add_argument('-i', '--interface')
        retrofit_parser.add_argument('-d', '--delete-port')
        retrofit_parser.set_defaults(func=commands['retrofit'])

        destroy_parser=subparsers.add_parser('destroy')
        destroy_parser.set_defaults(func=commands['destroy'])

        upgrade_parser=subparsers.add_parser('upgrade')
        upgrade_parser.add_argument('-u', '--upgrade_branch',
                                    choices=['v4.1.3rc','v4.2.2rc'],
                                    required=True)
        upgrade_parser.set_defaults(func=commands['upgrade'])

        openrc_parser=subparsers.add_parser('openrc')
        openrc_parser.set_defaults(func=commands['openrc'])

        horizon_parser=subparsers.add_parser('horizon')
        horizon_parser.set_defaults(func=commands['horizon'])

        show_parser=subparsers.add_parser('show')
        show_parser.set_defaults(func=commands['show'])

        test_parser=subparsers.add_parser('test')
        test_parser.add_argument('-d', '--deployment')
        test_parser.add_argument('-i', '--iterations', default=1)
        test_to_run=test_parser.add_mutually_exclusive_group(required=True)
        test_to_run.add_argument('-a', '--all')
        test_to_run.add_argument('--HA', '--ha')
        test_to_run.add_argument('--tp', '--tempest')
        test_to_run.add_argument('--oc', '--opencafe')
        test_parser.add_argument('--pn', 'provider_net',
                default='6241dfe9-11fe-45e7-b39d-45ef88f5d9cb')
        test_parser.set_defaults(func=commands['test'])

        tmux_parser=subparsers.add_parser('tmux')
        tmux_parser.set_defaults(func=commands['tmux'])

        def add_common_arguments(parser):
            parser.add_argument('-n', '--name')
            parser.add_argument('-c', '--config', default='rspc.yaml')
            parser.add_argument('-s', '--secret-path', default='secret.yaml')
            parser.add_argument('-l', '--logfile-path', default='./log')
            parser.add_argument('-L', '--log-level',
                                choices=['DEBUG', 'INFO', 'WARNING',
                                         'ERROR', 'CRITICAL'],
                                default='DEBUG')
        map(add_common_arguments, subparsers.choices.values())
<<<<<<< HEAD
        return parser
=======
        return parser
>>>>>>> james | moving things around...
