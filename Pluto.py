import logging
from configparser import ConfigParser
import psycopg2
import dns
import dns.resolver
import time

sfs = []
nxds = []
naws = []
live = []

logging.basicConfig (filename="plutolog.txt", level=logging.DEBUG, format="%(asctime)s %(message)s")

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

getSQL = """SELECT servfail from ns_failures"""

cur.execute(getSQL)
servfails = cur.fetchall()
time.sleep(60)

for servfail in servfails:
    clean = str(servfail)
    cleanstr = replace(clean)
    try:
        result = dns.resolver.resolve(cleanstr, 'A')
        for ipval in result:
            if ipval == None:
                logging.debug(result)
            else:
                live.append(result)
    except dns.resolver.NoAnswer:
        naws.append(cleanstr)
    except dns.resolver.NXDOMAIN:
        nxds.append(cleanstr)
    except dns.resolver.NoNameservers:
        sfs.append(cleanstr)

with open("servfails", "a") as f:
    for sf in sfs:
        clean = str(sf)
        cleanstr = replace(clean)
        f.write(cleanstr)
        f.write("\n")
    f.truncate(f.tell()-1)

with open("nxdomains", "a") as n:
    for nxd in nxds:
        clean = str(nxd)
        cleanstr = replace(clean)
        n.write(cleanstr)
        n.write("\n")
    n.truncate(n.tell()-1)

with open("live", "a") as l:
    for x in live:
        clean = str(x)
        cleanstr = replace(clean)
        l.write(cleanstr)
        l.write("\n")
    l.truncate(l.tell()-1)

with open("noanswer", "a") as w:
    for naw in naws:
        clean = str(naw)
        cleanstr = replace(clean)
        w.write(cleanstr)
        w.write("\n")
    w.truncate(w.tell()-1)
    