# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
import os
import logging
import sqlalchemy


_logger = logging.getLogger(__name__)


def _get_alembic_config(url):
    from alembic.config import Config

    current_dir = os.path.dirname(os.path.abspath(__file__))
    package_dir = os.path.normpath(os.path.join(current_dir, '..'))
    directory = os.path.join(package_dir, 'migrations')
    config = Config(os.path.join(package_dir, 'alembic.ini'))
    config.set_main_option('script_location', directory.replace('%', '%%'))
    config.set_main_option('sqlalchemy.url', url.replace('%', '%%'))
    return config


def upgrade(url, version=None):
    """Upgrade the database."""
    # alembic adds significant import time, so we import it lazily
    from alembic import command

    _logger.info("Upgrade the database, db uri: {}.".format(url))
    config = _get_alembic_config(url)
    if version is None:
        version = 'heads'
    command.history(config)
    command.upgrade(config, version)


def init_db(url):
    _logger.info("Init the database, db uri: {}.".format(url))
    upgrade(url)


def clear_db(url, metadata):
    _logger.info("Clear the database, db uri: {}.".format(url))
    engine = sqlalchemy.create_engine(url)
    connection = engine.connect()
    metadata.drop_all(connection)
    # alembic adds significant import time, so we import it lazily
    from alembic.migration import MigrationContext  # noqa

    migration_ctx = MigrationContext.configure(connection)
    version = migration_ctx._version  # noqa pylint: disable=protected-access
    if version.exists(connection):
        version.drop(connection)


def reset_db(url, metadata):
    _logger.info("Reset the database, db uri: {}.".format(url))
    clear_db(url, metadata)
    init_db(url)


def downgrade(url, version):
    """Downgrade the database."""
    # alembic adds significant import time, so we import it lazily
    from alembic import command

    _logger.info("Downgrade the database, db uri: {}.".format(url))
    config = _get_alembic_config(url)
    command.history(config)
    command.downgrade(config, version)


def tables_exists(url):
    """Returns whether tables are created"""
    engine_ = sqlalchemy.create_engine(url)
    if len(engine_.table_names()) > 0:
        return True
    else:
        return False
