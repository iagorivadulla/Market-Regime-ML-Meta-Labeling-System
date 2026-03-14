import numpy as np
import sqlalchemy as db
import pandas as pd
import talib as ta


def process_db():
    engine = db.create_engine('sqlite:///../raw/data.db')

    # loads all tables from db splitting events if they have data or don't
    data_stocks = pd.read_sql('SELECT * FROM Stocks', con=engine)  # Loads Stocks table

    # get all dates from original dataframe
    data_stocks['date'] = pd.to_datetime(data_stocks['date'])
    # use date as index
    data_stocks = data_stocks.sort_values('date').set_index('date')

    def technical_analysis(df):
        close = df['close'].astype(float)
        high = df['high'].astype(float)
        low = df['low'].astype(float)
        volume = df['volume'].astype(float)

        # --- Overlap Studies ---
        df['EMA_14'] = ta.EMA(close, timeperiod=14)
        df['EMA_30'] = ta.EMA(close, timeperiod=30)
        df['EMA_60'] = ta.EMA(close, timeperiod=60)

        df['SMA_14'] = ta.SMA(close, timeperiod=14)
        df['SMA_30'] = ta.SMA(close, timeperiod=30)
        df['SMA_60'] = ta.SMA(close, timeperiod=60)

        df['BB_upper'], df['BB_middle'], df['BB_lower'] = ta.BBANDS(close, timeperiod=20)

        # --- Momentum Indicators ---
        df['RSI_14'] = ta.RSI(close, timeperiod=14)
        df['RSI_21'] = ta.RSI(close, timeperiod=21)
        df['RSI_30'] = ta.RSI(close, timeperiod=30)

        df['MACD'], df['MACD_signal'], df['MACD_hist'] = ta.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)

        df['AROON_down'], df['AROON_up'] = ta.AROON(high, low, timeperiod=14)

        df['MFI'] = ta.MFI(high, low, close, volume, timeperiod=14)

        # --- Price Transform ---
        df['AVGPRICE'] = ta.AVGPRICE(df['open'], high, low, close)
        df['MEDPRICE'] = ta.MEDPRICE(high, low)

        df = df.dropna()

        return df

    df_sp500 = technical_analysis(data_stocks[data_stocks['ticker'] == 'SPY'])
    df_qqq = technical_analysis(data_stocks[data_stocks['ticker'] == 'QQQ'])
    df_vix = technical_analysis(data_stocks[data_stocks['ticker'] == '^VIX'])
    df_dxy = technical_analysis(data_stocks[data_stocks['ticker'] == 'DX-Y.NYB'])
    df_gold = technical_analysis(data_stocks[data_stocks['ticker'] == 'GC=F'])

    def col_names(df):
        ticker_name = str(df['ticker'].iloc[0]).lower()

        df = df.drop(columns=['ticker'])

        df.columns = [f'{ticker_name}_{col}' for col in df.columns]

        return df

    df_sp500_format = col_names(df_sp500)
    df_qqq_format = col_names(df_qqq)
    df_vix_format = col_names(df_vix)
    df_dxy_format = col_names(df_dxy)
    df_gold_format = col_names(df_gold)

    df_stocks = pd.concat([df_sp500_format, df_qqq_format, df_vix_format, df_dxy_format, df_gold_format], axis=1)

    df_stocks = df_stocks.dropna(how='any')

    # defragment memory
    df_stocks = df_stocks.copy()

    #save here into db
    df_stocks.to_sql("stocks_processed", engine, if_exists="replace")


    # loads macro data table
    data_fed = pd.read_sql('SELECT * FROM Macro', con=engine)

    # get all dates from original dataframe
    data_fed['date'] = pd.to_datetime(data_fed['date'])
    # sort all unique dates
    all_dates = sorted(data_fed['date'].unique(), reverse=False)
    # create the new dataframe and set all sorted dates as index
    data_fed_transposed = pd.DataFrame(index=all_dates)

    cols = data_fed['serie'].unique()
    # creates one new colum for each serie and assign all the values into the correct date
    for column in cols:
        if column == 'SOFR':
            pass
        else:
            series_data = data_fed[data_fed['serie'] == column].set_index('date')['value']
            data_fed_transposed[column] = series_data

    # now we need to fill al Nans with the previous values
    data_fed_transposed = data_fed_transposed.ffill(axis=0)  # ffill

    data_fed_transposed = data_fed_transposed.dropna(axis=0, how='any')

    #save here data fed
    data_fed_transposed.to_sql("macro_processed", engine, if_exists="replace")



    # load events with data
    data_events = pd.read_sql('SELECT * FROM Events WHERE actual != "None" OR previous != "None"',
                              con=engine)

    # get all dates from original dataframe
    data_events['date'] = pd.to_datetime(data_events['date'])

    # Creates the transposed
    data_events_transposed = data_events.pivot_table(
        index='date',
        columns='event',
        values='actual',
        aggfunc='first'
    )

    # fill forward
    data_events_transposed = data_events_transposed.ffill(axis=0)

    data_events_transposed = data_events_transposed.dropna(axis=0, how='any')

    #clean the values in event
    def clean_values(val):
        if not isinstance(val, str):
            return val

        val = val.strip().replace(',', '').replace(' ', '')

        if val in ('', '-', 'N/A', 'nan'):
            return np.nan

        prefix = ''
        if val.startswith('<') or val.startswith('>'):
            prefix = val[0]
            val = val[1:]

        try:
            if val.endswith('%'):
                return float(val[:-1]) / 100
            elif val.upper().endswith('M'):
                return float(val[:-1]) * 1000000
            elif val.upper().endswith('K'):
                return float(val[:-1]) * 1000
            elif val.upper().endswith('B'):
                return float(val[:-1]) * 1000000000
            else:
                return float(val)
        except ValueError:
            return val

    data_events_clean = data_events_transposed.apply(lambda col: col.map(clean_values))

    #save here data events
    data_events_clean.to_sql("events_processed", engine, if_exists="replace")



    # load events without data
    events_no_data = pd.read_sql('SELECT * FROM Events WHERE actual = "None" AND previous = "None"',
                                 con=engine)

    # manually adds next event date, all of them are Mar 18 2026
    future_event_dates = pd.to_datetime('2026-03-18')
    cols = events_no_data['event'].unique()

    last_event = pd.DataFrame({
        'date': [future_event_dates] * len(cols),  # number of events
        'event': cols
    })

    # concat this event to the original df
    events_no_data = pd.concat([events_no_data, last_event], ignore_index=True)

    # format dates into datetime
    events_no_data['date'] = pd.to_datetime(events_no_data['date'])

    # creates a new col for the event day
    events_no_data['event_date'] = events_no_data['date']
    events_no_data['event_value'] = events_no_data['date']

    # pivots one col for event
    df_pivot = events_no_data.pivot_table(index='event_date',
                                          columns='event',
                                          values='event_value',  # use a copy to avoid errors
                                          aggfunc='first')

    # creates a diary index for range
    first_date = df_pivot.index.min()
    last_date = df_pivot.index.max()
    diary_index = pd.date_range(start=first_date, end=last_date, freq='D')

    # reindex to include all days
    df_diary = df_pivot.reindex(diary_index)

    # backfill the dates
    future_dates = df_diary.bfill()

    # calculates the countdown for every date
    df_countdown = future_dates.apply(lambda x: (x - future_dates.index).dt.days)

    df_countdown.index.name = 'date'

    #save here
    df_countdown.to_sql("events_countdown", engine, if_exists="replace")

if __name__ == '__main__':
    process_db()
