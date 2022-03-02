
import datetime
import os
import re
import shutil
import sqlite3
import time

import bs4
import numpy as np
import openpyxl
import pandas as pd
import requests
import selenium

from dateutil.parser import parse
from selenium import webdriver

def results_worksheet_download(website_inputs: dict,
                               webdriver_path,
                               downloads_path
                              ):
    
    """
    
    Args:
        website_inputs: Dictionary with following keys:
            email_input: Email login for Play-Cricket.com
            pwd_input: Password for Play-Cricket.com
            start_date: string of start date of fixture search "dd/mm/yyyy"
            end_date: string of end date of fixture search "dd/mm/yyyy"
        webdriver_path: path to chromedriver.exe
        downloads_path: path to Downloads folder
            
    
    """
    
    driver = webdriver.Chrome(webdriver_path)
    driver.get('https://southboroughcc.play-cricket.com/')

    link = driver.find_element_by_xpath('//*[@id="cookieaccept"]/div/div/div/div/button')
    link.click()

    login_link = driver.find_element_by_xpath('/html/body/div[2]/div/div[3]/ul/li[1]/a')
    login_link.click()

    driver.implicitly_wait(10)

    email_link = driver.find_element_by_xpath('//*[@id="main"]/form/div[1]/input')
    email_link.send_keys(website_inputs["email_input"])

    pwd_link = driver.find_element_by_xpath('//*[@id="main"]/form/div[2]/input')
    pwd_link.send_keys(website_inputs["pwd_input"])

    link = driver.find_element_by_xpath('//*[@id="main"]/form/div[4]/input')
    link.click()

    driver.get('https://southboroughcc.play-cricket.com/site_admin/results')
    startdate_link = driver.find_element_by_xpath('//*[@id="q_match_date_gteq"]')
    startdate_link.clear()
    startdate_link.send_keys(website_inputs["start_date"])
    enddate_link = driver.find_element_by_xpath('//*[@id="q_match_date_lteq"]')
    enddate_link.clear()
    enddate_link.send_keys(website_inputs["end_date"])
    # generic_link = driver.find_element_by_xpath('"//body"')
    # generic_link.click()
    link = driver.find_element_by_xpath('//*[@id="match_search"]/div[3]/div[2]/button')
    link.click()
    link = driver.find_element_by_xpath('//*[@id="index_page"]/div[1]/div[2]/div/div/a')
    link.click()
    
    ticker = 0
    while ticker < 60:
        time.sleep(1)
        ticker = ticker + 1
        if os.path.exists(downloads_path + '/download_results.xlsx'):
            driver.quit()
            break
    driver.quit()