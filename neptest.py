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

#urlsfromfile = open('useme').read().splitlines()
urls = ['https://{}'.format(x) for x in targets[0:]]
# Specifiy the Text to search the responses for
patterns = ["There is no app configured at that hostname", "NoSuchBucket", "No Such Account", "You're Almost There", "a GitHub Pages site here", "There's nothing here", "project not found", "Your CNAME settings", "InvalidBucketName", "PermanentRedirect", "The specified bucket does not exist", "Repository not found", "Sorry, We Couldn't Find That Page", "The feed has not been found.", "The thing you were looking for is no longer here, or never was", "Please renew your subscription", "There isn't a Github Pages site here", "We could not find what you're looking for.", "No settings were found for this company:", "No such app", "is not a registered InCloud YouTrack", "Unrecognized domain", "project not found", "Web Site Not Found", "Sorry, this page is no longer available", "If this is your website and you've just created it, try refreshing in a minute", "Trying to access your account?", "Fastly error: unknown domain:", "404 Blog is not found", "Uh oh. That page doesn't exist.", "No Site For Domain", "It looks like you’re lost...", "It looks like you may have taken a wrong turn somewhere. Don't worry...it happens to all of us.", "Not Found - Request ID:", "Tunnel *.ngrok.io not found", "404 error unknown site!", "Sorry, couldn't find the status page", "Project doesnt exist... yet!", "Sorry, this shop is currently unavailable.", "Link does not exist", "This job board website is either expired or its domain name is invalid.", "Domain is not configured", "Whatever you were looking for doesn't currently exist at this address", "Non-hub domain, The URL you've accessed does not provide a hub.", "Looks Like This Domain Isn't Connected To A Website Yet!", "Do you want to register *.wordpress.com?", "Hello! Sorry, but the website you&rsquo;re looking for doesn&rsquo;t exist.", "This UserVoice subdomain is currently available!", "404 Web Site not found", "domain has not been configured", "Do you want to register" "Help Center Closed"]
#40 threads is stable on DO droplet (currently testing 100)
threads = 60
TIMEOUT = 6
failures = []
hits = []

def slack_send(i, pattern):
    url = "https://hooks.slack.com/services/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"
    title = (f"Possible Hit")
    message = i + " " + pattern
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

def success_slack(i):
    url = "https://hooks.slack.com/services/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"
    title = (f"Possible Hit")
    message = i + " You son of a bitch, I'm in." 
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
    
def check_fastly(url):
    with fastly.ApiClient(configuration) as api_client:
        api_instance = domain_api.DomainApi(api_client)
        options = {
            'service_id': '4N9Euaa9URB5jruymfddbF',
            'version_id': 1,
            'name': 'www.example.com',
        }
        options['name'] = url
    try:
        api_response = api_instance.create_domain(**options)
        success_slack(url)
    except fastly.ApiException as e:
        slack_send(url, "r")
        print("Exception when calling DomainApi->create_domain: %s\n" % e)


testurl = "reddit.com"
testurl2 = "smorgashboard.com"
check_fastly(testurl)
check_fastly(testurl2)