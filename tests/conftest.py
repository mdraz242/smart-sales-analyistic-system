import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models.store import Store
from backend.app.models.product import Product, ProductCategory, ProductCategoryMapping
from backend.app.models.customer import Customer
from backend.app.models.order import Order, OrderItem, Refund, RefundItem, OrderCoupon
from backend.app.models.cost import ProductCostHistory
from backend.app.services.analytics_engine import AnalyticsEngine
from backend.app.services.sample_data_generator import generate_sample_dataset


@pytest.fixture(scope="session")
def engine():
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(test_engine)
    return test_engine


@pytest.fixture(scope="function")
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="session")
def populated_db(engine):
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    store = generate_sample_dataset(session, seed=123)
    yield session, store
    session.close()
