import json
import logging
import requests

from time import sleep

from monster.nodes.util import node_search
from provisioner import Provisioner

from monster import util

logger = logging.getLogger(__name__)


class Razor(Provisioner):
    """Provisions chef nodes in a Razor environment."""

    def __init__(self, ip=None):
        self.ipaddress = ip or util.config['secrets']['razor']['ip']
        self.api = RazorAPI(self.ipaddress)

    def provision(self, template, deployment):
        """Provisions a ChefNode using Razor environment.
        :param template: template for cluster
        :type template: dict
        :param deployment: ChefDeployment to provision for
        :type deployment: ChefDeployment
        :rtype: list
        """
        logger.info("Provisioning with Razor!")
        image = deployment.os_name
        self.nodes += [self.available_node(image, deployment)
                       for _ in template['nodes']]
        return self.nodes

    def available_node(self, image, deployment):
        """Provides a free node from chef pool.
        :param image: name of os image
        :type image: string
        :param deployment: ChefDeployment to add node to
        :type deployment: ChefDeployment
        :rtype: ChefNodeWrapper
        """
        # TODO: Should probably search on system name node attributes
        # Avoid specific naming of razor nodes, not portable
        nodes = node_search("name:qa-%s-pool*" % image)
        for node in nodes:
            is_default = node.chef_environment == "_default"
            iface_in_run_list = "recipe[network-interfaces]" in node.run_list
            if is_default and iface_in_run_list:
                node.chef_environment = deployment.environment.name
                node['in_use'] = "provisioning"
                node.save()
                return node
        deployment.destroy()
        raise Exception("No more nodes!!")

    def power_down(self, node):
        if node.has_feature('controller'):
            # rabbit can cause the node to not actually reboot
            kill = ("for i in `ps -U rabbitmq | tail -n +2 | "
                    "awk '{print $1}' `; do kill -9 $i; done")
            node.run_cmd(kill)
        node.run_cmd("shutdown -r now")

    def power_up(self, node):
        pass

    def destroy_node(self, node_wrapper):
        """Destroys a node provisioned by Razor.
        :param node_wrapper: Node to destroy
        :type node_wrapper: ChefNodeWrapper
        """
        node = node_wrapper.local_node
        in_use = node_wrapper['in_use']
        if in_use == "provisioning" or in_use == 0:
            # Return to pool if the node is clean
            node['in_use'] = 0
            node['archive'] = {}
            node.chef_environment = "_default"
            node.save()
        else:
            # Remove active model if the node is dirty
            active_model = node['razor_metadata']['razor_active_model_uuid']
            try:
                if node_wrapper.has_feature('controller'):
                    # rabbit can cause the node to not actually reboot
                    kill = ("for i in `ps -U rabbitmq | tail -n +2 | "
                            "awk '{print $1}' `; do kill -9 $i; done")
                    node_wrapper.run_cmd(kill)
                node_wrapper.run_cmd("shutdown -r now")
                self.api.remove_active_model(active_model)
                node_wrapper.client.delete()
                node.delete()
                sleep(15)
            except:
                logger.error("Node unreachable. "
                             "Manual restart required:{0}".format(str(node)))


