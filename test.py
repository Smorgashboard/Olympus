import json
import subprocess
from subprocess import Popen
import logging


#Start Logging
logging.basicConfig (filename="mercuryLog.txt", level=logging.DEBUG, format="%(asctime)s %(message)s")
aRecServFail = []

def lookForServFails():
    #massServFailProcess = subprocess.Popen(['massdns', '-r', '/home/kali/tools/dns/resolvers.txt', '-t', 'A', '-s', '15000', '-o', 'J', '-w', 'jsonMass', 'all'])
    grepcmd = 'cat jsonMass | grep "SERVFAIL" | tee -a servfail '
    combineCMD1Process = subprocess.run(grepcmd, shell = True)
    sfs =[]
    serverFails = open('servfail').read().splitlines()
    for serverfail in serverFails:
        print("printing serverfail in serverFails:")
        print(serverfail)
        sf = serverfail.split('"')[3]
        sf = sf[:-1]
        print(sf)
        sfs.append(sf)
    #print(sfs)


lookForServFails()