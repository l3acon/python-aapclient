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

"""Configuration management for AAP client"""

import os
from typing import Any, Dict, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    # python-dotenv not available, skip loading .env file
    pass


class AAPConfig:
    """Configuration for AAP API client"""

    def __init__(self):
        """Initialize configuration from environment variables"""
        self.host: Optional[str] = os.getenv('AAP_HOST')
        self.username: Optional[str] = os.getenv('AAP_USERNAME')
        self.password: Optional[str] = os.getenv('AAP_PASSWORD')
        self.token: Optional[str] = os.getenv('AAP_TOKEN')

        # SSL/TLS configuration
        verify_ssl_env = os.getenv('AAP_VERIFY_SSL', 'true').lower()
        self.verify_ssl: bool = verify_ssl_env in ('true', '1', 'yes', 'on')
        self.ca_bundle: Optional[str] = os.getenv('AAP_CA_BUNDLE')

        # Request timeout
        try:
            self.timeout: int = int(os.getenv('AAP_TIMEOUT', '30'))
        except ValueError:
            self.timeout = 30

    def validate(self) -> None:
        """Validate configuration"""
        if not self.host:
            raise ValueError("AAP host is required. Set AAP_HOST environment variable or use --aap-host")

        # Ensure host is a string and properly formatted
        if not isinstance(self.host, str):
            raise ValueError("AAP host must be a string")

        # Remove any trailing slashes
        self.host = self.host.rstrip('/')

        # Add https:// prefix if not present
        if not self.host.startswith(('http://', 'https://')):
            self.host = f'https://{self.host}'

        # Authentication validation
        if not (self.token or (self.username and self.password)):
            raise ValueError(
                "Authentication required. Provide either:\n"
                "  - AAP_TOKEN environment variable or --aap-token\n"
                "  - AAP_USERNAME and AAP_PASSWORD environment variables or --aap-username/--aap-password"
            )

    def get_auth_headers(self) -> dict:
        """Get authentication headers for API requests"""
        if self.token:
            return {'Authorization': f'Bearer {self.token}'}
        elif self.username and self.password:
            import base64
            credentials = base64.b64encode(f'{self.username}:{self.password}'.encode()).decode()
            return {'Authorization': f'Basic {credentials}'}
        else:
            raise ValueError("No authentication credentials available")

    def get_ssl_config(self) -> dict:
        """Get SSL configuration for requests"""
        if self.ca_bundle:
            return {'verify': self.ca_bundle}
        else:
            return {'verify': self.verify_ssl}

    def __repr__(self):
        return (f"AAPConfig(host='{self.host}', username='{self.username}', "
                f"has_password={bool(self.password)}, has_token={bool(self.token)}, "
                f"verify_ssl={self.verify_ssl}, ca_bundle='{self.ca_bundle}')")


