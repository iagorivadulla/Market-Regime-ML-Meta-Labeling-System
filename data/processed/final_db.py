import pandas as pd
import sqlalchemy as db

def final_db(engine):
    #engine = db.create_engine('sqlite:///../raw/data.db')

    stocks = pd.read_sql('SELECT * FROM stocks_processed', engine)
    fed = pd.read_sql('SELECT * FROM macro_processed', engine)
    events = pd.read_sql('SELECT * FROM events_processed', engine)
    event_day = pd.read_sql('SELECT * FROM events_countdown', engine)

    for df_temp in [stocks, fed, events, event_day]:
        df_temp['date'] = pd.to_datetime(df_temp['date'])
        df_temp.set_index('date', inplace=True)

    # Usar stocks como base y hacer join, rellenando huecos con ffill
    df = stocks.join([events, fed, event_day], how='left')
    df = df.ffill()
    df = df.dropna(how='all')

    # Cortar hasta hoy
    today = pd.Timestamp.today().normalize()
    df = df[df.index <= today]

    return df