class RazorAPI(object):

    def __init__(self, rzrip, rzrport='8026'):
        """Initializer for RazorAPI class."""

        self.ip = rzrip
        self.port = rzrport
        self.url = "http://{0}:{1}/razor/api".format(self.ip, self.port)

    def __repr__(self):
        """Print out current instance of RazorAPI."""

        outl = 'class: {0}'.format(self.__class__.__name__)
        for attr in self.__dict__:
            outl += '\n\t{0}:{1}'.format(attr, str(getattr(self, attr)))
        return outl

    def images(self):

        # Call the Razor RESTful API to get a list of models
        headers = {'content-type': 'application/json'}
        r = requests.get('{0}/model'.format(self.url), headers=headers)

        # Check the status code and return appropriately
        if r.status_code == 200:
            return json.loads(r.content)
        else:
            return 'Error: exited with status code: {0}'.format(
                str(r.status_code))

    def nodes(self):

        # Call the Razor RESTful API to get a list of models
        headers = {'content-type': 'application/json'}
        r = requests.get('{0}/node'.format(self.url), headers=headers)

        # Check the status code and return appropriately
        if r.status_code == 200:
            return json.loads(r.content)
        else:
            return 'Error: exited with status code: {0}'.format(
                str(r.status_code))

    def model_templates(self):

        # Call the Razor RESTful API to get a list of models
        headers = {'content-type': 'application/json'}
        r = requests.get('{0}/model/templates'.format(self.url),
                         headers=headers)

        # Check the status code and return appropriately
        if r.status_code == 200:
            return json.loads(r.content)
        else:
            return 'Error: exited with status code: {0}'.format(
                str(r.status_code))

    def models(self):
        """ This function returns the whole model json returned by Razor."""

        # Call the Razor RESTful API to get a list of models
        headers = {'content-type': 'application/json'}
        r = requests.get('{0}/model'.format(self.url), headers=headers)

        # Check the status code and return appropriately
        if r.status_code == 200:
            return json.loads(r.content)
        else:
            return 'Error: exited with status code: {0}'.format(
                str(r.status_code))

    def simple_models(self, uuid=None):
        """
        This returns a smaller, simpler set of information
        about the models returned by Razor.
        """

        # Call the Razor RESTful API to get a list of models
        headers = {'content-type': 'application/json'}

        if uuid is None:
            r = requests.get('{0}/model'.format(self.url), headers=headers)
            if r.status_code == 200:
                return json.loads(r.content)
            else:
                return 'Error: exited with status code: {0}'.format(
                    str(r.status_code))
        else:
            r = requests.get('{0}/model/{1}'.format(self.url, uuid),
                             headers=headers)
            if r.status_code == 200:
                return self.build_simple_model(json.loads(r.content))
            else:
                return 'Error: exited with status code: {0}'.format(
                    str(r.status_code))

    def build_simple_model(self, razor_json):
        """
        This will return the current available
        model in a simple minimal info json
        """

        # loop through all the nodes and take the simple info from them
        for response in razor_json['response']:
            model = {'name': response['@name'],
                     'root_password': response['@root_password'],
                     'current_state': response['@current_state'],
                     'uuid': response['@uuid'],
                     'label': response['@label']}

        return model

    def active_models(self, filter=None):
        """
         This return the whole json returned
        by the Razor API for a single active model.
        """

        if filter is None:
            url = '{0}/active_model'.format(self.url)
        else:
            url = '{0}/active_model?label={1}'.format(self.url, filter)

        # make the request to get active models from Razor
        headers = {'content-type': 'application/json'}
        r = requests.get(url, headers=headers)

        # Check the status code and return appropriately
        if r.status_code == 200:
            return json.loads(r.content)
        else:
            return 'Error: exited with status code: {0}'.format(
                str(r.status_code))

    def simple_active_models(self, filter=None):
        """
        This will return all the active
        models with an easy to consume JSON
        """
        # make the request to get active models from Razor

        am_content = self.active_models(filter)

        #print json.dumps(am_content, indent=4)

        # Check the status code and return appropriately
        if 'response' in am_content.keys():
            active_models = {}
            for response in am_content['response']:

                # get info from razor about the active model
                headers = {'content-type': 'application/json'}
                r = requests.get(
                    '{0}/active_model/{1}'.format(
                        self.url, response['@uuid']
                    ),
                    headers=headers
                )
                single_am_content = json.loads(r.content)
                #print json.dumps(single_am_content, indent=2)
                active_models[response['@uuid']] = \
                    self.build_simple_active_model(single_am_content)

            return active_models
        else:
            return 'Error: exited with status code: {0}'.format(
                str(r.status_code))

    def build_simple_active_model(self, razor_json):
        """
        This will return an active model JSON
        that is simplified from the Razor API json
        """

        # step through the json and gather simplified information
        for item in razor_json['response']:

            if item['@broker'] is not None:
                broker = item['@broker']['@name']
            else:
                broker = None
            model = item['@model']
            node = model['@node']
            active_model = {'node_uuid': item['@node_uuid'],
                            'am_uuid': item['@uuid'],
                            'description': model['@description'],
                            'root_password': model['@root_password'],
                            'current_state': model['@current_state'],
                            'final_state': model['@final_state'],
                            'broker': broker,
                            'bind_number': model['@counter'],
                            'hostname_prefix':
                            model['@hostname_prefix'],
                            'domain': model['@domainname']}
            try:
                hdwnic_count = int(
                    node['@attributes_hash']['mk_hw_nic_count'])
                active_model['nic_count'] = hdwnic_count
                # Get the active network interface ips
                for i in range(0, hdwnic_count):
                    try:
                        mac_eth_str = 'macaddress_eth{0}'.format(i)
                        mac_eth = node['@attributes_hash'][mac_eth_str]
                        active_model['eth{0}_mac'.format(i)] = mac_eth
                    except KeyError:
                        pass

                    try:
                        eth_str = 'ipaddress_eth{0}'.format(i)
                        eth_ip = node['@attributes_hash'][eth_str]
                        active_model['eth{0}_ip'.format(i)] = eth_ip
                    except KeyError:
                        pass
            except:
                print "Error getting nic count"
                print "Model: {0} ".format(model)
        return active_model

    def active_ready(self, razor_json):
        """
        This method will return all the online complete servers
        """

        servers = []

        # step through the json and gather simplified information
        for item in razor_json:
            r_item = razor_json[item]
            model = item['@model']
            if 'complete' in r_item['current_state']:
                ready_server = {'description': r_item['description'],
                                'node_uuid': r_item['node_uuid'],
                                'am_uuid': r_item['am_uuid'],
                                'root_passwd': r_item['root_password'],
                                'broker': r_item['broker'],
                                'bind_number': model['@counter'],
                                'hostname_prefix': model['@hostname_prefix'],
                                'domain': model['@domainname']}
                for x in range(0, r_item['nic_count']):
                    try:
                        eth_ip = r_item['eth{0}_ip'.format(x)]
                        ready_server['eth{0}_ip_addr'.format(x)] = eth_ip
                    except:
                        pass
                    try:
                        eth_mac = r_item['eth{0}_mac'.format(x)]
                        ready_server['eth{0}_mac'.format(x)] = eth_mac
                    except:
                        pass

                servers.append(ready_server)

        return servers

    def broker_success(self, razor_json):
        """
        This method will return all the online broker complete servers
        """

        servers = []
        # step through the json and gather simplified information
        for item in razor_json:
            r_item = razor_json[item]
            model = item['@model']
            if 'broker_success' in r_item['current_state']:
                ready_server = {'description': r_item['description'],
                                'node_uuid': r_item['node_uuid'],
                                'am_uuid': r_item['am_uuid'],
                                'root_passwd': r_item['root_password'],
                                'broker': r_item['broker'],
                                'bind_number': model['@counter'],
                                'hostname_prefix': model['@hostname_prefix'],
                                'domain': model['@domainname']
                                }
                for x in range(0, r_item['nic_count']):
                    try:
                        eth_ip = r_item['eth{0}_ip'.format(x)]
                        ready_server['eth{0}_ip_addr'.format(x)] = eth_ip
                    except:
                        pass
                    try:
                        eth_mac = r_item['eth{0}_mac'.format(x)]
                        ready_server['eth{0}_mac'.format(x)] = eth_mac
                    except:
                        pass

                servers.append(ready_server)

        return servers

    def remove_active_model(self, am_uuid):
        """This method removes an active model from Razor."""

        # Call the Razor RESTful API to get a list of models
        headers = {'content-type': 'application/json'}
        r = requests.delete('{0}/active_model/{1}'.format(self.url, am_uuid),
                            headers=headers)

        return {'status': r.status_code, 'content': json.loads(r.content)}

    def remove_active_models(self, am_uuids):
        """This method loops through a list of am uuids and removes each."""

        removed_servers = []
        for uuid in am_uuids:
            removed_servers.append(self.remove_active_model(uuid))

        return removed_servers

    def get_active_model_pass(self, am_uuid):
        """ This function will get an active models password """
        headers = {'content-type': 'application/json'}
        r = requests.get('{0}/active_model/{1}'.format(self.url, am_uuid),
                         headers=headers)

        passwd = ''
        if r.status_code == 200:
            content_json = json.loads(r.content)
            passwd = content_json['response'][0]['@model']['@root_password']

        return {'status_code': r.status_code, 'password': passwd}
