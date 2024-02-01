from configparser import ConfigParser
import logging
import json
from random import randint, random
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
import time
from datetime import datetime
from rfeed import *
from selenium.common.exceptions import NoSuchElementException
import psycopg2
import subprocess
import requests
import re
import json
import concurrent.futures
import sys
import urllib3
from subprocess import PIPE
from urllib.parse import unquote
import os

#setup Logging file
logging.basicConfig (filename="jupiterlog.txt", level=logging.DEBUG, format="%(asctime)s %(message)s")

#turn off warnings because they are useless anyway
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#DB Connection
def config(filename='database.ini', section='postgresql'):
    parser = ConfigParser()
    parser.read(filename)

    db ={}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]
    else:
        logging.debug("Nope. Something is up with the connection.")
    return db

#Execute DB Connection
params = config()
logging.debug("Connecting to POSTGRES SQL ON AWS")
conn = psycopg2.connect(**params)
cur = conn.cursor()
logging.debug(conn.get_dsn_parameters())

#Firefox (Selenium) variables
fireFoxOptions = Options()
fireFoxOptions.headless = True

#Selenium connection
driver = webdriver.Firefox(options=fireFoxOptions)
driver.get("https://hackerone.com/directory/programs?offers_bounties=true&order_direction=DESC&order_field=launched_at")
original_window = driver.current_window_handle
wait = WebDriverWait(driver, 10)
time.sleep(10)

#SQL Variables
insertProgramSQL = """INSERT INTO public.programs(program_id, program_name, program_url, burp_exists) VALUES(%s,%s,%s,%s);"""
checkInScopeURLSQL = """SELECT plain_url FROM in_scope"""
checkOutOfScopeURLSQL = """SELECT plain_url FROM out_of_scope"""
getProgramIdSQL = """SELECT program_id FROM programs WHERE programs.program_name=%s"""
selectProgramSQL = """ SELECT program_name FROM programs """
wildcardSQL = """SELECT plain_url FROM in_scope WHERE program_name=%s"""
cnameSQL = """INSERT INTO public.cnames(program_name, program_id, url, target) VALUES(%s,%s,%s,%s);"""
nsfailsSQL = """INSERT INTO public.ns_failures(program_name, program_id, servfail) VALUES(%s,%s,%s);"""
getcnameSQL = """SELECT url FROM cnames"""
reconSQL = """INSERT INTO public.recon(program_name, program_id, domain) VALUES(%s,%s,%s)"""

#Combine commands to end with one file for massdns probing
combineCMD1 = "cat assetfinder | anew all"
combineCMD2 = "cat subs | anew all"
combineCMD3 = "cat amassout | anew all"

#Various Variables
programURLS = []
startTime = time.time()
textToFind = "There is no app configured at that hostname | NoSuchBucket | No Such Account | You're Almost There | a GitHub Pages site here | There's nothing here | project not found | Your CNAME settings | InvalidBucketName | PermanentRedirect | The specified bucket does not exist | Repository not found | Sorry, We Couldn't Find That Page | The feed has not been found. | The thing you were looking for is no longer here, or never was | Please renew your subscription | There isn't a Github Pages site here. | We could not find what you're looking for. | No settings were found for this company: | No such app | is not a registered InCloud YouTrack | Unrecognized domain | project not found | Web Site Not Found | Sorry, this page is no longer available | If this is your website and you've just created it, try refreshing in a minute | Trying to access your account? | Fastly error: unknown domain: | 404 Blog is not found | Uh oh. That page doesn't exist. | No Site For Domain | It looks like you’re lost... | It looks like you may have taken a wrong turn somewhere. Don't worry...it happens to all of us. | Not Found - Request ID: | Tunnel *.ngrok.io not found | 404 error unknown site! | Sorry, couldn't find the status page | Project doesnt exist... yet! | Sorry, this shop is currently unavailable. | Link does not exist | This job board website is either expired or its domain name is invalid. | Domain is not configured | Whatever you were looking for doesn't currently exist at this address | Non-hub domain, The URL you've accessed does not provide a hub. | Please renew your subscription | Looks Like This Domain Isn't Connected To A Website Yet! | Do you want to register *.wordpress.com? | Hello! Sorry, but the website you&rsquo;re looking for doesn&rsquo;t exist. | This UserVoice subdomain is currently available! | 404 Web Site not found | domain has not been configured | Do you want to register | Help Center Closed"
#Conner named this variable
peanutButterJellyTime = True
httpTime = True
#40 threads is stable on DO droplet (currently testing 100)
threads = 40
TIMEOUT = 6
failures = []

########   Function Declarations 

