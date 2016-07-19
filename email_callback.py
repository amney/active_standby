import smtplib
import argparse
from sys import argv
from platform import uname
from email.mime.text import MIMEText

# help: 
#	email_callback.py "message"
#
#	sends email to recipients 

# edit variables
me = 'apicmon@fqdn'
you = 'you@fqdn'

mailserver = '127.0.0.1'

# done with user variables

hostname = uname()[1]
script = argv[0]
active = argv[1]
stndby = argv[2]
info = argv[3]

body = """
ACI APIC monitor script ran this callback:

running on :	%s
script name:	%s

desired active:	%s
desired stndby:	%s

info:	
%s
""" % (hostname, script, active, stndby, info)

msg = MIMEText(body, "plain")


msg['Subject'] = 'ACI APIC Monitor - active_standby - callback'
msg['From'] = me
msg['To'] = you 

try:
	s = smtplib.SMTP(mailserver)
	s.sendmail(me, [you], msg.as_string())
	s.quit()

	#print "Successfully sent email"
except SMTPException:
	print("Error: unable to send email")
