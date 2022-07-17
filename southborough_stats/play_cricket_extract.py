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
from openpyxl import Workbook
from selenium import webdriver
from selenium.webdriver.common.by import By


def results_worksheet_download(
    website_inputs: dict,
    webdriver_path,
    downloads_path,
):

    """

    Uses Selenium to log into the play-cricket website and download all of the matches between the dates selected.

    Args:
        website_inputs: Dictionary with following keys:
            email: Email login for Play-Cricket.com
            password: Password for Play-Cricket.com
            start_date: string of start date of fixture search "dd/mm/yyyy"
            end_date: string of end date of fixture search "dd/mm/yyyy"
        webdriver_path: path to chromedriver.exe
        downloads_path: path to Downloads folder (without / at end)


    """

    driver = webdriver.Chrome(webdriver_path)
    driver.get("https://southboroughcc.play-cricket.com/")

    cookie_accept_link = driver.find_element(by=By.XPATH,
                                             value='/html/body/div[7]/div/div/div/div[1]/div[2]/div/button',
    )
    cookie_accept_link.click()

    login_link = driver.find_element(by=By.XPATH,
                                     value="/html/body/div[2]/div/div[3]/ul/li[1]/a",
                                    )
    login_link.click()

    driver.implicitly_wait(10)
    
    email_link = driver.find_element(by=By.XPATH,
                                     value='/html/body/div[1]/div/div/div[3]/div[1]/div/div/form/div[1]/div/input',
                                    )
    email_link.send_keys(website_inputs["email"])
    
    pwd_link = driver.find_element(by=By.XPATH,
                                   value='/html/body/div[1]/div/div/div[3]/div[1]/div/div/form/div[2]/div/input',
                                  )

    pwd_link.click()
    
    time.sleep(5)
    
    pwd_link.send_keys(website_inputs["password"])
    
    time.sleep(5)
    
    link = driver.find_element_by_xpath('/html/body/div[1]/div/div/div[3]/div[1]/div/div/form/div[3]/button[1]')
    link.click()
    
    time.sleep(2)

    driver.get("https://southboroughcc.play-cricket.com/site_admin/results")

    driver.implicitly_wait(5)

    startdate_link = driver.find_element_by_xpath('//*[@id="q_match_date_gteq"]')
    startdate_link.clear()
    startdate_link.send_keys(website_inputs["start_date"])
    enddate_link = driver.find_element_by_xpath('//*[@id="q_match_date_lteq"]')
    enddate_link.clear()
    enddate_link.send_keys(website_inputs["end_date"])
    match_search_link = driver.find_element_by_xpath(
        '/html/body/div[5]/div[2]/div[4]/div[1]/div[3]/form/div[4]/div[2]/button/span[1]'
    )
    match_search_link.click()
    download_results_link = driver.find_element_by_xpath(
        '//*[@id="index_page"]/div[1]/div[2]/div/div/a'
    )
    download_results_link.click()

    ticker = 0
    while ticker < 60:
        time.sleep(1)
        ticker = ticker + 1
        if os.path.exists(downloads_path + "/download_results.xlsx"):
            driver.quit()
            break
    driver.quit()


def move_fixture_download(
    website_inputs: dict,
    downloads_path,
    storage_path,
):

    """
    
    Moves the downloaded results file from downloads folder to folder of your choice. Renames for future referenece. 

    Args:
        website_inputs: Dictionary with following keys:
            start_date: string of start date of fixture search "dd/mm/yyyy"
            end_date: string of end date of fixture search "dd/mm/yyyy"
        downloads_path: path to downloads folder (without / at end)
        storage_path: path to folder that want the results file moved to (without / at end)

    """

    start_date = website_inputs["start_date"].replace("/", "")
    end_date = website_inputs["end_date"].replace("/", "")
    name = "download_results_" + start_date + "_" + end_date + ".xlsx"
    shutil.move(
        downloads_path + "/download_results.xlsx",
        storage_path + "/download_results.xlsx",
    )
    
    results_path = storage_path + "/" + name
    os.rename(storage_path + "/download_results.xlsx", results_path)
    
    return results_path

    
def fixture_id_extract(results_path):
    
    """
    
    Returns a list of all Play-Cricket Fixture IDs of games in the results download provided.
    
    Args:
        results_path: path to the saved results download or openpyxl Workbook (for testing purposes)
    
    """
    
    if type(results_path) == Workbook:
        wb = results_path
        
    else:
        wb = openpyxl.load_workbook(results_path)
        
    fixture_id_column = [i.value for i in wb["Results"][1]].index("Fixture ID")
    return [str(i.value) for i in list(wb["Results"].columns)[fixture_id_column] if type(i.value)==int]