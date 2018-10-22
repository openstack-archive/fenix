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
import aodhclient.client as aodhclient
from ast import literal_eval
try:
    basestring
except NameError:
    # Python3
    basestring = str
import collections
from oslo_log import log as logging
import oslo_messaging as messaging
from oslo_service import threadgroup
from threading import Thread
import time

from fenix.db import api as db_api
from fenix.utils.identity_auth import get_identity_auth
from fenix.utils.identity_auth import get_session


LOG = logging.getLogger(__name__)


class Instance(object):

    def __init__(self, project, instance_id, instance_name, host, ha=False):
        self.project = project
        self.instance_id = instance_id
        self.instance_name = instance_name
        self.host = host
        self.ha = ha

    def __str__(self):
        return "%s: %s" % (self.instance_id, self.instance_name)

    def is_on_host(self, host):
        if self.host == host:
            return True
        else:
            return False


class Project(object):

    def __init__(self, name):
        self.name = name
        self.state = None
        self.state_instances = []

    def add_instance(self, project, instance_id, instance_name, host,
                     ha=False):
        if host not in self.hosts:
            LOG.error('%s: instance %s in invalid host %s' %
                      (self.session_id, instance_id, host.hostname))
        if project not in self.project_names():
            self.projects.append(Project(project))
        self.instances.append(Instance(project, instance_id, instance_name,
                              host.hostname, ha))

    def project(self, name):
        return ([project for project in self.projects if
                project.name == name][0])

    def project_names(self):
        return [project.name for project in self.projects]

    def set_projets_state(self, state):
        for project in self.projects:
            project.state = state
            project.state_instances = []

    def project_has_state_instances(self, name):
        project = self.project(name)
        if project.state_instances:
            return True
        else:
            return False

    def set_projects_state_and_host_instances(self, state, host):
        some_project_has_instances = False
        for project in self.projects:
            project.state = state
            project.state_instances = (
                self.instance_ids_by_host_and_project(host, project.name))
            if project.state_instances:
                some_project_has_instances = True
                project.state = state
            else:
                project.state = None
        if not some_project_has_instances:
            LOG.error('%s: No project has instances on host %s' %
                      (self.session_id, host))

    def get_projects_with_state(self):
        return ([project for project in self.projects if project.state
                is not None])

    def state_instance_ids(self, name):
        instances = ([project.state_instances for project in self.projects if
                     project.name == name][0])
        if not instances:
            instances = self.instance_ids_by_project(name)
        return instances

    def instances_by_project(self, project):
        return [instance for instance in self.instances if
                instance.project == project]

    def instance_ids_by_project(self, project):
        return [instance.instance_id for instance in self.instances if
                instance.project == project]

    def instance_ids_by_host_and_project(self, host, project):
        return [instance.instance_id for instance in self.instances
                if instance.host == host and
                instance.project == project]

    def instances_by_host_and_project(self, host, project):
        return [instance for instance in self.instances
                if instance.host == host and
                instance.project == project]

    def instance_action_by_project_reply(self, project, instance_id):
        return self.proj_instance_actions[project][instance_id]

    def __str__(self):
        info = 'Instance info:\n'
        for host in self.hosts:
            info += ('%s:\n' % host.hostname)
            for project in self.project_names():
                instances = self.instances_by_host_and_project(host.hostname,
                                                               project)
                if instances:
                    info += ('  %s:\n' % project)
                    for instance in instances:
                        info += ('    %s\n' % instance)
        return info


