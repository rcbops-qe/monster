import sys
from cStringIO import StringIO
from paramiko import SSHClient, AutoAddPolicy
from subprocess import check_call, CalledProcessError

from monster import util


def run_cmd(command):
    """
    @param cmd
    @return A map based on pass / fail run info
    """
    util.logger.info("Running: {0}".format(command))
    try:
        ret = check_call(command, shell=True)
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
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    ssh.connect(ip, username=user, password=password)
    stdin, stdout, stderr = ssh.exec_command(remote_cmd)
    stdin.close()
    for line in stdout:
        if util.logger < 10:
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
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    ssh.connect(ip, username=user, password=password)
    sftp = ssh.open_sftp()
    sftp.put(local_path, remote_path)


def scp_from(ip, remote_path, user=None, password=None, local_path=""):
    """
    @param path_to_file: file to copy
    @param copy_location: place on localhost to place file
    """

    command = ("sshpass -p %s scp "
               "-o Self.UserKnownHostsFile=/dev/null "
               "-o StrictHostKeyChecking=no "
               "-o LogLevel=quiet "
               "%s@%s:%s %s") % (password,
                                 user, ip,
                                 remote_path,
                                 local_path)

    try:
        ret = check_call(command, shell=True)
        return {'success': True,
                'return': ret,
                'exception': None}
    except CalledProcessError, cpe:
        return {'success': False,
                'return': None,
                'exception': cpe,
                'command': command}
