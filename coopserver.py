#!/usr/bin/env python

# Thanks to Ryan Detzel for his effort on initial CoopDoor
# Check also https://github.com/ryanrdetzel !

# Adaptions:
# ----------
# Enhance logging
# Fixed initial state 
# Eliminate second chance and temperature
# Other email (smtp)
# Change status message for webclient
#
# Todo:
# -----
# proper config handling
# using any push client api for apps (mobile support)
# propably use checkTime for blinking state instead of extra thread for manual mode (save ressources)

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
import ConfigParser
import string

#custom coopmailer (simple ssl smtp mailer)
from coopmailer import CoopMailer


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler('/var/log/coopserver.log')
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)

class Coop(object):
    # CHECKTIMEINTERVAL ... Interval to check times for opening and closing in seconds
    CHECKTIMEINTERVAL = 1
    MAX_CHECKTIME_HEARTBEAT = 5*60
    # SERVERPORT ... port to send commands 
    SERVERPORT = 55567
    # MAX_MANUAL_MODE_TIME ... Leaving manual mode and went to AUTO
    MAX_MANUAL_MODE_TIME = 60*60
    # MAX_MOTOR_ON ... After n seconds if open or closed not reached, emergency mode set
    MAX_MOTOR_ON = 45
    # TIMEZONE for astral (sunset,sunrise)
    TIMEZONE_CITY = 'Vienna'
    # OFFSET/DELAY in minutes
    AFTER_SUNSET_DELAY = 30
    AFTER_SUNRISE_DELAY = 60
    
    # Internal status values
    IDLE = UNKNOWN = NOT_TRIGGERED = AUTO = 0
    UP = OPEN = TRIGGERED = MANUAL = 1
    DOWN = CLOSED = HALT = 2

    #Status pin
    PIN_LED = 5

    #Input pins for manual steering
    PIN_BUTTON_UP = 13
    PIN_BUTTON_DOWN = 19

    #top and bottom sensor of the door (typically hal sensors)
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
        self.cache = {}

        logger.info("__init()__: CoopServer Service starting ...")

        #just a simple (ssl) smtp mail wrapper
        #what does, what it should do for chickens
        #the defaults (pipis@gmx.at) should be fine with us
        self.coopmailer = CoopMailer()

        a = Astral()
        self.city = a[Coop.TIMEZONE_CITY]

        self.setupPins()
        GPIO.output(Coop.PIN_LED, GPIO.HIGH)

        # Initialize Mode 
        self.changeDoorMode(Coop.AUTO)

        # Initialize Door Status via stopDoor Method
        self.stopDoor(0)

        # Start the Workers for Triggers and Times
        t1 = Thread(target = self.checkTriggers)
        t2 = Thread(target = self.checkTime)
        t1.setDaemon(True)
        t2.setDaemon(True)

        logger.info("__init()__: Starting daemon for Triggers ...")
        t1.start()
        logger.info("__init()__: Started daemon for Triggers.")

        logger.info("__init()__: Starting daemon for Times ...")
        t2.start()
        logger.info("__init()__: Started daemon for Time.")

        # networking stuff, e.g. webclient
        host = 'localhost'
        port = Coop.SERVERPORT 
        addr = (host, port)

        serversocket = socket(AF_INET, SOCK_STREAM)
        serversocket.bind(addr)
        serversocket.listen(2)

        logger.info("__init()__: Network connections accepted on:" + str(Coop.SERVERPORT))

        # add callback eventhandler buttonPress
        GPIO.add_event_detect(Coop.PIN_BUTTON_UP, GPIO.RISING, callback=self.buttonPress, bouncetime=200)
        GPIO.add_event_detect(Coop.PIN_BUTTON_DOWN, GPIO.RISING, callback=self.buttonPress, bouncetime=200)

        logger.info("__init()__: CoopServer Service started.")
        logger.info("__init()__: Status: {" + self.getStatus().replace("\n", " | ") + "}")
        
        while True:
            try:
                logger.info("__init()__: Server is listening for connections\n")
                clientsocket, clientaddr = serversocket.accept()
                thread.start_new_thread(self.handler, (clientsocket, clientaddr))
            except KeyboardInterrupt:
                break
            time.sleep(0.01)

        logger.info("__init()__: CoopServer Service stopping ...")
        logger.info("__init()__: Close connection")
        GPIO.output(Coop.PIN_LED, GPIO.LOW)
        serversocket.close()
        self.stopDoor(0)
        GPIO.cleanup()
        

    def setupPins(self):
        GPIO.setmode(GPIO.BCM)

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
            logger.info("closeDoor(): Door is already closed")
            self.door_status = Coop.CLOSED
            return
        logger.info("closeDoor(): Closing door")
        self.started_motor = datetime.datetime.now()
        GPIO.output(Coop.PIN_MOTOR_ENABLE, GPIO.HIGH)
        GPIO.output(Coop.PIN_MOTOR_A, GPIO.LOW)
        GPIO.output(Coop.PIN_MOTOR_B, GPIO.HIGH)
        self.direction = Coop.DOWN

    def openDoor(self):
        (top, bottom) = self.currentTriggerStatus()
        if (top == Coop.TRIGGERED):
            logger.info("openDoor(): Door is already open")
            self.door_status = Coop.OPEN
            return
        logger.info("openDoor(): Opening door")
        self.started_motor = datetime.datetime.now()
        GPIO.output(Coop.PIN_MOTOR_ENABLE, GPIO.HIGH)
        GPIO.output(Coop.PIN_MOTOR_A, GPIO.HIGH)
        GPIO.output(Coop.PIN_MOTOR_B, GPIO.LOW)
        self.direction= Coop.UP

    def stopDoor(self, delay):
        if self.direction != Coop.IDLE:
            logger.info("stopDoor(): Stop door")
            time.sleep(delay)
            GPIO.output(Coop.PIN_MOTOR_ENABLE, GPIO.LOW)
            GPIO.output(Coop.PIN_MOTOR_A, GPIO.LOW)
            GPIO.output(Coop.PIN_MOTOR_B, GPIO.LOW)
            self.direction = Coop.IDLE
            self.started_motor = None

        (top, bottom) = self.currentTriggerStatus()
        if (top == Coop.TRIGGERED):
            logger.info("stopDoor(): Coop door is open")
            self.door_status = Coop.OPEN
        elif (bottom == Coop.TRIGGERED):
            logger.info("stopDoor(): Coop door is closed")
            self.door_status = Coop.CLOSED
        else:
            logger.info("stopDoor(): Coop door is in an unknown state")
            self.door_status = Coop.UNKNOWN
            
    def emergencyStopDoor(self, reason):
        ## Just shut it off no matter what
        logger.info("emergencyStopDoor(): " + reason)
        GPIO.output(Coop.PIN_MOTOR_ENABLE, GPIO.LOW)
        GPIO.output(Coop.PIN_MOTOR_A, GPIO.LOW)
        GPIO.output(Coop.PIN_MOTOR_B, GPIO.LOW)
        self.direction = Coop.IDLE
        self.started_motor = None
        self.changeDoorMode(Coop.HALT)
        self.stopDoor(0)
        self.sendEmail('Coop Home Emergency STOP', reason)

    def sendEmail(self, subject, content):
        logger.info("Sending email: %s" % subject)
        try:
            self.coopmailer.sendCoopStatus(subject,content) 
        except Exception as e:
            logger.error("Error: " + str(e))

    def checkTime(self):
        # set to MAX Value, so that we got a info at the first run, not only in MAX_CHECKTIME_HEARTBEAT secs ...
        checkTime_heartbeat = Coop.MAX_CHECKTIME_HEARTBEAT
        while True:
            if self.door_mode == Coop.AUTO:
                current = datetime.datetime.now(pytz.timezone(self.city.timezone))
                sun = self.city.sun(date=datetime.datetime.now(), local=True)
                after_sunset = sun["sunset"] + datetime.timedelta(minutes = Coop.AFTER_SUNSET_DELAY)
                after_sunrise = sun["sunrise"] + datetime.timedelta(minutes = Coop.AFTER_SUNRISE_DELAY)

                if (current < after_sunrise or current > after_sunset) and self.door_status != Coop.CLOSED and self.direction != Coop.DOWN:
                    logger.info("checkTime(): Door should be closed based on time of day")
                    self.closeDoor()
                elif current > after_sunrise and current < after_sunset and self.door_status != Coop.OPEN and self.direction != Coop.UP:
                    logger.info("checkTime(): Door should be open based on time of day")
                    self.openDoor()

            # just for testing if thread dies
            checkTime_heartbeat += 1
            if (checkTime_heartbeat > Coop.MAX_CHECKTIME_HEARTBEAT):
                logger.info("checkTime(): I'm alive, generate next heartbeat log entry in " + str(Coop.MAX_CHECKTIME_HEARTBEAT) + " secs ... check times for opening and closing every " + str(Coop.CHECKTIMEINTERVAL) + " secs.");
                checkTime_heartbeat = 0
            
            time.sleep(Coop.CHECKTIMEINTERVAL)
        

    def currentTriggerStatus(self):
        bottom = GPIO.input(Coop.PIN_SENSOR_BOTTOM)
        top = GPIO.input(Coop.PIN_SENSOR_TOP)
        return (top, bottom)

    def currentButtonStatus(self):
        button_down = GPIO.input(Coop.PIN_BUTTON_DOWN)
        button_up = GPIO.input(Coop.PIN_BUTTON_UP)
        return (button_up,button_down)

    def checkTriggers(self):
        while True:
            (top, bottom) = self.currentTriggerStatus()
            if (self.direction == Coop.UP and top == Coop.TRIGGERED):
                logger.info("checkTriggers(): Top sensor triggered")
                self.stopDoor(0)
            elif (self.direction == Coop.DOWN and bottom == Coop.TRIGGERED):
                logger.info("checkTriggers(): Bottom sensor triggered")
                self.stopDoor(1)

            # Check for issues
            # started_motor is set when turning on for up or down
            if self.started_motor is not None:
                if (datetime.datetime.now() - self.started_motor).seconds > Coop.MAX_MOTOR_ON:
                    self.emergencyStopDoor('Motor ran too long')
            
            # sleep some time, but seems to be quite to short ... let sleep longer than 0.01
            time.sleep(0.1)

    def changeDoorMode(self, new_mode):
        log_info = "changeDoorMode(new_mode =" + str(new_mode) + ", current_mode=" + str(self.door_mode) + ")"
                    
        if new_mode == self.door_mode:
            logger.info(log_info + ": Already in that mode ! - do nothing.")
            return

        if new_mode == Coop.AUTO:
            logger.info(log_info + ": Enter auto mode")
            self.door_mode = Coop.AUTO
            GPIO.output(Coop.PIN_LED, GPIO.HIGH)
        else:
            logger.info(log_info + ": Enter manual mode")
            self.door_mode = new_mode
            self.stopDoor(0)
            self.manual_mode_start = int(time.time())

            t2 = Thread(target = self.blink)
            t2.setDaemon(True)
            t2.start()

    def buttonPress(self, button):
        logger.info("buttonPress("+str(button)+"): triggered.")
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

    def blink(self):
        while(self.door_mode != Coop.AUTO):
            GPIO.output(Coop.PIN_LED, GPIO.LOW)
            time.sleep(1)
            GPIO.output(Coop.PIN_LED, GPIO.HIGH)
            time.sleep(1)
            if self.door_mode == Coop.MANUAL: 
                if int(time.time()) - self.manual_mode_start > Coop.MAX_MANUAL_MODE_TIME:
                    logger.info("blink(): In manual mode too long, switching")
                    self.changeDoorMode(Coop.AUTO)

    def getStatus(self):
        msg = "\nDoorstatus=>"
        
        if (self.door_status == Coop.CLOSED):
            msg += "CLOSED"
        elif (self.door_status == Coop.OPEN):
            msg += "OPEN"
        else:
            msg += "UNKNOWN"
        
        msg += "\nMode=>"
        if (self.door_mode == Coop.MANUAL):
            msg += "MANUAL"
        elif (self.door_mode == Coop.AUTO):
            msg += "AUTO"
        elif (self.door_mode == Coop.HALT):
            msg += "HALT"
        else:   
            msg += "UNKNOWN"
        
        (button_up, button_down) = self.currentButtonStatus()
        msg += "\nButton Up=>"+str(button_up)
        msg += "\nButton Down=>"+str(button_down)
    
        (top, bottom) = self.currentTriggerStatus()
        msg += "\nTrigger bottom=>"+str(bottom)
        msg += "\nTrigger top=>" + str(top)
        #status of motor
        msg += "\nMotorDirection=>" + str(self.direction)
        
        #sunset and sunrise
        current = datetime.datetime.now(pytz.timezone(self.city.timezone))
        sun = self.city.sun(date=datetime.datetime.now(), local=True)
        closing = sun["sunset"] + datetime.timedelta(minutes = Coop.AFTER_SUNSET_DELAY)
        opening  = sun["sunrise"] + datetime.timedelta(minutes = Coop.AFTER_SUNRISE_DELAY)
      
        fmt = "%a, %d %b %Y %H:%M:%S"
        msg += "\nCurrent time=>" + current.strftime(fmt)   
        msg += "\nOpening time=>" + opening.strftime(fmt)   
        msg += "\nClosing time=>" + closing.strftime(fmt)
        msg += "\nSunrise=>" + sun["sunrise"].strftime(fmt)
        msg += "\nSunset=>" + sun["sunset"].strftime(fmt)
        msg += "\nDawn=>" + sun["dawn"].strftime(fmt)
        msg += "\nDusk=>" + sun["dusk"].strftime(fmt)
 
        return msg


    def handler(self, clientsocket, clientaddr):
        logger.info("handler(): Accepted connection from: " + str(clientaddr))

        while True:
            data = clientsocket.recv(1024)
            addinfo = ""
            if not data:
                break
            else:
                data = data.strip()

                logger.info("handler(): Received request: " + data)

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
                    addinfo = self.getStatus()
                    logger.info("handler(): Send Status: {" + addinfo.replace("\n", " | ") + "}")
                     
                msg = "You sent me: %s" % data
                msg += "\n" + addinfo
                
                clientsocket.send(msg)
            time.sleep(0.01)
        clientsocket.close()

if __name__ == "__main__":
    coop = Coop()
