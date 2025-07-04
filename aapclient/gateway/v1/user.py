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

"""User management commands using Gateway API"""

import logging

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common.utils import get_dict_properties, CommandError, format_name, format_datetime


LOG = logging.getLogger(__name__)


class ListUser(Lister):
    """List users"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--long',
            action='store_true',
            help='List additional fields in output',
        )
        parser.add_argument(
            '--organization',
            metavar='<organization>',
            help='Filter by organization (name or ID)',
        )
        parser.add_argument(
            '--superuser',
            action='store_true',
            help='Filter to superusers only',
        )
        parser.add_argument(
            '--active',
            action='store_true',
            help='Filter to active users only',
        )
        parser.add_argument(
            '--inactive',
            action='store_true',
            help='Filter to inactive users only',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.gateway

        params = {}
        if parsed_args.organization:
            params['organization'] = parsed_args.organization
        if parsed_args.superuser:
            params['is_superuser'] = True
        if parsed_args.active:
            params['is_active'] = True
        elif parsed_args.inactive:
            params['is_active'] = False

        data = client.list_users(**params)

        # Process the data to add GUI-aligned fields
        for user in data.get('results', []):
            # Determine user type based on permissions
            user_type = 'Normal'
            if user.get('is_superuser'):
                user_type = 'System Administrator'
            elif user.get('is_platform_auditor'):
                user_type = 'System Auditor'
            user['user_type'] = user_type

            # Format last login timestamp
            user['last_login_formatted'] = format_datetime(user.get('last_login'))

        if parsed_args.long:
            columns = ('ID', 'Name', 'User Type', 'Email', 'First Name', 'Last Name', 'Last Login', 'Active', 'Created')
            display_columns = ['id', 'username', 'user_type', 'email', 'first_name', 'last_name', 'last_login_formatted', 'is_active', 'date_joined']
        else:
            columns = ('ID', 'Name', 'User Type', 'Email', 'First Name', 'Last Name', 'Last Login')
            display_columns = ['id', 'username', 'user_type', 'email', 'first_name', 'last_name', 'last_login_formatted']

        return (
            columns,
            (get_dict_properties(item, display_columns) for item in data.get('results', []))
        )


class ShowUser(ShowOne):
    """Show user details"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'user',
            metavar='<user>',
            nargs='?',
            help='User to display (username or ID)',
        )

        # Create mutually exclusive group for --id and --username
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='User ID to display',
        )
        group.add_argument(
            '--username',
            metavar='<username>',
            help='Username to display',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.gateway

        # Validate arguments
        if not any([parsed_args.user, parsed_args.id, parsed_args.username]):
            raise CommandError("Must specify a user (by positional argument, --id, or --username)")

        # Check for redundant --username with positional argument
        if parsed_args.username and parsed_args.user:
            raise CommandError("Cannot use positional argument with --username (redundant)")

        # Determine lookup method
        user = None

        if parsed_args.id and parsed_args.user:
            # ID flag with positional argument - search by ID and validate username matches
            try:
                user = client.get_user(parsed_args.id)
            except Exception as e:
                raise CommandError(f"User with ID {parsed_args.id} not found")

            # Validate that the user found has the expected username
            if user['username'] != parsed_args.user:
                raise CommandError(
                    f"ID {parsed_args.id} and username '{parsed_args.user}' refer to different users: "
                    f"ID {parsed_args.id} is '{user['username']}', not '{parsed_args.user}'"
                )

        elif parsed_args.id:
            # Explicit ID lookup only
            try:
                user = client.get_user(parsed_args.id)
            except Exception as e:
                raise CommandError(f"User with ID {parsed_args.id} not found")

        else:
            # Username lookup (either explicit --username or positional argument)
            search_username = parsed_args.username or parsed_args.user
            users = client.list_users(username=search_username)
            if users['count'] == 0:
                raise CommandError(f"User with username '{search_username}' not found")
            elif users['count'] > 1:
                raise CommandError(f"Multiple users found with username '{search_username}'")
            user = users['results'][0]

        # Common user attributes to display (using Gateway API field names)
        display_columns = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'managed', 'is_superuser', 'is_platform_auditor',
            'created', 'last_login'
        ]

        return (
            display_columns,
            get_dict_properties(user, display_columns)
        )


