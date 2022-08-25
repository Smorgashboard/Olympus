#retrieve data from SQL and then create local files and call reconbot... hopefully
import logging
import psycopg2
from configparser import ConfigParser
import os

logging.basicConfig (filename="mercuryLog.txt", level=logging.DEBUG, format="%(asctime)s %(message)s")

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

programSQL = """ SELECT program_name FROM programs """
wildcardSQL = """SELECT plain_url FROM in_scope WHERE program_name=%s"""

homepath = "/Users/hackintosh/pantheon/"

def replace(text):
    chars_to_replace = "\*^$(),'"
    for char in chars_to_replace:
        if char in text:
            text = text.replace(char, "")
    return text

cur.execute(programSQL)
allPrograms = cur.fetchall()
urlswritten = 0

for program in allPrograms:
    cleanstr = str(program)
    useme = replace(cleanstr)
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
                useurl = replace(strurl)
                f.write(useurl + "\n")
            f.truncate(f.tell()-1)
        except OSError:
            logging.debug("No urls")

for program in allPrograms:
    cleanstr = str(program)
    useme = replace(cleanstr)
    os.chdir(homepath)
    os.chdir(useme)
    import Noctua