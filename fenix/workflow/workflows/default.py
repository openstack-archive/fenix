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
from novaclient.exceptions import BadRequest
from oslo_log import log as logging
import oslo_messaging as messaging
import time

from fenix.utils.identity_auth import get_identity_auth
from fenix.utils.identity_auth import get_session

import aodhclient.client as aodhclient
import novaclient.client as novaclient


from fenix.workflow.workflow import BaseWorkflow

LOG = logging.getLogger(__name__)


class Workflow(BaseWorkflow):

    def __init__(self, conf, session_id, data):
        super(Workflow, self).__init__(conf, session_id, data)
        self.url = "http://%s:%s" % (conf.host, conf.port)
        self.auth = get_identity_auth(conf.workflow_user,
                                      conf.workflow_password,
                                      conf.workflow_project)
        self.session = get_session(auth=self.auth)
        self.aodh = aodhclient.Client('2', self.session)
        self.nova = novaclient.Client(version='2.34', session=self.session)
        transport = messaging.get_transport(self.conf)
        self.notif_proj = messaging.Notifier(transport,
                                             'maintenance.planned',
                                             driver='messaging',
                                             topics=['notifications'])
        self.notif_proj = self.notif_proj.prepare(publisher_id='fenix')
        self.notif_admin = messaging.Notifier(transport,
                                              'maintenance.host',
                                              driver='messaging',
                                              topics=['notifications'])
        self.notif_admin = self.notif_admin.prepare(publisher_id='fenix')
        LOG.info("%s: initialized" % self.session_id)

    def cleanup(self):
        LOG.info("%s: cleanup" % self.session_id)

    def stop(self):
        LOG.info("%s: stop" % self.session_id)
        self.stopped = True

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
            self.session_data.add_instance(project,
                                           instance_id,
                                           instance_name,
                                           host,
                                           ha)
        LOG.info(str(self.session_data))

    def update_server_info(self):
        opts = {'all_tenants': True}
        servers = self.nova.servers.list(detailed=True, search_opts=opts)
        # TBD actually update, not regenerate
        self.session_data.instances = []
        for server in servers:
            try:
                host = str(server.__dict__.get('OS-EXT-SRV-ATTR:host'))
                project = str(server.tenant_id)
                instance_name = str(server.name)
                instance_id = str(server.id)
                ha = self.is_ha_instance(server)
            except Exception:
                raise Exception('can not get params from server=%s' % server)
            self.session_data.add_instance(project,
                                           instance_id,
                                           instance_name,
                                           host,
                                           ha)
        LOG.info(str(self.session_data))

    def projects_listen_alarm(self, match_event):
        match_projects = ([str(alarm['project_id']) for alarm in
                          self.aodh.alarm.list() if
                          str(alarm['event_rule']['event_type']) ==
                          match_event])
        all_projects_match = True
        for project in self.session_data.project_names():
            if project not in match_projects:
                LOG.error('%s: project %s not '
                          'listening to %s' %
                          (self.session_id, project, match_event))
                all_projects_match = False
        return all_projects_match

    def str_to_datetime(self, dt_str):
        mdate, mtime = dt_str.split()
        year, month, day = map(int, mdate.split('-'))
        hours, minutes, seconds = map(int, mtime.split(':'))
        return datetime.datetime(year, month, day, hours, minutes, seconds)

    def reply_time_str(self, wait):
        now = datetime.datetime.utcnow()
        reply = now - datetime.timedelta(
            seconds=wait)
        return (reply.strftime('%Y-%m-%d %H:%M:%S'))

    def is_time_after_time(self, before, after):
        if type(before) == str:
            time_before = self.str_to_datetime(before)
        else:
            time_before = before
        if type(after) == str:
            time_after = self.str_to_datetime(after)
        else:
            time_after = after
        if time_before > time_after:
            return True
        else:
            return False

    def _project_notify(self, project_id, instance_ids, allowed_actions,
                        actions_at, reply_at, state, metadata):
        reply_url = '%s/v1/maintenance/%s/%s' % (self.url,
                                                 self.session_id,
                                                 project_id)

        payload = dict(project_id=project_id,
                       instance_ids=instance_ids,
                       allowed_actions=allowed_actions,
                       state=state,
                       actions_at=actions_at,
                       reply_at=reply_at,
                       session_id=self.session_id,
                       metadata=metadata,
                       reply_url=reply_url)

        LOG.info('Sending "maintenance.planned" to project: %s' % payload)

        self.notif_proj.info({'some': 'context'}, 'maintenance.scheduled',
                             payload)

    def _admin_notify(self, project, host, state, session_id):
        payload = dict(project_id=project, host=host, state=state,
                       session_id=session_id)

        LOG.info('Sending "maintenance.host": %s' % payload)

        self.notif_admin.info({'some': 'context'}, 'maintenance.host', payload)

    def projects_answer(self, state, projects):
        state_ack = 'ACK_%s' % state
        state_nack = 'NACK_%s' % state
        for project in projects:
            pstate = project.state
            if pstate == state:
                break
            elif pstate == state_ack:
                continue
            elif pstate == state_nack:
                LOG.error('%s: %s from %s' %
                          (self.session_id, pstate, project.name))
                break
            else:
                LOG.error('%s: Project %s in invalid state %s' %
                          (self.session_id, project.name, pstate))
                break
        return pstate

    def wait_projects_state(self, state, timer_name):
        state_ack = 'ACK_%s' % state
        state_nack = 'NACK_%s' % state
        projects = self.session_data.get_projects_with_state()
        if not projects:
            LOG.error('%s: wait_projects_state %s. Emtpy project list' %
                      (self.session_id, state))
        while not self.is_timer_expired(timer_name):
            answer = self.projects_answer(state, projects)
            if answer == state:
                pass
            else:
                self.stop_timer(timer_name)
                if answer == state_ack:
                    LOG.info('all projects in: %s' % state_ack)
                    return True
                elif answer == state_nack:
                    return False
                else:
                    return False
            time.sleep(1)
        LOG.error('%s: timer %s expired waiting answer to state %s' %
                  (self.session_id, timer_name, state))
        LOG.error('%s: project states' % self.session_id)
        return False

    def confirm_maintenance(self):
        allowed_actions = []
        actions_at = self.session_data.maintenance_at
        state = 'MAINTENANCE'
        self.session_data.set_projets_state(state)
        for project in self.session_data.project_names():
            LOG.info('\nMAINTENANCE to project %s\n' % project)
            instance_ids = '%s/v1/maintenance/%s/%s' % (self.url,
                                                        self.session_id,
                                                        project)
            reply_at = self.reply_time_str(self.conf.project_maintenance_reply)
            if self.is_time_after_time(reply_at, actions_at):
                raise Exception('%s: No time for project to'
                                ' answer in state: %s' %
                                (self.session_id, state))
            metadata = self.session_data.metadata
            self._project_notify(project, instance_ids, allowed_actions,
                                 actions_at, reply_at, state, metadata)
        self.start_timer(self.conf.project_maintenance_reply,
                         'MAINTENANCE_TIMEOUT')
        return self.wait_projects_state(state, 'MAINTENANCE_TIMEOUT')

    def confirm_scale_in(self):
        allowed_actions = []
        actions_at = self.reply_time_str(self.conf.project_scale_in_reply)
        reply_at = actions_at
        state = 'SCALE_IN'
        self.session_data.set_projets_state(state)
        for project in self.session_data.project_names():
            LOG.info('\nSCALE_IN to project %s\n' % project)
            instance_ids = '%s/v1/maintenance/%s/%s' % (self.url,
                                                        self.session_id,
                                                        project)
            metadata = self.session_data.metadata
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
            vcpus = hvisor.__getattr__('vcpus')
            vcpus_used = hvisor.__getattr__('vcpus_used')
            hostname = hvisor.__getattr__('hypervisor_hostname')
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
        for host in self.session_data.hosts:
            free_vcpus = self.get_free_vcpus_by_host(host, hvisors)
            ha_instances = 0
            nonha_instances = 0
            for project in self.session_data.project_names():
                for instance in (
                    self.session_data.instances_by_host_and_project(host,
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
        actions_at = self.reply_time_str(self.conf.project_maintenance_reply)
        reply_at = actions_at
        self.session_data.set_projects_state_and_host_instances(state, host)
        for project in self.session_data.project_names():
            if not self.session_data.project_has_state_instances(project):
                continue
            LOG.info('%s to project %s' % (state, project))

            instance_ids = '%s/v1/maintenance/%s/%s' % (self.url,
                                                        self.session_id,
                                                        project)
            metadata = self.session_data.metadata
            self._project_notify(project, instance_ids, allowed_actions,
                                 actions_at, reply_at, state, metadata)
        self.start_timer(self.conf.project_maintenance_reply,
                         '%s_TIMEOUT' % state)
        return self.wait_projects_state(state, '%s_TIMEOUT' % state)

    def confirm_maintenance_complete(self):
        state = 'MAINTENANCE_COMPLETE'
        metadata = self.session_data.metadata
        actions_at = self.reply_time_str(self.conf.project_scale_in_reply)
        reply_at = actions_at
        self.session_data.set_projets_state(state)
        for project in self.session_data.project_names():
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
        metadata = None
        self._project_notify(project, instance_ids, allowed_actions,
                             actions_at, reply_at, state, metadata)

    def actions_to_have_empty_host(self, host):
        # TBD these might be done parallel
        for project in self.session_data.proj_instance_actions.keys():
            instances = (
                self.session_data.instances_by_host_and_project(host, project))
            for instance in instances:
                action = (self.session_data.instance_action_by_project_reply(
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
        retry_migrate = 5
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
                    raise Exception('server %s migrate failed' % server_id)
                # Might take time for scheduler to sync inconsistent instance
                # list for host
                retry_time = 180 - (retry_migrate * 30)
                LOG.info('server %s migrate failed, retry in %s sec'
                         % (server_id, retry_time))
                time.sleep(retry_time)
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
            self.state = 'FAILED'
            return

        if not self.confirm_maintenance():
            self.state = 'FAILED'
            return

        maintenance_empty_hosts = self.session_data.get_empty_hosts()

        if len(maintenance_empty_hosts) == 0:
            if self.need_scale_in():
                LOG.info('%s: Need to scale in to get capacity for '
                         'empty host' % (self.session_id))
                self.state = 'SCALE_IN'
            else:
                LOG.info('%s: Free capacity, but need empty host' %
                         (self.session_id))
                self.state = 'PREPARE_MAINTENANCE'
        else:
            LOG.info('Empty host found')
            self.state = 'START_MAINTENANCE'

        maint_at = self.str_to_datetime(
            self.session_data.maintenance_at)
        if maint_at > datetime.datetime.utcnow():
            time_now = (datetime.datetime.utcnow().strftime(
                        '%Y-%m-%d %H:%M:%S'))
            LOG.info('Time now: %s maintenance starts: %s....' %
                     (time_now, self.session_data.maintenance_at))
            td = maint_at - datetime.datetime.utcnow()
            self.start_timer(td.total_seconds(), 'MAINTENANCE_START_TIMEOUT')
            while not self.is_timer_expired('MAINTENANCE_START_TIMEOUT'):
                time.sleep(1)

        time_now = (datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
        LOG.info('Time to start maintenance: %s' % time_now)

    def scale_in(self):
        LOG.info("%s: scale in" % self.session_id)

        if not self.confirm_scale_in():
            self.state = 'FAILED'
            return
        # TBD it takes time to have proper infromation updated about free
        # capacity. Should make sure instances removed has also VCPUs removed
        self.update_server_info()
        maintenance_empty_hosts = self.session_data.get_empty_hosts()

        if len(maintenance_empty_hosts) == 0:
            if self.need_scale_in():
                LOG.info('%s: Need to scale in more to get capacity for '
                         'empty host' % (self.session_id))
                self.state = 'SCALE_IN'
            else:
                LOG.info('%s: Free capacity, but need empty host' %
                         (self.session_id))
                self.state = 'PREPARE_MAINTENANCE'
        else:
            LOG.info('Empty host found')
            self.state = 'START_MAINTENANCE'

    def prepare_maintenance(self):
        LOG.info("%s: prepare_maintenance called" % self.session_id)
        host = self.find_host_to_be_empty()
        if not self.confirm_host_to_be_emptied(host, 'PREPARE_MAINTENANCE'):
            self.state = 'FAILED'
            return
        if not self.actions_to_have_empty_host(host):
            # TBD we found the hard way that we couldn't make host empty and
            # need to scale in more. Thigns might fail after this if any
            # instance if error or Nova scheduler cached data corrupted for
            # what instance on which host
            LOG.info('%s: Failed to empty %s. Need to scale in more to get '
                     'capacity for empty host' % (self.session_id, host))
            self.state = 'SCALE_IN'
        else:
            self.state = 'START_MAINTENANCE'
        self.update_server_info()

    def start_maintenance(self):
        LOG.info("%s: start_maintenance called" % self.session_id)
        empty_hosts = self.session_data.get_empty_hosts()
        if not empty_hosts:
            LOG.info("%s: No empty host to be maintained" % self.session_id)
            self.state = 'FAILED'
            return
        maintained_hosts = self.session_data.maintained_hosts
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
                maintained_hosts.append(host)
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
                maintained_hosts.append(host)
        if [h for h in self.session_data.hosts if h not in maintained_hosts]:
            # Not all host maintained
            self.state = 'PLANNED_MAINTENANCE'
        else:
            self.state = 'MAINTENANCE_COMPLETE'

    def planned_maintenance(self):
        LOG.info("%s: planned_maintenance called" % self.session_id)
        maintained_hosts = self.session_data.maintained_hosts
        not_maintained_hosts = ([h for h in self.session_data.hosts if h not in
                                maintained_hosts])
        LOG.info("%s: Not maintained hosts: %s" % (self.session_id,
                                                   not_maintained_hosts))
        host = not_maintained_hosts[0]
        if not self.confirm_host_to_be_emptied(host, 'PLANNED_MAINTENANCE'):
            self.state = 'FAILED'
            return
        if not self.actions_to_have_empty_host(host):
            # Failure in here might indicate action to move instance failed.
            # This might be as Nova VCPU capacity was not yet emptied from
            # expected target hosts
            self.state = 'FAILED'
            return
        self.update_server_info()
        self.state = 'START_MAINTENANCE'

    def maintenance_complete(self):
        LOG.info("%s: maintenance_complete called" % self.session_id)
        LOG.info('Projects may still need to up scale back to full '
                 'capcity')
        self.confirm_maintenance_complete()
        self.update_server_info()
        self.state = 'MAINTENANCE_DONE'

    def maintenance_done(self):
        pass

    def maintenance_failed(self):
        LOG.info("%s: maintenance_failed called" % self.session_id)