#Step One scroll to the bottom
def ShawtyAreYouDown():
    moretoscroll = True
    while moretoscroll:
        if driver.find_elements(By.XPATH, '/html/body/div[2]/div[4]/div/div[2]/div/div[2]/div/div/p/a'):
            moretoscroll = False
        else:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5)

#Replace text for better formating
def neptuneReplace(text):
    chars_to_replace = "(),'"
    for char in chars_to_replace:
        if char in text:
            text = text.replace(char, "")
    return text

def minervaReplace(text):
    chars_to_replace = "\*^$"
    for char in chars_to_replace:
        if char in text:
            text = text.replace(char, "")
    return text

def mercuryReplace(text):
    chars_to_replace = "\*^$(),'"
    for char in chars_to_replace:
        if char in text:
            text = text.replace(char, "")
    return text

#Slack Messaging function
def slack_send(i):
    url = ""
    title = (f"Possible Hit")
    #fix this to concatenate strings
    message = i
    slack_data = {
        "username": "SubBot",
        "icon_emoji": ":sub3:",
        "attachments": [
                {
                    "color": "#9733EE",
                    "fields": [
                        {
                            "title": title,
                            "value": message,
                            "short": "false",
                        }
                    ]
                }
            ]    
        }
    byte_length = str(sys.getsizeof(slack_data))
    headers = {'Content-Type': "application/json", 'Content-Length': byte_length}
    response = requests.post(url, data=json.dumps(slack_data), headers=headers)
    if response.status_code != 200:
        raise Exception(response.status_code, response.text)

#Take the burp suite configuration file and pull out inscope and out of scope urls 
def evalJSON(burpJSON, programID, programName):
    scope_dict = burpJSON[36:]
    data = json.loads(scope_dict)
    excludeSQL = "INSERT INTO public.out_of_scope(program_id, program_name, reg_url, plain_url) VALUES(%s,%s,%s,%s);"
    includeSQL = "INSERT INTO public.in_scope(program_id, program_name, reg_url, plain_url) VALUES(%s,%s,%s,%s);" 
    for item in data['target']['scope']['exclude']:
        #only pull out the https urls becuase pulling out http is causing duplicates. A better option here could be to execute another sql statement to see if the url exists and then determine if it should be pulled out. However the likelyhood that http urls are in scope and thier counterpart https are not is low.
        if item['protocol'] == "https":
            excludedURLS = item['host']
            # burpjson files contain the url in regex format. The following lines attempt to clean it up as best as possible
            dirty = True
            excludedPlainURL = minervaReplace(excludedURLS)
            while dirty:
                if excludedPlainURL[0] == "-" or excludedPlainURL[0] == "." or excludedPlainURL[0] == "*":
                   excludedPlainURL= excludedPlainURL[1:]
                else:
                    dirty = False
            #Send the id, name, regex url and non regex url to pgsql. Regex url will be used for creating a .scope file and non regex url is for wildcards.
            # add a line here to check to see if the url already exists.
            cur.execute(checkOutOfScopeURLSQL)
            excludedURLSInSQL = cur.fetchall()
            if any(excludedPlainURL in x for x in excludedURLSInSQL):
                logging.debug("URL ALREADY IN SQL")
            else:
                cur.execute(excludeSQL, (programID,programName,excludedURLS, excludedPlainURL))
                conn.commit()
                logging.debug(excludedPlainURL)
    #Repeat all above steps for included urls.
    for item in data ['target']['scope']['include']:
        if item['protocol'] == "https":
            includedURLS = item['host']
            dirty = True
            includedPlainURL = minervaReplace(includedURLS)
            while dirty:
                if includedPlainURL[0] == "-" or includedPlainURL[0] == "." or includedPlainURL[0] == "*":
                    includedPlainURL= includedPlainURL[1:]
                else:
                    dirty = False
            cur.execute(checkInScopeURLSQL)
            includedURLSInSQL = cur.fetchall()
            if any(includedPlainURL in x for x in includedURLSInSQL):
                logging.debug("URLS ALREADY IN SQL")
            else:
                cur.execute(includeSQL, (programID,programName,includedURLS, includedPlainURL))
                conn.commit()
                logging.debug(includedPlainURL) 