class CreateUser(ShowOne):
    """Create a new user"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'username',
            metavar='<username>',
            help='Username for the new user',
        )
        parser.add_argument(
            '--email',
            metavar='<email>',
            help='Email address',
        )
        parser.add_argument(
            '--first-name',
            metavar='<first-name>',
            help='First name',
        )
        parser.add_argument(
            '--last-name',
            metavar='<last-name>',
            help='Last name',
        )
        parser.add_argument(
            '--password',
            metavar='<password>',
            help='Password for the user',
        )
        parser.add_argument(
            '--organization',
            metavar='<organization>',
            help='Organization ID or name to assign the user to',
        )
        parser.add_argument(
            '--superuser',
            action='store_true',
            help='Make the user a superuser',
        )
        parser.add_argument(
            '--system-auditor',
            action='store_true',
            help='Make the user a system auditor',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.gateway

        # Build user data
        user_data = {
            'username': parsed_args.username,
        }

        if parsed_args.email:
            user_data['email'] = parsed_args.email
        if parsed_args.first_name:
            user_data['first_name'] = parsed_args.first_name
        if parsed_args.last_name:
            user_data['last_name'] = parsed_args.last_name
        if parsed_args.password:
            user_data['password'] = parsed_args.password
        if parsed_args.organization:
            user_data['organization'] = parsed_args.organization
        if parsed_args.superuser:
            user_data['is_superuser'] = True
        if parsed_args.system_auditor:
            user_data['is_system_auditor'] = True

        # Create the user
        user = client.create_user(user_data)

        display_columns = ['id', 'username', 'email', 'first_name', 'last_name', 'is_superuser', 'date_joined']

        return (
            display_columns,
            get_dict_properties(user, display_columns)
        )


class DeleteUser(Command):
    """Delete user(s)"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'users',
            metavar='<user>',
            nargs='*',
            help='User(s) to delete (username or ID)',
        )

        # Create mutually exclusive group for --id and --username
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='User ID to delete',
        )
        group.add_argument(
            '--username',
            metavar='<username>',
            help='Username to delete',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.gateway

        # Validate arguments
        if not any([parsed_args.users, parsed_args.id, parsed_args.username]):
            raise CommandError("Must specify user(s) to delete")

        # Check for redundant --username with positional argument
        if parsed_args.username and parsed_args.users:
            raise CommandError("Cannot use positional arguments with --username (redundant)")

        # Check for --id with multiple positional arguments
        if parsed_args.id and len(parsed_args.users) > 1:
            raise CommandError("Cannot use --id with multiple positional arguments")

        # Handle single user deletion via flags
        if parsed_args.id or parsed_args.username:
            if parsed_args.id and parsed_args.users:
                # ID flag with one positional argument - search by ID and validate username matches
                username = parsed_args.users[0]
                try:
                    user = client.get_user(parsed_args.id)
                except Exception as e:
                    raise CommandError(f"User with ID {parsed_args.id} not found")

                # Validate that the user found has the expected username
                if user['username'] != username:
                    raise CommandError(
                        f"ID {parsed_args.id} and username '{username}' refer to different users: "
                        f"ID {parsed_args.id} is '{user['username']}', not '{username}'"
                    )

            elif parsed_args.id:
                # Explicit ID lookup only
                try:
                    user = client.get_user(parsed_args.id)
                except Exception as e:
                    raise CommandError(f"User with ID {parsed_args.id} not found")

            else:
                # --username flag only
                users = client.list_users(username=parsed_args.username)
                if users['count'] == 0:
                    raise CommandError(f"User with username '{parsed_args.username}' not found")
                elif users['count'] > 1:
                    raise CommandError(f"Multiple users found with username '{parsed_args.username}'")
                user = users['results'][0]

            # Delete the single user
            user_id = user['id']
            username = user['username']

            try:
                client.delete_user(user_id)
                self.app.stdout.write(f"User {format_name(username)} (ID: {user_id}) deleted\n")
            except Exception as e:
                raise CommandError(f"Failed to delete user {format_name(username)}: {e}")
            return

        # Handle multiple users via positional arguments (default to username lookup)
        for user_identifier in parsed_args.users:
            try:
                # Default to username lookup for positional arguments
                users = client.list_users(username=user_identifier)
                if users['count'] == 0:
                    # If username lookup fails, it might be an ID
                    try:
                        user_id = int(user_identifier)
                        user = client.get_user(user_id)
                    except (ValueError, Exception):
                        self.app.stdout.write(f"User '{user_identifier}' not found\n")
                        continue
                elif users['count'] > 1:
                    self.app.stdout.write(f"Multiple users found with username '{user_identifier}'\n")
                    continue
                else:
                    user = users['results'][0]
                    user_id = user['id']

                # Delete the user
                client.delete_user(user_id)
                self.app.stdout.write(f"User {format_name(user['username'])} (ID: {user_id}) deleted\n")

            except Exception as e:
                self.app.stdout.write(f"Failed to delete user {format_name(user_identifier)}: {e}\n")


class SetUser(ShowOne):
    """Set user properties"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'user',
            metavar='<user>',
            help='User to modify (username or ID)',
        )
        parser.add_argument(
            '--username',
            metavar='<username>',
            help='New username',
        )
        parser.add_argument(
            '--email',
            metavar='<email>',
            help='Email address',
        )
        parser.add_argument(
            '--first-name',
            metavar='<first-name>',
            help='First name',
        )
        parser.add_argument(
            '--last-name',
            metavar='<last-name>',
            help='Last name',
        )
        parser.add_argument(
            '--password',
            metavar='<password>',
            help='New password',
        )
        parser.add_argument(
            '--active',
            action='store_true',
            dest='is_active',
            help='Set user as active',
        )
        parser.add_argument(
            '--inactive',
            action='store_true',
            help='Set user as inactive',
        )
        parser.add_argument(
            '--superuser',
            action='store_true',
            dest='is_superuser',
            help='Set user as superuser',
        )
        parser.add_argument(
            '--no-superuser',
            action='store_true',
            help='Remove superuser privileges',
        )
        parser.add_argument(
            '--system-auditor',
            action='store_true',
            dest='is_system_auditor',
            help='Set user as system auditor',
        )
        parser.add_argument(
            '--no-system-auditor',
            action='store_true',
            help='Remove system auditor privileges',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.gateway

        # Find the user
        try:
            user_id = int(parsed_args.user)
        except ValueError:
            # Not an integer, search by username
            users = client.list_users(username=parsed_args.user)
            if users['count'] == 0:
                raise CommandError(f"User '{parsed_args.user}' not found")
            elif users['count'] > 1:
                raise CommandError(f"Multiple users found with username '{parsed_args.user}'")
            user_id = users['results'][0]['id']

        # Build update data
        update_data = {}
        if parsed_args.username:
            update_data['username'] = parsed_args.username
        if parsed_args.email is not None:
            update_data['email'] = parsed_args.email
        if parsed_args.first_name is not None:
            update_data['first_name'] = parsed_args.first_name
        if parsed_args.last_name is not None:
            update_data['last_name'] = parsed_args.last_name
        if parsed_args.password:
            update_data['password'] = parsed_args.password

        # Handle boolean flags
        if parsed_args.is_active:
            update_data['is_active'] = True
        elif parsed_args.inactive:
            update_data['is_active'] = False

        if parsed_args.is_superuser:
            update_data['is_superuser'] = True
        elif parsed_args.no_superuser:
            update_data['is_superuser'] = False

        if parsed_args.is_system_auditor:
            update_data['is_system_auditor'] = True
        elif parsed_args.no_system_auditor:
            update_data['is_system_auditor'] = False

        if not update_data:
            raise CommandError("No properties specified to update")

        # Update the user
        user = client.update_user(user_id, update_data)

        display_columns = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'is_superuser', 'modified']

        return (
            display_columns,
            get_dict_properties(user, display_columns)
        )
