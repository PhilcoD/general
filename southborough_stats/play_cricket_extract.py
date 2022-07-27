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


def find_innings_id(string):
    """
    Finds the innings id for the game (up to two IDs)
    Args:
        string: requests.models.request.text, i.e. the output from requests(website) with .text to make it a string
    Outputs:
        inns_id: list of up to two innings IDs (strings)
    """
    
    sub = "innings"
    counter = 0
    inns_id = []
    
    while counter < len(string):
        if len(inns_id) == 2:
            break        
        if string.find(sub,counter) == -1:
            break
        begin = string.find(sub,counter)
        end = string.find('\"',begin)
        if "-" not in string[begin + len(sub):end] and string[begin + len(sub):end] not in inns_id:
            inns_id.append(string[begin + len(sub):end])
        counter = string.find(sub,counter) + len(sub)
    
    return inns_id 


def gamepoints_extract(soup4, match_figures_dict, error_msg):
    for i in range(1,3):
        gamepoints_table = soup4.select("#multiCollapseExample" + str(i) + " > table")

        if len(gamepoints_table) != 0:
            pd_gamepoints_table = pd.read_html(str(gamepoints_table[0]))[0]

            if len(pd_gamepoints_table) != 6:       
                error_msg.append("Length of game points table is neither 0 or 6. Expecting game, penalty, batting, bowling, match offical and total as the categories")

            if i == 1:
                match_figures_dict["home_game_points"] = pd_gamepoints_table[1][0]
                match_figures_dict["home_penalty_points"] = pd_gamepoints_table[1][1]
                match_figures_dict["home_batting_points"] = pd_gamepoints_table[1][2]
                match_figures_dict["home_bowling_points"] = pd_gamepoints_table[1][3]
                match_figures_dict["home_match_official_points"] = pd_gamepoints_table[1][4]
                match_figures_dict["home_total_points"] = pd_gamepoints_table[1][5]

            else:
                match_figures_dict["away_game_points"] = pd_gamepoints_table[1][0]
                match_figures_dict["away_penalty_points"] = pd_gamepoints_table[1][1]
                match_figures_dict["away_batting_points"] = pd_gamepoints_table[1][2]
                match_figures_dict["away_bowling_points"] = pd_gamepoints_table[1][3]
                match_figures_dict["away_match_official_points"] = pd_gamepoints_table[1][4]
                match_figures_dict["away_total_points"] = pd_gamepoints_table[1][5]
    
    return match_figures_dict, error_msg


def league_extract(soup4, match_figures_dict, error_msg):
    
    league_data = [""]*2
    
    divisioninfo = soup4.select(
        "body > div.breadcrumb-league-wrapper > div.container.breadcrumb-league > div > div.col-sm-12.col-md-6.col-lg-6.text-center.text-lg-left.leaguedetail-left"
    )
    
    if "friendly" in str(divisioninfo[0]).lower():
        league_data = ["Friendly", "Friendly"]
    
    elif divisioninfo[0].find_all("span")[0].contents[0].strip() == "":
        league_data = [
            divisioninfo[0].find_all("span")[2].contents[0].strip()
        ] * 2
    
    elif len(divisioninfo[0].find_all("span")[2]) == 1:
        league_data[0] = divisioninfo[0].find_all("span")[0].contents[0].strip()
        league_data[1] = divisioninfo[0].find_all("span")[2].contents[0].strip()
        
    elif "https" in str(divisioninfo[0].find_all("span")[2].contents[1]).lower():
        league_data[0] = divisioninfo[0].find_all("span")[0].contents[0].strip()
        start = str(divisioninfo[0].find_all("span")[2].contents[1]).find(">") + 1
        end = str(divisioninfo[0].find_all("span")[2].contents[1]).find(
            "<", str(divisioninfo[0].find_all("span")[2].contents[1]).find(">")
        )
        league_data[1] = str(divisioninfo[0].find_all("span")[2].contents[1])[
            start:end
        ]
        
    match_figures_dict["league"] = league_data[0]
    match_figures_dict["division"] = league_data[1]
    
    return match_figures_dict, error_msg


def date_ground_extract(soup4, match_figures_dict, error_msg):
    
    date_ground_data = [""]*2
    
    date_ground = soup4.select(
        "body > div.breadcrumb-league-wrapper > div.container.breadcrumb-league > div > div.col-sm-12.col-md-6.col-lg-6.text-lg-right.leaguedetail-right"
    )
    date = parse(re.search("\d*? \w* \d{4}", date_ground[0].text)[0])
    ground = date_ground[0].find_all("a")[0].contents[0]
    
    if "\n" not in ground:
        date_ground_data[0] = ground
    
    date_ground_data[1] = date.date()
    
    match_figures_dict["ground"] = date_ground_data[0]
    match_figures_dict["date"] = date_ground_data[1]
    
    return match_figures_dict, error_msg


