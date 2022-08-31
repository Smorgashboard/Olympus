from ssl import SSL_ERROR_EOF, SSLError
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


#####Version 1.5 ###########

logging.basicConfig (filename="NeptuneLog.txt", level=logging.DEBUG, format="%(asctime)s %(message)s")

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

getcnameSQL = """SELECT url FROM cnames"""
cur.execute(getcnameSQL)
cnames = cur.fetchall()

with open("domains", "a") as f:
    for cname in cnames:
        cnamestr = str(cname)
        cleanstrcname = replace(cnamestr)
        f.write(cleanstrcname)
        f.write("\n")
    f.truncate(f.tell()-1)

urlsfromfile = open('domains').read().splitlines()
urls = ['https://{}'.format(x) for x in urlsfromfile[0:]]
# Specifiy the Text to search the responses for
textToFind = "There is no app configured at that hostname | NoSuchBucket | No Such Account | You're Almost There | a GitHub Pages site here | There's nothing here | project not found | Your CNAME settings | InvalidBucketName | PermanentRedirect | The specified bucket does not exist | Repository not found | Sorry, We Couldn't Find That Page | The feed has not been found. | The thing you were looking for is no longer here, or never was | Please renew your subscription | There isn't a Github Pages site here. | We could not find what you're looking for. | No settings were found for this company: | No such app | is not a registered InCloud YouTrack | Unrecognized domain | project not found | Web Site Not Found | Sorry, this page is no longer available | If this is your website and you've just created it, try refreshing in a minute | Trying to access your account? | Fastly error: unknown domain: | 404 Blog is not found | Uh oh. That page doesn't exist. | No Site For Domain | It looks like you’re lost... | It looks like you may have taken a wrong turn somewhere. Don't worry...it happens to all of us. | Not Found - Request ID: | Tunnel *.ngrok.io not found | 404 error unknown site! | Sorry, couldn't find the status page | Project doesnt exist... yet! | Sorry, this shop is currently unavailable. | Link does not exist | This job board website is either expired or its domain name is invalid. | Domain is not configured | Whatever you were looking for doesn't currently exist at this address | Non-hub domain, The URL you've accessed does not provide a hub. | Please renew your subscription | Looks Like This Domain Isn't Connected To A Website Yet! | Do you want to register *.wordpress.com? | Hello! Sorry, but the website you&rsquo;re looking for doesn&rsquo;t exist. | This UserVoice subdomain is currently available! | 404 Web Site not found | domain has not been configured | Do you want to register | Help Center Closed"

#Conner named this variable
peanutButterJellyTime = True
httpTime = True
#40 threads is stable on DO droplet (currently testing 100)
threads = 40
TIMEOUT = 6
failures = []

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
logging.debug("There were", + len(failures), "missed targets, and the script took ", str(executionTime))
logging.debug("The script completed at", date_time)

#Better Logging
with open("failures.txt", "w") as f:
    for item in failures:
        f.write("%s\n" % item)
