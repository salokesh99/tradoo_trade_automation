import logging
from kiteconnect import KiteConnect
from keys import *
from tkinter import *


kite = KiteConnect(api_key=API_KEY)
session_token = kite.login_url()
print(session_token)
print('\n \n')



root = Tk()
root.geometry('350x150')
root.configure(bg='red')



def connect_zerodha():
    global kite
    logging.basicConfig(level=logging.DEBUG)
    kite = KiteConnect(api_key=API_KEY)
    session_token = kite.login_url()
    print(session_token)
    print('\n \n')
    req_token=reqToken.get()
    top.destroy()
    data = kite.generate_session(req_token, api_secret=API_SECRET)
    kite.set_access_token(data["access_token"])

    profile = kite.profile()
    print(profile['user_name'], profile['email'])


def popup():
    global top, reqToken
    top=Toplevel(root)
    reqToken = Entry(top)
    reqToken.grid(row=0,column=0)
    Button(top, text='SUBMIT', command=connect_zerodha).grid(row=0,column=1)



def addStocks():
    instruments = kite.instruments()
    # print('instruments====',instruments)
    i=0
    for instrument in instruments :
        if instruments[i]['exchange']=='NSE' and instruments[i]['name']  != '' and  instruments[i]['instrument_type'] == 'EQ':
            print(instruments[i]['name'])

            stockList.insert(stockList.size(), instruments[i]['name'])
        i+=1

        


Button(root, text='CONNECT ZERODHA', command=popup).grid(row=0, column=0)
label=Label(root, text='', bg='white', fg='black')
label.pack(pady=20)
label.grid(row=0,column=1)

Button(root, text="ALL STOCKS", command=addStocks).grid(row=1,column=0)
stockList=Listbox(root, width=40)
stockList.grid(row=1,column=1)

root.mainloop()





