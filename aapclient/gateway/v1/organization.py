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

"""Organization management commands using both Gateway and Controller APIs"""

import logging

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common.utils import get_dict_properties, CommandError


LOG = logging.getLogger(__name__)


class ListOrganization(Lister):
    """List organizations"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--long',
            action='store_true',
            help='List additional fields in output',
        )
        return parser

    def take_action(self, parsed_args):
        # Use Gateway API for listing (identity management)
        client = self.app.client_manager.gateway

        data = client.list_organizations()

        if parsed_args.long:
            columns = ['id', 'name', 'description', 'managed', 'created', 'modified']
        else:
            columns = ['id', 'name', 'description']

        return (
            columns,
            (get_dict_properties(item, columns) for item in data.get('results', []))
        )


class ShowOrganization(ShowOne):
    """Show organization details"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'organization',
            metavar='<organization>',
            help='Organization to display (name or ID)',
        )
        return parser

    def take_action(self, parsed_args):
        gateway_client = self.app.client_manager.gateway
        controller_client = self.app.client_manager.controller

        # Get organization from Gateway API (identity info)
        try:
            org_id = int(parsed_args.organization)
            gateway_org = gateway_client.get_organization(org_id)
        except ValueError:
            # Not an integer, search by name
            orgs = gateway_client.list_organizations(name=parsed_args.organization)
            if orgs['count'] == 0:
                raise CommandError(f"Organization '{parsed_args.organization}' not found")
            elif orgs['count'] > 1:
                raise CommandError(f"Multiple organizations found with name '{parsed_args.organization}'")
            gateway_org = orgs['results'][0]
            org_id = gateway_org['id']

        # Get operational details from Controller API
        try:
            controller_org = controller_client.get_organization(org_id)
        except Exception as e:
            LOG.warning(f"Could not fetch operational details from Controller API: {e}")
            controller_org = {}

        # Merge data prioritizing Gateway for identity, Controller for operational
        merged_org = gateway_org.copy()
        if controller_org:
            # Add operational fields from Controller API
            merged_org['max_hosts'] = controller_org.get('max_hosts')
            merged_org['custom_virtualenv'] = controller_org.get('custom_virtualenv')
            merged_org['default_environment'] = controller_org.get('default_environment')

            # Add related field counts from Controller API (more comprehensive)
            controller_counts = controller_org.get('summary_fields', {}).get('related_field_counts', {})
            merged_org['users'] = controller_counts.get('users', 0)
            merged_org['teams'] = controller_counts.get('teams', 0)
            merged_org['projects'] = controller_counts.get('projects', 0)
            merged_org['job_templates'] = controller_counts.get('job_templates', 0)
            merged_org['inventories'] = controller_counts.get('inventories', 0)
        else:
            # Fall back to Gateway API counts if Controller API unavailable
            gateway_counts = gateway_org.get('summary_fields', {}).get('related_field_counts', {})
            merged_org['users'] = gateway_counts.get('users', 0)
            merged_org['teams'] = gateway_counts.get('teams', 0)
            merged_org['projects'] = 0
            merged_org['job_templates'] = 0
            merged_org['inventories'] = 0

        # Display columns combining both APIs
        display_columns = [
            'id', 'name', 'description', 'max_hosts', 'managed',
            'users', 'teams', 'projects', 'job_templates', 'inventories',
            'created', 'modified'
        ]

        return (
            display_columns,
            get_dict_properties(merged_org, display_columns)
        )


