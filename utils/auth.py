import base64
import hashlib
import hmac
import time
import urllib.parse
from flask import Flask, request
import threading
import requests

from constants import (
    CALLBACK_URL,
    CONSUMER_KEY,
    CONSUMER_SECRET,
    oauth_signature_method,
    oauth_version,
)

# Flask server for capturing callback
app = Flask(__name__)
verifier = None
oauth_token = None

@app.route('/callback')
def callback():
    global verifier, oauth_token
    verifier = request.args.get('oauth_verifier')
    oauth_token = request.args.get('oauth_token')
    return "Authentication complete. You may close this window."

def run_server():
    app.run(port=8080)

def get_fatsecret_token(callback_url=CALLBACK_URL):
    """Obtain OAuth request token from FatSecret API."""
    oauth_nonce = hashlib.md5(str(time.time()).encode()).hexdigest()
    oauth_timestamp = str(int(time.time()))

    params = {
        "oauth_callback": callback_url,
        "oauth_consumer_key": CONSUMER_KEY,
        "oauth_nonce": oauth_nonce,
        "oauth_signature_method": oauth_signature_method,
        "oauth_timestamp": oauth_timestamp,
        "oauth_version": oauth_version,
    }

    # Create parameter string for base string
    param_string = "&".join(
        f"{k}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(params.items())
    )

    # Create signature base string
    base_string = "&".join([
        "GET",
        urllib.parse.quote(
            "https://authentication.fatsecret.com/oauth/request_token",
            safe="",
        ),
        urllib.parse.quote(param_string, safe=""),
    ])

    signing_key = f"{CONSUMER_SECRET}&"
    signature = hmac.new(
        signing_key.encode(),
        base_string.encode(),
        hashlib.sha1,
    ).digest()
    oauth_signature = base64.b64encode(signature).decode()

    params["oauth_signature"] = oauth_signature

    query_string = "&".join(
        f"{k}={urllib.parse.quote(str(v), safe='')}"
        for k, v in params.items()
    )
    request_url = (
        "https://authentication.fatsecret.com/oauth/request_token"
        f"?{query_string}"
    )

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "python-requests/2.31.0",
    }

    response = requests.get(request_url, headers=headers)
    if response.status_code == 200:
        return dict(pair.split('=') for pair in response.text.split('&'))
    raise Exception(f"Failed to get request token: {response.text}")

def get_verifier(request_token):
    """Start a local server to capture the OAuth verifier"""
    global verifier
    
    # Start temporary web server in a daemon thread
    server = threading.Thread(target=run_server)
    server.daemon = True
    server.start()
    
    # Generate the authorization URL with local callback
    auth_url = (
        "https://authentication.fatsecret.com/oauth/authorize"
        f"?oauth_token={request_token}"
        f"&oauth_callback=http://localhost:8080/callback"
    )
    
    print(f"\nPlease visit this URL to authorize:")
    print(auth_url)
    
    # Wait for callback
    while verifier is None:
        time.sleep(1)
    
    return verifier

def exchange_for_access_token(request_token, request_token_secret, verifier):
    """Exchange verified request token for access token"""
    url = "https://authentication.fatsecret.com/oauth/access_token"
    
    params = {
        "oauth_consumer_key": CONSUMER_KEY,
        "oauth_token": request_token,
        "oauth_verifier": verifier,
        "oauth_signature_method": oauth_signature_method,
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": hashlib.md5(str(time.time()).encode()).hexdigest(),
        "oauth_version": oauth_version
    }

    # Generate signature
    base_string = "&".join([
        "GET",
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote("&".join(f"{k}={v}" for k,v in sorted(params.items())), safe="")
    ])
    
    signing_key = f"{CONSUMER_SECRET}&{request_token_secret}"
    signature = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    params["oauth_signature"] = base64.b64encode(signature).decode()

    response = requests.get(url, params=params)
    if response.status_code == 200:
        return dict(pair.split('=') for pair in response.text.split('&'))
    raise Exception(f"Access token error: {response.text}")

def main():
    """Complete OAuth flow without browser GUI interaction"""
    try:
        # Step 1: Get request token with local callback URL
        print("Getting request token...")
        token_data = get_fatsecret_token(callback_url="http://localhost:8080/callback")
        print("\nRequest Token Obtained:")
        print(f"Token: {token_data['oauth_token']}")
        print(f"Token Secret: {token_data['oauth_token_secret']}")
        
        # Step 2: Get verifier through local callback server
        print("\nStarting local callback server...")
        verifier = get_verifier(token_data['oauth_token'])
        print(f"\nVerifier Received: {verifier}")
        
        # Step 3: Exchange for access token
        print("\nExchanging for access token...")
        access_data = exchange_for_access_token(
            token_data['oauth_token'],
            token_data['oauth_token_secret'],
            verifier
        )
        
        print("\nAccess Token Obtained:")
        print(f"Access Token: {access_data['oauth_token']}")
        print(f"Access Token Secret: {access_data['oauth_token_secret']}")
        
        print("\nOAuth flow completed successfully!")
        return access_data
        
    except Exception as e:
        print(f"\nError during OAuth flow: {str(e)}")
        return None

if __name__ == "__main__":
    main()