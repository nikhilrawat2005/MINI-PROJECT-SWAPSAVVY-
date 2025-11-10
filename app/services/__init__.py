"""
Services Package
================

This package contains all the business logic and service layers for the SwapSavvy Pro application.

Services:
- UserService: User management, authentication, profile operations
- EmailService: Email sending and template management

These services are used by route handlers to separate business logic from presentation logic.
"""

from .user_service import UserService
from .email_service import EmailService

# Export all services for easy access
__all__ = ['UserService', 'EmailService']

# Package metadata
__version__ = '1.0.0'
__author__ = 'SwapSavvy Pro Team'
__description__ = 'Business logic services for SwapSavvy Pro application'

# Service instances for easy access
user_service = UserService()
email_service = EmailService()