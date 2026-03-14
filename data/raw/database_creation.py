import sqlalchemy as db

#creates the database as data.db
engine = db.create_engine('sqlite:///../data/raw/data.db')

#connection object
conn = engine.connect()

#extracting the metadata
metadata = db.MetaData()

#creates the table for diary prices
Stocks = db.Table('Stocks', metadata,
                 db.Column('date', db.DateTime, primary_key=True),
                 db.Column('ticker', db.String(6), nullable=False, primary_key=True),
                 db.Column('open', db.Float, nullable=False),
                 db.Column('high', db.Float, nullable=False),
                 db.Column('low', db.Float, nullable=False),
                 db.Column('close', db.Float, nullable=False),
                 db.Column('volume', db.BigInteger, nullable=False),
                 )

#creates the table for macro
Macro = db.Table('Macro', metadata,
                 db.Column('date', db.DateTime, primary_key=True),
                 db.Column('serie', db.String(10), nullable=False, primary_key=True), #the name of the macro data
                 db.Column('value', db.Float, nullable=False),
                 )

#creates the table for events
Events = db.Table('Events', metadata,
                  db.Column('date', db.DateTime, primary_key=True),
                  db.Column('event', db.String(100), nullable=False, primary_key=True),
                  db.Column('actual', db.String(100), nullable=True),
                  db.Column('previous', db.String(100), nullable=True),
                  )



metadata.create_all(engine)
conn.close()