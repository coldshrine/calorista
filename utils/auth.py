import base64
import hashlib
import hmac
import time
import urllib.parse
from flask import Flask, request
import threading
import requests
from typing import Dict, Optional
from pathlib import Path
import json
import os

from .constants import (
    CALLBACK_URL,
    CONSUMER_KEY,
    CONSUMER_SECRET,
    OAUTH_SIGNATURE_METHOD,
    OAUTH_VERSION,
)

class TokenManager:
    def __init__(self, token_file: str = "fatsecret_tokens.json"):
        self.token_file = Path(token_file)
        self.tokens = self._load_tokens()

    def _load_tokens(self) -> Dict:
        if self.token_file.exists():
            with open(self.token_file, 'r') as f:
                return json.load(f)
        return {}

    def save_tokens(self, tokens: Dict):
        with open(self.token_file, 'w') as f:
            json.dump(tokens, f)
        self.tokens = tokens

    def get_tokens(self) -> Optional[Dict]:
        return self.tokens if self.tokens else None

    def clear_tokens(self):
        if self.token_file.exists():
            os.remove(self.token_file)
        self.tokens = {}

class FatSecretAuth:
    def __init__(self, token_file: str = "fatsecret_tokens.json"):
        self.verifier = None
        self.oauth_token = None
        self.app = Flask(__name__)
        self.token_manager = TokenManager(token_file)
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route('/callback')
        def callback():
            self.verifier = request.args.get('oauth_verifier')
            self.oauth_token = request.args.get('oauth_token')
            return "Authentication complete. You may close this window."

    def _run_server(self):
        self.app.run(port=8080)

    def _generate_oauth_params(self, extra_params: Optional[Dict] = None) -> Dict:
        params = {
            "oauth_consumer_key": CONSUMER_KEY,
            "oauth_nonce": hashlib.md5(str(time.time()).encode()).hexdigest(),
            "oauth_signature_method": OAUTH_SIGNATURE_METHOD,
            "oauth_timestamp": str(int(time.time())),
            "oauth_version": OAUTH_VERSION,
        }
        if extra_params:
            params.update(extra_params)
        return params

    def _generate_signature(self, url: str, params: Dict, token_secret: str = "") -> str:
        param_string = "&".join(
            f"{k}={urllib.parse.quote(str(v), safe='')}"
            for k, v in sorted(params.items()))
        
        base_string = "&".join([
            "GET",
            urllib.parse.quote(url, safe=""),
            urllib.parse.quote(param_string, safe=""),
        ])
        
        signing_key = f"{CONSUMER_SECRET}&{token_secret}"
        signature = hmac.new(
            signing_key.encode(),
            base_string.encode(),
            hashlib.sha1,
        ).digest()
        return base64.b64encode(signature).decode()

    def get_request_token(self, callback_url: str = CALLBACK_URL) -> Dict:
        """Obtain OAuth request token from FatSecret API."""
        params = self._generate_oauth_params({
            "oauth_callback": callback_url,
        })
        
        url = "https://authentication.fatsecret.com/oauth/request_token"
        params["oauth_signature"] = self._generate_signature(url, params)
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return dict(pair.split('=') for pair in response.text.split('&'))
        raise Exception(f"Failed to get request token: {response.text}")

    def get_verifier(self, request_token: str) -> str:
        """Start a local server to capture the OAuth verifier"""
        server = threading.Thread(target=self._run_server)
        server.daemon = True
        server.start()
        
        auth_url = (
            "https://authentication.fatsecret.com/oauth/authorize"
            f"?oauth_token={request_token}"
            f"&oauth_callback=http://localhost:8080/callback"
        )
        
        print(f"\nPlease visit this URL to authorize:")
        print(auth_url)
        
        while self.verifier is None:
            time.sleep(1)
        
        return self.verifier

    def get_access_token(self, request_token: str, request_token_secret: str, verifier: str) -> Dict:
        """Exchange verified request token for access token"""
        url = "https://authentication.fatsecret.com/oauth/access_token"
        
        params = self._generate_oauth_params({
            "oauth_token": request_token,
            "oauth_verifier": verifier,
        })

        params["oauth_signature"] = self._generate_signature(url, params, request_token_secret)
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return dict(pair.split('=') for pair in response.text.split('&'))
        raise Exception(f"Access token error: {response.text}")

    def authenticate(self) -> Dict:
        """Complete OAuth 1.0a 3-legged authentication flow"""
        try:
            # Check for existing tokens first
            existing_tokens = self.token_manager.get_tokens()
            if existing_tokens:
                print("Using existing access tokens")
                return existing_tokens

            # Step 1: Get request token
            token_data = self.get_request_token(callback_url="http://localhost:8080/callback")
            
            # Step 2: Get user authorization
            verifier = self.get_verifier(token_data['oauth_token'])
            
            # Step 3: Exchange for access token
            access_data = self.get_access_token(
                token_data['oauth_token'],
                token_data['oauth_token_secret'],
                verifier
            )
            
            # Save tokens for future use
            self.token_manager.save_tokens(access_data)
            
            return access_data
            
        except Exception as e:
            print(f"\nError during OAuth flow: {str(e)}")
            raise

    def logout(self):
        """Clear saved tokens"""
        self.token_manager.clear_tokens()