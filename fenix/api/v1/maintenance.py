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

from flask import request
import json
from oslo_log import log
from oslo_serialization import jsonutils

from fenix.api.v1 import base
from fenix import engine
from fenix.utils import service

LOG = log.getLogger(__name__)


class EngineRPCAPI(service.RPCClient):
    BASE_RPC_API_VERSION = '1.0'

    def __init__(self):
        """Initiate RPC API client with needed topic and RPC version."""
        super(EngineRPCAPI, self).__init__(engine.get_target())

    def admin_get(self):
        """Get maintenance workflow sessions"""
        return self.call('admin_get')

    def admin_create_session(self, data):
        """Create maintenance workflow session thread"""
        return self.call('admin_create_session', data=data)

    def admin_get_session(self, session_id):
        """Get maintenance workflow session details"""
        return self.call('admin_get_session', session_id=session_id)

    def admin_delete_session(self, session_id):
        """Delete maintenance workflow session thread"""
        return self.call('admin_delete_session', session_id=session_id)

    def admin_update_session(self, session_id):
        """Update maintenance workflow session"""
        return self.call('admin_update_session', session_id=session_id)

    def project_get_session(self, session_id, project_id):
        """Get maintenance workflow session project specific details"""
        return self.call('project_get_session', session_id=session_id,
                         project_id=project_id)

    def project_update_session(self, session_id, project_id, data):
        """Update maintenance workflow session project state"""
        return self.call('project_update_session', session_id=session_id,
                         project_id=project_id, data=data)


class Maintenance(base.Resource):

    def __init__(self):
        self.engine_rpcapi = EngineRPCAPI()

    @base.http_codes
    def get(self):
        if request.data:
            LOG.error("Unexpected data")
            return {}, 400, None
        LOG.info("admin get")
        LOG.info("self.engine_rpcapi.admin_get")
        sessions = self.engine_rpcapi.admin_get()
        LOG.info("return: %s" % sessions)
        return jsonutils.to_primitive(sessions), 200, None

    @base.http_codes
    def post(self):
        LOG.info("admin post: first")
        data = json.loads(request.data.decode('utf8'))
        LOG.info("admin post: %s" % data)
        session = self.engine_rpcapi.admin_create_session(data)
        if session is None:
            return {"error": "Too many sessions"}, 509, None
        LOG.info("return: %s" % session)
        return jsonutils.to_primitive(session), 200, None


class MaintenanceSession(base.Resource):

    def __init__(self):
        self.engine_rpcapi = EngineRPCAPI()

    @base.http_codes
    def get(self, session_id=None):
        if request.data:
            LOG.error("Unexpected data")
            return {}, 400, None
        LOG.info("admin session_id get")
        session = self.engine_rpcapi.admin_get_session(session_id)
        if session is None:
            return {"error": "Invalid session"}, 404, None
        return jsonutils.to_primitive(session), 200, None

    @base.http_codes
    def put(self, session_id=None):
        data = json.loads(request.data.decode('utf8'))
        LOG.info("admin session_id put: %s" % data)
        engine_data = self.engine_rpcapi.admin_update_session(session_id)
        LOG.info("engine_data: %s" % engine_data)
        response_body = {'maintenance': request.base_url,
                         'session_id': session_id}
        return jsonutils.to_primitive(response_body), 200, None

    @base.http_codes
    def delete(self, session_id=None):
        if request.data:
            LOG.error("Unexpected data")
            return {}, 400, None
        LOG.info("admin session_id delete")
        ret = self.engine_rpcapi.admin_delete_session(session_id)
        LOG.info("return: %s" % ret)
        return jsonutils.to_primitive(ret), 200, None


class MaintenanceSessionProject(base.Resource):

    def __init__(self):
        self.engine_rpcapi = EngineRPCAPI()

    @base.http_codes
    def get(self, session_id=None, project_id=None):
        if request.data:
            LOG.error("Unexpected data")
            return {}, 400, None
        LOG.info("%s_get" % project_id)
        engine_data = self.engine_rpcapi.project_get_session(session_id,
                                                             project_id)
        LOG.info("engine_data: %s" % engine_data)
        return jsonutils.to_primitive(engine_data), 200, None

    @base.http_codes
    def put(self, session_id=None, project_id=None):
        data = json.loads(request.data.decode('utf8'))
        LOG.info("%s_put: %s" % (project_id, data))
        engine_data = self.engine_rpcapi.project_update_session(session_id,
                                                                project_id,
                                                                data)
        LOG.info("engine_data: %s" % engine_data)
        return jsonutils.to_primitive(engine_data), 200, None
