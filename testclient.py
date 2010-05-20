import errno
from functools import partial
import json
import logging
from os.path import join, dirname
import socket
from urllib import urlencode
from urlparse import urlsplit, urlunsplit, parse_qsl

from httplib2 import Http
from itty import *

from sessionstore import SessionStore
from responses import TemplateResponse, OopsResponse, RedirectResponse


log = logging.getLogger()

get('/static/(?P<filename>.+)')(partial(serve_static_file, root=join(dirname(__file__), 'static')))

sessionize = SessionStore()
servers = {}


@get('/')
@sessionize
def index(request):
    return TemplateResponse('index.html', {
        'user': request.session.get('user'),
    })


def identifier_for_url(openid_url):
    scheme, domain, path, query, fragment = urlsplit(openid_url)
    log.debug("From %r, split into (%r, %r, %r)", openid_url, scheme, domain, path)
    if not scheme:
        if '@' in path:
            log.debug("That's an email, so pretend it's an acct: URI")
            scheme = 'acct'
        else:
            # Re-split so we get the domain in the netloc.
            scheme, domain, path, query, fragment = urlsplit('http://%s' % openid_url)
            log.debug("Resplit the ID as 'http://%s', so now it's (%r, %r, %r)", openid_url, scheme, domain, path)
    if scheme.startswith('http') and not path:
        path = '/'
    identifier = urlunsplit((scheme, domain, path, query, fragment))
    log.debug("Recomposed the identifier into %r", identifier)

    if scheme == 'acct':
        domain = '@'.split(path, 1)[-1]

    return domain, identifier


class BadResponse(Exception):
    pass


def hostmeta_for_domain(domain):
    # Try to get the host-meta document.
    http = Http()
    try:
        response, content = http.request('https://%s/.well-known/host-meta?format=json' % domain)
    except socket.error, exc:
        if exc.errno != errno.ECONNREFUSED:
            raise
        try:
            response, content = http.request('http://%s/.well-known/host-meta?format=json' % domain)
        except socket.error, exc:
            if exc.errno == errno.ECONNREFUSED:
                raise BadResponse('Connection refused')
            raise

    if response.status != 200:
        raise BadResponse('%d %s' % (response.status, response.reason))

    try:
        hostmeta = json.loads(content)
    except Exception, exc:
        raise BadResponse('%s: %s' % (type(exc).__name__, str(exc)))

    return hostmeta


def discover_server(domain, redirect_uri):
    hostmeta = hostmeta_for_domain(domain)

    if 'link' not in hostmeta:
        raise BadResponse("hostmeta document contains no links")
    openid_links = [link for link in hostmeta['link'] if link.get('rel') == 'openid']
    if len(openid_links) != 1:
        raise BadResponse("Expected one 'openid' link in hostmeta but there were %d" % len(openid_links))

    # We aren't already associated, or we would have had the server info already. So do dynamic association.
    token_endpoint = openid_links[0]['href']
    body = urlencode({
        'type': 'client_associate',
        'redirect_uri': redirect_uri,
    })

    http = Http()
    response, content = http.request(token_endpoint, method='POST', body=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    if response.status != 200:
        raise BadResponse("%d %s trying to associate" % (response.status, response.reason))
    if not response['content-type'].startswith('application/x-www-form-urlencoded'):
        raise BadResponse("Result of association was unexpected content type %r, not application/x-www-form-urlencoded" % response['content-type'])

    association = dict(parse_qsl(content))

    return {
        'client_id': association['client_id'],
        'client_secret': association['client_secret'],
        'token_endpoint': token_endpoint,
        'end_user_endpoint': association['user_endpoint_url'],
        'user_info_endpoint': None,  # this is the final identifier now?
    }


@post('/discover')
@sessionize
def discover(request):
    openid_url = request.POST.get('openid_url')

    domain, identifier = identifier_for_url(openid_url)
    log.debug("Yay, cleaved the openid_url into %r and %r", domain, identifier)

    redirect_uri = '%s/authorized' % (request._environ['HTTP_ORIGIN'],)
    if domain not in servers:
        try:
            servers[domain] = discover_server(domain, redirect_uri)
        except BadResponse, exc:
            return OopsResponse('Oops: %s', str(exc))
    server = servers[domain]

    # We have the server info. Now we send the viewer to the end-user endpoint.
    scheme, netloc, path, query, fragment = urlsplit(server['end_user_endpoint'])
    query = urlencode({
        'type': 'web_server',
        'client_id': server['client_id'],
        'redirect_uri': redirect_uri,
        'scope': 'openid',
    })
    authorize_url = urlunsplit((scheme, netloc, path, query, fragment))

    return RedirectResponse(authorize_url)


@get('/authorized')
@sessionize
def authorized(request):
    return Response('homg sweet', content_type='text/plain')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    run_itty()
