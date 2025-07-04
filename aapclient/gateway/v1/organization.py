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

from aapclient.common.utils import get_dict_properties, CommandError, format_name


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
        gateway_client = self.app.client_manager.gateway
        controller_client = self.app.client_manager.controller

        data = gateway_client.list_organizations()

        # Enhance organization data with user and team counts
        for org in data.get('results', []):
            # Try to get counts from Controller API first (more comprehensive)
            try:
                controller_org = controller_client.get_organization(org['id'])
                controller_counts = controller_org.get('summary_fields', {}).get('related_field_counts', {})
                org['users'] = controller_counts.get('users', 0)
                org['teams'] = controller_counts.get('teams', 0)
            except Exception:
                # Fall back to Gateway API counts if Controller API unavailable
                gateway_counts = org.get('summary_fields', {}).get('related_field_counts', {})
                org['users'] = gateway_counts.get('users', 0)
                org['teams'] = gateway_counts.get('teams', 0)

        # GUI-aligned columns: ID, Name, Users, Teams
        columns = ['ID', 'Name', 'Users', 'Teams']
        display_columns = ['id', 'name', 'users', 'teams']

        if parsed_args.long:
            # Long format adds Description, Managed, Created, Modified while preserving primary column order
            columns = ['ID', 'Name', 'Users', 'Teams', 'Description', 'Managed', 'Created', 'Modified']
            display_columns = ['id', 'name', 'users', 'teams', 'description', 'managed', 'created', 'modified']

        return (
            columns,
            (get_dict_properties(item, display_columns) for item in data.get('results', []))
        )


