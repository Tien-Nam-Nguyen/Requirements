import string


class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		try:
			self.file = open(filename, 'rb')
		except:
			raise IOError
		self.frameNum = 0
		self.frames = []
		self.totalframe = 0

	def nextFrame(self):
		"""Get next frame."""
		if self.frameNum + 1 <= self.totalframe:
			self.frameNum += 1
			return self.frames[self.frameNum - 1]

		
	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum
	
	def getnumFrame(self):
		'''Get total frame num'''
		while True:
			data = self.file.read(5) # Get the framelength from the first 5 bits
			if data: 
				framelength = int(float(data))
				# Read the current frame
				data = self.file.read(framelength)
				self.totalframe += 1
				self.frames.append(data)	
			else:
				self.file.seek(0)
				self.frameNum = 0
				break	
		return self.totalframe

	