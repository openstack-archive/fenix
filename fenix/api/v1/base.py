# Copyright (c) 2018 OpenStack Foundation.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import decorator
import flask
import flask_restful as restful
import inspect
import json
import re

SORT_KEY_SPLITTER = re.compile('[ ,]')


class Resource(restful.Resource):
    method_decorators = []

    def error_response(self, status_code, message):
        body = json.dumps(
            {
                'status': status_code,
                'message': message
            },
        )
        resp = flask.make_response("{body}\n".format(body=body))
        resp.status_code = status_code
        return resp


@decorator.decorator
def http_codes(f, *args, **kwargs):
    try:
        return f(*args, **kwargs)
    except Exception as err:
        try:
            inspect.getmodule(f).LOG.error(
                'Error during %s: %s' % (f.__qualname__, err))
        except AttributeError:
            inspect.getmodule(f).LOG.error(
                'Error during %s: %s' % (f.__name__, err))
        return args[0].error_response(500, 'Unknown Error')
