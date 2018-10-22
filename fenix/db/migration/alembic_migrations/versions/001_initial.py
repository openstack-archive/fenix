# Copyright 2014 OpenStack Foundation.
# Copyright 2014 Intel Corporation
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
revision = '001'
down_revision = None

import uuid

from alembic import op
import six
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT


def _generate_unicode_uuid():
    return six.text_type(str(uuid.uuid4()))


def MediumText():
    return sa.Text().with_variant(MEDIUMTEXT(), 'mysql')


def upgrade():
    op.create_table(
        'sessions',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('session_id', sa.String(36), primary_key=True),
        sa.Column('state', sa.String(length=32), nullable=True),
        sa.Column('maintenance_at', sa.DateTime(), nullable=True),
        sa.Column('meta', MediumText(), nullable=True),
        sa.Column('workflow', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('session_id'))

    op.create_table(
        'hosts',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True,
                  default=_generate_unicode_uuid),
        sa.Column('session_id', sa.String(36),
                  sa.ForeignKey('sessions.session_id')),
        sa.Column('hostname', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=32), nullable=True),
        sa.Column('maintained', sa.Boolean, default=False),
        sa.Column('disabled', sa.Boolean, default=False),
        sa.UniqueConstraint('session_id', 'hostname', name='_session_host_uc'),
        sa.PrimaryKeyConstraint('id'))

    op.create_table(
        'projects',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True,
                  default=_generate_unicode_uuid),
        sa.Column('session_id', sa.String(36),
                  sa.ForeignKey('sessions.session_id')),
        sa.Column('project_id', sa.String(36), nullable=True,),
        sa.Column('state', sa.String(length=37), nullable=True),
        sa.UniqueConstraint('session_id', 'project_id',
                            name='_session_project_uc'),
        sa.PrimaryKeyConstraint('id'))

    op.create_table(
        'instances',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True,
                  default=_generate_unicode_uuid),
        sa.Column('session_id', sa.String(36),
                  sa.ForeignKey('sessions.session_id')),
        sa.Column('instance_id', sa.String(36), nullable=True,
                  primary_key=True),
        sa.Column('action', sa.String(32), nullable=True),
        sa.Column('project_id', sa.String(36), nullable=True),
        sa.Column('instance_id', sa.String(36), nullable=True),
        sa.Column('project_state', sa.String(length=37), nullable=True),
        sa.Column('state', sa.String(length=16), nullable=True),
        sa.Column('instance_name', sa.String(length=255), nullable=False),
        sa.Column('action_done', sa.Boolean, default=False),
        sa.Column('details', sa.String(255), nullable=True),
        sa.Column('host', sa.String(length=255), nullable=False),
        sa.UniqueConstraint('session_id', 'instance_id',
                            name='_session_instance_uc'),
        sa.PrimaryKeyConstraint('id'))

    op.create_table(
        'action_plugins',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True,
                  default=_generate_unicode_uuid),
        sa.Column('session_id', sa.String(36),
                  sa.ForeignKey('sessions.session_id')),
        sa.Column('plugin', sa.String(length=255), nullable=False),
        sa.Column('state', sa.String(length=32), nullable=True),
        sa.Column('type', sa.String(length=32), nullable=True),
        sa.Column('meta', MediumText(), nullable=False),
        sa.UniqueConstraint('session_id', 'plugin', name='_session_plugin_uc'),
        sa.PrimaryKeyConstraint('id'))


def downgrade():
    op.drop_table('sessions')
    op.drop_table('hosts')
    op.drop_table('projects')
    op.drop_table('instances')
    op.drop_table('action_plugins')
