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

"""Whoami command - show current user information"""

import logging

from cliff.show import ShowOne

from aapclient.common.utils import get_dict_properties

LOG = logging.getLogger(__name__)


class Whoami(ShowOne):
    """Show current user information"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        # No additional arguments needed for whoami
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.gateway

        # Get current user information
        me_response = client.me()
        
        # Extract the user data from the results array
        if 'results' in me_response and me_response['results']:
            me = me_response['results'][0]
        else:
            raise RuntimeError("Unable to retrieve current user information")
        
        # Extract organization information if available
        orgs = []
        if 'summary_fields' in me and 'organizations' in me['summary_fields']:
            orgs = [org['name'] for org in me['summary_fields']['organizations']]
        
        # Add organization names to the data for display
        me['organizations'] = ', '.join(orgs) if orgs else 'None'

        # Display columns for current user info
        display_columns = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'is_superuser', 'is_platform_auditor', 'organizations',
            'last_login', 'created'
        ]
        
        return (
            display_columns,
            get_dict_properties(me, display_columns)
        ) 