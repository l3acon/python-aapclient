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

"""Host commands for AAP Controller v2 API"""

import logging

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common import utils
from aapclient.common.utils import CommandError, format_datetime


LOG = logging.getLogger(__name__)


class ListHost(Lister):
    """List hosts"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--long',
            action='store_true',
            default=False,
            help='List additional fields in output'
        )
        parser.add_argument(
            '--inventory',
            metavar='<inventory>',
            help='Filter by inventory name or ID'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of results (default: 20)'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        params = {}
        if parsed_args.inventory:
            # Resolve inventory name to ID if needed
            if parsed_args.inventory.isdigit():
                params['inventory'] = int(parsed_args.inventory)
            else:
                inventories = client.list_inventories(name=parsed_args.inventory)
                inventory = utils.find_resource(inventories, parsed_args.inventory)
                params['inventory'] = inventory['id']

        # Set consistent default limit of 20 (same as other list commands)
        if parsed_args.limit:
            params['page_size'] = parsed_args.limit
        else:
            params['page_size'] = 20

        # Sort by ID for consistency with other list commands
        params['order_by'] = 'id'

        data = client.list_hosts(**params)

        # Process the data to replace IDs with names
        for host in data.get('results', []):
            if 'summary_fields' in host and 'inventory' in host['summary_fields']:
                host['inventory_name'] = host['summary_fields']['inventory']['name']
            else:
                host['inventory_name'] = str(host.get('inventory', ''))

        # Standard columns: ID, Name, Description, Inventory, Enabled
        columns = ('ID', 'Name', 'Description', 'Inventory', 'Enabled')
        column_headers = columns

        if parsed_args.long:
            # Long format adds Created, Modified, Last Job
            columns = ('ID', 'Name', 'Description', 'Inventory', 'Enabled', 'Created', 'Modified', 'Last Job')
            column_headers = columns

        hosts = []
        for host in data.get('results', []):
            host_info = [
                host['id'],
                host.get('name', ''),
                host.get('description', ''),
                host.get('inventory_name', ''),
                'Yes' if host.get('enabled', True) else 'No',
            ]

            if parsed_args.long:
                # Get last job info
                last_job = ''
                if 'summary_fields' in host and 'last_job' in host['summary_fields']:
                    last_job_info = host['summary_fields']['last_job']
                    last_job = f"#{last_job_info.get('id', '')} ({last_job_info.get('status', '')})"

                host_info.extend([
                    format_datetime(host.get('created')),
                    format_datetime(host.get('modified')),
                    last_job,
                ])

            hosts.append(host_info)

        return (column_headers, hosts)


class ShowHost(ShowOne):
    """Display host details"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'host',
            help='Host name or ID to display'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Find host by name or ID
        if parsed_args.host.isdigit():
            host_id = int(parsed_args.host)
            data = client.get_host(host_id)
        else:
            hosts = client.list_hosts(name=parsed_args.host)
            host = utils.find_resource(hosts, parsed_args.host)
            data = client.get_host(host['id'])

        # Add names from summary_fields
        if 'summary_fields' in data and 'inventory' in data['summary_fields']:
            data['inventory_name'] = data['summary_fields']['inventory']['name']
        else:
            data['inventory_name'] = str(data.get('inventory', ''))

        if 'summary_fields' in data and 'created_by' in data['summary_fields']:
            data['created_by_name'] = data['summary_fields']['created_by']['username']
        else:
            data['created_by_name'] = str(data.get('created_by', ''))

        if 'summary_fields' in data and 'modified_by' in data['summary_fields']:
            data['modified_by_name'] = data['summary_fields']['modified_by']['username']
        else:
            data['modified_by_name'] = str(data.get('modified_by', ''))

        # Format the data for display
        display_data = []

        fields = [
            'id', 'name', 'description', 'inventory_name', 'enabled',
            'variables', 'created', 'modified', 'created_by_name', 'modified_by_name'
        ]

        for field in fields:
            value = data.get(field, '')
            if field in ['created', 'modified']:
                value = format_datetime(value)
            elif isinstance(value, bool):
                value = 'Yes' if value else 'No'
            elif isinstance(value, dict) and field == 'variables':
                # Format variables as readable string
                if value:
                    value = str(value)
                else:
                    value = ''
            elif value is None:
                value = ''

            display_data.append((field.replace('_', ' ').title(), value))

        return zip(*display_data) if display_data else ((), ())


