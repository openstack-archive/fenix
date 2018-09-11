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

from oslo_log import log as logging
from oslo_service import threadgroup
from threading import Thread
import time


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


class SessionData(object):

    def __init__(self, data):
        self.projects = []
        self.hosts = data['hosts']
        self.maintenance_at = str(data['maintenance_at'])
        self.metadata = data['metadata']
        self.instances = []
        self.maintained_hosts = []
        self.proj_instance_actions = {}

    def get_empty_hosts(self):
        empty_hosts = list(self.hosts)
        ([empty_hosts.remove(instance.host) for instance in
            self.instances if instance.host in empty_hosts])
        return empty_hosts

    def add_instance(self, project, instance_id, instance_name, host,
                     ha=False):
        if host not in self.hosts:
            LOG.error('instance %s in invalid host ' % instance_id)
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
        for project in self.projects:
            project.state = state
            project.state_instances = (
                self.instance_ids_by_host_and_project(host, project.name))
            if project.state_instances:
                project.state = state
            else:
                project.state = None

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
                if instance.host == host
                and instance.project == project]

    def instances_by_host_and_project(self, host, project):
        return [instance for instance in self.instances
                if instance.host == host
                and instance.project == project]

    def instance_action_by_project_reply(self, project, instance_id):
        return self.proj_instance_actions[project][instance_id]

    def __str__(self):
        info = 'Instance info:\n'
        for host in self.hosts:
            info += ('%s:\n' % host)
            for project in self.project_names():
                instances = self.instances_by_host_and_project(host, project)
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
        self.state = 'MAINTENANCE'
        self.session_data = SessionData(data)
        self.states_methods = {'MAINTENANCE': 'maintenance',
                               'SCALE_IN': 'scale_in',
                               'PREPARE_MAINTENANCE': 'prepare_maintenance',
                               'START_MAINTENANCE': 'start_maintenance',
                               'PLANNED_MAINTENANCE': 'planned_maintenance',
                               'MAINTENANCE_COMPLETE': 'maintenance_complete',
                               'MAINTENANCE_DONE': 'maintenance_done',
                               'FAILED': 'maintenance_failed'}

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
            if self.state != "MAINTENANCE_DONE" and self.state != "FAILED":
                statefunc = getattr(self, self.states_methods[self.state])
                statefunc()
            else:
                time.sleep(1)
                # IDLE while session removed
        LOG.info("%s: done" % self.session_id)
