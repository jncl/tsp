""" Email module """

import os

# Import smtplib for the actual sending function
import smtplib

# Import the email modules we'll need
from email.message import EmailMessage

from dataclasses import dataclass

@dataclass
class Email:
    """ email class """
    def __init__(self):
    	# Create the container email message.
        self.msg = EmailMessage()

    def send_mail(self, subject, body):
        """ send an email """

        self.msg['Subject'] = subject
        self.msg['From'] = "hogg.jon+tsp@gmail.com"
        self.msg['To'] = os.getenv("TS_MAILTO")

        self.msg.set_content(body)

        print(f"Email contents: {self.msg}")

        # determine how to send an email

    	# # Send the email via our own SMTP server.
        # with smtplib.SMTP('localhost') as s:
        #     s.send_message(self.msg)
