from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Float, Text
from sqlalchemy.orm import sessionmaker, DeclarativeBase


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
    phone = Column(String)


class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    address = Column(String, nullable=True)


class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'))
    link = Column(String)
    price = Column(Float, nullable=True)
    additional_info = Column(Text, nullable=True)


engine = create_engine('sqlite:///db.sqlite')
Base.metadata.create_all(engine)


Session = sessionmaker(bind=engine)
