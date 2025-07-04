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
Credential commands for AAP Controller v2 API
"""

import logging

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common import utils
from aapclient.common.utils import format_name


LOG = logging.getLogger(__name__)


class ListCredential(Lister):
    """List credentials"""

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
            '--credential-type',
            help='Filter by credential type'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        params = {}
        if parsed_args.organization:
            params['organization'] = parsed_args.organization
        if parsed_args.credential_type:
            params['credential_type'] = parsed_args.credential_type

        # Sort by ID for consistency with other list commands
        params['order_by'] = 'id'

        data = client.list_credentials(**params)

        # Process the data to replace IDs with names
        for credential in data.get('results', []):
            # Extract credential type name from summary_fields
            if 'summary_fields' in credential and 'credential_type' in credential['summary_fields']:
                credential['credential_type_name'] = credential['summary_fields']['credential_type']['name']
            else:
                credential['credential_type_name'] = str(credential.get('credential_type', ''))

            # Extract organization name from summary_fields
            if 'summary_fields' in credential and 'organization' in credential['summary_fields']:
                credential['organization_name'] = credential['summary_fields']['organization']['name']
            else:
                credential['organization_name'] = str(credential.get('organization', ''))

        if parsed_args.long:
            columns = ('ID', 'Name', 'Credential Type', 'Organization', 'Description', 'Created', 'Modified')
            column_headers = columns
        else:
            columns = ('ID', 'Name', 'Credential Type', 'Organization')
            column_headers = columns

        credentials = []
        for credential in data.get('results', []):
            credential_info = [
                credential['id'],
                credential.get('name', ''),
                credential.get('credential_type_name', ''),
                credential.get('organization_name', ''),
            ]

            if parsed_args.long:
                credential_info.extend([
                    credential.get('description', ''),
                    utils.format_datetime(credential.get('created')),
                    utils.format_datetime(credential.get('modified')),
                ])

            credentials.append(credential_info)

        return (column_headers, credentials)


class ShowCredential(ShowOne):
    """Display credential details"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'credential',
            nargs='?',
            help='Credential name or ID to display'
        )

        # Create mutually exclusive group for --id and --name
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='Credential ID to display',
        )
        group.add_argument(
            '--name',
            metavar='<name>',
            help='Credential name to display',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Validate arguments
        if not any([parsed_args.credential, parsed_args.id, parsed_args.name]):
            raise utils.CommandError("Must specify a credential (by positional argument, --id, or --name)")

        # Check for redundant --name with positional argument
        if parsed_args.name and parsed_args.credential:
            raise utils.CommandError("Cannot use positional argument with --name (redundant)")

        # Determine lookup method
        data = None

        if parsed_args.id and parsed_args.credential:
            # ID flag with positional argument - search by ID and validate name matches
            try:
                data = client.get_credential(parsed_args.id)
            except Exception as e:
                raise utils.CommandError(f"Credential with ID {parsed_args.id} not found")

            # Validate that the credential found has the expected name
            if data['name'] != parsed_args.credential:
                raise utils.CommandError(
                    f"ID {parsed_args.id} and name '{parsed_args.credential}' refer to different credentials: "
                    f"ID {parsed_args.id} is '{data['name']}', not '{parsed_args.credential}'"
                )

        elif parsed_args.id:
            # Explicit ID lookup only
            try:
                data = client.get_credential(parsed_args.id)
            except Exception as e:
                raise utils.CommandError(f"Credential with ID {parsed_args.id} not found")

        else:
            # Name lookup (either explicit --name or positional argument)
            search_name = parsed_args.name or parsed_args.credential
            credentials = client.list_credentials(name=search_name)
            credential = utils.find_resource(credentials, search_name)
            data = client.get_credential(credential['id'])

        # Add names from summary_fields
        if 'summary_fields' in data and 'credential_type' in data['summary_fields']:
            data['credential_type_name'] = data['summary_fields']['credential_type']['name']
        else:
            data['credential_type_name'] = str(data.get('credential_type', ''))

        if 'summary_fields' in data and 'organization' in data['summary_fields']:
            data['organization_name'] = data['summary_fields']['organization']['name']
        else:
            data['organization_name'] = str(data.get('organization', ''))

        # Format the data for display (excluding sensitive input data)
        display_data = []
        fields = [
            'id', 'name', 'description', 'credential_type_name',
            'organization_name', 'created', 'modified',
            'created_by', 'modified_by'
        ]

        for field in fields:
            value = data.get(field, '')
            if field in ['created', 'modified']:
                value = utils.format_datetime(value)
            elif isinstance(value, bool):
                value = str(value)
            elif value is None:
                value = ''

            display_data.append((field.replace('_', ' ').title(), value))

        return zip(*display_data) if display_data else ((), ())


class CreateCredential(ShowOne):
    """Create a new credential"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            help='Name of the credential'
        )
        parser.add_argument(
            '--description',
            help='Description of the credential'
        )
        parser.add_argument(
            '--organization',
            required=True,
            help='Organization name or ID'
        )
        parser.add_argument(
            '--credential-type',
            required=True,
            help='Credential type ID or name'
        )
        parser.add_argument(
            '--username',
            help='Username for machine/SSH credentials'
        )
        parser.add_argument(
            '--password',
            help='Password for machine/SSH credentials'
        )
        parser.add_argument(
            '--ssh-key-data',
            help='SSH private key data'
        )
        parser.add_argument(
            '--ssh-key-unlock',
            help='SSH key unlock passphrase'
        )
        parser.add_argument(
            '--become-method',
            help='Privilege escalation method'
        )
        parser.add_argument(
            '--become-username',
            help='Privilege escalation username'
        )
        parser.add_argument(
            '--become-password',
            help='Privilege escalation password'
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

        # Prepare credential data
        credential_data = {
            'name': parsed_args.name,
            'organization': org_id,
            'credential_type': parsed_args.credential_type,
        }

        if parsed_args.description:
            credential_data['description'] = parsed_args.description

        # Build inputs dictionary for credential-specific data
        inputs = {}
        if parsed_args.username:
            inputs['username'] = parsed_args.username
        if parsed_args.password:
            inputs['password'] = parsed_args.password
        if parsed_args.ssh_key_data:
            inputs['ssh_key_data'] = parsed_args.ssh_key_data
        if parsed_args.ssh_key_unlock:
            inputs['ssh_key_unlock'] = parsed_args.ssh_key_unlock
        if parsed_args.become_method:
            inputs['become_method'] = parsed_args.become_method
        if parsed_args.become_username:
            inputs['become_username'] = parsed_args.become_username
        if parsed_args.become_password:
            inputs['become_password'] = parsed_args.become_password

        if inputs:
            credential_data['inputs'] = inputs

        # Create the credential
        data = client.create_credential(credential_data)

        # Display the created credential (without sensitive data)
        display_data = [
            ('ID', data['id']),
            ('Name', data.get('name', '')),
            ('Description', data.get('description', '')),
            ('Credential Type', data.get('credential_type_name', '')),
            ('Organization', data.get('organization_name', '')),
            ('Created', utils.format_datetime(data.get('created'))),
        ]

        return zip(*display_data) if display_data else ((), ())


class SetCredential(Command):
    """Set credential properties"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'credential',
            help='Credential name or ID to modify'
        )
        parser.add_argument(
            '--name',
            help='New name for the credential'
        )
        parser.add_argument(
            '--description',
            help='New description for the credential'
        )
        parser.add_argument(
            '--username',
            help='Username for machine/SSH credentials'
        )
        parser.add_argument(
            '--password',
            help='Password for machine/SSH credentials'
        )
        parser.add_argument(
            '--ssh-key-data',
            help='SSH private key data'
        )
        parser.add_argument(
            '--ssh-key-unlock',
            help='SSH key unlock passphrase'
        )
        parser.add_argument(
            '--become-method',
            help='Privilege escalation method'
        )
        parser.add_argument(
            '--become-username',
            help='Privilege escalation username'
        )
        parser.add_argument(
            '--become-password',
            help='Privilege escalation password'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Find credential by name or ID
        if parsed_args.credential.isdigit():
            credential_id = int(parsed_args.credential)
        else:
            credentials = client.list_credentials(name=parsed_args.credential)
            credential = utils.find_resource(credentials, parsed_args.credential)
            credential_id = credential['id']

        # Build update data
        update_data = {}
        if parsed_args.name:
            update_data['name'] = parsed_args.name
        if parsed_args.description:
            update_data['description'] = parsed_args.description

        # Build inputs for credential-specific updates
        inputs = {}
        if parsed_args.username:
            inputs['username'] = parsed_args.username
        if parsed_args.password:
            inputs['password'] = parsed_args.password
        if parsed_args.ssh_key_data:
            inputs['ssh_key_data'] = parsed_args.ssh_key_data
        if parsed_args.ssh_key_unlock:
            inputs['ssh_key_unlock'] = parsed_args.ssh_key_unlock
        if parsed_args.become_method:
            inputs['become_method'] = parsed_args.become_method
        if parsed_args.become_username:
            inputs['become_username'] = parsed_args.become_username
        if parsed_args.become_password:
            inputs['become_password'] = parsed_args.become_password

        if inputs:
            update_data['inputs'] = inputs

        if not update_data:
            self.app.stdout.write("No changes specified\n")
            return

        # Update the credential
        client.update_credential(credential_id, update_data)
        self.app.stdout.write(f"Credential {credential_id} updated\n")


class DeleteCredential(Command):
    """Delete a credential"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'credential',
            nargs='*',
            help='Credential name or ID to delete'
        )

        # Create mutually exclusive group for --id and --name
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='Credential ID to delete',
        )
        group.add_argument(
            '--name',
            metavar='<name>',
            help='Credential name to delete',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Validate arguments
        if not any([parsed_args.credential, parsed_args.id, parsed_args.name]):
            raise utils.CommandError("Must specify credential(s) to delete")

        # Check for redundant --name with positional argument
        if parsed_args.name and parsed_args.credential:
            raise utils.CommandError("Cannot use positional arguments with --name (redundant)")

        # Check for --id with multiple positional arguments
        if parsed_args.id and len(parsed_args.credential) > 1:
            raise utils.CommandError("Cannot use --id with multiple positional arguments")

        # Handle single credential deletion via flags
        if parsed_args.id or parsed_args.name:
            if parsed_args.id and parsed_args.credential:
                # ID flag with one positional argument - search by ID and validate name matches
                credential_name = parsed_args.credential[0]
                try:
                    credential_obj = client.get_credential(parsed_args.id)
                except Exception as e:
                    raise utils.CommandError(f"Credential with ID {parsed_args.id} not found")

                # Validate that the credential found has the expected name
                if credential_obj['name'] != credential_name:
                    raise utils.CommandError(
                        f"ID {parsed_args.id} and name '{credential_name}' refer to different credentials: "
                        f"ID {parsed_args.id} is '{credential_obj['name']}', not '{credential_name}'"
                    )

            elif parsed_args.id:
                # Explicit ID lookup only
                try:
                    credential_obj = client.get_credential(parsed_args.id)
                except Exception as e:
                    raise utils.CommandError(f"Credential with ID {parsed_args.id} not found")

            else:
                # --name flag only
                credentials = client.list_credentials(name=parsed_args.name)
                try:
                    credential_obj = utils.find_resource(credentials, parsed_args.name)
                except Exception as e:
                    raise utils.CommandError(f"Credential with name '{parsed_args.name}' not found")

            # Delete the single credential
            credential_id = credential_obj['id']
            credential_name = credential_obj['name']

            try:
                client.delete_credential(credential_id)
                self.app.stdout.write(f"Credential {format_name(credential_name)} (ID: {credential_id}) deleted\n")
            except Exception as e:
                raise utils.CommandError(f"Failed to delete credential {format_name(credential_name)}: {e}")
            return

        # Handle multiple credentials via positional arguments (default to name lookup)
        for credential_name_or_id in parsed_args.credential:
            try:
                # Default to name lookup for positional arguments
                credentials = client.list_credentials(name=credential_name_or_id)
                try:
                    credential = utils.find_resource(credentials, credential_name_or_id)
                    credential_id = credential['id']
                    credential_name = credential['name']
                except Exception:
                    # If name lookup fails, it might be an ID
                    if credential_name_or_id.isdigit():
                        credential_id = int(credential_name_or_id)
                        credential_obj = client.get_credential(credential_id)
                        credential_name = credential_obj['name']
                    else:
                        raise utils.CommandError(f"Credential '{credential_name_or_id}' not found")

                # Delete the credential
                client.delete_credential(credential_id)
                self.app.stdout.write(f"Credential {format_name(credential_name)} (ID: {credential_id}) deleted\n")
            except Exception as e:
                self.app.stdout.write(f"Failed to delete credential {format_name(credential_name_or_id)}: {e}\n")
