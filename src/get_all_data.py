#search and save data into db
from data.raw.market_prices import get_market_prices
from data.raw.events_data import get_events
from data.raw.fed_data import get_fed_data
#transform the data
from data.interim.process_db import process_db
#final dataset
from data.processed.final_db import final_db

def get_all_data():
    print('Searching for events')
    get_events()
    print('Searching for fed data')
    get_fed_data()
    print('Searching for market prices')
    get_market_prices()
    print('processing database')
    process_db()
    return final_db()

if __name__ == '__main__':
    get_all_data()