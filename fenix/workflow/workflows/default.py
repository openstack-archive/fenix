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
import novaclient.client as novaclient
from novaclient.exceptions import BadRequest

from oslo_log import log as logging
import time

from fenix.utils.time import datetime_to_str
from fenix.utils.time import is_time_after_time
from fenix.utils.time import reply_time_str
from fenix.utils.time import time_now_str


from fenix.workflow.workflow import BaseWorkflow

LOG = logging.getLogger(__name__)


class Workflow(BaseWorkflow):

    def __init__(self, conf, session_id, data):
        super(Workflow, self).__init__(conf, session_id, data)
        self.nova = novaclient.Client(version='2.34',
                                      session=self.auth_session)
        self._init_update_hosts()
        LOG.info("%s: initialized" % self.session_id)

    def _init_update_hosts(self):
        controllers = self.nova.services.list(binary='nova-conductor')
        computes = self.nova.services.list(binary='nova-compute')
        for host in self.hosts:
            hostname = host.hostname
            match = [compute for compute in computes if
                     hostname == compute.host]
            if match:
                host.type = 'compute'
                if match[0].status == 'disabled':
                    LOG.info("compute status from services")
                    host.disabled = True
                continue
            if ([controller for controller in controllers if
                 hostname == controller.host]):
                host.type = 'controller'
                continue
            host.type = 'other'

    def is_ha_instance(self, instance):
        network_interfaces = next(iter(instance.addresses.values()))
        for network_interface in network_interfaces:
            _type = network_interface.get('OS-EXT-IPS:type')
            if _type == "floating":
                LOG.info('Instance with floating ip: %s %s' %
                         (instance.id, instance.name))
                return True
        return False

    def initialize_server_info(self):
        project_ids = []
        opts = {'all_tenants': True}
        servers = self.nova.servers.list(detailed=True, search_opts=opts)
        for server in servers:
            try:
                host = str(server.__dict__.get('OS-EXT-SRV-ATTR:host'))
                project = str(server.tenant_id)
                instance_name = str(server.name)
                instance_id = str(server.id)
                ha = self.is_ha_instance(server)
            except Exception:
                raise Exception('can not get params from server=%s' % server)
            self.add_instance(project,
                              instance_id,
                              instance_name,
                              host,
                              ha)
            if project not in project_ids:
                project_ids.append(project)
        self.projects = self.init_projects(project_ids)
        LOG.info(str(self))

    def update_server_info(self):
        opts = {'all_tenants': True}
        servers = self.nova.servers.list(detailed=True, search_opts=opts)
        # TBD actually update, not regenerate
        self.instances = []
        for server in servers:
            try:
                host = str(server.__dict__.get('OS-EXT-SRV-ATTR:host'))
                project = str(server.tenant_id)
                instance_name = str(server.name)
                instance_id = str(server.id)
                ha = self.is_ha_instance(server)
            except Exception:
                raise Exception('can not get params from server=%s' % server)
            self.add_instance(project,
                              instance_id,
                              instance_name,
                              host,
                              ha)
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
        # Preferrably host with most free vcpus, no ha instances and least
        # instances altogether
        host_to_be_empty = None
        host_nonha_instances = 0
        host_free_vcpus = 0
        hvisors = self.nova.hypervisors.list(detailed=True)
        for host in self.get_compute_hosts():
            free_vcpus = self.get_free_vcpus_by_host(host, hvisors)
            ha_instances = 0
            nonha_instances = 0
            for project in self.project_names():
                for instance in (self.instances_by_host_and_project(host,
                                 project)):
                    if instance.ha:
                        ha_instances += 1
                    else:
                        nonha_instances += 1
            LOG.info('host %s has %d ha and %d non ha instances %s free '
                     'vcpus' % (host, ha_instances, nonha_instances,
                                free_vcpus))
            if ha_instances == 0:
                # We do not want to choose host with HA instance
                if host_to_be_empty:
                    # We have host candidate, let's see if this is better
                    if free_vcpus > host_free_vcpus:
                        # Choose as most vcpus free
                        host_to_be_empty = host
                        host_nonha_instances = nonha_instances
                        host_free_vcpus = 0
                    elif free_vcpus == host_free_vcpus:
                        if nonha_instances < host_nonha_instances:
                            # Choose as most vcpus free and least instances
                            host_to_be_empty = host
                            host_nonha_instances = nonha_instances
                            host_free_vcpus = 0
                else:
                    # This is first host candidate
                    host_to_be_empty = host
                    host_nonha_instances = nonha_instances
                    host_free_vcpus = 0
        if not host_to_be_empty:
            # No best cadidate found, let's choose last host in loop
            host_to_be_empty = host
        LOG.info('host %s selected to be empty' % host_to_be_empty)
        # TBD It might yet not be possible to move instances away from this
        # host is other hosts has vcpu capacity scattered. It should be checked
        # if instances on this host fits to other hosts
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

    def notify_action_done(self, project, instance_id):
        instance_ids = instance_id
        allowed_actions = []
        actions_at = None
        reply_at = None
        state = "INSTANCE_ACTION_DONE"
        metadata = "{}"
        self._project_notify(project, instance_ids, allowed_actions,
                             actions_at, reply_at, state, metadata)

    def actions_to_have_empty_host(self, host):
        # TBD these might be done parallel
        for project in self.proj_instance_actions.keys():
            instances = (
                self.instances_by_host_and_project(host, project))
            for instance in instances:
                action = (self.instance_action_by_project_reply(
                          project, instance.instance_id))
                LOG.info('Action %s instance %s ' % (action,
                                                     instance.instance_id))
                if action == 'MIGRATE':
                    if not self.migrate_server(instance.instance_id):
                        return False
                    self.notify_action_done(project, instance.instance_id)
                elif action == 'OWN_ACTION':
                    pass
                else:
                    # TBD LIVE_MIGRATE not supported
                    raise Exception('%s: instance %s action '
                                    '%s not supported' %
                                    (self.session_id, instance.instance_id,
                                     action))
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

    def migrate_server(self, server_id):
        # TBD this method should be enhanced for errors and to have failed
        # instance back to state active instead of error
        server = self.nova.servers.get(server_id)
        vm_state = server.__dict__.get('OS-EXT-STS:vm_state')
        LOG.info('server %s state %s' % (server_id, vm_state))
        last_vm_state = vm_state
        retry_migrate = 2
        while True:
            try:
                server.migrate()
                time.sleep(5)
                retries = 36
                while vm_state != 'resized' and retries > 0:
                    # try to confirm within 3min
                    server = self.nova.servers.get(server_id)
                    vm_state = server.__dict__.get('OS-EXT-STS:vm_state')
                    if vm_state == 'resized':
                        server.confirm_resize()
                        LOG.info('instance %s migration confirmed' %
                                 server_id)
                        return True
                    if last_vm_state != vm_state:
                        LOG.info('instance %s state: %s' % (server_id,
                                 vm_state))
                    if vm_state == 'error':
                        LOG.error('instance %s migration failed, state: %s'
                                  % (server_id, vm_state))
                        return False
                    time.sleep(5)
                    retries = retries - 1
                    last_vm_state = vm_state
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
                  (server_id, vm_state))
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
        # TBD it takes time to have proper infromation updated about free
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
        maintained_hosts = self.get_maintained_hosts()
        if not maintained_hosts:
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
                LOG.info('MAINTENANCE_COMPLETE host %s' % host)

                self.host_maintained(host)
        maintained_hosts = self.get_maintained_hosts()
        if len(maintained_hosts) != len(self.hosts):
            # Not all host maintained
            self.session.state = 'PLANNED_MAINTENANCE'
        else:
            self.session.state = 'MAINTENANCE_COMPLETE'

    def planned_maintenance(self):
        LOG.info("%s: planned_maintenance called" % self.session_id)
        maintained_hosts = self.get_maintained_hosts()
        not_maintained_hosts = ([h.hostname for h in self.hosts if h.hostname
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
