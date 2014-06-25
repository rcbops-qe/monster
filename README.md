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

### top-level commands

**status**

Verifies that all dependant services are up and running and that secret credentials authenticate.

```
monster status
```


### deployment-level commands

**list**

List all current deployments.

```
monster deployment list
```

**build**

Deploy an OS cluster.

```
monster deployment build rpcs my_build -t ubuntu-ha-neutron -c pubcloud-neutron.yaml -b v4.1.5 -p rackspace
```

**show**

Show details about an OS deployment.

```
monster deployment show my_build
```

**update**

Runs package updates on deployment nodes.

```
monster deployment update my_build
```

**explore**

Opens up an ipython shell with a deployment object loaded.

```
monster deployment explore my_build
```


**destroy**

Destroy an OS deployment.

```
monster deployment destroy my_build
```

**openrc**

Load openrc environment variables into shell. Once loaded,
openstack CLI commands will communicate to cluster.

```
monster deployment openrc my_build
nova boot --image cirros-image --flavor 1
```

**horizon**

Open Horizon in browser.

```
monster deployment horizon my_build
```

**test**

Run tests on an OS cluster.

```
monster deployment test cloudcafe my_build
```
```
monster deployment test ha my_build
```
```
monster deployment test tempest my_build
```

**upgrade**

Upgrade the deployment to the specified branch.

```
monster deployment upgrade my_build -u v4.2.1
```

**tmux**

Open a tmux session with each node in a different window.

```
monster deployment tmux my_build
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

#### CLI

For development convenience, the CLI is also accessible from the project root by using `monster/executable.py`.  For example, we can profile a build by using the command
```
python -m cProfile -s time -o build_profile.txt monster/executable.py build rpcs my_build -t ubuntu-ha-neutron
```
