import time
import chef


def node_search(query, environment=None, tries=10):
    """Performs a node search query on the chef server.
    :param query: search query to request
    :type query: string
    :param environment: Environment the query should be
    :type environment: monster.environments.chef.environment.Environment
    :rtype: Iterator (chef.Node)
    """
    if environment:
        api = environment.local_api
    else:
        api = chef.autoconfigure()
    search = None
    while not search and tries > 0:
        search = chef.Search("node", api=api).query(query)
        time.sleep(10)
        tries -= 1
    return (n.object for n in search)
