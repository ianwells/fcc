from BeautifulSoup import BeautifulSoup as bs
from urllib2 import urlopen
import csv
import hashlib
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import datetime

SHORT_STATION_URL = "http://transition.fcc.gov/fcc-bin/fmq?freq=0.0&fre2=107.9&list=4&NS=N&EW=W&size=9&facid="

def remove_non_ascii(s):
    return "".join(i for i in s if ord(i)<128)

class FccScraper():

    def __init__(self,name,stations,history,fromaddy,password,toaddy,cc,server,port):
        self.reset()
        self.scraper_name = name
        self.station_file = stations
        self.history_file = history
        self.from_address = fromaddy
        self.from_password = password
        self.to_address = toaddy
        self.cc_address = cc
        self.smtp_server = server
        self.smtp_port = port

    def reset(self):
        self.new_station_alert = 0
        self.new_stations = ""
        self.dead_station_alert = 0
        self.dead_stations = ""

    def check_stations(self):
        print("checking " + self.scraper_name)
        stations = self.get_certain_stations(self.station_file)
        self.compare_station_histories(stations,self.history_file)
        self.mail_alerts(stations)
        self.send_mail(self.dump_stations(stations),'html','Summary')
        self.save_station_histories(stations,self.history_file)    
    
    def get_certain_stations(self,filename):
        stations = []
        reader = csv.reader(open(filename))
        for row in reader:
            time.sleep(0.1) #be polite to fcc webservers
            tempurl = SHORT_STATION_URL + row[0]
            stations.extend(self.get_stations(tempurl))
        return stations

    def get_stations(self,url):
        stations = []
        csvfile = urlopen(url)
        reader = csv.reader(csvfile, delimiter='|')
        for row in reader:
            if (len(row) > 0): 
                stations.append(Station(row))
        stations.sort(key=lambda x: x.channel)
        return stations

    def mail_alerts(self,stations):
        alert_text = ""
    
        alert = 0
    
        if self.new_station_alert:
            alert = 1
            alert_text += self.new_stations
            
        if self.dead_station_alert:
            alert = 1
            alert_text += self.dead_stations
    
        for station in stations:
            if (station.has_alert): 
                alert = 1
                alert_text += (station.alert + "\n")
                
        if (alert):
            self.send_mail(alert_text,'plain','Alert')
            
    
    def dump_stations(self,stations):
        
        summary_text = ""
    
        summary_text += (" <html> station dump for: " + str(datetime.datetime.now()))
        
        for station in stations:
            summary_text += (station.dump())
    
        return summary_text + "</html>"

    def compare_station_histories(self,stations,filename):
        stationDict = dict()
        historyDict = dict()
        
        #assume no duplicate facilityId
        for station in stations:
            stationDict[station.facilityId] = station
            
        stringReader = csv.reader(open(filename), delimiter=',', quotechar= '"')
    
        for row in stringReader:
            history = StationHistory(row)
            historyDict[history.facilityId] = history
            
        for history in historyDict:    
            if (stationDict.has_key(history)):
                stationDict[history].compare_history(historyDict[history])    
            else:
                self.dead_station_alert = 1;
                self.dead_stations += ("FACILITY: " + historyDict[history].facilityId + " " +historyDict[history].name + " IS NO LONGER LISTED\n")
                
        for station in stations:
            if not (historyDict.has_key(station.facilityId)):
                self.new_station_alert = 1
                self.new_stations += ("FACILITY: " + station.facilityId + " " + station.name + " IS NEW\n")
                      
    def save_station_histories(self,stations,filename):
        f = open(filename,'w')
        
        for station in stations:
            f.write(station.facilityId+','+station.pnHash+','+station.corrHash+','+station.channel+',"'+station.name+'",'+station.apStatus+','+station.applistHash+'\n')    
    
    def send_mail(self,text, type, subj):
        msg = MIMEMultipart('alternative')
    
        msg['Subject'] = subj + ' from '+ self.scraper_name +' FCC Monitor'
        msg['From'] = self.from_address
        msg['To'] = self.to_address
        msg['CC'] = self.cc_address

        s = smtplib.SMTP(self.smtp_server,self.smtp_port)
    
        part1 = MIMEText(text, type)
        msg.attach(part1)
    
        s.ehlo()
        s.starttls()
        s.login(self.from_address, self.from_password)
        s.sendmail(self.from_address, [self.to_address], msg.as_string())
        s.quit()
    

    

    
class StationHistory:
    
    facilityId = 0
    channel = 0
    pnHash = 0
    corrHash = 0
    applistHash = 0
    status = 0
    
    def __init__(self,row):
        self.facilityId = row[0]
        self.pnHash = row[1]
        self.corrHash = row[2]
        self.channel = row[3]
        self.name = row[4]
        self.status = row[5]
        self.applistHash = row[6]

