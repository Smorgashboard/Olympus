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

threads = 60
sfs = []
nxds = []
naws = []
live = []
cnames = []

getAllProgramsSQL = """SELECT program_id from programs"""
getAllCheapoProgramsSQL = """SELECT program_id FROM cheap_programs"""
getSQL = """SELECT servfail from ns_failures"""
moreCnamesSQL = """INSERT INTO more_cnames(url) VALUES(%s) ON CONFLICT (url) DO NOTHING;"""

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
    cur.execute(moreCnamesSQL, (cname,))
    conn.commit()

params = config()
logging.debug("Connecting to POSTGRES SQL ON AWS")
conn = psycopg2.connect(**params)
cur = conn.cursor()
logging.debug(conn.get_dsn_parameters())

cur.execute(getSQL)
servfails = cur.fetchall()
time.sleep(60)

cur.execute(getAllProgramsSQL)
programIDs = cur.fetchall()
time.sleep(10)

cur.execute(getAllCheapoProgramsSQL)
cheapoIDs = cur.fetchall()
time.sleep(10)

def q_dns_cname(servfail):
    clean = str(servfail)
    cleanstr = replace(clean)
    try:
        result = dns.resolver.resolve(cleanstr, 'CNAME')
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
    except dns.resolver.NXDOMAIN:
        nxds.append(cleanstr)
    except dns.resolver.NoNameservers:
        sfs.append(cleanstr)
    except:
        logging.debug(cleanstr)
        logging.debug("Timed Out")

def q_dns_A(servfail):
    clean = str(servfail)
    cleanstr = replace(clean)
    try:
        result = dns.resolver.resolve(cleanstr, 'A')
        for ipval in result:
            if ipval == None:
                logging.debug(result)
            else:
                if dns.rdatatype.to_text(result.rdtype) == 'A':
                    live.append(cleanstr)
                else:
                    live.append(cleanstr)
    except dns.resolver.NoAnswer:
        naws.append(cleanstr)
    except dns.resolver.NXDOMAIN:
        nxds.append(cleanstr)
    except dns.resolver.NoNameservers:
        sfs.append(cleanstr)
    except:
        logging.debug(cleanstr)
        logging.debug("Timed Out")

with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
    futures_to_url = (executor.submit(q_dns_cname, i) for i in servfails)
#iterate through formated urls and send a request
    for future in concurrent.futures.as_completed(futures_to_url):
        try:
            data = future.result()
        except Exception as exc:
            data = str(type(exc))
        continue      

time.sleep(10)

with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
    futures_dns_check2 = (executor.submit(q_dns_A, x) for x in naws)
    for future in concurrent.futures.as_completed(futures_dns_check2):
        try:
            data = future.result()
        except Exception as exc:
            data = str(type(exc))
        continue

for cname in cnames:
    update_SQL(cname)

cnamecoun = len(cnames)
print(cnamecoun)
livecoun = len(live)
print(livecoun)