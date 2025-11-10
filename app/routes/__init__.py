"""
Routes Package
==============

This package contains all the route blueprints for the SwapSavvy Pro application.

Blueprints:
- auth_bp: Authentication routes (login, signup, logout, verification)
- main_bp: Main application routes (dashboard, explore, landing, guest mode)
- profile_bp: User profile management routes
- social_bp: Social features routes (follow, like, comment, messaging)

Each blueprint is registered in the main application factory.
"""

from .auth import auth_bp
from .main import main_bp
from .profile import profile_bp
from .social import social_bp

# Export all blueprints for easy access
__all__ = ['auth_bp', 'main_bp', 'profile_bp', 'social_bp']

# Package metadata
__version__ = '1.0.0'
__author__ = 'SwapSavvy Pro Team'
__description__ = 'Route blueprints for SwapSavvy Pro application'