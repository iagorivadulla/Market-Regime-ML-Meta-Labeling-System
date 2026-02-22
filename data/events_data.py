from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import pandas as pd
from bs4 import BeautifulSoup
import time
import sqlalchemy as db
from sqlalchemy import text
from datetime import datetime


def get_events():
    driver = webdriver.Chrome()
    driver.get("https://www.forexfactory.com/calendar")

    engine = db.create_engine('sqlite:///../data/data.db')

    year = 2007 #this is the first year
    year_now = datetime.now().year
    month = None
    last_date = None

    with engine.connect() as conn:
        result = conn.execute(text(f'SELECT MAX(date) FROM Events'))
        last_date = result.scalar() #gets last date if exists

    if last_date is not None:
        year = pd.to_datetime(last_date).year
        month = pd.to_datetime(last_date).month

    years = range(year, year_now + 1)
     #months for data search
    months = {'Jan': 31,
                  'Feb': 28,
                  'Mar': 31,
                  'Apr': 30,
                  'May': 31,
                  'Jun': 30,
                  'Jul': 31,
                  'Aug': 31,
                  'Sep': 30,
                  'Oct': 31,
                  'Nov': 30,
                  'Dec': 31}

    if month is not None:
         month, day = list(months.items())[month]
         months = {month: day} #rescribe the dict to get only the month we need

    macro_events = pd.DataFrame()

    #search the filter button
    elements = driver.find_element(By.XPATH, '//*[@id="content"]/section[2]/div[3]/div/div/div/div/div[1]/ul/li[8]/a')
    elements.click()
    #deselect the countries
    deselect_all = driver.find_element(By.XPATH, '//*[@id="content"]/section[2]/div[3]/div/div/div/div/div[2]/div[2]/div/div[2]/div[1]/div[1]/div[2]/p/span/a[2]')
    deselect_all.click()
    #select only usa
    usa_element = driver.find_element(By.XPATH, '//*[@id="content"]/section[2]/div[3]/div/div/div/div/div[2]/div[2]/div/div[2]/div[1]/div[1]/div[2]/div/div[2]/div[5]/div[1]')
    usa_element.click()
    #apply changes
    apply_changes = driver.find_element(By.XPATH, '//*[@id="content"]/section[2]/div[3]/div/div/div/div/div[2]/div[2]/div/table/tbody/tr/td[3]/input[1]')
    apply_changes.click()
    time.sleep(1)

    for year in years:
        for month, last_day in months.items():

            #search te calendar
            calendar_element = driver.find_element(By.CLASS_NAME, 'calendar__options.left')
            calendar_element.click()
            #select date range
            date_range_element = driver.find_element(By.ID, 'calendar-date-range-1')
            date_range_element.click()
            date_range_element.clear()
            date_range_element.send_keys(f'{month} 1, {year} – {month} {last_day}, {year}')
            #apply date settings
            apply_date = driver.find_element(By.XPATH, '//*[@id="content"]/section[2]/div[3]/div/div/div/div/div[2]/div[1]/div/table/tbody/tr/td[2]/input[1]')
            apply_date.click()
            time.sleep(2)

            #scroll page
            actions = ActionChains(driver)
            actions.send_keys(Keys.END).perform()
            time.sleep(1)

            #get html
            page_html = driver.page_source
            #read the html with beautifulsoup
            soup = BeautifulSoup(page_html, 'lxml')

            #get the event table
            tables = soup.find_all('table', {'class': 'calendar__table'})
            rows = soup.find_all('tr', {'class': 'calendar__row'})

            day = ""
            event = ""
            actual = ""
            previous = ""
            seen = set()
            #creates the empty dataset
            data = []

            for row in rows:
                date_span = row.find('span', {'class': 'date'})
                event_span = row.find('span', {'class': 'calendar__event-title'})
                actual_span = row.find('td', {'class': 'calendar__actual'})
                previous_span = row.find('td', {'class': 'calendar__previous'})

                if date_span is not None:
                    day = date_span.text.strip()
                    event = ''
                    actual = ''
                    previous = ''

                if event_span is not None:
                    event = event_span.text.strip()
                    actual = ''  # reset actual when we find a new event
                    previous = '' #reset previous too

                if actual_span is not None:
                    actual = actual_span.text.strip()

                if previous_span is not None:
                    previous = previous_span.text.strip()

                # Only print when we have a full, new (day, event) combo
                if day and event:
                    key = (day, event)
                    if key not in seen:
                        seen.add(key)
                        #format the date
                        date = f'{day} {year}'
                        date = pd.to_datetime(date, format='%a %b %d %Y')
                        #add data to dataset

                        data.append({
                            "date": date,
                            "event": event,
                            "actual": actual,
                            "previous": previous
                        })
            df = pd.DataFrame(data)

            events = [
                #monetary policy
                'Federal Funds Rate',
                'FOMC Statement',
                'FOMC Press Conference',
                'FOMC Economic Projections',
                'Fed Chair Press Conference',

                #inflation
                'Core CPI m/m',
                'CPI m/m',
                'Core CPI y/y',
                'PPI m/m',
                'Core PCE Price Index m/m',
                'PCE Price Index m/m',

                #laboral
                'Non-Farm Employment Change',
                'Unemployment Rate',
                'Average Hourly Earnings m/m',
                'Initial Jobless Claims',

                #growth
                'Advance GDP q/q',
                'Prelim GDP q/q',
                'Final GDP q/q',

                #Spending
                'Retail Sales m/m',
                'Core Retail Sales m/m',
                'Personal Spending m/m',
                'Personal Income m/m',

                #Economic feeling
                'ISM Manufacturing PMI',
                'ISM Services PMI',
                'S&P Global Manufacturing PMI',
                'S&P Global Services PMI',

                #Housing
                'Building Permits',
                'Housing Starts',
                'Existing Home Sales',
                'New Home Sales',
            ]


            df = df[df['event'].isin(events)]

            print(f'{len(df)} new entries added')
            macro_events = pd.concat([macro_events, df])

            actions.send_keys(Keys.HOME).perform()
            time.sleep(2)

        #saves this into the db
    with engine.connect() as conn:
        macro_events.to_sql('Events', con=conn, if_exists='append', index=False)
        conn.commit()
        print(f'{len(macro_events)} new entries added to the database')

    driver.quit()

if __name__ == '__main__':
    get_events()