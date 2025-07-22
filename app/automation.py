import os
import platform
import logging
import requests
from typing import Dict, Any, Optional, Tuple, List
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
            
    def add_torrent(self, urls: str, category: Optional[str] = None, 
                   save_path: Optional[str] = None, sequential_download: bool = False) -> Tuple[bool, str, Optional[str]]:
        """Add torrent(s) to qBittorrent
        
        Args:
            urls: Magnet link(s) or torrent file URL(s), separated by newlines
            category: Category to assign to the torrent
            save_path: Download location (uses default if not specified)
            sequential_download: Enable sequential download for streaming
            
        Returns:
            Tuple of (success, message, info_hash)
        """
        if not self._sid and not self.login():
            return False, "Failed to authenticate with qBittorrent", None
            
        try:
            data = {
                'urls': urls,
                'autoTMM': 'false' if save_path else 'true'  # Auto Torrent Management
            }
            
            if category:
                data['category'] = category
            if save_path:
                data['savepath'] = save_path
            if sequential_download:
                data['sequentialDownload'] = 'true'
                
            response = self.session.post(
                self._get_api_url('torrents/add'),
                data=data
            )
            
            if response.status_code == 200:
                # Extract hash from magnet link if it's a magnet
                info_hash = None
                if urls.startswith('magnet:'):
                    import re
                    hash_match = re.search(r'btih:([a-fA-F0-9]{40})', urls)
                    if hash_match:
                        info_hash = hash_match.group(1).lower()
                
                if response.text == 'Ok.':
                    return True, "Torrent added successfully", info_hash
                else:
                    return True, f"Torrent added (response: {response.text})", info_hash
            elif response.status_code == 415:
                return False, "Torrent file is not valid", None
            else:
                return False, f"Failed to add torrent: HTTP {response.status_code}", None
                
        except Exception as e:
            logger.error(f"Failed to add torrent: {e}")
            return False, f"Error adding torrent: {str(e)}", None
            
    def get_torrents(self, category: Optional[str] = None, 
                     hashes: Optional[List[str]] = None) -> Tuple[bool, Any]:
        """Get list of torrents with optional filters
        
        Args:
            category: Filter by category
            hashes: Filter by torrent hashes
            
        Returns:
            Tuple of (success, torrents_list/error_message)
        """
        try:
            if not self._sid and not self.login():
                return False, "Not authenticated"
                
            params = {}
            if category:
                params['category'] = category
            if hashes:
                params['hashes'] = '|'.join(hashes)
                
            response = self.session.get(
                self._get_api_url('torrents/info'),
                params=params
            )
            
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f"Failed to get torrents: {response.status_code}"
                
        except Exception as e:
            logger.error(f"Failed to get torrents: {e}")
            return False, f"Error getting torrents: {str(e)}"
            
    def get_torrent_progress(self, info_hash: str) -> Dict[str, Any]:
        """Get detailed progress information for a specific torrent
        
        Args:
            info_hash: The torrent's info hash
            
        Returns:
            Dict with torrent progress information or empty dict on error
        """
        success, torrents = self.get_torrents(hashes=[info_hash])
        
        if success and torrents:
            torrent = torrents[0] if torrents else {}
            return {
                'hash': torrent.get('hash', ''),
                'name': torrent.get('name', ''),
                'progress': torrent.get('progress', 0) * 100,  # Convert to percentage
                'state': torrent.get('state', 'unknown'),
                'eta': torrent.get('eta', 8640000),  # Default to 100 days if unknown
                'dlspeed': torrent.get('dlspeed', 0),
                'size': torrent.get('size', 0),
                'downloaded': torrent.get('downloaded', 0),
                'uploaded': torrent.get('uploaded', 0),
                'num_seeds': torrent.get('num_seeds', 0),
                'num_leechs': torrent.get('num_leechs', 0),
                'category': torrent.get('category', ''),
                'save_path': torrent.get('save_path', ''),
                'completed': torrent.get('progress', 0) >= 1.0
            }
        
        return {}


