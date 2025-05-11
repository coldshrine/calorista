import hashlib
import time
import urllib.parse
import requests
import base64
import hmac
from typing import Dict, Any, Optional
from requests.exceptions import RequestException

from .constants import CONSUMER_KEY, CONSUMER_SECRET
from .models import UserProfile
from .auth import FatSecretAuth

class FatSecretAPI:
    def __init__(self, auth: FatSecretAuth, max_retries: int = 2):
        """
        Initialize the API client with authentication handler.
        
        Args:
            auth: FatSecretAuth instance for token management
            max_retries: Number of retries for failed requests (default: 2)
        """
        self.auth = auth
        self.base_url = "https://platform.fatsecret.com/rest/server.api"
        self.max_retries = max_retries
        self._refresh_tokens()

    def _refresh_tokens(self):
        """Refresh or obtain new OAuth tokens"""
        tokens = self.auth.token_manager.get_tokens()
        if not tokens or 'oauth_token' not in tokens:
            tokens = self.auth.authenticate()
        self.access_token = tokens['oauth_token']
        self.access_token_secret = tokens['oauth_token_secret']

    def _generate_signature(self, params: Dict) -> str:
        """Generate OAuth 1.0 signature for the request"""
        param_string = "&".join(
            f"{k}={urllib.parse.quote(str(v), safe='')}"
            for k, v in sorted(params.items())
        )
        
        base_string = "&".join([
            "GET",
            urllib.parse.quote(self.base_url, safe=""),
            urllib.parse.quote(param_string, safe=""),
        ])
        
        signing_key = f"{CONSUMER_SECRET}&{self.access_token_secret}"
        signature = hmac.new(
            signing_key.encode(),
            base_string.encode(),
            hashlib.sha1,
        ).digest()
        return base64.b64encode(signature).decode()

    def _make_request(self, method: str, params: Optional[Dict] = None, attempt: int = 0) -> Dict:
        """
        Make authenticated API request with automatic token refresh on failure
        
        Args:
            method: API method name (e.g., 'profile.get')
            params: Additional request parameters
            attempt: Current retry attempt (used internally)
            
        Returns:
            Parsed JSON response
            
        Raises:
            Exception: When request fails after max retries
        """
        try:
            request_params = {
                "method": method,
                "format": "json",
                "oauth_consumer_key": CONSUMER_KEY,
                "oauth_token": self.access_token,
                "oauth_timestamp": str(int(time.time())),
                "oauth_nonce": hashlib.md5(str(time.time()).encode()).hexdigest(),
                "oauth_signature_method": "HMAC-SHA1",
                "oauth_version": "1.0",
            }
            
            if params:
                request_params.update(params)
            
            request_params["oauth_signature"] = self._generate_signature(request_params)
            
            response = requests.get(
                self.base_url,
                params=request_params,
                timeout=10  # Add timeout to prevent hanging
            )
            
            if response.status_code == 200:
                return response.json()
                
            # Handle specific error cases
            error_msg = response.text.lower()
            if 'token' in error_msg and attempt < self.max_retries:
                self._refresh_tokens()
                return self._make_request(method, params, attempt + 1)
                
            raise Exception(f"API request failed ({response.status_code}): {response.text}")
            
        except RequestException as e:
            if attempt < self.max_retries:
                return self._make_request(method, params, attempt + 1)
            raise Exception(f"Network error: {str(e)}")

    def get_user_profile(self) -> UserProfile:
        """Get the authenticated user's profile data"""
        response = self._make_request("profile.get")
        return UserProfile.from_dict(response['profile'])

    def get_food_entries(self, date: str) -> Dict:
        """
        Get food entries for a specific date
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            Dictionary containing food entries data
        """
        return self._make_request("food_entries.get", {"date": date})

    def get_exercises(self, date: Optional[str] = None) -> Dict:
        """
        Get exercises data
        
        Args:
            date: Optional date filter in YYYY-MM-DD format
            
        Returns:
            Dictionary containing exercises data
        """
        params = {"date": date} if date else None
        return self._make_request("exercises.get", params)

    def search_foods(self, query: str, max_results: int = 10) -> Dict:
        """
        Search for foods
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary containing search results
        """
        return self._make_request(
            "foods.search",
            {"search_expression": query, "max_results": str(max_results)}
        )

    def get_food(self, food_id: str) -> Dict:
        """
        Get detailed information about a specific food
        
        Args:
            food_id: FatSecret food ID
            
        Returns:
            Dictionary containing food details
        """
        return self._make_request("food.get", {"food_id": food_id})