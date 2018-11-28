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

from oslo_config import cfg
from oslo_log import log as logging

from fenix import engine
from fenix.utils import service as service_utils

opts = [
    cfg.IntOpt('wait_project_reply',
               default=120,
               help='Wait for project reply after message sent to project '),
]

CONF = cfg.CONF
CONF.register_opts(opts, 'engine')
LOG = logging.getLogger(__name__)


class EngineService(service_utils.RPCServer):
    """Service class for the fenix-engine service.

    Responsible for Fenix workflow
    """

    def __init__(self):
        target = engine.get_target()
        super(EngineService, self).__init__(target)
        LOG.info("EngineService init")

    def start(self):
        super(EngineService, self).start()
        LOG.info("EngineService start")
