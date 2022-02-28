import requests, bs4, pandas, re, datetime, numpy, sqlite3
from dateutil.parser import parse

import selenium, openpyxl, shutil, os, time
from selenium import webdriver

# SQL connector to database 

conn = sqlite3.connect('SboroCricket.db')

#########################################
#
# Play cricket scorecard extracting 
#
#########################################

# Finds the innings ids for each team in a match

def find_innings_id(string):
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

# Extracts match info, eg winner, ground, points, etc

def Match_extract(soup4, innings_id, PlayCricketID, insert_db = True):

    Match_figures = [""] * 30

    GamePoints_data = []
    
    # Downloads match points for teams if a league game
    
    for i in range(1,3):
        GamePoints = soup4.select('#multiCollapseExample' + str(i) + ' > table')

        if len(GamePoints) == 0:
            GamePoints_data = [""]*10

        else:
            GamePoints_table = pandas.read_html(str(GamePoints[0]))[0]
            for j in range(len(GamePoints_table)):
                GamePoints_data.append(GamePoints_table.iloc[[j]].values[0][1])

    Match_figures[13:18] = GamePoints_data[:5]
    Match_figures[21:26] = GamePoints_data[5:]

    ##Extracts division and league data [league , division]

    DivisionInfo = soup4.select('body > div.breadcrumb-league-wrapper > div.container.breadcrumb-league > div > div.col-sm-12.col-md-6.col-lg-6.text-center.text-lg-left.leaguedetail-left')
    DivisionInfo_data = [""]*2

    if 'friendly' in str(DivisionInfo[0]).lower():
        DivisionInfo_data = ["Friendly", "Friendly"]

    elif DivisionInfo[0].find_all('span')[0].contents[0].strip() == "":
        DivisionInfo_data = [DivisionInfo[0].find_all('span')[2].contents[0].strip()]*2

    elif len(DivisionInfo[0].find_all('span')[2]) == 1:
        DivisionInfo_data[0] = DivisionInfo[0].find_all('span')[0].contents[0].strip()
        DivisionInfo_data[1] = DivisionInfo[0].find_all('span')[2].contents[0].strip()
        
    elif 'https' in str(DivisionInfo[0].find_all('span')[2].contents[1]).lower():
        DivisionInfo_data[0] = DivisionInfo[0].find_all('span')[0].contents[0].strip()
        start = str(DivisionInfo[0].find_all('span')[2].contents[1]).find(">") + 1 
        end = str(DivisionInfo[0].find_all('span')[2].contents[1]).find("<",str(DivisionInfo[0].find_all('span')[2].contents[1]).find(">")) 
        DivisionInfo_data[1] = str(DivisionInfo[0].find_all('span')[2].contents[1])[start:end]

    Match_figures[3:5] = DivisionInfo_data

    ##Extracts date and location data [ground , date]

    DateGround_data = [""]*2

    DateGround = soup4.select('body > div.breadcrumb-league-wrapper > div.container.breadcrumb-league > div > div.col-sm-12.col-md-6.col-lg-6.text-lg-right.leaguedetail-right')
    Date = parse(re.search('\d*? \w* \d{4}',DateGround[0].text)[0])
    Ground = DateGround[0].find_all('a')[0].contents[0]

    if "\n" not in Ground:
        DateGround_data[0] = Ground
    DateGround_data[1] = Date.date()

    Match_figures[2] = DateGround_data[1]
    Match_figures[7] = DateGround_data[0]



    ## Extracts [Home team, Away team, Home batting score, Away batting score, Home wickets lost, Away wickets lost, Home overs, Away overs, Winner, by runs, by wickets, other, toss winner, toss decision]

    Teams = soup4.select('body > div.container.main-header.main-header-lg.d-none.d-lg-block > table')

    Teams_data = [""]*14

    for i in range(2):
        Clubname = Teams[0].find_all('p', class_="team-name")[i].contents[0]
        first = str(Teams[0].find_all('p', class_="team-info-2")[i].find_all(class_ = "team-info-1")[0]).find("\n")
        second = str(Teams[0].find_all('p', class_="team-info-2")[i].find_all(class_ = "team-info-1")[0]).find("\n", first + 1)
        Clubteam = str(Teams[0].find_all('p', class_="team-info-2")[i].find_all(class_ = "team-info-1")[0])[first+1:second].strip()
        Teams_data[i] = Clubname + ' ' + Clubteam


    for i in range(2):
        first = str(Teams[0].find_all('p', class_ = "team-info-2")[i]).find("</span>\n")
        second = str(Teams[0].find_all('p', class_ = "team-info-2")[i]).find("<", first + 1)
        Battingscore = str(Teams[0].find_all('p', class_ = "team-info-2")[i])[first + len("</span>\n") : second].strip()
        if Battingscore != "":
            Teams_data[2 + i] = int(Battingscore)


    for i in range(2):
        if len(Teams[0].find_all('p', class_ = "team-info-2")[i].find_all(class_ = "smalltxt")) == 0:
            Teams_data[4 + i], Teams_data[6 + i] = "",""
        else :
            WicketsOvers_html = Teams[0].find_all('p', class_ = "team-info-2")[i].find_all(class_ = "smalltxt")[0].contents[0]
            first = WicketsOvers_html.find("/")
            second = WicketsOvers_html.find("(", first + 1)
            third = WicketsOvers_html.find(")", second + 1)
            Wickets = WicketsOvers_html[first + 1 : second].strip()
            if "All out" in Wickets:
                Teams_data[4 + i] = 10
            else :
                Teams_data[4 + i] = Wickets
            Overs = WicketsOvers_html[second + 1 : third].strip()
            if len(Overs) > 0:
                Teams_data[6 + i] = float(Overs)


    if "ABANDONED" in str(Teams[0]):
        Teams_data[8] = "None"
        Teams_data[11] = "Abandoned"

    elif "CONCEDED" in str(Teams[0]):
        Teamconceded = Teams[0].find_all('p', class_ = "match-ttl win-cb-name")[0].contents[0].strip()
        if Teamconceded in Teams_data[0].upper():
            Teams_data[8] = Teams_data[1]
        else :
            Teams_data[8] = Teams_data[0]
        Teams_data[11] = "Conceded"
    
    elif len(Teams[0].find_all('p', class_ = "match-ttl win-cb-name")) == 0:
        Teams_data[8] = "None"
        Teams_data[11] = "Cancelled"
    
    else :
        Matchwinner = Teams[0].find_all('p', class_ = "match-ttl win-cb-name")[0].contents[0].strip()
        first = str(Teams[0].find_all('div', class_ = "info mdont")[0].contents[1]).find("<span>")
        second = str(Teams[0].find_all('div', class_ = "info mdont")[0].contents[1]).find("<", first + 1)
        Wintype = str(Teams[0].find_all('div', class_ = "info mdont")[0].contents[1])[first + len("<span>") : second]
        Byhowmuch = ''.join(filter(str.isdigit, str(Teams[0].find_all('div', class_ = "info mdont")[0].contents[0])))

        if Matchwinner in Teams_data[0].upper():
            Teams_data[8] = Teams_data[0]
        else :
            Teams_data[8] = Teams_data[1]
        if Wintype == "RUNS":
                Teams_data[9] = int(Byhowmuch)
        if Wintype == "WICKETS":
                Teams_data[10] = int(Byhowmuch)     


    if len(Teams[0].find_all('p', class_ = "team-info-3")) != 0:
        for i in range(2):
            if len(Teams[0].find_all('p', class_ = "team-info-3")[i].contents) != 0:
                Teams_data[12] = Teams_data[i]
                if "bat" in Teams[0].find_all('p', class_ = "team-info-3")[i].contents[0]:
                    Teams_data[13] = "Bat"
                else :
                    Teams_data[13] = "Field"

        if Teams_data[12] == "" and Teams_data[13] == "":
            Teams_data[12], Teams_data[13] = "No toss", "No toss"

    elif len(Teams[0].find_all('p', class_ = "team-info-3 adma")) != 0:
        for i in range(2):
            if len(Teams[0].find_all('p', class_ = "team-info-3 adma")[i].contents) != 0:
                Teams_data[12] = Teams_data[i]
                if "bat" in Teams[0].find_all('p', class_ = "team-info-3 adma")[i].contents[0]:
                    Teams_data[13] = "Bat"
                else :
                    Teams_data[13] = "Field"

        if Teams_data[12] == "" and Teams_data[13] == "":
            Teams_data[12], Teams_data[13] = "No toss", "No toss"            


    Match_figures[5:7] = Teams_data[0:2]
    Match_figures[10:13] = [Teams_data[2], Teams_data[4], Teams_data[6]]
    Match_figures[18:21] = [Teams_data[3], Teams_data[5], Teams_data[7]]
    Match_figures[26:30] = Teams_data[8:12]
    Match_figures[8:10] = Teams_data[12:14]


    ## Extracts Playcricket match code (URL) and creates my own match reference

    Reference_data = [""]*2

    Reference_data[0] = PlayCricketID
    
    Date_reference = str(DateGround_data[1]).replace("-","")
    Sboro_teams = ['Southborough CC 1st XI', 'Southborough CC 2nd XI', 'Southborough CC Sunday XI', 'Southborough CC Under 13', 'Southborough CC Under 13 B', 'Southborough CC Under 11', 'Southborough CC Under 21', 'Southborough CC Under 15', 'Southborough CC Midweek XI']
    Sboro_teams_references = ['1ST', '2ND', 'SUN', '13A', '13B', '11A', '21A', '15A', 'MID']
    
    for i in range(len(Sboro_teams)):
        if Teams_data[0] == Sboro_teams[i] or Teams_data[1] == Sboro_teams[i]:
            Team_reference = Sboro_teams_references[i]
    
    Reference_data[1] = Team_reference + Date_reference + '00'
    
    # If there is already a game with same fixture, eg. two Sunday teams play on same day, creates a second match reference
    
    Additional_match_references = ['01', '02', '03', '04', '05', '06']
    stored_matchIDs = sql_matchID_fetch(conn)
    Reference_data = Reference_switch(stored_matchIDs, Reference_data, Additional_match_references)
    
    Match_figures[:2] = Reference_data

    if insert_db:
        sql_insert_match(conn, Match_figures)
        print('Match reference is: ' + Reference_data[1])
    else:
        print(Match_figures)

    return Reference_data, Teams_data