# Using Selenium drill down into the program and gather information about the actual bug bounty program
def gatherIntel(url, cur):
    time.sleep(15)
    programName = driver.find_element(By.XPATH, "/html/body/div[2]/div[2]/div[1]/div/div/div/div/div/div/div/div/div/div/div[1]/div/div[2]/div[1]/div/h1").get_attribute('innerText')
    programURL = url
    logging.debug(programName)
    cur.execute('SELECT program_name FROM programs')
    exists = cur.fetchall()
    tryagain = True
    try:
        burpFile = driver.find_element(By.XPATH,"//a[contains(text(), 'Download Burp Suite Project Configuration File')]")
    except NoSuchElementException:
        burpFile = None
    # This next section gets wonky. Probably can cleanup later. However step one is check for burp suite config file.
    #Burp file exists 
    if burpFile != None:
        if any(programName in x for x in exists):
            #burp exists and program already is in sql - this is where we would check for scope changes
            cur.execute(getProgramIdSQL, (programName,))
            programID = cur.fetchone()
            burpJSON = unquote(burpFile.get_attribute("href"))
            evalJSON(burpJSON, programID, programName)
            logging.debug("program exists")
        else:
            #burp exists and program is not in SQL - This is for new programs
            #generate an random ID number and check it
            lookingForIDNumber = True
            burpBoolean = True
            id1 = randint(10000, 99999)
            cur.execute('SELECT program_id from programs')
            ids = cur.fetchall()
            while lookingForIDNumber: 
                if id1 not in ids:
                    #if random number isn't taken execute the SQL to update the programs table with info
                    programID = id1
                    cur.execute(insertProgramSQL, (programID,programName,programURL,burpBoolean))
                    conn.commit()
                    lookingForIDNumber = False
                    #end our search for ids and call evalJSON to read the burp config and update in/out of scope tables
                    burpJSON = unquote(burpFile.get_attribute("href"))
                    evalJSON(burpJSON, programID, programName)
                else:
                    # random number was taken so restart the loop
                    id1 = random.randint(10000, 99999)
    #no burp config files
    else:
        if any(programName in x for x in exists):
            #program was already in SQL and theres no burp file so do nothing else.
            logging.debug("program exists")
        else:
            #program does not have burp file but it doesnt exist in SQL
            lookingForIDNumber = True
            burpBOOLFALSE = False
            id1 = randint(10000, 99999)
            cur.execute('SELECT program_id from programs')
            ids = cur.fetchall()
            while lookingForIDNumber: 
                if id1 not in ids:
                    programID = id1
                    # Add to SQL but dont call json evaluation
                    cur.execute(insertProgramSQL, (programID,programName,programURL, burpBOOLFALSE))
                    conn.commit()
                    lookingForIDNumber = False
                else:
                    id1 = random.randint(10000, 99999)

# For all the public bug bounty programs that exist that pay money, create a array to iterate through of their links.
def gatherAll():
    programs = driver.find_elements(By.CSS_SELECTOR, "html body.js-application.controller_directory.action_index._layout.signed-out div.js-application-root.full-size div.daisy-grid.daisy-grid--has-outside-gutter div.daisy-grid__row.daisy-grid__row--has-gutter div.daisy-grid__column div.card div div.infinite-scroll-component__outerdiv div.infinite-scroll-component table.daisy-table tbody.daisy-table-body tr.spec-directory-entry.daisy-table__row.fade.fade--show td.daisy-table__cell div.sc-gsnTZi.bKAToT div.sc-gsnTZi.iBoIkk div.sc-gsnTZi.jnnUyh div span strong span a.daisy-link.routerlink.daisy-link--major.spec-profile-name")
    for p in programs:
        link = p.get_attribute("href")
        programURLS.append(link)

#Neptune switching protocols
def httpTry(url, timeout):
    global httpTime
    global failures
    global textToFind
    while(httpTime):
        try:
            protocolSwap = url.replace("https", "http")
            request = requests.get(protocolSwap, verify=False, timeout=timeout)
            if(re.search(textToFind, request.text)):
                slack_send(protocolSwap)
                print(protocolSwap)
        except (requests.exceptions.ConnectionError):
            failures.append(url)
            httpTime = False
        else:
            break

#Request cname and read it
def load_url(url, timeout):
    global failures
    global peanutButterJellyTime
    global textToFind
    try:
        request = requests.get(url, verify=False, timeout=timeout)
        html = request.content
#Read the responses and if response text matches variable textToFind then alert slack webhook
        if(re.search(textToFind, request.text)):
            slack_send(url)
            print(url)
#definately going to come back and fix these
    except (requests.exceptions.ConnectionError):
        httpTry(url, timeout)        
    except(requests.exceptions.ReadTimeout):
        while peanutButterJellyTime:
            try:
                request = requests.get(url, verify=False, timeout=20)
                if(re.search(textToFind, request.text)):
                    slack_send(url)
                    print(url)
            except(requests.exceptions.ReadTimeout):
                failures.append(url)
                peanutButterJellyTime = False
            except(requests.exceptions.ConnectionError):
                httpTry(url, timeout=20)
                peanutButterJellyTime = False
            else:
                failures.append(url)
                break
    except Exception:
        failures.append(url)

