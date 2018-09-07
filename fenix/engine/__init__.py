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
import oslo_messaging as messaging

opts = [
    cfg.StrOpt('rpc_topic',
               default='fenix.engine',
               help='fenix-engine messages'),
    cfg.StrOpt('host',
               default="127.0.0.1",
               help="API host IP"),
]

CONF = cfg.CONF

CONF.register_opts(opts, 'engine')
logging.register_options(cfg.CONF)
RPC_API_VERSION = '1.0'


def get_target():
    return messaging.Target(topic=CONF.engine.rpc_topic,
                            version=RPC_API_VERSION,
                            server=CONF.engine.host)
