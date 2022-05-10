from ast import Pass, Str, Try
from concurrent.futures import thread
from pickle import READONLY_BUFFER
from struct import pack
from time import time
from tkinter import *
import tkinter.messagebox
from tkinter.ttk import Progressbar
from turtle import left, width
from typing_extensions import Self
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	SWITCH = 3
	state = SWITCH
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	DESCRIBE = 4
	FORWARD = 5
	BACKWARD = 6
	CHOOSE = 7
	
	LOSS_NUM = 0
	TOTAL_DATA = 0
	START_TIME = 0
	END_TIME = 0

	PASS_TIME = 5

	TOTAL_TIME = 0
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
		self.setupflag = 0
	# THIS GUI IS JUST FOR REFERENCE ONLY, STUDENTS HAVE TO CREATE THEIR OWN GUI 	
	def createWidgets(self):
		"""Build GUI."""
		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=2, column=2, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=2, column=3, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=3, column=2, padx=2, pady=2)
		
		#	Create Describe button
		self.describe = Button(self.master, width=20, padx=3, pady=3)
		self.describe['text'] = 'Describe'
		self.describe['command'] = self.describeMovie
		self.describe.grid(row=3, column=3, padx=2, pady=2)

		#	Create Backward button
		self.backward = Button(self.master, width=20, padx=3, pady=3)
		self.backward['text'] = '<<<'
		self.backward['command'] = self.backwardMovie
		self.backward.grid(row=2, column=1, padx=2, pady=2)

		#	Create Forward button
		self.forward = Button(self.master, width=20, padx=3, pady=3)
		self.forward['text'] = '>>>'
		self.forward['command'] = self.forwardMovie
		self.forward.grid(row=2, column=4, padx=2, pady=2)


		# Create a label to display the video length
		self.labellen = Label(self.master, height=1, width= 6, borderwidth= 3, relief='groove')
		self.labellen.grid(row=1, column=4, ipadx=0) 
		self.labellen.configure(text='...')

		# Create a label to display the remaining time
		self.label_remain = Label(self.master, height=1, width= 6, borderwidth= 3, relief='groove')
		self.label_remain.grid(row=1, column=1, ipadx=0) 
		self.label_remain.configure(text='...')

		# Create a label to display the movie
		self.label = Label(self.master, height=19, width= 30)
		self.label.grid(row=0, column=1, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 

		#Create a progress bar
		self.progress = Progressbar(self.master, orient= HORIZONTAL, length= 310, mode= 'determinate')
		self.progress.grid(row=1, column=2, columnspan= 2)
	
	def exitClient(self):
		"""Teardown button handler."""
		if self.state == self.PLAYING or self.state == self.READY:
			self.sendRtspRequest(self.TEARDOWN)
			self.master.destroy()
			os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)

	
	def playMovie(self):
		"""Play button handler."""
		if self.state == self.INIT:
			self.fileName = self.clicked.get()
			self.sendRtspRequest(self.SETUP)
			self.state = self.READY
			self.done = threading.Event()
		if self.setupflag == 0:
			while True:
				if self.state == self.READY and self.done.isSet():
					self.sendRtspRequest(self.PLAY)
					self.setupflag = 1
					break
		else:
			if self.state == self.READY:
				self.sendRtspRequest(self.PLAY)
		#self.sendRtspRequest(self.PLAY)
		
	def describeMovie(self):
		if self.state == self.READY or self.state == self.PLAYING:
			self.sendRtspRequest(self.DESCRIBE)

	def listenRtp(self):		
		"""Listen for RTP packets."""
		while True:
			try:
			
				data, addr = self.rtp_soc.recvfrom(20480)

				packet = RtpPacket()
				packet.decode(data)
				#Dieu kien xac dinh su mat goi
				
				if self.forward_event.isSet() and self.frameNbr + self.pass_frame < packet.seqNum():
					self.LOSS_NUM += packet.seqNum() - (self.frameNbr + self.pass_frame)
				elif self.backward_event.isSet() and self.frameNbr - self.pass_frame < packet.seqNum():
					self.LOSS_NUM += packet.seqNum() - (self.frameNbr - self.pass_frame)
				elif packet.seqNum() != self.frameNbr + 1 and self.requestSent == self.PLAY and (not self.forward_event and not self.backward_event):
					self.LOSS_NUM += packet.seqNum() - (self.frameNbr + 1)		
						
					
				if packet.seqNum() >= 1 and packet.seqNum() <= self.total_frame:
					payload = packet.getPayload()
					self.updateMovie(self.writeFrame(payload))
					self.frameNbr = packet.seqNum()
					self.TOTAL_DATA += len(payload)
					self.backward_event.clear()
					self.forward_event.clear()
					self.label_remain.configure(text=f'{self.len - round((self.len / self.total_frame) * self.frameNbr)}')
					self.progress['value'] = (self.frameNbr / self.total_frame) * 100
				#Code uoc tinh do dai video
				#print(packet.timestamp())
				if self.frameNbr >= self.total_frame:
					if self.START_TIME:
						self.END_TIME = time()
						self.TOTAL_TIME += self.END_TIME - self.START_TIME
						self.START_TIME = 0
						break
			except:	
				if self.event.isSet() and self.teardownAcked == 1:
					self.event.clear()
					self.rtp_soc.close()
					break
				elif self.event.isSet() and self.teardownAcked == 0:
					self.event.clear()
					break
				
			
	
					
	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		name = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		try:
			temp = open(name, 'wb')
			temp.write(data)
		except:
			print('WRITE FRAME ERROR!')
		temp.close()
		return name

	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		frame = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image=frame, height=288)
		self.label.image = frame

		
	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtsp_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		addr = (self.serverAddr, self.serverPort)
		self.rtsp_soc.connect(addr)
		self.sendRtspRequest(self.CHOOSE)
		

	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""	
		#-------------
		# TO COMPLETE
		#-------------
		if requestCode == self.CHOOSE:
			self.rtspSeq += 1
			request = 'CHOOSE VIDEO RTSP/1.0\n'
			request += f'CSeq: {self.rtspSeq}'
			self.requestSent = self.CHOOSE
			threading.Thread(target=self.recvRtspReply).start()
		elif requestCode == self.SETUP:
			self.rtspSeq += 1
			request = f'SETUP {self.fileName} RTSP/1.0\n' #version giong nhu trong vi du
			request += f'CSeq: {self.rtspSeq}\n'
			request += f'Transport: RTP/UDP; client_port= {self.rtpPort}'
			self.requestSent = self.SETUP
			#thread cho phan hoi tu server
			#threading.Thread(target=self.recvRtspReply).start()
		elif requestCode == self.TEARDOWN:
			self.rtspSeq += 1
			request = f'TEARDOWN {self.fileName} RTSP/1.0\n'
			request += f'CSeq: {self.rtspSeq}\n'
			request += f'Session: {self.sessionId}'
			self.requestSent = self.TEARDOWN
		elif requestCode == self.PAUSE:
			self.rtspSeq += 1
			request = f'PAUSE {self.fileName} RTSP/1.0\n'
			request += f'CSeq: {self.rtspSeq}\n'
			request += f'Session: {self.sessionId}'
			self.requestSent = self.PAUSE
		elif requestCode == self.PLAY:
			self.rtspSeq += 1
			request = f'PLAY {self.fileName} RTSP/1.0\n'
			request += f'CSeq: {self.rtspSeq}\n'
			request += f'Session: {self.sessionId}'
			self.requestSent = self.PLAY
		elif requestCode == self.DESCRIBE:
			self.rtspSeq += 1
			request = f'DESCRIBE {self.fileName} RTSP/1.0\n'
			request += f'CSeq: {self.rtspSeq}\n'
			self.requestSent = self.DESCRIBE
		elif requestCode == self.FORWARD:
			self.rtspSeq += 1
			request = f'FORWARD {self.fileName} RTSP/1.0\n'
			request += f'CSeq: {self.rtspSeq}\n'
			request += f'Session: {self.sessionId}'
			self.requestSent = self.FORWARD
		elif requestCode == self.BACKWARD:
			self.rtspSeq += 1
			request = f'BACKWARD {self.fileName} RTSP/1.0\n'
			request += f'CSeq: {self.rtspSeq}\n'
			request += f'Session: {self.sessionId}'
			self.requestSent = self.BACKWARD
		self.rtsp_soc.send(request.encode('utf-8'))
		
	
	
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			rep = self.rtsp_soc.recv(256).decode('utf-8')
			self.parseRtspReply(rep)
			if self.teardownAcked == 1:
				self.rtsp_soc.close()
				break


	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		#des = data
		data = data.split('\n')
		#print(data)
		if len(data) != 0:
			rep_code = data[0].split(' ')[1]
			cseq = int(data[1].split(' ')[1])
			if len(data) == 5:
						self.len = int(data[3].split(' ')[1])
						self.total_frame = int(data[4].split(' ')[1]) 
						self.pass_frame = round(self.PASS_TIME / (self.len / self.total_frame))
						self.labellen.configure(text= str(self.len))
			elif cseq == self.rtspSeq:
				if self.requestSent == self.CHOOSE:
					self.state = self.INIT
					self.video_list = data[2].split(' ')[1].split('|')
					self.clicked = StringVar()
					self.clicked.set(self.fileName)
					self.drop = OptionMenu(self.master, self.clicked, *self.video_list)
					self.drop.grid(row=3, column=1)
				elif self.requestSent == self.SETUP:
					id = int(data[2].split(' ')[1])
					self.sessionId = id
					self.state = self.READY
					self.openRtpPort()
					self.listencheck()
					self.forward_event = threading.Event()
					self.backward_event = threading.Event()
				elif self.requestSent == self.PLAY:
					self.state = self.PLAYING
					self.event = threading.Event()
					threading.Thread(target=self.listenRtp).start()
					
					#Phan time
					self.START_TIME = time()

				elif self.requestSent == self.PAUSE:
					self.state = self.READY
					self.event.set()
					#Phan time
					self.END_TIME = time()
					self.TOTAL_TIME += self.END_TIME - self.START_TIME
					self.START_TIME = 0

				elif self.requestSent == self.TEARDOWN :
					self.state = self.SETUP
					self.event.set()
					self.teardownAcked = 1

					if self.START_TIME != 0:
						self.END_TIME = time()
						self.TOTAL_TIME += self.END_TIME - self.START_TIME
					
					loss_rate = (self.LOSS_NUM / self.frameNbr) * 100
					data_rate = self.TOTAL_DATA / self.TOTAL_TIME
					print('Stats value: ')
					print('LOSS RATE: {:.2f}%'.format(loss_rate))
					print('DATA RATE: {:.2f} bps'.format(data_rate))
				elif self.requestSent == self.DESCRIBE :
					des = data[3:]
					file = open('des.sdp', 'a')
					for line in des:
						print(line)
					des = data[6:]
					for line in des:
						file.write(line+'\n')
					file.close()
				elif self.requestSent == self.FORWARD:
					self.forward_event.set()
				elif self.requestSent == self.BACKWARD:
					self.backward_event.set()

					

	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		#-------------
		# TO COMPLETE
		#-------------
		# Create a new datagram socket to receive RTP packets from the server
		# self.rtpSocket = ...
		
		# Set the timeout value of the socket to 0.5sec
		# ...
		self.rtp_soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.rtp_soc.settimeout(0.5)
		addr = (self.serverAddr, self.rtpPort)
		self.rtp_soc.bind(addr)
		

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		if tkinter.messagebox.askokcancel("Quit?", "Do you want to quit?"):
			self.exitClient()
		else: 
			self.playMovie()

	def listencheck(self):
		'''Receive the first 3 packet for testing'''
		while True:
			try:
				data, addr = self.rtp_soc.recvfrom(20480)
		
				packet = RtpPacket()
				packet.decode(data)
				if packet.seqNum() == 3:
					break
			except:	
				print('error')
				break
		self.done.set()
		
	
	def backwardMovie(self):
		'''Rewind the video'''
		if (self.state == self.PLAYING ) and (self.frameNbr - self.pass_frame >= 1):
			self.sendRtspRequest(self.BACKWARD)

	def forwardMovie(self):
		'''Fast-forward the video'''
		if (self.state == self.PLAYING ) and (self.frameNbr + self.pass_frame <= self.total_frame):
			self.sendRtspRequest(self.FORWARD)