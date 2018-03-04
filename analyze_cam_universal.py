import json
import cv2
import numpy as np
import time
import requests
from PIL import Image
from io import BytesIO
import threading
from filelock import Timeout, FileLock
import os

historyQueue = []		# rolling history of recent webcam images to help detect spoofing
timestamps = []
IMAGE = 0				# index of image for each object in history queue
COGNITIVE = 1			# index of cognitive data for each object in history queue
ACCEL = 2				# index of sensor data for each object in history queue
historyLen = 20		# number of past data entries kept in rolling history

apiKeys = ['1b8a0e91c0464595a236a1623336b3be', '526edc0134c74f789e72e23d89622843', '6c9efce637af4ef4b2e76556ccd4c6fe', '358e2f8a85c4433a9947eb7d0ab7978b', 'ecce36f84b834b198cdae2120cba1258', '7ddb75c9ced54c6096e8254d0ad8ef35', '3f3fec7c6b624abbb3ef0baae547d6d8', '95a35f2f364f4e44b9224b1765bffd11', '611eb0fbe31945d29cc9bdc8d55fced5', '9e64f255e27747119c5b6046cfc71eec', '4a177b7db1e94b1eba28912502f5ae15', '85c0b99e69ed4691bf63ba10dc4e6ce7', 'bb4c29de7acb4de880d03a3216ffa823', '4a4c16053cc94ffea42337e10ddb9ce8']
firstStarted = False
firstFinished = False

def analyzeImg(imgResp, apiKey):
	"""
	Sends encoded image through Microsoft computer vision API to get tags and categories.
	Args:
		imgResp: image response from urlopening webcam image
		apiKey: Computer Vision API key
	Returns:
		json object with 'categories' and 'tags' as keys
	"""
	headers = {
	  'content-type':'application/octet-stream',
	  'Ocp-Apim-Subscription-Key': apiKey
	}

	params = {
	  'visualFeatures': 'Categories,Tags,Description'
	}

	baseUrl = 'https://westcentralus.api.cognitive.microsoft.com/vision/v1.0/analyze'
	
	response = None
	try:
		response = requests.post(baseUrl, params=params, headers=headers, data=imgResp)
	except requests.exceptions.RequestException as e:
		print(e)
		return ''
	categories = response.json()
	return categories

def getOpenCVImage(imgResp):
	"""
	Converts URL image to OpenCV image.
	Args:
		imgResp: content from url request to image
	Returns:
		OpenCV image
	"""
	img = Image.open(BytesIO(imgResp)).convert('RGB')
	cvImg = np.array(img)
	# convert to BGR
	cvImg = cvImg[:, :, ::-1].copy()
	return cvImg

def displayImage(cvImg, state):
	"""
	Displays webcam image on screen.
	Args:
		imgResp: image reponse from urlopening webcam image
		state: true for locked, false for unlocked
	"""
	cv2.imshow('IPWebcam', cvImg)
	cv2.waitKey(0)
	cv2.destroyAllWindows()

def updateRollingHistory(image, cognitiveData, maxAccelMag):
	"""
	Updates queue of recent webcam image, cognitive data, and sensor data.
	Args:
		image: OpenCV image of current webcam view
		cognitiveData: json object from computer vision API
		maxAccelMag: maximum acceleration
	Returns:
		True if spoofed, False if not spoofed
	"""
	entry = [0]*3
	entry[IMAGE] = image
	entry[COGNITIVE] = cognitiveData
	entry[ACCEL] = maxAccelMag
	historyQueue.insert(0, entry)
	timestamps.insert(0, time.time())
	if len(historyQueue) > historyLen:
		historyQueue.pop()
		timestamps.pop()

def simplifyImage(image):
	"""
	Simplifies image for motion detection.
	Args:
		image: OpenCV image
	Returns:
		blurred black and white image
	"""
	gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)	# convert to BW
	gray = cv2.GaussianBlur(gray, (21, 21), 0)		# blur to compensate for noise
	return gray

