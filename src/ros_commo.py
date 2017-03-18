#
# ros_commo.py - ROS messaging module for OpenCog behaviors.
# Copyright (C) 2015  Hanson Robotics
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License v3 as
# published by the Free Software Foundation and including the exceptions
# at http://opencog.org/wiki/Licenses
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to:
# Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import rosmsg
import rospy
import roslib
import time
import logging
import random
import yaml
import tf
import numpy
import dynamic_reconfigure.client
# Eva ROS message imports
from std_msgs.msg import String, Int32
from blender_api_msgs.msg import AvailableEmotionStates, AvailableGestures
from blender_api_msgs.msg import EmotionState
from blender_api_msgs.msg import SetGesture
from blender_api_msgs.msg import Target
from blender_api_msgs.msg import SomaState

logger = logging.getLogger('hr.OpenCog_Eva')

# ROS interfaces for the Atomese (OpenCog) Behavior Tree. Publishes
# ROS messages for animation control (smiling, frowning), as well
# ass messages that tell the robot to say something.
#
# This is meant to be a convenience wrapper, allowing Eva to be
# controlled from OpenCog Atomese.  Although it probably works as
# a stand-alone ROS node, it was not designed to be used that way.
# In particular, the python interpreter built into the atomspace
# will be runnig this code.
#
# It currently publishes robot motor control messages -- expression
# and gesture animations, text to be verbalized. 
#
# This does listen to two topics that are used to turn behaviors on
# and off:
#
# `/behavior_switch`, which is used to start and stop the behavior tree.
#
# `/behavior_control`, which is used to enable/disable the publication
#      of classes of expression/gesture messages.
#
class EvaControl():

	# Control bitflags. Bit-wise anded with control_mode. If the bit
	# is set, then the corresponding ROS message is emitted, else it
	# is not.
	C_EXPRESSION = 1
	C_GESTURE = 2
	C_SOMA = 4
	C_SACCADE = 8
	C_EYES = 16
	C_FACE = 32

	def step(self):
		print "step once"
		return not rospy.is_shutdown()
    # Temporary disable sleeping.
	def go_sleep(self):
		# Vytas altered this in commit
		# 67ba02f75c5f82f4abb3e600711c97f65f007534
		# presumably because of conflicts with the current blender model!?
		# Or perhaps the behavior tree is sleeping too often?
		# self.soma_state('sleep', 1, 1, 3)
		# self.soma_state('normal', 0, 1, 0)
		self.soma_state('normal', 0.1, 1, 3)

	def wake_up(self):
		# self.soma_state('sleep', 0, 1, 0)
		self.soma_state('normal', 0.1, 1, 3)

	# ----------------------------------------------------------
	# Wrapper for facial expressions
	def expression(self, name, intensity, duration):
		if 'noop' == name or (not self.control_mode & self.C_EXPRESSION):
			return
		# Create the message
		exp = EmotionState()
		exp.name = name
		exp.magnitude = intensity
		exp.duration.secs = int(duration)
		exp.duration.nsecs = 1000000000 * (duration - int(duration))
		self.expression_pub.publish(exp)
		print "Publish facial expression:", exp.name

	# Wrapper for Soma state expressions
	def soma_state(self, name, intensity, rate, ease_in=0.0):
		if 'noop' == name or (not self.control_mode & self.C_SOMA):
			return
		# Create the message
		soma = SomaState()
		soma.name = name
		soma.magnitude = intensity
		soma.rate = rate
		soma.ease_in.secs = int(ease_in)
		soma.ease_in.nsecs = 1000000000 * (ease_in - int(ease_in))
		self.soma_pub.publish(soma)
		print "Publish soma state:", soma.name, "intensity:", intensity

	# Wrapper for gestures
	def gesture(self, name, intensity, repeat, speed):
		if 'noop' == name or (not self.control_mode & self.C_GESTURE):
			return
		# Create the message
		ges = SetGesture()
		ges.name = name
		ges.magnitude = intensity
		ges.repeat = repeat
		ges.speed = speed
		self.gesture_pub.publish(ges)
		print "Published gesture: ", ges.name

	# ----------------------------------------------------------
	# Look at, gaze at, glance at face id's
	# Look_at turns entire head in that direction, once.
	# Gaze_at has the eyes track the face location (servoing)
	# Glance_t is a momentary eye movement towards the face target.

	def look_at(self, face_id):
		# Can get called 10x/second, don't print.
		# print "----- Looking at face: " + str(face_id)
		if not self.control_mode & self.C_EYES:
			return
		self.look_at_pub.publish(face_id)

	def gaze_at(self, face_id):
		print "----- Gazing at face: " + str(face_id)
		self.gaze_at_pub.publish(face_id)

	def glance_at(self, face_id):
		print "----- Glancing at face: " + str(face_id)
		self.glance_at_pub.publish(face_id)

	# ----------------------------------------------------------
	# Explicit directional look-at, gaze-at locations

	# Turn only the eyes towards the given target point.
	# Coordinates: meters; x==forward, y==to Eva's left.
	def gaze_at_point(self, x, y, z):
		xyz1 = numpy.array([x, y, z, 1.0])
		xyz = numpy.dot(self.conv_mat, xyz1)
		trg = Target()
		trg.x = xyz[0]
		trg.y = xyz[1]
		trg.z = xyz[2]
		print "gaze at point: ", trg.x, trg.y, trg.z
		self.gaze_pub.publish(trg)

	# Turn head towards the given target point.
	# Coordinates: meters; x==forward, y==to Eva's left.
	def look_at_point(self, x, y, z):
		xyz1 = numpy.array([x, y, z, 1.0])
		xyz = numpy.dot(self.conv_mat, xyz1)
		trg = Target()
		trg.x = xyz[0]
		trg.y = xyz[1]
		trg.z = xyz[2]
		print "look at point: ", trg.x, trg.y, trg.z
		self.turn_pub.publish(trg)

	# ----------------------------------------------------------

	# Tell the world what we are up to. This is so that other
	# subsystems can listen in on what we are doing.
	def publish_behavior(self, event):
		print "----- Behavior pub: " + event
		self.behavior_pub.publish(event)

	# ----------------------------------------------------------

	def update_opencog_control_parameter(self, name, value):
		"""
		This function is used for updating ros parameters that are used to
		modify the weight of openpsi rules. When the changes in weight occur
		independent of changes in HEAD's web-ui.
		"""
		update =  False
		param_name = name[len(self.psi_prefix) - 1:]

		# Update parameter
		if (param_name in self.param_dict) and \
		   (self.param_dict[param_name] != value):
			self.param_dict[param_name] = value
			self.update_parameters = True


	def push_parameter_update(self):
		if self.update_parameters and not rospy.is_shutdown():
			if self.client is None:
				return
			self.client.update_configuration(self.param_dict)
			self.update_parameters = False

	# ----------------------------------------------------------
	# Subscription callbacks
	# Get the list of available gestures.
	def get_gestures_cb(self, msg):
		print("Available Gestures:" + str(msg.data))

	# Get the list of available facial expressions.
	def get_expressions_cb(self, msg):
		print("Available Facial Expressions:" + str(msg.data))

	# ----------------------------------------------------------

	# Tell the TTS subsystem to vocalize a plain text-string
	def say_text(self, text_to_say):
		rospy.logwarn('publishing text to TTS ' + text_to_say)
		self.tts_pub.publish(text_to_say)

	# Turn behaviors on and off.
	#
	# 'btree_on' and 'btree_off' data-strings shouldn't be used, as they are
	#    meant for switching on and off non-opencog demos.
	def behavior_switch_callback(self, data):
		if data.data == "opencog_on":
			if not self.running:
				self.running = True
		if data.data == "opencog_off":
			if self.running:
				self.look_at(0)
				self.gaze_at(0)
				self.running = False

	# Data is a bit-flag that enables/disables publication of messages.
	def behavior_control_callback(self, data):
		self.control_mode = data.data

	def __init__(self):
		# Full control by default
		self.control_mode = 255
		self.running = True

		# The below will hang until roscore is started!
		rospy.init_node("OpenCog_Eva")
		print("Starting OpenCog Behavior Node")

		self.LOCATION_FRAME = "blender"
		# Transform Listener. Tracks history for RECENT_INTERVAL.
		self.tf_listener = tf.TransformListener()
		print "**1\n"
		try:
			self.tf_listener.waitForTransform('camera', self.LOCATION_FRAME, \
				rospy.Time(0), rospy.Duration(10.0))#world
			print "***2\n"
		except Exception:
			print("No camera transforms!\n")
			exit(1)
		print "***3\n"
		(trans,rot) = self.tf_listener.lookupTransform( \
			self.LOCATION_FRAME, 'camera', rospy.Time(0))
		print "***4\n"
		a=tf.listener.TransformerROS()
		print "***5\n"
		self.conv_mat=a.fromTranslationRotation(trans,rot)
		print "hello! ***********"

		# ----------------
		# A list of parameter names that are mirrored in opencog for controling
		# psi-rules
		self.param_list = []
		# Parameter dictionary that is used for updating states recorede in
		# the atomspace. It is used to cache the atomspace values, thus updating
		# of the dictionary is only made from opencog side (openpsi
		# updating rule)
		self.param_dict = {}

		# For controlling when to push updates, for saving bandwidth.
		self.update_parameters = False
		self.psi_prefix = "OpenPsi: "

		# For web ui based control of openpsi contorled-psi-rules
		try:
			self.client = dynamic_reconfigure.client.Client("/opencog_control", timeout=2)
		except Exception:
			self.client = None

		# ----------------
		# Get the available facial animations
		rospy.Subscriber("/blender_api/available_emotion_states",
		       AvailableEmotionStates, self.get_expressions_cb)

		rospy.Subscriber("/blender_api/available_gestures",
		       AvailableGestures, self.get_gestures_cb)

		# Send out facial expressions and gestures.
		self.expression_pub = rospy.Publisher("/blender_api/set_emotion_state",
		                                   EmotionState, queue_size=1)
		self.gesture_pub = rospy.Publisher("/blender_api/set_gesture",
		                                   SetGesture, queue_size=1)
		self.soma_pub = rospy.Publisher("/blender_api/set_soma_state",
		                                   SomaState, queue_size=2)

		# ----------------
		# XYZ coordinates of where to turn and look.
		self.turn_pub = rospy.Publisher("/blender_api/set_face_target",
			Target, queue_size=1)

		self.gaze_pub = rospy.Publisher("/blender_api/set_gaze_target",
			Target, queue_size=1)

		# Int32 faceid of the face to glence at or turn and face.
		self.glance_at_pub = rospy.Publisher("/opencog/glance_at",
			Int32, queue_size=1)

		self.look_at_pub = rospy.Publisher("/opencog/look_at",
			Int32, queue_size=1)

		self.gaze_at_pub = rospy.Publisher("/opencog/gaze_at",
			Int32, queue_size=1)

		# ----------------
		# Publish cues to the chatbot, letting it know what we are doing.
		self.behavior_pub = rospy.Publisher("robot_behavior",
		                                  String, queue_size=1)

		# Tell the TTS subsystem what to vocalize
		self.tts_pub = rospy.Publisher("chatbot_responses", String, queue_size=1)

		# ----------------
		# Boolean flag, turn the behavior tree on and off (set it running,
		# or stop it)
		rospy.Subscriber("/behavior_switch", String, \
			self.behavior_switch_callback)

		# Bit-flag to enable/disable publication of various classes of
		# expressions and gestures.
		rospy.Subscriber("/behavior_control", Int32, \
			self.behavior_control_callback)

# ----------------------------------------------------------------
