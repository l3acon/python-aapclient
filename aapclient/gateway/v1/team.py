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

from aapclient.common.utils import get_dict_properties, CommandError, format_name

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

        # Sort by ID for consistency with other list commands
        params['order_by'] = 'id'

        data = client.list_teams(**params)

        # Process the data to replace organization ID with name
        for team in data.get('results', []):
            if 'summary_fields' in team and 'organization' in team['summary_fields']:
                team['organization_name'] = team['summary_fields']['organization']['name']
            else:
                team['organization_name'] = str(team.get('organization', ''))

        if parsed_args.long:
            columns = ['id', 'name', 'organization_name', 'created', 'modified']
        else:
            columns = ['id', 'name', 'organization_name']

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
            nargs='?',
            help='Team to display (name or ID)',
        )

        # Create mutually exclusive group for --id and --name
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='Team ID to display',
        )
        group.add_argument(
            '--name',
            metavar='<name>',
            help='Team name to display',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.gateway

        # Validate arguments
        if not any([parsed_args.team, parsed_args.id, parsed_args.name]):
            raise CommandError("Must specify a team (by positional argument, --id, or --name)")

        # Check for redundant --name with positional argument
        if parsed_args.name and parsed_args.team:
            raise CommandError("Cannot use positional argument with --name (redundant)")

        # Determine lookup method
        team = None

        if parsed_args.id and parsed_args.team:
            # ID flag with positional argument - search by ID and validate name matches
            try:
                team = client.get_team(parsed_args.id)
            except Exception as e:
                raise CommandError(f"Team with ID {parsed_args.id} not found")

            # Validate that the team found has the expected name
            if team['name'] != parsed_args.team:
                raise CommandError(
                    f"ID {parsed_args.id} and name '{parsed_args.team}' refer to different teams: "
                    f"ID {parsed_args.id} is '{team['name']}', not '{parsed_args.team}'"
                )

        elif parsed_args.id:
            # Explicit ID lookup only
            try:
                team = client.get_team(parsed_args.id)
            except Exception as e:
                raise CommandError(f"Team with ID {parsed_args.id} not found")

        else:
            # Name lookup (either explicit --name or positional argument)
            search_name = parsed_args.name or parsed_args.team
            teams = client.list_teams(name=search_name)
            if teams['count'] == 0:
                raise CommandError(f"Team with name '{search_name}' not found")
            elif teams['count'] > 1:
                raise CommandError(f"Multiple teams found with name '{search_name}'")
            team = teams['results'][0]

        # Extract organization name from summary_fields
        org_info = team.get('summary_fields', {}).get('organization', {})
        team['organization_name'] = org_info.get('name', 'N/A')

        # Display columns
        display_columns = [
            'id', 'name', 'description', 'organization_name',
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
            nargs='*',
            help='Team(s) to delete (name or ID)',
        )

        # Create mutually exclusive group for --id and --name
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='Team ID to delete',
        )
        group.add_argument(
            '--name',
            metavar='<name>',
            help='Team name to delete',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.gateway

        # Validate arguments
        if not any([parsed_args.teams, parsed_args.id, parsed_args.name]):
            raise CommandError("Must specify team(s) to delete")

        # Check for redundant --name with positional argument
        if parsed_args.name and parsed_args.teams:
            raise CommandError("Cannot use positional arguments with --name (redundant)")

        # Check for --id with multiple positional arguments
        if parsed_args.id and len(parsed_args.teams) > 1:
            raise CommandError("Cannot use --id with multiple positional arguments")

        # Handle single team deletion via flags
        if parsed_args.id or parsed_args.name:
            if parsed_args.id and parsed_args.teams:
                # ID flag with one positional argument - search by ID and validate name matches
                team_name = parsed_args.teams[0]
                try:
                    team = client.get_team(parsed_args.id)
                except Exception as e:
                    raise CommandError(f"Team with ID {parsed_args.id} not found")

                # Validate that the team found has the expected name
                if team['name'] != team_name:
                    raise CommandError(
                        f"ID {parsed_args.id} and name '{team_name}' refer to different teams: "
                        f"ID {parsed_args.id} is '{team['name']}', not '{team_name}'"
                    )

            elif parsed_args.id:
                # Explicit ID lookup only
                try:
                    team = client.get_team(parsed_args.id)
                except Exception as e:
                    raise CommandError(f"Team with ID {parsed_args.id} not found")

            else:
                # --name flag only
                teams = client.list_teams(name=parsed_args.name)
                if teams['count'] == 0:
                    raise CommandError(f"Team with name '{parsed_args.name}' not found")
                elif teams['count'] > 1:
                    raise CommandError(f"Multiple teams found with name '{parsed_args.name}'")
                team = teams['results'][0]

            # Delete the single team
            team_id = team['id']
            team_name = team['name']

            try:
                client.delete_team(team_id)
                self.app.stdout.write(f"Team {format_name(team_name)} (ID: {team_id}) deleted\n")
            except Exception as e:
                raise CommandError(f"Failed to delete team {format_name(team_name)}: {e}")
            return

        # Handle multiple teams via positional arguments (default to name lookup)
        for team_identifier in parsed_args.teams:
            try:
                # Default to name lookup for positional arguments
                teams = client.list_teams(name=team_identifier)
                if teams['count'] == 0:
                    # If name lookup fails, it might be an ID
                    try:
                        team_id = int(team_identifier)
                        team = client.get_team(team_id)
                    except (ValueError, Exception):
                        self.app.stdout.write(f"Team '{team_identifier}' not found\n")
                        continue
                elif teams['count'] > 1:
                    self.app.stdout.write(f"Multiple teams found with name '{team_identifier}'\n")
                    continue
                else:
                    team = teams['results'][0]
                    team_id = team['id']

                # Delete the team
                client.delete_team(team_id)
                self.app.stdout.write(f"Team {format_name(team['name'])} (ID: {team_id}) deleted\n")

            except Exception as e:
                self.app.stdout.write(f"Failed to delete team {format_name(team_identifier)}: {e}\n")


class SetTeam(ShowOne):
    """Set team properties"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'team',
            metavar='<team>',
            nargs='?',
            help='Team to modify (name or ID)',
        )

        # Create mutually exclusive group for --id and --team-name
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='Team ID to modify',
        )
        group.add_argument(
            '--team-name',
            metavar='<name>',
            help='Team name to modify',
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

        # Validate arguments
        if not any([parsed_args.team, parsed_args.id, parsed_args.team_name]):
            raise CommandError("Must specify a team (by positional argument, --id, or --team-name)")

        # Check for redundant --team-name with positional argument
        if parsed_args.team_name and parsed_args.team:
            raise CommandError("Cannot use positional argument with --team-name (redundant)")

        # Determine lookup method
        team_id = None

        if parsed_args.id and parsed_args.team:
            # ID flag with positional argument - search by ID and validate name matches
            try:
                team = client.get_team(parsed_args.id)
                team_id = parsed_args.id
            except Exception as e:
                raise CommandError(f"Team with ID {parsed_args.id} not found")

            # Validate that the team found has the expected name
            if team['name'] != parsed_args.team:
                raise CommandError(
                    f"ID {parsed_args.id} and name '{parsed_args.team}' refer to different teams: "
                    f"ID {parsed_args.id} is '{team['name']}', not '{parsed_args.team}'"
                )

        elif parsed_args.id:
            # Explicit ID lookup only
            team_id = parsed_args.id

        else:
            # Name lookup (either explicit --team-name or positional argument)
            search_name = parsed_args.team_name or parsed_args.team
            teams = client.list_teams(name=search_name)
            if teams['count'] == 0:
                raise CommandError(f"Team with name '{search_name}' not found")
            elif teams['count'] > 1:
                raise CommandError(f"Multiple teams found with name '{search_name}'")
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
