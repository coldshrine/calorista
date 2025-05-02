import base64
import hashlib
import hmac
import time
import urllib.parse

import requests

from constants import (
    CALLBACK_URL,
    CONSUMER_KEY,
    CONSUMER_SECRET,
    oauth_signature_method,
    oauth_version,
)


def get_fatsecret_token():
    """Obtain OAuth request token from FatSecret API.
    
    Returns:
        dict: Dictionary containing token response data
        
    Raises:
        Exception: If token request fails
    """
    oauth_nonce = hashlib.md5(str(time.time()).encode()).hexdigest()
    oauth_timestamp = str(int(time.time()))

    params = {
        "oauth_callback": CALLBACK_URL,
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

    print("Making request to:", request_url)
    response = requests.get(request_url, headers=headers)

    print("\nResponse:")
    print("Status Code:", response.status_code)
    print("Response:", response.text)

    if response.status_code == 200:
        return dict(pair.split('=') for pair in response.text.split('&'))
    
    raise Exception(f"Failed to get request token: {response.text}")


def main():
    """Main execution function."""
    try:
        token_data = get_fatsecret_token()
        print("\nSuccess! Token data:")
        print(token_data)
        
        auth_url = (
            "https://authentication.fatsecret.com/oauth/authorize"
            f"?oauth_token={token_data['oauth_token']}"
        )
        print(f"\nAuthorization URL: {auth_url}")
        
    except Exception as e:
        print(f"\nError: {str(e)}")


if __name__ == "__main__":
    main()