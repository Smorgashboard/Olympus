import logging
import psycopg2
from configparser import ConfigParser
import os
import time
import subprocess
import json
from crtsh import crtshAPI
from subprocess import Popen, PIPE 

#Start Logging
logging.basicConfig (filename="mercuryLog.txt", level=logging.DEBUG, format="%(asctime)s %(message)s")

#Combine commands to end with one file for massdns probing
combineCMD1 = "cat assetfinder | anew all"
combineCMD2 = "cat subs | anew all"
combineCMD3 = "cat amassout | anew all"
combineCMD4 = "cat cershdomains | anew all"

#SQL STATEMENTS
programSQL = """ SELECT program_name FROM programs """
programIDSQL = """SELECT program_id from programs WHERE program_name=%s"""
wildcardSQL = """SELECT plain_url FROM in_scope WHERE program_name=%s"""
cnameSQL = """INSERT INTO public.cnames(program_name, program_id, url) VALUES(%s,%s,%s);"""

#various Variables
homepath = "/home/kali/pantheon/"
domains = []

# SQL DB Connection
def config(filename='database.ini', section='postgresql'):
    parser = ConfigParser()
    parser.read(filename)

    db ={}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]
    else:
        logging.debug("Ya done mucked something up with the connection.")
    return db

params = config()
logging.debug("Connecting to POSTGRES SQL ON AWS")
conn = psycopg2.connect(**params)
cur = conn.cursor()
logging.debug(conn.get_dsn_parameters())

#Functions
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

def lookForServFails():
    #this is currently broken Do not use till fixed
    aRecServFail = []
    massServFailProcess = subprocess.Popen(['massdns', '-r', '/home/kali/tools/dns/resolvers.txt', '-t', 'A', '-s', '15000', '-o', 'J', '-w', 'jsonMass', 'all'])
    jsonMass = open('jsonMass').read.splitlines()
    jsondict = json.loads(jsonMass)
    for item in jsondict:
        if['status'] == "SERVFAIL":
            aRecServFail.append(item)

        

def recon():
    try:
        urlsfromfile = open('wildcards').read().splitlines()     
        for i in urlsfromfile:
            print("Running crtSH for " + i)
            #call the function to actually do anything
            crtshDATA(i)
        else:
            subprocess.run(combineCMD4, shell = True)
        subFinderProcess()
        amassProcess()
        assetfinderProcess()

        #amassProecss = subprocess.run(amassCMD, shell = True)
        combineCMD1Process = subprocess.run(combineCMD1, shell = True)
        combineCMD2Process = subprocess.run(combineCMD2, shell = True)
        combineCMD3Process = subprocess.run(combineCMD3, shell = True)

        for i in range(2):
            massAProcess()

        for i in range(2):
            massCProcess()
    except OSError:
            logging.debug("No wildcards file")

def replace(text):
    chars_to_replace = "\*^$(),'"
    for char in chars_to_replace:
        if char in text:
            text = text.replace(char, "")
    return text

def crtshDATA(url):
    try:
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
    except TypeError:
        logging.debug("There was a Type Error!")


#Retrieve All Programs from SQL
cur.execute(programSQL)
allPrograms = cur.fetchall()
urlswritten = 0

#Make all Directories in /home/kali/pantheon/
for program in allPrograms:
    cleanstr = str(program)
    useme = replace(cleanstr)
    os.chdir(homepath)
    if not os.path.exists(useme):
        os.makedirs(useme)
    cur.execute(wildcardSQL, (useme,))
    urls = cur.fetchall()
    os.chdir(useme)
    with open("wildcards", 'a') as f:
        try:
            for url in urls:
                urlswritten = urlswritten + 1
                strurl = str(url)
                useurl = replace(strurl)
                f.write(useurl + "\n")
            f.truncate(f.tell()-1)
        except OSError:
            logging.debug("No urls")

for program in allPrograms:
    cur.execute(programIDSQL,(program,))
    program_id = cur.fetchone()
    cleanstr = str(program)
    useme = replace(cleanstr)
    os.chdir(homepath)
    os.chdir(useme)
    recon()
    masscnamesfromfile = open('botdomains').read().splitlines()
    time.sleep(60)
    #update CNAME table with found cnames
    for cname in masscnamesfromfile:
        program = program
        program_id = program_id
        cur.execute(cnameSQL, (program, program_id, cname))
        conn.commit()
    time.sleep(60)