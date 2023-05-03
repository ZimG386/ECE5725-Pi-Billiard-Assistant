from datetime import datetime
from multiprocessing import Process, Queue, Value
from scipy.spatial import ConvexHull
import copy
import cv2 as cv
import numpy as np
import time

# Time for initialization
time.sleep(1)

# Define a class for balls and the move function
class Object:
    def __init__(self, pos, speed, direct, radius):
        self.pos = pos # Ball position
        self.speed = speed # Ball speed, not used yet
        self.direct = direct # Ball direction vector
        self.radius = radius # Ball radius

    def move(self, hull): # Move the ball based on its direction vector
        self.pos[0] += self.direct[0]
        self.pos[1] += self.direct[1]
        # If the ball is out of the table, change its direction, not yet implemented
        res = point_in_hull(self.pos, hull)
        if res is not None:
            self.direct = collide_hull(self.direct[0:2], res)
            return False
        return True
    
def point_in_hull(point, hull, tolerance=1e-12):
        res = 0
        for eq in hull.equations:
            res = np.dot(eq[:-1], point) + eq[-1]
            if res >= tolerance:
                return eq[0:2]
        return None

def collide_hull(direct, eq):
    res = direct-2*np.dot(direct, eq)*eq 
    return  res  

# A helper function for collide detection between two objects
def collide(object1, object2):
    dist = np.linalg.norm(object1.pos-object2.pos)
    if dist <= (object1.radius + object2.radius) + 1:
        return True
    return False

# Change the speed of two objects based on real-world physics
def change_v(object1, object2):
    m1, m2 = object1.radius**2, object2.radius**2
    M = m1 + m2
    r1, r2 = object1.pos, object2.pos
    d = np.linalg.norm(r1-r2)**2
    v1 = object1.direct
    v2 = object2.direct
    # u1 = (v1 - 2*m2/M*np.dot(v1-v2,r1-r2)/d*(r1-r2))
    u2 = (v2 - 2*m1/M*np.dot(v2-v1,r2-r1)/d*(r2-r1))
    # object1.speed = [round(u1[0]), round(u1[1])]
    # We only care about the speed of the second object
    object2.direct = [u2[0], u2[1]]

# Simulate the cue stick behavior, hits the cue ball and let the cue ball move
def simulate_stick(object1, object2, num_iter, frame, hull):
    iter = 0
    collided = False
    ini_pos = copy.deepcopy(object1.pos)
    lines = np.array([[]])
    while iter <= num_iter:
        res = object1.move(hull)
        if res == False:
            break
        collided = collide(object1, object2)
        if collided:
            change_v(object1, object2)
            lines = np.append(lines, [[ini_pos[0], ini_pos[1], object1.pos[0], object1.pos[1]]], axis=0)
            lines = simulate_ball(object2, num_iter, frame, hull, lines, True)
            return lines
    if collided == False:
        lines = np.append(lines, [[ini_pos[0], ini_pos[1], object1.pos[0], object1.pos[1]]], axis=0)
    return lines

# Simulate the cue ball behavior, move the cue ball
def simulate_ball(object, num_iter, frame, hull, lines, flag):
    iter = 0
    ini_pos = copy.deepcopy(object.pos)
    while iter <= num_iter:
        res = object.move(hull)
        if res == False:
            if flag == True:
                simulate_ball(object, num_iter, frame, hull, False)
            break
    lines = np.append(lines, [[ini_pos[0], ini_pos[1], object.pos[0], object.pos[1]]], axis=0)
    return lines

def find_table(frame_hsv):
	# hsv color range for blue pool table
	lower_blue = np.array([110,50,50])
	upper_blue = np.array([130,255,255])
	# Mask out everything but the pool table (blue)
	mask = cv.inRange(frame_hsv, lower_blue, upper_blue)
	# Find the pool table contour
	contours, _ = cv.findContours(mask, cv.RETR_TREE, cv.CHAIN_APPROX_NONE)
	# Find the largest contour as the border of the table
	try:
		table = max(contours, key = cv.contourArea)
	except:
		print("No table found!")
		return None
	return cv.convexHull(table)[:, 0, :]

