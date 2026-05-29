# Script for https://www.nordnet.dk/logind
import requests, json, base64, sys, string, secrets, uuid
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
sys.path.append("..")
sys.path.append(".")
from BrowserClient.Helpers import get_authentication_code, process_args, get_default_args

def nordnet_login(user_id, password='', method="APP", proxy=None):
    nordnet_session = requests.Session()
    if proxy:
        nordnet_session.proxies.update({"http": f"socks5://{proxy}", "https": f"socks5://{proxy}" })

    # First part of Nordnet procedure
    nem_login_state = uuid.uuid4()
    digits = string.digits
    form_digits = ''.join(secrets.choice(digits) for i in range(29))

    json_data = {
        "redirectUri": "https://www.nordnet.dk/login",
        "state": f"NEXT_OIDC_STATE_{nem_login_state}",
        "idp":"MITID"
    }
    login_url = 'https://api.prod.nntech.io/authentication/v2/methods/signicat/start'
    request = nordnet_session.post(login_url, json=json_data)
    request.raise_for_status()

    request = nordnet_session.get(request.json()['requestUri'])
    request.raise_for_status()
    soup = BeautifulSoup(request.text, 'lxml')

    request = nordnet_session.get(soup.div['data-index-url'])
    request.raise_for_status()
    soup = BeautifulSoup(request.text, 'lxml')

    request = nordnet_session.post(soup.div.next['data-base-url']+soup.div.next['data-init-auth-path'])
    request.raise_for_status()

    # MitID procedure
    aux = json.loads(base64.b64decode(request.json()["aux"]))
    authorization_code = get_authentication_code(nordnet_session, aux, method, user_id, password)
    print(f"Your MitID authorization code was ({authorization_code})")

    # Second part of Nordnet procedure
    payload = f'''-----------------------------{form_digits}\r\nContent-Disposition: form-data; name="authCode"\r\n\r\n{authorization_code}\r\n-----------------------------{form_digits}--\r\n'''
    headers = {'Content-Type': f'multipart/form-data; boundary=---------------------------{form_digits}'}

    request = nordnet_session.post(soup.div.next['data-base-url']+soup.div.next['data-auth-code-path'], data=payload, headers=headers)
    request.raise_for_status()

    request = nordnet_session.get(soup.div.next['data-base-url']+soup.div.next['data-finalize-auth-path'])
    request.raise_for_status()

    parsed_url = urlparse(request.url)
    code = parse_qs(parsed_url.query)['code'][0]

    payload = {
        "authenticationProvider": "SIGNICAT",
        "countryCode":"DK", 
        "signicat": {
            "authorizationCode": code,
            "redirectUri":"https://www.nordnet.dk/login"
            }
        }

    nordnet_session.headers['client-id'] = 'NEXT'

    request = nordnet_session.post('https://www.nordnet.dk/nnxapi/authentication/v2/sessions', json=payload)
    request.raise_for_status()
    
    request = nordnet_session.post('https://www.nordnet.dk/api/2/authentication/nnx-session/login', json={})
    request.raise_for_status()
    nordnet_session.headers['ntag'] = request.headers['ntag']

    request = nordnet_session.post('https://www.nordnet.dk/nnxapi/authorization/v1/tokens', json={})
    request.raise_for_status()

    bearer_token = request.json()['jwt']

    nntech_session = requests.Session()
    if proxy:
        nntech_session.proxies.update({"http": f"socks5://{proxy}", "https": f"socks5://{proxy}" })
    nntech_session.headers['authorization'] = f'Bearer {bearer_token}'
    nntech_session.headers['x-locale'] = 'da-DK'

    return nordnet_session, nntech_session

if __name__ == "__main__":
    argparser = get_default_args()
    args = argparser.parse_args()
    method, user_id, password, proxy = process_args(args)

    nordnet_session, nntech_session = nordnet_login(user_id, password, method, proxy)

    # Get accounts
    #accounts = nordnet_session.get('https://www.nordnet.dk/api/2/accounts')
    #print(accounts.json())

    # Get transactions
    # accids = (',').join([str(account['accid']) for account in accounts.json()])
    # fromdate = '2013-01-01'
    # todate = datetime.strftime(date.today(), '%Y-%m-%d')

    # Get JSON transactions
    # Limited to 800 results, the maximum may be larger
    # Change offset to get subsequent transactions
    # You can get total transactions by requesting: 
    # f'https://api.prod.nntech.io/transaction/transaction-and-notes/v1/transaction-summary?fromDate={fromdate}&toDate={todate}&accids={accids}&includeCancellations=false'
    # transactions_json = nntech_session.get(f'https://api.prod.nntech.io/transaction/transaction-and-notes/v1/transactions/page?fromDate={fromdate}&toDate={todate}&accids={accids}&offset=0&limit=800&sort=ACCOUNTING_DATE&sortOrder=DESC&includeCancellations=false')
    # print(transactions_json.json())

    # Get CSV transactions
    # Tab delimited. To change to semicolon-delimited, add:
    # csv_file = csv_file.replace('\t',';')
    #transactions_csv = nntech_session.get(f'https://api.prod.nntech.io/transaction/transaction-and-notes/v1/transactions/csv/filter?accids={accids}&fromDate={fromdate}&toDate={todate}&sort=ACCOUNTING_DATE&sortOrder=DESC&includeCancellations=false')
    #transactions_csv_bytes = transactions_csv.json()['bytes']
    #transactions_csv_decoded_bytes = base64.b64decode(transactions_csv_bytes)
    #csv_file = transactions_csv_decoded_bytes.decode('utf-16')
    #print(csv_file)