class CreateHost(ShowOne):
    """Create a new host"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            help='Name of the host'
        )
        parser.add_argument(
            '--description',
            help='Description of the host'
        )
        parser.add_argument(
            '--inventory',
            required=True,
            help='Inventory name or ID'
        )
        parser.add_argument(
            '--variables',
            help='Host variables in JSON format'
        )
        parser.add_argument(
            '--enabled',
            action='store_true',
            default=True,
            help='Enable the host (default: true)'
        )
        parser.add_argument(
            '--disabled',
            action='store_true',
            help='Disable the host'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Resolve inventory
        if parsed_args.inventory.isdigit():
            inventory_id = int(parsed_args.inventory)
        else:
            inventories = client.list_inventories(name=parsed_args.inventory)
            inventory = utils.find_resource(inventories, parsed_args.inventory)
            inventory_id = inventory['id']

        # Prepare host data
        host_data = {
            'name': parsed_args.name,
            'inventory': inventory_id,
        }

        if parsed_args.description:
            host_data['description'] = parsed_args.description

        # Handle enabled/disabled flags
        if parsed_args.disabled:
            host_data['enabled'] = False
        else:
            host_data['enabled'] = parsed_args.enabled

        if parsed_args.variables:
            try:
                import json
                host_data['variables'] = json.loads(parsed_args.variables)
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON in variables: {e}")

        # Create the host
        try:
            data = client.create_host(host_data)
        except Exception as e:
            # Check if this is a duplicate host error
            if "400" in str(e) or "Bad Request" in str(e):
                # Check if a host with this name already exists in this inventory
                try:
                    existing_hosts = client.list_hosts(name=parsed_args.name, inventory=inventory_id)
                    if existing_hosts.get('count', 0) > 0:
                        existing_host = existing_hosts['results'][0]
                        raise CommandError(
                            f"Host '{parsed_args.name} (ID: {existing_host['id']})' already exists in this inventory"
                        )
                except CommandError:
                    # Re-raise our custom error
                    raise
                except Exception:
                    # If we can't check for duplicates, fall back to a generic message
                    pass

            # For other errors or if duplicate check failed, provide a generic error message
            raise CommandError(f"Failed to create host: {e}")

        # Display the created host
        display_data = [
            ('ID', data['id']),
            ('Name', data.get('name', '')),
            ('Description', data.get('description', '')),
            ('Inventory', data.get('inventory', '')),
            ('Enabled', 'Yes' if data.get('enabled', True) else 'No'),
            ('Created', format_datetime(data.get('created'))),
        ]

        return zip(*display_data) if display_data else ((), ())


class SetHost(Command):
    """Set host properties"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'host',
            help='Host name or ID to modify'
        )
        parser.add_argument(
            '--name',
            help='New name for the host'
        )
        parser.add_argument(
            '--description',
            help='New description for the host'
        )
        parser.add_argument(
            '--variables',
            help='Host variables in JSON format'
        )
        parser.add_argument(
            '--enabled',
            action='store_true',
            help='Enable the host'
        )
        parser.add_argument(
            '--disabled',
            action='store_true',
            help='Disable the host'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Find host by name or ID
        if parsed_args.host.isdigit():
            host_id = int(parsed_args.host)
            # Get host details to obtain the name
            host_obj = client.get_host(host_id)
            host_name = host_obj['name']
        else:
            hosts = client.list_hosts(name=parsed_args.host)
            host = utils.find_resource(hosts, parsed_args.host)
            host_id = host['id']
            host_name = host['name']

        # Build update data
        update_data = {}
        if parsed_args.name:
            update_data['name'] = parsed_args.name
        if parsed_args.description:
            update_data['description'] = parsed_args.description
        if parsed_args.variables:
            try:
                import json
                update_data['variables'] = json.loads(parsed_args.variables)
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON in variables: {e}")

        # Handle enabled/disabled flags (mutually exclusive)
        if parsed_args.enabled and parsed_args.disabled:
            raise CommandError("Cannot specify both --enabled and --disabled")
        elif parsed_args.enabled:
            update_data['enabled'] = True
        elif parsed_args.disabled:
            update_data['enabled'] = False

        if not update_data:
            self.app.stdout.write("No changes specified\n")
            return

        # Update the host
        client.update_host(host_id, update_data)
        # Use the updated name if the name was changed, otherwise use the original name
        final_name = update_data.get('name', host_name)
        self.app.stdout.write(f"Host {final_name} updated\n")


class DeleteHost(Command):
    """Delete host(s)"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'hosts',
            nargs='*',
            help='Host name(s) or ID(s) to delete'
        )
        parser.add_argument(
            '--name',
            help='Delete host by name'
        )
        parser.add_argument(
            '--id',
            type=int,
            help='Delete host by ID'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        hosts_to_delete = []

        # Handle single host deletion via flags
        if parsed_args.id or parsed_args.name:
            if parsed_args.id and parsed_args.hosts:
                # ID flag with one positional argument - search by ID and validate name matches
                host_name = parsed_args.hosts[0]
                try:
                    host_obj = client.get_host(parsed_args.id)
                except Exception:
                    raise CommandError(f"Host with ID {parsed_args.id} not found")

                # Validate that the host found has the expected name
                if host_obj['name'] != host_name:
                    raise CommandError(
                        f"ID {parsed_args.id} and name '{host_name}' refer to different hosts: "
                        f"ID {parsed_args.id} is '{host_obj['name']}', not '{host_name}'"
                    )

            elif parsed_args.id:
                # Explicit ID lookup only
                try:
                    host_obj = client.get_host(parsed_args.id)
                except Exception:
                    raise CommandError(f"Host with ID {parsed_args.id} not found")

            else:
                # --name flag only
                hosts = client.list_hosts(name=parsed_args.name)
                if hosts['count'] == 0:
                    raise CommandError(f"Host with name '{parsed_args.name}' not found")
                elif hosts['count'] > 1:
                    raise CommandError(f"Multiple hosts found with name '{parsed_args.name}'")
                host_obj = hosts['results'][0]

            # Delete the single host
            host_id = host_obj['id']
            host_name = host_obj['name']
            hosts_to_delete.append((host_id, host_name))

        # Handle multiple hosts via positional arguments
        if parsed_args.hosts and not (parsed_args.id and len(parsed_args.hosts) == 1):
            for host_identifier in parsed_args.hosts:
                if host_identifier.isdigit():
                    # It's an ID
                    host_id = int(host_identifier)
                    try:
                        host_obj = client.get_host(host_id)
                        hosts_to_delete.append((host_id, host_obj['name']))
                    except Exception:
                        raise CommandError(f"Host with ID {host_id} not found")
                else:
                    # It's a name
                    hosts = client.list_hosts(name=host_identifier)
                    if hosts['count'] == 0:
                        raise CommandError(f"Host with name '{host_identifier}' not found")
                    elif hosts['count'] > 1:
                        raise CommandError(f"Multiple hosts found with name '{host_identifier}'")

                    host_obj = hosts['results'][0]
                    hosts_to_delete.append((host_obj['id'], host_obj['name']))

        if not hosts_to_delete:
            raise CommandError("No hosts specified for deletion")

        # Delete hosts
        for host_id, host_name in hosts_to_delete:
            try:
                client.delete_host(host_id)
                self.app.stdout.write(f"Host '{host_name}' (ID: {host_id}) deleted\n")
            except Exception as e:
                self.app.stdout.write(f"Failed to delete host '{host_name}' (ID: {host_id}): {e}\n")


class HostMetrics(Lister):
    """Display host automation metrics"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--long',
            action='store_true',
            default=False,
            help='List additional fields in output'
        )
        parser.add_argument(
            '--hostname',
            metavar='<hostname>',
            help='Filter by hostname'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of results (default: 20)'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        params = {}
        if parsed_args.hostname:
            params['hostname'] = parsed_args.hostname

        # Set consistent default limit of 20 (same as other list commands)
        if parsed_args.limit:
            params['page_size'] = parsed_args.limit
        else:
            params['page_size'] = 20

        # Sort by ID for consistency with other list commands
        params['order_by'] = 'id'

        data = client.list_host_metrics(**params)

        # Standard columns: ID, Hostname, First Automated, Last Automated, Automation Count, Deleted, Deleted Count
        columns = ('ID', 'Hostname', 'First Automated', 'Last Automated', 'Automation Count', 'Deleted', 'Deleted Count')
        column_headers = columns

        if parsed_args.long:
            # Long format adds additional fields
            columns = ('ID', 'Hostname', 'First Automated', 'Last Automated', 'Automation Count', 'Deleted', 'Deleted Count', 'Created', 'Modified')
            column_headers = columns

        metrics = []
        for metric in data.get('results', []):
            metric_info = [
                metric['id'],
                metric.get('hostname', ''),
                format_datetime(metric.get('first_automation')),
                format_datetime(metric.get('last_automation')),
                metric.get('automated_counter', 0),
                'Yes' if metric.get('deleted', False) else 'No',
                metric.get('deleted_counter', 0),
            ]

            if parsed_args.long:
                metric_info.extend([
                    format_datetime(metric.get('created')),
                    format_datetime(metric.get('modified')),
                ])

            metrics.append(metric_info)

        return (column_headers, metrics)
