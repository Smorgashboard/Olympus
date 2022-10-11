import logging
import psycopg2
from configparser import ConfigParser
import os
import time
import subprocess
import json
from subprocess import Popen, PIPE 

#Start Logging
logging.basicConfig (filename="hermeslog.txt", level=logging.DEBUG, format="%(asctime)s %(message)s")

#Combine commands to end with one file for massdns probing
combineCMD1 = "cat assetfinder | anew all"
combineCMD2 = "cat subs | anew all"
combineCMD3 = "cat amassout | anew all"

#SQL STATEMENTS
programSQL = """ SELECT program_name FROM cheap_programs """
programIDSQL = """SELECT program_id from cheap_programs WHERE program_name=%s"""
wildcardSQL = """SELECT plain_url FROM in_scope WHERE program_name=%s"""
cnameSQL = """INSERT INTO public.cnames(program_name, program_id, url, target) VALUES(%s,%s,%s,%s) ON CONFLICT (target) DO UPDATE SET (program_name, program_id, url, target) = (EXCLUDED.program_name, EXCLUDED.program_id, EXCLUDED.url, EXCLUDED.target);"""
nsfailsSQL = """INSERT INTO public.ns_failures(program_name, program_id, servfail) VALUES(%s,%s,%s) ON CONFLICT (servfail) DO UPDATE SET (program_name, program_id, servfail) = (EXCLUDED.program_name, EXCLUDED.program_id, EXCLUDED.servfail);"""
nxfailsSQL = """INSERT INTO public.nx_failures(program_name, program_id, servfail) VALUES(%s,%s,%s) ON CONFLICT (servfail) DO UPDATE SET (program_name, program_id, servfail) = (EXCLUDED.program_name, EXCLUDED.program_id, EXCLUDED.servfail);"""
reconSQL = """INSERT INTO public.recon(program_name, program_id, domain) VALUES(%s,%s,%s) ON CONFLICT (domain) DO UPDATE SET (program_name, program_id, domain) = (EXCLUDED.program_name, EXCLUDED.program_id, EXCLUDED.domain);"""
reconTheseSQL = """ SELECT program_name FROM cheap_programs WHERE burp_exists='true' """

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
    massServFailProcess = subprocess.Popen(['massdns', '-r', '/home/kali/tools/dns/resolvers.txt', '-t', 'A', '-s', '15000', '-o', 'J', '-w', 'jsonMass', 'all'])
    

def cnameParsing(programName, programID):
    time.sleep(20)
    cnamesfromfile = open('masscnames').read().splitlines()
    time.sleep(20)
    targets = []
    cnames = []
    for cname in cnamesfromfile:
        target = cname.split(" ")[2]
        url = cname.split(" ")[0]
        target = target[:-1]
        url = url[:-1]
        targets.append(target)
        cnames.append(url)
        cur.execute(cnameSQL, (programName, programID, url, target))
        conn.commit()     

def uploadRecon(program, program_id):
    r = open("all").read().splitlines()
    for x in r:
        cur.execute(reconSQL, (program, program_id, x))
        conn.commit()

def recon(program, program_id):
    try:  
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

        cnameParsing(program, program_id)
        time.sleep(20)
        uploadRecon(program, program_id)
        time.sleep(20)
        lookForServFails()
        time.sleep(20)
        grepcmd = 'cat jsonMass | grep "SERVFAIL" | anew servfail'
        combineCMD1Process = subprocess.run(grepcmd, shell = True)
        sfs =[]
        serverFails = open('servfail').read().splitlines()
        time.sleep(10)
        for serverfail in serverFails:
            sf = serverfail.split('"')[3]
            sf = sf[:-1]
            sfs.append(sf)   
            cur.execute(nsfailsSQL, (program, program_id, sf))
            conn.commit()
        time.sleep(10)
        grep2cmd = 'cat jsonMass | grep "NXDOMAIN" | anew nxdomains'
        cCMD = subprocess.run(grep2cmd, shell = True)
        nxds = []
        nxdomains = open('nxdomains').read().splitlines()
        time.sleep(10)
        for nxdomain in nxdomains:
            nx = nxdomain.split('"')[3]
            nx = nx[:-1]
            nxds.append(nx)   
            cur.execute(nxfailsSQL, (program, program_id, nx))
            conn.commit()

    except OSError:
            logging.debug("No wildcards file")

def replace(text):
    chars_to_replace = "\*^$(),'"
    for char in chars_to_replace:
        if char in text:
            text = text.replace(char, "")
    return text

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
    if os.path.exists("wildcards"):
        os.remove("wildcards")
    with open("wildcards", 'a') as f:
        try:
            for url in urls:
                urlswritten = urlswritten + 1
                strurl = str(url)
                useurl = replace(strurl)
                f.write(useurl + "\n")
            f.truncate(f.tell()-1)
        except OSError:
            logging.debug(useme)
            logging.debug("No urls")


cur.execute(reconTheseSQL)
programsToBeReconed = cur.fetchall()

for program in programsToBeReconed:
    cleanstr = str(program)
    useme = replace(cleanstr)
    os.chdir(homepath)
    os.chdir(useme)
    logging.debug(useme)
    logging.debug("running recon")
    cur.execute(programIDSQL,(program,))
    program_id = cur.fetchone()
    time.sleep(5)
    recon(useme, program_id)
    time.sleep(20)
    
        