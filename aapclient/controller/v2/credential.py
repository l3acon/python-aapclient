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
            
        data = client.list_credentials(**params)
        
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
            help='Credential name or ID to display'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller
        
        # Find credential by name or ID
        if parsed_args.credential.isdigit():
            credential_id = int(parsed_args.credential)
            data = client.get_credential(credential_id)
        else:
            # Search by name
            credentials = client.list_credentials(name=parsed_args.credential)
            credential = utils.find_resource(credentials, parsed_args.credential)
            data = client.get_credential(credential['id'])
        
        # Format the data for display (excluding sensitive input data)
        display_data = []
        fields = [
            'id', 'name', 'description', 'credential_type', 'credential_type_name',
            'organization', 'organization_name', 'created', 'modified', 
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
            nargs='+',
            help='Credential name or ID to delete'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller
        
        for credential_name_or_id in parsed_args.credential:
            # Find credential by name or ID
            if credential_name_or_id.isdigit():
                credential_id = int(credential_name_or_id)
                credential_name = credential_name_or_id
            else:
                credentials = client.list_credentials(name=credential_name_or_id)
                credential = utils.find_resource(credentials, credential_name_or_id)
                credential_id = credential['id']
                credential_name = credential['name']
            
            # Delete the credential
            client.delete_credential(credential_id)
            self.app.stdout.write(f"Credential '{credential_name}' deleted\n") 