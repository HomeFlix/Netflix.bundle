
import re, cgi, urllib, httplib, sys
import oauth

HEADERS = {'User-agent' : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_2) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.101 Safari/537.1', 'Accept' : 'text/html,application/xhtml+xml,application/xml', 'Content-Type' : 'text/xml'}
NETFLIX_SERVER = 'api-public.netflix.com'
NETFLIX_PORT   = 80

NETFLIX_VERSION = '1.5'

REQUEST_TOKEN_URL = 'http://api-public.netflix.com/oauth/request_token'
ACCESS_TOKEN_URL  = 'http://api-public.netflix.com/oauth/access_token'
AUTHORIZATION_URL = 'https://api-public.netflix.com/oauth/login'
API_URL = 'http://api-public.netflix.com/'

CONSUMER_KEY    = 'nfeafbf2hpdnyfvr5dd32ka6'
CONSUMER_SECRET = 'bBsa6TqYab'

SORT_ALPHA = 'alphabetical'
SORT_DATE  = 'date_added'
SORT_QUEUE = 'queue_sequence'

RATING_NO_OPINION     = 'no_opinion'
RATING_NOT_INTERESTED = 'not_interested'

###################################################################################################

class NetflixAuthToken(oauth.OAuthToken):

  app_name = None
  user_id = None

  def __init__(self, key, secret, app_name=None, user_id=None):
    self.app_name = 'Plex'
    self.user_id = user_id
    oauth.OAuthToken.__init__(self, key, secret)

  def to_string(self):
    return oauth.OAuthToken.to_string(self)

  @staticmethod
  def from_string(s):
    params = cgi.parse_qs(s, keep_blank_values = False)

    key = params['oauth_token'][0]
    secret = params['oauth_token_secret'][0]

    if 'application_name' in params:
      app_name = params['application_name'][0]
    else:
      app_name = None

    if 'user_id' in params:
      user_id = params['user_id'][0]
    else:
      user_id = None

    return NetflixAuthToken(key, secret, app_name, user_id)

  def __str__(self):
    return self.to_string()

class NetflixRequest(object):

  custom_headers = HEADERS
  server = NETFLIX_SERVER
  port = NETFLIX_PORT
  request_token_url = REQUEST_TOKEN_URL
  access_token_url = ACCESS_TOKEN_URL
  authorization_url = AUTHORIZATION_URL
  api_url = API_URL
  signature_method = oauth.OAuthSignatureMethod_HMAC_SHA1()
  api_version = NETFLIX_VERSION

  def __init__(self, consumer_key = CONSUMER_KEY, consumer_secret = CONSUMER_SECRET):
    self.consumer_key = consumer_key
    self.consumer_secret = consumer_secret

    self.connection = httplib.HTTPConnection("%s:%d" % (self.server, self.port))
    #self.connection.debug = 1
    self.consumer = oauth.OAuthConsumer(self.consumer_key, self.consumer_secret)

    self.queue_etag = None

  def get_request_token(self):
    req = oauth.OAuthRequest.from_consumer_and_token(self.consumer, http_url = self.request_token_url)
    req.sign_request(self.signature_method, self.consumer, None)

    
    #Log(self.request_token_url)
    Log(req.to_url())
    
    #self.connection.debug = 1
    #self.connection.request(req.http_method, req.to_url(), headers = HEADERS)
    #response = self.connection.getresponse()
    #token = NetflixAuthToken.from_string(response.read())

    feeddata = urllib.urlopen(req.to_url()).read()
    #Log(feeddata)
    token = NetflixAuthToken.from_string(feeddata)

    #self.connection.close()

    return token

  def get_access_token(self, req_token):

    req = oauth.OAuthRequest.from_consumer_and_token(self.consumer, token = req_token, http_url = self.access_token_url)
    req.sign_request(self.signature_method, self.consumer, req_token)

    #self.connection.request(req.http_method, self.access_token_url, headers=req.to_header())
    #response = self.connection.getresponse()
    #data = response.read()
    #token = NetflixAuthToken.from_string(data)
    #self.connection.close()

    feeddata = urllib.urlopen(req.to_url()).read()
    #Log(feeddata)
    token = NetflixAuthToken.from_string(feeddata)

    return token

  def generate_authorization_url(self, req_token):
    params = {'application_name': req_token.app_name, 'oauth_consumer_key': self.consumer_key}
    req = oauth.OAuthRequest.from_token_and_callback(token = req_token, http_url = self.authorization_url, parameters = params)
    return req.to_url()

  def make_query(self, access_token = None, method = "GET", query = "", params = None, returnURL = True):
    if params is None:
      params = {}

    if query.startswith('http://'):
      url = query
    else:
      url = self.api_url + query

    params['v'] = self.api_version
    params['oauth_consumer_key'] = self.consumer_key
        
    req = oauth.OAuthRequest.from_consumer_and_token(self.consumer, token = access_token, http_method = method, http_url = url, parameters = params)
    req.sign_request(self.signature_method, self.consumer, access_token)

    if method == 'GET' or method == 'PUT' or method == 'DELETE':
      if returnURL:
        return req.to_url()
      else:  
        self.connection.request(method, req.to_url())

    elif method == 'POST':
      headers = {'Content-Type': 'application/x-www-form-urlencoded'}
      self.connection.request(method, url, body = req.to_postdata(), headers = headers)
    else:
      return None

    try:
         feeddata = urllib.urlopen(req.to_url()).read()
         #Log(feeddata)

    except HTTPError, e:
	 #Log(e.code)
         if e.code  == 401:
             feeddata = 401 

    #return self.connection.getresponse()
    return feeddata

