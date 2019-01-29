# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Implementation of SQLAlchemy backend."""

import sys

from oslo_config import cfg
from oslo_db import exception as common_db_exc
from oslo_db.sqlalchemy import session as db_session
from oslo_log import log as logging
import sqlalchemy as sa

from fenix.db import exceptions as db_exc
from fenix.db.sqlalchemy import facade_wrapper
from fenix.db.sqlalchemy import models


LOG = logging.getLogger(__name__)

get_engine = facade_wrapper.get_engine
get_session = facade_wrapper.get_session


def get_backend():
    """The backend is this module itself."""
    return sys.modules[__name__]


def model_query(model, session=None):
    """Query helper.

    :param model: base model to query
    """
    session = session or get_session()

    return session.query(model)


def setup_db():
    try:
        engine = db_session.EngineFacade(cfg.CONF.database.connection,
                                         sqlite_fk=True).get_engine()
        models.MaintenanceSession.metadata.create_all(engine)
        models.MaintenanceActionPlugin.metadata.create_all(engine)
        models.MaintenanceActionPluginInstance.metadata.create_all(engine)
        models.MaintenanceHost.metadata.create_all(engine)
        models.MaintenanceProject.metadata.create_all(engine)
        models.MaintenanceInstance.metadata.create_all(engine)
    except sa.exc.OperationalError as e:
        LOG.error("Database registration exception: %s", e)
        return False
    return True


def drop_db():
    try:
        engine = db_session.EngineFacade(cfg.CONF.database.connection,
                                         sqlite_fk=True).get_engine()
        models.Lease.metavalues.drop_all(engine)
    except Exception as e:
        LOG.error("Database shutdown exception: %s", e)
        return False
    return True


# Helpers for building constraints / equality checks


def constraint(**conditions):
    return Constraint(conditions)


def equal_any(*values):
    return EqualityCondition(values)


def not_equal(*values):
    return InequalityCondition(values)


class Constraint(object):
    def __init__(self, conditions):
        self.conditions = conditions

    def apply(self, model, query):
        for key, condition in self.conditions.items():
            for clause in condition.clauses(getattr(model, key)):
                query = query.filter(clause)
        return query


class EqualityCondition(object):
    def __init__(self, values):
        self.values = values

    def clauses(self, field):
        return sa.or_([field == value for value in self.values])


class InequalityCondition(object):
    def __init__(self, values):
        self.values = values

    def clauses(self, field):
        return [field != value for value in self.values]


# Session
def _maintenance_session_get(session, session_id):
    query = model_query(models.MaintenanceSession, session)
    return query.filter_by(session_id=session_id).first()


def maintenance_session_get(session_id):
    return _maintenance_session_get(get_session(), session_id)


def create_session(values):
    values = values.copy()
    msession = models.MaintenanceSession()
    msession.update(values)

    session = get_session()
    with session.begin():
        try:
            msession.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.FenixDBDuplicateEntry(
                model=msession.__class__.__name__, columns=e.columns)

    return maintenance_session_get(msession.session_id)


def remove_session(session_id):
    session = get_session()
    with session.begin():

        action_plugin_instances = _action_plugin_instances_get_all(session,
                                                                   session_id)
        if action_plugin_instances:
            for action in action_plugin_instances:
                session.delete(action)

        action_plugins = _action_plugins_get_all(session, session_id)
        if action_plugins:
            for action in action_plugins:
                session.delete(action)

        hosts = _hosts_get(session, session_id)
        if hosts:
            for host in hosts:
                session.delete(host)

        projects = _projects_get(session, session_id)
        if projects:
            for project in projects:
                session.delete(project)

        instances = _instances_get(session, session_id)
        if instances:
            for instance in instances:
                session.delete(instance)

        msession = _maintenance_session_get(session, session_id)
        if not msession:
            # raise not found error
            raise db_exc.FenixDBNotFound(session, session_id=session_id,
                                         model='sessions')

        session.delete(msession)


# Action Plugin
def _action_plugin_get(session, session_id, plugin):
    query = model_query(models.MaintenanceActionPlugin, session)
    return query.filter_by(session_id=session_id, plugin=plugin).first()


def action_plugin_get(session_id, plugin):
    return _action_plugin_get(get_session(), session_id, plugin)


def _action_plugins_get_all(session, session_id):
    query = model_query(models.MaintenanceActionPlugin, session)
    return query.filter_by(session_id=session_id).all()


def action_plugins_get_all(session_id):
    return _action_plugins_get_all(get_session(), session_id)


def create_action_plugin(values):
    values = values.copy()
    ap = models.MaintenanceActionPlugin()
    ap.update(values)

    session = get_session()
    with session.begin():
        try:
            ap.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.FenixDBDuplicateEntry(
                model=ap.__class__.__name__, columns=e.columns)

    return action_plugin_get(ap.session_id, ap.plugin)


def create_action_plugins(values_list):
    for values in values_list:
        vals = values.copy()
        session = get_session()
        with session.begin():
            ap = models.MaintenanceActionPlugin()
            ap.update(vals)
            try:
                ap.save(session=session)
            except common_db_exc.DBDuplicateEntry as e:
                # raise exception about duplicated columns (e.columns)
                raise db_exc.FenixDBDuplicateEntry(
                    model=ap.__class__.__name__, columns=e.columns)

    return action_plugins_get_all(ap.session_id)


