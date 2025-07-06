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

"""Resource list command for AAP CLI"""

import logging

from cliff.lister import Lister

from aapclient.common.utils import CommandError


LOG = logging.getLogger(__name__)


class ResourceList(Lister):
    """List resource counts for each resource type"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        return parser

    def take_action(self, parsed_args):
        controller_client = self.app.client_manager.controller
        gateway_client = self.app.client_manager.gateway

        # Resource types and their API clients in the specified order
        resource_configs = [
            ('Templates', controller_client, 'list_job_templates'),
            ('Projects', controller_client, 'list_projects'),
            ('Inventories', controller_client, 'list_inventories'),
            ('Hosts', controller_client, 'list_hosts'),
            ('Credentials', controller_client, 'list_credentials'),
            ('Organizations', gateway_client, 'list_organizations'),
            ('Teams', gateway_client, 'list_teams'),
            ('Users', gateway_client, 'list_users'),
        ]

        # Collect counts for each resource type
        resource_counts = []

        for resource_name, client, method_name in resource_configs:
            try:
                # Get the list method from the client
                list_method = getattr(client, method_name)

                # Call the method with page_size=1 to minimize data transfer
                # We only need the count, not the actual results
                response = list_method(page_size=1)

                # Extract count from response
                count = response.get('count', 0)

                resource_counts.append([resource_name, count])

            except Exception as e:
                LOG.warning(f"Failed to get count for {resource_name}: {e}")
                resource_counts.append([resource_name, 'Error'])

        # Define columns for output
        columns = ('Resource Type', 'Count')

        return (columns, resource_counts)
