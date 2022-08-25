import configparser
from subprocess import Popen, PIPE 
import subprocess
from crtsh import crtshAPI
import json
import logging
from configparser import ConfigParser
import psycopg2

logging.basicConfig (filename="noctualog.txt", level=logging.DEBUG, format="%(asctime)s %(message)s")

#Build Urls for crtsh api
urlsfromfile = open('wildcards').read().splitlines()

#Combine commands to end with one file for massdns probing
combineCMD1 = "cat assetfinder | anew all"
combineCMD2 = "cat subs | anew all"
combineCMD3 = "cat amassout | anew all"
combineCMD4 = "cat cershdomains | anew all"


#define functions for commands
def massAProcess():
    combineCMD5 = "cat massed | cut -d ' ' -f1 | awk '{print substr($0, 1, length($0)-1)}' | anew domains"
    print("Running MassDNS!")
    massAProcess = subprocess.Popen(['massdns', '-r', '/home/kali/tools/dns/resolvers.txt', '-t', 'A', '-s', '15000', '-o', 'S', '-w', 'massed', 'all'], stdout=PIPE, stderr=PIPE)
    stdout, stderr = massAProcess.communicate()
    subprocess.run(combineCMD5, shell= True)

def massCProcess():
    combineCnames = "cat masscnames | cut -d ' ' -f1 | awk '{print substr($0, 1, length($0)-1)}' | anew botdomains"
    print("Running MassDNS! Now with CNAMES!")
    massCProcess = subprocess.Popen(['massdns', '-r', '/home/kali/tools/dns/resolvers.txt', '-t', 'CNAME', '-s', '15000', '-o', 'S', '-w', 'masscnames', 'all'], stdout=PIPE, stderr=PIPE)
    stdout, stderr = massCProcess.communicate()
    subprocess.run(combineCnames, shell = True)

def subFinderProcess():
    #subfinderCMD = "subfinder -dL wildcards -o subs
    print("Running SubFinder: hold please...")
    subfinderProcess = subprocess.Popen(['subfinder', '-dL', 'wildcards', '-all', '-o', 'subs'], stdout=PIPE, stderr=PIPE)
    stdout, stderr = subfinderProcess.communicate()

def amassProcess():
    #amassCMD = "amass enum --passive -df ./wildcards | anew amass"
    print("Running Amass: This one takes a bit....")
    amassprocess = subprocess.Popen(['amass', 'enum', '--passive', '-df', 'wildcards', '-o', 'amassout'], stdout=PIPE, stderr=PIPE)
    stdout, stderr = amassprocess.communicate()

def assetfinderProcess():
    assetCMD = "cat wildcards | assetfinder --subs-only | anew assetfinder"
    print("Running AssetFinder: This one is faster")
    assetProcess = subprocess.run(assetCMD, shell = True, stdout=subprocess.DEVNULL)

#run commands
subFinderProcess()
amassProcess()
assetfinderProcess()

#amassProecss = subprocess.run(amassCMD, shell = True)
combineCMD1Process = subprocess.run(combineCMD1, shell = True)
combineCMD2Process = subprocess.run(combineCMD2, shell = True)
combineCMD3Process = subprocess.run(combineCMD3, shell = True)

domains = []

def crtshDATA(url):
    crtshResponse = json.dumps(crtshAPI().search(url))
    json_tree = json.loads(crtshResponse)
    #iterate through json and pull out name_value which should be the domain names covered by the SSL Cert... Should...
    for element in json_tree:
        # the reason this wasnt (but still isnt for some unknown reason) working is because its checking to see if element in json_tree is in domains not name_value
        # ignore the comment above we are now working 95% still getting 1-2 dupes but i dont think that matters
        if (element['name_value'] not in domains):
            domains.append(element['name_value'])
    # write domains from json to file called cershdomains
    with open('cershdomains', 'w') as f:
        for line in domains:   
            f.write(line + "\n" )

#fix this to accept wildcards - Done remove comment and replace with what is actually happening here
for i in urlsfromfile:
    print("Running crtSH for " + i)
    #call the function to actually do anything
    crtshDATA(i)
else:
    subprocess.run(combineCMD4, shell = True)

#probe here with massdns twice and using anew add the results to domains
for i in range(2):
    massAProcess()
    
#Probe for Mass Cnames
for i in range(2):
    massCProcess()

# here we call jsminerbot
# will check the domains file
# jsminerbot needs to send info to fetcherbot