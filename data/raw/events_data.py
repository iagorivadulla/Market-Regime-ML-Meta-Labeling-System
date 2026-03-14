from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
import pandas as pd
from bs4 import BeautifulSoup
import time
from selenium.common.exceptions import NoSuchElementException
import sqlalchemy as db
from sqlalchemy import text


def get_events():
    events = [
                #monetary policy
                'US Federal Funds Rate',
                'US FOMC Statement',
                'US FOMC Press Conference',
                'US FOMC Economic Projections',


                #inflation
                'US Core CPI m/m',
                'US CPI m/m',
                'US CPI y/y',
                'US PPI m/m',
                'US Core PCE Price Index m/m',

                #laboral
                'US Non-Farm Employment Change',
                'US Unemployment Rate',
                'US Average Hourly Earnings m/m',

                #growth
                'US Advance GDP q/q',
                'US Prelim GDP q/q',
                'US Final GDP q/q',

                #Spending
                'US Retail Sales m/m',
                'US Core Retail Sales m/m',
                'US Personal Spending m/m',
                'US Personal Income m/m',

                #Economic feeling
                'US ISM Manufacturing PMI',
                'US ISM Services PMI',

                #Housing
                'US Building Permits',
                'US Housing Starts',
                'US Existing Home Sales',
                'US New Home Sales',
            ]

    def select_event(event, driver):

        actions = ActionChains(driver)

        #search for the search bar and clicks it
        driver.find_element(By.XPATH, '//*[@id="content"]/section[2]/div[3]/div/div/div/div/div[1]/ul/li[7]/a').click()
        time.sleep(1)

        #click the search input
        driver.find_element(By.XPATH, '//*[@id="calendar-search-input"]').click()
        time.sleep(1)

        #writes the event name
        actions.send_keys(event)
        actions.perform()
        time.sleep(1)

        #search the event in the dropdown menu and clicks it
        driver.find_element(By.LINK_TEXT, event).click()

        return driver

    def search_dates(driver):
        #search for the dates inside the page loading all the data
        actions = ActionChains(driver)

        while True:
            try:
                #if footer is hidden stops
                driver.find_element(By.CSS_SELECTOR, ".foot.hidden")
                time.sleep(1)
                #goes to the end of the site to load all the htm
                actions.send_keys(Keys.END).perform()
                time.sleep(1)
                #do the same but going at the start of the site
                actions.send_keys(Keys.HOME).perform()
                time.sleep(1)
                break

            except NoSuchElementException:
                # if not footer is hidden, click more button to load all dates
                more = driver.find_element(By.CLASS_NAME, "more")
                more.click()
                time.sleep(1)

        return driver


    def get_event(driver):
        #get html
        page_html = driver.page_source
        print('Get html')

        #read the html with beautifulsoup
        soup = BeautifulSoup(page_html, 'lxml')

        #search for the dates, the current value and the previous value if exist
        dates = soup.find_all(class_= 'calendarhistory__row nowrap calendarhistory__row--history')
        currents = soup.find_all(class_= 'calendarhistory__row calendarhistory__row--actual')
        previouses = soup.find_all(class_= 'calendarhistory__row calendarhistory__row--previous nowrap')

        data = {}

        #stores the data into a dict
        for i in range(0, len(dates)):
            date = pd.to_datetime(dates[i].text.strip()) #format the date

            #load the data into the data dict
            data[date] = (currents[i].text.strip() if currents else None,
                                           previouses[i].text.strip() if previouses else None)

        print('Data obtained')
        #closes the web driver
        driver.close()
        #returns the data dict
        return data


    #starts db engine
    engine = db.create_engine('sqlite:///../data/raw/data.db')

    #option to run navigator silently
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")

    # forces resolution
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")

    # changes user agent
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    chrome_options.add_argument(f'user-agent={user_agent}')

    # disable some features to avoid bot detections
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    #start searching all events stored into events' list
    for i in events:
        with engine.connect() as conn:
            #search for the most recent date stored for this event
            result = conn.execute(text((f'SELECT MAX(date) FROM Events WHERE event = "{i}"')))
            last_date = result.scalar()
            if last_date:
                last_date = pd.to_datetime(last_date).normalize()

            print(i)
            driver = webdriver.Chrome(options=chrome_options) #delete the option to see the navigator proces
            driver.get("https://www.forexfactory.com/calendar") #loads the site

            data = get_event(search_dates((select_event(i, driver)))) #data is stored

            driver.quit()

            #saves data into db testing the last date in the db for the event
            with engine.connect() as conn:
                for date, (current, previous) in data.items():
                    if last_date is None or date > last_date:
                        conn.execute(text((f'INSERT INTO Events VALUES ("{str(date)}", "{i}", "{current}", "{previous}")')))
                        conn.commit()
                print(f'{i} is up to date')
                conn.close()
    print('Everything is up to date!')




if __name__ == '__main__':
    get_events()