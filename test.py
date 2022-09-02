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
import subprocess
from subprocess import PIPE
from datetime import datetime

sfs =[]

logging.basicConfig (filename="test.txt", level=logging.DEBUG, format="%(asctime)s %(message)s")
#####Version 1.5 ###########

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

getSQL = """SELECT servfail from nx_failures"""

cur.execute(getSQL)
servfails = cur.fetchall()
time.sleep(60)

for servfail in servfails:
    clean = str(servfail)
    cleanstr = replace(clean)
    sfs.append(cleanstr)
    
with open("search", "a") as f:
    for sf in sfs:
        clean = str(sf)
        cleanstr = replace(clean)
        f.write(cleanstr)
        f.write("\n")
    f.truncate(f.tell()-1)