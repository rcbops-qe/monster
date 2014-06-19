from paste.httpserver import serve
from pyramid.config import Configurator
from pyramid.response import Response

import monster.executable
import json


def build_rpcs(request):
    request_dict = json.loads(request.body)
    request_dict.update(request.matchdict)
    deployment = monster.executable.rpcs_build(**request_dict)
    return Response(json.dumps(deployment.to_dict))


def show_rpcs(request):
    deployment = monster.executable.show(request.matchdict['name'])
    return Response(json.dumps(deployment.to_dict))


if __name__ == '__main__':
    config = Configurator()
    config.add_route('rpcs', '/rpcs/deployment/{name}')
    config.add_view(build_rpcs, route_name='rpcs', request_method='POST')
    config.add_view(show_rpcs, route_name='rpcs', request_method='GET')
    app = config.make_wsgi_app()
    serve(app, host='0.0.0.0')
