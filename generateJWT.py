import jwt,datetime,json

# Load the config file which contains the configuration parameters for this application
try:
    with open("config.json", "r") as f:
        config = json.load(f)
except:
    print('Exit programme caused by error in reading config file.')
    exit(0) 

if not config:
    print('Exit programme with no configuration')
    exit(0)    
#read the private key from the file which will be used for signing JWTs
with open(config['keyPath'], 'r') as file:
    private_key = file.read()

#geberate JWT token fo authorisation of the Tilisy API calls 
type = "JWT"
algorithm = "RS256"
id = config['applicationId']
iss = "enablebanking.com"
aud = "api.tilisy.com"
iat = datetime.datetime.now(datetime.timezone.utc)
exp = iat + datetime.timedelta(hours=23)
token = jwt.encode( {"iss":iss, "aud":aud,"iat":iat,"exp":exp}, private_key, algorithm="RS256",
headers={"kid": id,"typ":type,"alg":algorithm})

