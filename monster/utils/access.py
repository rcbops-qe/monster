import cStringIO
import os
import socket
import subprocess
import sys
import time
import paramiko
import logging


logger = logging.getLogger(__name__)


def check_port(host, port, timeout=2, attempts=100):
    logger.debug("Testing connection to - {0}:{1}".format(host, port))
    for attempt in xrange(attempts):
        try:
            s = socket.create_connection((host, port), timeout)
            s.close()
        except socket.error:
            logger.debug("Waiting for ssh connection...")
            time.sleep(0.5)
        else:
            logger.debug("Connection successful to {host}:{port}".
                         format(host=host, port=port))
            ssh_up = True
            break
    else:
        raise Exception("Connection unsuccessful to {host}:{port}"
                        .format(host=host, port=port))
    return ssh_up


def get_file(ip, user, password, remote, local, remote_delete=False):
    cmd1 = 'sshpass -p {0} scp -q {1} {2}'.format(password, remote, local)
    subprocess.call(cmd1, shell=True)
    if remote_delete:
        cmd2 = ("sshpass -p {0} ssh -o UserKnownHostsFile=/dev/null "
                "-o StrictHostKeyChecking=no -o LogLevel=quiet -l {1} {2}"
                " 'rm *.xml; exit'".format(password, user, ip))
        subprocess.call(cmd2, shell=True)


def get_paramiko_ssh_client():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return ssh


def scp_from(ip, remote_path, local_path, user, password=None):
    """
    :param remote_path: file to copy
    :param local_path: place on localhost to place file
    """
    logger.info("SCP: {host}:{path} to {local}"
                .format(host=ip, path=remote_path, local=local_path))

    ssh = get_paramiko_ssh_client()
    ssh.connect(ip, username=user, password=password, allow_agent=False)
    sftp = ssh.open_sftp()
    sftp.get(remote_path, local_path)


def scp_to(ip, local_path, remote_path, user, password=None):
    """Send a file to a server.
    :param local_path: file on localhost to copy
    :param remote_path: destination to copy to
    """
    logger.info("SCP: {local} to {host}:{path}"
                .format(local=local_path, host=ip, path=remote_path))

    ssh = get_paramiko_ssh_client()
    ssh.connect(ip, username=user, password=password, allow_agent=False)
    sftp = ssh.open_sftp()
    sftp.put(local_path, remote_path)


def ssh_cmd(server_ip, remote_cmd, user='root', password=None, attempts=5,
            hostname=""):
    """
    :param server_ip
    :param user
    :param password
    :param remote_cmd
    :return A map based on pass / fail run info
    """
    remote_log_string = ("IP: %(ip)-17s HOST: %(host)-23s " %
                         {"ip": server_ip, "host": hostname})

    output = cStringIO.StringIO()
    error = cStringIO.StringIO()
    ssh = get_paramiko_ssh_client()
    for attempt in range(attempts):
        try:
            ssh.connect(server_ip, username=user, password=password,
                        allow_agent=False)
            break
        except (EOFError, socket.error):
            logger.info(remote_log_string + "Error connecting; retrying...")
            time.sleep(0.5)
    else:
        logger.exception(remote_log_string + "Ran out of connection attempts!")
    logger.info(remote_log_string + "Running: " + remote_cmd)
    stdin, stdout, stderr = ssh.exec_command(remote_cmd)
    stdin.close()
    for line in stdout:
        if logger < 10:
            logger.debug(remote_log_string + line)
            sys.stdout.write(line)
        logger.info(remote_log_string + line.strip())
        output.write(line)
    for line in stderr:
        logger.error(remote_log_string + line.strip())
        error.write(line)
    exit_status = stdout.channel.recv_exit_status()
    result = {'success': True if exit_status == 0 else False,
              'return': output.getvalue(),
              'exit_status': exit_status,
              'error': error.getvalue()}
    return result


def run_cmd(command):
    """
    :param command
    :return A map based on pass / fail run info
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