# Extracts bowling figures for game

def Bowling_extract(soup4, innings_id, Reference_data, Teams_data, insert_db = True):

    for k in range(len(innings_id)):

        elems = soup4.select('body > div.container100sm.container.container-scorecard > div > div.col-sm-12.col-scorecard.mb50')
        if str(elems[0].find_all('a')[k].contents[0]).replace('\n', ' ').strip() in Teams_data[0]:
            batting_team = Teams_data[0]
            bowling_team = Teams_data[1]
        else:
            batting_team = Teams_data[1]
            bowling_team = Teams_data[0]

        for i in range(11):

            elems = soup4.select('#innings' + innings_id[k] + ' > table > tbody > tr:nth-child(' + str(i+1) + ') > td:nth-child(1)')
            if len(elems) > 0:

                Bowling_figures = [""]*14

                Bowling_figures[1:5] = [Reference_data[1], batting_team, bowling_team, str(i+1)]
                
                # Extracts bowlers name
                
                if "Unsure" in elems[0].contents[0]:
                    Bowlersname = "Unsure"
                elif "player_stats" not in str(elems[0].contents[0]):
                    Bowlersname = elems[0].contents[0]
                else:
                    Bowlersname = str(elems[0].contents[0].contents[0])

                Bowling_figures[5] = Bowlersname

                # Extracts the bowling figures from table
                
                for j in range(6):
                    elems = soup4.select('#innings' + innings_id[k] + ' > table > tbody > tr:nth-child(' + str(i+1) + ') > td:nth-child(' + str(j+2) + ')')
                    if len(elems[0].contents) == 0:
                        Bowling_figures[j + 6] = 0
                    if len(elems[0].contents) > 0:
                        Bowling_figures[j + 6] = float(elems[0].contents[0])
                
                # Calculate economy rate
                
                if Bowling_figures[6] == 0:
                    Bowling_figures[12] = 0
                else:
                    Bowling_figures[12] = Bowling_figures[8] / Bowling_figures[6]
                
                # Calculates average
                
                if Bowling_figures[9] == 0:
                    Bowling_figures[13] = float(0)
                else:
                    Bowling_figures[13] = Bowling_figures[8] / Bowling_figures[9]
                
                # Creates unique bowler reference
                
                Bowling_figures[0] = Bowling_figures[1] + Bowling_figures[2][:2].upper() + Bowling_figures[3][:2].upper() + 'BOW' + Bowling_figures[4]

                if insert_db:
                    sql_insert_bowling(conn, Bowling_figures)
                else:
                    print(Bowling_figures)
                    
                    
