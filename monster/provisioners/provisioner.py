class Provisioner(object):

    def available_node(self, image, deployment):
        raise NotImplementedError

    def destroy_node(self, node):
        raise NotImplementedError
