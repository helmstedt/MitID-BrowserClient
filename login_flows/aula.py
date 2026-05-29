# Script for https://www.aula.dk/auth/login.php?type=unilogin
import requests, json, base64, sys
from bs4 import BeautifulSoup
sys.path.append("..")
sys.path.append(".")
from BrowserClient.BrowserClient import BrowserClient
from BrowserClient.Helpers import get_authentication_code, process_args, generate_nem_login_parameters, get_default_args, choose_between_multiple_identitites

argparser = get_default_args()
args = argparser.parse_args()

method, user_id, password, proxy = process_args(args)
session = requests.Session()
if proxy:
    session.proxies.update({"http": f"socks5://{proxy}", "https": f"socks5://{proxy}" })

# First part of aula.dk procedure
request = session.get("https://www.aula.dk/auth/login.php?type=unilogin")
request.raise_for_status()

soup = BeautifulSoup(request.text, "lxml")
params = {'selectedIdp': 'nemlogin3'}
request = session.post(soup.form['action'], data=params)
request.raise_for_status()

if request.url != "https://nemlog-in.mitid.dk/login/mitid":
    print(f"Unexpected URL, failure to proceed.")
    raise Exception(request.content)   
soup = BeautifulSoup(request.text, "lxml")
requestverificationtoken = soup.find('input', {'name': '__RequestVerificationToken'}).get('value')

params = {
    '__RequestVerificationToken': requestverificationtoken,
    'SessionStorageActiveSessionUuid': session.cookies['SessionUuid'],
    'SessionStorageActiveChallenge': session.cookies['Challenge']
}
initialize_url = 'https://nemlog-in.mitid.dk/login/mitid/initialize'
request = session.post(initialize_url, data=params)
request.raise_for_status()

aux = json.loads(json.loads(request.text))['Aux']

# MitID procedure
aux = json.loads(base64.b64decode(aux))
authorization_code = get_authentication_code(session, aux, method, user_id, password)
print(f"Your MitID authorization code was ({authorization_code})")

# Second part of aula.dk procedure
params['MitIDAuthCode'] = authorization_code
request = session.post("https://nemlog-in.mitid.dk/login/mitid", data=params)
request.raise_for_status()
soup = BeautifulSoup(request.text, "xml")

# User has more than one login option
if request.url == 'https://nemlog-in.mitid.dk/loginoption':
    request, soup = choose_between_multiple_identitites(session, request, soup)
    request.raise_for_status()

params = {}
for soupinput in soup.form.find_all('input'):
    try:
        params[soupinput['name']] = soupinput['value']
    except:
        continue
request = session.post(soup.form['action'], data=params)
request.raise_for_status()
soup = BeautifulSoup(request.text, "lxml")

request = session.post(soup.form['action'])
request.raise_for_status()
soup = BeautifulSoup(request.text, "lxml")

params = {}
for soupinput in soup.form.find_all('input'):
    try:
        params[soupinput['name']] = soupinput['value']
    except:
        continue
request = session.post(soup.form['action'], data=params)
request.raise_for_status()

print('Login succeeeded, trying API request')

api_request = session.get('https://www.aula.dk/api/v23/?method=profiles.getProfileContext')
request.raise_for_status()
print(api_request.json())