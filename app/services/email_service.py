from flask_mail import Message
from flask import current_app
from app import mail
import logging

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    def send_verification_email(email, username, code):
        """Send email verification code"""
        try:
            msg = Message(
                subject="SwapSavvy Pro — Email Verification Code",
                recipients=[email],
                html=f"""
                <h2>SwapSavvy Pro Email Verification</h2>
                <p>Hi {username},</p>
                <p>Your verification code is: <strong>{code}</strong></p>
                <p>This code will expire in 10 minutes.</p>
                """
            )
            msg.body = f"Hi {username},\n\nYour verification code is: {code}\n\nThis code will expire in 10 minutes."
            mail.send(msg)
            logger.info(f"Verification email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {email}: {e}")
            return False

    @staticmethod
    def send_welcome_email(email, username):
        """Send welcome email after successful registration"""
        try:
            msg = Message(
                subject="Welcome to SwapSavvy Pro!",
                recipients=[email],
                html=f"""
                <h2>Welcome to SwapSavvy Pro!</h2>
                <p>Hi {username},</p>
                <p>Your account has been successfully created and verified.</p>
                <p>Start exploring the platform and connect with other professionals!</p>
                """
            )
            msg.body = f"Hi {username},\n\nWelcome to SwapSavvy Pro! Your account has been successfully created."
            mail.send(msg)
            logger.info(f"Welcome email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send welcome email to {email}: {e}")
            return False