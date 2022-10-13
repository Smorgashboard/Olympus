import requests
import re
import json
import concurrent.futures
import sys
import urllib3
import logging
from configparser import ConfigParser
import psycopg2
import time
from datetime import datetime
import fastly
from fastly.api import domain_api

configuration = fastly.Configuration()
configuration.api_token = 'uetVvm9u7WCfALxNEJQ3mlvmFSkenBrD'

#####Version 1.6 ###########

logging.basicConfig (filename="NeptuneLog.txt", level=logging.DEBUG, format="%(asctime)s %(message)s")

targets = []

def github_username_creation(url):
    strip_url = url[8:]
    username = strip_url.split(".")[0]
    return username

def strip_fastly(url):
    strip_url = url[8:]
    return strip_url

def replace(text):
    chars_to_replace = "(),'"
    for char in chars_to_replace:
        if char in text:
            text = text.replace(char, "")
    return text

def config(filename='database.ini', section='postgresql'):
    parser = ConfigParser()
    parser.read(filename)

    db ={}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]
    else:
        logging.debug("Ya done fucked something up with the connection.")
    return db

params = config()
logging.debug("Connecting to POSTGRES SQL ON AWS")
conn = psycopg2.connect(**params)
cur = conn.cursor()
logging.debug(conn.get_dsn_parameters())

startTime = time.time()
#turn off warnings because they are useless anyway
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

getcnameSQL = """SELECT target FROM cnames"""
insertFoundSQL = """INSERT INTO found_subs(program_name,program_id,url,alerted,target) VALUES(%s,%s,%s,%s,%s)"""
makeMyLifeEasierSQL = """SELECT url FROM cnames WHERE target=%s"""
makeMyLifeEasierSQL2 = """SELECT program_name FROM cnames WHERE target=%s"""
makeMyLifeEasierSQL3 = """SELECT program_id FROM cnames WHERE target=%s"""
alertedSQL = """SELECT alerted FROM found_subs WHERE target=%s"""
getMoreCnameSQL = """SELECT url FROM more_cnames """
cur.execute(getcnameSQL)
cnames = cur.fetchall()
time.sleep(30)

for cname in cnames:
    cnamestr = str(cname)
    cleanstrcname = replace(cnamestr)
    targets.append(cleanstrcname)

time.sleep(20)

cur.execute(getMoreCnameSQL)
cnames2 = cur.fetchall()
time.sleep(10)

for cname in cnames2:
    cnamestr = str(cname)
    cleanstrcname = replace(cnamestr)
    targets.append(cleanstrcname)

time.sleep(20)

#urlsfromfile = open('useme').read().splitlines()
urls = ['https://{}'.format(x) for x in targets[0:]]
# Specifiy the Text to search the responses for
patterns = ["There is no app configured at that hostname", "NoSuchBucket", "No Such Account", "You're Almost There", "a GitHub Pages site here", "There's nothing here", "project not found", "Your CNAME settings", "InvalidBucketName", "PermanentRedirect", "The specified bucket does not exist", "Repository not found", "Sorry, We Couldn't Find That Page", "The feed has not been found.", "The thing you were looking for is no longer here, or never was", "Please renew your subscription", "There isn't a Github Pages site here", "We could not find what you're looking for.", "No settings were found for this company:", "No such app", "is not a registered InCloud YouTrack", "Unrecognized domain", "project not found", "Web Site Not Found", "Sorry, this page is no longer available", "If this is your website and you've just created it, try refreshing in a minute", "Trying to access your account?", "Fastly error: unknown domain:", "404 Blog is not found", "Uh oh. That page doesn't exist.", "No Site For Domain", "It looks like you’re lost...", "It looks like you may have taken a wrong turn somewhere. Don't worry...it happens to all of us.", "Not Found - Request ID:", "Tunnel *.ngrok.io not found", "404 error unknown site!", "Sorry, couldn't find the status page", "Project doesnt exist... yet!", "Sorry, this shop is currently unavailable.", "Link does not exist", "This job board website is either expired or its domain name is invalid.", "Domain is not configured", "Whatever you were looking for doesn't currently exist at this address", "Non-hub domain, The URL you've accessed does not provide a hub.", "Looks Like This Domain Isn't Connected To A Website Yet!", "Do you want to register *.wordpress.com?", "Hello! Sorry, but the website you&rsquo;re looking for doesn&rsquo;t exist.", "This UserVoice subdomain is currently available!", "404 Web Site not found", "domain has not been configured", "Do you want to register" "Help Center Closed"]
#40 threads is stable on DO droplet (currently testing 100)
threads = 60
TIMEOUT = 6
failures = []
hits = []

def slack_send(i):
    url = "https://hooks.slack.com/services/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"
    title = (f"Possible Hit")
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

