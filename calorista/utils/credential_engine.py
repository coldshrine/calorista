#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import subprocess
import time
import urllib.parse
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Dict, Any, Optional
import requests
from dotenv import load_dotenv

class CredentialEngine:
    def __init__(self, token_file: str):
        self.token_file = Path(token_file)
        self.tokens = self._load_tokens()
        self.verifier = None
        self.oauth_token = None

    def _load_tokens(self) -> Dict[str, Any]:
        """Load tokens from JSON file"""
        try:
            if self.token_file.exists():
                if self.token_file.stat().st_size == 0:
                    return {}
                with open(self.token_file) as f:
                    return json.load(f)
            return {}
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to load tokens - {str(e)}")
            return {}

    def save_tokens(self, tokens: Dict[str, Any]) -> None:
        """Save tokens to JSON file"""
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_file, "w") as f:
            json.dump(tokens, f, indent=2)
        self.tokens = tokens
        print(f"Tokens saved to: {self.token_file}")

    def _generate_oauth_params(self, extra_params: Optional[Dict] = None) -> Dict[str, str]:
        """Generate OAuth 1.0 parameters"""
        params = {
            "oauth_consumer_key": os.getenv("CONSUMER_KEY"),
            "oauth_nonce": hashlib.md5(str(time.time()).encode()).hexdigest(),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_version": "1.0",
        }
        if extra_params:
            params.update(extra_params)
        return params

    def _generate_signature(self, url: str, params: Dict[str, str], token_secret: str = "") -> str:
        """Generate OAuth 1.0 signature"""
        param_string = "&".join(
            f"{k}={urllib.parse.quote(str(v), safe='')}"
            for k, v in sorted(params.items()))
        base_string = "&".join([
            "GET",
            urllib.parse.quote(url, safe=""),
            urllib.parse.quote(param_string, safe="")
        ])
        signing_key = f"{os.getenv('CONSUMER_SECRET')}&{token_secret}"
        signature = hmac.new(
            signing_key.encode(),
            base_string.encode(),
            hashlib.sha1
        ).digest()
        return base64.b64encode(signature).decode()

    def get_request_token(self) -> Dict[str, str]:
        """Step 1: Get OAuth request token"""
        params = self._generate_oauth_params({
            "oauth_callback": os.getenv("CALLBACK_URL", "https://oauth.pstmn.io/v1/callback")
        })
        url = "https://authentication.fatsecret.com/oauth/request_token"
        params["oauth_signature"] = self._generate_signature(url, params)

        response = requests.get(url, params=params)
        if response.status_code == 200:
            return dict(pair.split("=") for pair in response.text.split("&"))
        raise Exception(f"Failed to get request token: {response.text}")

    def get_access_token(self, oauth_token: str, oauth_token_secret: str, oauth_verifier: str) -> Dict[str, str]:
        """Step 3: Exchange verifier for access token"""
        url = "https://authentication.fatsecret.com/oauth/access_token"
        params = self._generate_oauth_params({
            "oauth_token": oauth_token,
            "oauth_verifier": oauth_verifier
        })
        params["oauth_signature"] = self._generate_signature(url, params, oauth_token_secret)

        response = requests.get(url, params=params)
        if response.status_code == 200:
            return dict(pair.split("=") for pair in response.text.split("&"))
        raise Exception(f"Failed to get access token: {response.text}")

def get_browser_url() -> Optional[str]:
    """Get current URL from browser on macOS"""
    try:
        script = '''
        tell application "Google Chrome"
            if it is running then
                return URL of active tab of first window
            end if
        end tell
        '''
        chrome_url = subprocess.check_output(["osascript", "-e", script]).decode("utf-8").strip()
        if chrome_url:
            return chrome_url
        
        script = '''
        tell application "Safari"
            return URL of current tab of first window
        end tell
        '''
        return subprocess.check_output(["osascript", "-e", script]).decode("utf-8").strip()
    except Exception as e:
        print(f"Browser URL detection failed: {e}")
        return None

def main():
    # Load environment variables first
    env_path = Path(__file__).parent.parent / ".env"
    print(f"Loading .env from: {env_path}")
    
    if not env_path.exists():
        print(f"Error: .env file not found at {env_path}")
        print("Please create the file with CONSUMER_KEY and CONSUMER_SECRET")
        exit(1)
    
    load_dotenv(env_path, override=True)
    
    # Debug: Print loaded environment variables
    print("Loaded environment variables:")
    print(f"CONSUMER_KEY: {'****' if os.getenv('CONSUMER_KEY') else 'NOT SET'}")
    print(f"CONSUMER_SECRET: {'****' if os.getenv('CONSUMER_SECRET') else 'NOT SET'}")
    print(f"CALLBACK_URL: {os.getenv('CALLBACK_URL')}")
    
    # Verify required environment variables
    if not os.getenv("CONSUMER_KEY") or not os.getenv("CONSUMER_SECRET"):
        print("Error: CONSUMER_KEY and CONSUMER_SECRET must be set in .env file")
        print("Please check your .env file and try again")
        exit(1)
    
    # Configuration
    TOKEN_PATH = Path(__file__).parent.parent.parent / "auth_tokens" / "tokens.json"
    
    # Initialize auth
    auth = CredentialEngine(str(TOKEN_PATH))
    
    try:
        # Step 1: Get request token
        print("\n1. Getting request token...")
        token_data = auth.get_request_token()
        
        # Step 2: Authorize in browser
        print("\n2. Opening browser for authorization...")
        auth_url = f"https://authentication.fatsecret.com/oauth/authorize?oauth_token={token_data['oauth_token']}"
        print(f"Please visit: {auth_url}")
        webbrowser.open(auth_url)
        
        # Step 3: Wait for callback
        print("\n3. Waiting for authorization... (30 second timeout)")
        callback_url = None
        for _ in range(30):
            time.sleep(1)
            current_url = get_browser_url()
            if current_url and "oauth.pstmn.io/v1/callback" in current_url:
                callback_url = current_url
                break
        
        if callback_url:
            # Extract tokens from callback URL
            print("\nCallback URL detected!")
            parsed = urlparse(callback_url)
            params = parse_qs(parsed.query)
            access_data = auth.get_access_token(
                params['oauth_token'][0],
                token_data['oauth_token_secret'],
                params['oauth_verifier'][0]
            )
            auth.save_tokens(access_data)
        else:
            # Manual fallback
            print("\nAutomatic detection failed. Please:")
            print("1. Complete authorization in browser")
            print("2. Copy the FULL callback URL (from address bar)")
            print("3. Paste it below\n")
            
            while True:
                callback_url = input("Paste callback URL: ").strip()
                if "oauth_token" in callback_url and "oauth_verifier" in callback_url:
                    parsed = urlparse(callback_url)
                    params = parse_qs(parsed.query)
                    access_data = auth.get_access_token(
                        params['oauth_token'][0],
                        token_data['oauth_token_secret'],
                        params['oauth_verifier'][0]
                    )
                    auth.save_tokens(access_data)
                    break
                print("Invalid URL. Must contain oauth_token and oauth_verifier")
    
    except Exception as e:
        print(f"\nAuthentication failed: {str(e)}")

if __name__ == "__main__":
    main()