# Extracts batting scorecard


def Batting_extract(soup4, innings_id, Reference_data, Teams_data, insert_db = True):

    for k in range(len(innings_id)):

        elems = soup4.select('body > div.container100sm.container.container-scorecard > div > div.col-sm-12.col-scorecard.mb50')
        if str(elems[0].find_all('a')[k].contents[0]).replace('\n', ' ').strip() in Teams_data[0]:
            batting_team = Teams_data[0]
            bowling_team = Teams_data[1]
        else:
            batting_team = Teams_data[1]
            bowling_team = Teams_data[0]

        for i in range(11):

            Batting_figures = [""] * 15

            Batting_figures[1:3] = [Reference_data[1], batting_team, bowling_team]
            Batting_figures[6:7] = ["N", "N"]
            Batting_figures[4] = str(i+1)

            elems = soup4.select('#innings' + innings_id[k] + ' > div.table-responsive-sm > table.table.standm.table-hover > tbody > tr:nth-child(' + str(1+i) + ') > td:nth-child(1) > div.bts')# > a')
            
            # Extracts batter's name
            
            if len(elems) == 0:
                break
            if "Unsure" in elems[0]:
                Batting_figures[5] = "Unsure"
            elif 'player_stats' not in str(elems[0].contents[0]):
                Batting_figures[5] = elems[0].contents[0]
            else:
                Batting_figures[5] = elems[0].contents[0].contents[0]

                # Extracts whether batter is Keeper, Captain, or both.
                
                if len(elems[0].contents[0].contents) == 2:
                    if "captain" in str(elems[0].contents[0].contents):
                        Batting_figures[6] = "Y"
                    if "Keeper" in str(elems[0].contents[0].contents):
                        Batting_figures[7] = "Y"
                if len(elems[0].contents[0].contents) == 3:
                        Batting_figures[6:8] = ["Y", "Y"]


            elems = soup4.select('#innings' + innings_id[k] + ' > div.table-responsive-sm > table.table.standm.table-hover > tbody > tr:nth-child(' + str(1+i) + ') > td:nth-child(2)')
            if len(elems[0].contents) > 0:
                Batting_figures[8] = elems[0].contents[0].contents[0]
                if 'Unsure' in elems[0]:
                    Batting_figures[9] = 'Unsure'
                elif len(elems[0].contents) > 1 and 'player_stats' not in str(elems[0].contents[1]):
                    Batting_figures[9] = str(elems[0].contents[1])
                elif len(elems[0].contents) > 1:
                    Batting_figures[9] = elems[0].contents[1].contents[0]

            elems = soup4.select('#innings' + innings_id[k] + ' > div.table-responsive-sm > table.table.standm.table-hover > tbody > tr:nth-child(' + str(1+i) + ') > td:nth-child(3)')
            if len(elems[0].contents) > 0:
                Batting_figures[10] = elems[0].contents[0].contents[0].strip()
                if "Unsure" in elems[0]:
                    Batting_figures[11] = "Unsure"
                elif 'player_stats' not in str(elems[0].contents[1]):
                    Batting_figures[11] = str(elems[0].contents[1])
                else:
                    Batting_figures[11] = elems[0].contents[1].contents[0]

            elems = soup4.select('#innings' + innings_id[k] + ' > div.table-responsive-sm > table.table.standm.table-hover > tbody > tr:nth-child(' + str(1+i) + ') > td:nth-child(4)')
            if len(elems[0].contents) > 0:
                Batting_figures[12] = int(elems[0].contents[0].contents[0])

            for j in range(5,9):
                elems = soup4.select('#innings' + innings_id[k] + ' > div.table-responsive-sm > table.table.standm.table-hover > tbody > tr:nth-child(' + str(1+i) + ') > td:nth-child(' + str(j) + ')')
                if len(elems[0].contents) > 0:
                    Batting_figures[j + 8] = float(elems[0].contents[0])

            Batting_figures[0] = Batting_figures[1] + Batting_figures[2][:2].upper() + Batting_figures[3][:2].upper() + 'BAT' + Batting_figures[4]

            if insert_db:
                sql_insert_batting(conn, Batting_figures)
            else:
                print(Batting_figures)
            

            
