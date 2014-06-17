from monster import active


def name_node(name, deployment):
    """Helper for naming nodes.
    :param name: name for node
    :type name: str
    :param deployment: deployment object
    :type deployment: monster.deployments.base.Deployment
    :rtype: str
    """
    root = "{0}-{1}".format(deployment.name, name)
    if root not in active.node_names:
        active.node_names.add(root)
        return root
    else:
        counter = 2
        name = root
        while name in active.node_names:
            name = "{prefix}{suffix}".format(prefix=root, suffix=counter)
            counter += 1
        active.node_names.add(name)
        return name
