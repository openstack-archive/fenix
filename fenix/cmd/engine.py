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

import eventlet
eventlet.monkey_patch()

import sys

from oslo_config import cfg
from oslo_service import service

from fenix.engine import service as engine_service
from fenix.utils import service as service_utils


def main():
    cfg.CONF(project='fenix', prog='fenix-engine')
    service_utils.prepare_service(sys.argv)

    service.launch(
        cfg.CONF,
        engine_service.EngineService()
    ).wait()


if __name__ == '__main__':
    main()
