#
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
#
import os
import threading
import unittest
from unittest import mock

from ai_flow.plugin_interface.blob_manager_interface import BlobConfig, BlobManagerFactory

from ai_flow.util.path_util import get_file_dir

from ai_flow_plugins.blob_manager_plugins.s3_blob_manager import S3BlobManager


class TestS3BlobManager(unittest.TestCase):

    @unittest.skipUnless((os.environ.get('blob_server.service_name') is not None
                          and os.environ.get('blob_server.region_name') is not None
                          and os.environ.get('blob_server.api_version') is not None
                          and os.environ.get('blob_server.use_ssl') is not None
                          and os.environ.get('blob_server.verify') is not None
                          and os.environ.get('blob_server.endpoint_url') is not None
                          and os.environ.get('blob_server.access_key_id') is not None
                          and os.environ.get('blob_server.secret_access_key') is not None
                          and os.environ.get('blob_server.bucket_name') is not None), 'need set s3')
    def test_project_upload_download_s3(self):
        project_path = get_file_dir(__file__)
        config = {
            'blob_manager_class': 'ai_flow_plugins.blob_manager_plugins.s3_blob_manager.S3BlobManager',
            'blob_manager_config': {
                'service_name': os.environ.get('blob_server.service_name'),
                'region_name': os.environ.get('blob_server.region_name'),
                'api_version': os.environ.get('blob_server.api_version'),
                'use_ssl': os.environ.get('blob_server.use_ssl'),
                'verify': os.environ.get('blob_server.verify'),
                'endpoint_url': os.environ.get('blob_server.endpoint_url'),
                'access_key_id': os.environ.get('blob_server.access_key_id'),
                'secret_access_key': os.environ.get('blob_server.secret_access_key'),
                'bucket_name': os.environ.get('blob_server.bucket_name'),
                'local_repository': '/tmp'
            }
        }

        blob_config = BlobConfig(config)
        blob_manager = BlobManagerFactory.create_blob_manager(
            blob_config.blob_manager_class(), blob_config.blob_manager_config())
        uploaded_path = blob_manager.upload_project('1', project_path)

        downloaded_path = blob_manager.download_project('1', uploaded_path)
        self.assertEqual('/tmp/workflow_1_project/project', downloaded_path)

    def test_concurrent_download_s3_file(self):
        project_zip = '/tmp/workflow_1_project.zip'
        if os.path.exists(project_zip):
            os.remove(project_zip)
        config = {'service_name': 's3'}
        s3_blob_manager = S3BlobManager(config)
        zip_file_path = None
        call_count = 0

        def mock_get_s3_object(local_path, object_key):
            nonlocal zip_file_path, call_count
            call_count += 1
            zip_file_path = local_path
            with open(local_path, 'w') as f:
                pass

        s3_blob_manager._get_s3_object = mock_get_s3_object
        with mock.patch(
                'ai_flow_plugins.blob_manager_plugins.s3_blob_manager.extract_project_zip_file'):
            def download_loop():
                for i in range(1000):
                    s3_blob_manager.download_project('1', 'dummy_path', '/tmp')

            try:
                t1 = threading.Thread(target=download_loop)
                t1.start()
                download_loop()
                t1.join()
                self.assertEqual(1, call_count)
            finally:
                if zip_file_path:
                    os.remove(zip_file_path)

    def test__get_s3_object_retry(self):
        config = {'service_name': 's3'}
        s3_blob_manager = S3BlobManager(config)

        with mock.patch.object(s3_blob_manager, 's3_client') as mock_client:
            mock_client.download_fileobj.side_effect = [RuntimeError("boom"), RuntimeError("boom"),
                                                        RuntimeError("boom")]
            with self.assertRaises(RuntimeError):
                s3_blob_manager._get_s3_object('dummy_dest', 'key', retry_sleep_sec=0.1)
                self.assertEqual(3, mock_client.download_fileobj.call_count)


if __name__ == '__main__':
    unittest.main()
