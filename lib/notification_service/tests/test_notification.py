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
import time
from typing import List
import unittest
from notification_service.base_notification import BaseEvent, EventWatcher
from notification_service.client import NotificationClient
from notification_service.event_storage import MemoryEventStorage, DbEventStorage
from notification_service.high_availability import SimpleNotificationServerHaManager, DbHighAvailabilityStorage
from notification_service.server import NotificationServer
from notification_service.service import NotificationService, HighAvailableNotificationService
from notification_service.util import db
from notification_service.util.db import SQL_ALCHEMY_DB_FILE


def start_ha_master(host, port):
    server_uri = host + ":" + str(port)
    storage = DbEventStorage()
    ha_manager = SimpleNotificationServerHaManager()
    ha_storage = DbHighAvailabilityStorage()
    service = HighAvailableNotificationService(
        storage,
        ha_manager,
        server_uri,
        ha_storage)
    master = NotificationServer(service, port=port)
    master.run()
    return master


properties = {'enable.idempotence': 'True'}


class NotificationTest(object):

    def test_send_event(self):
        event = self.client.send_event(BaseEvent(key="key", value="value1"))
        self.assertTrue(event.version >= 1)

    def test_list_events(self):
        self.client._default_namespace = "a"
        self.client._sender = 's'
        event1 = self.client.send_event(BaseEvent(key="key", value="value1"))

        self.client._default_namespace = "b"
        self.client.send_event(BaseEvent(key="key", value="value2", event_type="a"))
        self.client.send_event(BaseEvent(key="key", value="value3"))
        self.client.send_event(BaseEvent(key="key2", value="value3"))

        events = self.client.list_events(["key", "key2"], version=event1.version)
        self.assertEqual(3, len(events))
        self.assertEqual('s', events[0].sender)

        self.client._default_namespace = "a"
        events = self.client.list_events("key")
        self.assertEqual(1, len(events))
        count = self.client.count_events("key")
        self.assertEqual(1, count[0])

        self.client._default_namespace = "b"
        events = self.client.list_events("key")
        self.assertEqual(2, len(events))
        count = self.client.count_events("key")
        self.assertEqual(2, count[0])

        events = self.client.list_events("key", event_type="a")
        self.assertEqual(1, len(events))
        count = self.client.count_events("key", event_type="a")
        self.assertEqual(1, count[0])

        events = self.client.list_events("key", sender='s')
        self.assertEqual(2, len(events))
        count = self.client.count_events("key", sender="s")
        self.assertEqual(2, count[0])
        self.assertEqual(2, count[1][0].event_count)

        events = self.client.list_events("key", sender='p')
        self.assertEqual(0, len(events))
        count = self.client.count_events("key", sender="p")
        self.assertEqual(0, count[0])
        self.assertEqual([], count[1])

    def test_listen_events(self):
        event_list = []

        class TestWatch(EventWatcher):
            def __init__(self, event_list) -> None:
                super().__init__()
                self.event_list = event_list

            def process(self, events: List[BaseEvent]):
                self.event_list.extend(events)

        self.client._default_namespace = "a"
        self.client._sender = "s"
        event1 = self.client.send_event(BaseEvent(key="key", value="value1"))
        h = self.client.start_listen_event(key="key",
                                           watcher=TestWatch(event_list),
                                           version=event1.version)
        self.client.send_event(BaseEvent(key="key", value="value2"))
        self.client.send_event(BaseEvent(key="key", value="value3"))

        self.client._default_namespace = None
        self.client.send_event(BaseEvent(key="key", value="value4"))

        self.client._default_namespace = "a"
        h.stop()
        events = self.client.list_events("key", version=event1.version)
        self.assertEqual(2, len(events))
        self.assertEqual(2, len(event_list))

        # listen by event_type
        print('listen by event_type')
        event_list.clear()
        time.sleep(1)
        h = self.client.start_listen_event(key="key",
                                           watcher=TestWatch(event_list),
                                           start_time=int(time.time() * 1000),
                                           event_type='e')
        self.client.send_event(BaseEvent(key="key", value="value2", event_type='e'))
        self.client.send_event(BaseEvent(key="key", value="value2", event_type='f'))
        h.stop()
        self.assertEqual(1, len(event_list))

        event_list.clear()
        time.sleep(1)
        h = self.client.start_listen_event(key="key",
                                           start_time=int(time.time() * 1000),
                                           watcher=TestWatch(event_list))
        self.client.send_event(BaseEvent(key="key", value="value2", event_type='e'))
        self.client.send_event(BaseEvent(key="key", value="value2", event_type='f'))
        h.stop()
        self.assertEqual(2, len(event_list))

        # listen by namespace
        print("listen by namespace")
        self.client._default_namespace = "a"
        event_list.clear()
        time.sleep(1)
        h = self.client.start_listen_event(key="key",
                                           start_time=int(time.time() * 1000),
                                           watcher=TestWatch(event_list),
                                           namespace='a')
        self.client.send_event(BaseEvent(key="key", value="value2"))
        self.client._default_namespace = "b"
        self.client.send_event(BaseEvent(key="key", value="value2"))
        h.stop()
        self.assertEqual(1, len(event_list))

        event_list.clear()
        time.sleep(1)
        h = self.client.start_listen_event(key="key",
                                           start_time=int(time.time() * 1000),
                                           watcher=TestWatch(event_list),
                                           namespace='*')
        self.client._default_namespace = "a"
        self.client.send_event(BaseEvent(key="key", value="value2"))
        self.client._default_namespace = "b"
        self.client.send_event(BaseEvent(key="key", value="value2"))
        h.stop()
        self.assertEqual(2, len(event_list))

        # listen by sender
        print("listen by sender")
        event_list.clear()
        time.sleep(1)
        h = self.client.start_listen_event(key="key",
                                           watcher=TestWatch(event_list),
                                           start_time=int(time.time() * 1000),
                                           namespace='*',
                                           sender='s')
        self.client._sender = "s"
        self.client.send_event(BaseEvent(key="key", value="value2"))
        self.client._sender = "p"
        self.client.send_event(BaseEvent(key="key", value="value2"))
        h.stop()
        self.assertEqual(1, len(event_list))

        event_list.clear()
        time.sleep(1)
        h = self.client.start_listen_event(key="key",
                                           watcher=TestWatch(event_list),
                                           start_time=int(time.time() * 1000),
                                           namespace='*')
        self.client._sender = "s"
        self.client.send_event(BaseEvent(key="key", value="value2"))
        self.client._sender = "p"
        self.client.send_event(BaseEvent(key="key", value="value2"))
        h.stop()
        self.assertEqual(2, len(event_list))

    def test_all_listen_events(self):
        self.client.send_event(BaseEvent(key="key", value="value1"))
        time.sleep(1.0)
        event2 = self.client.send_event(BaseEvent(key="key", value="value2"))
        start_time = event2.create_time
        self.client.send_event(BaseEvent(key="key", value="value3"))
        events = self.client.list_all_events(start_time)
        self.assertEqual(2, len(events))

    def test_list_all_events_with_id_range(self):
        event1 = self.client.send_event(BaseEvent(key="key", value="value1"))
        self.client.send_event(BaseEvent(key="key", value="value2"))
        event3 = self.client.send_event(BaseEvent(key="key", value="value3"))
        events = self.client.list_all_events(start_version=event1.version, end_version=event3.version)
        self.assertEqual(2, len(events))

    def test_listen_all_events(self):
        event_list = []

        class TestWatch(EventWatcher):
            def __init__(self, event_list) -> None:
                super().__init__()
                self.event_list = event_list

            def process(self, events: List[BaseEvent]):
                self.event_list.extend(events)

        handle = None
        try:
            handle = self.client.start_listen_events(watcher=TestWatch(event_list))
            self.client.send_event(BaseEvent(key="key1", value="value1"))
            self.client.send_event(BaseEvent(key="key2", value="value2"))
            self.client.send_event(BaseEvent(key="key3", value="value3"))
        finally:
            if handle is not None:
                handle.stop()
        self.assertEqual(3, len(event_list))

    def test_listen_all_events_from_id(self):
        event_list = []

        class TestWatch(EventWatcher):
            def __init__(self, event_list) -> None:
                super().__init__()
                self.event_list = event_list

            def process(self, events: List[BaseEvent]):
                self.event_list.extend(events)

        try:
            event1 = self.client.send_event(BaseEvent(key="key1", value="value1"))
            self.client.start_listen_events(watcher=TestWatch(event_list), version=event1.version)
            self.client.send_event(BaseEvent(key="key2", value="value2"))
            self.client.send_event(BaseEvent(key="key3", value="value3"))
        finally:
            self.client.stop_listen_events()
        self.assertEqual(2, len(event_list))

    def test_listen_large_events(self):
        list1 = []
        list2 = []

        class TestWatcher(EventWatcher):
            def __init__(self, event_list) -> None:
                super().__init__()
                self.event_list = event_list

            def process(self, events: List[BaseEvent]):
                self.event_list.extend(events)
        try:
            self.client.send_event(BaseEvent(key="key", value="value"))

            properties1 = {'enable.idempotence': 'True', 'grpc.max_receive_message_length': '10'}
            small_client = NotificationClient(server_uri="localhost:50051", properties=properties1)
            small_client.start_listen_events(watcher=TestWatcher(list1), version=0)

            properties2 = {'enable.idempotence': 'True'}
            big_client = NotificationClient(server_uri="localhost:50051", properties=properties2)
            big_client.start_listen_events(watcher=TestWatcher(list2), version=0)

        finally:
            small_client.stop_listen_events()
            big_client.stop_listen_events()
        self.assertEqual(0, len(list1))
        self.assertEqual(1, len(list2))

    def test_get_latest_version(self):
        event = self.client.send_event(BaseEvent(key="key", value="value1"))
        event = self.client.send_event(BaseEvent(key="key", value="value2"))
        latest_version = self.client.get_latest_version(key="key")
        self.assertEqual(event.version, latest_version)

    def test_list_any_condition(self):
        self.client._default_namespace = 'a'
        self.client._sender = 's'
        self.client.send_event(BaseEvent(key="key_1", value="value1"))
        self.client.send_event(BaseEvent(key="key_2", value="value2"))
        result = self.client.list_events(key='*', event_type='*')
        self.assertEqual(2, len(result))
        self.client._default_namespace = 'b'
        self.client._sender = 'p'
        self.client.send_event(BaseEvent(key="key_1", value="value1", event_type='event_type'))
        result = self.client.list_events(key='*', event_type='*')
        self.assertEqual(1, len(result))
        result = self.client.list_events(key='*', event_type='*', namespace='*')
        self.assertEqual(3, len(result))
        result = self.client.list_events(key='key_1', event_type='*', namespace='*')
        self.assertEqual(2, len(result))
        result = self.client.list_events(key='key_1', event_type='event_type', namespace='*')
        self.assertEqual(1, len(result))
        result = self.client.list_events(key='key_1', namespace='*')
        self.assertEqual(2, len(result))
        result = self.client.list_events(key='key_1', namespace='*', sender='*')
        self.assertEqual(2, len(result))
        result = self.client.list_events(key='key_1', namespace='*', sender='s')
        self.assertEqual(1, len(result))
        result = self.client.list_events(key='key_1', namespace='*', sender='p')
        self.assertEqual(1, len(result))

    def test_register_client(self):
        self.assertIsNotNone(self.client.client_id)
        tmp_client = NotificationClient(server_uri="localhost:50051", properties=properties)
        self.assertEqual(1, tmp_client.client_id - self.client.client_id)

    def test_is_client_exists(self):
        client_id = self.client.client_id
        self.assertIsNotNone(client_id)
        self.assertEqual(True, self.storage.is_client_exists(client_id))

    def test_delete_client(self):
        client_id = self.client.client_id
        self.assertIsNotNone(client_id)
        self.client.close()
        self.assertEqual(False, self.storage.is_client_exists(client_id))

    def test_send_event_idempotence(self):
        event = BaseEvent(key="key", value="value1")
        idempotent_client = NotificationClient(server_uri="localhost:50051", properties=properties)
        idempotent_client.send_event(event)
        self.assertEqual(1, idempotent_client.sequence_num_manager.get_sequence_number())
        self.assertEqual(1, len(idempotent_client.list_events(key="key")))

        idempotent_client.send_event(event)
        self.assertEqual(2, idempotent_client.sequence_num_manager.get_sequence_number())
        self.assertEqual(2, len(idempotent_client.list_events(key="key")))

        idempotent_client.sequence_num_manager._seq_num = 1
        idempotent_client.send_event(event)
        self.assertEqual(2, idempotent_client.sequence_num_manager.get_sequence_number())
        self.assertEqual(2, len(idempotent_client.list_events(key="key")))

    def test_client_recovery(self):
        event = BaseEvent(key="key", value="value1")
        client1 = NotificationClient(server_uri="localhost:50051", properties=properties)

        client1.send_event(event)
        client1.send_event(event)
        self.assertEqual(2, client1.sequence_num_manager.get_sequence_number())
        self.assertEqual(2, len(client1.list_events(key="key")))

        properties_new = {'enable.idempotence': 'True',
                          'client.id': str(client1.client_id),
                          'initial.sequence.number': '1'}
        client2 = NotificationClient(server_uri="localhost:50051", properties=properties_new)
        client2.send_event(event)
        self.assertEqual(2, client2.sequence_num_manager.get_sequence_number())
        self.assertEqual(2, len(client2.list_events(key="key")))

        client2.send_event(event)
        self.assertEqual(3, client2.sequence_num_manager.get_sequence_number())
        self.assertEqual(3, len(client2.list_events(key="key")))