# Function for the Master Process
def grab_frame_display(run_flag, frame_queue, line_queue):
	global table
	start_datetime = datetime.now()
	initial = True
	while run_flag.value:
		# Capture frame-by-frame
		ret, frame = cap.read()
		# if frame is read correctly ret is True
		if not ret:
			print("Can't receive frame (stream end?). Exiting ...")
			break
		# Convert to hsv color space
		frame_hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)
		# Find the pool table if it is the first frame
		if initial:
			table = find_table(frame_hsv)
			initial = False
		# Check if time since last send to queue exceeds 30ms
		curr_datetime = datetime.now()
		delta_time = curr_datetime-start_datetime
		delta_time_ms = delta_time.total_seconds()*1000
		if delta_time_ms > 30 and frame_queue.qsize() < 4:
			start_datetime = curr_datetime
			frame_queue.put(frame_hsv)
			print('P0 Put frame, queue size: ', frame_queue.qsize())
		if not line_queue.empty():
			lines = line_queue.get()
			print('P0 Get line, queue size: ', line_queue.qsize())
			for i in lines:
				cv.line(frame, (i[0], i[1]), (i[2], i[3]), (0, 255, 0), 2)
		cv.imshow('frame',frame)
		if cv.waitKey(1) == ord('q'):
			cap.release()
			cv.destroyAllWindows()
			run_flag.value = 0
			print("Set run_flag 0")
			break
	print("Quiting P0")
	print('P0 frame queue empty: ', frame_queue.empty())
	print('P0 line queue empty: ', line_queue.empty())

# Process 1 detects the stick
def process_stick(run_flag, frame_queue, stick_queue, start_turn):
	while run_flag.value:
		if not frame_queue.empty() and start_turn.value == 1:
			start_turn.value = 2
			# Get frame from queue
			frame_hsv = frame_queue.get()
			# hsv color range for pink cue stick
			lower_pink = np.array([150, 120, 120])
			upper_pink = np.array([165, 255, 255])
			# Mask out everything but the cue stick (pink)
			mask = cv.inRange(frame_hsv, lower_pink, upper_pink)
			# Find the cue stick
			lines = cv.HoughLinesP(mask, 1, np.pi/180, 40, minLineLength=20, maxLineGap=0)
			print("Line coordinates:", lines)
			cue = 0
			if lines is not None:
				for i in range(0, len(lines)):
					l = lines[i][0]
					cue += l
				cue = cue / len(lines)
				cue = np.round(cue).astype(int)
			stick_queue.put(cue) # Put stick coordinates to queue
		else:
			time.sleep(0.03)
	print("Quiting P1")
	print('P1 frame queue empty: ', frame_queue.empty())

# Process 2 detects the ball
def process_ball(run_flag, frame_queue, stick_queue, ball_queue, start_turn):
	while run_flag.value:
		if not frame_queue.empty() and not stick_queue.empty() and start_turn.value == 2:
			start_turn.value = 3
			# Get frame from queue
			frame_hsv = frame_queue.get()
			sensitivity = 80
			# hsv color range for white ball
			lower_white = np.array([0, 0, 255 - sensitivity])
			upper_white = np.array([255, sensitivity, 255])
			# Mask out everything but the cue stick (pink)
			mask = cv.inRange(frame_hsv, lower_white, upper_white)
			circles = cv.HoughCircles(mask, cv.HOUGH_GRADIENT, 1, 20, param1=11, param2=11, minRadius=10, maxRadius=15)
			print("Ball coordinates:", circles)
			cue = stick_queue.get() # Get stick coordinates from queue
			cue = np.array([135, 670, 185, 661])
			if cue is not None:
				center = np.array([320, 240])
				d0 = np.linalg.norm(cue[0:2] - center)
				d1 = np.linalg.norm(cue[2:4] - center)
				d0 = 10
				d1 = 20
				# if d0 < d1:
				# 	cue[0], cue[2] = cue[2], cue[0]
				# 	cue[1], cue[3] = cue[3], cue[1]
				print("Cue stick coordinates:", cue)
				min = 0
				if circles is not None:
					circles = np.uint16(np.around(circles))
					d0 = 1000
					min = np.array([10, 10, 10])
					for i in circles[0, :]:
						d1 = np.linalg.norm(i[0:2] - cue[2:4])
						if d1 < d0:
							d0 = d1
							min = i
					print("Cue ball coordinates:", min)
					# cv.circle(frame, (min[0], min[1]), min[2], (0, 255, 0), 2)
					# cv.circle(frame, (min[0], min[1]), 2, (0, 0, 255), 3)
			ball_queue.put(min) # Put stick back
		else:
			time.sleep(0.03)
	print("Quiting P2")
	print('P2 frame queue empty: ', frame_queue.empty())
	print('P2 stick queue empty: ', stick_queue.empty())


