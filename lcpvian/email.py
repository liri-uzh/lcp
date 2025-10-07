import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

MAIL_SERVER = os.getenv("MAIL_SERVER", "")
MAIL_PORT = os.getenv("MAIL_PORT", "50")
MAIL_SUBJECT_PREFIX = os.getenv("MAIL_SUBJECT_PREFIX", "")
MAIL_FROM_EMAIL = os.getenv("MMAIL_FROM_EMAIL", "")


def send_email(to: str | list[str], subject: str, message: str):
    message_html = message
    message_plain = message.replace("<br>", "\n")
    message_plain = re.sub(r"</?[^>]*>", "", message_plain)

    main_to: str = to if isinstance(to, str) else to[0]

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"{MAIL_SUBJECT_PREFIX}{subject} [LCP]"
        msg["From"] = MAIL_FROM_EMAIL
        msg["To"] = main_to
        msg.attach(MIMEText(message_html, "html", "utf-8"))
        msg.attach(MIMEText(message_plain, "plain"))

        s = smtplib.SMTP(MAIL_SERVER, int(MAIL_PORT))
        s.sendmail(MAIL_FROM_EMAIL, to, msg.as_string())
        s.quit()
    except Exception as e:
        print(f"Could not send an email to {', '.join(str(x) for x in to)}.", e)
        print(f"HTML email: {message_html}")
