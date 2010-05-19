from functools import partial
import logging
from os.path import join, dirname

from itty import *

from sessionstore import SessionStore
from templateresponse import TemplateResponse


get('/static/(?P<filename>.+)')(partial(serve_static_file, root=join(dirname(__file__), 'static')))

sessionize = SessionStore()


@get('/')
@sessionize
def index(request):
    assert hasattr(request, 'session')
    return TemplateResponse('index.html', {})


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    run_itty()
