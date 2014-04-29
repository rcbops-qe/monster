from time import sleep
import chef


def node_search(query, environment=None, tries=10):
    """Performs a node search query on the chef_ server.
    :param query: search query to request
    :type query: string
    :param environment: Environment the query should be
    :type environment: ChefEnvironment
    :rtype: Iterator (chef_.Node)
    """
    if environment:
        api = environment.local_api
    else:
        api = chef.autoconfigure()
    search = None
    while not search and tries > 0:
        search = chef.Search("node", api=api).query(query)
        sleep(10)
        tries -= 1
    return (n.object for n in search)