def isSpoofed(image, cognitiveData, sensorData):
	"""
	Returns if the camera is being covered up or fooled based on recent recorded data.
	Args:
		image: OpenCV image of current webcam view
		cognitiveData: json object from computer vision API
		sensorData: json object from IP webcam sensor data
	Returns:
		True if spoofed, False if not spoofed
	"""
	
	# for testing with plain video
	if sensorData == None:
		return False
	
	# detect motion of camera by getting max magnitude in last data collection
	maxAccelMag = 0
	data = sensorData['lin_accel']['data']
	for dataPoint in data:
		accel = dataPoint[1]
		mag = accel[0]*accel[0] + accel[1]*accel[1] + accel[2]*accel[2]
		if mag > maxAccelMag:
			maxAccelMag = mag
	
	updateRollingHistory(image, cognitiveData, maxAccelMag)
	
	# if no history, can't say it's spoofed
	if len(historyQueue) < 2:
		return False
	
	# detect motion of image in OpenCV by comparing this frame to a frame about deltaT ago
	maxImgDelta = 0
	lastImgDelta = 0
	deltaT = 2		# in seconds
	i = 0
	
	# copy to prevent thread problems
	historyCopy = historyQueue[:]
	timeCopy = timestamps[:]
	
	while i < len(historyCopy):
		j = i
		while j < len(historyCopy) - 1 and timeCopy[i] - timeCopy[j] < deltaT:
			j += 1
		if j == i:
			break
		
		lastFrame = simplifyImage(historyQueue[j][IMAGE])		
		thisFrame = simplifyImage(historyQueue[i][IMAGE])
		frameDelta = cv2.absdiff(lastFrame, thisFrame)
		averageDelta_per_row = np.average(frameDelta, axis=0)
		averageDelta = np.average(averageDelta_per_row, axis=0)
		if i == 0:
			lastImgDelta = averageDelta
		if averageDelta > maxImgDelta:
			maxImgDelta = averageDelta

		i += 1
	
	# thresholds chosen based on data analysis
	if lastImgDelta < 10 or maxImgDelta < 15 or maxAccelMag/lastImgDelta > 1:		# moving more than image shows
		return True
	
	return False
	

def decideState(image, cognitiveData, sensorData, thresholdConfidence):
	"""
	Returns if the gun should lock or not based on image.
	Args:
		image: OpenCV image of current webcam view
		cognitiveData: json object from computer vision API
		sensorData: json object from IP webcam sensor data
		thresholdConfidence: minimum confidence (0 to 1) of finding multiple people
	Returns:
		0\\1\\2 if gun can shoot \\ covered camera \\ crowd
	"""
	if cognitiveData == '':		# no wifi signal
		return 1
	
	try:
		# select relevant tags to flag as don't shoot
		flagTags = ['crowd', 'people', 'group', 'person', 'man', 'woman', 'young', 'sitting', 'standing']
		captionInclusions = ['people', 'man', 'woman', 'boy', 'girl', 'person']
		
		categories = cognitiveData['categories']
		tags = cognitiveData['tags']

		# before checking for people, make sure image isn't being spoofed (staying still while gun is moving)
		if isSpoofed(image, cognitiveData, sensorData):
			return 1

		caption = cognitiveData['description']['captions'][0]['text']
		for captionInclusion in captionInclusions:
			if captionInclusion in caption:
				return 2

		for category in categories:
			name = category['name']
			score = category['score']
			if 'people' in name:
				return 2
		for tag in tags:
			name = tag['name']
			score = tag['confidence']
			if name in flagTags and score > thresholdConfidence:
				return 2
	except KeyError:
		print(cognitiveData)
	
	return 0

def getState(camUrl, apiKey, path):
	"""
	Writes file 0\\1\\2 if gun can shoot \\ covered camera \\ crowd
	Args:
		url: web address to image
		apiKey: Computer Vision API key
		path: string (ending in \\) of path to save filelock file about gun status
	"""
	global firstFinished, firstStarted
	
	if not firstStarted:
		firstStarted = True
	elif not firstFinished and apiKey == apiKeys[0]:
		firstFinished = True
	threading.Timer(7, getState, args=(camUrl,apiKey,path,)).start()
	
	image = 'shot.jpg'
	sensors = 'sensors.json'
	lock = FileLock(path + 'threading_file.lock')
	
	imgResp = None
	sensorResp = None
	try:
		imgResp = requests.get(url + image).content
		sensorResp = json.loads(requests.get(url + sensors).content.decode('utf-8'))
	except requests.exceptions.RequestException as e:
		print(e)
		return
	cvImg = getOpenCVImage(imgResp)
	cognitiveData = analyzeImg(imgResp, apiKey)
	state = decideState(cvImg, cognitiveData, sensorResp, 0.1)
	with lock:
		open(path + 'lock.txt', 'w').write(str(state))		# writes 0 if unlocked, 1 if locked
	print(str(state))