class ShowOrganization(ShowOne):
    """Show organization details"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'organization',
            metavar='<organization>',
            nargs='?',
            help='Organization to display (name or ID)',
        )

        # Create mutually exclusive group for --id and --name
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='Organization ID to display',
        )
        group.add_argument(
            '--name',
            metavar='<name>',
            help='Organization name to display',
        )
        return parser

    def take_action(self, parsed_args):
        gateway_client = self.app.client_manager.gateway
        controller_client = self.app.client_manager.controller

        # Validate arguments
        if not any([parsed_args.organization, parsed_args.id, parsed_args.name]):
            raise CommandError("Must specify an organization (by positional argument, --id, or --name)")

        # Check for redundant --name with positional argument
        if parsed_args.name and parsed_args.organization:
            raise CommandError("Cannot use positional argument with --name (redundant)")

        # Determine lookup method
        gateway_org = None
        org_id = None

        if parsed_args.id and parsed_args.organization:
            # ID flag with positional argument - search by ID and validate name matches
            try:
                gateway_org = gateway_client.get_organization(parsed_args.id)
                org_id = parsed_args.id
            except Exception as e:
                raise CommandError(f"Organization with ID {parsed_args.id} not found")

            # Validate that the organization found has the expected name
            if gateway_org['name'] != parsed_args.organization:
                raise CommandError(
                    f"ID {parsed_args.id} and name '{parsed_args.organization}' refer to different organizations: "
                    f"ID {parsed_args.id} is '{gateway_org['name']}', not '{parsed_args.organization}'"
                )

        elif parsed_args.id:
            # Explicit ID lookup only
            try:
                gateway_org = gateway_client.get_organization(parsed_args.id)
                org_id = parsed_args.id
            except Exception as e:
                raise CommandError(f"Organization with ID {parsed_args.id} not found")

        else:
            # Name lookup (either explicit --name or positional argument)
            search_name = parsed_args.name or parsed_args.organization
            orgs = gateway_client.list_organizations(name=search_name)
            if orgs['count'] == 0:
                raise CommandError(f"Organization with name '{search_name}' not found")
            elif orgs['count'] > 1:
                raise CommandError(f"Multiple organizations found with name '{search_name}'")
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
            nargs='*',
            help='Organization(s) to delete (name or ID)',
        )

        # Create mutually exclusive group for --id and --name
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='Organization ID to delete',
        )
        group.add_argument(
            '--name',
            metavar='<name>',
            help='Organization name to delete',
        )
        return parser

    def take_action(self, parsed_args):
        gateway_client = self.app.client_manager.gateway

        # Validate arguments
        if not any([parsed_args.organizations, parsed_args.id, parsed_args.name]):
            raise CommandError("Must specify organization(s) to delete")

        # Check for redundant --name with positional argument
        if parsed_args.name and parsed_args.organizations:
            raise CommandError("Cannot use positional arguments with --name (redundant)")

        # Check for --id with multiple positional arguments
        if parsed_args.id and len(parsed_args.organizations) > 1:
            raise CommandError("Cannot use --id with multiple positional arguments")

        # Handle single organization deletion via flags
        if parsed_args.id or parsed_args.name:
            if parsed_args.id and parsed_args.organizations:
                # ID flag with one positional argument - search by ID and validate name matches
                org_name = parsed_args.organizations[0]
                try:
                    org = gateway_client.get_organization(parsed_args.id)
                except Exception as e:
                    raise CommandError(f"Organization with ID {parsed_args.id} not found")

                # Validate that the organization found has the expected name
                if org['name'] != org_name:
                    raise CommandError(
                        f"ID {parsed_args.id} and name '{org_name}' refer to different organizations: "
                        f"ID {parsed_args.id} is '{org['name']}', not '{org_name}'"
                    )

            elif parsed_args.id:
                # Explicit ID lookup only
                try:
                    org = gateway_client.get_organization(parsed_args.id)
                except Exception as e:
                    raise CommandError(f"Organization with ID {parsed_args.id} not found")

            else:
                # --name flag only
                orgs = gateway_client.list_organizations(name=parsed_args.name)
                if orgs['count'] == 0:
                    raise CommandError(f"Organization with name '{parsed_args.name}' not found")
                elif orgs['count'] > 1:
                    raise CommandError(f"Multiple organizations found with name '{parsed_args.name}'")
                org = orgs['results'][0]

            # Delete the single organization
            org_id = org['id']
            org_name = org['name']

            try:
                gateway_client.delete_organization(org_id)
                self.app.stdout.write(f"Organization {format_name(org_name)} (ID: {org_id}) deleted\n")
            except Exception as e:
                raise CommandError(f"Failed to delete organization {format_name(org_name)}: {e}")
            return

        # Handle multiple organizations via positional arguments (default to name lookup)
        for org_identifier in parsed_args.organizations:
            try:
                # Default to name lookup for positional arguments
                orgs = gateway_client.list_organizations(name=org_identifier)
                if orgs['count'] == 0:
                    # If name lookup fails, it might be an ID
                    try:
                        org_id = int(org_identifier)
                        org = gateway_client.get_organization(org_id)
                    except (ValueError, Exception):
                        self.app.stdout.write(f"Organization '{org_identifier}' not found\n")
                        continue
                elif orgs['count'] > 1:
                    self.app.stdout.write(f"Multiple organizations found with name '{org_identifier}'\n")
                    continue
                else:
                    org = orgs['results'][0]
                    org_id = org['id']

                # Delete from Gateway API (this should cascade to Controller)
                gateway_client.delete_organization(org_id)
                self.app.stdout.write(f"Organization {format_name(org['name'])} (ID: {org_id}) deleted\n")

            except Exception as e:
                self.app.stdout.write(f"Failed to delete organization {format_name(org_identifier)}: {e}\n")


class SetOrganization(ShowOne):
    """Set organization properties"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'organization',
            metavar='<organization>',
            nargs='?',
            help='Organization to modify (name or ID)',
        )

        # Create mutually exclusive group for --id and --org-name
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='Organization ID to modify',
        )
        group.add_argument(
            '--org-name',
            metavar='<name>',
            help='Organization name to modify',
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

        # Validate arguments
        if not any([parsed_args.organization, parsed_args.id, parsed_args.org_name]):
            raise CommandError("Must specify an organization (by positional argument, --id, or --org-name)")

        # Check for redundant --org-name with positional argument
        if parsed_args.org_name and parsed_args.organization:
            raise CommandError("Cannot use positional argument with --org-name (redundant)")

        # Determine lookup method
        org_id = None

        if parsed_args.id and parsed_args.organization:
            # ID flag with positional argument - search by ID and validate name matches
            try:
                org = gateway_client.get_organization(parsed_args.id)
                org_id = parsed_args.id
            except Exception as e:
                raise CommandError(f"Organization with ID {parsed_args.id} not found")

            # Validate that the organization found has the expected name
            if org['name'] != parsed_args.organization:
                raise CommandError(
                    f"ID {parsed_args.id} and name '{parsed_args.organization}' refer to different organizations: "
                    f"ID {parsed_args.id} is '{org['name']}', not '{parsed_args.organization}'"
                )

        elif parsed_args.id:
            # Explicit ID lookup only
            org_id = parsed_args.id

        else:
            # Name lookup (either explicit --org-name or positional argument)
            search_name = parsed_args.org_name or parsed_args.organization
            orgs = gateway_client.list_organizations(name=search_name)
            if orgs['count'] == 0:
                raise CommandError(f"Organization with name '{search_name}' not found")
            elif orgs['count'] > 1:
                raise CommandError(f"Multiple organizations found with name '{search_name}'")
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
