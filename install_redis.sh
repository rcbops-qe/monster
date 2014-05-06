apt-get install -y git python-pip virtualenvwrapper python-dev libevent-dev python-software-properties > /dev/null;
add-apt-repository -y ppa:rwky/redis
apt-get update
apt-get install -y redis-server
