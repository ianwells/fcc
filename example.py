from FccScraper import FccScraper


STATIONS_FILE = "example_stations.txt"
HISTORY_FILE = "example_history.txt" #it'll make one if none exists


FROM_ADDRESS = "your email address here"
FROM_PASSWORD = "your password here"
TO_ADDRESS = 'to address here'
CC_ADDRESS = ''
SMTP = 'smtp server address here'
PORT = 0 #smtp port goes here

def main(): 
  example_scraper = FccScraper("Example Scraper", STATIONS_FILE, HISTORY_FILE, FROM_ADDRESS, FROM_PASSWORD, TO_ADDRESS, CC_ADDRESS, SMTP, PORT) 
  
  example_scraper.check_stations()


if __name__ == "__main__": main()    
