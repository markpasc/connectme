import errno
from functools import partial
import json
import logging
from os.path import join, dirname
import socket
from urlparse import urlsplit, urlunsplit

from httplib2 import Http
from itty import *

from sessionstore import SessionStore
from templateresponse import TemplateResponse


log = logging.getLogger()

get('/static/(?P<filename>.+)')(partial(serve_static_file, root=join(dirname(__file__), 'static')))

sessionize = SessionStore()


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


@post('/discover')
@sessionize
def discover(request):
    openid_url = request.POST.get('openid_url')

    domain, identifier = identifier_for_url(openid_url)
    log.debug("Yay, cleaved the openid_url into %r and %r", domain, identifier)

    try:
        hostmeta = hostmeta_for_domain(domain)
    except BadResponse, exc:
        return Response('Oops: %s' % str(exc), content_type='text/plain')

    return Response(json.dumps(hostmeta), content_type='text/plain')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    run_itty()
