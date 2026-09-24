from pymongo import MongoClient
import os

MONGO_URL = os.getenv("MONGO_URL", "mongodb://ventas_app:ventas123@ventas-db:27017/")
client = MongoClient(MONGO_URL)
db = client.tienda_ventas

def get_db():
    return db
