from functools import partial
import json
import logging
from os.path import join, dirname

from itty import *

from sessionstore import SessionStore
from templateresponse import TemplateResponse


log = logging.getLogger()

get('/static/(?P<filename>.+)')(partial(serve_static_file, root=join(dirname(__file__), 'static')))

sessionize = SessionStore()


class Client(object):

    _indexes = {}

    def __init__(self, **kwargs):
        self.client_id = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for i in range(10))
        self.client_secret = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)") for i in range(20))
        for key, val in kwargs.items():
            setattr(self, key, val)

    def _indexed_property(name):
        def getter(self):
            return self.__dict__[name]

        def setter(self, val):
            try:
                old_value = self.__dict__[name]
            except KeyError:
                pass
            else:
                del self.indexes[name][old_value]

            self.__dict__[name] = val

            if name not in self._indexes:
                self._indexes[name] = {}
            self._indexes[name][val] = self

        @classmethod
        def lookup(cls, val):
            return cls._indexes[name][val]

        return property(getter, setter), lookup

    client_id, get_by_client_id = _indexed_property('client_id')
    redirect_uri, get_by_redirect_uri = _indexed_property('redirect_uri')


@get('/')
@sessionize
def index(request):
    return Response('Hello nerd', content_type='text/plain')


@get('/.well-known/host-meta')
def hostmeta(request):
    format = request.GET.get('format')
    if format != 'json':
        return Response("Unsupported format %r; only 'json' is supported" % format, status=400, content_type='text/plain')

    hostmeta = {
        'ns': {
            'hm': 'http://host-meta.net/ns/1.0',
        },
        'hm:host': (request._environ['HTTP_HOST'],),  # obviously
        'link': ({
            'rel': 'openid',
            'href': 'https://%s/token_endpoint' % request._environ['HTTP_HOST'],  # "token endpoint" url?
        }),
    }

    return Response(json.dumps(hostmeta), content_type='text/plain')


@post('/token_endpoint')
def token_endpoint(request):
    req_type = request.POST.get('type')
    if req_type != 'client_associate':
        return Response('Unknown request type %r' % req_type, status=400, content_type='text/plain')

    # Register this client.
    redirect_uri = request.POST.get('redirect_uri')
    try:
        client = Client.get_by_redirect_uri(redirect_uri)
    except KeyError:
        client = Client(redirect_uri=redirect_uri)

    resp_data = {
        'client_id': client.client_id,
        'client_secret': client.client_secret,
        'expires_in': 0,
        'flows_supported': ('web_server', 'user_agent'),
        'user_endpoint_url': 'https://%s/user_endpoint' % request._environ['HTTP_HOST'],
    }

    return Response(urlencode(resp_data), content_type='application/x-www-form-urlencoded')


if __name__ == '__main__':
    run_itty()
