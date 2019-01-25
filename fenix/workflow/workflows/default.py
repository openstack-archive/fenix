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
import datetime

from novaclient import API_MAX_VERSION as nova_max_version
import novaclient.client as novaclient
from novaclient.exceptions import BadRequest

from oslo_log import log as logging
import time

from fenix.db import api as db_api
from fenix.utils.time import datetime_to_str
from fenix.utils.time import is_time_after_time
from fenix.utils.time import reply_time_str
from fenix.utils.time import time_now_str


from fenix.workflow.workflow import BaseWorkflow

LOG = logging.getLogger(__name__)


class Workflow(BaseWorkflow):

    def __init__(self, conf, session_id, data):
        super(Workflow, self).__init__(conf, session_id, data)
        nova_version = 2.53
        self.nova = novaclient.Client(nova_version, session=self.auth_session)
        max_nova_server_ver = float(self.nova.versions.get_current().version)
        max_nova_client_ver = float(nova_max_version.get_string())
        if max_nova_server_ver > 2.53 and max_nova_client_ver > 2.53:
            if max_nova_client_ver <= max_nova_server_ver:
                nova_version = max_nova_client_ver
            else:
                nova_version = max_nova_server_ver
            self.nova = novaclient.Client(nova_version,
                                          session=self.auth_session)
        if not self.hosts:
            self.hosts = self._init_hosts_by_services()
        else:
            self._init_update_hosts()
        LOG.info("%s: initialized. Nova version %f" % (self.session_id,
                                                       nova_version))

    def _init_hosts_by_services(self):
        LOG.info("%s: Dicovering hosts by Nova services" % self.session_id)
        hosts = []

        controllers = self.nova.services.list(binary='nova-conductor')
        for controller in controllers:
            host = {}
            service_host = str(controller.__dict__.get(u'host'))
            host['hostname'] = service_host
            host['type'] = 'controller'
            if str(controller.__dict__.get(u'status')) == 'disabled':
                LOG.error("%s: %s nova-conductor disabled before maintenance"
                          % (self.session_id, service_host))
                raise Exception("%s: %s already disabled"
                                % (self.session_id, service_host))
            host['disabled'] = False
            host['details'] = str(controller.__dict__.get(u'id'))
            host['maintained'] = False
            hosts.append(host)

        computes = self.nova.services.list(binary='nova-compute')
        for compute in computes:
            host = {}
            service_host = str(compute.__dict__.get(u'host'))
            host['hostname'] = service_host
            host['type'] = 'compute'
            if str(compute.__dict__.get(u'status')) == 'disabled':
                LOG.error("%s: %s nova-compute disabled before maintenance"
                          % (self.session_id, service_host))
                raise Exception("%s: %s already disabled"
                                % (self.session_id, service_host))
            host['disabled'] = False
            host['details'] = str(compute.__dict__.get(u'id'))
            host['maintained'] = False
            hosts.append(host)

        return db_api.create_hosts_by_details(self.session_id, hosts)

    def _init_update_hosts(self):
        LOG.info("%s: Update given hosts" % self.session_id)
        controllers = self.nova.services.list(binary='nova-conductor')
        computes = self.nova.services.list(binary='nova-compute')

        for host in self.hosts:
            hostname = host.hostname
            host['disabled'] = False
            host['maintained'] = False
            match = [compute for compute in computes if
                     hostname == compute.host]
            if match:
                host.type = 'compute'
                if match[0].status == 'disabled':
                    LOG.error("%s: %s nova-compute disabled before maintenance"
                              % (self.session_id, hostname))
                    raise Exception("%s: %s already disabled"
                                    % (self.session_id, hostname))
                host.details = match[0].id
                continue
            if ([controller for controller in controllers if
                 hostname == controller.host]):
                host.type = 'controller'
                continue
            host.type = 'other'

    def disable_host_nova_compute(self, hostname):
        LOG.info('%s: disable nova-compute on host %s' % (self.session_id,
                                                          hostname))
        host = self.get_host_by_name(hostname)
        try:
            self.nova.services.disable_log_reason(host.details, "maintenance")
        except TypeError:
            LOG.debug('%s: Using old API to disable nova-compute on host %s' %
                      (self.session_id, hostname))
            self.nova.services.disable_log_reason(hostname, "nova-compute",
                                                  "maintenance")
        host.disabled = True

    def enable_host_nova_compute(self, hostname):
        LOG.info('%s: enable nova-compute on host %s' % (self.session_id,
                                                         hostname))
        host = self.get_host_by_name(hostname)
        try:
            self.nova.services.enable(host.details)
        except TypeError:
            LOG.debug('%s: Using old API to enable nova-compute on host %s' %
                      (self.session_id, hostname))
            self.nova.services.enable(hostname, "nova-compute")
        host.disabled = False

    def get_compute_hosts(self):
        return [host.hostname for host in self.hosts
                if host.type == 'compute']

    def get_empty_computes(self):
        all_computes = self.get_compute_hosts()
        instance_computes = []
        for instance in self.instances:
            if instance.host not in instance_computes:
                instance_computes.append(instance.host)
        return [host for host in all_computes if host not in instance_computes]

    def get_instance_details(self, instance):
        network_interfaces = next(iter(instance.addresses.values()))
        for network_interface in network_interfaces:
            _type = network_interface.get('OS-EXT-IPS:type')
            if _type == "floating":
                LOG.info('Instance with floating ip: %s %s' %
                         (instance.id, instance.name))
                return "floating_ip"
        return None

    def _fenix_instance(self, project_id, instance_id, instance_name, host,
                        state, details, action=None, project_state=None,
                        action_done=False):
        instance = {'session_id': self.session_id,
                    'instance_id': instance_id,
                    'action': action,
                    'project_id': project_id,
                    'instance_id': instance_id,
                    'project_state': project_state,
                    'state': state,
                    'instance_name': instance_name,
                    'action_done': action_done,
                    'host': host,
                    'details': details}
        return instance

    def initialize_server_info(self):
        project_ids = []
        instances = []
        compute_hosts = self.get_compute_hosts()
        opts = {'all_tenants': True}
        servers = self.nova.servers.list(detailed=True, search_opts=opts)
        for server in servers:
            try:
                host = str(server.__dict__.get('OS-EXT-SRV-ATTR:host'))
                if host not in compute_hosts:
                    continue
                project_id = str(server.tenant_id)
                instance_name = str(server.name)
                instance_id = str(server.id)
                details = self.get_instance_details(server)
                state = str(server.__dict__.get('OS-EXT-STS:vm_state'))
            except Exception:
                raise Exception('can not get params from server=%s' % server)
            instances.append(self._fenix_instance(project_id, instance_id,
                                                  instance_name, host, state,
                                                  details))
            if project_id not in project_ids:
                project_ids.append(project_id)

        if len(project_ids):
            self.projects = self.init_projects(project_ids)
        else:
            LOG.info('%s: No projects on computes under maintenance %s' %
                     self.session_id)
        if len(instances):
            self.instances = self.add_instances(instances)
        else:
            LOG.info('%s: No instances on computes under maintenance %s' %
                     self.session_id)
        LOG.info(str(self))

    def update_instance(self, project_id, instance_id, instance_name, host,
                        state, details):
        if self.instance_id_found(instance_id):
            # TBD Might need to update instance variables here if not done
            # somewhere else
            return
        elif self.instance_name_found(instance_name):
            # Project has made re-instantiation, remove old add new
            old_instance = self.instance_by_name(instance_name)
            instance = self._fenix_instance(project_id, instance_id,
                                            instance_name, host,
                                            state, details,
                                            old_instance.action,
                                            old_instance.project_state,
                                            old_instance.action_done)
            self.instances.append(self.add_instance(instance))
            self.remove_instance(old_instance)
        else:
            # Instance new, as project has added instances
            instance = self._fenix_instance(project_id, instance_id,
                                            instance_name, host,
                                            state, details)
            self.instances.append(self.add_instance(instance))

    def remove_non_existing_instances(self, instance_ids):
        remove_instances = [instance for instance in
                            self.instances if instance.instance_id not in
                            instance_ids]
        for instance in remove_instances:
            # Instance deleted, as project possibly scaled down
            self.remove_instance(instance)

    def update_server_info(self):
        # TBD This keeps internal instance information up-to-date and prints
        # it out. Same could be done by updating the information when changed
        # Anyhow this also double checks information against Nova
        instance_ids = []
        compute_hosts = self.get_compute_hosts()
        opts = {'all_tenants': True}
        servers = self.nova.servers.list(detailed=True, search_opts=opts)
        for server in servers:
            try:
                host = str(server.__dict__.get('OS-EXT-SRV-ATTR:host'))
                if host not in compute_hosts:
                    continue
                project_id = str(server.tenant_id)
                instance_name = str(server.name)
                instance_id = str(server.id)
                details = self.get_instance_details(server)
                state = str(server.__dict__.get('OS-EXT-STS:vm_state'))
            except Exception:
                raise Exception('can not get params from server=%s' % server)
            self.update_instance(project_id, instance_id, instance_name, host,
                                 state, details)
            instance_ids.append(instance_id)
        self.remove_non_existing_instances(instance_ids)

        LOG.info(str(self))

    def confirm_maintenance(self):
        allowed_actions = []
        actions_at = self.session.maintenance_at
        state = 'MAINTENANCE'
        self.set_projets_state(state)
        for project in self.project_names():
            LOG.info('\nMAINTENANCE to project %s\n' % project)
            instance_ids = '%s/v1/maintenance/%s/%s' % (self.url,
                                                        self.session_id,
                                                        project)
            reply_at = reply_time_str(self.conf.project_maintenance_reply)
            if is_time_after_time(reply_at, actions_at):
                LOG.error('%s: No time for project to answer in state: %s' %
                          (self.session_id, state))
                self.session.state = "MAINTENANCE_FAILED"
                return False
            metadata = self.session.meta
            self._project_notify(project, instance_ids, allowed_actions,
                                 actions_at, reply_at, state, metadata)
        self.start_timer(self.conf.project_maintenance_reply,
                         'MAINTENANCE_TIMEOUT')
        return self.wait_projects_state(state, 'MAINTENANCE_TIMEOUT')

    def confirm_scale_in(self):
        allowed_actions = []
        actions_at = reply_time_str(self.conf.project_scale_in_reply)
        reply_at = actions_at
        state = 'SCALE_IN'
        self.set_projets_state(state)
        for project in self.project_names():
            LOG.info('\nSCALE_IN to project %s\n' % project)
            instance_ids = '%s/v1/maintenance/%s/%s' % (self.url,
                                                        self.session_id,
                                                        project)
            metadata = self.session.meta
            self._project_notify(project, instance_ids, allowed_actions,
                                 actions_at, reply_at, state, metadata)
        self.start_timer(self.conf.project_scale_in_reply,
                         'SCALE_IN_TIMEOUT')
        return self.wait_projects_state(state, 'SCALE_IN_TIMEOUT')

    def need_scale_in(self):
        hvisors = self.nova.hypervisors.list(detailed=True)
        prev_vcpus = 0
        free_vcpus = 0
        prev_hostname = ''
        LOG.info('checking hypervisors for VCPU capacity')
        for hvisor in hvisors:
            hostname = hvisor.__getattr__('hypervisor_hostname')
            if hostname not in self.get_compute_hosts():
                continue
            vcpus = hvisor.__getattr__('vcpus')
            vcpus_used = hvisor.__getattr__('vcpus_used')
            if prev_vcpus != 0 and prev_vcpus != vcpus:
                raise Exception('%s: %d vcpus on %s does not match to'
                                '%d on %s'
                                % (self.session_id, vcpus, hostname,
                                   prev_vcpus, prev_hostname))
            free_vcpus += vcpus - vcpus_used
            prev_vcpus = vcpus
            prev_hostname = hostname
        if free_vcpus >= vcpus:
            # TBD vcpu capacity might be too scattered so moving instances from
            # one host to other host still might not succeed.
            return False
        else:
            return True

    def get_free_vcpus_by_host(self, host, hvisors):
        hvisor = ([h for h in hvisors if
                  h.__getattr__('hypervisor_hostname') == host][0])
        vcpus = hvisor.__getattr__('vcpus')
        vcpus_used = hvisor.__getattr__('vcpus_used')
        return vcpus - vcpus_used

    def find_host_to_be_empty(self):
        # Preferrably host with most free vcpus, no floating ip instances and
        # least instances altogether
        host_to_be_empty = None
        host_no_fip_instances = 0
        host_free_vcpus = 0
        hvisors = self.nova.hypervisors.list(detailed=True)
        for host in self.get_compute_hosts():
            free_vcpus = self.get_free_vcpus_by_host(host, hvisors)
            fip_instances = 0
            no_fip_instances = 0
            for project in self.project_names():
                for instance in (self.instances_by_host_and_project(host,
                                 project)):
                    if instance.details and "floating_ip" in instance.details:
                        fip_instances += 1
                    else:
                        no_fip_instances += 1
            LOG.info('%s has %d floating ip and %d other instances %s free '
                     'vcpus' % (host, fip_instances, no_fip_instances,
                                free_vcpus))
            if fip_instances == 0:
                # We do not want to choose host with floating ip instance
                if host_to_be_empty:
                    # We have host candidate, let's see if this is better
                    if free_vcpus > host_free_vcpus:
                        # Choose as most vcpus free
                        host_to_be_empty = host
                        host_no_fip_instances = no_fip_instances
                        host_free_vcpus = 0
                    elif free_vcpus == host_free_vcpus:
                        if no_fip_instances < host_no_fip_instances:
                            # Choose as most vcpus free and least instances
                            host_to_be_empty = host
                            host_no_fip_instances = no_fip_instances
                            host_free_vcpus = 0
                else:
                    # This is first host candidate
                    host_to_be_empty = host
                    host_no_fip_instances = no_fip_instances
                    host_free_vcpus = 0
        if not host_to_be_empty:
            # No best cadidate found, let's choose last host in loop
            host_to_be_empty = host
        LOG.info('host %s selected to be empty' % host_to_be_empty)
        # TBD It might yet not be possible to move instances away from this
        # host if other hosts has free vcpu capacity scattered. It should
        # checked if instances on this host fits to other hosts
        return host_to_be_empty

    def confirm_host_to_be_emptied(self, host, state):
        allowed_actions = ['MIGRATE', 'LIVE_MIGRATE', 'OWN_ACTION']
        actions_at = reply_time_str(self.conf.project_maintenance_reply)
        reply_at = actions_at
        self.set_projects_state_and_hosts_instances(state, [host])
        for project in self.project_names():
            if not self.project_has_state_instances(project):
                continue
            LOG.info('%s to project %s' % (state, project))

            instance_ids = '%s/v1/maintenance/%s/%s' % (self.url,
                                                        self.session_id,
                                                        project)
            metadata = self.session.meta
            self._project_notify(project, instance_ids, allowed_actions,
                                 actions_at, reply_at, state, metadata)
        self.start_timer(self.conf.project_maintenance_reply,
                         '%s_TIMEOUT' % state)
        return self.wait_projects_state(state, '%s_TIMEOUT' % state)

    def confirm_maintenance_complete(self):
        state = 'MAINTENANCE_COMPLETE'
        metadata = self.session.meta
        actions_at = reply_time_str(self.conf.project_scale_in_reply)
        reply_at = actions_at
        self.set_projets_state(state)
        for project in self.project_names():
            LOG.info('%s to project %s' % (state, project))
            instance_ids = '%s/v1/maintenance/%s/%s' % (self.url,
                                                        self.session_id,
                                                        project)
            allowed_actions = []
            self._project_notify(project, instance_ids, allowed_actions,
                                 actions_at, reply_at, state, metadata)
        self.start_timer(self.conf.project_scale_in_reply,
                         '%s_TIMEOUT' % state)
        return self.wait_projects_state(state, '%s_TIMEOUT' % state)

    def notify_action_done(self, project, instance):
        instance_ids = [instance.instance_id]
        allowed_actions = []
        actions_at = None
        reply_at = None
        state = "INSTANCE_ACTION_DONE"
        instance.project_state = state
        metadata = "{}"
        self._project_notify(project, instance_ids, allowed_actions,
                             actions_at, reply_at, state, metadata)

    def actions_to_have_empty_host(self, host):
        # TBD these might be done parallel
        for project in self.proj_instance_actions.keys():
            instances = (
                self.instances_by_host_and_project(host, project))
            for instance in instances:
                instance.action = (self.instance_action_by_project_reply(
                                   project, instance.instance_id))
                LOG.info('Action %s instance %s ' % (instance.action,
                                                     instance.instance_id))
                if instance.action == 'MIGRATE':
                    if not self.migrate_server(instance):
                        return False
                    self.notify_action_done(project, instance)
                elif instance.action == 'OWN_ACTION':
                    pass
                else:
                    # TBD LIVE_MIGRATE not supported
                    raise Exception('%s: instance %s action '
                                    '%s not supported' %
                                    (self.session_id, instance.instance_id,
                                     instance.action))
        return self._wait_host_empty(host)

    def _wait_host_empty(self, host):
        hid = self.nova.hypervisors.search(host)[0].id
        vcpus_used_last = 0
        # wait 4min to get host empty
        for j in range(48):
            hvisor = self.nova.hypervisors.get(hid)
            vcpus_used = hvisor.__getattr__('vcpus_used')
            if vcpus_used > 0:
                if vcpus_used != vcpus_used_last or vcpus_used_last == 0:
                    LOG.info('%s still has %d vcpus reserved. wait...'
                             % (host, vcpus_used))
                vcpus_used_last = vcpus_used
                time.sleep(5)
            else:
                LOG.info('%s empty' % host)
                return True
        LOG.info('%s host still not empty' % host)
        return False

    def migrate_server(self, instance):
        # TBD this method should be enhanced for errors and to have failed
        # instance back to state active instead of error
        server_id = instance.instance_id
        server = self.nova.servers.get(server_id)
        instance.state = server.__dict__.get('OS-EXT-STS:vm_state')
        LOG.info('server %s state %s' % (server_id, instance.state))
        last_vm_state = instance.state
        retry_migrate = 2
        while True:
            try:
                server.migrate()
                time.sleep(5)
                retries = 36
                while instance.state != 'resized' and retries > 0:
                    # try to confirm within 3min
                    server = self.nova.servers.get(server_id)
                    instance.state = server.__dict__.get('OS-EXT-STS:vm_state')
                    if instance.state == 'resized':
                        server.confirm_resize()
                        LOG.info('instance %s migration confirmed' %
                                 server_id)
                        instance.host = (
                            str(server.__dict__.get('OS-EXT-SRV-ATTR:host')))
                        return True
                    if last_vm_state != instance.state:
                        LOG.info('instance %s state: %s' % (server_id,
                                 instance.state))
                    if instance.state == 'error':
                        LOG.error('instance %s migration failed, state: %s'
                                  % (server_id, instance.state))
                        return False
                    time.sleep(5)
                    retries = retries - 1
                    last_vm_state = instance.state
                # Timout waiting state to change
                break

            except BadRequest:
                if retry_migrate == 0:
                    LOG.error('server %s migrate failed after retries' %
                              server_id)
                    return False
                # Might take time for scheduler to sync inconsistent instance
                # list for host
                # TBD Retry doesn't help, need investigating if reproduces
                retry_timeout = 150 - (retry_migrate * 60)
                LOG.info('server %s migrate failed, retry in %s sec'
                         % (server_id, retry_timeout))
                time.sleep(retry_timeout)
            except Exception as e:
                LOG.error('server %s migration failed, Exception=%s' %
                          (server_id, e))
                return False
            finally:
                retry_migrate = retry_migrate - 1
        LOG.error('instance %s migration timeout, state: %s' %
                  (server_id, instance.state))
        return False

    def host_maintenance(self, host):
        LOG.info('maintaining host %s' % host)
        # TBD Here we should call maintenance plugin given in maintenance
        # session creation
        time.sleep(5)

    def maintenance(self):
        LOG.info("%s: maintenance called" % self.session_id)
        self.initialize_server_info()

        if not self.projects_listen_alarm('maintenance.scheduled'):
            self.session.state = 'MAINTENANCE_FAILED'
            return

        if not self.confirm_maintenance():
            self.session.state = 'MAINTENANCE_FAILED'
            return

        maintenance_empty_hosts = self.get_empty_computes()

        if len(maintenance_empty_hosts) == 0:
            if self.need_scale_in():
                LOG.info('%s: Need to scale in to get capacity for '
                         'empty host' % (self.session_id))
                self.session.state = 'SCALE_IN'
            else:
                LOG.info('%s: Free capacity, but need empty host' %
                         (self.session_id))
                self.session.state = 'PREPARE_MAINTENANCE'
        else:
            LOG.info('Empty host found')
            self.session.state = 'START_MAINTENANCE'

        if self.session.maintenance_at > datetime.datetime.utcnow():
            time_now = time_now_str()
            LOG.info('Time now: %s maintenance starts: %s....' %
                     (time_now, datetime_to_str(self.session.maintenance_at)))
            td = self.session.maintenance_at - datetime.datetime.utcnow()
            self.start_timer(td.total_seconds(), 'MAINTENANCE_START_TIMEOUT')
            while not self.is_timer_expired('MAINTENANCE_START_TIMEOUT'):
                time.sleep(1)

        time_now = time_now_str()
        LOG.info('Time to start maintenance: %s' % time_now)

    def scale_in(self):
        LOG.info("%s: scale in" % self.session_id)

        if not self.confirm_scale_in():
            self.session.state = 'MAINTENANCE_FAILED'
            return
        # TBD it takes time to have proper information updated about free
        # capacity. Should make sure instances removed has also VCPUs removed
        self.update_server_info()
        maintenance_empty_hosts = self.get_empty_computes()

        if len(maintenance_empty_hosts) == 0:
            if self.need_scale_in():
                LOG.info('%s: Need to scale in more to get capacity for '
                         'empty host' % (self.session_id))
                self.session.state = 'SCALE_IN'
            else:
                LOG.info('%s: Free capacity, but need empty host' %
                         (self.session_id))
                self.session.state = 'PREPARE_MAINTENANCE'
        else:
            LOG.info('Empty host found')
            self.session.state = 'START_MAINTENANCE'

    def prepare_maintenance(self):
        LOG.info("%s: prepare_maintenance called" % self.session_id)
        host = self.find_host_to_be_empty()
        if not self.confirm_host_to_be_emptied(host, 'PREPARE_MAINTENANCE'):
            self.session.state = 'MAINTENANCE_FAILED'
            return
        if not self.actions_to_have_empty_host(host):
            # TBD we found the hard way that we couldn't make host empty and
            # need to scale in more. Thigns might fail after this if any
            # instance if error or Nova scheduler cached data corrupted for
            # what instance on which host
            LOG.info('%s: Failed to empty %s. Need to scale in more to get '
                     'capacity for empty host' % (self.session_id, host))
            self.session.state = 'SCALE_IN'
        else:
            self.session.state = 'START_MAINTENANCE'
        self.update_server_info()

    def start_maintenance(self):
        LOG.info("%s: start_maintenance called" % self.session_id)
        empty_hosts = self.get_empty_computes()
        if not empty_hosts:
            LOG.info("%s: No empty host to be maintained" % self.session_id)
            self.session.state = 'MAINTENANCE_FAILED'
            return
        maintained_hosts = self.get_maintained_hosts_by_type('compute')
        if not maintained_hosts:
            computes = self.get_compute_hosts()
            for compute in computes:
                # When we start to maintain compute hosts, all these hosts
                # nova-compute service is disabled, so projects cannot have
                # instances scheduled to not maintained hosts
                self.disable_host_nova_compute(compute)
            # First we maintain all empty hosts
            for host in empty_hosts:
                # TBD we wait host VCPUs to report right, but this is not
                # correct place. We should handle this after scale in
                # also this could be made parallel if more than one empty host
                self._wait_host_empty(host)

                LOG.info('IN_MAINTENANCE host %s' % host)
                self._admin_notify(self.conf.workflow_project, host,
                                   'IN_MAINTENANCE',
                                   self.session_id)
                self.host_maintenance(host)
                self._admin_notify(self.conf.workflow_project, host,
                                   'MAINTENANCE_COMPLETE',
                                   self.session_id)

                self.enable_host_nova_compute(host)
                LOG.info('MAINTENANCE_COMPLETE host %s' % host)
                self.host_maintained(host)
        else:
            # Now we maintain hosts gone trough PLANNED_MAINTENANCE
            hosts = [h for h in empty_hosts if h not in maintained_hosts]
            for host in hosts:
                # TBD this could be made parallel if more than one empty host
                self._wait_host_empty(host)

                LOG.info('IN_MAINTENANCE host %s' % host)
                self._admin_notify(self.conf.workflow_project, host,
                                   'IN_MAINTENANCE',
                                   self.session_id)
                self.host_maintenance(host)
                self._admin_notify(self.conf.workflow_project, host,
                                   'MAINTENANCE_COMPLETE',
                                   self.session_id)

                self.enable_host_nova_compute(host)
                LOG.info('MAINTENANCE_COMPLETE host %s' % host)
                self.host_maintained(host)
        maintained_hosts = self.get_maintained_hosts_by_type('compute')
        if len(maintained_hosts) != len(self.get_compute_hosts()):
            # Not all host maintained
            self.session.state = 'PLANNED_MAINTENANCE'
        else:
            self.session.state = 'MAINTENANCE_COMPLETE'

    def planned_maintenance(self):
        LOG.info("%s: planned_maintenance called" % self.session_id)
        maintained_hosts = self.get_maintained_hosts_by_type('compute')
        compute_hosts = self.get_compute_hosts()
        not_maintained_hosts = ([host for host in compute_hosts if host
                                 not in maintained_hosts])
        LOG.info("%s: Not maintained hosts: %s" % (self.session_id,
                                                   not_maintained_hosts))
        host = not_maintained_hosts[0]
        if not self.confirm_host_to_be_emptied(host, 'PLANNED_MAINTENANCE'):
            self.session.state = 'MAINTENANCE_FAILED'
            return
        if not self.actions_to_have_empty_host(host):
            # Failure in here might indicate action to move instance failed.
            # This might be as Nova VCPU capacity was not yet emptied from
            # expected target hosts
            self.session.state = 'MAINTENANCE_FAILED'
            return
        self.update_server_info()
        self.session.state = 'START_MAINTENANCE'

    def maintenance_complete(self):
        LOG.info("%s: maintenance_complete called" % self.session_id)
        LOG.info('Projects may still need to up scale back to full '
                 'capcity')
        if not self.confirm_maintenance_complete():
            self.session.state = 'MAINTENANCE_FAILED'
            return
        self.update_server_info()
        self.session.state = 'MAINTENANCE_DONE'

    def maintenance_done(self):
        pass

    def maintenance_failed(self):
        LOG.info("%s: maintenance_failed called" % self.session_id)

    def cleanup(self):
        LOG.info("%s: cleanup" % self.session_id)
        db_api.remove_session(self.session_id)
