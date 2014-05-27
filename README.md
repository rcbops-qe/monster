# Monster

An OpenStack Orchestration Engine

### Installation
1. Use the [monster installer](https://github.com/rcbops-qa/monster-installer.git).  Then, run `pip install -e .` from the project root.

   **or**

2. Clone the repo and setup manually.
```
git clone https://github.com/rcbops-qa/monster.git ~/monster
virtualenv -p `which python2` ~/monster/.venv
source ~/monster/.venv/bin/activate
~/monster/install_redis.sh
pip install -r ~/monster/requirements.txt -e ~/monster
```

**Note:** On a small servers, we have experienced gevent installation failures due to insufficient memory. Adding swap
may resolve these issues.

- Credentials should be saved in `monster/data/secret.yaml`.  An example `secret.yaml` file can be found at `monster/data/examples/secret.example`.


---------------------------------------

## CLI

**build**

Deploy an OS cluster.

```
monster build rpcs my_build -t ubuntu-ha-neutron -c pubcloud-neutron.yaml -b v4.1.5 -p rackspace
```

**show**

Show details about an OS deployment.

```
monster show my_build
```

**destroy**

Destroy an OS deployment.

```
monster destroy my_build
```

**openrc**

Load openrc environment variables into shell. Once loaded,
openstack CLI commands will communicate to cluster.

```
monster openrc my_build
nova boot --image cirros-image --flavor 1
```

**horizon**

Open Horizon in browser.

```
monster horizon my_build
```

**test**

Run tests on an OS cluster.

```
monster test cloudcafe my_build
```
```
monster test ha my_build
```
```
monster test tempest my_build
```

**upgrade**

Upgrade the deployment to the specified branch.

```
monster upgrade my_build -u v4.2.1
```

**tmux**

Open a tmux session with each node in a different window.

```
monster tmux my_build
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
from monster.utils.ipython import load
deployment = load("my_build")
```

#### CLI

For development convenience, the CLI is also accessible from the project root by using `monster/executable.py`.  For example, we can profile a build by using the command
```
python -m cProfile -s time -o build_profile.txt monster/executable.py build rpcs my_build -t ubuntu-ha-neutron
```
