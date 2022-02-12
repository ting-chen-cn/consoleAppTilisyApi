

import json,os,sys,uuid,datetime,requests,jwt,pickle,re
from locale import currency
from pprint import pprint
from urllib.parse import urlparse, parse_qs
from generateJWT import token

# Function to extract the index, name and country of the ASPSPData https://enablebanking.com/docs/tilisy/latest/#tocs_aspsp
def Extract(lst):
    return [[lst.index(item),item['name'] ,item['country']] for item in lst ]

# Function to get the application data https://enablebanking.com/docs/tilisy/latest/#tocs_getapplicationresponse associated with provided JWT token
def getApp(API_ORIGIN,base_headers):
    r = requests.get(f"{API_ORIGIN}/application", headers=base_headers)
    if r.status_code == 200:
        app = r.json()
        return app
    else:
        print(f"Error response {r.status_code}:", r.text)
        print('Exit programme caused by error in getting application request.')
        exit(0)

# Function to get the ASPSPData https://enablebanking.com/docs/tilisy/latest/#tocs_aspsp
def getBanks(API_ORIGIN,base_headers):
    r = requests.get(f"{API_ORIGIN}/aspsps", headers=base_headers)
    if r.status_code == 200:
        aspsps = r.json()["aspsps"]
        return aspsps
    else:
        print(f"Error response {r.status_code}:", r.text)
        print('Exit programme caused by error in getting aspsps request.')
        exit(0)
    
# Print the selections o available ASPSPs for user to selected from
def printSelections(aspsps):
    namesOfBanks = Extract(aspsps)
    lengthOfName = max([len(name[1]) for name in namesOfBanks])
    print("\n")
    print("<---------------- Available banks list ---------------->")
    pprint(f"  {'index':<10}{'name':^{lengthOfName}}{'country':>10}   ")
    for i in range(len(namesOfBanks)):
        pprint(f"  {namesOfBanks[i][0]:<10}{namesOfBanks[i][1]:^{lengthOfName}}{namesOfBanks[i][2]:>10}   ")
    print('<------------------------------------------------------>\n')
    id = input("Please choose bank from the above list by inputting the index or letter q to quit the programme: ")
    if id=='q':
        print('Exit programme caused by user input.')
        exit(0)
    while int(id)<0 or int(id)>len(namesOfBanks)-1:
        pprint('The index you input is out of range')
        id = input("Please input the index again or letter q to quit the programme: ")
        if id=='q':
            print('Exit programme caused by user input.')
            exit(0)
    chosenASP = aspsps[int(id)]
    
    if 'sandbox' in chosenASP.keys():
        print('\n The sandbox of users of the bank you selected is list below:\n')
        print(chosenASP['sandbox'])
    return chosenASP

# Function for user authorization by providing a link redirect link and redirecting a PSU to that link
def authorization(API_ORIGIN,chosenASP,app,base_headers):
    ASPSP_NAME = chosenASP['name']
    ASPSP_COUNTRY = chosenASP['country']
    # Starting authorization
    body = {
        "access": {
            "valid_until": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=10)).isoformat()
        },
        "aspsp": {"name": ASPSP_NAME, "country": ASPSP_COUNTRY},
        "state": str(uuid.uuid4()),
        "redirect_url": app["redirect_urls"][0],
        "psu_type": "personal",
    }
    r = requests.post(f"{API_ORIGIN}/auth", json=body, headers=base_headers)
    if r.status_code == 200:
        auth_url = r.json()["url"]
        print(f"\n To authenticate open URL:\n\n {auth_url}")
    else:
        print(f"Error response {r.status_code}:", r.text)
        print('Exit programme caused by error in authorization request.')
        exit(0)
    redirected_url = input("\nPaste here the URL you have been redirected to or type letter q to quit programme: ")
    if redirected_url=='q':
        exit(0)
    auth_code = parse_qs(urlparse(redirected_url).query)["code"][0]
    r = requests.post(f"{API_ORIGIN}/sessions", json={"code": auth_code}, headers=base_headers)
    if r.status_code == 200:
        session = r.json()
        return session
    else:
        print(f"Error response {r.status_code}:", r.text)
        print('Exit programme caused by error in getting session request.')
        exit(0)

# Function to get the list of account transactions according to provided parameters
def getTransactions(API_ORIGIN,session,base_headers):
    accounts = [ (item["uid"],item["account_id"]["iban"]) for item in session["accounts"]]
    data = {'balances':{},'transactions':{}}
    for uid,name in accounts:
        if name == None:
            name = 'empty iban'
        # Retrieving account balances
        r = requests.get(f"{API_ORIGIN}/accounts/{uid}/balances", headers=base_headers)
        if r.status_code == 200:
            data['balances'][name] = r.json()['balances']
        else:
            print(f"Error response {r.status_code}:", r.text)
            print('Exit programme caused by error in getting balances request.')
            exit(0)


        # Retrieving account transactions (since 30 days ago)
        query = {
            "date_from": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).date().isoformat(),
        }
        transactions = []
        continuation_key = None
        while True:
            if continuation_key:
                query["continuation_key"] = continuation_key
            r = requests.get(
                f"{API_ORIGIN}/accounts/{uid}/transactions",
                params=query,
                headers=base_headers,
            )
            if r.status_code == 200:
                resp_data = r.json()
                transactions.append(resp_data["transactions"])
                continuation_key = resp_data.get("continuation_key")
                if not continuation_key:
                    break
                
            else:
                print(f"Error response {r.status_code}:", r.text)
                print('Exit programme caused by error in getting transactions request.')
                exit(0)
        
        data['transactions'][name] = transactions
    return data

# Function to print the summary information of each account 
def printSummary(data):
    print("\n")
    print("<---------------------- Summary of transactions ---------------------->")
    print(f"{'account iban':<20}{'numbers':^10}{'maximum':^10}{'credit':^10}{'debit':^10}{'currency':>10}\n")
    for key,values in data['transactions'].items():
        transaction = values[0]
        numberOfTransactions = len(transaction)
        if numberOfTransactions!=0:
            currency = transaction[0]['transaction_amount']['currency']
            maxValue = max([float(item['transaction_amount']['amount']) for item in transaction])
            amount_DBIT = sum([float(item['transaction_amount']['amount']) for item in transaction  if item['credit_debit_indicator']=='DBIT'] )
            amount_CRDT = sum([float(item['transaction_amount']['amount']) for item in transaction  if item['credit_debit_indicator']=='CRDT'])
            maxValue = format(maxValue, '.2f')
            amount_DBIT = format(amount_DBIT, '.2f')
            amount_CRDT = format(amount_CRDT, '.2f')
            if key=='':
                key='empty name'
            print(f"{key:<20}{numberOfTransactions:^10}{maxValue:^10}{amount_CRDT:^10}{amount_DBIT:^10}{currency:>10}")
    print('<--------------------------------------------------------------------->')
    print("\n")


if __name__ == "__main__":
    base_headers = {"Authorization": f"Bearer {token}"}
    API_ORIGIN = "https://api.tilisy.com"
    ASPSP_NAME = "Nordea"
    ASPSP_COUNTRY = "FI"

    app = getApp(API_ORIGIN,base_headers)
    aspsps = getBanks(API_ORIGIN,base_headers)
    while True:
        chosenASP = printSelections(aspsps)
        session = authorization(API_ORIGIN,chosenASP,app,base_headers)
        transactions = getTransactions(API_ORIGIN,session, base_headers)
        printSummary(transactions)
        userInput = input('Type letter q to quite programme or any other letter to continue with another bank: ')
        if userInput=='q':
            print('Exit programme caused by user input.')
            break

