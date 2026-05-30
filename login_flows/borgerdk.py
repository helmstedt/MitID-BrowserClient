# Script for https://www.borger.dk/mitoverblik
import requests, json, base64, sys
from bs4 import BeautifulSoup
sys.path.append("..")
sys.path.append(".")
from BrowserClient.BrowserClient import BrowserClient
from BrowserClient.Helpers import get_authentication_code, process_args, generate_nem_login_parameters, get_default_args, choose_between_multiple_identitites, get_aux_nem_login

argparser = get_default_args()
args = argparser.parse_args()

method, user_id, password, proxy = process_args(args)
if method not in ['APP', 'TOKENANDPASSWORD']:
    raise ValueError('Only app and token and password methods are supported for borger.dk')
session = requests.Session()
if proxy:
    session.proxies.update({"http": f"socks5://{proxy}", "https": f"socks5://{proxy}" })

# First part of borger.dk procedure
base_url = "https://www.borger.dk/mitoverblik?allowLogin=1"
request = session.get(base_url)
request.raise_for_status()
soup = BeautifulSoup(request.text, "xml")

params = {soup.form.input['name']: soup.form.input['value']}
request = session.post(soup.form['action'], data=params)
request.raise_for_status()

if request.status_code != 200:
    print(f"Failed session setup attempt, status code {request.status_code}")
    raise Exception(request.content)
if request.url != "https://nemlog-in.mitid.dk/login/mitid":
    print(f"Unexpected URL, failure to proceed.")
    raise Exception(request.content)   

soup = BeautifulSoup(request.text, "lxml")
requestverificationtoken = soup.find('input', {'name': '__RequestVerificationToken'}).get('value')

aux, params = get_aux_nem_login(session, requestverificationtoken)

# MitID procedure
aux = json.loads(base64.b64decode(aux))
authorization_code = get_authentication_code(session, aux, method, user_id, password)
print(f"Your MitID authorization code was ({authorization_code})")

# Second part of borger.dk procedure
params['MitIDAuthCode'] = authorization_code
request = session.post("https://nemlog-in.mitid.dk/login/mitid", data=params)
request.raise_for_status()
soup = BeautifulSoup(request.text, "xml")

# User has more than one login option
if request.url == 'https://nemlog-in.mitid.dk/loginoption':
    request, soup = choose_between_multiple_identitites(session, request, soup)
    request.raise_for_status()

params = {soup.form.input['name']: soup.form.input['value']}
request = session.post(soup.form['action'], data=params)
request.raise_for_status()

request = session.get(base_url)
request.raise_for_status()
soup = BeautifulSoup(request.text, "xml")
print(f'You are {soup.select_one("span.poa-picker__title").text.strip()}')