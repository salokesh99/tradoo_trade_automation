import logging
from kiteconnect import KiteConnect
from keys import *




logging.basicConfig(level=logging.DEBUG)

kite = KiteConnect(api_key=API_KEY)


session_token = kite.login_url()
print(session_token)
print('\n \n')



def connect_zerodha():
    global kite
    logging.basicConfig(level=logging.DEBUG)
    kite = KiteConnect(api_key=API_KEY)
    req_token= input('Pls enter the root token--- \n')
    data = kite.generate_session(req_token, api_secret=API_SECRET)
    kite.set_access_token(data["access_token"])
    profile = kite.profile()
    print(profile['user_name'], profile['email'])




def Get_all_stocks():
    instruments = kite.instruments()
    # print('instruments====',instruments)
    stocks_list = []
    count = 0
    # i=0
    print('Stocks Listed on NSE are ')
    for instrument in instruments :
        if instrument['exchange']=='NSE' and instrument['name'] != '':
            name = instrument['name']
            print(name)
            stocks_list.append(name)
            if name == 'NIFTY BANK':
                print('instrument data \n', instrument)
            # if count %20 == 0 :
            #     break
        count += 1
        # i+=1
        
    return stocks_list




if __name__=='__main__':
    connect_zerodha()
    stocks_list =  Get_all_stocks()

