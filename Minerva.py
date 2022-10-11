from configparser import ConfigParser
from genericpath import exists
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
from rfeed import *
from selenium.common.exceptions import NoSuchElementException
import psycopg2
from urllib.parse import unquote

logging.basicConfig (filename="minervalog.txt", level=logging.DEBUG, format="%(asctime)s %(message)s")

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

cheapoSQL = """INSERT INTO public.cheap_programs(program_id, program_name, program_url, burp_exists) VALUES(%s,%s,%s,%s);"""        
programSQL = """INSERT INTO public.programs(program_id, program_name, program_url, burp_exists) VALUES(%s,%s,%s,%s);"""
checkInScopeURLSQL = """SELECT plain_url FROM in_scope"""
checkOutOfScopeURLSQL = """SELECT plain_url FROM out_of_scope"""
getProgramIdSQL = """SELECT program_id FROM programs WHERE programs.program_name=%s"""
getCheapoProgramIdSQL = """SELECT program_id FROM programs WHERE programs.cheap_programs=%s"""

fireFoxOptions = Options()
fireFoxOptions.headless = True

driver = webdriver.Firefox(options=fireFoxOptions)
driver.get("https://hackerone.com/directory/programs?offers_bounties=true&order_direction=DESC&order_field=launched_at")
original_window = driver.current_window_handle
wait = WebDriverWait(driver, 10)
time.sleep(10)

programURLS = []
cheapos = []

def replace(text):
    chars_to_replace = "\*^$"
    for char in chars_to_replace:
        if char in text:
            text = text.replace(char, "")
    return text


#Step One scroll to the bottom
def ShawtyAreYouDown():
    moretoscroll = True
    while moretoscroll:
        if driver.find_elements(By.XPATH, '/html/body/div[2]/div/main/div[3]/div/div[2]/div/div[2]/div/div/p/a'):
            logging.debug("Found the bottom")
            moretoscroll = False
        else:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5)

#take the burp suite configuration file and pull out inscope and out of scope urls 
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
            excludedPlainURL = replace(excludedURLS)
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
            includedPlainURL = replace(includedURLS)
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
        
def gatherIntel(url, cur):
    time.sleep(15)
    programName = driver.find_element(By.XPATH, "/html/body/div[2]/div/main/div[1]/div[1]/div/div/div/div/div/div/div/div/div/div/div[1]/div/div[2]/div[1]/div/h1").get_attribute('innerText')
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
                    cur.execute(programSQL, (programID,programName,programURL,burpBoolean))
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
                    cur.execute(programSQL, (programID,programName,programURL, burpBOOLFALSE))
                    conn.commit()
                    lookingForIDNumber = False
                else:
                    id1 = random.randint(10000, 99999)

def gatherCheapIntel(url, cur):
    time.sleep(15)
    programName = driver.find_element(By.XPATH, "/html/body/div[2]/div/main/div[1]/div[1]/div/div/div/div/div/div/div/div/div/div/div[1]/div/div[2]/div[1]/div/h1").get_attribute('innerText')
    programURL = url
    logging.debug(programName)
    cur.execute('SELECT program_name FROM cheap_programs')
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
            cur.execute(getCheapoProgramIdSQL, (programName,))
            programID = cur.fetchone()
            burpJSON = unquote(burpFile.get_attribute("href"))
            evalJSON(burpJSON, programID, programName)
            logging.debug("program exists")
        else:
            #burp exists and program is not in SQL - This is for new programs
            #generate an random ID number and check it
            lookingForIDNumber = True
            burpBoolean = True
            id1 = randint(1000, 9999)
            cur.execute('SELECT program_id from cheap_programs')
            ids = cur.fetchall()
            while lookingForIDNumber: 
                if id1 not in ids:
                    #if random number isn't taken execute the SQL to update the programs table with info
                    programID = id1
                    cur.execute(cheapoSQL, (programID,programName,programURL,burpBoolean))
                    conn.commit()
                    lookingForIDNumber = False
                    #end our search for ids and call evalJSON to read the burp config and update in/out of scope tables
                    burpJSON = unquote(burpFile.get_attribute("href"))
                    evalJSON(burpJSON, programID, programName)
                else:
                    # random number was taken so restart the loop
                    id1 = random.randint(1000, 9999)
    #no burp config files
    else:
        if any(programName in x for x in exists):
            #program was already in SQL and theres no burp file so do nothing else.
            logging.debug("program exists")
        else:
            #program does not have burp file but it doesnt exist in SQL
            lookingForIDNumber = True
            burpBOOLFALSE = False
            id1 = randint(1000, 9999)
            cur.execute('SELECT program_id from cheap_programs')
            ids = cur.fetchall()
            while lookingForIDNumber: 
                if id1 not in ids:
                    programID = id1
                    # Add to SQL but dont call json evaluation
                    cur.execute(cheapoSQL, (programID,programName,programURL, burpBOOLFALSE))
                    conn.commit()
                    lookingForIDNumber = False
                else:
                    id1 = random.randint(1000, 9999)

def gatherAll():
    programs = driver.find_elements(By.CSS_SELECTOR, "html body.js-application.controller_directory.action_index._layout.signed-out div.js-application-root.full-size div.app_shell main.app_shell__content div.daisy-grid.daisy-grid--has-outside-gutter div.daisy-grid__row.daisy-grid__row--has-gutter div.daisy-grid__column div.card div div.infinite-scroll-component__outerdiv div.infinite-scroll-component table.daisy-table tbody.daisy-table-body tr.spec-directory-entry.daisy-table__row.fade.fade--show td.daisy-table__cell div.sc-bczRLJ.juxDLZ div.sc-bczRLJ.kuXVOq div.sc-bczRLJ.bjVIKL div span strong span a.daisy-link.routerlink.daisy-link--major.spec-profile-name")
    for p in programs:
        link = p.get_attribute("href")
        programURLS.append(link)

def cheapo():
    driver.get("https://hackerone.com/directory/programs?order_direction=DESC&order_field=laun")
    ShawtyAreYouDown()
    cheapoprograms = driver.find_elements(By.CSS_SELECTOR, "html body.js-application.controller_directory.action_index._layout.signed-out div.js-application-root.full-size div.app_shell main.app_shell__content div.daisy-grid.daisy-grid--has-outside-gutter div.daisy-grid__row.daisy-grid__row--has-gutter div.daisy-grid__column div.card div div.infinite-scroll-component__outerdiv div.infinite-scroll-component table.daisy-table tbody.daisy-table-body tr.spec-directory-entry.daisy-table__row.fade.fade--show td.daisy-table__cell div.sc-bczRLJ.juxDLZ div.sc-bczRLJ.kuXVOq div.sc-bczRLJ.bjVIKL div span strong span a.daisy-link.routerlink.daisy-link--major.spec-profile-name")
    for p in cheapoprograms:
        link = p.get_attribute("href")
        if any(link in x for x in programURLS):
            logging.debug(f"{link} ain't cheap")
        else:
            cheapos.append(link)
        
ShawtyAreYouDown()
gatherAll()
count = len(programURLS)
logging.debug(count)

for url in programURLS:
    driver.get(url)
    gatherIntel(url, cur)

cheapo()

for url in cheapos:
    driver.get(url)
    gatherCheapIntel(url, cur)