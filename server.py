import os
import logging
import requests
from socket import *
from threading import Thread
import thread
import pytz
import time
import sys
import glob
import datetime
import RPi.GPIO as GPIO
from astral import Astral

# Hold either button for 2 seconds to switch modes
# In auto buttons Stop for 60 seconds. Again, continues
# In manual, left goes up assuming it's not up. right goes down assuming
#  any button while moving stops it
# Todo:
# Record how long it takes to open the door, close
# ERror states

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler('/tmp/log.log')
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)


class Coop(object):
    MAX_MANUAL_MODE_TIME = 60 * 60
    MAX_MOTOR_ON = 45
    TEMP_INTERVAL = 60 * 5
    TIMEZONE_CITY = 'Vienna'
    AFTER_SUNSET_DELAY = 60
    AFTER_SUNRISE_DELAY = 3 * 60
    SECOND_CHANCE_DELAY = 60 * 10
    IDLE = UNKNOWN = NOT_TRIGGERED = AUTO = 0
    UP = OPEN = TRIGGERED = MANUAL = 1
    DOWN = CLOSED = HALT = 2

    #Status pin
    PIN_LED = 5
    #Input pins for manual steering
    PIN_BUTTON_UP = 13
    PIN_BUTTON_DOWN = 19
    #top and bottom sensor of the door (typically hal)
    PIN_SENSOR_TOP = 20
    PIN_SENSOR_BOTTOM = 21
    #Motor (H-Bridge using !)
    PIN_MOTOR_ENABLE = 18
    PIN_MOTOR_A = 12
    PIN_MOTOR_B = 16

    def __init__(self):
        self.door_status = Coop.UNKNOWN
        self.started_motor = None 
        self.direction = Coop.IDLE
        self.door_mode = Coop.AUTO
        self.manual_mode_start = 0
        self.second_chance = True
        self.cache = {}

        self.mail_key = os.environ.get('MAILGUN_KEY') or exit('You need a key set')
        self.mail_url = os.environ.get('MAILGUN_URL') or exit('You need a key set')
        self.mail_recipient = os.environ.get('MAILGUN_RECIPIENT') or exit('You need a key set')

        a = Astral()
        self.city = a[Coop.TIMEZONE_CITY]
        self.setupPins()

        t1 = Thread(target = self.checkTriggers)
        t2 = Thread(target = self.checkTime)
        t1.setDaemon(True)
        t2.setDaemon(True)
        t1.start()
        t2.start()

        host = 'localhost'
        port = 55567
        addr = (host, port)

        serversocket = socket(AF_INET, SOCK_STREAM)
        serversocket.bind(addr)
        serversocket.listen(2)

        self.changeDoorMode(Coop.AUTO)
        self.stopDoor(0)

        GPIO.add_event_detect(Coop.PIN_BUTTON_UP, GPIO.RISING, callback=self.buttonPress, bouncetime=200)
        GPIO.add_event_detect(Coop.PIN_BUTTON_DOWN, GPIO.RISING, callback=self.buttonPress, bouncetime=200)

        while True:
            try:
                logger.info("Server is listening for connections\n")
                clientsocket, clientaddr = serversocket.accept()
                thread.start_new_thread(self.handler, (clientsocket, clientaddr))
            except KeyboardInterrupt:
                break
            time.sleep(0.01)

        logger.info("Close connection")
        GPIO.output(Coop.PIN_LED, GPIO.LOW)
        serversocket.close()
        self.stopDoor(0)

    def setupPins(self):
        GPIO.setmode(GPIO.BOARD)

        GPIO.setup(Coop.PIN_MOTOR_ENABLE, GPIO.OUT)
        GPIO.setup(Coop.PIN_MOTOR_A, GPIO.OUT)
        GPIO.setup(Coop.PIN_MOTOR_B, GPIO.OUT)
        GPIO.setup(Coop.PIN_LED, GPIO.OUT)
        GPIO.setup(Coop.PIN_SENSOR_BOTTOM, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(Coop.PIN_SENSOR_TOP, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(Coop.PIN_BUTTON_UP, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(Coop.PIN_BUTTON_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    def closeDoor(self):
        (top, bottom) = self.currentTriggerStatus()
        if (bottom == Coop.TRIGGERED):
            logger.info("Door is already closed")
            return
        logger.info("Closing door")
        self.started_motor = datetime.datetime.now()
        GPIO.output(Coop.PIN_MOTOR_ENABLE, GPIO.HIGH)
        GPIO.output(Coop.PIN_MOTOR_A, GPIO.LOW)
        GPIO.output(Coop.PIN_MOTOR_B, GPIO.HIGH)
        self.direction = Coop.DOWN

    def openDoor(self):
        (top, bottom) = self.currentTriggerStatus()
        if (top == Coop.TRIGGERED):
            logger.info("Door is already open")
            return
        logger.info("Opening door")
        self.started_motor = datetime.datetime.now()
        GPIO.output(Coop.PIN_MOTOR_ENABLE, GPIO.HIGH)
        GPIO.output(Coop.PIN_MOTOR_A, GPIO.HIGH)
        GPIO.output(Coop.PIN_MOTOR_B, GPIO.LOW)
        self.direction= Coop.UP

    def stopDoor(self, delay):
        if self.direction != Coop.IDLE:
            logger.info("Stop door")
            time.sleep(delay)
            GPIO.output(Coop.PIN_MOTOR_ENABLE, GPIO.LOW)
            GPIO.output(Coop.PIN_MOTOR_A, GPIO.LOW)
            GPIO.output(Coop.PIN_MOTOR_B, GPIO.LOW)
            self.direction = Coop.IDLE
            self.started_motor = None

        (top, bottom) = self.currentTriggerStatus()
        if (top == Coop.TRIGGERED):
            logger.info("Door is open")
            self.door_status = Coop.OPEN
            self.sendEmail('Coop door is OPEN', 'Yay!')
        elif (bottom == Coop.TRIGGERED):
            logger.info("Door is closed")
            self.door_status = Coop.CLOSED
            self.sendEmail('Coop door is CLOSED', 'Yay!')
        else:
            logger.info("Door is in an unknown state")
            self.door_status = Coop.UNKNOWN
            self.sendEmail('Coop door is UNKNOWN', 'Oops!')
            
            #payload = {'status': self.door_status, 'ts': datetime.datetime.now() }
            #self.postData('door', payload)

    def emergencyStopDoor(self, reason):
        ## Just shut it off no matter what
        logger.info("Emergency Stop door: " + reason)
        GPIO.output(Coop.PIN_MOTOR_ENABLE, GPIO.LOW)
        GPIO.output(Coop.PIN_MOTOR_A, GPIO.LOW)
        GPIO.output(Coop.PIN_MOTOR_B, GPIO.LOW)
        self.direction = Coop.IDLE
        self.started_motor = None
        self.changeDoorMode(Coop.HALT)
        self.stopDoor(0)
        self.sendEmail('Coop Emergency STOP', reason)

    def sendEmail(self, subject, content):
        logger.info("Sending email: %s" % subject)
        try:
            request = requests.post(
                self.mail_url,
                auth=("api", self.mail_key),
                data={"from": "Pippis <pippis@mailgun.dxxd.net>",
                      "to": [self.mail_recipient],
                      "subject": subject,
                      "text": content}) 
            #logger.info('Status: {0}'.format(request.status_code))
        except Exception as e:
            logger.error("Error: " + e)

 #   def postData(self, endpoint, payload):
 #       try:
 #           r = requests.post("http://yourhost.com:port/api/" + endpoint, data=payload)
 #       except Exception as e:
 #           logger.error(e)
    def getSunsetrise()
        current = datetime.datetime.now(pytz.timezone(self.city.timezone))
        sun = self.city.sun(date=datetime.datetime.now(), local=True)
        after_sunset = sun["sunset"] + datetime.timedelta(minutes = Coop.AFTER_SUNSET_DELAY)
        after_sunrise = sun["sunrise"] + datetime.timedelta(minutes = Coop.AFTER_SUNRISE_DELAY) 
        
        return (after_sunset, after_sunrise)
        
    def checkTime(self):
        while True:
            if self.door_mode == Coop.AUTO:
                (after_sunset, after_sunrise) = getSunsetrise()

                if (current < after_sunrise or current > after_sunset) and self.door_status != Coop.CLOSED and self.direction != Coop.DOWN:
                    logger.info("Door should be closed based on time of day")
                    self.closeDoor()

                    if self.second_chance:
                        t2 = Thread(target = self.secondChance)
                        t2.setDaemon(True)
                        t2.start()
                elif current > after_sunrise and current < after_sunset and self.door_status != Coop.OPEN and self.direction != Coop.UP:
                    logger.info("Door should be open based on time of day")
                    self.openDoor()
            time.sleep(1)

    def currentTriggerStatus(self):
        bottom = GPIO.input(Coop.PIN_SENSOR_BOTTOM)
        top = GPIO.input(Coop.PIN_SENSOR_TOP)
        return (top, bottom)

    def checkTriggers(self):
        while True:
            (top, bottom) = self.currentTriggerStatus()
            if (self.direction == Coop.UP and top == Coop.TRIGGERED):
                logger.info("Top sensor triggered")
                self.stopDoor(0)
            if (self.direction == Coop.DOWN and bottom == Coop.TRIGGERED):
                logger.info("Bottom sensor triggered")
                self.stopDoor(1)

            # Check for issues
            # started_motor is set when turning on for up or down
            if self.started_motor is not None:
                if (datetime.datetime.now() - self.started_motor).seconds > Coop.MAX_MOTOR_ON:
                    self.emergencyStopDoor('Motor ran too long')
			# sleep some time, but seems to be quite to short ... let sleep longer than 0.01
            time.sleep(0.1)

    def changeDoorMode(self, new_mode):
        if new_mode == self.door_mode:
            logger.info("Already in that mode")
            return

        if new_mode == Coop.AUTO:
            logger.info("Entered auto mode")
            self.door_mode = Coop.AUTO
            GPIO.output(Coop.PIN_LED, GPIO.HIGH)
        else:
            logger.info("Entered manual mode")
            self.door_mode = new_mode
            self.stopDoor(0)
            self.manual_mode_start = int(time.time())

            t2 = Thread(target = self.blink)
            t2.setDaemon(True)
            t2.start()

    def buttonPress(self, button):
        waiting = True
        start = end = int(round(time.time() * 1000))

        while GPIO.input(button) and waiting:
            end = int(round(time.time() * 1000))
            if end - start >= 2000:
                if self.door_mode == Coop.AUTO:
                    self.changeDoorMode(Coop.MANUAL)
                else:
                    self.changeDoorMode(Coop.AUTO)
                time.sleep(2)
                waiting = False
                return
            time.sleep(0.1)

        # Quick touch, what mode?
        if self.door_mode == Coop.MANUAL:
            if self.direction != Coop.IDLE:
                self.stopDoor(0)
            elif (button == Coop.PIN_BUTTON_UP):
                self.openDoor()
            else:
                self.closeDoor()

    def secondChance(self):
        logger.info("Starting second chance timer")
        time.sleep(Coop.SECOND_CHANCE_DELAY)
        if self.door_status == Coop.CLOSED or self.door_status == Coop.UNKNOWN:
            logger.info("Opening door for second chance")
            self.openDoor()
            time.sleep(Coop.SECOND_CHANCE_DELAY)
            logger.info("Closing door for the night")
            self.closeDoor()

    def blink(self):
        while(self.door_mode != Coop.AUTO):
            GPIO.output(Coop.PIN_LED, GPIO.LOW)
            time.sleep(1)
            GPIO.output(Coop.PIN_LED, GPIO.HIGH)
            time.sleep(1)
            if self.door_mode == Coop.MANUAL: 
                if int(time.time()) - self.manual_mode_start > Coop.MAX_MANUAL_MODE_TIME:
                    logger.info("In manual mode too long, switching")
                    self.changeDoorMode(Coop.AUTO)

    def getstatus():
        msg = "Doorstatus : "
        
        if (self.door_status == Coop.CLOSED):
            msg += " CLOSED"
        elif (self.door_status == Coop.OPEN):
            msg += " OPEN"
        else:
            msg += "UNKNOWN
        
        msg += "\nMode: "
        if (self.door_mode == Coop.MANUAL):
            msg += "MANUAL"
        elif (self.door_mode == Coop.AUTO):
            msg += "AUTO"
        else:
            msg += "UNKNOWN"
            
        msg += "\nTriggerstatus: "
        (top, bottom) = self.currentTriggerStatus()
        msg += "bottom(" + str(bottom) + "), top(" + str(top) +")"
        
        #sunset and sunrise
        (sunset, sunrise) = getSunsetrise()
        msg += ", Sunset: " + str(sunset) + ", Sunrise: " + str(sunrise)
        
        #self.sendEmail('Coop Status', msg)
        
        return msg


    def handler(self, clientsocket, clientaddr):
        #logger.info("Accepted connection from: %s " % clientaddr)

        while True:
            data = clientsocket.recv(1024)
            addinfo = ""
            if not data:
                break
            else:
                data = data.strip()
                if (data == 'stop'):
                    self.changeDoorMode(Coop.MANUAL)
                    self.stopDoor(0)
                elif (data == 'open'):
                    self.changeDoorMode(Coop.MANUAL)
                    self.openDoor()
                elif (data == 'close'):
                    self.changeDoorMode(Coop.MANUAL)
                    self.closeDoor()
                elif (data == 'manual'):
                    self.changeDoorMode(Coop.MANUAL)
                elif (data == 'auto'):
                    self.changeDoorMode(Coop.AUTO)
                elif (data == 'halt'):
                    self.changeDoorMode(Coop.HALT)
                elif (data == 'status'):
                    addinfo = self.getstatus()
                
                msg = "You sent me: %s" % data
                msg += "\n" addinfo
                
                clientsocket.send(msg)
            time.sleep(0.01)
        clientsocket.close()

if __name__ == "__main__":
    coop = Coop()
