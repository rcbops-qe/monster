# Monster

An OpenStack Orchestration Engine

### Installation
1. Use the [monster installer](https://github.com/rcbops-qa/monster-installer.git).

   **or**

2. Clone the repo and setup manually.
```
git clone https://github.com/rcbops-qa/monster.git ~/monster
virtualenv -p `which python2` ~/monster/.venv
source ~/monster/.venv/bin/activate
pip install -r ~/monster/requirements.txt
```

**Note:** On a small servers, we have experienced gevent installation failures due to insufficient memory. Adding swap
may resolve these issues.

- Credentials should be saved in `monster/secret.yaml`.  An example `secret.yaml` file can be found at `monster/examples/secret.yaml`.

### Post-install

From the project root, run `python setup.py install`.

---------------------------------------

## CLI

#### build
Deploy an OS cluster.

```
monster build rpcs -n my_build -t ubuntu-ha-neutron -c pubcloud-neutron.yaml -b v4.1.5 -p rackspace
```

#### show
Show details about an OS deployment.

```
monster show -n my_build
```

#### destroy
Destroy an OS deployment.

```
monster destroy -n my_build
```

#### openrc
Load openrc environment variables into shell. Once loaded,
openstack CLI commands will communicate to cluster.

```
monster openrc -n my_build
```

```
nova boot --image cirros-image --flavor 1
```

#### horizon
Open Horizon in browser.

```
monster horizon -n my_build
```

#### test
Run tests on an OS cluster.

```
monster test cloudcafe -n my_build
```
```
monster test ha -n my_build
```
```
monster test tempest -n my_build
```

#### upgrade
Upgrade the deployment to the specified branch.

```
monster upgrade -n my_build -u v4.2.1 -c pubcloud-neutron.yaml
```

#### tmux
Open a tmux session with each node in a different window.

```
monster tmux -n my_build -c pubcloud-neutron.yaml
```

**Requires tmux version >= 1.8**

To add a 12.4 precise tmux 1.8 backport PPA, execute the following:

```
add-apt-repository -y ppa:kalakris/tmux
apt-get update
apt-get install tmux -y
```

---------------------------------------

## Development

#### iPython
To make development of monster easier you can load deployment objects in iPython.

1. Start `ipython` in top monster directory
2. Run:
```python
from tools.ipython import load
deployment = load("my_build", "configs/pubcloud-neutron.yaml")
```

#### CLI

For development convienence, the CLI is also accessible from the project root by using `monster/executable.py`.  For example,
```
monster/executable.py build rpcs -n my_build -t ubuntu-ha-neutron
```
