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

"""AAP Command-line interface"""

import sys
from importlib.metadata import version, PackageNotFoundError

from cliff.app import App
from cliff.commandmanager import CommandManager

from aapclient.common.clientmanager import ClientManager
from aapclient.common.aapconfig import AAPConfig


class AAPShell(App):
    """AAP CLI application"""

    def __init__(self):
        # Load commands from entry points
        command_manager = CommandManager('aap.controller.v2')
        
        super().__init__(
            description='AAP (Ansible Automation Platform) command-line client',
            version=self._get_version(),
            command_manager=command_manager,
            deferred_help=True,
        )

        # Initialize client manager
        self.client_manager = None

    def _get_version(self):
        """Get package version"""
        try:
            return version('python-aapclient')
        except PackageNotFoundError:
            return '0.0.0-dev'

    def build_option_parser(self, description, version):
        """Build option parser with AAP-specific options"""
        parser = super().build_option_parser(description, version)
        
        # AAP connection options
        parser.add_argument(
            '--aap-host',
            metavar='<aap-host>',
            help='AAP hostname (default: env[AAP_HOST])',
        )
        parser.add_argument(
            '--aap-username',
            metavar='<username>',
            help='AAP username (default: env[AAP_USERNAME])',
        )
        parser.add_argument(
            '--aap-password',
            metavar='<password>',
            help='AAP password (default: env[AAP_PASSWORD])',
        )
        parser.add_argument(
            '--aap-token',
            metavar='<token>',
            help='AAP API token (default: env[AAP_TOKEN])',
        )
        parser.add_argument(
            '--aap-verify-ssl',
            action='store_true',
            default=None,
            help='Verify SSL certificates (default: env[AAP_VERIFY_SSL])',
        )
        parser.add_argument(
            '--aap-ca-bundle',
            metavar='<ca-bundle>',
            help='CA bundle file (default: env[AAP_CA_BUNDLE])',
        )
        
        return parser

    def prepare_to_run_command(self, cmd):
        """Prepare to run a command, including authentication"""
        
        # Initialize configuration
        config = AAPConfig()
        
        # Override config with command line options
        if self.options.aap_host:
            config.host = self.options.aap_host
        if self.options.aap_username:
            config.username = self.options.aap_username
        if self.options.aap_password:
            config.password = self.options.aap_password
        if self.options.aap_token:
            config.token = self.options.aap_token
        if self.options.aap_verify_ssl is not None:
            config.verify_ssl = self.options.aap_verify_ssl
        if self.options.aap_ca_bundle:
            config.ca_bundle = self.options.aap_ca_bundle
        
        # Validate configuration
        config.validate()
        
        # Initialize client manager
        self.client_manager = ClientManager(config)
        
        return super().prepare_to_run_command(cmd)

    def clean_up(self, cmd, result, err):
        """Clean up after command execution"""
        self.LOG.debug('Clean up %s', cmd.__class__.__name__)
        if err:
            self.LOG.debug('Error during command: %s', err)
        
        return super().clean_up(cmd, result, err)


def main(argv=None):
    """Main entry point for the AAP CLI"""
    if argv is None:
        argv = sys.argv[1:]
    
    shell = AAPShell()
    return shell.run(argv)


if __name__ == '__main__':
    sys.exit(main()) 