class US_Account(object):

  @staticmethod
  def LoggedIn():

    Log("Testing logged in status")

    username = Prefs['username']
    password = Prefs['password']

    if not username or not password:
      Log("No Username or Password set")
      return False

    if 'accesstoken' in Dict:
      Log("Testing Access Token")
      access_token = NetflixAuthToken.from_string(Dict['accesstoken'])
      request = NetflixRequest()
      status = request.make_query(access_token = access_token, query = 'http://api-public.netflix.com/users/%s' % access_token.user_id, returnURL = False)

      if status == 401:
        del Dict['accesstoken']
        Dict.Save()
        Log("Access Token Failed")
        return False
      else:
        Log("Access Token Valid")
        return True

    Log("No Access Token")
    return False

  @staticmethod
  def TryLogIn():

    Log("Attempting to log in")

    # If we're already logged in, no need to try again...
    if US_Account.LoggedIn():
      Log("Already logged in")
      return True

    username = Prefs['username']
    password = Prefs['password']

    #Log(username)
    #Log(password)

    if not username or not password:
      Log("No Username or Password set")
      return False

    try:
      request = NetflixRequest()
      request_token = request.get_request_token()

      values = {'nextpage': 'http://www.netflix.com/',
                'SubmitButton': 'Click Here to Continue',
                'movieid': '',
                'trkid': '',
                'email': username,
                'password1': password,
                'RememberMe': 'True'}

      original_params = {'oauth_callback': '', 
                         'oauth_token': request_token.key, 
                         'application_name':'Plex', 
                         'oauth_consumer_key': CONSUMER_KEY,
                         'accept_tos': 'checked', 
                         'login': username, 
                         'password': password,
                         'x':'166',
                         'y':'13'}

      Log("Attempting to accept OAuth request token")
      page_content = HTTP.Request('https://api-user.netflix.com/oauth/login', original_params, cacheTime = 0).content
      page = HTML.ElementFromString(page_content)

      access_token = request.get_access_token(request_token)

      Log("Saving Access Token")
      Dict['accesstoken'] = access_token.to_string()
      Dict.Save()

      return US_Account.LoggedIn()

    except:
      Log.Exception("An error occurred while attempting to determine login status")
      return False

  @staticmethod
  def GetUserId():

    request = NetflixRequest()
    access_token = NetflixAuthToken.from_string(Dict['accesstoken'])
    url = request.make_query(access_token = access_token, method = 'GET', query = 'http://api-public.netflix.com/users/current', params = { 'v': '2' })

    details = XML.ElementFromURL(url)
    user_url = details.xpath('//resource/link')[0].get('href')

    return re.match('http://(.)+\.netflix.com/users/(?P<id>.+)', user_url).groupdict()['id']

  @staticmethod
  def GetAPIURL(url, params = {}):

    request = NetflixRequest()
    access_token = NetflixAuthToken.from_string(Dict['accesstoken'])
    return request.make_query(access_token = access_token, method = 'GET', query = url, params = params, returnURL = True)

  @staticmethod
  def GetTitleRating(title_ref):

    request = NetflixRequest()
    access_token = NetflixAuthToken.from_string(Dict['accesstoken'])
    url = request.make_query(access_token = access_token, method = 'GET', query = 'http://api-public.netflix.com/users/%s/ratings/title' % US_Account.GetUserId(), params = { 'title_refs': title_ref })

    details = XML.ElementFromURL(url)

    return True

  @staticmethod
  def SetTitleRating(title_ref, rating):

    Log("Attempting to set rating (%s) for title (%s)" % (rating, title_ref))
    request = NetflixRequest()
    access_token = NetflixAuthToken.from_string(Dict['accesstoken'])
    url = request.make_query(access_token = access_token, method = 'POST', query = 'http://api-public.netflix.com/users/%s/ratings/title' % US_Account.GetUserId(), params = { 'title_refs': title_ref, 'rating': str(rating) })

    details = XML.ElementFromURL(url)
    Log(XMl.StringFromElement(details))

    return True

  @staticmethod
  def RemoveFromQueue(url):
    entry_id = US_Account.IDFromURL(url)

    Log("Attempting to remove (%s) from queue" % entry_id)
    request = NetflixRequest()
    access_token = NetflixAuthToken.from_string(Dict['accesstoken'])
    status = request.make_query(access_token = access_token, method = 'DELETE', query ='http://api-public.netflix.com/users/%s/queues/instant/available/%s' % (US_Account.GetUserId(), entry_id), returnURL = False)

    if status == 401:
      return False
    else:
      return True

  @staticmethod
  def IDFromURL(url):
    return re.match('http://(.)+\.netflix.com/.+/(?P<id>[0-9]+)', url).groupdict()['id']