##### Recon Functions

#MASSDNS A records function - running massdns for A recs in simple output  - combinecmd5 takes the live targets and dumps them into domains file
def massAProcess():
    combineCMD5 = "cat massed | cut -d ' ' -f1 | awk '{print substr($0, 1, length($0)-1)}' | anew domains"
    print("Running MassDNS!")
    massAProcess = subprocess.Popen(['massdns', '-r', '/home/kali/tools/dns/resolvers.txt', '-t', 'A', '-s', '15000', '-o', 'S', '-w', 'massed', 'all'], stdout=PIPE, stderr=PIPE)
    stdout, stderr = massAProcess.communicate()
    subprocess.run(combineCMD5, shell= True)

#MASSDNS Cname recs function - running massdns for CNAMES in simple - combineCnames dumps live targets into a file called botdomains
def massCProcess():
    combineCnames = "cat masscnames | cut -d ' ' -f3 | awk '{print substr($0, 1, length($0)-1)}' | anew botdomains"
    print("Running MassDNS! Now with CNAMES!")
    massCProcess = subprocess.Popen(['massdns', '-r', '/home/kali/tools/dns/resolvers.txt', '-t', 'CNAME', '-s', '15000', '-o', 'S', '-w', 'masscnames', 'all'], stdout=PIPE, stderr=PIPE)
    stdout, stderr = massCProcess.communicate()
    subprocess.run(combineCnames, shell = True)

#Run subfinder from wildcards
def subFinderProcess():
    #subfinderCMD = "subfinder -dL wildcards -o subs
    print("Running SubFinder: hold please...")
    subfinderProcess = subprocess.Popen(['subfinder', '-dL', 'wildcards', '-all', '-o', 'subs'], stdout=PIPE, stderr=PIPE)
    stdout, stderr = subfinderProcess.communicate()

#Run Amass from wildcards
def amassProcess():
    #amassCMD = "amass enum --passive -df ./wildcards | anew amass"
    print("Running Amass: This one takes a bit....")
    amassprocess = subprocess.Popen(['amass', 'enum', '--passive', '-df', 'wildcards', '-o', 'amassout'], stdout=PIPE, stderr=PIPE)
    stdout, stderr = amassprocess.communicate()

#Run AssetFinder from wildcards
def assetfinderProcess():
    assetCMD = "cat wildcards | assetfinder --subs-only | anew assetfinder"
    print("Running AssetFinder: This one is faster")
    assetProcess = subprocess.run(assetCMD, shell = True, stdout=subprocess.DEVNULL)

#This function is not complete - Running MASSDNS for server fails
def lookForServFails(program, program_id):
    #this is currently broken Do not use till fixed
    massServFailProcess = subprocess.Popen(['massdns', '-r', '/home/kali/tools/dns/resolvers.txt', '-t', 'A', '-s', '15000', '-o', 'J', '-w', 'jsonMass', 'all'])
    grepcmd = 'cat jsonMass | grep "SERVFAIL" | tee -a servfail '
    combineCMD1Process = subprocess.run(grepcmd, shell = True)
    sfs =[]
    serverFails = open('servfail').read().splitlines()
    for serverfail in serverFails:
        sf = serverfail.split('"')[3]
        sf = sf[:-1]
        sfs.append(sf)   
        cur.execute(nsfailsSQL, (program, program_id, sf))
        conn.commit()

def uploadRecon(program, program_id):
    r = open("all").read().splitlines()
    for x in r:
        cur.execute(reconSQL, (program, program_id, x))
        conn.commit()

#Function to call all recon functions 
def recon():
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

    except OSError:
            logging.debug("No wildcards file")

#Better SQLS for cnames
def cnameParsing(programID, programName):
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
        
#From Neptune
def getCnamesFromSQL():
    cur.execute(getcnameSQL)
    time.sleep(60)
    cnames = cur.fetchall()
    time.sleep(60)
    #make file called cnames with cnames listed 
    with open("cnames", "a") as f:
        for cname in cnames:
            cnamestr = str(cname)
            cleanstrcname = neptuneReplace(cnamestr)
            f.write(cleanstrcname)
            f.write("\n")
        f.truncate(f.tell()-1)

