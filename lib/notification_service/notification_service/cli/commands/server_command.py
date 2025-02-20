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
"""Server command"""
import datetime
import logging
import os
import signal
import time

import daemon
from daemon.pidfile import TimeoutPIDLockFile

import notification_service.settings
from notification_service.server import NotificationServerRunner
from notification_service.settings import get_configuration_file_path
from notification_service.util.utils import check_pid_exist

logger = logging.getLogger(__name__)


def sigterm_handler(signum, frame):
    # We raise KeyboardInterrupt so that the server can stop gracefully
    raise KeyboardInterrupt()


def make_log_dir_if_not_exist():
    log_dir = os.path.join(notification_service.settings.NOTIFICATION_HOME, "logs")
    if os.path.exists(log_dir):
        return

    os.makedirs(log_dir, exist_ok=True)


def server_start(args):
    pid_file_path = os.path.join(notification_service.settings.NOTIFICATION_HOME,
                                 notification_service.settings.NOTIFICATION_PID_FILENAME)
    if args.daemon:
        make_log_dir_if_not_exist()
        log_path = os.path.join(notification_service.settings.NOTIFICATION_HOME, "logs",
                                'notification_server-{}.log'.format(datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))

        logger.info(f"\nStarting Notification Server in daemon mode\n"
                    f"Notification server log: {log_path}\n"
                    f"Notification server pid file: {pid_file_path}")

        log = open(log_path, 'w+')
        ctx = _get_daemon_context(log, pid_file_path)
        with ctx:
            config_file_path = get_configuration_file_path()
            server_runner = NotificationServerRunner(config_file_path)
            server_runner.start(True)

        log.close()
    else:
        """Start the notification server"""
        signal.signal(signal.SIGTERM, sigterm_handler)
        config_file_path = get_configuration_file_path()

        pid = os.getpid()
        logger.info("Starting notification server at pid: {}".format(pid))
        with open(pid_file_path, 'w') as f:
            f.write(str(pid))

        try:
            server_runner = NotificationServerRunner(config_file_path)
            server_runner.start(True)
        finally:
            if os.path.exists(pid_file_path):
                os.remove(pid_file_path)


def server_stop(args):
    pid_file_path = os.path.join(notification_service.settings.NOTIFICATION_HOME,
                                 notification_service.settings.NOTIFICATION_PID_FILENAME)
    if not os.path.exists(pid_file_path):
        logger.info(
            "PID file of Notification server does not exist at {}. The Notification server is not running.".format(
                pid_file_path))
        return

    with open(pid_file_path, 'r') as f:
        pid = int(f.read())

    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        logger.warning("Failed to stop Notification server (pid: {}) with SIGTERM. Try to send SIGKILL".format(pid))
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception as e:
            raise RuntimeError("Failed to kill Notification server (pid: {}) with SIGKILL.".format(pid)) from e

    stop_timeout = 60
    start_time = time.monotonic()
    while check_pid_exist(pid):
        if time.monotonic() - start_time > stop_timeout:
            raise RuntimeError(
                "Notification server (pid: {}) does not exit after {} seconds.".format(pid, stop_timeout))
        time.sleep(0.5)

    logger.info("Notification server pid: {} stopped".format(pid))


def _get_daemon_context(log, pid_file_path: str) -> daemon.DaemonContext:
    return daemon.DaemonContext(
        pidfile=TimeoutPIDLockFile(pid_file_path, -1),
        stdout=log,
        stderr=log,
        signal_map={
            signal.SIGTERM: sigterm_handler
        }
    )
