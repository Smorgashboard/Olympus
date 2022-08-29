import json
import subprocess
from subprocess import Popen
import logging


#Start Logging
logging.basicConfig (filename="mercuryLog.txt", level=logging.DEBUG, format="%(asctime)s %(message)s")
aRecServFail = []

def lookForServFails():
    massServFailProcess = subprocess.Popen(['massdns', '-r', '/home/kali/tools/dns/resolvers.txt', '-t', 'A', '-s', '15000', '-o', 'J', '-w', 'jsonMass', 'all'])
    logging.debug("starting json")
    jsonMass = open('jsonMass').read().splitlines()
    logging.debug(jsonMass)
    jsondict = json.loads(jsonMass)
    for item in jsondict:
        if ['status'] == "SERVFAIL":
            aRecServFail.append(item)
    print(aRecServFail)

def loadJson():
    f = open('jsonMass')
    data = json.load(f)
    for item in data:
        #print(item)
        if ['status'] == "NOERROR":
            print(item)
            aRecServFail.append(item)
    print(aRecServFail)

loadJson()

#lookForServFails()