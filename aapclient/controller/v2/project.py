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

"""AAP Controller v2 Project action implementations"""

import logging

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common.utils import CommandError, get_dict_properties, format_name
from aapclient.controller.client import ControllerClientError


LOG = logging.getLogger(__name__)


class CreateProject(ShowOne):
    """Create new project"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            metavar='<project-name>',
            help='New project name',
        )
        parser.add_argument(
            '--description',
            metavar='<description>',
            help='Project description',
        )
        parser.add_argument(
            '--organization',
            metavar='<organization>',
            type=int,
            required=True,
            help='Organization ID for the project',
        )
        parser.add_argument(
            '--scm-type',
            metavar='<scm-type>',
            choices=['git', 'hg', 'svn', ''],
            default='git',
            help='Source control type (default: git)',
        )
        parser.add_argument(
            '--scm-url',
            metavar='<scm-url>',
            help='Source control URL',
        )
        parser.add_argument(
            '--scm-branch',
            metavar='<scm-branch>',
            help='Source control branch/tag/commit',
        )
        parser.add_argument(
            '--scm-credential',
            metavar='<credential-id>',
            type=int,
            help='Credential ID for SCM authentication',
        )
        parser.add_argument(
            '--local-path',
            metavar='<path>',
            help='Local absolute file path',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        data = {
            'name': parsed_args.name,
            'organization': parsed_args.organization,
        }

        if parsed_args.description:
            data['description'] = parsed_args.description
        if parsed_args.scm_type:
            data['scm_type'] = parsed_args.scm_type
        if parsed_args.scm_url:
            data['scm_url'] = parsed_args.scm_url
        if parsed_args.scm_branch:
            data['scm_branch'] = parsed_args.scm_branch
        if parsed_args.scm_credential:
            data['credential'] = parsed_args.scm_credential
        if parsed_args.local_path:
            data['local_path'] = parsed_args.local_path

        project = client.create_project(data)

        display_columns = [
            'id', 'name', 'description', 'organization', 'scm_type',
            'scm_url', 'scm_branch', 'status', 'created', 'modified'
        ]

        return (
            display_columns,
            get_dict_properties(project, display_columns)
        )


class DeleteProject(Command):
    """Delete project(s)"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'projects',
            metavar='<project>',
            nargs='*',
            help='Project(s) to delete (name or ID)',
        )

        # Create mutually exclusive group for --id and --name
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='Project ID to delete',
        )
        group.add_argument(
            '--name',
            metavar='<name>',
            help='Project name to delete',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Validate arguments
        if not any([parsed_args.projects, parsed_args.id, parsed_args.name]):
            raise CommandError("Must specify project(s) to delete")

        # Check for redundant --name with positional argument
        if parsed_args.name and parsed_args.projects:
            raise CommandError("Cannot use positional arguments with --name (redundant)")

        # Check for --id with multiple positional arguments
        if parsed_args.id and len(parsed_args.projects) > 1:
            raise CommandError("Cannot use --id with multiple positional arguments")

        # Handle single project deletion via flags
        if parsed_args.id or parsed_args.name:
            if parsed_args.id and parsed_args.projects:
                # ID flag with one positional argument - search by ID and validate name matches
                project_name = parsed_args.projects[0]
                try:
                    project_obj = client.get_project(parsed_args.id)
                except ControllerClientError:
                    raise CommandError(f"Project with ID {parsed_args.id} not found")

                # Validate that the project found has the expected name
                if project_obj['name'] != project_name:
                    raise CommandError(
                        f"ID {parsed_args.id} and name '{project_name}' refer to different projects: "
                        f"ID {parsed_args.id} is '{project_obj['name']}', not '{project_name}'"
                    )

            elif parsed_args.id:
                # Explicit ID lookup only
                try:
                    project_obj = client.get_project(parsed_args.id)
                except ControllerClientError:
                    raise CommandError(f"Project with ID {parsed_args.id} not found")

            else:
                # --name flag only
                projects = client.list_projects(name=parsed_args.name)
                if projects['count'] == 0:
                    raise CommandError(f"Project with name '{parsed_args.name}' not found")
                elif projects['count'] > 1:
                    raise CommandError(f"Multiple projects found with name '{parsed_args.name}'")
                project_obj = projects['results'][0]

            # Delete the single project
            project_id = project_obj['id']
            project_name = project_obj['name']

            try:
                client.delete_project(project_id)
                print(f"Project {format_name(project_name)} (ID: {project_id}) deleted successfully")
            except Exception as e:
                raise CommandError(f"Failed to delete project {format_name(project_name)}: {e}")
            return

        # Handle multiple projects via positional arguments (default to name lookup)
        errors = 0
        for project in parsed_args.projects:
            try:
                # Default to name lookup for positional arguments
                projects = client.list_projects(name=project)
                if projects['count'] == 0:
                    raise CommandError(f"Project with name '{project}' not found")
                elif projects['count'] > 1:
                    raise CommandError(f"Multiple projects found with name '{project}'")

                project_obj = projects['results'][0]
                project_id = project_obj['id']

                client.delete_project(project_id)
                print(f"Project {format_name(project)} (ID: {project_id}) deleted successfully")
            except Exception as e:
                errors += 1
                LOG.error(f"Failed to delete project {format_name(project)}: {e}")

        if errors > 0:
            total = len(parsed_args.projects)
            msg = f"{errors} of {total} projects failed to delete."
            raise CommandError(msg)


class ListProject(Lister):
    """List projects"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--organization',
            metavar='<organization>',
            type=int,
            help='Filter by organization ID',
        )
        parser.add_argument(
            '--scm-type',
            metavar='<scm-type>',
            choices=['git', 'hg', 'svn', ''],
            help='Filter by SCM type',
        )
        parser.add_argument(
            '--long',
            action='store_true',
            default=False,
            help='List additional fields in output',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        params = {}
        if parsed_args.organization:
            params['organization'] = parsed_args.organization
        if parsed_args.scm_type:
            params['scm_type'] = parsed_args.scm_type

        data = client.list_projects(**params)

        # Process the data to replace organization ID with name
        for project in data['results']:
            if 'summary_fields' in project and 'organization' in project['summary_fields']:
                project['organization_name'] = project['summary_fields']['organization']['name']
            else:
                project['organization_name'] = str(project.get('organization', ''))

        if parsed_args.long:
            columns = ('ID', 'Name', 'Description', 'Organization', 'SCM Type', 'SCM URL', 'Status', 'Created')
            display_columns = ['id', 'name', 'description', 'organization_name', 'scm_type', 'scm_url', 'status', 'created']
        else:
            columns = ('ID', 'Name', 'Description', 'Organization', 'SCM Type', 'Status')
            display_columns = ['id', 'name', 'description', 'organization_name', 'scm_type', 'status']

        return (
            columns,
            (
                get_dict_properties(s, display_columns)
                for s in data['results']
            ),
        )


class ShowProject(ShowOne):
    """Display project details"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'project',
            metavar='<project>',
            nargs='?',
            help='Project to display (name or ID)',
        )

        # Create mutually exclusive group for --id and --name
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='Project ID to display',
        )
        group.add_argument(
            '--name',
            metavar='<name>',
            help='Project name to display',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Validate arguments
        if not any([parsed_args.project, parsed_args.id, parsed_args.name]):
            raise CommandError("Must specify a project (by positional argument, --id, or --name)")

        # Check for redundant --name with positional argument
        if parsed_args.name and parsed_args.project:
            raise CommandError("Cannot use positional argument with --name (redundant)")

        # Determine lookup method
        project = None

        if parsed_args.id and parsed_args.project:
            # ID flag with positional argument - search by ID and validate name matches
            try:
                project = client.get_project(parsed_args.id)
            except ControllerClientError:
                raise CommandError(f"Project with ID {parsed_args.id} not found")

            # Validate that the project found has the expected name
            if project['name'] != parsed_args.project:
                raise CommandError(
                    f"ID {parsed_args.id} and name '{parsed_args.project}' refer to different projects: "
                    f"ID {parsed_args.id} is '{project['name']}', not '{parsed_args.project}'"
                )

        elif parsed_args.id:
            # Explicit ID lookup only
            try:
                project = client.get_project(parsed_args.id)
            except ControllerClientError:
                raise CommandError(f"Project with ID {parsed_args.id} not found")

        else:
            # Name lookup (either explicit --name or positional argument)
            search_name = parsed_args.name or parsed_args.project
            projects = client.list_projects(name=search_name)
            if projects['count'] == 0:
                raise CommandError(f"Project with name '{search_name}' not found")
            elif projects['count'] > 1:
                raise CommandError(f"Multiple projects found with name '{search_name}'")
            project = projects['results'][0]

        # Add organization name from summary_fields
        if 'summary_fields' in project and 'organization' in project['summary_fields']:
            project['organization_name'] = project['summary_fields']['organization']['name']
        else:
            project['organization_name'] = str(project.get('organization', ''))

        display_columns = [
            'id', 'name', 'description', 'organization_name', 'scm_type',
            'scm_url', 'scm_branch', 'scm_credential', 'local_path',
            'status', 'last_job_run', 'last_job_failed', 'next_job_run',
            'created', 'modified'
        ]

        return (
            display_columns,
            get_dict_properties(project, display_columns)
        )


class SetProject(Command):
    """Set project properties"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'project',
            metavar='<project>',
            help='Project to modify (name or ID)',
        )
        parser.add_argument(
            '--name',
            metavar='<name>',
            help='Set project name',
        )
        parser.add_argument(
            '--description',
            metavar='<description>',
            help='Set project description',
        )
        parser.add_argument(
            '--scm-url',
            metavar='<scm-url>',
            help='Set source control URL',
        )
        parser.add_argument(
            '--scm-branch',
            metavar='<scm-branch>',
            help='Set source control branch/tag/commit',
        )
        parser.add_argument(
            '--scm-credential',
            metavar='<credential-id>',
            type=int,
            help='Set credential ID for SCM authentication',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Find the project
        try:
            project_id = int(parsed_args.project)
        except ValueError:
            # Not an integer, search by name
            projects = client.list_projects(name=parsed_args.project)
            if projects['count'] == 0:
                raise CommandError(f"Project '{parsed_args.project}' not found")
            elif projects['count'] > 1:
                raise CommandError(f"Multiple projects found with name '{parsed_args.project}'")
            project_id = projects['results'][0]['id']

        # Build update data
        data = {}
        if parsed_args.name:
            data['name'] = parsed_args.name
        if parsed_args.description:
            data['description'] = parsed_args.description
        if parsed_args.scm_url:
            data['scm_url'] = parsed_args.scm_url
        if parsed_args.scm_branch:
            data['scm_branch'] = parsed_args.scm_branch
        if parsed_args.scm_credential:
            data['credential'] = parsed_args.scm_credential

        if not data:
            raise CommandError("No changes specified")

        client.update_project(project_id, data)
        print(f"Project {format_name(parsed_args.project)} updated successfully")
