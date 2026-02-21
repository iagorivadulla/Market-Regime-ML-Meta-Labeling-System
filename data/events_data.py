from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import pandas as pd
from bs4 import BeautifulSoup
import time

def get_events():
    driver = webdriver.Chrome()
    driver.get("https://www.forexfactory.com/calendar")

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

    # search the filter button
    elements = driver.find_element(By.CLASS_NAME, "highlight.filters")
    elements.click()
    # deselect the countries
    deselect_all = driver.find_element(By.XPATH,
                                       '//*[@id="content"]/section[2]/div[3]/div/div/div/div/div[2]/div[2]/div/div[2]/div[1]/div[1]/div[2]/p/span/a[2]')
    deselect_all.click()
    # select only usa
    usa_element = driver.find_element(By.XPATH,
                                      '//*[@id="content"]/section[2]/div[3]/div/div/div/div/div[2]/div[2]/div/div[2]/div[1]/div[1]/div[2]/div/div[2]/div[5]/div[1]')
    usa_element.click()
    # apply changes
    apply_changes = driver.find_element(By.XPATH,
                                        '//*[@id="content"]/section[2]/div[3]/div/div/div/div/div[2]/div[2]/div/table/tbody/tr/td[3]/input[1]')
    apply_changes.click()
    time.sleep(5)

    # search te calendar
    calendar_element = driver.find_element(By.CLASS_NAME, 'calendar__options.left')
    calendar_element.click()
    # select date range
    date_range_element = driver.find_element(By.ID, 'calendar-date-range-1')
    date_range_element.click()
    date_range_element.clear()
    date_range_element.send_keys('Jan 1, 2007 – Jan 31, 2007')
    # apply date settings
    apply_date = driver.find_element(By.XPATH,
                                     '//*[@id="content"]/section[2]/div[3]/div/div/div/div/div[2]/div[1]/div/table/tbody/tr/td[2]/input[1]')
    apply_date.click()
    time.sleep(3)

    # scroll page
    actions = ActionChains(driver)
    actions.send_keys(Keys.END).perform()
    time.sleep(3)

    # get html
    page_html = driver.page_source
    # read the html with beautifulsoup
    soup = BeautifulSoup(page_html, 'lxml')

    # get the event table
    tables = soup.find_all('table', {'class': 'calendar__table'})
    rows = soup.find_all('tr', {'class': 'calendar__row'})

    day = ""

    for row in rows:
        # Get the date and the event name
        date_span = row.find('span', {'class': 'date'})
        event_span = row.find('span', {'class': 'calendar__event-title'})

        if date_span is not None:
            # stores the data for the same event days
            day = date_span.text.split()[-1]

        if event_span is not None:
            event = event_span.text.strip()
            if event:
                print(f"{day} - {event}")