from airsim_client import *
import pprint
import os
import tensorflow as tf
import pickle

from image_helper import loadgray
from tf_softmax_layer import inference

TMPFILE = 'active.png'
PARAMFILE = 'params.pkl'
IMGSIZE = 1032
INITIAL_THROTTLE= 0.65
BRAKING_DURATION = 15

# connect to the AirSim simulator 
client = CarClient()
client.confirmConnection()
print('Connected')
client.enableApiControl(True)
car_controls = CarControls()

client.reset()

# go forward
car_controls.throttle = INITIAL_THROTTLE
car_controls.steering = 0
client.setCarControls(car_controls)

# Load saved training params as ordinary NumPy
W,b = pickle.load(open('params.pkl', 'rb'))

with tf.Graph().as_default():

    # Placeholder for an image
    x = tf.placeholder('float', [None, IMGSIZE])

    # Our inference engine, intialized with weights we just loaded
    output = inference(x, IMGSIZE, 2, W, b)

    # TensorFlow initialization boilerplate
    sess = tf.Session()
    init_op = tf.global_variables_initializer()
    sess.run(init_op)

    # Once the brakes come on, we need to keep them on for a while before exiting; otherwise,
    # the vehicle will resume moving.
    brakingCount = 0

    # Loop until we detect a collision
    while True:

        # Get RGBA camera images from the car
        responses = client.simGetImages([ImageRequest(1, AirSimImageType.Scene)])

        # Save it to a temporary file
        image = responses[0].image_data_uint8
        AirSimClientBase.write_file(os.path.normpath(TMPFILE), image)

        # Read-load the image as a grayscale array
        image = loadgray(TMPFILE)

        # Run the image through our inference engine.
        # Engine returns a softmax output inside a list, so we grab the first
        # element of the list (the actual softmax vector), whose second element
        # is the absence of an obstacle.
        safety = sess.run(output, feed_dict={x:[image]})[0][1]

        # Slam on the brakes if it ain't safe!
        if safety < 0.5:

            if brakingCount > BRAKING_DURATION:
                print('BRAKING TO AVOID COLLISSION')
                break
            
            car_controls.brake = 1.0
            client.setCarControls(car_controls)

            brakingCount += 1
            
        # Wait a bit on each iteration
        time.sleep(0.1)

client.enableApiControl(False)
