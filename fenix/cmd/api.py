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

from wsgiref import simple_server

from oslo_config import cfg
from oslo_log import log as logging

from fenix import api

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


def main():
    app = api.setup_app()
    host, port = cfg.CONF.host, cfg.CONF.port
    LOG.info("host %s port %s" % (host, port))
    srv = simple_server.make_server(host, port, app)
    LOG.info("fenix-api started")
    srv.serve_forever()


if __name__ == "__main__":
    main()
