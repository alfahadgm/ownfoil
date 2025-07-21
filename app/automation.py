import os
import platform
import logging
import requests
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


class ServiceConnectionError(Exception):
    """Raised when a service connection fails"""
    pass


class QBittorrentClient:
    """qBittorrent Web API client with cross-platform support"""
    
    def __init__(self, url: str, username: str, password: str):
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self._sid = None
        
    def _get_api_url(self, endpoint: str) -> str:
        """Build full API URL"""
        return urljoin(self.url + '/', f'api/v2/{endpoint}')
        
    def login(self) -> bool:
        """Authenticate with qBittorrent"""
        try:
            response = self.session.post(
                self._get_api_url('auth/login'),
                data={'username': self.username, 'password': self.password}
            )
            if response.text == 'Ok.':
                self._sid = response.cookies.get('SID')
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to login to qBittorrent: {e}")
            return False
            
    def test_connection(self) -> Tuple[bool, str]:
        """Test connection and return status with message"""
        try:
            # First try to connect
            response = self.session.get(self._get_api_url('app/version'), timeout=5)
            
            # If we get 403, we need to login
            if response.status_code == 403:
                if not self.login():
                    return False, "Authentication failed - check username/password"
                    
                # Retry after login
                response = self.session.get(self._get_api_url('app/version'))
                
            if response.status_code == 200:
                version = response.text.strip()
                return True, f"Connected to qBittorrent {version}"
            else:
                return False, f"Unexpected response: {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            return False, "Connection failed - check URL and ensure qBittorrent is running"
        except requests.exceptions.Timeout:
            return False, "Connection timeout - qBittorrent is not responding"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
            
    def get_torrents(self, category: Optional[str] = None) -> Optional[list]:
        """Get list of torrents, optionally filtered by category"""
        if not self._sid and not self.login():
            return None
            
        try:
            params = {'category': category} if category else {}
            response = self.session.get(
                self._get_api_url('torrents/info'),
                params=params
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Failed to get torrents: {e}")
            return None
            
    def set_category(self, torrent_hash: str, category: str) -> bool:
        """Set category for a torrent"""
        if not self._sid and not self.login():
            return False
            
        try:
            response = self.session.post(
                self._get_api_url('torrents/setCategory'),
                data={'hashes': torrent_hash, 'category': category}
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to set category: {e}")
            return False


class JackettClient:
    """Jackett API client for torrent searching"""
    
    def __init__(self, url: str, api_key: Optional[str] = None):
        self.url = url.rstrip('/')
        self.api_key = api_key
        
    def test_connection(self) -> Tuple[bool, str]:
        """Test connection to Jackett"""
        try:
            # Try to access the Jackett UI or API endpoint
            response = requests.get(self.url, timeout=5)
            
            if response.status_code == 200:
                # Check if it's actually Jackett by looking for specific content
                if 'Jackett' in response.text or 'jackett' in response.text.lower():
                    return True, "Connected to Jackett"
                else:
                    return False, "URL is accessible but doesn't appear to be Jackett"
            else:
                return False, f"Unexpected response: {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            return False, "Connection failed - check URL and ensure Jackett is running"
        except requests.exceptions.Timeout:
            return False, "Connection timeout - Jackett is not responding"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
            
    def build_search_url(self, query: str) -> str:
        """Build a search URL for Jackett"""
        # Remove any trailing /UI/Dashboard or similar paths
        base_url = self.url
        parsed = urlparse(base_url)
        if parsed.path.endswith('/UI/Dashboard'):
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
        # Build the search URL
        search_path = f"/UI/Dashboard#search={query}&tracker=&category="
        return urljoin(base_url + '/', search_path.lstrip('/'))


class AutomationManager:
    """Manages automation configuration and service connections"""
    
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self.qbit_client = None
        self.jackett_client = None
        
    def get_platform_info(self) -> Dict[str, Any]:
        """Get platform-specific information"""
        return {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'python_version': platform.python_version(),
            'is_docker': os.path.exists('/.dockerenv'),
            'is_windows': platform.system() == 'Windows',
            'is_linux': platform.system() == 'Linux',
            'supports_hardlinks': platform.system() != 'Windows'  # Simplified check
        }
        
    def validate_automation_config(self, config: Dict[str, Any]) -> Tuple[bool, list]:
        """Validate automation configuration"""
        errors = []
        
        # Validate qBittorrent settings
        qbit = config.get('qbittorrent', {})
        if qbit.get('url'):
            # Ensure URL has protocol
            if not qbit['url'].startswith(('http://', 'https://')):
                errors.append("qBittorrent URL must start with http:// or https://")
                
        # Validate Jackett settings
        jackett = config.get('jackett', {})
        if jackett.get('url'):
            # Ensure URL has protocol
            if not jackett['url'].startswith(('http://', 'https://')):
                errors.append("Jackett URL must start with http:// or https://")
                
        # Validate processing settings
        processing = config.get('processing', {})
        if processing.get('use_hardlinks') and platform.system() == 'Windows':
            # Note: Windows does support hardlinks but with limitations
            logger.warning("Hardlinks on Windows have limitations and may require admin privileges")
            
        return len(errors) == 0, errors
        
    def test_qbittorrent_connection(self) -> Tuple[bool, str]:
        """Test qBittorrent connection"""
        qbit_config = self.settings.get('automation', {}).get('qbittorrent', {})
        
        if not qbit_config.get('url'):
            return False, "qBittorrent URL not configured"
            
        try:
            self.qbit_client = QBittorrentClient(
                qbit_config['url'],
                qbit_config.get('username', ''),
                qbit_config.get('password', '')
            )
            return self.qbit_client.test_connection()
        except Exception as e:
            return False, f"Failed to create client: {str(e)}"
            
    def test_jackett_connection(self) -> Tuple[bool, str]:
        """Test Jackett connection"""
        jackett_config = self.settings.get('automation', {}).get('jackett', {})
        
        if not jackett_config.get('url'):
            return False, "Jackett URL not configured"
            
        try:
            self.jackett_client = JackettClient(
                jackett_config['url'],
                jackett_config.get('api_key')
            )
            return self.jackett_client.test_connection()
        except Exception as e:
            return False, f"Failed to create client: {str(e)}"
            
    def get_processing_config(self) -> Dict[str, Any]:
        """Get processing configuration with platform-specific adjustments"""
        config = self.settings.get('automation', {}).get('processing', {}).copy()
        platform_info = self.get_platform_info()
        
        # Adjust for platform limitations
        if platform_info['is_windows'] and config.get('use_hardlinks'):
            # On Windows, we'll try hardlinks but fall back to copy if it fails
            config['hardlink_fallback'] = 'copy'
            
        # Add platform info to config
        config['platform'] = platform_info
        
        return config