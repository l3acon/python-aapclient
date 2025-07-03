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

from aapclient.common.utils import CommandError, get_dict_properties


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
            nargs="+",
            help='Project(s) to delete (name or ID)',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        errors = 0
        for project in parsed_args.projects:
            try:
                # Try to get by ID first, then by name
                try:
                    project_id = int(project)
                    project_obj = client.get_project(project_id)
                except ValueError:
                    # Not an integer, search by name
                    projects = client.list_projects(name=project)
                    if projects['count'] == 0:
                        raise CommandError(f"Project '{project}' not found")
                    elif projects['count'] > 1:
                        raise CommandError(f"Multiple projects found with name '{project}'")
                    project_obj = projects['results'][0]
                    project_id = project_obj['id']
                
                client.delete_project(project_id)
                print(f"Project '{project}' deleted successfully")
            except Exception as e:
                errors += 1
                LOG.error(f"Failed to delete project '{project}': {e}")

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
            help='Project to display (name or ID)',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Try to get by ID first, then by name
        try:
            project_id = int(parsed_args.project)
            project = client.get_project(project_id)
        except ValueError:
            # Not an integer, search by name
            projects = client.list_projects(name=parsed_args.project)
            if projects['count'] == 0:
                raise CommandError(f"Project '{parsed_args.project}' not found")
            elif projects['count'] > 1:
                raise CommandError(f"Multiple projects found with name '{parsed_args.project}'")
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
        print(f"Project '{parsed_args.project}' updated successfully") 