def fixture_details_extract(soup4, match_figures_dict, error_msg):
    
    fixture_details = soup4.select(
        "body > div.container.main-header.main-header-lg.d-none.d-lg-block > table")
    
    home_away = ["home", "away"]
    
    for i in range(2):
        
        which_team = home_away[i]
        
        clubname = fixture_details[0].find_all("p", class_="team-name")[i].contents[0]
        clubteam_first = str(
            fixture_details[0]
            .find_all("p", class_="team-info-2")[i]
            .find_all(class_="team-info-1")[0]
        ).find("\n")
        clubteam_second = str(
            fixture_details[0]
            .find_all("p", class_="team-info-2")[i]
            .find_all(class_="team-info-1")[0]
        ).find("\n", clubteam_first + 1)
        clubteam = str(
            fixture_details[0]
            .find_all("p", class_="team-info-2")[i]
            .find_all(class_="team-info-1")[0]
        )[clubteam_first + 1 : clubteam_second].strip()
        
        
        battingscore_first = str(fixture_details[0].find_all("p", class_="team-info-2")[i]).find("</span>\n")
        battingscore_second = str(fixture_details[0].find_all("p", class_="team-info-2")[i]).find(
            "<", battingscore_first + 1
        )
        battingscore = str(fixture_details[0].find_all("p", class_="team-info-2")[i])[
            battingscore_first + len("</span>\n") : battingscore_second
        ].strip()
        
        if (
            len(
               fixture_details[0]
                .find_all("p", class_="team-info-2")[i]
                .find_all(class_="smalltxt")
            )
            == 0
        ):
            wickets = ""
            overs = ""
            
        else:
            # Teams_data[4 + i], Teams_data[6 + i] = "", ""
            wickets_overs_details = (
                fixture_details[0]
                .find_all("p", class_="team-info-2")[i]
                .find_all(class_="smalltxt")[0]
                .contents[0]
            )
            wickets_first = wickets_overs_details.find("/")
            wickets_second = wickets_overs_details.find("(", wickets_first + 1)
            overs_third = wickets_overs_details.find(")", wickets_second + 1)
            wickets = wickets_overs_details[wickets_first + 1 : wickets_second].strip()
            if "All out" in wickets:
                wickets = 10
                
            overs = wickets_overs_details[wickets_second + 1 : overs_third].strip()
            if len(overs) > 0:
                overs = float(overs)
        
        match_figures_dict[which_team + "_team"] = clubname + " " + clubteam
        
        if battingscore != "":
            match_figures_dict[which_team + "_batting_score"] = battingscore

        if wickets != "":
            match_figures_dict[which_team + "_wickets"] = wickets

        if overs != "":
            match_figures_dict[which_team + "_overs"] = overs
            
    if "ABANDONED" in str(fixture_details[0]):
        match_figures_dict["match_winner"] = "None"
        match_figures_dict["result_other"] = "Abandoned"

    elif "CONCEDED" in str(fixture_details[0]):
        team_conceded = (
            fixture_details[0]
            .find_all("p", class_="match-ttl win-cb-name")[0]
            .contents[0]
            .strip()
        )
        if team_conceded in match_figures_dict["home_team"].upper():
            match_figures_dict["match_winner"] = match_figures_dict["away_team"]
        else:
            match_figures_dict["match_winner"] = match_figures_dict["home_team"]
        match_figures_dict["result_other"] = "Conceded"
        
    elif len(fixture_details[0].find_all("p", class_="match-ttl win-cb-name")) == 0:
        match_figures_dict["match_winner"] = "None"
        match_figures_dict["result_other"] = "Cancelled"
        
    else:
        match_winner = (
            fixture_details[0]
            .find_all("p", class_="match-ttl win-cb-name")[0]
            .contents[0]
            .strip()
        )
        win_details_first = str(fixture_details[0].find_all("div", class_="info mdont")[0].contents[1]).find(
            "<span>"
        )
        win_details_second = str(fixture_details[0].find_all("div", class_="info mdont")[0].contents[1]).find(
            "<", win_details_first + 1
        )
        win_type = str(fixture_details[0].find_all("div", class_="info mdont")[0].contents[1])[
            win_details_first + len("<span>") : win_details_second
        ]
        by_how_much = "".join(
            filter(
                str.isdigit,
                str(fixture_details[0].find_all("div", class_="info mdont")[0].contents[0]),
            )
        )

        if match_winner in match_figures_dict["home_team"].upper():
            match_figures_dict["match_winner"] = match_figures_dict["home_team"]
        else:
            match_figures_dict["match_winner"] = match_figures_dict["away_team"]
        if win_type == "RUNS":
            match_figures_dict["win_by_runs"] = int(by_how_much)
        if win_type == "WICKETS":
            match_figures_dict["win_by_wickets"] = int(by_how_much)
            
    if len(fixture_details[0].find_all("p", class_="team-info-3")) != 0:
        for i in range(2):
            if len(fixture_details[0].find_all("p", class_="team-info-3")[i].contents) != 0:
                match_figures_dict["toss_winner"] = match_figures_dict[home_away[i] + "_team"]
                if "bat" in fixture_details[0].find_all("p", class_="team-info-3")[i].contents[0]:
                    match_figures_dict["toss_decision"] = "Bat"
                else:
                    match_figures_dict["toss_decision"] = "Field"

    elif len(fixture_details[0].find_all("p", class_="team-info-3 adma")) != 0:
        for i in range(2):
            if len(fixture_details[0].find_all("p", class_="team-info-3 adma")[i].contents) != 0:
                match_figures_dict["toss_winner"] = match_figures_dict[home_away[i] + "_team"]
                if "bat" in fixture_details[0].find_all("p", class_="team-info-3 adma")[i].contents[0]:
                    match_figures_dict["toss_decision"] = "Bat"
                else:
                    match_figures_dict["toss_decision"] = "Field"
    if match_figures_dict["toss_winner"] == "" and  match_figures_dict["toss_decision"] == "":
        match_figures_dict["toss_winner"], match_figures_dict["toss_decision"] = "No toss", "No toss"
            
    return match_figures_dict, error_msg