# Action Plugin Instance
def _action_plugin_instance_get(session, session_id, plugin, hostname):
    query = model_query(models.MaintenanceActionPluginInstance, session)
    return query.filter_by(session_id=session_id, plugin=plugin,
                           hostname=hostname).first()


def action_plugin_instance_get(session_id, plugin, hostname):
    return _action_plugin_instance_get(get_session(), session_id, plugin,
                                       hostname)


def _action_plugin_instances_get_all(session, session_id):
    query = model_query(models.MaintenanceActionPluginInstance, session)
    return query.filter_by(session_id=session_id).all()


def action_plugin_instances_get_all(session_id):
    return _action_plugin_instances_get_all(get_session(), session_id)


def create_action_plugin_instance(values):
    values = values.copy()
    ap_instance = models.MaintenanceActionPluginInstance()
    ap_instance.update(values)

    session = get_session()
    with session.begin():
        try:
            ap_instance.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.FenixDBDuplicateEntry(
                model=ap_instance.__class__.__name__, columns=e.columns)

    return action_plugin_instance_get(ap_instance.session_id,
                                      ap_instance.plugin,
                                      ap_instance.hostname)


def remove_action_plugin_instance(ap_instance):
    session = get_session()
    with session.begin():
        session.delete(ap_instance)


# Host
def _host_get(session, session_id, hostname):
    query = model_query(models.MaintenanceHost, session)
    return query.filter_by(session_id=session_id, hostname=hostname).first()


def host_get(session_id, hostname):
    return _host_get(get_session(), session_id, hostname)


def _hosts_get(session, session_id):
    query = model_query(models.MaintenanceHost, session)
    return query.filter_by(session_id=session_id).all()


def hosts_get(session_id):
    return _hosts_get(get_session(), session_id)


def create_host(values):
    values = values.copy()
    mhost = models.MaintenanceHost()
    mhost.update(values)

    session = get_session()
    with session.begin():
        try:
            mhost.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.FenixDBDuplicateEntry(
                model=mhost.__class__.__name__, columns=e.columns)

    return host_get(mhost.session_id, mhost.hostname)


def create_hosts(values_list):
    for values in values_list:
        vals = values.copy()
        session = get_session()
        with session.begin():
            mhost = models.MaintenanceHost()
            mhost.update(vals)
            try:
                mhost.save(session=session)
            except common_db_exc.DBDuplicateEntry as e:
                # raise exception about duplicated columns (e.columns)
                raise db_exc.FenixDBDuplicateEntry(
                    model=mhost.__class__.__name__, columns=e.columns)

    return hosts_get(mhost.session_id)


# Project
def _project_get(session, session_id, project_id):
    query = model_query(models.MaintenanceProject, session)
    return query.filter_by(session_id=session_id,
                           project_id=project_id).first()


def project_get(session_id, project_id):
    return _project_get(get_session(), session_id, project_id)


def _projects_get(session, session_id):
    query = model_query(models.MaintenanceProject, session)
    return query.filter_by(session_id=session_id).all()


def projects_get(session_id):
    return _projects_get(get_session(), session_id)


def create_project(values):
    values = values.copy()
    mproject = models.MaintenanceProject()
    mproject.update(values)

    session = get_session()
    with session.begin():
        try:
            mproject.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.FenixDBDuplicateEntry(
                model=mproject.__class__.__name__, columns=e.columns)

    return project_get(mproject.session_id, mproject.project_id)


def create_projects(values_list):
    for values in values_list:
        vals = values.copy()
        session = get_session()
        with session.begin():
            mproject = models.MaintenanceProject()
            mproject.update(vals)
            try:
                mproject.save(session=session)
            except common_db_exc.DBDuplicateEntry as e:
                # raise exception about duplicated columns (e.columns)
                raise db_exc.FenixDBDuplicateEntry(
                    model=mproject.__class__.__name__, columns=e.columns)

    return projects_get(mproject.session_id)


# Instance
def _instance_get(session, session_id, instance_id):
    query = model_query(models.MaintenanceInstance, session)
    return query.filter_by(session_id=session_id,
                           instance_id=instance_id).first()


def instance_get(session_id, instance_id):
    return _instance_get(get_session(), session_id, instance_id)


def _instances_get(session, session_id):
    query = model_query(models.MaintenanceInstance, session)
    return query.filter_by(session_id=session_id).all()


def instances_get(session_id):
    return _instances_get(get_session(), session_id)


def create_instance(values):
    values = values.copy()
    minstance = models.MaintenanceInstance()
    minstance.update(values)

    session = get_session()
    with session.begin():
        try:
            minstance.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.FenixDBDuplicateEntry(
                model=minstance.__class__.__name__, columns=e.columns)

    return instance_get(minstance.session_id, minstance.instance_id)


def create_instances(values_list):
    for values in values_list:
        vals = values.copy()
        session = get_session()
        with session.begin():
            minstance = models.MaintenanceInstance()
            minstance.update(vals)
            try:
                minstance.save(session=session)
            except common_db_exc.DBDuplicateEntry as e:
                # raise exception about duplicated columns (e.columns)
                raise db_exc.FenixDBDuplicateEntry(
                    model=minstance.__class__.__name__, columns=e.columns)

    return instances_get(minstance.session_id)


def remove_instance(session_id, instance_id):
    session = get_session()
    with session.begin():

        minstance = _instance_get(session, session_id, instance_id)

        if not minstance:
            # raise not found error
            raise db_exc.FenixDBNotFound(session, session_id=session_id,
                                         model='instances')

        session.delete(minstance)
