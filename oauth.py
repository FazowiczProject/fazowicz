#!/usr/bin/env python3
from requests.auth import HTTPBasicAuth
import json
import requests
import time
ACCESS_TOKEN = None
REFRESH_TOKEN = None
ACCESS_TOKEN_CLIENT_ID = '...'
ACCESS_TOKEN_CLIENT_SECRET = '...'
ACCESS_TOKEN_URL = '...'
ACCESS_TOKEN_INTROSPECT_URL = '...'

next_access_token_request_time = time.time()

def get_access_token():
    global ACCESS_TOKEN, next_access_token_request_time
    if next_access_token_request_time > time.time() and ACCESS_TOKEN != None: # access token is still valid
        return ACCESS_TOKEN
    
    client_credentials_request = {
        'grant_type': 'client_credentials',
    }
    oauth_response = requests.post(ACCESS_TOKEN_URL, data=client_credentials_request, auth=HTTPBasicAuth(ACCESS_TOKEN_CLIENT_ID, ACCESS_TOKEN_CLIENT_SECRET))
    if oauth_response.status_code == 200:
        oauth_response_body = json.loads(oauth_response.text)
        next_access_token_request_time = time.time() + float(oauth_response_body['expires_in'])
        if 'access_token' in oauth_response_body.keys():
            ACCESS_TOKEN = oauth_response_body['access_token']
            return ACCESS_TOKEN
        
def verify_access_token(access_token):
    token_introspection_request = {
        'token': access_token
    }
    oauth_response = requests.post(ACCESS_TOKEN_INTROSPECT_URL, data=token_introspection_request, auth=HTTPBasicAuth(ACCESS_TOKEN_CLIENT_ID, ACCESS_TOKEN_CLIENT_SECRET))
    if oauth_response.status_code == 200:
        oauth_response_body = json.loads(oauth_response.text)
        return oauth_response_body['active']
    else:
        return False