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

"""AAP Gateway API client"""

import logging
from typing import Dict, Any, Optional

import requests

from aapclient.common.aapconfig import AAPConfig


LOG = logging.getLogger(__name__)


class GatewayClientError(Exception):
    """Gateway API client error"""
    pass


class Client:
    """AAP Gateway API client for AAP 2.5+"""
    
    def __init__(self, config: AAPConfig):
        """Initialize Gateway API client"""
        self.config = config
        self.session = requests.Session()
        
        # Set up authentication
        if config.token:
            self.session.headers.update({
                'Authorization': f'Bearer {config.token}'
            })
        elif config.username and config.password:
            self.session.auth = (config.username, config.password)
        
        # Set up SSL verification
        if not config.verify_ssl:
            self.session.verify = False
        elif config.ca_bundle:
            self.session.verify = config.ca_bundle
            
        self.base_url = self._get_base_url()
        
    def _get_base_url(self) -> str:
        """Get the Gateway API base URL"""
        # For AAP 2.5+, gateway API is typically at /api/gateway/v1/
        # Try to detect the structure
        try:
            # Check if we have AAP 2.5+ structure
            resp = self.session.get(
                f"{self.config.host}/api/gateway/v1/",
                timeout=self.config.timeout
            )
            if resp.status_code == 200:
                return f"{self.config.host}/api/gateway/v1/"
        except Exception as e:
            LOG.debug(f"Failed to detect AAP 2.5+ gateway structure: {e}")
        
        # Fallback - assume gateway endpoint exists
        return f"{self.config.host}/api/gateway/v1/"
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a request to the Gateway API"""
        url = f"{self.base_url}{endpoint.lstrip('/')}"
        
        try:
            resp = self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                json=data,
                timeout=self.config.timeout
            )
            resp.raise_for_status()
            
            # DELETE requests often return empty responses
            if method.upper() == 'DELETE':
                if resp.text.strip():
                    try:
                        return resp.json()
                    except ValueError:
                        # If we can't parse JSON, just return an empty dict
                        return {}
                else:
                    # Empty response is expected for DELETE
                    return {}
            else:
                return resp.json()
        except requests.exceptions.RequestException as e:
            raise GatewayClientError(f"Gateway API request failed: {e}")
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET request"""
        return self._make_request('GET', endpoint, params=params)
    
    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """POST request"""
        return self._make_request('POST', endpoint, data=data)
    
    def patch(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """PATCH request"""
        return self._make_request('PATCH', endpoint, data=data)
    
    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """PUT request"""
        return self._make_request('PUT', endpoint, data=data)
    
    def delete(self, endpoint: str) -> None:
        """DELETE request"""
        self._make_request('DELETE', endpoint)

    # Users (managed at Gateway level in AAP 2.5+)
    def list_users(self, **params) -> Dict[str, Any]:
        """List users"""
        return self.get('users/', params=params)
    
    def get_user(self, user_id: int) -> Dict[str, Any]:
        """Get a specific user"""
        return self.get(f'users/{user_id}/')
    
    def create_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user"""
        return self.post('users/', data=data)
    
    def update_user(self, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a user"""
        return self.patch(f'users/{user_id}/', data=data)
    
    def delete_user(self, user_id: int) -> None:
        """Delete a user"""
        self.delete(f'users/{user_id}/')

    # Organizations (also available at Gateway level)
    def list_organizations(self, **params) -> Dict[str, Any]:
        """List organizations"""
        return self.get('organizations/', params=params)
    
    def get_organization(self, org_id: int) -> Dict[str, Any]:
        """Get a specific organization"""
        return self.get(f'organizations/{org_id}/')
    
    def create_organization(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new organization"""
        return self.post('organizations/', data=data)
    
    def update_organization(self, org_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an organization"""
        return self.patch(f'organizations/{org_id}/', data=data)
    
    def delete_organization(self, org_id: int) -> None:
        """Delete an organization"""
        self.delete(f'organizations/{org_id}/')

    # Teams (also available at Gateway level)
    def list_teams(self, **params) -> Dict[str, Any]:
        """List teams"""
        return self.get('teams/', params=params)
    
    def get_team(self, team_id: int) -> Dict[str, Any]:
        """Get a specific team"""
        return self.get(f'teams/{team_id}/')
    
    def create_team(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new team"""
        return self.post('teams/', data=data)
    
    def update_team(self, team_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a team"""
        return self.patch(f'teams/{team_id}/', data=data)
    
    def delete_team(self, team_id: int) -> None:
        """Delete a team"""
        self.delete(f'teams/{team_id}/')


def make_client(instance):
    """Factory function for creating client instances"""
    # This will be called by the plugin system
    return Client 