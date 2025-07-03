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

"""Client manager for AAP clients"""

from aapclient.common.aapconfig import AAPConfig


class ClientManager:
    """Manages AAP client instances"""

    def __init__(self, config: AAPConfig):
        """Initialize client manager with configuration"""
        self.config = config
        self._controller = None
        self._eda = None
        self._galaxy = None
        self._gateway = None

    @property
    def controller(self):
        """Get Controller API client"""
        if self._controller is None:
            from aapclient.controller.client import Client
            self._controller = Client(self.config)
        return self._controller

    @property
    def eda(self):
        """Get EDA API client"""
        if self._eda is None:
            from aapclient.eda.client import Client
            self._eda = Client(self.config)
        return self._eda

    @property
    def galaxy(self):
        """Get Galaxy API client"""
        if self._galaxy is None:
            from aapclient.galaxy.client import Client
            self._galaxy = Client(self.config)
        return self._galaxy

    @property
    def gateway(self):
        """Get Gateway API client"""
        if self._gateway is None:
            from aapclient.gateway.client import Client
            self._gateway = Client(self.config)
        return self._gateway
