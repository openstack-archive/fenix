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

"""Defines interface for DB access.

Functions in this module are imported into the fenix.db namespace. Call these
functions from fenix.db namespace, not the fenix.db.api namespace.

All functions in this module return objects that implement a dictionary-like
interface.

**Related Flags**

:db_backend:  string to lookup in the list of LazyPluggable backends.
              `sqlalchemy` is the only supported backend right now.

:sql_connection:  string specifying the sqlalchemy connection to use, like:
                  `sqlite:///var/lib/fenix/fenix.sqlite`.

"""

from oslo_config import cfg
from oslo_db import api as db_api
from oslo_db import options as db_options
from oslo_log import log as logging


_BACKEND_MAPPING = {
    'sqlalchemy': 'fenix.db.sqlalchemy.api',
}

db_options.set_defaults(cfg.CONF)
IMPL = db_api.DBAPI(cfg.CONF.database.backend,
                    backend_mapping=_BACKEND_MAPPING)
LOG = logging.getLogger(__name__)


def get_instance():
    """Return a DB API instance."""
    return IMPL


def setup_db():
    """Set up database, create tables, etc.

    Return True on success, False otherwise
    """
    return IMPL.setup_db()


def drop_db():
    """Drop database.

    Return True on success, False otherwise
    """
    return IMPL.drop_db()


# Helpers for building constraints / equality checks


def constraint(**conditions):
    """Return a constraint object suitable for use with some updates."""
    return IMPL.constraint(**conditions)


def equal_any(*values):
    """Return an equality condition object suitable for use in a constraint.

    Equal_any conditions require that a model object's attribute equal any
    one of the given values.
    """
    return IMPL.equal_any(*values)


def not_equal(*values):
    """Return an inequality condition object suitable for use in a constraint.

    Not_equal conditions require that a model object's attribute differs from
    all of the given values.
    """
    return IMPL.not_equal(*values)


def to_dict(func):
    def decorator(*args, **kwargs):
        res = func(*args, **kwargs)

        if isinstance(res, list):
            return [item.to_dict() for item in res]

        if res:
            return res.to_dict()
        else:
            return None

    return decorator


# Fenix workflow session DB access
def create_session(values):
    """Create a session from the values."""
    return IMPL.create_session(values)


def remove_session(session_id):
    """Remove a session from the tables."""
    return IMPL.remove_session(session_id)


def create_action(values):
    """Create a action from the values."""
    return IMPL.create_action(values)


def create_host(values):
    """Create a host from the values."""
    return IMPL.create_host(values)


def create_hosts(session_id, hostnames):
    hosts = []
    for hostname in hostnames:
        host = {
            'session_id': session_id,
            'hostname': str(hostname),
            'type': None,
            'maintained': False,
            'disabled': False}
        hosts.append(host)
    return IMPL.create_hosts(hosts)


def create_projects(session_id, project_ids):
    projects = []
    for project_id in project_ids:
        project = {
            'session_id': session_id,
            'project_id': str(project_id),
            'state': None}
        projects.append(project)
    return IMPL.create_projects(projects)