### Grabs batting extras data [1st byes, 1st leg byes, 1st wides, 1st no balls, 1st total, 2nd byes, etc]

def Extras_extract(soup4, innings_id, Reference_data, Teams_data, insert_db = True):

    for k in range(len(innings_id)):

        Extras_figures = [""] * 9
        elems = soup4.select('body > div.container100sm.container.container-scorecard > div > div.col-sm-12.col-scorecard.mb50')
        if str(elems[0].find_all('a')[k].contents[0]).replace('\n', ' ').strip() in Teams_data[0]:
            batting_team = Teams_data[0]
            bowling_team = Teams_data[1]
        else:
            batting_team = Teams_data[1]
            bowling_team = Teams_data[0]
        Extras_figures[1:4] = [Reference_data[1], batting_team, bowling_team] 

        elems = soup4.select('#innings' + innings_id[k] + ' > div.table-responsive-sm > table.table.table-sm.table-scorecard-footer > tbody > tr:nth-child(1) > td.text-left.text-md-right.d-none.d-md-block > div')
        if len(elems) > 0:
            if elems[0].contents[1] == "0":
                Extras_figures[4:8] = [0]*4
            Extras_type = ["b", "lb", "w", "nb"]
            for i in range(4):
                if re.search('\d{1,2}' + Extras_type[i], elems[0].contents[1]) == None:
                    Extras_figures[4 + i] = 0
                else:
                    Extras_figures[4 + i] = int(re.search('\d{1,2}' + Extras_type[i], elems[0].contents[1])[0].replace(Extras_type[i], " ").strip())
            Extras_figures[8] = sum(Extras_figures[4:8]) 
        Extras_figures[0] = Extras_figures[1] + Extras_figures[2][:2].upper() + Extras_figures[3][:2].upper()
        
        if insert_db:
            sql_insert_extras(conn, Extras_figures)
        else:
            print(Extras_figures)


            ### Gets fall of wickets data if available

