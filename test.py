import logging
from configparser import ConfigParser
import psycopg2
import dns
import dns.resolver
import dns.rdatatype
import dns.rdata
import dns.rdtypes
import time
import concurrent.futures

dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8', '2001:4860:4860::8888', '8.8.4.4', '2001:4860:4860::8844']
badideaSQL= """SELECT * from ns_failures"""

threads = 60
sfs = []
nxds = []
naws = []
live = []
cnames = []
servfails = ['help.simpletax.ca','epicgames.com', 'google.com', 'amazon.com', 'sftp.cornershop.io']

logging.basicConfig (filename="plutolog.txt", level=logging.DEBUG, format="%(asctime)s %(message)s")
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

def update_SQL(cname):
    print("imma do something cool someday")

params = config()
logging.debug("Connecting to POSTGRES SQL ON AWS")
conn = psycopg2.connect(**params)
cur = conn.cursor()
logging.debug(conn.get_dsn_parameters())

cur.execute(badideaSQL)
servDict = cur.fetchall()
time.sleep(60)
print(servDict[1])


def q_dns(servfail):
    clean = str(servfail)
    cleanstr = replace(clean)
    try:
        result = dns.resolver.resolve(cleanstr, 'CNAME')
        rd = dns.rdatatype.to_text(result.rdtype)
        print(rd)
        for ipval in result:
            if ipval == None:
                logging.debug(result)
            else:
                if dns.rdatatype.to_text(result.rdtype) == 'CNAME':
                    cnames.append(cleanstr)
                else:
                    live.append(cleanstr)
    except dns.resolver.NoAnswer:
        naws.append(cleanstr)
        print("noanswer")
    except dns.resolver.NXDOMAIN:
        nxds.append(cleanstr)
        print("nxdomain")
    except dns.resolver.NoNameservers:
        sfs.append(cleanstr)
        print("something else")
    except:
        logging.debug(cleanstr)
        logging.debug("Timed Out")

