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

from flask import Flask
from oslo_config import cfg
from oslo_log import log as logging
import sys

from fenix.api import v1


LOG = logging.getLogger(__name__)

api_opts = [
    cfg.StrOpt('api_config',
               default="api.conf",
               help="Configuration file for API service."),
    cfg.StrOpt('host',
               default="127.0.0.1",
               help="API host IP"),
    cfg.IntOpt('port',
               default=5000,
               help="API port to use."),
]

CONF = cfg.CONF
CONF.register_opts(api_opts)
logging.register_options(cfg.CONF)
cfg.CONF(sys.argv[1:], project='fenix', prog='fenix-api')


def create_app(global_config, **local_config):
    return setup_app()


def setup_app(config=None):
    app = Flask(__name__, static_folder=None)
    app.config.update(PROPAGATE_EXCEPTIONS=True)
    app.register_blueprint(v1.bp, url_prefix='/v1')
    return app
