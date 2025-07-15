# pylint: disable=logging-fstring-interpolation
# vim: set ts=4 sts=4 sw=4 et tw=0:
""" Email module """

# using info from here: https://realpython.com/python-send-email/

import logging

import subprocess
from email.message import EmailMessage

from dataclasses import dataclass

logger = logging.getLogger(__name__)

msg = EmailMessage()
SENDMAIL_LOCATION = "/usr/sbin/sendmail"


@dataclass
class Email:
    """ email class """
    @staticmethod
    def send_mail(msg_subject, msg_body):
        """ send an email """

        msg['Subject'] = msg_subject
        msg.set_content(msg_body)
        # msg['From'] = from_addr
        # msg['To'] = to_addrs

        logger.debug(f"Email contents: {msg}")

        try:
            subprocess.run([SENDMAIL_LOCATION], input=msg.as_bytes(), check=True)
            # subprocess.run([SENDMAIL_LOCATION, "-t", "-oi"], input=msg.as_bytes(), check=True)
        except Exception as e:
            logger.error(f"Email send error: {e}")
            raise
