'''
HumanGreeter is ispired by http://doc.aldebaran.com/2-5/dev/python/examples/vision/face_detection.html.
When the Pepper robot, defined in "app" session, receives a callback for event GazeAnalysis/PersonStartsLookingAtRobot,
disables its "ALBasicAwareness" module, present itself and capture some face images.
It saves only 5 valid images in "outputdir" based on "is_valid_image" method.
'''

#!/usr/bin/python
# -*- coding: UTF-8 -*-

import qi
import time
import sys
import argparse
import numpy as np
import os
import cv2

THRESHOLD_BLURRY = 70
SPEECH_SPEED = "80"

def is_valid_image(img):
	"""
	Check if img is valid: not blurry. 
	"""
	# Load the cascade
	# https://github.com/opencv/opencv/tree/master/data/haarcascades
	face_cascade = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
	# Convert into grayscale
	gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
	# Detect faces
	faces = face_cascade.detectMultiScale(
		gray,
		scaleFactor=1.1,
		minNeighbors=5,
		minSize=(30, 30)
	)

	# If there isn't a face
	if len(faces) == 0:
		return False
	
	# If there is a face
	for (x, y, w, h) in faces:
		face = img[y:y+h, x:x+w]
		# check if image is blurry
		gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
		fm = cv2.Laplacian(gray, cv2.CV_64F).var()
		# if the focus measure is less than the supplied threshold,
		# then the image should be considered "blurry"
		blurry = True if fm<THRESHOLD_BLURRY else False
		if blurry:
			return False
		else:
			#cv2.imshow("valid", gray)
			#cv2.waitKey(0)
			return True
			
	return False
	
#-------------------------------------------------------------------------------------------