class BaseWorkflow(Thread):

    def __init__(self, conf, session_id, data):
        Thread.__init__(self)
        self.conf = conf
        self.session_id = session_id
        self.stopped = False
        self.thg = threadgroup.ThreadGroup()
        self.timer = {}
        self.session = self._init_session(data)
        LOG.info('%s:  session %s' % (self.session_id, self.session))
        self.hosts = self._init_hosts(self.convert(data['hosts']))
        LOG.info('%s:  hosts %s' % (self.session_id, self.hosts))
        # TBD API to support action plugins
        # self.actions =
        self.projects = []
        self.instances = []
        self.maintained_hosts = []
        self.proj_instance_actions = {}

        self.states_methods = {'MAINTENANCE': 'maintenance',
                               'SCALE_IN': 'scale_in',
                               'PREPARE_MAINTENANCE': 'prepare_maintenance',
                               'START_MAINTENANCE': 'start_maintenance',
                               'PLANNED_MAINTENANCE': 'planned_maintenance',
                               'MAINTENANCE_COMPLETE': 'maintenance_complete',
                               'MAINTENANCE_DONE': 'maintenance_done',
                               'MAINTENANCE_FAILED': 'maintenance_failed'}
        self.url = "http://%s:%s" % (conf.host, conf.port)
        self.auth = get_identity_auth(conf.workflow_user,
                                      conf.workflow_password,
                                      conf.workflow_project)
        self.auth_session = get_session(auth=self.auth)
        self.aodh = aodhclient.Client('2', self.auth_session)
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

    def _init_hosts(self, hostnames):
        LOG.info('%s:  _init_hosts: %s' % (self.session_id, hostnames))
        return db_api.create_hosts(self.session_id, hostnames)

    def convert(self, data):
        if isinstance(data, basestring):
            return str(data)
        elif isinstance(data, collections.Mapping):
            return dict(map(self.convert, data.iteritems()))
        elif isinstance(data, collections.Iterable):
            return type(data)(map(self.convert, data))
        else:
            return data

    def _init_session(self, data):
        session = {
            'session_id': self.session_id,
            'state': 'MAINTENANCE',
            'maintenance_at': str(data['maintenance_at']),
            'meta': str(self.convert(data['metadata'])),
            'workflow': self.convert((data['workflow']))}
        LOG.info('%s:  _init_session: %s' % (self.session_id, session))
        return db_api.create_session(session)

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

    def get_maintained_hosts(self):
        return [host.hostname for host in self.hosts if host.maintained]

    def host_maintained(self, hostname):
        host_obj = [host for host in self.hosts if
                    host.hostname == hostname][0]
        host_obj.maintained = True

    def add_instance(self, project, instance_id, instance_name, host,
                     ha=False):
        if host not in self.get_compute_hosts():
            LOG.error('%s: instance %s in invalid host %s' %
                      (self.session_id, instance_id, host))
        if project not in self.project_names():
            self.projects.append(Project(project))
        self.instances.append(Instance(project, instance_id, instance_name,
                              host, ha))

    def project(self, name):
        return ([project for project in self.projects if
                project.name == name][0])

    def project_names(self):
        return [project.name for project in self.projects]

    def set_projets_state(self, state):
        for project in self.projects:
            project.state = state
            project.state_instances = []

    def project_has_state_instances(self, name):
        project = self.project(name)
        if project.state_instances:
            return True
        else:
            return False

    def set_projects_state_and_host_instances(self, state, host):
        some_project_has_instances = False
        for project in self.projects:
            project.state = state
            project.state_instances = (
                self.instance_ids_by_host_and_project(host, project.name))
            if project.state_instances:
                some_project_has_instances = True
                project.state = state
            else:
                project.state = None
        if not some_project_has_instances:
            LOG.error('%s: No project has instances on host %s' %
                      (self.session_id, host))

    def get_projects_with_state(self):
        return ([project for project in self.projects if project.state
                is not None])

    def state_instance_ids(self, name):
        instances = ([project.state_instances for project in self.projects if
                     project.name == name][0])
        if not instances:
            instances = self.instance_ids_by_project(name)
        return instances

    def instances_by_project(self, project):
        return [instance for instance in self.instances if
                instance.project == project]

    def instance_ids_by_project(self, project):
        return [instance.instance_id for instance in self.instances if
                instance.project == project]

    def instance_ids_by_host_and_project(self, host, project):
        return [instance.instance_id for instance in self.instances
                if instance.host == host and
                instance.project == project]

    def instances_by_host_and_project(self, host, project):
        return [instance for instance in self.instances
                if instance.host == host and
                instance.project == project]

    def instance_action_by_project_reply(self, project, instance_id):
        return self.proj_instance_actions[project][instance_id]

    def __str__(self):
        info = 'Instance info:\n'
        for host in self.hosts:
            info += ('%s:\n' % host.hostname)
            for project in self.project_names():
                instances = self.instances_by_host_and_project(host.hostname,
                                                               project)
                if instances:
                    info += ('  %s:\n' % project)
                    for instance in instances:
                        info += ('    %s\n' % instance)
        return info

    def _timer_expired(self, name):
        LOG.info("%s: timer expired %s" % (self.session_id, name))
        if name in self.timer.keys():
            self.timer[name].stop()
            self.thg.timer_done(self.timer[name])
            self.timer.pop(name)

    def is_timer_expired(self, name):
        if name in self.timer.keys():
            return False
        else:
            return True

    def stop_timer(self, name):
        LOG.info("%s: stop_timer %s" % (self.session_id, name))
        if name in self.timer.keys():
            self.timer[name].stop()
            self.thg.timer_done(self.timer[name])
            self.timer.pop(name)

    def start_timer(self, delay, name):
        LOG.info("%s: start_timer %s" % (self.session_id, name))
        if name in self.timer.keys():
            LOG.error("%s: timer exist!" % self.session_id)
        else:
            self.timer[name] = (self.thg.add_timer(delay,
                                                   self._timer_expired,
                                                   delay,
                                                   name))

    def cleanup(self):
        db_api.remove_session(self.session_id)
        LOG.info("%s: cleanup" % self.session_id)

    def stop(self):
        LOG.info("%s: stop" % self.session_id)
        self.stopped = True

    def maintenance(self):
        LOG.error("%s: maintenance method not implemented!" % self.session_id)

    def maintenance_failed(self):
        LOG.error("%s: maintenance_failed method not implemented!" %
                  self.session_id)

    def run(self):
        LOG.info("%s: started" % self.session_id)
        while not self.stopped:
            if self.session.state not in ["MAINTENANCE_DONE",
                                          "MAINTENANCE_FAILED"]:
                try:
                    statefunc = (getattr(self,
                                 self.states_methods[self.session.state]))
                    statefunc()
                except Exception as e:
                    LOG.error("%s: %s Raised exception: %s" % (self.session_id,
                              statefunc, e), exc_info=True)
                    self.session.state = "MAINTENANCE_FAILED"
            else:
                time.sleep(1)
                # IDLE while session removed
        LOG.info("%s: done" % self.session_id)

    def projects_listen_alarm(self, match_event):
        match_projects = ([str(alarm['project_id']) for alarm in
                          self.aodh.alarm.list() if
                          str(alarm['event_rule']['event_type']) ==
                          match_event])
        all_projects_match = True
        for project in self.project_names():
            if project not in match_projects:
                LOG.error('%s: project %s not '
                          'listening to %s' %
                          (self.session_id, project, match_event))
                all_projects_match = False
        return all_projects_match

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
                       metadata=literal_eval(metadata),
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

    def _project_names_in_state(self, projects, state):
        return ([project.name for project in projects if
                 project.state == state])

    def wait_projects_state(self, state, timer_name):
        state_ack = 'ACK_%s' % state
        state_nack = 'NACK_%s' % state
        projects = self.get_projects_with_state()
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
                    pnames = self._project_names_in_state(projects, answer)
                    LOG.error('%s: projects rejected with %s: %s' %
                              (self.session_id, answer, pnames))
                    return False
                else:
                    pnames = self._project_names_in_state(projects, answer)
                    LOG.error('%s: projects with invalid state %s: %s' %
                              (self.session_id, answer, pnames))
                    return False
            time.sleep(1)
        LOG.error('%s: timer %s expired waiting answer to state %s' %
                  (self.session_id, timer_name, state))
        pnames = self._project_names_in_state(projects, state)
        LOG.error('%s: projects not answered: %s' % (self.session_id, pnames))
        return False
