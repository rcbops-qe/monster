import sys
import pytest
import monster.executable


@pytest.mark.tryfirst
def test_build():
    sys.argv = ("monster build rpcs test-build -t ubuntu-ha-neutron "
                "-c pubcloud-neutron.yaml -b v4.1.5 -p rackspace").split()
    monster.executable.run()


def test_show():
    sys.argv = "monster show test-build".split()
    monster.executable.run()


def test_upgrade():
    sys.argv = "monster upgrade test-build -b v4.2.2".split()
    monster.executable.run()


@pytest.mark.trylast
def test_destroy():
    sys.argv = "monster destroy test-build".split()
    monster.executable.run()
