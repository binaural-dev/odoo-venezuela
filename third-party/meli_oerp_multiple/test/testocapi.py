
import requests
import json
import sys
import pprint
pp = pprint.PrettyPrinter(indent=4)

access_token = False
if len(sys.argv)<2:
    print("Need at least one argument, run like this: python3 testocapi.py https://www.mysite.com mercadolibre")

baseurl = sys.argv[1]
connector = sys.argv[2]
_url = baseurl+"/ocapi/"+connector

params = {
    'params': {
        'client_id': '123456',
        'secret_key': '456789'
    }
}
url = _url+"/auth"
print(url)
print(params)
#headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
r = requests.post(url=url, json=dict(params))
print(r.content)

rjson = r.json()
#print(rjson)
pp.pprint(rjson)

if "result" in rjson:
    result = rjson["result"][0]
    if "access_token" in result:
        access_token = result["access_token"]

if not access_token:
    exit(1)

#################################################################

params = {
    'params': {
        'access_token': access_token,
    }
}
url = _url+"/catalog"
print(url)
print(params)

r = requests.post(url=url, json=dict(params))
print(r.content)

rjson = r.json()
#print(rjson)
pp.pprint(rjson)

#################################################################

params = {
    'params': {
        'access_token': access_token,
    }
}
url = _url+"/pricestock"
print(url)
print(params)

r = requests.post(url=url, json=dict(params))
print(r.content)

rjson = r.json()
#print(rjson)
pp.pprint(rjson)

#################################################################

params = {
    'params': {
        'access_token': access_token,
    }
}
url = _url+"/pricelist"
print(url)
print(params)

r = requests.post(url=url, json=dict(params))
print(r.content)

rjson = r.json()
#print(rjson)
pp.pprint(rjson)

#################################################################

params = {
    'params': {
        'access_token': access_token,
    }
}
url = _url+"/stock"
print(url)
print(params)

r = requests.post(url=url, json=dict(params))
print(r.content)

rjson = r.json()
#print(rjson)
pp.pprint(rjson)

#################################################################
import json
data = []
with open('sale.json') as json_file:
    data = json.load(json_file)

pp.pprint(data)

params = {
    'params': {
        'access_token': access_token,
        'sales': [data],
    }
}
url = _url+"/sales"
print(url)
print(params)

r = requests.post(url=url, json=dict(params))
print(r.content)

rjson = r.json()
#print(rjson)
pp.pprint(rjson)
