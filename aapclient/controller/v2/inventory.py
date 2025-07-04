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
Inventory commands for AAP Controller v2 API
"""

import logging

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common import utils
from aapclient.common.utils import format_name


LOG = logging.getLogger(__name__)


class ListInventory(Lister):
    """List inventories"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--long',
            action='store_true',
            default=False,
            help='List additional fields in output'
        )
        parser.add_argument(
            '--organization',
            help='Filter by organization name or ID'
        )
        parser.add_argument(
            '--kind',
            choices=['', 'smart'],
            help='Filter by inventory kind (smart or regular)'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        params = {}
        if parsed_args.organization:
            params['organization'] = parsed_args.organization
        if parsed_args.kind:
            params['kind'] = parsed_args.kind

        data = client.list_inventories(**params)

        # Process the data to replace organization ID with name
        for inventory in data.get('results', []):
            if 'summary_fields' in inventory and 'organization' in inventory['summary_fields']:
                inventory['organization_name'] = inventory['summary_fields']['organization']['name']
            else:
                inventory['organization_name'] = str(inventory.get('organization', ''))

        # GUI-aligned columns: ID, Name, Status, Type, Organization, Labels, Hosts, Host Failures, Groups, Sources, Source Failures
        columns = ('ID', 'Name', 'Status', 'Type', 'Organization', 'Labels', 'Hosts', 'Host Failures', 'Groups', 'Sources', 'Source Failures')
        column_headers = columns

        if parsed_args.long:
            # Long format adds Description, Created, Modified while preserving primary column order
            columns = ('ID', 'Name', 'Status', 'Type', 'Organization', 'Labels', 'Hosts', 'Host Failures', 'Groups', 'Sources', 'Source Failures', 'Description', 'Created', 'Modified')
            column_headers = columns

        inventories = []
        for inventory in data.get('results', []):
            # Determine status - inventories may not have explicit status, use sync status or 'Ready'
            status = 'Ready'  # Default status for inventories
            if inventory.get('has_inventory_sources', False):
                if inventory.get('inventory_sources_with_failures', 0) > 0:
                    status = 'Failed'
                elif inventory.get('pending_deletion', False):
                    status = 'Deleting'
                # Add other status logic as needed

            # Format type (convert 'kind' field)
            inventory_type = inventory.get('kind', '')
            if inventory_type == '':
                inventory_type = 'Inventory'
            elif inventory_type == 'smart':
                inventory_type = 'Smart Inventory'

            # Handle labels - may be in variables or separate field
            labels = ''
            if 'variables' in inventory and isinstance(inventory['variables'], dict):
                # Look for labels in variables
                vars_dict = inventory['variables']
                if 'labels' in vars_dict:
                    labels = ', '.join(vars_dict['labels']) if isinstance(vars_dict['labels'], list) else str(vars_dict['labels'])

            inventory_info = [
                inventory['id'],
                inventory.get('name', ''),
                status,
                inventory_type,
                inventory.get('organization_name', ''),
                labels,
                inventory.get('total_hosts', 0),
                inventory.get('hosts_with_active_failures', 0),
                inventory.get('total_groups', 0),
                inventory.get('total_inventory_sources', 0),
                inventory.get('inventory_sources_with_failures', 0),
            ]

            if parsed_args.long:
                inventory_info.extend([
                    inventory.get('description', ''),
                    utils.format_datetime(inventory.get('created')),
                    utils.format_datetime(inventory.get('modified')),
                ])

            inventories.append(inventory_info)

        return (column_headers, inventories)


class ShowInventory(ShowOne):
    """Display inventory details"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'inventory',
            nargs='?',
            help='Inventory name or ID to display'
        )

        # Create mutually exclusive group for --id and --name
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='Inventory ID to display',
        )
        group.add_argument(
            '--name',
            metavar='<name>',
            help='Inventory name to display',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Validate arguments
        if not any([parsed_args.inventory, parsed_args.id, parsed_args.name]):
            raise utils.CommandError("Must specify an inventory (by positional argument, --id, or --name)")

        # Check for redundant --name with positional argument
        if parsed_args.name and parsed_args.inventory:
            raise utils.CommandError("Cannot use positional argument with --name (redundant)")

        # Determine lookup method
        data = None

        if parsed_args.id and parsed_args.inventory:
            # ID flag with positional argument - search by ID and validate name matches
            try:
                data = client.get_inventory(parsed_args.id)
            except Exception as e:
                raise utils.CommandError(f"Inventory with ID {parsed_args.id} not found")

            # Validate that the inventory found has the expected name
            if data['name'] != parsed_args.inventory:
                raise utils.CommandError(
                    f"ID {parsed_args.id} and name '{parsed_args.inventory}' refer to different inventories: "
                    f"ID {parsed_args.id} is '{data['name']}', not '{parsed_args.inventory}'"
                )

        elif parsed_args.id:
            # Explicit ID lookup only
            try:
                data = client.get_inventory(parsed_args.id)
            except Exception as e:
                raise utils.CommandError(f"Inventory with ID {parsed_args.id} not found")

        else:
            # Name lookup (either explicit --name or positional argument)
            search_name = parsed_args.name or parsed_args.inventory
            inventories = client.list_inventories(name=search_name)
            inventory = utils.find_resource(inventories, search_name)
            data = client.get_inventory(inventory['id'])

        # Add organization name from summary_fields
        if 'summary_fields' in data and 'organization' in data['summary_fields']:
            data['organization_name'] = data['summary_fields']['organization']['name']
        else:
            data['organization_name'] = str(data.get('organization', ''))

        # Format the data for display
        display_data = []
        fields = [
            'id', 'name', 'description', 'kind', 'host_filter', 'variables',
            'organization_name', 'total_hosts', 'hosts_with_active_failures',
            'total_groups', 'total_inventory_sources', 'inventory_sources_with_failures',
            'created', 'modified', 'created_by', 'modified_by'
        ]

        for field in fields:
            value = data.get(field, '')
            if field in ['created', 'modified']:
                value = utils.format_datetime(value)
            elif isinstance(value, bool):
                value = str(value)
            elif isinstance(value, dict) and field == 'variables':
                # Format variables as YAML-like string
                if value:
                    value = str(value)
                else:
                    value = ''
            elif value is None:
                value = ''

            display_data.append((field.replace('_', ' ').title(), value))

        return zip(*display_data) if display_data else ((), ())


class CreateInventory(ShowOne):
    """Create a new inventory"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            help='Name of the inventory'
        )
        parser.add_argument(
            '--description',
            help='Description of the inventory'
        )
        parser.add_argument(
            '--organization',
            required=True,
            help='Organization name or ID'
        )
        parser.add_argument(
            '--kind',
            choices=['', 'smart'],
            default='',
            help='Inventory kind (smart or regular, default: regular)'
        )
        parser.add_argument(
            '--host-filter',
            help='Host filter for smart inventories'
        )
        parser.add_argument(
            '--variables',
            help='Inventory variables in JSON format'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Resolve organization
        if parsed_args.organization.isdigit():
            org_id = int(parsed_args.organization)
        else:
            orgs = client.list_organizations(name=parsed_args.organization)
            org = utils.find_resource(orgs, parsed_args.organization)
            org_id = org['id']

        # Prepare inventory data
        inventory_data = {
            'name': parsed_args.name,
            'organization': org_id,
        }

        if parsed_args.description:
            inventory_data['description'] = parsed_args.description

        if parsed_args.kind:
            inventory_data['kind'] = parsed_args.kind

        if parsed_args.host_filter:
            inventory_data['host_filter'] = parsed_args.host_filter

        if parsed_args.variables:
            try:
                import json
                inventory_data['variables'] = json.loads(parsed_args.variables)
            except json.JSONDecodeError as e:
                raise utils.CommandError(f"Invalid JSON in variables: {e}")

        # Create the inventory
        data = client.create_inventory(inventory_data)

        # Display the created inventory
        display_data = [
            ('ID', data['id']),
            ('Name', data.get('name', '')),
            ('Description', data.get('description', '')),
            ('Kind', data.get('kind', 'regular')),
            ('Organization', data.get('organization_name', '')),
            ('Host Filter', data.get('host_filter', '')),
            ('Total Hosts', data.get('total_hosts', 0)),
            ('Created', utils.format_datetime(data.get('created'))),
        ]

        return zip(*display_data) if display_data else ((), ())


class SetInventory(Command):
    """Set inventory properties"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'inventory',
            help='Inventory name or ID to modify'
        )
        parser.add_argument(
            '--name',
            help='New name for the inventory'
        )
        parser.add_argument(
            '--description',
            help='New description for the inventory'
        )
        parser.add_argument(
            '--host-filter',
            help='Host filter for smart inventories'
        )
        parser.add_argument(
            '--variables',
            help='Inventory variables in JSON format'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Find inventory by name or ID
        if parsed_args.inventory.isdigit():
            inventory_id = int(parsed_args.inventory)
        else:
            inventories = client.list_inventories(name=parsed_args.inventory)
            inventory = utils.find_resource(inventories, parsed_args.inventory)
            inventory_id = inventory['id']

        # Build update data
        update_data = {}
        if parsed_args.name:
            update_data['name'] = parsed_args.name
        if parsed_args.description:
            update_data['description'] = parsed_args.description
        if parsed_args.host_filter:
            update_data['host_filter'] = parsed_args.host_filter
        if parsed_args.variables:
            try:
                import json
                update_data['variables'] = json.loads(parsed_args.variables)
            except json.JSONDecodeError as e:
                raise utils.CommandError(f"Invalid JSON in variables: {e}")

        if not update_data:
            self.app.stdout.write("No changes specified\n")
            return

        # Update the inventory
        client.update_inventory(inventory_id, update_data)
        self.app.stdout.write(f"Inventory {inventory_id} updated\n")


class DeleteInventory(Command):
    """Delete an inventory"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'inventory',
            nargs='*',
            help='Inventory name or ID to delete'
        )

        # Create mutually exclusive group for --id and --name
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='Inventory ID to delete',
        )
        group.add_argument(
            '--name',
            metavar='<name>',
            help='Inventory name to delete',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Validate arguments
        if not any([parsed_args.inventory, parsed_args.id, parsed_args.name]):
            raise utils.CommandError("Must specify inventory(s) to delete")

        # Check for redundant --name with positional argument
        if parsed_args.name and parsed_args.inventory:
            raise utils.CommandError("Cannot use positional arguments with --name (redundant)")

        # Check for --id with multiple positional arguments
        if parsed_args.id and len(parsed_args.inventory) > 1:
            raise utils.CommandError("Cannot use --id with multiple positional arguments")

        # Handle single inventory deletion via flags
        if parsed_args.id or parsed_args.name:
            if parsed_args.id and parsed_args.inventory:
                # ID flag with one positional argument - search by ID and validate name matches
                inventory_name = parsed_args.inventory[0]
                try:
                    inventory_obj = client.get_inventory(parsed_args.id)
                except Exception as e:
                    raise utils.CommandError(f"Inventory with ID {parsed_args.id} not found")

                # Validate that the inventory found has the expected name
                if inventory_obj['name'] != inventory_name:
                    raise utils.CommandError(
                        f"ID {parsed_args.id} and name '{inventory_name}' refer to different inventories: "
                        f"ID {parsed_args.id} is '{inventory_obj['name']}', not '{inventory_name}'"
                    )

            elif parsed_args.id:
                # Explicit ID lookup only
                try:
                    inventory_obj = client.get_inventory(parsed_args.id)
                except Exception as e:
                    raise utils.CommandError(f"Inventory with ID {parsed_args.id} not found")

            else:
                # --name flag only
                inventories = client.list_inventories(name=parsed_args.name)
                try:
                    inventory_obj = utils.find_resource(inventories, parsed_args.name)
                except Exception as e:
                    raise utils.CommandError(f"Inventory with name '{parsed_args.name}' not found")

            # Delete the single inventory
            inventory_id = inventory_obj['id']
            inventory_name = inventory_obj['name']

            try:
                client.delete_inventory(inventory_id)
                self.app.stdout.write(f"Inventory {format_name(inventory_name)} (ID: {inventory_id}) deleted\n")
            except Exception as e:
                raise utils.CommandError(f"Failed to delete inventory {format_name(inventory_name)}: {e}")
            return

        # Handle multiple inventories via positional arguments (default to name lookup)
        for inventory_name_or_id in parsed_args.inventory:
            try:
                # Default to name lookup for positional arguments
                inventories = client.list_inventories(name=inventory_name_or_id)
                try:
                    inventory = utils.find_resource(inventories, inventory_name_or_id)
                    inventory_id = inventory['id']
                    inventory_name = inventory['name']
                except Exception:
                    # If name lookup fails, it might be an ID
                    if inventory_name_or_id.isdigit():
                        inventory_id = int(inventory_name_or_id)
                        inventory_obj = client.get_inventory(inventory_id)
                        inventory_name = inventory_obj['name']
                    else:
                        raise utils.CommandError(f"Inventory '{inventory_name_or_id}' not found")

                # Delete the inventory
                client.delete_inventory(inventory_id)
                self.app.stdout.write(f"Inventory {format_name(inventory_name)} (ID: {inventory_id}) deleted\n")
            except Exception as e:
                self.app.stdout.write(f"Failed to delete inventory {format_name(inventory_name_or_id)}: {e}\n")