def checkCam(camUrl, timeStep, path):
	"""
	Continuously checks webcam at given url.
	Args:
		url: web address to image
		timeStep: time between threads
		path: string (ending in \\) of path to save filelock file about gun status
	"""
	threads = []
	ind = 0
	t1 = time.time()
	while len(threads) < len(apiKeys) and not firstFinished:
		t = threading.Thread(target=getState, args=(camUrl,apiKeys[ind],path,))
		t.start()
		threads.append(t)
		time.sleep(timeStep)
		print('spawned thread', ind)
		ind = (ind+1) % len(apiKeys)
	print(time.time() - t1)


def downloadVideo(path, url):
	"""
	Writes video stream to jpg files: img1.jpg is recent image, img2.jpg is old
	Goes at around 6 fps
	Args:
		path: string path to save images (ends with \\)
		url: webcam url
	"""
	empty = Image.new('RGB', (1, 1))
	empty.save(path + 'shot.jpg', 'JPEG')
	while True:
		imgResp = requests.get(url + 'shot.jpg').content
		img = Image.open(BytesIO(imgResp)).convert('RGB')
		img.save(path + 'img2.jpg', 'JPEG')
		os.remove(path + 'shot.jpg')
		os.rename(path + 'img2.jpg', path + 'shot.jpg')

def getVideoState(apiKey, imgResps, names):
	"""
	Writes file 0\\1\\2 if gun can shoot \\ covered camera \\ crowd
	Args:
		apiKey: Computer Vision API key
		imgResps: list of images encoded from reading frame
		names: frame names of imgResps given
	"""
	global firstFinished, firstStarted
	
	if not firstStarted:
		firstStarted = True
	elif not firstFinished and apiKey == apiKeys[0]:
		firstFinished = True
	
	if len(imgResps) > 1:
		threading.Timer(6.5, getVideoState, args=(apiKey,imgResps[1:],names[1:])).start()
	
	cvImg = getOpenCVImage(imgResps[0])
	cognitiveData = analyzeImg(imgResps[0], apiKey)
	state = decideState(cvImg, cognitiveData, None, 0.1)
	
	colors = [(0, 255, 0), (0, 0, 0), (255, 0, 0)]
	orig = Image.open(BytesIO(imgResps[0])).convert('RGB')
	tint = Image.new('RGB', (orig.width, orig.height), colors[state])
	outImg = Image.blend(orig, tint, 0.2)
	outImg.save('.\\seq-output\\' + names[0], 'JPEG')
	print(names[0])

def testOnStaticVideo():
	"""
	Determines gun lock/unlock on jpg sequence from .\\seq-input/ and saves
	annotated version to .\\seq-output/
	"""
	imgResps = []
	names = []
	for file in os.listdir(os.fsencode('.\\seq-input')):
		filename = os.fsdecode(file)
		if filename.endswith('.jpg'):
			imgResp = ''
			try:
				f = open('.\\seq-input\\' + filename, 'rb')
				imgResp = f.read()
				f.close()
			except IOError:
				print('Cannot get image')
			imgResps.append(imgResp)
			names.append(filename)
	
	threads = len(apiKeys)
	
	# divide imgResps and names into # threads roughly equal chunks
	roughChunk = len(imgResps) // threads
	imgSplits = []
	nameSplits = []
	for i in range(threads):
		imgSplits.append(imgResps[i*roughChunk:(i+1)*roughChunk])
		nameSplits.append(names[i*roughChunk:(i+1)*roughChunk])
	imgSplits[-1] = imgResps[(threads-1)*roughChunk:]
	nameSplits[-1] = names[(threads-1)*roughChunk:]
	
	for i in range(threads):
		imgSplit = imgSplits[i]
		nameSplit = nameSplits[i]
		t = threading.Thread(target=getVideoState, args=(apiKeys[i],imgSplit,nameSplit))
		t.start()
		t.join()
		print('spawned thread', i)

if __name__ == '__main__':
	url = 'http://10.8.57.71:8080/'		# Alycia
# 	url = 'http://10.8.56.160:8080/'	# Albert

	checkCam(url, 0.5, '..\\Unity\\XboxTest\\Assets\\')
# 	t = threading.Thread(target=downloadVideo, args=('..\\Unity\\XboxTest\\Assets\\', url,))
# 	t.start()