# Copyright (c) 2013 Mirantis Inc.
# Copyright (c) 2013 Bull.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class FenixException(Exception):
    """Base Fenix Exception.

    To correctly use this class, inherit from it and define
    a 'msg_fmt' and 'code' properties.
    """
    msg_fmt = "An unknown exception occurred"
    code = 500

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if 'code' not in self.kwargs:
            self.kwargs['code'] = self.code

        if not message:
            try:
                message = self.msg_fmt % kwargs
            except KeyError:
                # kwargs doesn't match a variable in the message
                # log the issue and the kwargs
                LOG.exception('Exception in string format operation')
                for name, value in kwargs.items():
                    LOG.error("%(name)s: %(value)s",
                              {'name': name, 'value': value})

                message = self.msg_fmt

        super(FenixException, self).__init__(message)
