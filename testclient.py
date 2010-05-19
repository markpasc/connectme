from functools import partial
import logging
from os.path import join, dirname
from urlparse import urlsplit, SplitResult

from httplib2 import Http
from itty import *

from sessionstore import SessionStore
from templateresponse import TemplateResponse


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
    if scheme is None:
        if '@' in path:
            scheme = 'acct'
        else:
            # Re-split so we get the domain in the netloc.
            scheme, domain, path, query, fragment = urlsplit('http://%s' % openid_url)
    if scheme.startswith('http') and not path:
        path = '/'
    identifier = urlunsplit((scheme, domain, path, query, fragment))

    if scheme == 'acct':
        domain = '@'.split(path, 1)[-1]

    return domain, identifier


@post('/discover')
@sessionize
def discover(request):
    log = logging.getLogger('discover')
    openid_url = request.POST.get('openid_url')

    domain, identifier = identifier_for_url(openid_url)

    # Try to get the host-meta document.
    http = Http()
    response, content = http.request('https://%s/.well-known/host-meta?format=json' % domain)
    log.debug('From https: host-meta request, got a %d response', response.status)

    return Response(content, content_type='text/plain')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    run_itty()
