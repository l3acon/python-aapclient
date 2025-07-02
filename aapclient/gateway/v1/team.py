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

"""Team management commands"""

import logging

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common.utils import get_dict_properties, CommandError

LOG = logging.getLogger(__name__)


class ListTeam(Lister):
    """List teams"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--organization',
            metavar='<organization>',
            help='Filter by organization name or ID',
        )
        parser.add_argument(
            '--long',
            action='store_true',
            help='List additional fields in output',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.gateway

        # Build query parameters
        params = {}
        if parsed_args.organization:
            # Try to resolve organization name to ID
            try:
                org_id = int(parsed_args.organization)
                params['organization'] = org_id
            except ValueError:
                # Search by name
                orgs = client.list_organizations(name=parsed_args.organization)
                if orgs['count'] == 0:
                    raise CommandError(f"Organization '{parsed_args.organization}' not found")
                elif orgs['count'] > 1:
                    raise CommandError(f"Multiple organizations found with name '{parsed_args.organization}'")
                params['organization'] = orgs['results'][0]['id']

        data = client.list_teams(**params)

        if parsed_args.long:
            columns = ['id', 'name', 'description', 'organization', 'created', 'modified']
        else:
            columns = ['id', 'name', 'description', 'organization']
        
        return (
            columns,
            (get_dict_properties(item, columns) for item in data.get('results', []))
        )


class ShowTeam(ShowOne):
    """Show team details"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'team',
            metavar='<team>',
            help='Team to display (name or ID)',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.gateway

        # Try to get by ID first, then by name
        try:
            team_id = int(parsed_args.team)
            team = client.get_team(team_id)
        except ValueError:
            # Not an integer, search by name
            teams = client.list_teams(name=parsed_args.team)
            if teams['count'] == 0:
                raise CommandError(f"Team '{parsed_args.team}' not found")
            elif teams['count'] > 1:
                raise CommandError(f"Multiple teams found with name '{parsed_args.team}'")
            team = teams['results'][0]

        # Extract organization name from summary_fields
        org_info = team.get('summary_fields', {}).get('organization', {})
        team['organization_name'] = org_info.get('name', 'N/A')

        # Display columns
        display_columns = [
            'id', 'name', 'description', 'organization', 'organization_name',
            'created', 'modified'
        ]
        
        return (
            display_columns,
            get_dict_properties(team, display_columns)
        )


class CreateTeam(ShowOne):
    """Create a new team"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            metavar='<name>',
            help='Name of the team',
        )
        parser.add_argument(
            '--description',
            metavar='<description>',
            help='Description of the team',
        )
        parser.add_argument(
            '--organization',
            metavar='<organization>',
            required=True,
            help='Organization name or ID for the team',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.gateway

        # Resolve organization name to ID
        try:
            org_id = int(parsed_args.organization)
        except ValueError:
            # Search by name
            orgs = client.list_organizations(name=parsed_args.organization)
            if orgs['count'] == 0:
                raise CommandError(f"Organization '{parsed_args.organization}' not found")
            elif orgs['count'] > 1:
                raise CommandError(f"Multiple organizations found with name '{parsed_args.organization}'")
            org_id = orgs['results'][0]['id']

        # Build team data
        team_data = {
            'name': parsed_args.name,
            'organization': org_id,
        }
        
        if parsed_args.description:
            team_data['description'] = parsed_args.description

        # Create the team
        team = client.create_team(team_data)
        
        display_columns = ['id', 'name', 'description', 'organization', 'created']
        
        return (
            display_columns,
            get_dict_properties(team, display_columns)
        )


class DeleteTeam(Command):
    """Delete team(s)"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'teams',
            metavar='<team>',
            nargs='+',
            help='Team(s) to delete (name or ID)',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.gateway
        
        for team_identifier in parsed_args.teams:
            try:
                # Try to get by ID first, then by name
                try:
                    team_id = int(team_identifier)
                    team = client.get_team(team_id)
                except ValueError:
                    # Not an integer, search by name
                    teams = client.list_teams(name=team_identifier)
                    if teams['count'] == 0:
                        self.app.stdout.write(f"Team '{team_identifier}' not found\n")
                        continue
                    elif teams['count'] > 1:
                        self.app.stdout.write(f"Multiple teams found with name '{team_identifier}'\n")
                        continue
                    team = teams['results'][0]
                    team_id = team['id']

                # Delete the team
                client.delete_team(team_id)
                self.app.stdout.write(f"Team '{team['name']}' (ID: {team_id}) deleted\n")
                
            except Exception as e:
                self.app.stdout.write(f"Failed to delete team '{team_identifier}': {e}\n")


class SetTeam(ShowOne):
    """Set team properties"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'team',
            metavar='<team>',
            help='Team to modify (name or ID)',
        )
        parser.add_argument(
            '--name',
            metavar='<name>',
            help='New name for the team',
        )
        parser.add_argument(
            '--description',
            metavar='<description>',
            help='Description of the team',
        )
        parser.add_argument(
            '--organization',
            metavar='<organization>',
            help='Organization name or ID to move the team to',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.gateway

        # Find the team
        try:
            team_id = int(parsed_args.team)
        except ValueError:
            # Not an integer, search by name
            teams = client.list_teams(name=parsed_args.team)
            if teams['count'] == 0:
                raise CommandError(f"Team '{parsed_args.team}' not found")
            elif teams['count'] > 1:
                raise CommandError(f"Multiple teams found with name '{parsed_args.team}'")
            team_id = teams['results'][0]['id']

        # Build update data
        update_data = {}
        if parsed_args.name:
            update_data['name'] = parsed_args.name
        if parsed_args.description is not None:
            update_data['description'] = parsed_args.description
        if parsed_args.organization:
            # Resolve organization name to ID
            try:
                org_id = int(parsed_args.organization)
                update_data['organization'] = org_id
            except ValueError:
                # Search by name
                orgs = client.list_organizations(name=parsed_args.organization)
                if orgs['count'] == 0:
                    raise CommandError(f"Organization '{parsed_args.organization}' not found")
                elif orgs['count'] > 1:
                    raise CommandError(f"Multiple organizations found with name '{parsed_args.organization}'")
                update_data['organization'] = orgs['results'][0]['id']

        if not update_data:
            raise CommandError("No properties specified to update")

        # Update the team
        updated_team = client.update_team(team_id, update_data)

        display_columns = ['id', 'name', 'description', 'organization', 'modified']
        
        return (
            display_columns,
            get_dict_properties(updated_team, display_columns)
        ) 