class DbStorageTest(unittest.TestCase, NotificationTest):

    @classmethod
    def set_up_class(cls):
        db.create_all_tables()
        cls.storage = DbEventStorage()
        cls.master = NotificationServer(NotificationService(cls.storage))
        cls.master.run()
        cls.wait_for_master_started("localhost:50051")

    @classmethod
    def setUpClass(cls):
        cls.set_up_class()

    @classmethod
    def tearDownClass(cls):
        cls.master.stop()
        os.remove(SQL_ALCHEMY_DB_FILE)

    def setUp(self):
        db.prepare_db()
        self.storage.clean_up()
        self.client = NotificationClient(server_uri="localhost:50051", properties=properties)

    def tearDown(self):
        self.client.stop_listen_events()
        self.client.stop_listen_event()
        db.clear_engine_and_session()

    def test_db_clean_up(self):
        db.clear_engine_and_session()
        global_db_uri = db.SQL_ALCHEMY_CONN
        db_file = 'test_ns.db'
        db_uri = 'sqlite:///{}'.format(db_file)
        store = DbEventStorage(db_uri)
        db.upgrade(db_uri, '87cb292bcc31')
        db.prepare_db()
        with db.create_session() as session:
            client = db.ClientModel()
            client.namespace = 'a'
            client.sender = 'a'
            client.create_time = 1
            session.add(client)
            session.commit()
            client_res = session.query(db.ClientModel).all()
            self.assertEqual(1, len(client_res))
        store.clean_up()
        client_res = session.query(db.ClientModel).all()
        self.assertEqual(0, len(client_res))
        self.assertTrue(db.tables_exists(db_uri))
        db.SQL_ALCHEMY_CONN = global_db_uri
        db.clear_engine_and_session()
        if os.path.exists(db_file):
            os.remove(db_file)

    @classmethod
    def wait_for_master_started(cls, server_uri="localhost:50051"):
        last_exception = None
        for i in range(60):
            try:
                return NotificationClient(server_uri=server_uri, enable_ha=True)
            except Exception as e:
                time.sleep(2)
                last_exception = e
        raise Exception("The server %s is unavailable." % server_uri) from last_exception


