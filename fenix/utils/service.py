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

from importlib import import_module
import os
from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging as messaging
from oslo_service import service
from uuid import uuid1 as generate_uuid

from fenix import context

MAX_SESSIONS = 3

LOG = logging.getLogger(__name__)

CONF = cfg.CONF

opts = [
    cfg.StrOpt('host',
               default="127.0.0.1",
               help="API host IP"),
    cfg.IntOpt('port',
               default=5000,
               help="API port to use."),
    cfg.StrOpt('workflow_user',
               default=os.environ.get('OS_USERNAME', 'admin'),
               help="API host IP"),
    cfg.StrOpt('workflow_password',
               default=os.environ.get('OS_PASSWORD', 'admin'),
               help="API host IP"),
    cfg.StrOpt('workflow_project',
               default=os.environ.get('OS_PROJECT_NAME', 'admin'),
               help="API host IP"),
    cfg.IntOpt('project_maintenance_reply',
               default=20,
               help="Project maintenance reply confirmation time in seconds"),
    cfg.IntOpt('project_scale_in_reply',
               default=60,
               help="Project scale in reply confirmation time in seconds"),
]

CONF.register_opts(opts)


class RPCClient(object):
    def __init__(self, target):
        super(RPCClient, self).__init__()
        self._client = messaging.RPCClient(
            target=target,
            transport=messaging.get_rpc_transport(cfg.CONF),
        )

    def cast(self, name, **kwargs):
        ctx = context.current()
        self._client.cast(ctx.to_dict(), name, **kwargs)

    def call(self, name, **kwargs):
        return self._client.call({}, name, **kwargs)


class EngineEndpoint(object):

    def __init__(self):
        self.workflow_sessions = {}

    def _validate_session(self, session_id):
        if session_id not in self.workflow_sessions.keys():
            return False
        return True

    def admin_get(self, ctx):
        """Get maintenance workflow sessions"""
        LOG.info("EngineEndpoint: admin_get")
        return {'sessions': self.workflow_sessions.keys()}

    def admin_create_session(self, ctx, data):
        """Create maintenance workflow session thread"""
        LOG.info("EngineEndpoint: admin_create_session")
        LOG.info("data: %s" % data)
        if len(self.workflow_sessions.keys()) == MAX_SESSIONS:
            LOG.error("Too many sessions: %d" % MAX_SESSIONS)
            return None
        session_id = str(generate_uuid())
        if "workflow" not in data:
            workflow = "fenix.workflow.workflows.default"
        else:
            workflow = "fenix.workflow.workflows.%s" % data["workflow"]
        LOG.info("Workflow plugin module: %s" % workflow)
        wf_plugin = getattr(import_module(workflow), 'Workflow')
        self.workflow_sessions[session_id] = (
            wf_plugin(CONF,
                      session_id,
                      data))
        self.workflow_sessions[session_id].start()
        return {'session_id': session_id}

    def admin_get_session(self, ctx, session_id):
        """Get maintenance workflow session details"""
        if not self._validate_session(session_id):
            return None
        LOG.info("EngineEndpoint: admin_get_session")
        return ({'session_id': session_id, 'state':
                self.workflow_sessions[session_id].state})

    def admin_delete_session(self, ctx, session_id):
        """Delete maintenance workflow session thread"""
        LOG.info("EngineEndpoint: admin_delete_session")
        self.workflow_sessions[session_id].cleanup()
        self.workflow_sessions[session_id].stop()
        self.workflow_sessions.pop(session_id)
        return {}

    def admin_update_session(self, ctx, session_id):
        """Update maintenance workflow session"""
        LOG.info("EngineEndpoint: admin_update_session")
        return {'session_id': session_id}

    def project_get_session(self, ctx, session_id, project_id):
        """Get maintenance workflow session project specific details"""
        if not self._validate_session(session_id):
            return None
        LOG.info("EngineEndpoint: project_get_session")
        instance_ids = (self.workflow_sessions[session_id].session_data.
                        state_instance_ids(project_id))
        return {'instance_ids': instance_ids}

    def project_update_session(self, ctx, session_id, project_id, data):
        """Update maintenance workflow session project state"""
        LOG.info("EngineEndpoint: project_update_session")
        session_data = self.workflow_sessions[session_id].session_data
        project = session_data.project(project_id)
        project.state = data["state"]
        if 'instance_actions' in data:
            session_data.proj_instance_actions[project_id] = (
                data['instance_actions'].copy())
        return data


class RPCServer(service.Service):

    def __init__(self, target):
        super(RPCServer, self).__init__()
        self._server = messaging.get_rpc_server(
            target=target,
            transport=messaging.get_rpc_transport(cfg.CONF),
            endpoints=[
                EngineEndpoint()],
            executor='eventlet',
        )

    def start(self):
        super(RPCServer, self).start()
        self.tg.add_thread(self._server.start)

    def stop(self):
        super(RPCServer, self).stop()
        self._server.stop()


def prepare_service(argv=[]):
    logging.setup(cfg.CONF, 'fenix')