class Station:
        
    FM_URL_BASE = 'http://transition.fcc.gov/fcc-bin/fmq?facid='
    PN_URL_BASE = 'http://licensing.fcc.gov/cgi-bin/ws.exe/prod/cdbs/pubacc/prod/comment.pl'
    #?Application_id=1582212&File_number=BNPL-20131112ATV'
    
    AP_URL_BASE = 'http://licensing.fcc.gov/cgi-bin/ws.exe/prod/cdbs/pubacc/prod/app_det.pl?Application_id='
    #1594176
    APPLIST_URL_BASE = 'http://licensing.fcc.gov/cgi-bin/ws.exe/prod/cdbs/pubacc/prod/app_list.pl?Facility_id='
    
    CORR_URL_BASE = 'http://licensing.fcc.gov/cgi-bin/ws.exe/prod/cdbs/pubacc/prod/corrp_list.pl'
    #?Application_id=1582212&File_Prefix=BNPL&App_Arn=20131112ATV&Facility_id=193940
    
    newAp = 0
    newPn = 0
    newCorr = 0
    newChannel = 0
    newApplist = 0
    has_alert = 0
    alert = ""
    
    def __init__(self,row):
        self.fileNo = self.clean_file_no(row[13].strip())
        self.applicationNo = row[37].strip()
        self.facilityId = row[18].strip()
        self.frequency = row[2].strip()
        self.channel = row[4].strip()
        self.name = row[27].strip()
        self.city = row[10].strip()
        self.state = row[11].strip()
        self.power = row[14].strip()
        self.filePrefix = self.fileNo.split('-')[0];
        self.fileSuffix = self.fileNo.split('-')[1];
        
        self.fmUrl = self.FM_URL_BASE + self.facilityId
        self.pnUrl = self.PN_URL_BASE + '?Application_id=' + self.applicationNo + '&File_number=' + self.fileNo
        self.corrUrl = self.CORR_URL_BASE + '?Application_id=' + self.applicationNo + '&File_Prefix=' + self.filePrefix + '&App_Arn=' + self.fileSuffix + '&Facility_id=' + self.facilityId
        self.apUrl = self.AP_URL_BASE + self.applicationNo
        self.applistUrl = self.APPLIST_URL_BASE + self.facilityId
        
        self.ap = urlopen(self.apUrl)
        self.apSoup = bs(self.ap)
        self.apStatus = remove_non_ascii(self.apSoup.findAll('tr')[17].text.encode('utf-8').strip().replace('\n',' '))
        self.apDate = remove_non_ascii(self.apSoup.findAll('tr')[18].text.encode('utf-8').strip().replace('\n',' '))
        self.pn = urlopen(self.pnUrl)
        self.pnSoup = bs(self.pn)
        self.pnTable = self.pnSoup.findAll('table')[5]#.text
        
        self.corr = urlopen(self.corrUrl)
        self.corrSoup = bs(self.corr)
        self.corrTable = self.corrSoup.findAll('table')[5]#.text.replace('\n\n',' ')
                   
        self.applist = urlopen(self.applistUrl)
        self.applistSoup = bs(self.applist)
        self.applistTable = self.applistSoup.findAll('table')[6]#.text.replace('\n\n',' ')           
                   
        self.pnHash = hashlib.md5(self.pnSoup.text.encode('utf-8')).hexdigest()
        self.corrHash = hashlib.md5(self.corrSoup.text.encode('utf-8')).hexdigest()
        self.applistHash = hashlib.md5(self.applistSoup.text.encode('utf-8')).hexdigest()
        
    def compare_history(self,history):
        self.newPn = (self.pnHash != history.pnHash)  
        self.newCorr = (self.corrHash != history.corrHash)    
        self.newChannel = (self.channel != history.channel)
        self.newAp = (self.apStatus != history.status)
        self.newApplist = (self.applistHash != history.applistHash)
        
        if self.newAp:
            print("new ap?")
        if self.newApplist:
            print("new applist?")
            
            
        
        self.determine_alerts()

    def determine_alerts(self):
        self.has_alert = 0
        
        self.alert = ""
        if (self.newPn):
            self.has_alert = 1
            self.alert += ("Facility:" + self.facilityId + " " + self.name + " has new public notices.\n")
        if (self.newCorr): 
            self.has_alert = 1
            self.alert += ("Facility:" + self.facilityId + " " + self.name + " has new correspondences.\n")
        if (self.newChannel): 
            self.has_alert = 1
            self.alert += ("Facility:" + self.facilityId + " " + self.name + " has changed channel.\n")
        if (self.newAp):
            self.has_alert = 1
            self.alert += ("Facility:" + self.facilityId + " " + self.name + " has changed application status.\n")
        if (self.newApplist):
            self.has_alert = 1
            self.alert += ("Facility:" + self.facilityId + " " + self.name + " has new application search results.\n")
        
            
    def clean_file_no(self,fn):
        half = ['','']
        half = fn.split('-')
        return half[0].strip() +'-'+ half[1].strip()
    
    def dump(self):
        text = ""
        
        text += ("\n***************************************************<br><br>")
        text += ("\n\n" + self.name + " " + self.city + ", " + self.state  + "<br>")
        if (self.newAp): text +=  ('!!! APPLICATION STATUS HAS CHANGED !!!<br>')
        text += ("\n\n" + self.apStatus + " as of " + self.apDate + "<br>")
        if (self.newChannel): text +=  ('!!! CHANNEL HAS CHANGED !!!<br>')
        text += (self.channel + " " + self.frequency + "<br>")
        text += ('File #: '+ self.fileNo + "<br>")
        text += ('<A href=  '+ self.fmUrl +'> Facility ID:' + self.facilityId + "</A> <br>")
        
        text += ('<A href = ' + self.pnUrl + '> Public Notices </A><br>')
        if (self.newPn): text +=  ('!!! PUBLIC NOTICES HAVE CHANGED !!! + "<br>"')
        
        text += ('<A href = ' + self.corrUrl + '> Correspondence </A><br>')
        if (self.newCorr): text +=  ('!!! CORRESPONDENCES HAVE CHANGED !!! + "<br>"')
        text += ('<A href = ' + self.applistUrl + '> Application Search </A><br>')
        if (self.newApplist): text +=  ('!!! APPLICATION SEARCH RESULTS HAVE CHANGED !!! + "<br>"')
        text += ("<br> PUBLIC NOTICES: " + "<br>")
        text += str(self.pnTable)
        
        text += ("<br> CORRESPONDENCE:" + "<br>") 
        text += str(self.corrTable)   
        
        text += ("<br> APPLICATION SEARCH:" + "<br>") 
        text += str(self.applistTable)     
        return text
