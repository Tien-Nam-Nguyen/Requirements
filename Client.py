from ast import Pass, Str, Try
from concurrent.futures import thread
from struct import pack
from time import time
from tkinter import *
import tkinter.messagebox
from turtle import left
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
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	
	LOSS_NUM = 0
	TOTAL_DATA = 0
	START_TIME = 0
	END_TIME = 0

	#PASS_TIME = 5

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
		
		
	# THIS GUI IS JUST FOR REFERENCE ONLY, STUDENTS HAVE TO CREATE THEIR OWN GUI 	
	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		self.setup = Button(self.master, width=20, padx=3, pady=3)
		self.setup["text"] = "Setup"
		self.setup["command"] = self.setupMovie
		self.setup.grid(row=4, column=0, padx=2, pady=2)
		
		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=4, column=1, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=4, column=2, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=4, column=3, padx=2, pady=2)
		

		# Create a label to display the movie
		self.label = Label(self.master, height=25, width= 60)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 

	
	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)
	
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
		if self.state == self.READY:
			self.sendRtspRequest(self.PLAY)

	def listenRtp(self):		
		"""Listen for RTP packets."""
		while True:
			try:
				data, addr = self.rtp_soc.recvfrom(20480)
				if data:
					packet = RtpPacket()
					packet.decode(data)
					if packet.seqNum() != self.frameNbr + 1:
						self.LOSS_NUM += packet.seqNum() - (self.frameNbr + 1)
				
					if packet.seqNum() >= 1:
						payload = packet.getPayload()
						self.updateMovie(self.writeFrame(payload))
						self.frameNbr = packet.seqNum()
						self.TOTAL_DATA += len(payload)
						


			except:	
				if self.event.isSet() and self.teardownAcked == 1:
					self.event.clear()
					self.rtp_soc.close()
					break
				elif self.event.isSet() and self.teardownAcked == 0:
					self.event.clear()
					break
				else:
					if self.START_TIME:
						self.END_TIME = time()
						self.TOTAL_TIME += self.END_TIME - self.START_TIME
						self.START_TIME = 0
						break
					else:
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
		#self.sendRtspRequest(self.SETUP)
		

	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""	
		#-------------
		# TO COMPLETE
		#-------------
		if requestCode == self.SETUP:
			self.rtspSeq += 1
			request = f'SETUP {self.fileName} RTSP/1.0\n' #version giong nhu trong vi du
			request += f'CSeq: {self.rtspSeq}\n'
			request += f'Transport: RTP/UDP; client_port= {self.rtpPort}'
			self.requestSent = self.SETUP
			#thread cho phan hoi tu server
			threading.Thread(target=self.recvRtspReply).start()
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
		print(data)
		
		rep_code = data[0].split(' ')[1]
		cseq = int(data[1].split(' ')[1])
		id = int(data[2].split(' ')[1])
			
		if cseq == self.rtspSeq:

			if self.requestSent == self.SETUP:
				self.sessionId = id
				self.openRtpPort()
				self.state = self.READY
			elif self.requestSent == self.PLAY and self.sessionId == id:
				self.state = self.PLAYING
				threading.Thread(target=self.listenRtp).start()
				self.event = threading.Event()
				#Phan time
				self.START_TIME = time()

			elif self.requestSent == self.PAUSE and self.sessionId == id:
				self.state = self.READY
				self.event.set()
				#Phan time
				self.END_TIME = time()
				self.TOTAL_TIME += self.END_TIME - self.START_TIME
				self.START_TIME = 0

			elif self.requestSent == self.TEARDOWN and self.sessionId == id:
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
				print(f'Video duration: {self.TOTAL_TIME}')


					

	
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
