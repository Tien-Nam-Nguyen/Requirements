from concurrent.futures import thread
from decimal import ROUND_UP
import imp
from math import ceil, floor
from random import randint
from statistics import median
import sys, traceback, threading, socket
from time import time
from VideoStream import VideoStream
from RtpPacket import RtpPacket

class ServerWorker:
	SETUP = 'SETUP'
	PLAY = 'PLAY'
	PAUSE = 'PAUSE'
	TEARDOWN = 'TEARDOWN'
	DESCRIBE = 'DESCRIBE'
	FORWARD = 'FORWARD'
	BACKWARD = 'BACKWARD'
	CHOOSE = 'CHOOSE'
	
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	OK_200 = 0
	FILE_NOT_FOUND_404 = 1
	CON_ERR_500 = 2
	
	#START_TIME = 0
	#END_TIME = 0
	#TOTAL_TIME = 0

	clientInfo = {}
	video_list = ['movie.Mjpeg', 'movie1.Mjpeg']
	def __init__(self, clientInfo):
		self.clientInfo = clientInfo
		
	def run(self):
		threading.Thread(target=self.recvRtspRequest).start()
	
	def recvRtspRequest(self):
		"""Receive RTSP request from the client."""
		connSocket = self.clientInfo['rtspSocket'][0]
		while True:            
			data = connSocket.recv(256)
			if data:
				print("Data received:\n" + data.decode("utf-8"))
				self.processRtspRequest(data.decode("utf-8"))
	
	def processRtspRequest(self, data):
		"""Process RTSP request sent from the client."""
		# Get the request type
		request = data.split('\n')
		line1 = request[0].split(' ')
		requestType = line1[0]
		
		# Get the media file name
		filename = line1[1]
		# Get the RTSP sequence number 
		seq = request[1].split(' ')
		
		# Process CHOOSE request
		if requestType == self.CHOOSE:
			print('processing CHOOSE\n')
			reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq[1] + '\nVideos: ' + '|'.join(self.video_list)
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply.encode())

		elif requestType == self.SETUP:
				# Update state
				print("processing SETUP\n")
				
				try:
					self.clientInfo['videoStream'] = VideoStream(filename)
					self.state = self.READY
				except IOError:
					self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
				
				# Generate a randomized RTSP session ID
				self.clientInfo['session'] = randint(100000, 999999)
				
				# Send RTSP reply
				self.replyRtsp(self.OK_200, seq[1])
				
				# Get the RTP/UDP port from the last line
				self.clientInfo['rtpPort'] = request[2].split(' ')[3]

				# Create a new socket for RTP/UDP
				self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				
				self.clientInfo['tuadi'] = threading.Event()
				self.clientInfo['tuanguoc'] = threading.Event()
				
		
				numframe = self.clientInfo['videoStream'].getnumFrame()
				
				self.gaptest()
				len = round(self.average * numframe)
			
				self.replyRtspp(self.OK_200, seq[1], len, numframe)
				self.pass_frame = round(5 / (len / numframe))
		
		# Process PLAY request 		
		elif requestType == self.PLAY:
				print("processing PLAY\n")
				self.state = self.PLAYING
				
				
				self.replyRtsp(self.OK_200, seq[1])
				
				# Create a new thread and start sending RTP packets
				self.clientInfo['event'] = threading.Event()
				self.clientInfo['worker']= threading.Thread(target=self.sendRtp) 
				self.clientInfo['worker'].start()
				#Code uoc tinh video duration
				#self.START_TIME = time()
		
		# Process PAUSE request
		elif requestType == self.PAUSE:
				print("processing PAUSE\n")
				self.state = self.READY
				
				self.clientInfo['event'].set()
			
				self.replyRtsp(self.OK_200, seq[1])
				
		# Process TEARDOWN request
		elif requestType == self.TEARDOWN:
			print("processing TEARDOWN\n")

			self.clientInfo['event'].set()
			
			self.replyRtsp(self.OK_200, seq[1])
			
			# Close the RTP socket
			self.clientInfo['rtpSocket'].close()
			#CODE UOC TINH
			'''
			if self.START_TIME:
				self.END_TIME = time()
				self.TOTAL_TIME += self.END_TIME - self.START_TIME
			'''
			
		elif requestType == self.DESCRIBE:
			print('processing DESCRIBE\n')
			dest_port = self.clientInfo['rtspSocket'][1][1]
			sessionid = self.clientInfo['session']
			des = 'v=0\n'
			des += f'm=video {dest_port} RTP/AVP 26\n'
			des += f'a=control:streamid= {sessionid}\n'
			des += f'a=rtpmap:26 JPEG/90000\n'
			des += f'a=mimetype: video/JPEG'
			self.repdes(self.OK_200, seq[1], des, filename)

		elif requestType == self.FORWARD:
			print('processing FORWARD\n')
			self.clientInfo['tuadi'].set()
			self.replyRtsp(self.OK_200, seq[1])

			
		elif requestType == self.BACKWARD:
			print('processing BACKWARD\n')
			self.clientInfo['tuanguoc'].set()
			self.replyRtsp(self.OK_200, seq[1])
			
			
	def sendRtp(self):
		"""Send RTP packets over UDP."""
		while True:
			self.clientInfo['event'].wait(0.05) 
			
			# Stop sending if request is PAUSE or TEARDOWN
			if self.clientInfo['event'].isSet(): 
				break 


			if self.clientInfo['tuadi'].isSet():
				data = self.clientInfo['videoStream'].fastward(self.pass_frame)
			elif self.clientInfo['tuanguoc'].isSet():
				data = self.clientInfo['videoStream'].fastward(self.pass_frame * -1)	
			else:
				data = self.clientInfo['videoStream'].nextFrame()
			if data: 
				frameNumber = self.clientInfo['videoStream'].frameNbr()
				try:
					address = self.clientInfo['rtspSocket'][1][0]
					port = int(self.clientInfo['rtpPort'])
					self.clientInfo['rtpSocket'].sendto(self.makeRtp(data, frameNumber),(address,port))
					self.clientInfo['tuadi'].clear()
					self.clientInfo['tuanguoc'].clear()
				except:
					print("Connection Error")
					#print('-'*60)
					#traceback.print_exc(file=sys.stdout)
					#print('-'*60)
			else:
				'''
				self.END_TIME = time()
				self.TOTAL_TIME += self.END_TIME - self.START_TIME
				self.START_TIME = 0
				print(f'Video duration: {round(self.TOTAL_TIME)}')	
				'''
				break
	def makeRtp(self, payload, frameNbr):
		"""RTP-packetize the video data."""
		version = 2
		padding = 0
		extension = 0
		cc = 0
		marker = 0
		pt = 26 # MJPEG type
		seqnum = frameNbr
		ssrc = 0 
		rtpPacket = RtpPacket()
		
		rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)
		
		return rtpPacket.getPacket()
		
	def replyRtsp(self, code, seq):
		"""Send RTSP reply to the client."""
		if code == self.OK_200:
			#print("200 OK")
			reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply.encode())
		
		# Error messages
		elif code == self.FILE_NOT_FOUND_404:
			print("404 NOT FOUND")
		elif code == self.CON_ERR_500:
			print("500 CONNECTION ERROR")
	
	def replyRtspp(self, code, seq, len, numframe):
		"""Send estimated video length and num of frame to the client."""
		if code == self.OK_200:
			#print("200 OK")
			reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
			reply += f'\nLen: {len}'
			reply += f'\nNumframe: {numframe}'
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply.encode())
		
		# Error messages
		elif code == self.FILE_NOT_FOUND_404:
			print("404 NOT FOUND")
		elif code == self.CON_ERR_500:
			print("500 CONNECTION ERROR")

	def repdes(self, code, seq, des, filename):
		'''Send sdp file to the client in des.sdp'''
		if code == self.OK_200:
			content_part = f'Content-Base: {filename}\n'
			content_part += f'Content-Type: application/sdp\n'
			content_part += f'Content-Length: {len(des)}\n'
			content_part += des

			reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session']) + '\n'+content_part
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply.encode())

	def gaptest(self):
		'''Estimate time to send a packet: try to send 3 first packet and take the average'''
		address = self.clientInfo['rtspSocket'][1][0]
		port = int(self.clientInfo['rtpPort'])
		interval = []
		even = threading.Event()
		self.frames = self.clientInfo['videoStream'].frame_list()
		i = 1
		for i in range(1,4):
					time1 = time()
					even.wait(0.05)
					self.clientInfo['rtpSocket'].sendto(self.makeRtp(self.frames[i - 1], i),(address,port))
					time2 = time()
					interval.append(time2 - time1)
		self.average = sum(interval) / 3
