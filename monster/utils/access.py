import cStringIO
import os
import socket
import subprocess
import sys
import time
import paramiko
import logging


logger = logging.getLogger(__name__)


def check_port(host, port, timeout=2):
    logger.debug("Testing connection to - {0}:{1}".format(host, port))
    ssh_up = False
    while not ssh_up:
        try:
            s = socket.create_connection((host, port), timeout)
            s.close()
        except socket.error:
            ssh_up = False
            logger.debug("Waiting for ssh connection...")
            time.sleep(1)
        else:
            ssh_up = True
    return ssh_up


def get_file(ip, user, password, remote, local, remote_delete=False):
    cmd1 = 'sshpass -p {0} scp -q {1} {2}'.format(password, remote, local)
    subprocess.call(cmd1, shell=True)
    if remote_delete:
        cmd2 = ("sshpass -p {0} ssh -o UserKnownHostsFile=/dev/null "
                "-o StrictHostKeyChecking=no -o LogLevel=quiet -l {1} {2}"
                " 'rm *.xml;exit'".format(password, user, ip))
        subprocess.call(cmd2, shell=True)


def get_paramiko_ssh_client():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
    return ssh


def scp_from(ip, remote_path, user='root', password=None, local_path=""):
    """
    :param remote_path: file to copy
    :param local_path: place on localhost to place file
    """
    ssh = get_paramiko_ssh_client()
    ssh.connect(ip, username=user, password=password, allow_agent=False)
    sftp = ssh.open_sftp()
    sftp.get(remote_path, local_path)


def scp_to(ip, local_path, user='root', password=None, remote_path=""):
    """Send a file to a server.
    :param local_path: file on localhost to copy
    :param remote_path: destination to copy to
    """
    ssh = get_paramiko_ssh_client()
    ssh.connect(ip, username=user, password=password, allow_agent=False)
    sftp = ssh.open_sftp()
    sftp.put(local_path, remote_path)


def ssh_cmd(server_ip, remote_cmd, user='root', password=None):
    """
    :param server_ip
    :param user
    :param password
    :param remote_cmd
    :return A map based on pass / fail run info
    """
    output = cStringIO.StringIO()
    error = cStringIO.StringIO()
    ssh = get_paramiko_ssh_client()
    ssh.connect(server_ip, username=user, password=password, allow_agent=False)
    stdin, stdout, stderr = ssh.exec_command(remote_cmd)
    stdin.close()
    for line in stdout:
        if logger < 10:
            logger.debug(line)
            sys.stdout.write(line)
        logger.info(line.strip())
        output.write(line)
    for line in stderr:
        logger.error(line.strip())
        error.write(line)
    exit_status = stdout.channel.recv_exit_status()
    ret = {'success': True if exit_status == 0 else False,
           'return': output.getvalue(),
           'exit_status': exit_status,
           'error': error.getvalue()}
    return ret


def run_cmd(command):
    """
    @param command
    @return A map based on pass / fail run info
    """
    logger.info("Running: {0}".format(command))
    try:
        ret = subprocess.check_call(command, shell=True, env=os.environ)
        return {'success': True, 'return': ret, 'exception': None}
    except subprocess.CalledProcessError, cpe:
        return {'success': False,
                'return': None,
                'exception': cpe,
                'command': command}
