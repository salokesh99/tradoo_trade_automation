from kiteconnect import KiteConnect
from keys import *

api_key = API_KEY
api_secret = API_SECRET

kite = KiteConnect(api_key=api_key)

def generate_tokens():
        try :
            # You need to generate a request token from the login URL and use it to get access token
            print(kite.login_url())  # Open this in browser to get request_token
            REQUEST_TOKEN = input("your_request_token - \n")
            # After redirect, exchange request_token for access_token:
            data = kite.generate_session(REQUEST_TOKEN, api_secret=api_secret)
            kite.set_access_token(data["access_token"])
            profile = kite.profile()
            print("Conncted to Kite Successfully!!!")
            print(profile['user_name'], profile['email'])
            return True
        except Exception as err :
            print("Unhandled Exception Occured", err)
            return False
            


if __name__=="__main__":
    token_generation = generate_tokens()
    if not token_generation :
         print("critical Error Exit!!!")
         exit()
        

    
         
     



