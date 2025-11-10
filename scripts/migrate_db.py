#!/usr/bin/env python3
"""
Database migration and setup script
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User

def setup_database():
    """Initialize database with proper migrations"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Setting up database...")
        
        try:
            # Run migrations
            from flask_migrate import upgrade
            upgrade()
            
            print("✅ Database migrations applied successfully!")
            
        except Exception as e:
            print(f"❌ Database setup error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    setup_database()