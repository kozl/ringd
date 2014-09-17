#!/usr/bin/python
# -*- coding: utf-8 -*-
import cv2
import tweepy
import daemon
import signal
import os, os.path
import Image, ImageDraw
import RPi.GPIO as GPIO
from time import sleep
from datetime import datetime
from ConfigParser import ConfigParser
from lockfile.pidlockfile import PIDLockFile

config = ConfigParser()
config.read('/etc/ringd.conf')

LOGFILE = config.get('general', 'logfile')
PIDFILE = config.get('general', 'pidfile')
WORKDIR = config.get('general', 'workdir')

CONSUMER_KEY = config.get('authentication', 'consumer_key')
CONSUMER_SECRET = config.get('authentication', 'consumer_secret')
KEY = config.get('authentication', 'access_token_key')
SECRET = config.get('authentication', 'access_token_secret')



class MyPIDLockFile(PIDLockFile):
    def __enter__(self):
        self.acquire(0)
        return self

class RingDaemonContext(daemon.DaemonContext):
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        GPIO.cleanup()


def main():
    import RPi.GPIO as GPIO
    import logging, logging.handlers
    
    logger = logging.getLogger('ringd')
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(message)s")
    handler = logging.handlers.RotatingFileHandler(LOGFILE, 
                                                   maxBytes=5242880, 
                                                   backupCount=5)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    def capture_photo(*args, **kwargs):
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        if ret:
            frame = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame)
            (w, h) = image.size
            draw = ImageDraw.Draw(image)
            draw.text((20, h-20), "{0:%Y-%m-%d %H:%M:%S}".format(datetime.today()), fill="black")
            del draw
            filename = "{0:%Y-%m-%d_%H:%M:%S}.jpg".format(datetime.today())
            image.save(filename)
            logger.info("Captured file %s from webcam. Someone behind the door!" % filename)
            return True
        return False
    
    def tweet_photo(api, filename):
        try:
            api.update_with_media(filename, status="Ура! Кто-то пришел!")
            os.unlink(filename)
            logger.info("Sent tweet with photo %s" % filename)
        except tweepy.error.TweepError:
            pass
    
    # GPIO initial configuration
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(5, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(5, GPIO.FALLING)
    GPIO.add_event_callback(5, capture_photo, bouncetime=3000)
    
    # tweepy initialization
    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(KEY, SECRET)
    api = tweepy.API(auth)
    
    while True:
        filelist = [ os.path.join(WORKDIR, onefile) for onefile in sorted(filter(os.path.isfile, os.listdir(WORKDIR))) ]
        for onefile in filelist:
            tweet_photo(api, onefile)
        sleep(5)





context = RingDaemonContext(pidfile=MyPIDLockFile(PIDFILE),
                            working_directory=WORKDIR)

context.signal_map = {
    signal.SIGTERM: 'terminate',
    signal.SIGHUP: None,
    }


with context:
    main()
