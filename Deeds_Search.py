# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.support.ui import WebDriverWait
import unittest, time, re
import sys
from dateutil.parser import parse
from datetime import datetime, date
import csv
import os.path
from threading import Thread
import thread

def log(logString):
    print str(datetime.now()) + ": " + str(logString)

def runner(pin,fileLock):
    selenium = SearchRecordOfDeedsPin()
    selenium.setUp()
    try:
        selenium.search_record_of_deeds_pin(pin,fileLock)
    finally:
        selenium.tearDown()


def test_search_all_pins():
    log("")

    fileLock = thread.allocate_lock()
    threads = []
    with open(SearchRecordOfDeedsPin.PINFILE) as f:
        for pin in f:
            # t = Thread(target=runner, args=(pin,fileLock))
            # t.start()
            # threads += [t]
            runner(pin,fileLock)
    for t in threads:
        t.join()

class SearchRecordOfDeedsPin():
    PINFILE = "pins.txt"

    def setUp(self):
        self.driver = webdriver.Chrome()
        self.driver.implicitly_wait(10)
        self.base_url = "http://162.217.184.82"
        self.verificationErrors = []
        self.accept_next_alert = True

        # self.pin = "07-08-101-026-1138".split("-")
    
    def search_record_of_deeds_pin(self, rawPin, fileLock):
        driver = self.driver
        driver.delete_all_cookies()
        driver.get(self.base_url + "/i2/default.aspx?AspxAutoDetectCookieSupport=1")
        pin = rawPin.split("-")
        log("Collecting data for PIN {}".format(rawPin))

        # Enter pin and search
        for i in range(5):
            elemName = "SearchFormEx1_PINTextBox" + str(i)
            driver.find_element_by_id(elemName).send_keys(pin[i])
        driver.find_element_by_id("SearchFormEx1_btnSearch").click()

        # Get all result rows
        searchResults = driver.find_elements_by_class_name("DataGridRow") + driver.find_elements_by_class_name("DataGridAlternatingRow")
        javascriptLinks = []

        # Iterate each row, and extract the necessary javascript to run to get each document's details
        for element in searchResults:
            docTypeChild = element.find_element_by_xpath('.//td[4]/a')
            docType = docTypeChild.text
            # For now, just grab MORTGAGEs and WARRENTY DEEDs
            if ("MORTGAGE" in docType) or ("WARRANTY DEED" in docType):
                attr = docTypeChild.get_attribute('href').replace('javascript:', '') + ';'
                docNumber = element.find_element_by_xpath('.//td[5]/a').text
                result = {}
                result['link'] = attr
                result['docNumber'] = docNumber
                result['docType'] = docType
                javascriptLinks.append(result)

        deeds = []
        # For each relevant row, extract the rest of the details
        for document in javascriptLinks:
            result = driver.execute_script(str(document['link']))
            self.waitForIdTextToMatch('DocDetails1_GridView_Details_ctl02_ctl00', document['docNumber'])
            newRecord = DeedRecord("-".join(pin), document['docNumber'], document['docType'])
            newRecord.executedDate = parse(self.getTextFromId('DocDetails1_GridView_Details_ctl02_ctl01', ''))
            newRecord.recordedDate = parse(self.getTextFromId('DocDetails1_GridView_Details_ctl02_ctl02', ''))
            newRecord.amount = self.getTextFromId('DocDetails1_GridView_Details_ctl02_ctl05', '')

            # Grantors and grantees take a little more finesse
            grantElement = driver.find_element_by_id('DocDetails1_GrantorGrantee_Table')
            numGrantors = grantElement.find_element_by_xpath('.//tbody/tr[1]/td/span').text
            numGrantees = grantElement.find_element_by_xpath('.//tbody/tr[3]/td/span').text
            for i in range(int(numGrantors[len(numGrantors)-1])):
                newRecord.grantors.append(self.getTextFromId('DocDetails1_GridView_Grantor_ctl0{}_ctl00'.format(str(2 + i)), ''))
            for i in range(int(numGrantees[len(numGrantees)-1])):
                newRecord.grantees.append(self.getTextFromId('DocDetails1_GridView_Grantee_ctl0{}_ctl00'.format(str(2 + i)), ''))
            deeds.append(newRecord)

        # Sort and save to a csv file
        deeds.sort(key=lambda x: x.executedDate)
        self.outputToCsv(deeds,fileLock)

    def getTextFromId(self, id, relativeXpath):
        parent = self.driver.find_element_by_id(id)
        if relativeXpath == "":
            return parent.text
        child = parent.find_element_by_xpath(relativeXpath)
        return child.text

    def waitForIdTextToMatch(self, id, text):
        for i in range(10):
            currentText = self.getTextFromId(id, '')
            if currentText == text:
                return;
            else:
                time.sleep(0.2)
        self.fail("Couldn't find doc number " + document['docNumber'] + " instead found " + docNumber)

    def waitForElement(self, name):
        for i in range(60):
            try:
                if self.is_element_present(By.ID, name): break
            except: pass
            time.sleep(1)
        else: self.fail("time out")
    
    def is_element_present(self, how, what):
        try: self.driver.find_element(by=how, value=what)
        except NoSuchElementException as e: return False
        return True
    
    def is_alert_present(self):
        try: self.driver.switch_to_alert()
        except NoAlertPresentException as e: return False
        return True
    
    def close_alert_and_get_its_text(self):
        try:
            alert = self.driver.switch_to_alert()
            alert_text = alert.text
            if self.accept_next_alert:
                alert.accept()
            else:
                alert.dismiss()
            return alert_text
        finally: self.accept_next_alert = True

    def outputToCsv(self, deeds, fileLock):
        with fileLock:
            file_existed = os.path.isfile('test.csv')
            with open('test.csv', 'a') as f:
                writer = csv.DictWriter(f, deeds[0].__dict__.keys())
                if not file_existed:
                    writer.writeheader()
                for deed in deeds:
                    writer.writerow(deed.__dict__)
    
    def tearDown(self):
        self.driver.quit()

class DeedRecord:
    def __init__(self, pin, documentNumber, documentType):
        self.mainPin = pin
        self.documentNumber = documentNumber
        self.documentType = documentType
        self.grantors = []
        self.grantees = []

    def __str__(self):
        return str(self.__dict__)
        # return "{} (#{}): type:{} executed:{} recorded:{} amount:{} grantors:{} grantees:{}".format(self.mainPin, self.documentNumber, self.documentType, self.executedDate, self.recordedDate, self.amount, str(self.grantees), str(self.grantors))

#SearchRecordOfDeedsPin.PIN = sys.argv.pop()
# suite = unittest.TestLoader().loadTestsFromTestCase(SearchRecordOfDeedsPin)
# unittest.TextTestRunner(verbosity=2).run(suite)
test_search_all_pins()
