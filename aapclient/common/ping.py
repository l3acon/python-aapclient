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
        parser.add_argument(
            '--detail',
            action='store_true',
            help='Show detailed Controller infrastructure information in addition to standard output'
        )
        return parser

    def take_action(self, parsed_args):
        controller_client = self.app.client_manager.controller
        gateway_client = self.app.client_manager.gateway

        # Note: --detail flag will be handled after the standard output

        def ping_api(client, api_name):
            """Ping a specific API and return status information"""
            start_time = time.time()

            try:
                response = client.ping()
                response_time = time.time() - start_time
                response_time_ms = round(response_time * 1000, 2)

                # Determine status based on response time
                status = "OK"
                if response_time > 5.0:
                    status = "WARNING"
                elif response_time > 2.0:
                    status = "SLOW"

                                # Extract information from response
                server_version = response.get('version', 'Unknown')

                # Handle API-specific fields
                if api_name == 'Controller':
                    # Controller API has active_node at top level
                    active_node = response.get('active_node', 'N/A')
                    server_time = None  # Controller API doesn't provide timestamp
                    db_connected = None
                    proxy_connected = None
                elif api_name == 'Gateway':
                    # Gateway API has pong field with timestamp and connection status
                    pong_time = response.get('pong', '')
                    server_time = utils.format_datetime(pong_time) if pong_time else None
                    active_node = None  # Gateway API doesn't have active_node
                    db_connected = response.get('db_connected')
                    proxy_connected = response.get('proxy_connected')
                else:
                    server_time = None
                    active_node = None
                    db_connected = None
                    proxy_connected = None

                return {
                    'api': api_name,
                    'status': status,
                    'response_time': response_time_ms,
                    'version': server_version,
                    'server_time': server_time,
                    'active_node': active_node,
                    'db_connected': db_connected,
                    'proxy_connected': proxy_connected,
                    'error': None
                }

            except Exception as e:
                response_time = time.time() - start_time
                response_time_ms = round(response_time * 1000, 2)

                return {
                    'api': api_name,
                    'status': 'FAILED',
                    'response_time': response_time_ms,
                    'version': 'Unknown',
                    'server_time': None,
                    'active_node': None,
                    'db_connected': None,
                    'proxy_connected': None,
                    'error': str(e)
                }

        # Ping both APIs
        controller_result = ping_api(controller_client, 'Controller')
        gateway_result = ping_api(gateway_client, 'Gateway')

        # Determine overall status
        overall_status = 'OK'
        if controller_result['status'] == 'FAILED' or gateway_result['status'] == 'FAILED':
            overall_status = 'PARTIAL' if controller_result['status'] != gateway_result['status'] else 'FAILED'
        elif controller_result['status'] == 'WARNING' or gateway_result['status'] == 'WARNING':
            overall_status = 'WARNING'
        elif controller_result['status'] == 'SLOW' or gateway_result['status'] == 'SLOW':
            overall_status = 'SLOW'

        # Prepare display data - Gateway first, then Controller
        display_data = [
            ('Overall Status', overall_status),
            ('Server Host', controller_client.config.host),
            ('Authentication', 'Token' if controller_client.config.token else 'Username/Password'),
            ('', ''),  # Separator
            ('Gateway API Status', gateway_result['status']),
            ('Gateway Response Time', f"{gateway_result['response_time']} ms"),
            ('Gateway Version', gateway_result['version']),
        ]

        # Add Gateway Server Time only if available
        if gateway_result['server_time']:
            display_data.append(('Gateway Server Time', gateway_result['server_time']))

        # Add Gateway connection status if available
        if gateway_result['db_connected'] is not None:
            db_status = 'Connected' if gateway_result['db_connected'] else 'Disconnected'
            display_data.append(('Gateway DB Status', db_status))

        if gateway_result['proxy_connected'] is not None:
            proxy_status = 'Connected' if gateway_result['proxy_connected'] else 'Disconnected'
            display_data.append(('Gateway Proxy Status', proxy_status))

        if gateway_result['error']:
            display_data.append(('Gateway Error', gateway_result['error']))

        display_data.extend([
            ('', ''),  # Separator
            ('Controller API Status', controller_result['status']),
            ('Controller Response Time', f"{controller_result['response_time']} ms"),
            ('Controller Version', controller_result['version']),
        ])

        # Add Controller Active Node only if available
        if controller_result['active_node']:
            display_data.append(('Controller Active Node', controller_result['active_node']))

        if controller_result['error']:
            display_data.append(('Controller Error', controller_result['error']))

        # Add detailed controller information if --detail flag is used
        if parsed_args.detail:
            detailed_data = self._get_detailed_controller_data(controller_client)
            if detailed_data:
                display_data.extend(detailed_data)

        return zip(*display_data) if display_data else ((), ())

    def _get_detailed_controller_data(self, controller_client):
        """Get detailed Controller API information to append to display"""
        try:
            response = controller_client.ping()

            # Extract detailed information that's not already shown in standard output
            detailed_data = [
                ('', ''),  # Separator
                ('Controller HA Enabled', 'Yes' if response.get('ha') else 'No'),
                ('Controller Install UUID', response.get('install_uuid', 'N/A')),
            ]

            # Add instance information
            instances = response.get('instances', [])
            if instances:
                detailed_data.append(('', ''))  # Separator
                detailed_data.append(('Controller Instances', f"{len(instances)} node(s)"))

                for i, instance in enumerate(instances, 1):
                    prefix = f"Instance {i}"
                    detailed_data.extend([
                        (f'{prefix} Node', instance.get('node', 'Unknown')),
                        (f'{prefix} Type', instance.get('node_type', 'Unknown')),
                        (f'{prefix} Capacity', str(instance.get('capacity', 'Unknown'))),
                        (f'{prefix} Version', instance.get('version', 'Unknown')),
                        (f'{prefix} Heartbeat', utils.format_datetime(instance.get('heartbeat', ''))),
                    ])
                    if i < len(instances):
                        detailed_data.append(('', ''))  # Separator between instances

            # Add instance group information
            instance_groups = response.get('instance_groups', [])
            if instance_groups:
                detailed_data.append(('', ''))  # Separator
                detailed_data.append(('Controller Instance Groups', f"{len(instance_groups)} group(s)"))

                for i, group in enumerate(instance_groups, 1):
                    prefix = f"Group {i}"
                    group_instances = group.get('instances', [])
                    detailed_data.extend([
                        (f'{prefix} Name', group.get('name', 'Unknown')),
                        (f'{prefix} Capacity', str(group.get('capacity', 'Unknown'))),
                        (f'{prefix} Instances', f"{len(group_instances)} ({', '.join(group_instances)})"),
                    ])
                    if i < len(instance_groups):
                        detailed_data.append(('', ''))  # Separator between groups

            return detailed_data

        except Exception as e:
            # If detailed information fails, just return error info
            return [
                ('', ''),  # Separator
                ('Controller Detail Error', str(e)),
            ]
