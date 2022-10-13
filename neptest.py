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
TIMEOUT = 6

def check_github(url):
    #dosomething awesome
    global TIMEOUT
    username = github_username_creation(url)
    github_request_url = f"https://api.github.com/users/{username}"
    print(username)
    super_secret_github_token = "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"
    api_call = requests.get(github_request_url, verify=False, timeout=TIMEOUT, headers={'Accept' : 'application/vnd.github+json', 'Authorization' : 'Bearer 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'})
    print(api_call.text)
    if(re.search("Not Found", api_call.text)):
        print("Not found")
    else:
        logging.debug(f"{username} already exists")
    
check_github("https://styleguide.github.io/")