# Process 3 computes Physics
def process_physics(run_flag, ball_queue, line_queue, start_turn):
	global table
	while run_flag.value:
		if not ball_queue.empty() and start_turn.value == 3:
			start_turn.value = 1
			x = ball_queue.get()
			cue_stick = np.array([135, 670, 185, 661])
			cue_ball = np.array([240, 660, 11])
			table = np.array([[1215, 620],[1179, 680], [1163, 682],
                  [80, 809], [59, 810], [58, 810],
                  [12, 774], [12, 263], [56, 223], 
                  [77, 217], [100, 214], [526, 161], 
                  [1043, 98], [1047, 98], [1055, 101], 
                  [1108, 135], [1114, 145], [1215, 608]
                  ])
			cv.drawContours(frame, [table], -1, (255,255,255), 2)
			for i in table:
				cv.circle(frame, (i[0], i[1]), 2, (255,255,255), 2, cv.LINE_AA)
			cv.line(frame, (cue_stick[0], cue_stick[1]), (cue_stick[2], cue_stick[3]), (0,0,0), 2, cv.LINE_AA)
			cv.circle(frame, (cue_ball[0], cue_ball[1]), cue_ball[2], (255,0,255), 2, cv.LINE_AA)
			hull = ConvexHull(table) # Turn the table coordinates into a convex hull
			stick_euclid = np.linalg.norm(cue_stick[2:4]-cue_stick[0:2])/10
			obj_stick = Object(cue_stick[2:4], 3, (cue_stick[2:4]-cue_stick[0:2])/stick_euclid, 4)
			obj_ball = Object(cue_ball[0:1], 0, [0,0], cue_ball[2])
			res = simulate_stick(obj_stick, obj_ball, 100, frame, hull)
			line_queue.put(res)
		else:
			#print("Processor 3 Didn't Receive Frame, sleep for 30ms")
			time.sleep(0.03)
	print("Quiting P3")
	print('P3 ball queue empty: ', ball_queue.empty())

RES_X = 640
RES_Y = 480
CENTER_X = RES_X/2
CENTER_Y = RES_Y/2
cap = cv.VideoCapture(0)
if not cap.isOpened():
	print("Cannot open camera")
	exit()
cap.set(cv.CAP_PROP_FRAME_WIDTH, RES_X)
cap.set(cv.CAP_PROP_FRAME_HEIGHT, RES_Y)

#Global Run Flag
table = np.array([])
frame = 0

if __name__ == '__main__':
	# run_flag controls all processes
	run_flag = Value('i', 1) 
	# start_turn controls process running sequence
	start_turn = Value('i', 1)  
	frame_queue = Queue()
	stick_queue = Queue()
	ball_queue = Queue()
	line_queue = Queue()
	p0 = Process(target=grab_frame_display, args=(run_flag, frame_queue, line_queue))
	p1 = Process(target=process_stick, args=(run_flag, frame_queue, stick_queue, start_turn))
	p2 = Process(target=process_ball, args=(run_flag, frame_queue, stick_queue, ball_queue, start_turn))
	p3 = Process(target=process_physics, args=(run_flag, ball_queue, line_queue, start_turn))
	p0.start()
	p1.start()
	p2.start()
	p3.start()
	p0.join()
	p1.join()
	p2.join()
	p3.join()