class MemoryStorageTest(unittest.TestCase, NotificationTest):

    @classmethod
    def set_up_class(cls):
        cls.storage = MemoryEventStorage()
        cls.master = NotificationServer(NotificationService(cls.storage))
        cls.master.run()

    @classmethod
    def setUpClass(cls):
        cls.set_up_class()

    @classmethod
    def tearDownClass(cls):
        cls.master.stop()

    def setUp(self):
        self.storage.clean_up()
        self.client = NotificationClient(server_uri="localhost:50051", properties=properties)

    def tearDown(self):
        self.client.stop_listen_events()
        self.client.stop_listen_event()


class HaDbStorageTest(unittest.TestCase, NotificationTest):
    """
    This test is used to ensure the high availability would not break the original functionality.
    """

    @classmethod
    def set_up_class(cls):
        db.create_all_tables()
        cls.storage = DbEventStorage()
        cls.master1 = start_ha_master("localhost", 50051)
        # The server startup is asynchronous, we need to wait for a while
        # to ensure it writes its metadata to the db.
        time.sleep(0.1)
        cls.master2 = start_ha_master("localhost", 50052)
        time.sleep(0.1)
        cls.master3 = start_ha_master("localhost", 50053)
        time.sleep(0.1)

    @classmethod
    def setUpClass(cls):
        cls.set_up_class()

    @classmethod
    def tearDownClass(cls):
        cls.master1.stop()
        cls.master2.stop()
        cls.master3.stop()
        os.remove(SQL_ALCHEMY_DB_FILE)

    def setUp(self):
        db.prepare_db()
        self.storage.clean_up()
        self.client = NotificationClient(server_uri="localhost:50052", enable_ha=True,
                                         list_member_interval_ms=1000,
                                         retry_timeout_ms=10000,
                                         properties=properties)

    def tearDown(self):
        self.client.stop_listen_events()
        self.client.stop_listen_event()
        self.client.disable_high_availability()
        db.clear_engine_and_session()


class HaClientWithNonHaServerTest(unittest.TestCase, NotificationTest):

    @classmethod
    def wait_for_master_started(cls, server_uri="localhost:50051"):
        last_exception = None
        for i in range(100):
            try:
                return NotificationClient(server_uri=server_uri, enable_ha=True, properties=properties)
            except Exception as e:
                time.sleep(10)
                last_exception = e
        raise Exception("The server %s is unavailable." % server_uri) from last_exception

    @classmethod
    def set_up_class(cls):
        db.create_all_tables()
        cls.storage = DbEventStorage()
        cls.master = NotificationServer(NotificationService(cls.storage))
        cls.master.run()

    @classmethod
    def setUpClass(cls):
        cls.set_up_class()

    @classmethod
    def tearDownClass(cls):
        cls.master.stop()
        os.remove(SQL_ALCHEMY_DB_FILE)

    def setUp(self):
        db.prepare_db()
        self.storage.clean_up()
        self.client = self.wait_for_master_started(server_uri="localhost:50051")

    def tearDown(self):
        self.client.stop_listen_events()
        self.client.stop_listen_event()
        db.clear_engine_and_session()