def match_reference(match_reference_dict, match_figures_dict, error_msg):
    southborough_teams = {
        "Southborough CC 1st XI": "1ST",
        "Southborough CC 2nd XI": "2ND",
        "Southborough CC Sunday XI": "SUN",
        "Southborough CC Under 13": "13A",
        "Southborough CC Under 13 B": "13B",
        "Southborough CC Under 11": "11A",
        "Southborough CC Under 21": "21A",
        "Southborough CC Under 15": "15A",
        "Southborough CC Midweek XI": "MID",
    }
    
    if match_figures_dict["home_team"] in list(southborough_teams.keys()):
        team_reference = southborough_teams[match_figures_dict["home_team"]]
    elif match_figures_dict["away_team"] in list(southborough_teams.keys()):
        team_reference = southborough_teams[match_figures_dict["away_team"]]
    
    date_reference = str(match_figures_dict["date"]).replace("-", "")
    
    num = 0
    num_reference = str(num).zfill(2)  
    
    match_reference_dict["unique_match_reference"] = team_reference + date_reference + num_reference
    
    match_reference_list = [] #### To be filled in with list of all unique match references on record
    
    match_reference_dict, num = match_reference_switch(match_reference_list, match_reference_dict, num)
    
    
    return match_reference_dict, error_msg

def match_reference_switch(match_reference_list, match_reference_dict, num):
    if match_reference_dict["unique_match_reference"] in match_reference_list:
        num = num + 1
        match_reference_dict["unique_match_reference"] = match_reference_dict["unique_match_reference"][:-2] + str(num).zfill(2)
        match_reference_switch(match_reference_list, match_reference_dict, num)
        print(str(num))
    
    return match_reference_dict, num


def match_extract(soup4, gameid):
    
    match_figures_dict = {
        "home_game_points": "",
        "home_penalty_points": "",
        "home_batting_points": "",
        "home_bowling_points": "",
        "home_match_official_points": "",
        "home_total_points": "",
        "away_game_points": "",
        "away_penalty_points": "",
        "away_batting_points": "",
        "away_bowling_points": "",
        "away_match_official_points": "",
        "away_total_points": "",
        "league": "",
        "division": "",
        "ground": "",
        "date": "",
        "home_team": "",
        "away_team": "",
        "home_batting_score": "",
        "away_batting_score": "",
        "home_wickets": "",
        "away_wickets": "",
        "home_overs": "",
        "away_overs": "",
        "match_winner": "",
        "win_by_runs": "",
        "win_by_wickets": "",
        "result_other": "",
        "toss_winner": "",
        "toss_decision": "",
}
    
    match_reference_dict = {
        "playcricketid": "",
        "unique_match_reference": "",
}

    error_msg = []
    
    match_figures_dict, error_msg = gamepoints_extract(soup4, match_figures_dict, error_msg)
    match_figures_dict, error_msg = league_extract(soup4, match_figures_dict, error_msg)
    match_figures_dict, error_msg = date_ground_extract(soup4, match_figures_dict, error_msg)
    match_figures_dict, error_msg = fixture_details_extract(soup4, match_figures_dict, error_msg)
    
    ### need to add in function to grab list of unique match references
    
    match_reference_dict["playcricketid"] = gameid
    match_reference_dict, error_msg = match_reference(match_reference_dict, match_figures_dict, error_msg)
    
    return match_figures_dict, match_reference_dict