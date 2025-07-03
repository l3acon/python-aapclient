# Copyright (c) 2025 Chris Edillon
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

"""
Ping command for AAP connectivity testing
"""

import logging
import time

from cliff.show import ShowOne

from aapclient.common import utils


LOG = logging.getLogger(__name__)


class Ping(ShowOne):
    """Test connectivity to AAP server"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--timeout',
            type=int,
            default=10,
            help='Request timeout in seconds (default: 10)'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Record start time
        start_time = time.time()

        try:
            # Make ping request to the controller
            response = client.ping()

            # Calculate response time
            response_time = time.time() - start_time
            response_time_ms = round(response_time * 1000, 2)

            # Determine status
            status = "OK"
            if response_time > 2.0:
                status = "SLOW"
            elif response_time > 5.0:
                status = "WARNING"

            # Get server information from response
            server_version = response.get('version', 'Unknown')
            server_time = response.get('time', '')
            active_node = response.get('ha', {}).get('node_name', 'N/A') if isinstance(response.get('ha'), dict) else 'N/A'

            # Format server time if available
            if server_time:
                server_time = utils.format_datetime(server_time)

            # Prepare display data
            display_data = [
                ('Status', status),
                ('Response Time', f"{response_time_ms} ms"),
                ('Server Host', client.config.host),
                ('Server Version', server_version),
                ('Server Time', server_time or 'Not Available'),
                ('Active Node', active_node),
                ('Authentication', 'Token' if client.config.token else 'Username/Password'),
            ]

            return zip(*display_data) if display_data else ((), ())

        except Exception as e:
            # Calculate response time even for failures
            response_time = time.time() - start_time
            response_time_ms = round(response_time * 1000, 2)

            # Prepare failure display data
            display_data = [
                ('Status', 'FAILED'),
                ('Response Time', f"{response_time_ms} ms"),
                ('Server Host', client.config.host),
                ('Error', str(e)),
                ('Authentication', 'Token' if client.config.token else 'Username/Password'),
            ]

            return zip(*display_data) if display_data else ((), ())
