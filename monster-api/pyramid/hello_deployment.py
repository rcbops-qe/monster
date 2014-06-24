from paste.httpserver import serve
from pyramid.config import Configurator
from pyramid.response import Response

import monster.executable
import json

# TODO (james): this only works in a single process; it should either kick off
#  a new process or subprocess to touch the app


def list_deployments(request):
    # deployments = monster.executable.list_deployments()
    return Response()


def build_rpcs(request):
    request_dict = json.loads(request.body)
    request_dict.update(request.matchdict)
    deployment = monster.executable.rpcs_build(**request_dict)
    return Response(json.dumps(deployment.to_dict))


def show(request):
    deployment = monster.executable.show(request.matchdict['name'])
    return Response(json.dumps(deployment.to_dict))


def delete(request):
    name = request.matchdict['name']
    try:
        monster.executable.destroy(name)
    except:
        Response("Failure!")
    else:
        Response("{} deleted!".format(name))


if __name__ == '__main__':
    config = Configurator()
    config.add_route('rpcs', '/rpcs/deployment/{name}')
    config.add_view(build_rpcs, route_name='rpcs', request_method='POST')
    config.add_view(show, route_name='rpcs', request_method='GET')
    config.add_view(delete, route_name='rpcs', request_method='DELETE')
    app = config.make_wsgi_app()
    serve(app, host='0.0.0.0')
