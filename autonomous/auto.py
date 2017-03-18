#
# auto.py - Autonomous ROS perception-reaction subsystem.
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

# ROS message imports
from std_msgs.msg import String, Int32
from blender_api_msgs.msg import BlinkCycle
from blender_api_msgs.msg import SaccadeCycle
from blender_api_msgs.msg import SetGesture
from chatbot.msg import ChatMessage

# Not everything has this message; don't break if it's missing.
# i.e. create a stub if its not defined.
#try:
#  from chatbot.msg import ChatMessage
#except (NameError, ImportError):
#  class ChatMessage:
#     def __init__(self):
#        self.utterance = ''
#        self.confidence = 0


class Autonomous():

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

	# ----------------------------------------------------------
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
	# The chat_heard message is of type chatbot/ChatMessage
	# from chatbot.msg import ChatMessage
	def chat_perceived_text_cb(self, chat_heard):
		if 'shut up' in chat_heard.utterance.lower():
			self.tts_control_pub.publish("shutup")
			return

	# ----------------------------------------------------------
	# Wrapper for saccade generator.
	# This is setup entirely in python, and not in the AtomSpace,
	# as, at this time, there are no knobs worth twiddling.

	# Explore-the-room saccade when not conversing.
	# ??? Is this exploring the room, or someone's face? I'm confused.
	def explore_saccade(self):
		if not self.control_mode & self.C_SACCADE:
			return
		# Switch to conversational (micro) saccade parameters
		msg = SaccadeCycle()
		msg.mean =  0.8        # saccade_explore_interval_mean
		msg.variation = 0.3    # saccade_explore_interval_var
		msg.paint_scale = 0.3   # saccade_explore_paint_scale
		# From study face, maybe better default should be defined for
		# explore
		msg.eye_size = 15      # saccade_study_face_eye_size
		msg.eye_distance = 100  # saccade_study_face_eye_distance
		msg.mouth_width = 90    # saccade_study_face_mouth_width
		msg.mouth_height = 27  # saccade_study_face_mouth_height
		msg.weight_eyes = 0.8    # saccade_study_face_weight_eyes
		msg.weight_mouth = 0.2   # saccade_study_face_weight_mouth
		self.saccade_pub.publish(msg)

	# Used during conversation to study face being looked at.
	def conversational_saccade(self):
		if not self.control_mode & self.C_SACCADE:
			return
		# Switch to conversational (micro) saccade parameters
		msg = SaccadeCycle()
		msg.mean =  0.8         # saccade_micro_interval_mean
		msg.variation = 0.5     # saccade_micro_interval_var
		msg.paint_scale = 0.3   # saccade_micro_paint_scale
		#
		msg.eye_size = 11.5      # saccade_study_face_eye_size
		msg.eye_distance = 100 # saccade_study_face_eye_distance
		msg.mouth_width = 90    # saccade_study_face_mouth_width
		msg.mouth_height = 5  # saccade_study_face_mouth_height
		msg.weight_eyes = 0.8    # saccade_study_face_weight_eyes
		msg.weight_mouth = 0.2   # saccade_study_face_weight_mouth
		self.saccade_pub.publish(msg)

	# Used during conversation to study face being looked at.
	def listening_saccade(self):
		if not self.control_mode & self.C_SACCADE:
			return
		# Switch to conversational (micro) saccade parameters
		msg = SaccadeCycle()
		msg.mean =  1         # saccade_micro_interval_mean
		msg.variation = 0.6      # saccade_micro_interval_var
		msg.paint_scale = 0.3      # saccade_micro_paint_scale
		#
		msg.eye_size = 11        # saccade_study_face_eye_size
		msg.eye_distance = 80    # saccade_study_face_eye_distance
		msg.mouth_width = 50     # saccade_study_face_mouth_width
		msg.mouth_height = 13.0  # saccade_study_face_mouth_height
		msg.weight_eyes = 0.8    # saccade_study_face_weight_eyes
		msg.weight_mouth = 0.2   # saccade_study_face_weight_mouth
		self.saccade_pub.publish(msg)

	# ----------------------------------------------------------
	# Wrapper for controlling the blink rate.
	def blink_rate(self, mean, variation):
		msg = BlinkCycle()
		msg.mean = mean
		msg.variation = variation
		self.blink_pub.publish(msg)

	# Chatbot requests blink.
	def chatbot_blink_cb(self, blink):

		# XXX currently, this by-passes the OC behavior tree.
		# Does that matter?  Currently, probably not.
		rospy.loginfo(blink.data + ' says blink')
		blink_probabilities = {
			'chat_heard' : 0.4,
			'chat_saying' : 0.7,
			'tts_end' : 0.7 }
		# If we get a string not in the dictionary, return 1.0.
		blink_probability = blink_probabilities[blink.data]
		if random.random() < blink_probability:
			self.gesture('blink', 1.0, 1, 1.0)

	# ----------------------------------------------------------
	# The perceived emotional content of words spoken to the robot.
	# That is, were people being rude to the robot? Polite to it? Angry
	# with it?  We subscribe; there may be multiple publishers of this
	# message: it might be supplied by some linguistic-processing module,
	# or it might be supplied by an AIML-derived chatbot.
	#
	# emo is of type std_msgs/String
	def language_affect_perceive_cb(self, emo):
		rospy.logwarn('publishing affect to chatbot ' + emo.data)
		self.affect_pub.publish(emo.data)

	# ----------------------------------------------------------
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
				self.running = False

	# Data is a bit-flag that enables/disables publication of messages.
	def behavior_control_callback(self, data):
		self.control_mode = data.data

	def __init__(self):
		# Full control by default
		self.control_mode = 255
		self.running = True

		# The below will hang until roscore is started!
		rospy.init_node("Autonomous")
		print("Starting Autonomous Behaviors")

		# ----------------
		# Send out facial gestures.
		self.gesture_pub = rospy.Publisher("/blender_api/set_gesture",
		                                   SetGesture, queue_size=1)
		self.blink_pub = rospy.Publisher("/blender_api/set_blink_randomly",
		                                   BlinkCycle, queue_size=1)
		self.saccade_pub = rospy.Publisher("/blender_api/set_saccade",
		                                   SaccadeCycle, queue_size=1)

		# ----------------
		rospy.logwarn("setting up chatbot affect perceive and express links")

		# String text of what the robot heard (from TTS)
		rospy.Subscriber("chatbot_speech", ChatMessage,
			self.chat_perceived_text_cb)

		# Emotional content of words spoken to the robot.
		rospy.Subscriber("chatbot_affect_perceive", String,
			self.language_affect_perceive_cb)

		# Tell the chatbot what sort of affect to apply during
		# TTS vocalization. XXX FIXME this should probably not
		# bypass the cogserver.
		self.affect_pub = rospy.Publisher("chatbot_affect_express",
		                                  String, queue_size=1)

		# Used to stop the vocalization.
		self.tts_control_pub = rospy.Publisher("tts_control",
		                        String, queue_size=1)

		# Chatbot can request blinks correlated with hearing and speaking.
		rospy.Subscriber("chatbot_blink", String, self.chatbot_blink_cb)

		# ----------------
		# Boolean flag, turn the behavior tree on and off (set it running,
		# or stop it)
		rospy.Subscriber("/behavior_switch", String, \
			self.behavior_switch_callback)

		# Bit-flag to enable/disable publication of various classes of
		# gestures.
		rospy.Subscriber("/behavior_control", Int32, \
			self.behavior_control_callback)

# ----------------------------------------------------------------
