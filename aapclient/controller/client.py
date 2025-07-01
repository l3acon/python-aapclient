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

"""AAP Controller API Client"""

import logging
import requests
from typing import Any, Dict, List, Optional

from aapclient.common.aapconfig import AAPConfig


LOG = logging.getLogger(__name__)

API_NAME = 'controller'
API_VERSION = '2'
DEFAULT_API_VERSION = '2'


class ControllerClientError(Exception):
    """Exception raised by Controller client"""
    pass


class Client:
    """AAP Controller API Client"""
    
    def __init__(self, config: AAPConfig):
        self.config = config
        self.session = requests.Session()
        
        # Set up authentication
        auth_headers = config.get_auth_headers()
        if auth_headers:
            self.session.headers.update(auth_headers)
        
        # Set up SSL verification
        ssl_config = config.get_ssl_config()
        self.session.verify = ssl_config['verify']
        
        # Set up base URL - try to detect API version
        self.base_url = self._get_base_url()
    
    def _get_base_url(self) -> str:
        """Get the base URL for the controller API"""
        # Try new AAP 2.5+ structure first
        try:
            resp = self.session.get(f"{self.config.host}/api/")
            if resp.status_code == 200:
                api_info = resp.json()
                if 'apis' in api_info and 'controller' in api_info['apis']:
                    # AAP 2.5+ structure
                    controller_path = api_info['apis']['controller']
                    # Get versioned path
                    resp = self.session.get(f"{self.config.host}{controller_path}")
                    if resp.status_code == 200:
                        version_info = resp.json()
                        if 'current_version' in version_info:
                            return f"{self.config.host}{version_info['current_version']}"
                        elif 'available_versions' in version_info:
                            # Use the highest version available
                            versions = version_info['available_versions']
                            if 'v2' in versions:
                                return f"{self.config.host}{versions['v2']}"
        except Exception as e:
            LOG.debug(f"Failed to detect AAP 2.5+ structure: {e}")
        
        # Fall back to AAP 2.4 structure
        return f"{self.config.host}/api/v2/"
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a request to the AAP API"""
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
            return resp.json()
        except requests.exceptions.RequestException as e:
            raise ControllerClientError(f"API request failed: {e}")
    
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
        try:
            self._make_request('DELETE', endpoint)
        except ControllerClientError as e:
            # Some DELETE operations might return empty responses
            if "JSONDecodeError" in str(e):
                pass  # This is expected for successful DELETE operations
            else:
                raise
    
    def ping(self) -> Dict[str, Any]:
        """Ping the API to check connectivity"""
        return self.get('ping/')
    
    # Projects
    def list_projects(self, **params) -> Dict[str, Any]:
        """List projects"""
        return self.get('projects/', params=params)
    
    def get_project(self, project_id: int) -> Dict[str, Any]:
        """Get a specific project"""
        return self.get(f'projects/{project_id}/')
    
    def create_project(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new project"""
        return self.post('projects/', data=data)
    
    def update_project(self, project_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a project"""
        return self.patch(f'projects/{project_id}/', data=data)
    
    def delete_project(self, project_id: int) -> None:
        """Delete a project"""
        self.delete(f'projects/{project_id}/')
    
    # Organizations
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
    
    # Job Templates
    def list_job_templates(self, **params) -> Dict[str, Any]:
        """List job templates"""
        return self.get('job_templates/', params=params)
    
    def get_job_template(self, template_id: int) -> Dict[str, Any]:
        """Get a specific job template"""
        return self.get(f'job_templates/{template_id}/')
    
    def create_job_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new job template"""
        return self.post('job_templates/', data=data)
    
    def update_job_template(self, template_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a job template"""
        return self.patch(f'job_templates/{template_id}/', data=data)
    
    def delete_job_template(self, template_id: int) -> None:
        """Delete a job template"""
        self.delete(f'job_templates/{template_id}/')
    
    def launch_job_template(self, template_id: int, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Launch a job template"""
        return self.post(f'job_templates/{template_id}/launch/', data=data or {})
    
    # Jobs
    def list_jobs(self, **params) -> Dict[str, Any]:
        """List jobs"""
        return self.get('jobs/', params=params)
    
    def get_job(self, job_id: int) -> Dict[str, Any]:
        """Get a specific job"""
        return self.get(f'jobs/{job_id}/')
    
    def cancel_job(self, job_id: int) -> Dict[str, Any]:
        """Cancel a job"""
        return self.post(f'jobs/{job_id}/cancel/')
    
    def get_job_output(self, job_id: int) -> Dict[str, Any]:
        """Get job output"""
        return self.get(f'jobs/{job_id}/stdout/')


def make_client(instance):
    """Factory function for creating client instances"""
    # This will be called by the plugin system
    return Client 