def FoW_extract(soup4, innings_id, Reference_data, Teams_data, insert_db = True):

    for k in range(len(innings_id)):

        FoW_figures = [""] * 44
        elems = soup4.select('body > div.container100sm.container.container-scorecard > div > div.col-sm-12.col-scorecard.mb50')
        if str(elems[0].find_all('a')[k].contents[0]).replace('\n', ' ').strip() in Teams_data[0]:
            batting_team = Teams_data[0]
            bowling_team = Teams_data[1]
        else:
            batting_team = Teams_data[1]
            bowling_team = Teams_data[0]
        FoW_figures[1:4] = [Reference_data[1], batting_team, bowling_team]
        FoW_figures[0] = FoW_figures[1] + FoW_figures[2][:2].upper() + FoW_figures[3][:2].upper()

        elems = soup4.select('#innings' + innings_id[k] + ' > div:nth-child(2) > div > p.font-3')
        FoW_teamruns = [""]*10
        FoW_batter = [""]*10
        FoW_NObatter = [""]*10
        FoW_NObatterscore = [""]*10
        if len(elems) > 0:
            for i in range(len(elems[0].contents)):

                #print(elems[0].contents[i])
                if re.search('>-\d{1,2}<',str(elems[0].contents[i])) != None:
                    break
                
                if re.search('\d{1,3}-\d{1,2}',str(elems[0].contents[i])) != None:
                    wicketno = int(re.search('-\d{1,2}',str(elems[0].contents[i]))[0][1:])
                    FoW_teamruns[wicketno - 1] = int(re.search('\d{1,3}-',str(elems[0].contents[i]))[0][:-1])

                if str(elems[0].contents[i]) == " (":
                    FoW_batter[wicketno - 1] = str(elems[0].contents[i -1].contents[0])
                    FoW_NObatter[wicketno - 1] = str(elems[0].contents[i + 1].contents[0])
                    FoW_NObatterscore[wicketno - 1] = int(re.search('-\d{1,3}\*', str(elems[0].contents[i + 2]))[0][1:-1])
                if "Unsure (Unsure-0*)" in elems[0].contents[i]:
                    FoW_batter[wicketno - 1] = 'Unsure'
                    FoW_NObatter[wicketno - 1] = 'Unsure'
                    FoW_NObatterscore[wicketno - 1] = int(re.search('-\d{1,3}\*', elems[0].contents[i])[0][1:-1])

        for i in range(10):
            FoW_figures[4*i + 4 : 4*i + 8] = [FoW_teamruns[i], FoW_batter[i], FoW_NObatter[i], FoW_NObatterscore[i]]
        
        if insert_db:
            sql_insert_fow(conn, FoW_figures) 
        else:
            print(FoW_figures)

