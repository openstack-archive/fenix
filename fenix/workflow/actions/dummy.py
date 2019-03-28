# Copyright (c) 2019 OpenStack Foundation.
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
from oslo_log import log as logging
import subprocess

LOG = logging.getLogger(__name__)


class ActionPlugin(object):

    def __init__(self, wf, ap_dbi):
        self.hostname = ap_dbi.hostname
        self.wf = wf
        self.ap_dbi = ap_dbi
        LOG.info("%s: Dummy action plugin initialized" % self.wf.session_id)

    def run(self):
        LOG.info("%s: Dummy action plugin run %s" % (self.wf.session_id,
                                                     self.hostname))
        try:
            output = subprocess.check_output("echo Dummy running in %s" %
                                             self.hostname,
                                             shell=True)
            self.ap_dbi.state = "DONE"
        except subprocess.CalledProcessError:
            self.ap_dbi.state = "FAILED"
        LOG.debug("%s: OUTPUT: %s" % (self.wf.session_id, output))
