# Copyright (c) 2014 Intel Corporation
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

from fenix import exceptions


LOG = logging.getLogger(__name__)


class FenixDBException(exceptions.FenixException):
    msg_fmt = 'An unknown database exception occurred'


class FenixDBDuplicateEntry(FenixDBException):
    msg_fmt = 'Duplicate entry for %(columns)s in %(model)s model was found'


class FenixDBNotFound(FenixDBException):
    msg_fmt = '%(id)s %(model)s was not found'


class FenixDBInvalidFilter(FenixDBException):
    msg_fmt = '%(query_filter)s is invalid'


class FenixDBInvalidFilterOperator(FenixDBException):
    msg_fmt = '%(filter_operator)s is invalid'
