import os
import socket
import sys

from cStringIO import StringIO
from paramiko import SSHClient, WarningPolicy
from subprocess import check_call, CalledProcessError
from time import sleep

from monster import util


class Command(object):
    def __init__(self, command):
        self.command = command
        self.successful = False
        self.output = None
        self.exception = None


def check_port(host, port, timeout=2):
    util.logger.debug("Testing connection to : {0}:{1}".format(host, port))
    ssh_up = False
    while not ssh_up:
        try:
            s = socket.create_connection((host, port), timeout)
            s.close()
            ssh_up = True
        except socket.error:
            ssh_up = False
            util.logger.debug("Waiting for ssh connection...")
            sleep(1)
    return ssh_up


def run_cmd(command):
    """
    @param cmd
    @return A map based on pass / fail run info
    """
    util.logger.info("Running: {0}".format(command))
    try:
        ret = check_call(command, shell=True, env=os.environ)
        return {'success': True, 'return': ret, 'exception': None}
    except CalledProcessError, cpe:
        return {'success': False,
                'return': None,
                'exception': cpe,
                'command': command}


def ssh_cmd(ip, remote_cmd, user='root', password=None):
    """
    @param server_ip
    @param user
    @param password
    @param remote_cmd
    @return A map based on pass / fail run info
    """
    output = StringIO()
    error = StringIO()
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(WarningPolicy())
    ssh.connect(ip, username=user, password=password, allow_agent=False)
    stdin, stdout, stderr = ssh.exec_command(remote_cmd)
    stdin.close()
    for line in stdout:
        if util.logger < 10:
            util.logger.debug(line)
            sys.stdout.write(line)
        util.logger.info(line.strip())
        output.write(line)
    for line in stderr:
        util.logger.error(line.strip())
        error.write(line)
    exit_status = stdout.channel.recv_exit_status()
    ret = {'success': True if exit_status == 0 else False,
           'return': output.getvalue(),
           'exit_status': exit_status,
           'error': error.getvalue()}
    return ret


def scp_to(ip, local_path, user='root', password=None, remote_path=""):
    """
    Send a file to a server
    """
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(WarningPolicy())
    ssh.connect(ip, username=user, password=password, allow_agent=False)
    sftp = ssh.open_sftp()
    sftp.put(local_path, remote_path)


def scp_from(ip, remote_path, user='root', password=None, local_path=""):
    """
    @param path_to_file: file to copy
    @param copy_location: place on localhost to place file
    """
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(WarningPolicy())
    ssh.connect(ip, username=user, password=password, allow_agent=False)
    sftp = ssh.open_sftp()
    sftp.get(remote_path, local_path)
