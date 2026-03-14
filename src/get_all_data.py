#search and save data into db
from data.raw.market_prices import get_market_prices
from data.raw.events_data import search_event
from data.raw.fed_data import get_fed_data
#transform the data
from data.interim.process_db import process_db
#final dataset
from data.processed.final_db import final_db
import sqlalchemy as db

def get_all_data(engine):
    print('Searching for events')
    search_event(engine)
    print('Searching for fed data')
    get_fed_data(engine)
    print('Searching for market prices')
    get_market_prices(engine)
    print('processing database')
    process_db(engine)
    return final_db(engine)

if __name__ == '__main__':
    engine = db.create_engine('sqlite:///../data/raw/data.db')
    get_all_data(engine)