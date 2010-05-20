import json
from os.path import join, dirname

from itty import Response, content_type
from jinja2 import Environment, FileSystemLoader


class TemplateResponse(Response):

    env = Environment(loader=FileSystemLoader(join(dirname(__file__), 'templates')))

    def __init__(self, template_name, context, *args, **kwargs):
        if 'content_type' not in kwargs:
            kwargs['content_type'] = content_type(template_name)
        self.template = self.env.get_template(template_name)
        self.context = context
        super(TemplateResponse, self).__init__(None, *args, **kwargs)

    @property
    def output(self):
        return self.template.render(self.context)

    @output.setter
    def output(self, val):
        pass  # ignore


class RedirectResponse(Response):

    def __init__(self, url, headers=None, status=302):
        super(RedirectResponse, self).__init__('Redirecting to %s' % url, headers, status, content_type='text/plain')
        self.add_header('Location', url)


class OopsResponse(Response):

    def __init__(self, str, *args):
        message = str % args
        super(OopsResponse, self).__init__(message, status=400, content_type='text/plain')


class JsonResponse(Response):

    def __init__(self, obj, headers=None, status=200):
        body = json.dumps(obj)
        super(JsonResponse, self).__init__(body, headers, status, content_type='application/json')