# If the unique match reference is already in use for another fixture, e.g. two sunday games on same day, adds an extra digit on end of the second to create a new unique reference. 

def Reference_switch(stored_matchIDs, Reference_data, Additional_match_references):
    for i in range(len(stored_matchIDs)):
        if Reference_data[1] in stored_matchIDs[i]:
            temp = list(Reference_data[1])
            temp[-2:] = Additional_match_references[0]
            Additional_match_references.remove(Additional_match_references[0])
            Reference_data[1] = "".join(temp)
    return Reference_data
    Reference_switch(stored_matchIDs, Reference_data, Additional_match_references)
    
    
#########################################
#
# SQL interacting
#
#########################################

def sql_insert_bowling(conn, bowling_figures):
    cursorObj = conn.cursor()
    cursorObj.execute('INSERT INTO Bowling(uniqueID, matchID, Batting_team, Bowling_team, Bowler_no, Bowler_name, Overs, Maidens, Runs, Wickets, Wides, Noballs, ER, Average) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', bowling_figures)
    conn.commit()


def sql_insert_batting(conn, batting_figures):
    cursorObj = conn.cursor()
    cursorObj.execute('INSERT INTO Batting(uniqueID, matchID, Batting_team, Bowling_team, Batting_no, Batter_name, Captain, Keeper, Secondary_dismissal, Secondary_dismisser, Bowled, Bowler, Runs, Balls, Fours, Sixes, Strikerate) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', batting_figures)
    conn.commit()
    
def sql_insert_match(conn, match_figures):
    cursorObj = conn.cursor()
    cursorObj.execute('INSERT INTO Match(PlayCricket, matchID, Date, League, Division, Home_team, Away_team, Ground, Toss_winner, Toss_decision, Home_battingscore, Home_wicketslost, Home_overs, Home_gamepts, Home_penaltypts, Home_battingpts, Home_bowlingpts, Home_totalpts, Away_battingscore, Away_wicketslost, Away_overs, Away_gamepts, Away_penaltypts, Away_battingpts, Away_bowlingpts, Away_totalpts, Winner, ByRuns, ByWickets, ByOther) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', match_figures)
    conn.commit()

