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
import unittest

from ai_flow.ai_graph.ai_graph import current_graph
from ai_flow.ai_graph.ai_node import AINode
from ai_flow.api.ai_flow_context import init_ai_flow_context
from ai_flow.cli import cli_parser
from ai_flow.context.workflow_config_loader import current_workflow_config
from ai_flow.endpoint.server.server import AIFlowServer
from ai_flow.plugin_interface import job_plugin_interface, register_job_plugin_factory
from ai_flow.scheduler_service.service.config import SchedulerServiceConfig
from ai_flow.test.api.mock_plugins import MockJobFactory
from ai_flow.test.util.notification_service_utils import start_notification_server, stop_notification_server
from ai_flow.test.util.server_util import wait_for_server_started
from ai_flow.util.path_util import get_file_dir, get_parent_dir

_SQLITE_DB_FILE = 'aiflow.db'
_SQLITE_DB_URI = '%s%s' % ('sqlite:///', _SQLITE_DB_FILE)
_PORT = '50051'
_SERVER_URI = 'localhost:{}'.format(_PORT)
_SCHEDULER_CLASS = 'ai_flow.test.api.mock_plugins.MockScheduler'
_WORKFLOW_NAME = 'test_workflow_operation'

PROJECT_PATH = get_parent_dir(get_parent_dir(get_file_dir(__file__)))


class TestCommand(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.parser = cli_parser.get_parser()
        cls.notification_server = start_notification_server()
        if os.path.exists(_SQLITE_DB_FILE):
            os.remove(_SQLITE_DB_FILE)
        raw_config = {
            'scheduler': {
                'scheduler_class': _SCHEDULER_CLASS,
            }
        }
        config = SchedulerServiceConfig(raw_config)
        register_job_plugin_factory(MockJobFactory())
        cls.aiflow_server = AIFlowServer(store_uri=_SQLITE_DB_URI, port=_PORT,
                                         start_meta_service=True,
                                         start_metric_service=False,
                                         start_model_center_service=False,
                                         start_scheduler_service=True,
                                         scheduler_service_config=config)
        cls.aiflow_server.run()
        wait_for_server_started(_SERVER_URI)
        init_ai_flow_context()

    @classmethod
    def tearDownClass(cls):
        cls.aiflow_server.stop()
        if os.path.exists(_SQLITE_DB_FILE):
            os.remove(_SQLITE_DB_FILE)
        stop_notification_server(cls.notification_server)
        job_plugin_interface.__job_controller_manager__.object_dict.pop('mock')

    def setUp(self):
        self.build_ai_graph()

    def tearDown(self):
        current_graph().clear_graph()

    @classmethod
    def build_ai_graph(cls):
        graph = current_graph()
        for job_config in current_workflow_config().job_configs.values():
            node = AINode(name=job_config.job_name)
            node.config = job_config
            graph.add_node(node)
