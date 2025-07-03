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

        if parsed_args.long:
            columns = ('ID', 'Name', 'Kind', 'Organization', 'Description', 'Host Count', 'Created', 'Modified')
            column_headers = columns
        else:
            columns = ('ID', 'Name', 'Kind', 'Organization', 'Host Count')
            column_headers = columns

        inventories = []
        for inventory in data.get('results', []):
            inventory_info = [
                inventory['id'],
                inventory.get('name', ''),
                inventory.get('kind', 'regular'),
                inventory.get('organization_name', ''),
                inventory.get('total_hosts', 0),
            ]

            if parsed_args.long:
                inventory_info.insert(4, inventory.get('description', ''))  # Insert description after organization
                inventory_info.extend([
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
            help='Inventory name or ID to display'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Find inventory by name or ID
        if parsed_args.inventory.isdigit():
            inventory_id = int(parsed_args.inventory)
            data = client.get_inventory(inventory_id)
        else:
            # Search by name
            inventories = client.list_inventories(name=parsed_args.inventory)
            inventory = utils.find_resource(inventories, parsed_args.inventory)
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
            nargs='+',
            help='Inventory name or ID to delete'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        for inventory_name_or_id in parsed_args.inventory:
            # Find inventory by name or ID
            if inventory_name_or_id.isdigit():
                inventory_id = int(inventory_name_or_id)
                inventory_name = inventory_name_or_id
            else:
                inventories = client.list_inventories(name=inventory_name_or_id)
                inventory = utils.find_resource(inventories, inventory_name_or_id)
                inventory_id = inventory['id']
                inventory_name = inventory['name']

            # Delete the inventory
            client.delete_inventory(inventory_id)
            self.app.stdout.write(f"Inventory '{inventory_name}' deleted\n")