def sql_insert_extras(conn, extras_figures):
    cursorObj = conn.cursor()
    cursorObj.execute('INSERT INTO Extras(uniqueID, matchID, Batting_team, Bowling_team, Byes, LegByes, Wides, NoBalls, Total) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)', extras_figures)
    conn.commit()

def sql_insert_fow(conn, fow_figures):
    cursorObj = conn.cursor()
    cursorObj.execute('INSERT INTO FoW(uniqueID, matchID, Batting_team, Bowling_team, teamruns_1, batter_1, NObatter_1, NObatterscore_1, teamruns_2, batter_2, NObatter_2, NObatterscore_2, teamruns_3, batter_3, NObatter_3, NObatterscore_3, teamruns_4, batter_4, NObatter_4, NObatterscore_4, teamruns_5, batter_5, NObatter_5, NObatterscore_5, teamruns_6, batter_6, NObatter_6, NObatterscore_6, teamruns_7, batter_7, NObatter_7, NObatterscore_7, teamruns_8, batter_8, NObatter_8, NObatterscore_8, teamruns_9, batter_9, NObatter_9, NObatterscore_9, teamruns_10, batter_10, NObatter_10, NObatterscore_10) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', fow_figures)
    conn.commit()
    

# Extracts all matchIDs currently saved in database
    
def sql_matchID_fetch(conn):
    cursorObj = conn.cursor()
    cursorObj.execute('SELECT matchID from Match')
    stored_matchIDs = cursorObj.fetchall()
    return stored_matchIDs

# Extracts all Playcricket IDs currently saved in database

def sql_PlayCricket_fetch(conn):
    cursorObj = conn.cursor()
    cursorObj.execute('SELECT PlayCricket from Match')
    stored_PlayCricketIDs = cursorObj.fetchall()
    return stored_PlayCricketIDs

# Deletes all data from match with the inputted matchID

def sql_match_delete(conn, matchID):
    cursorObj = conn.cursor()
    cursorObj.execute('DELETE FROM Match where matchID = "'+ matchID +'"')
    conn.commit()
    cursorObj.execute('DELETE FROM Batting where matchID = "'+ matchID +'"')
    conn.commit()
    cursorObj.execute('DELETE FROM Bowling where matchID = "'+ matchID +'"')
    conn.commit()
    cursorObj.execute('DELETE FROM Extras where matchID = "'+ matchID +'"')
    conn.commit()
    cursorObj.execute('DELETE FROM FoW where matchID = "'+ matchID +'"')
    conn.commit()

#########################################
#
# Full process
#
#########################################        

# Compares potential list of Play cricket IDs and removes any that are already stored in the database.

def Remove_duplicate_FixtureIDs(FixtureIDs):
    stored_PlayCricketIDs = sql_PlayCricket_fetch(conn)
    IDstoremove = []

    for j in range(len(FixtureIDs)):
        for i in range(len(stored_PlayCricketIDs)):
            if str(FixtureIDs[j]) in stored_PlayCricketIDs[i]:
                IDstoremove.append(FixtureIDs[j])

    FixtureIDs = [x for x in FixtureIDs if x not in IDstoremove]
    return FixtureIDs

# Sets user inputs for fixture download from Play cricket admin section.

def user_inputs():
    print('Enter Play-Cricket login email.')
    email_input = input()
    print('Enter Play-Cricket login password.')
    pwd_input = input()
    print('Enter start and end dates in format dd/mm/yyyy. The two dates must be less than 1 year apart.')
    print('Start date:')
    startdate = input()
    print('End date:')
    enddate = input()
    return email_input, pwd_input, startdate, enddate

# Downloads the fixture Ids from Play cricket within date range inputted

