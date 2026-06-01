"""
Load POS transaction data into the database.
"""
import csv
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import Base, POSTransaction

# Database URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://store_user:store_pass@localhost:5432/store_intelligence"
)

def load_pos_transactions(csv_file: str):
    """Load POS transactions from CSV into database."""
    
    # Create engine and session
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Read CSV
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            transactions = list(reader)
        
        print(f"Loading {len(transactions)} POS transactions...")
        
        loaded = 0
        for row in transactions:
            # Check if transaction already exists
            existing = session.query(POSTransaction).filter_by(
                transaction_id=row['transaction_id']
            ).first()
            
            if existing:
                print(f"  ⊙ {row['transaction_id']} already exists")
                continue
            
            # Parse timestamp
            timestamp = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
            
            # Create transaction
            txn = POSTransaction(
                transaction_id=row['transaction_id'],
                store_id=row['store_id'],
                timestamp=timestamp,
                basket_value_inr=float(row['basket_value_inr'])
            )
            
            session.add(txn)
            loaded += 1
            print(f"  ✓ {row['transaction_id']} - ₹{row['basket_value_inr']}")
        
        session.commit()
        print(f"\n✓ Loaded {loaded} new transactions")
        print(f"✓ Total transactions in database: {session.query(POSTransaction).count()}")
        
    except Exception as e:
        session.rollback()
        print(f"✗ Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    load_pos_transactions("data/pos_transactions.csv")