def success_slack(i, info):
    url = "https://hooks.slack.com/services/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"
    title = (f"Possible Hit")
    message = i + " You son of a bitch, I'm in." + info
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

def should_I_Alert(target):
    try:
        cur.execute(alertedSQL, (target,))
        alerted = cur.fetchone()
        time.sleep(2)
        if alerted is not None:
            if alerted[0] == True:
                print("already Alerted")
            else:
                slack_send(target)
                booly = True
                update_SQL(target, booly)
        else:
            slack_send(target)
            booly = True
            update_SQL(target, booly)
    except AttributeError:
        slack_send(target)
        booly = True
        update_SQL(target, booly)

def update_SQL(target, booly):
    cur.execute(makeMyLifeEasierSQL, (target,))
    turl = cur.fetchone()
    time.sleep(2)
    cur.execute(makeMyLifeEasierSQL2, (target,))
    programNAME = cur.fetchone()
    time.sleep(2)
    cur.execute(makeMyLifeEasierSQL3, (target,))
    programID = cur.fetchone()
    time.sleep(2)
    cur.execute(insertFoundSQL, (programNAME,programID,turl,booly,target))
    conn.commit()

#### HEY FUTURE JON this is important!!!!!!!!   URL to check_github and check_fastly and i assume future api calls is not URL in SQL but rather the column TARGET from cnames

def check_github(url):
    #dosomething awesome
    global TIMEOUT
    username = github_username_creation(url)
    github_request_url = f"https://api.github.com/users/{username}"
    super_secret_github_token = "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"
    api_call = requests.get(github_request_url, verify=False, timeout=TIMEOUT, headers={'Accept' : 'application/vnd.github+json', 'Authorization' : 'Bearer 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'})
    if(re.search("Not Found", api_call.text)):
        success_slack(url, username)
    else:
        logging.debug(f"{username} already exists")

def check_fastly(url):
    clean_url = strip_fastly(url)
    successful = "FastlyTakes"
    with fastly.ApiClient(configuration) as api_client:
        api_instance = domain_api.DomainApi(api_client)
        options = {
            'service_id': '4N9Euaa9URB5jruymfddbF',
            'version_id': 1,
            'name': 'www.example.com',
        }
        options['name'] = clean_url
    try:
        api_response = api_instance.create_domain(**options)
        success_slack(clean_url,successful)
    except fastly.ApiException as e:
        logging.debug("Exception when calling DomainApi->create_domain: %s\n" % e)

def httpTry(url, timeout):
    httpTime = True
    global hits
    global failures
    global patterns
    while(httpTime):
        try:
            protocolSwap = url.replace("https", "http")
            request = requests.get(protocolSwap, verify=False, timeout=timeout, allow_redirects=True)
            time.sleep(2)
            for pattern in patterns:
                if(re.search(pattern, request.text)):
                    if pattern == patterns[4] or pattern == patterns[16]:
                        check_github(url)
                    elif pattern == patterns[27]:
                        check_fastly(url)
                    else:
                        hits.append(url)
                        print(url)
        except (requests.exceptions.ConnectionError):
            failures.append(url)
            httpTime = False
        else:
            break

def load_url(url, timeout):
    print(url)
    global failures
    global hits
    #Conner named this variable
    peanutButterJellyTime = True
    global patterns
    try:
        request = requests.get(url, verify=False, timeout=timeout, allow_redirects=True)
        time.sleep(2)
        html = request.content
#Read the responses and if response text matches variable textToFind then alert slack webhook
        for pattern in patterns:
                if(re.search(pattern, request.text)):
                    if pattern == patterns[4] or pattern == patterns[16]:
                        check_github(url)
                    elif pattern == patterns[27]:
                        check_fastly(url)
                    else:
                        hits.append(url)
                        print(url)
#definately going to come back and fix these
    except (requests.exceptions.ConnectionError):
        httpTry(url, timeout)        
    except(requests.exceptions.ReadTimeout):
        while peanutButterJellyTime:
            try:
                request = requests.get(url, verify=False, timeout=20, allow_redirects=True)
                for pattern in patterns:
                    if(re.search(pattern, request.text)):
                        if pattern == patterns[4] or pattern == patterns[16]:
                            check_github(url)
                        elif pattern == patterns[27]:
                            check_fastly(url)
                        else:
                            hits.append(url)
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
#logging.debug("There were", + len(failures), "missed targets, and the script took ", str(executionTime))
#logging.debug("The script completed at", date_time)
logging.debug("Script Completed")
logging.debug(executionTime)

#Better Logging
with open("failures.txt", "w") as f:
    for item in failures:
        f.write("%s\n" % item)

for hit in hits:
    print(hit)
    #probs going to need to format that
    should_I_Alert(hit)