def results_worksheet_download(email_input, pwd_input, startdate, enddate):
    driver = webdriver.Chrome('C:/Users/philc/Documents/Python/chromedriver.exe')
    driver.get('https://southboroughcc.play-cricket.com/')

    link = driver.find_element_by_xpath('//*[@id="cookieaccept"]/div/div/div/div/button')
    link.click()

    login_link = driver.find_element_by_xpath('/html/body/div[2]/div/div[3]/ul/li[1]/a')
    login_link.click()

    driver.implicitly_wait(10)

    email_link = driver.find_element_by_xpath('//*[@id="main"]/form/div[1]/input')
    email_link.send_keys(email_input)

    pwd_link = driver.find_element_by_xpath('//*[@id="main"]/form/div[2]/input')
    pwd_link.send_keys(pwd_input)

    link = driver.find_element_by_xpath('//*[@id="main"]/form/div[4]/input')
    link.click()

    driver.get('https://southboroughcc.play-cricket.com/site_admin/results')
    startdate_link = driver.find_element_by_xpath('//*[@id="q_match_date_gteq"]')
    startdate_link.clear()
    startdate_link.send_keys(startdate)
    enddate_link = driver.find_element_by_xpath('//*[@id="q_match_date_lteq"]')
    enddate_link.clear()
    enddate_link.send_keys(enddate)
    link = driver.find_element_by_xpath('//*[@id="match_search"]/div/table/tbody/tr[4]/td[2]/input')
    link.click()
    link = driver.find_element_by_xpath('//*[@id="match_search"]/div/table/tbody/tr[4]/td[3]/a')
    link.click()
    
    ticker = 0
    while ticker < 60:
        time.sleep(1)
        ticker = ticker + 1
        if os.path.exists('C:/Users/philc/Downloads/download_results.xlsx'):
            driver.quit()
            break
    driver.quit()

# Moves the fixture download from my downloads to my git repository folder and renames to the relevant dates.

def move_fixturedownload(startdate, enddate):
    startdate = startdate.replace("/", "")
    enddate = enddate.replace("/", "")
    name = 'download_results_' + startdate + '_' + enddate + '.xlsx'
    shutil.move('C:/Users/philc/Downloads/download_results.xlsx','C:/Users/philc/Documents/Python/Southborough stats/Southborough-CC-Stats/download_results.xlsx')
    os.rename('download_results.xlsx', name)
    
# Extracts fixture IDs from PlayCricket download.

def FixtureID_extract(startdate, enddate):
    startdate = startdate.replace("/", "")
    enddate = enddate.replace("/", "")
    name = 'download_results_' + startdate + '_' + enddate + '.xlsx'
    wb = openpyxl.load_workbook(name)
    sheet = wb['Results']

    FixtureIDs = []
    for cellObj in list(sheet.columns)[13]:
        if type(cellObj.value) == int:
            FixtureIDs.append(cellObj.value)
    return FixtureIDs
    
   
# Full extract from list of Play cricket IDs. The input should either be a list or a single id in the from end of the website address, eg. https://southboroughcc.play-cricket.com/website/results/4928320. The 4928320 is the Play cricket ID.

def Full_extract(GameID):
    for i in GameID:
        
        starttime = time.perf_counter()
        
        if type(i) != str:
            i = str(i)
        print(i + ' started...')
        r4 = requests.get('https://southboroughcc.play-cricket.com/website/results/' + i)
        r4.raise_for_status()
        soup4 = bs4.BeautifulSoup(r4.content, 'html.parser')
        innings_id = find_innings_id(r4.text)

        Reference_data, Teams_data = Match_extract(soup4, innings_id, i)
        Batting_extract(soup4, innings_id, Reference_data, Teams_data)
        Bowling_extract(soup4, innings_id, Reference_data, Teams_data)
        Extras_extract(soup4, innings_id, Reference_data, Teams_data)
        FoW_extract(soup4, innings_id, Reference_data, Teams_data)
        
        endtime = time.perf_counter()
        
        print(i + ' uploaded!')
        print(i + ' took ' + str(endtime - starttime) + ' seconds to upload.')