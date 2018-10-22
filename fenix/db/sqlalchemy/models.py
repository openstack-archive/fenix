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


from oslo_utils import uuidutils
import six
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from fenix.db.sqlalchemy import model_base as mb

# Helpers


def _generate_unicode_uuid():
    return six.text_type(uuidutils.generate_uuid())


def MediumText():
    return sa.Text().with_variant(MEDIUMTEXT(), 'mysql')


def _id_column():
    return sa.Column(sa.String(36),
                     primary_key=True,
                     default=_generate_unicode_uuid)


class MaintenanceSession(mb.FenixBase):
    """Maintenance session"""

    __tablename__ = 'sessions'

    session_id = sa.Column(sa.String(36), primary_key=True)
    state = sa.Column(sa.String(length=32), nullable=True)
    maintenance_at = sa.Column(sa.DateTime(), nullable=True)
    meta = sa.Column(MediumText(), nullable=False)
    workflow = sa.Column(sa.String(length=255), nullable=True)

    def to_dict(self):
        return super(MaintenanceSession, self).to_dict()


class MaintenanceAction(mb.FenixBase):
    """Maintenance session"""

    __tablename__ = 'actions'

    id = _id_column()
    session_id = sa.Column(sa.String(36), sa.ForeignKey('sessions.session_id'),
                           nullable=False)
    plugin = sa.Column(sa.String(length=255), nullable=False)
    state = sa.Column(sa.String(length=32), nullable=True)
    type = sa.Column(sa.Enum('pre', 'post', 'host'), nullable=True)
    meta = sa.Column(MediumText(), nullable=False)

    def to_dict(self):
        return super(MaintenanceAction, self).to_dict()


class MaintenanceHost(mb.FenixBase):
    """Maintenance session"""

    __tablename__ = 'hosts'

    id = _id_column()
    session_id = sa.Column(sa.String(36), sa.ForeignKey('sessions.session_id'),
                           nullable=False)
    hostname = sa.Column(sa.String(length=255), primary_key=True)
    type = sa.Column(sa.Enum('compute', 'controller', 'other'), nullable=True)
    maintained = sa.Column(sa.Boolean, default=False)

    def to_dict(self):
        return super(MaintenanceHost, self).to_dict()