class HumanGreeter(object):

	def __init__(self, app, image_folder, not_valid_image_folder):
		"""
		Initialisation of qi framework and event detection.
		"""
		super(HumanGreeter, self).__init__()
		
		# Create folder where to save VALID captured images
		self.image_folder = image_folder
		if not os.path.exists(image_folder):
			os.mkdir(image_folder)

		# Create folder where to save NOT VALID captured images
		self.not_valid_image_folder = not_valid_image_folder
		if not os.path.exists(not_valid_image_folder):
			os.mkdir(not_valid_image_folder)

		app.start()
		session = app.session
		# Get the service ALMemory.
		self.memory = session.service("ALMemory")
		# Connect the event callback.
		self.subscriber_gaze = self.memory.subscriber("GazeAnalysis/PersonStartsLookingAtRobot")
		self.subscriber_gaze.signal.connect(self.on_human_tracked)
		self.subscriber_face = self.memory.subscriber("FaceDetected")
		#self.people_perception = session.service("ALTracker")
		self.subscriber_people = self.memory.subscriber("PeoplePerception/PeopleDetected")
		# Get the services ALTextToSpeech, ALFaceDetection, ALPeoplePerception, ALRobotPosture, ALBasicAwareness, ALVideoDevice
		self.posture = session.service("ALRobotPosture")
		self.tts = session.service("ALTextToSpeech")
		self.animated_speech = session.service("ALAnimatedSpeech")
		self.face_detection = session.service("ALFaceDetection")
		self.people_perception = session.service("ALPeoplePerception")
		self.awareness = session.service("ALBasicAwareness")
		self.video_device = session.service("ALVideoDevice")

		self.face_detection.subscribe("HumanGreeter")
		self.awareness.setEnabled(True) # Robot is enabled for catching a person
		self.got_face = False
		self.tts.setLanguage("Italian")
		
    #-------------------------------------------------------------------------------------------
	def on_human_tracked(self, value):
		"""
		Callback for event GazeAnalysis/PersonStartsLookingAtRobot.
		"""
		if value == []:  # empty value when the face disappears
			self.got_face = False
		elif not self.got_face:
			# GAZE DETECTION
			self.awareness.setEnabled(False) # Disabled person detection
			print("Someone is looking at me.")
			self.tts.say("Ciao! Piacere.")
			value_face = self.memory.getData("FaceDetected", 0)

			# SAVE FACE IMAGES and PEPPER PRESENTATION
			self.tts.say("Per favore rimane un attimo dove sei.")

			self.capture_images()

			self.awareness.setEnabled(True) # Enabled person catching
			self.tts.say("Grazie.")
			self.got_face = True # I don't want to capture other people

			'''
			# PEOPLE PERCEPTION -- not used but is working
			value_person = self.memory.getData("PeoplePerception/PeopleDetected", 0)
			timeStamp = value_person[0]
			print("TimeStamp is: " + str(timeStamp))
			personInfoArray = value_person[1][0]
			person_id = personInfoArray[0]
			distanceToCamera = personInfoArray[1]
			pitchAngleInImage = personInfoArray[2]
			yawAngleInImage = personInfoArray[3]
			print("Person Info: ID %.3f - distance %.3f" % (person_id, distanceToCamera))
			print("Person In Image (radians):  pitch %.3f - yaw %.3f" % (pitchAngleInImage, yawAngleInImage))
			
			# Head Pepper coordinates
			yaw, pitch, roll = self.memory.getData("PeoplePerception/Person/"+str(person_id)+"/HeadAngles")
			print "Head Robot (degrees):  --yam=%.3f --pitch=%.3f --roll=%.3f" % (np.rad2deg(yaw), np.rad2deg(pitch), np.rad2deg(roll))

			# FACE DETECTION
			# First Field = TimeStamp.
			timeStamp = value_face[0] 
			# Second Field = array of face_Info's.
			faceInfoArray = value_face[1]
			for j in range( len(faceInfoArray)-1 ):
				faceInfo = faceInfoArray[j]
				# First Field = Shape info.
				faceShapeInfo = faceInfo[0]
				# Second Field = Extra info (empty for now).
				faceExtraInfo = faceInfo[1]
				print "Face Infos :  alpha %.3f - beta %.3f" % (faceShapeInfo[1], faceShapeInfo[2])
				print "Face Infos :  width %.3f - height %.3f" % (faceShapeInfo[3], faceShapeInfo[4])
				print "Face Extra Infos :" + str(faceExtraInfo)
			'''

	#-------------------------------------------------------------------------------------------
	def capture_images(self):
		"""
		Capture some face images
		and save the 5 of them that are valid for is_valid_image().
		"""
		# Subscribe top camera
		# https://fileadmin.cs.lth.se/robot/nao/doc/family/juliette_technical/video_juliette.html#juliette-video
		AL_kTopCamera = 0
		AL_kQVGA = 2 #1: 320x240; 2: 640x480
		AL_kBGRColorSpace = 13
		fps = 13
		subscriberID = self.video_device.subscribeCamera("test", AL_kTopCamera, AL_kQVGA, AL_kBGRColorSpace, fps)

		# create image
		width = 320*AL_kQVGA
		height = 240*AL_kQVGA
		image = np.zeros((height, width, 3), np.uint8)

		# get image
		k = 0 # for valid images
		w = 0 # for not valid images
		while k < 5:
			result = self.video_device.getImageRemote(subscriberID)
			
			if result == None:
				print('cannot capture.')
			elif result[6] == None:
				print('no image data string.')
			else: # translate result to mat
				print(len(result[6]))
				values = list(result[6])
				i = 0
				for y in range(0, height):
					for x in range(0, width):
						image.itemset((y, x, 0), values[i + 0])
						image.itemset((y, x, 1), values[i + 1])
						image.itemset((y, x, 2), values[i + 2])
						i += 3
				# save image
				if is_valid_image(image):
					print("Image "+str(k)+" saved.")
					cv2.imwrite(self.image_folder+"/img_"+str(k)+".jpg", image)
					k += 1
				else:
					cv2.imwrite(self.not_valid_image_folder+"/img_"+str(w)+".jpg", image)
					w += 1
			if k == 5:
				print("Capturing done.")
		self.video_device.unsubscribe(subscriberID)
		self.face_detection.unsubscribe("HumanGreeter")

	#-------------------------------------------------------------------------------------------
	def say_something(self, animation_tag, text):
		"""
		Say the given 'text' with the animation from 'animation_tag'. 
		"""
		# Pepper default tags:
		# http://doc.aldebaran.com/2-5/naoqi/motion/alanimationplayer-advanced.html#animationplayer-list-behaviors-pepper
		sentence = "\RSPD="+SPEECH_SPEED+"\ "
		sentence += "^start(%s) %s ^wait(%s)" % (animation_tag, text, animation_tag)
		sentence +=  "\RST\ "
		self.animated_speech.say(sentence)

	#-------------------------------------------------------------------------------------------
	def introduce_robot_1(self):
		"""
		Pepper robot presents itself.
		"""		
		tag = "me"
		text = "Mi presento: sono Pepper. Sono un robot umanoide sviluppato da Softbank Robotics nel 2014. \n"
		text += "Spero che questa parte di esperimento sar"+u'\xe0'+" piacevole."
		'''
		text += "Sono alto 1 metro e 20 e peso 28 chili. \n"
		text += "Sono stato sviluppato per interagire con le persone e fornire assistenza, intrattenimento o qualsiasi cosa di cui abbiano bisogno. \n"
		text += "Sono in grado di comprendere il linguaggio naturale, riconoscere i volti e i movimenti delle persone, e comunicare con gesti e movimenti del corpo. \n"
		text += "Sono un robot molto popolare in Giappone e in altri paesi asiatici, ma sto guadagnando sempre pi"+u'\xf9'+" popolarit"+u'\xe0'+" in tutto il mondo. \n"
		text += "Spero di farti divertire. Grazie per interagire con me!"
		'''
		self.say_something(animation_tag=tag, text=text)

	#-------------------------------------------------------------------------------------------
	def introduce_robot_2(self):
		"""
		Pepper robot presents itself.
		"""
		# Pepper default tags:
		# http://doc.aldebaran.com/2-5/naoqi/motion/alanimationplayer-advanced.html#animationplayer-list-behaviors-pepper
		tag = "me"
		text = "Mi presento: sono Pepper. Sono un robot sviluppato per interagire con le persone e fornire assistenza, intrattenimento o qualsiasi cosa di cui abbiano bisogno. \n"
		text += "Spero che questa parte dell'esperimento sia di tuo gradimento."
		'''
		text += "Sono alto 1 metro e 20 e peso 28 chili. \n"
		text += "Sono stato sviluppato per interagire con le persone e fornire assistenza, intrattenimento o qualsiasi cosa di cui abbiano bisogno. \n"
		text += "Sono in grado di comprendere il linguaggio naturale, riconoscere i volti e i movimenti delle persone, e comunicare con gesti e movimenti del corpo. \n"
		text += "Sono un robot molto popolare in Giappone e in altri paesi asiatici, ma sto guadagnando sempre pi"+u'\xf9'+" popolarit"+u'\xe0'+" in tutto il mondo. \n"
		text += "Spero di farti divertire. Grazie per interagire con me!"
		'''
		self.say_something(animation_tag=tag, text=text)

	#-------------------------------------------------------------------------------------------
	def run(self):
		"""
		Loop on, wait for events until intercepting a single person.
		"""
		print("Starting HumanGreeter")
		while self.got_face == False:
			time.sleep(1)
		print("Stopping HumanGreeter")
		#stop
		#sys.exit(0)

#-------------------------------------------------------------------------------------------
if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--ip", type=str, default="172.20.10.10", help="Robot IP address. On robot or Local Naoqi: use '127.0.0.1'.")
	parser.add_argument("--port", type=int, default=9559, help="Naoqi port number")
	parser.add_argument("--outputdir", help="directory where captured images will be saved", required=True)

	args = parser.parse_args()
	try:
		# Initialize qi framework.
		connection_url = "tcp://" + args.ip + ":" + str(args.port)
		app = qi.Application(["HumanGreeter", "--qi-url=" + connection_url])
	except RuntimeError:
		print ("Can't connect to Naoqi at ip \"" + args.ip + "\" on port " + str(args.port) +".\n"
		"Please check your script arguments. Run with -h option for help.")
		sys.exit(1)

	human_greeter = HumanGreeter(app)
	human_greeter.run()
	sys.exit(0)