class CreateOrganization(ShowOne):
    """Create a new organization"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            metavar='<name>',
            help='Name of the organization',
        )
        parser.add_argument(
            '--description',
            metavar='<description>',
            help='Description of the organization',
        )
        parser.add_argument(
            '--max-hosts',
            metavar='<max-hosts>',
            type=int,
            help='Maximum number of hosts allowed in this organization',
        )
        return parser

    def take_action(self, parsed_args):
        gateway_client = self.app.client_manager.gateway
        controller_client = self.app.client_manager.controller

        # Create in Gateway API first (identity)
        gateway_data = {
            'name': parsed_args.name,
        }

        if parsed_args.description:
            gateway_data['description'] = parsed_args.description

        gateway_org = gateway_client.create_organization(gateway_data)
        org_id = gateway_org['id']

        # Update operational settings in Controller API if specified
        merged_org = gateway_org.copy()
        if parsed_args.max_hosts is not None:
            try:
                controller_data = {'max_hosts': parsed_args.max_hosts}
                controller_org = controller_client.update_organization(org_id, controller_data)
                merged_org['max_hosts'] = controller_org.get('max_hosts')
            except Exception as e:
                LOG.warning(f"Could not set max_hosts in Controller API: {e}")
                merged_org['max_hosts'] = None

        display_columns = ['id', 'name', 'description', 'max_hosts', 'created']

        return (
            display_columns,
            get_dict_properties(merged_org, display_columns)
        )


class DeleteOrganization(Command):
    """Delete organization(s)"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'organizations',
            metavar='<organization>',
            nargs='+',
            help='Organization(s) to delete (name or ID)',
        )
        return parser

    def take_action(self, parsed_args):
        gateway_client = self.app.client_manager.gateway

        for org_identifier in parsed_args.organizations:
            try:
                # Try to get by ID first, then by name
                try:
                    org_id = int(org_identifier)
                    org = gateway_client.get_organization(org_id)
                except ValueError:
                    # Not an integer, search by name
                    orgs = gateway_client.list_organizations(name=org_identifier)
                    if orgs['count'] == 0:
                        self.app.stdout.write(f"Organization '{org_identifier}' not found\n")
                        continue
                    elif orgs['count'] > 1:
                        self.app.stdout.write(f"Multiple organizations found with name '{org_identifier}'\n")
                        continue
                    org = orgs['results'][0]
                    org_id = org['id']

                # Delete from Gateway API (this should cascade to Controller)
                gateway_client.delete_organization(org_id)
                self.app.stdout.write(f"Organization '{org['name']}' (ID: {org_id}) deleted\n")

            except Exception as e:
                self.app.stdout.write(f"Failed to delete organization '{org_identifier}': {e}\n")


class SetOrganization(ShowOne):
    """Set organization properties"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'organization',
            metavar='<organization>',
            help='Organization to modify (name or ID)',
        )
        parser.add_argument(
            '--name',
            metavar='<name>',
            help='New name for the organization',
        )
        parser.add_argument(
            '--description',
            metavar='<description>',
            help='Description of the organization',
        )
        parser.add_argument(
            '--max-hosts',
            metavar='<max-hosts>',
            type=int,
            help='Maximum number of hosts allowed in this organization',
        )
        return parser

    def take_action(self, parsed_args):
        gateway_client = self.app.client_manager.gateway
        controller_client = self.app.client_manager.controller

        # Find the organization
        try:
            org_id = int(parsed_args.organization)
        except ValueError:
            # Not an integer, search by name
            orgs = gateway_client.list_organizations(name=parsed_args.organization)
            if orgs['count'] == 0:
                raise CommandError(f"Organization '{parsed_args.organization}' not found")
            elif orgs['count'] > 1:
                raise CommandError(f"Multiple organizations found with name '{parsed_args.organization}'")
            org_id = orgs['results'][0]['id']

        updated_org = None

        # Update identity fields in Gateway API
        gateway_update = {}
        if parsed_args.name:
            gateway_update['name'] = parsed_args.name
        if parsed_args.description is not None:
            gateway_update['description'] = parsed_args.description

        if gateway_update:
            updated_org = gateway_client.update_organization(org_id, gateway_update)

        # Update operational fields in Controller API
        controller_update = {}
        if parsed_args.max_hosts is not None:
            controller_update['max_hosts'] = parsed_args.max_hosts

        if controller_update:
            try:
                controller_org = controller_client.update_organization(org_id, controller_update)
                if updated_org is None:
                    updated_org = gateway_client.get_organization(org_id)
                updated_org['max_hosts'] = controller_org.get('max_hosts')
            except Exception as e:
                LOG.warning(f"Could not update operational settings in Controller API: {e}")

        if updated_org is None:
            raise CommandError("No properties specified to update")

        display_columns = ['id', 'name', 'description', 'max_hosts', 'modified']

        return (
            display_columns,
            get_dict_properties(updated_org, display_columns)
        )
