import logging
from kiteconnect import KiteConnect
from keys import *
from tkinter import *

root = Tk()
root.geometry('750x680')



def connect_zerodha():
    logging.basicConfig(level=logging.DEBUG)
    kite = KiteConnect(api_key=API_KEY)
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




Button(root, text='CONNECT ZERODHA', command=popup).grid(row=0, column=0)
label=Label(root, text='')
label.grid(row=0,column=1)
root.mainloop()