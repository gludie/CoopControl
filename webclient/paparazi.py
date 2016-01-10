#!/usr/bin/env python
import picamera
from time import sleep

camera = picamera.PiCamera()
camera.resolution = (640,480)
camera.quality = 85
camera.rotation = 270

filename = "/var/www/chickens/snapshot.jpg"

print "Capturing a foto"
sleep(1)
camera.capture(filename)

#print "Reference: https://www.raspberrypi.org/documentation/usage/camera/python/README.md"

