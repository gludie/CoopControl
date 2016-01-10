# Import smtplib to provide email functions
#import smtplib
from smtplib import SMTP_SSL as SMTP 
 
# Import the email modules
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
 
class CoopMailer(object):
    
    # Define email addresses to use
    ADDR_TO   = '_TO_ADDRESS'
    ADDR_FROM = '_FROM_ADDRESS'

    # Define SMTP email server details
    SMTP_SERVER = 'YOURMAILSERVER'
    SMTP_USER   = 'YOURMAILACCOUNT'
    SMTP_PASS   = 'YOURMAILPWD'

    def __init__(self):
        self.addr_to=CoopMailer.ADDR_TO
        self.addr_from=CoopMailer.ADDR_FROM
        
        self.smtp_server = CoopMailer.SMTP_SERVER
        self.smtp_user = CoopMailer.SMTP_USER
        self.smtp_pass = CoopMailer.SMTP_PASS
        
    def setAddrTo(self, sendto):
        self.addr_to = sendto
   
    def setAddrFrom(self, sendfrom):
        self.addr_from = sendfrom
    
    def setSMTPServer(self, smtp_server):
        self.smtp_server = smtp_server
        
    def setSMTPCredentials(self, smtp_user, smtp_pass):
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
    
    def sendCoopStatus(self, subject = 'Gock gock', text = 'Gack gack'):
        # Construct email
        msg = MIMEMultipart('alternative')
        msg['To'] = self.addr_to
        msg['From'] = self.addr_from
        msg['Subject'] = subject

        # Record the MIME types of both parts - text/plain and text/html.
        part1 = MIMEText(text, 'plain')
        #part2 = MIMEText(html, 'html')

        # Attach parts into message container.
        # According to RFC 2046, the last part of a multipart message, in this case
        # the HTML message, is best and preferred.
        msg.attach(part1)
        #msg.attach(part2)

        # Send the message via an SMTP server
        s = SMTP(self.smtp_server)
        s.login(self.smtp_user,self.smtp_pass)
        s.sendmail(self.addr_from, self.addr_to, msg.as_string())
        s.quit()

