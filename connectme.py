from functools import partial
import json
import logging
from os.path import join, dirname
import random
import string
from urllib import urlencode
from urlparse import urlsplit, urlunsplit

from itty import *

from sessionstore import SessionStore, squib
from responses import TemplateResponse, OopsResponse, RedirectResponse, JsonResponse


log = logging.getLogger()

get('/static/(?P<filename>.+)')(partial(serve_static_file, root=join(dirname(__file__), 'static')))

sessionize = SessionStore()
authorizations = {}
access_tokens = {}


class Client(object):

    _indexes = {}

    def __init__(self, **kwargs):
        self.client_id = squib(10)
        self.client_secret = squib(20)
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
    format = request.GET.get('format', 'json')
    if format != 'json':
        return OopsResponse("Unsupported format %r; only 'json' is supported", format)

    hostmeta = {
        'ns': {
            'hm': 'http://host-meta.net/ns/1.0',
        },
        'hm:host': (request._environ['HTTP_HOST'],),  # obviously
        'link': ({
            'rel': 'openid',
            'href': 'https://%s/token_endpoint' % request._environ['HTTP_HOST'],  # "token endpoint" url?
        },),
    }

    return Response(json.dumps(hostmeta), content_type='application/json')


@post('/token_endpoint')
def token_endpoint(request):
    req_type = request.POST.get('type')
    routines = {
        'client_associate': client_associate,
        'web_server': grant_access_token,
    }

    try:
        routine = routines[req_type]
    except KeyError:
        return OopsResponse('Unknown request type %r', req_type)

    return routine(request)


def client_associate(request):
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


def grant_access_token(request):
    client_id = request.POST.get('client_id')
    try:
        client = Client.get_by_client_id(client_id)
    except KeyError:
        return JsonResponse({'error': 'incorrect_client_credentials',
            'oops': "No such client %r" % client_id}, status=400)

    client_secret = request.POST.get('client_secret')
    if client_secret != client.client_secret:
        return JsonResponse({'error': 'incorrect_client_credentials',
            'oops': "Incorrect secret for client %r" % client_id}, status=400)

    code = request.POST.get('code')
    try:
        authorization = authorizations[code]
    except KeyError:
        return JsonResponse({'error': 'bad_verification_code',
            'oops': "Invalid authorization code %r" % code}, status=400)

    if client_id != authorization['client_id']:
        return JsonResponse({'error': 'bad_verification_code',
            'oops': "Invalid authorization code %r for client %r" % (code, client_id)}, status=400)

    redirect_uri = request.POST.get('redirect_uri')
    if redirect_uri != client.redirect_uri:
        return JsonResponse({'error': 'redirect_uri_mismatch',
            'oops': "Incorrect redirect URI for client %r" % client_id}, status=400)

    # Okay then.
    token_token = squib(20)
    access_token = {
        'token': token_token,
        'username': authorization['username'],
    }
    access_tokens[token_token] = access_token

    return JsonResponse({
        'access_token': token_token,
        'user_id': 'https://%s/person/%s' % (request._environ['HTTP_HOST'], authorization['username']),
    })


@get('/user_endpoint')
@sessionize
def user_endpoint(request):
    client_id = request.GET.get('client_id')
    try:
        Client.get_by_client_id(client_id)
    except KeyError:
        return OopsResponse("No such client %r", client_id)

    scope = request.GET.get('scope')
    if scope != 'openid':
        return OopsResponse("Unknown scope %r", scope)

    redirect_uri = request.GET.get('redirect_uri')

    authorization = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
    }
    code = squib(20)
    authorizations[code] = authorization

    return TemplateResponse('connectme/user_endpoint.html', {
        'code': code,
    })


@post('/user_authorized')
@sessionize
def user_authorized(request):
    code = request.POST.get('code')

    try:
        authorization = authorizations[code]
    except KeyError:
        return OopsResponse("Invalid authorization code %r", code)

    username = request.POST.get('username')
    if not username:
        return OopsResponse("A username is required for me to know who to say you are")
    authorization['username'] = username

    scheme, netloc, path, query, fragment = urlsplit(authorization['redirect_uri'])
    query = urlencode({
        'code': code,
    })
    authorized_url = urlunsplit((scheme, netloc, path, query, fragment))

    return RedirectResponse(authorized_url)


if __name__ == '__main__':
    run_itty()