#use this function to check if a program exists or not in the sql
def checkIfExists():
    driver = webdriver.Firefox(options=fireFoxOptions)
    driver.get("https://hackerone.com/directory/programs?offers_bounties=true&order_direction=DESC&order_field=launched_at")
    original_window = driver.current_window_handle
    wait = WebDriverWait(driver, 10)
    time.sleep(10)
    ShawtyAreYouDown()
    programs = driver.find_elements(By.CSS_SELECTOR, "html body.js-application.controller_directory.action_index._layout.signed-out div.js-application-root.full-size div.daisy-grid.daisy-grid--has-outside-gutter div.daisy-grid__row.daisy-grid__row--has-gutter div.daisy-grid__column div.card div div.infinite-scroll-component__outerdiv div.infinite-scroll-component table.daisy-table tbody.daisy-table-body tr.spec-directory-entry.daisy-table__row.fade.fade--show td.daisy-table__cell div.sc-gsnTZi.bKAToT div.sc-gsnTZi.iBoIkk div.sc-gsnTZi.jnnUyh div span strong span a.daisy-link.routerlink.daisy-link--major.spec-profile-name")
    for p in programs:
        link = p.get_attribute("href")
        if any(p in x for x in programURLS):
            #do nothing
            runNeptunefromfile()
        else:
            programURLS.append(link)
            driver.get(link)
            gatherIntel(link)
    driver.close()
     
# Minerva Commands
def runMinerva():
    ShawtyAreYouDown()
    gatherAll()
    count = len(programURLS)
    logging.debug(count)

    for url in programURLS:
        driver.get(url)
        gatherIntel(url)
    time.sleep(60)
    driver.close()

# Mercury Commands
def runMercury():
    homepath = "/home/kali/pantheon/"
    cur.execute(selectProgramSQL)
    allPrograms = cur.fetchall()
    urlswritten = 0
    #Make all Directories in /home/kali/pantheon/
    for program in allPrograms:
        cleanstr = str(program)
        useme = mercuryReplace(cleanstr)
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
                    useurl = mercuryReplace(strurl)
                    f.write(useurl + "\n")
                f.truncate(f.tell()-1)
            except OSError:
                logging.debug("No urls")

    for program in allPrograms:
        cur.execute(getProgramIdSQL,(program,))
        program_id = cur.fetchone()
        cleanstr = str(program)
        useme = mercuryReplace(cleanstr)
        os.chdir(homepath)
        os.chdir(useme)
        recon()
        lookForServFails(program, program_id)
        cnameParsing(program, program_id)
        uploadRecon(program, program_id)
        masscnamesfromfile = open('botdomains').read().splitlines()
        time.sleep(20)
        runNeptune(masscnamesfromfile)

def runNeptune(masscnamesfromfile):
    # Urls for Neptunes to search
    urlsfromfile = masscnamesfromfile
    urls = ['https://{}'.format(x) for x in urlsfromfile[0:]]
    time.sleep(20)
    #Concurrent futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures_to_url = (executor.submit(load_url, i, TIMEOUT) for i in urls)
    #iterate through formated urls and send a request
        for future in concurrent.futures.as_completed(futures_to_url):
            try:
                data = future.result()
            except Exception as exc:
                data = str(type(exc))
            continue      

    #time
    now = datetime.now()
    date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
    executionTime = (time.time() - startTime)
    logging.debug("There were")
    logging.debug(len(failures))
    logging.debug("missed targets, and the script took ") 
    logging.debug(str(executionTime))
    logging.debug("The script completed at") 
    logging.debug(date_time)

    #Better Logging
    with open("failures.txt", "w") as f:
        for item in failures:
            f.write("%s\n" % item)

def runNeptunefromfile():
    # Urls for Neptunes to search
    getCnamesFromSQL()
    urlsfromfile = open('cnames').read().splitlines()
    urls = ['https://{}'.format(x) for x in urlsfromfile[0:]]
    #Concurrent futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures_to_url = (executor.submit(load_url, i, TIMEOUT) for i in urls)
    #iterate through formated urls and send a request
        for future in concurrent.futures.as_completed(futures_to_url):
            try:
                data = future.result()
            except Exception as exc:
                data = str(type(exc))
            continue      

    #time
    now = datetime.now()
    date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
    executionTime = (time.time() - startTime)
    logging.debug("There were")
    logging.debug(len(failures))
    logging.debug("missed targets, and the script took ") 
    logging.debug(str(executionTime))
    logging.debug("The script completed at") 
    logging.debug(date_time)

    #Better Logging
    with open("failures.txt", "w") as f:
        for item in failures:
            f.write("%s\n" % item)

##### NOW DO SOMETHING #####

#first iteration
runMinerva()
runMercury()
#continuing iterations

for i in 10000:
    checkIfExists()
    time.sleep(3600)
