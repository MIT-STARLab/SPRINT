import RPi.GPIO as GPIO
import time

def light_toggle(rxsnd, where, state):
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    #blue: receive from ground
    #green: send to groudn
    #yellow: send to cs
    #red: receive from cs
    if rxsnd == 'r':
        if where == 'G0':
            color = 'blue'
        else:
            color = 'red'
    else:
        if where == 'G0':
            color = 'green'
        else:
            color = 'yellow'

    color_dict = {
        'red':17,
        'yellow':18,
        'green':22,
        'blue':23
    }

    pin = color_dict[color] 
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, state)
