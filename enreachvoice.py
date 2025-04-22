import os
import requests
import json
import logging
from datetime import datetime, timezone
import time

HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'X-Json-Serializer': '2',
    'User-Agent': 'enreachvoice-python/0.1',
}
DISCOVERY_URL = 'https://discover.enreachvoice.com'

class Client:
    def __init__(self, username:str, secretkey:str=None, password:str=None, apiEndpoint:str=None):
        """
        Initialize the EnreachVoice API client.

        Args:
        username (str): EnreachVoice API username
        secretkey (str): EnreachVoice API secret key. If not provided, will be retrieved using password
        password (str): EnreachVoice API password. If not provided, will be used to retrieve secretkey
        apiEndpoint (str): EnreachVoice API endpoint. If not provided, will be retrieved from discovery service by username
        """
        self.username = username

        if (apiEndpoint is not None):
            logging.debug("Using provided apiEndpoint")
            self.apiEndpoint = apiEndpoint
        else:
            logging.debug("No apiEndpoint provided")
            # get apiEndpoint from discovery service
            logging.debug("Getting apiEndpoint from discovery service")
            apiEndpoint = self.get_apiurl()
            if apiEndpoint is None:
                return
            self.apiEndpoint = apiEndpoint

        if (secretkey is not None):
            logging.debug("Using provided secretkey")
            self.secretkey = secretkey
        else:
            logging.debug("No secretkey provided")
            if (password is None):
                logging.error("Either secretkey or password must be provided")
                return
            logging.debug("Got password, using that to retieve secretkey")
            secretkey = self.authenticate_with_password(password)
            if secretkey is None:
                logging.error("Failed to authenticate")
                return
            self.secretkey = secretkey

        user = self.invoke_api(method='GET', path='users/me')
        if user is None:
            logging.error("Failed to get user id")
            return
        self.userid = user['Id']

    def get_apiurl(self):
        """
        Invoke discovery service to get the API endpoint.
        https://doc.enreachvoice.com/beneapi/#service-discovery

        Returns:
        str: API endpoint if successful, None otherwise

        """
        try:
            url = f"{DISCOVERY_URL}/api/user?user={self.username}"
            logging.debug(f"Invoking discovery: {url}")
            discoveryResponse = requests.get(url)
            if discoveryResponse.status_code != 200:
                logging.error(f"Discovery failed: {discoveryResponse.status_code} {discoveryResponse.text}")
                return None
            logging.debug(f"Discovery response: {json.dumps(discoveryResponse.json(),indent=2)}")
            apiEndpoint = discoveryResponse.json()[0]['apiEndpoint']
            # if api url has ending slash, remove it
            if apiEndpoint[-1] == '/':
                apiEndpoint = apiEndpoint[:-1]
            logging.info(f"API endpoint: {apiEndpoint}")
            return apiEndpoint
        except Exception as e:
            logging.error(f"Error invoking discovery: {e}")
            return None

    def invoke_api(self, path, method='GET', params=None, payload=None):
        """
        Invoke the EnreachVoice API with the given method, path, parameters and payload.

        Args:
        path (str): Path to the API endpoint
        method (str): HTTP method to use. Default is 'GET'
        params (dict): Query parameters to send with the request
        payload (dict): Payload to send with the request

        Returns:
        dict: API response if successful, None otherwise
        """

        try:
            # ensure we have a valid method
            if method not in ['GET', 'POST', 'PUT', 'DELETE']:
                logging.error(f"Invalid method: {method}")
                return None
            # ensure we have a valid path
            if path is None:
                logging.error("Path must be provided")
                return None
            #ensure path starts with a slash
            if path[0] != '/':
                path = '/' + path

            url = f"{self.apiEndpoint}{path}"
            logging.debug(f"Invoking {method}: {url}")
            start_time = time.time()
            if method == 'GET':
                response = requests.get(url, headers=HEADERS, auth=(self.username, self.secretkey), params=params)
            elif method == 'POST':
                response = requests.post(url, headers=HEADERS, auth=(self.username, self.secretkey), params=params, data=(json.dumps(payload)))
            elif method == 'PUT':
                response = requests.put(url, headers=HEADERS, auth=(self.username, self.secretkey), params=params, data=(json.dumps(payload)))
            elif method == 'DELETE':
                response = requests.delete(url, headers=HEADERS, auth=(self.username, self.secretkey), params=params)
            duration_ms = (time.time() - start_time) * 1000
            logging.debug(f"Got response {response.status_code} in {duration_ms} ms: {json.dumps(response.json(),indent=2)}")
            
            if response.ok is not True:
                logging.error(f"API request failed: {response.status_code} {response.text}")
                return None            
            return response.json()
        except Exception as e:
            logging.error(f"Error while invoking REST API: {e}")
            return None

    def authenticate_with_password(self, password):
        """
        Authenticate with the EnreachVoice API using the provided user password.
        https://doc.enreachvoice.com/beneapi/#post-authuser-email

        Args:
        password (str): User password

        Returns:
        str: Secretkey if successful, None otherwise
        """
        try:
            url =f"{self.apiEndpoint}/authuser/{self.username}"
            payload = {
                'UserName': self.username,
                'Password': password,
            }
            logging.debug(f"Invoking POST: {url} {json.dumps(payload,indent=2)}")
            response = requests.post(url, headers=HEADERS, data=json.dumps(payload))
            if response.status_code != 200:
                logging.error(f"Authentication failed: {response.status_code} {response.text}")
                return None
                        
            logging.debug(f"API response: {json.dumps(response.json(),indent=2)}")
            secretkey = response.json()['SecretKey']
            logging.info(f"User {self.username}uthenticated successfully")
            return secretkey
        except Exception as e:
            logging.error(f"Error authenticating: {e}")
            return None
               
    def get_usercalls(self, **filterParameters):
        """
        Get user call events. That is, call evets that are associated to a user. The same callId can be
        associated to multiple call events.

        https://doc.enreachvoice.com/beneapi/#get-calls

        Args:
        filterParameters (dict): Filter parameters to apply to the call events query
        https://doc.enreachvoice.com/beneapi/#callfilterparameters
        Give 'DateTime' as datetime objects, they will be converted to proper string format
        
        Returns:
        dict: User calls if successful, None otherwise
        """
        try:

            logging.debug(f"Filter parameters: {json.dumps(filterParameters,indent=2,default=str)}")
            # Ensure we have eithre StartTime and EndTime, ModifiedAfter and ModifiedBefore, or CallId
            # Time range cannot be more than 31 days
            # Times must be given in proper string format in UTC, like "2015-01-01 06:00:00"

            if 'StartTime' in filterParameters and 'EndTime' in filterParameters:
                st = filterParameters['StartTime']
                filterParameters['StartTime'] = st.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                et = filterParameters['EndTime']
                filterParameters['EndTime'] = et.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

                if (et - st).days > 31:
                    logging.error("Time range cannot be more than 31 days")
                    return None
            elif 'ModifiedAfter' in filterParameters and 'ModifiedBefore' in filterParameters:
                    ma = filterParameters['ModifiedAfter']
                    filterParameters['ModifiedAfter'] = ma.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    mb = filterParameters['ModifiedBefore']
                    filterParameters['ModifiedBefore'] = mb.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

                    if (mb - ma).days > 31:
                        logging.error("Time range cannot be more than 31 days")
                        return None
            elif 'CallId' in filterParameters:
                pass
            else:
                logging.error("Must have StartTime and EndTime, ModifiedAfter and ModifiedBefore, or CallId")
                return None
            
            calls = self.invoke_api(method='GET', path='/calls', params=filterParameters)
            
            logging.info(f"Retrieved {len(calls)} calls")
            return calls
        except Exception as e:
            logging.error(f"Error getting user calls: {e}")
            return None

    def get_inbound_queuecalls(self, **filterParameters):
        """
        Get inbound queuecalls aka. servicecalls.
        https://doc.enreachvoice.com/beneapi/#get-servicecall


        Args:
        filterParameters (dict): Filter parameters to apply to the servicecall query
        https://doc.enreachvoice.com/beneapi/#servicecallfilterparameters
        Give 'DateTime' as datetime objects, they will be converted to proper string format
        
        Returns:
        dict: Service calls if successful, None otherwise
        """
        try:
            logging.debug(f"Filter parameters: {json.dumps(filterParameters,indent=2,default=str)}")
            # Ensure we have eithre StartTime and EndTime, ModifiedAfter and ModifiedBefore, or CallId
            # Time range cannot be more than 31 days
            # Times must be given in proper string format in UTC, like "2015-01-01 06:00:00"

            if 'StartTime' in filterParameters and 'EndTime' in filterParameters:
                st = filterParameters['StartTime']
                filterParameters['StartTime'] = st.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                et = filterParameters['EndTime']
                filterParameters['EndTime'] = et.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

                if (et - st).days > 31:
                    logging.error("Time range cannot be more than 31 days")
                    return None
            elif 'ModifiedAfter' in filterParameters and 'ModifiedBefore' in filterParameters:
                    ma = filterParameters['ModifiedAfter']
                    filterParameters['ModifiedAfter'] = ma.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    mb = filterParameters['ModifiedBefore']
                    filterParameters['ModifiedBefore'] = mb.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

                    if (mb - ma).days > 31:
                        logging.error("Time range cannot be more than 31 days")
                        return None
            else:
                logging.error("Must have StartTime and EndTime or ModifiedAfter and ModifiedBefore")
                return None
            
            calls = self.invoke_api(method='GET', path='/servicecall', params=filterParameters)
            return calls
        except Exception as e:
            logging.error(f"Error getting service calls: {e}")
            return None

    def get_recording_file(self, recordingId, path):
        """
        Download recording to mp3-file.
        https://doc.enreachvoice.com/beneapi/#get-calls-recordings-recordingid

        Args:
        recordingId (str): RecordingId of the recording to get
        path (str): Path directory to save the recording file. File will be saved as <recordingId>.mp3

        Returns:
        """
        try:
            # ensure path exists
            os.makedirs(path, exist_ok=True)

            url = f"{self.apiEndpoint}/calls/recordings/{recordingId}"
            logging.debug(f"Invoking GET: {url}")
            recording_response = requests.get(url, headers=HEADERS, auth=(self.username, self.secretkey))
            if recording_response.status_code != 200:
                logging.error(f"Get recording failed: {recording_response.status_code} {recording_response.text}")
                return None
            recording_metadata = recording_response.json()
            logging.info(f"Retrieved recording metadata: {json.dumps(recording_metadata,indent=2)}")
            recordingUrl = f"{self.apiEndpoint}/{recording_metadata['URL']}"
            logging.debug(f"Invoking GET: {recordingUrl}")
            recording_audio = requests.get(recordingUrl)    

            with open(f"{path}/{recordingId}.mp3", 'wb') as f:
                f.write(recording_audio.content)
            logging.info(f"Recording file saved to {path}/{recordingId}.mp3")
        except Exception as e:
            logging.error(f"Error getting recording file: {e}")
            return None

    def get_transcript(self, transcriptId, wait_pending=True):
        """
        Get transcript by transcriptId.

        Args:
        transcriptId (str): TranscriptId of the transcript to get
        wait_pending (bool): If True, wait for pending transcript to be ready. Default is True

        Returns:
        dict: Transcript if successful, None otherwise
        """

        try:
            # GET /calls/transcripts/{transcriptId}

            path = f"/calls/transcripts/{transcriptId}"
            transcript = self.invoke_api(method='GET', path=path)
            if transcript is None:
                logging.error(f"Failed to get transcript {transcriptId}")
                return None
            
            # check status, if pending, wait for it to be ready
            status = transcript['TranscriptStatus']
            if status == 'Pending' and wait_pending:
                max_retries = 10
                retries = 0
                while status == 'Pending':
                    if retries >= max_retries:
                        logging.error("Max retries reached")
                        break
                    
                    retries += 1
                    time.sleep(10)
                    transcript = self.invoke_api(method='GET', path=path)
                    status = transcript['TranscriptStatus']
                    logging.info(f"Retrieved transcript status: {status}")
            
            return transcript
        except Exception as e:
            logging.error(f"Error getting transcript: {e}")
            return None






 