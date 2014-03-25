#! /usr/bin/env python

import argparse


class CLI:
    @classmethod
    def parser(self, commands):
        parser = argparse.ArgumentParser(
            description="Monster deployment and testing tool. Developed"
                        " for Rackspace Private Cloud QE.")
        subparsers = parser.add_subparsers()

        build_parser = subparsers.add_parser('build')
        build_parser.add_argument('-t', '--template-name', default='ubuntu-ha')
        build_parser.add_argument('-T', '--template-path')
        build_parser.add_argument('-b', '--branch', default='master')
        build_parser.add_argument('-p', '--provisioner', default='rackspace')
        build_parser.add_argument('-d', '--dry', action='store_true')
        build_parser.set_defaults(func=commands['build'])

        retrofit_parser = subparsers.add_parser('retrofit')
        retrofit_parser.add_argument('-r', '--retro-branch')
        retrofit_parser.add_argument('-o', '--ovs-brige')
        retrofit_parser.add_argument('-x', '--x-bridge')
        retrofit_parser.add_argument('-i', '--interface')
        retrofit_parser.add_argument('-d', '--delete-port')
        retrofit_parser.set_defaults(func=commands['retrofit'])

        destroy_parser = subparsers.add_parser('destroy')
        destroy_parser.set_defaults(func=commands['destroy'])

        upgrade_parser = subparsers.add_parser('upgrade')
        upgrade_parser.add_argument('-u', '--upgrade_branch',
                                    choices=['v4.1.3rc', 'v4.2.2rc'],
                                    required=True)
        upgrade_parser.set_defaults(func=commands['upgrade'])

        openrc_parser = subparsers.add_parser('openrc')
        openrc_parser.set_defaults(func=commands['openrc'])

        horizon_parser = subparsers.add_parser('horizon')
        horizon_parser.set_defaults(func=commands['horizon'])

        show_parser = subparsers.add_parser('show')
        show_parser.set_defaults(func=commands['show'])

        test_parser = subparsers.add_parser('test')
        test_parser.add_argument('-d', '--deployment')
        test_parser.add_argument(
            '-i', '--iterations', default=1,
            help='Iterations to run each selected test suite.  If nothing '
            'is specified, each selected test suite will be ran once.')
        test_to_run = test_parser.add_mutually_exclusive_group(required=True)
        test_to_run.add_argument('-a', '--all', action='store_const',
                                 help='Run all applicable tests.',
                                 const='all', dest='tests_to_run')
        test_to_run.add_argument('--ha', '--HA', action='store_const',
                                 help='Run only HA tests.',
                                 const='ha', dest='tests_to_run')
        test_to_run.add_argument('--tempest', '--tp', action='store_const',
                                 help='Run only Tempest tests.',
                                 const='tempest', dest='tests_to_run')
        test_to_run.add_argument('--cloudcafe', '--cc', action='store_const',
                                 help='Run only CloudCAFE tests.',
                                 const='cloudcafe', dest='tests_to_run')
        test_parser.add_argument('-p', '--provider_net',
                                 default='b6901fd8-4751-'
                                         '4f4d-8267-136e4b5ee111')
        test_parser.set_defaults(func=commands['test'])

        tmux_parser = subparsers.add_parser('tmux')
        tmux_parser.set_defaults(func=commands['tmux'])

        def add_common_arguments(parser):
            parser.add_argument('-n', '--name', help="Name of the OpenStack "
                                                     "deployment.")
            parser.add_argument('-c', '--config',
                                default='pubcloud-neutron.yaml')
            parser.add_argument('-s', '--secret-path', default='secret.yaml')
            parser.add_argument('-l', '--logfile-path', default='./log')
            parser.add_argument('-L', '--log-level',
                                choices=['DEBUG', 'INFO', 'WARNING',
                                         'ERROR', 'CRITICAL'],
                                default='DEBUG')
        map(add_common_arguments, subparsers.choices.values())
        return parser