class JackettClient:
    """Jackett API client for torrent searching"""
    
    def __init__(self, url: str, api_key: Optional[str] = None):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
    def test_connection(self) -> Tuple[bool, str]:
        """Test connection to Jackett"""
        try:
            # Try to access the Jackett UI or API endpoint
            response = requests.get(self.url, timeout=5)
            
            if response.status_code == 200:
                # Check if it's actually Jackett by looking for specific content
                if 'Jackett' in response.text or 'jackett' in response.text.lower():
                    # If we have an API key, test the API endpoint
                    if self.api_key:
                        api_test = self._test_api_connection()
                        if not api_test[0]:
                            return True, f"Connected to Jackett (Web UI accessible, API: {api_test[1]})"
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
            
    def _test_api_connection(self) -> Tuple[bool, str]:
        """Test API connection with API key"""
        if not self.api_key:
            return False, "No API key configured"
            
        try:
            # Test the indexers endpoint
            api_url = f"{self.url}/api/v2.0/indexers/all/results/torznab"
            params = {
                'apikey': self.api_key,
                't': 'caps'
            }
            response = self.session.get(api_url, params=params, timeout=5)
            
            if response.status_code == 200:
                return True, "API key valid"
            elif response.status_code == 401:
                return False, "Invalid API key"
            else:
                return False, f"API test failed: {response.status_code}"
                
        except Exception as e:
            return False, f"API test error: {str(e)}"
            
    def build_search_url(self, query: str) -> str:
        """Build a search URL for Jackett Web UI"""
        # Remove any trailing /UI/Dashboard or similar paths
        base_url = self.url
        parsed = urlparse(base_url)
        if parsed.path.endswith('/UI/Dashboard'):
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
        # Build the search URL
        search_path = f"/UI/Dashboard#search={query}&tracker=&category="
        return urljoin(base_url + '/', search_path.lstrip('/'))
        
    def search_api(self, query: str, category: Optional[str] = None, 
                   limit: int = 50) -> Tuple[bool, Any]:
        """Search using Jackett API
        
        Args:
            query: Search query
            category: Category filter (e.g., '1000' for Console)
            limit: Maximum number of results
            
        Returns:
            Tuple of (success, results/error_message)
        """
        if not self.api_key:
            return False, "API key not configured"
            
        try:
            api_url = f"{self.url}/api/v2.0/indexers/all/results/torznab/api"
            params = {
                'apikey': self.api_key,
                't': 'search',
                'q': query,
                'limit': limit
            }
            
            if category:
                params['cat'] = category
                
            response = self.session.get(api_url, params=params, timeout=60)
            
            if response.status_code == 200:
                # Parse the XML response
                results = self._parse_torznab_response(response.text)
                return True, results
            elif response.status_code == 401:
                return False, "Invalid API key"
            else:
                return False, f"Search failed: {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "Search timeout - request took too long"
        except Exception as e:
            logger.error(f"Jackett search error: {e}")
            return False, f"Search error: {str(e)}"
            
    def _parse_torznab_response(self, xml_content: str) -> list:
        """Parse Torznab XML response into list of results"""
        results = []
        
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_content)
            
            # Find all items in the RSS feed
            for item in root.findall('.//item'):
                result = {
                    'title': item.findtext('title', ''),
                    'link': item.findtext('link', ''),
                    'size': 0,
                    'seeders': 0,
                    'leechers': 0,
                    'publish_date': item.findtext('pubDate', ''),
                    'category': item.findtext('category', ''),
                    'indexer': '',
                    'magnet_link': '',
                    'info_hash': ''
                }
                
                # Parse torznab attributes
                for attr in item.findall('.//torznab:attr', {'torznab': 'http://torznab.com/schemas/2015/feed'}):
                    name = attr.get('name')
                    value = attr.get('value')
                    
                    if name == 'size':
                        result['size'] = int(value) if value else 0
                    elif name == 'seeders':
                        result['seeders'] = int(value) if value else 0
                    elif name == 'peers':
                        result['leechers'] = int(value) if value else 0
                    elif name == 'indexer':
                        result['indexer'] = value
                    elif name == 'magneturl':
                        result['magnet_link'] = value
                    elif name == 'infohash':
                        result['info_hash'] = value
                        
                # Try to get magnet from enclosure if not in attributes
                if not result['magnet_link']:
                    enclosure = item.find('enclosure')
                    if enclosure and enclosure.get('url', '').startswith('magnet:'):
                        result['magnet_link'] = enclosure.get('url')
                        
                results.append(result)
                
        except Exception as e:
            logger.error(f"Error parsing Torznab response: {e}")
            
        return results


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