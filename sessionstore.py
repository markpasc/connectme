from Cookie import SimpleCookie
from functools import wraps
import logging
import random
import string


log = logging.getLogger(__name__)


def squib(length):
    return "".join(random.choice(string.lowercase + string.digits * 2) for i in range(length))


class SessionStore(object):

    def __init__(self):
        self.store = {}

    def cookify(self, request):
        log.debug("Decoding cookie header %r into cookie", request._environ.get('HTTP_COOKIE'))
        try:
            cookie = SimpleCookie(request._environ['HTTP_COOKIE'])
            session_id = cookie['session_id'].value
            self.store[session_id]  # make sure it's a valid session
        except KeyError:
            cookie = SimpleCookie()
            session_id = squib(20)
            cookie['session_id'] = session_id
            self.store[session_id] = {}
            log.debug("Oops, made up a new session ID %r for new viewer", session_id)
        else:
            log.debug("Sweet, got session ID %r from viewer's cookie", session_id)

        request.session = self.store[session_id]
        return cookie

    def sessionize(self, fn):
        @wraps(fn)
        def sessioned(request, *args, **kwargs):
            cookie = self.cookify(request)
            response = fn(request, *args, **kwargs)

            cookie_header, cookie_value = cookie.output().split(': ', 1)
            log.debug("Setting cookie header %s to %r", cookie_header, cookie_value)
            response.add_header(cookie_header, cookie_value)
            return response
        return sessioned

    __call__ = sessionize

    def clear(self, fn):
        @wraps(fn)
        def desessioned(request, *args, **kwargs):
            cookie = self.cookify(request)
            session_id = cookie['session_id'].value

            # Delete the session, so the next request will generate a new one.
            if session_id in self.store:
                del self.store[session_id]

            return fn(request, *args, **kwargs)
        return desessioned
