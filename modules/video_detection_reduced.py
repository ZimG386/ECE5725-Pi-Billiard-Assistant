#
# W_yz2874_zg284 5/9/2023 Frame for Single Process Video Detection
#

import cv2 as cv
import numpy as np
import copy
from scipy.spatial import ConvexHull
import time
import pygame
from pygame.locals import * # for event MOUSE variables

# cap = cv.VideoCapture('./696_720p.mp4')
# cap = cv.VideoCapture('./716_720p.mp4')
cap = cv.VideoCapture('./806_480P.mp4')

# cap = cv.VideoCapture(0)

# Retake table map every 120 frames to avoid effect of hand movement
count = 0

# Define a class for balls and the move function
class Object:
    def __init__(self, pos, speed, direct, radius):
        self.pos = pos # Ball position
        self.speed = speed # Ball speed, not used yet
        self.direct = direct # Ball direction vector
        self.radius = radius # Ball radius

    def move(self, hull): # Move the ball based on its direction vector
        self.pos += self.direct
        # If the ball is out of the table, change its direction, not yet implemented
        res = point_in_hull(self.pos + 3 * self.direct, hull)
        if res is not None:
            self.direct = collide_hull(self.direct[0:2], res)
            return False
        return True

# Check if a point is inside the convex hull
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
def simulate_stick(object1, num_iter, image, hull, lines, flag):
    iter = 0
    ini_pos = copy.deepcopy(object1.pos)
    while iter <= num_iter:
        res = object1.move(hull)
        if res == False:
            if flag > 0:
                flag -= 1
                lines.append([ini_pos[0], ini_pos[1], object1.pos[0], object1.pos[1]])
                lines = simulate_stick(object1, num_iter, image, hull, lines, flag)
            break
    return lines

def find_table(frame_hsv):
    # hsv color range for blue pool table
    lower_blue = np.array([100,100,100])
    upper_blue = np.array([130,255,255])
    # Mask out everything but the pool table (blue)
    mask = cv.inRange(frame_hsv, lower_blue, upper_blue)
    # cv.imshow("cropped table", mask)
    # Find the pool table contour
    contours, _ = cv.findContours(mask, cv.RETR_TREE, cv.CHAIN_APPROX_NONE)
    # Find the largest contour as the border of the table
    try:
        table = max(contours, key = cv.contourArea)
    except:
        print("No table found!")
        return None
    return cv.convexHull(table)

code_run = True
# GPIO.setmode(GPIO.BCM) # Initialize GPIO mode and setup input pin
# GPIO.setup(26, GPIO.IN, pull_up_down=GPIO.PUD_UP)
# GPIO.add_event_detect(26, GPIO.FALLING, callback=GPIO26_callback, bouncetime=300)
# Initialize pygame and set general parameters
pygame.init() # MUST occur AFTER os enviroment variable calls
pygame.mouse.set_visible(True)
WHITE = 255, 255, 255
BLACK = 0, 0, 0
screen = pygame.display.set_mode((852, 480)) # Set screen size

# Define the buttons and the font
my_font = pygame.font.Font('From Cartoon Blocks.ttf', 50) # Font size 50
my_buttons = {'quit':(852/2, 400)} # Button dictionary
screen.fill(BLACK) # Erase the work space

header_font = pygame.font.Font('From Cartoon Blocks.ttf', 60)
header_text = header_font.render("Pi Billiard Assistant", True, WHITE)
header_rect = header_text.get_rect(center=(852/2, 140))
screen.blit(header_text, header_rect)

script_font = pygame.font.Font('From Cartoon Blocks.ttf', 40)
script_text = script_font.render("Press the button to start", True, WHITE)
script_rect = script_text.get_rect(center=(852/2, 240))
screen.blit(script_text, script_rect)

# Initialize the button and display it on the screen
my_buttons_rect = {}
for my_text, text_pos in my_buttons.items():
    text_surface = my_font.render(my_text, True, WHITE)
    rect = text_surface.get_rect(center=text_pos)
    screen.blit(text_surface, rect)
    my_buttons_rect[my_text] = rect # save rect for 'my-text' button

pygame.display.flip()

cv_on = False

while code_run: # main loop
    for event in pygame.event.get(): # for detecting an event for touch screen...
        if (event.type == MOUSEBUTTONDOWN):
            pos = pygame.mouse.get_pos()
        elif (event.type == MOUSEBUTTONUP):
            pos = pygame.mouse.get_pos()
            for (my_text, rect) in my_buttons_rect.items(): # for saved button rects...
                if (rect.collidepoint(pos)): # if collide with mouse click...
                    if (my_text == 'quit'): # indicate correct button press
                        code_run = False
                        cv_on = True
                        pygame.quit()


while cap.isOpened() and cv_on:
    
    ret, frame = cap.read()
    print(cap.get(cv.CAP_PROP_FRAME_HEIGHT))
    print(cap.get(cv.CAP_PROP_FRAME_WIDTH))
    time.sleep(0.05)
    cv.namedWindow('frame', cv.WINDOW_NORMAL) # Display full screen
    cv.setWindowProperty('frame', cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)
    if not ret:
        print("Can't receive frame (stream end?). Exiting ...")
        cap.release()
        cv.destroyAllWindows()
        break
    frame_hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)

    if count == 0:
        table = find_table(frame_hsv)

    new_mask = np.zeros_like(frame)
    img_new = cv.drawContours(new_mask, [table], -1, (255, 255, 255), -1)
    cropped = cv.bitwise_and(frame, img_new)
    # cv.imshow("cropped", cropped)

    lower = np.array([140, 50, 50])
    upper = np.array([170, 255, 255])
    mask = cv.inRange(frame_hsv, lower, upper)
    # cv.imshow("mask", mask)

    lines = cv.HoughLinesP(mask, 1, np.pi/180, 40, None, 20, 0)
    # print("Line coordinates:", lines)
    cue = 0
    if lines is not None:
        for i in range(0, len(lines)):
            l = lines[i][0]
            cue += l
            cv.line(frame, (l[0], l[1]), (l[2], l[3]), (0,0,0), 2, cv.LINE_AA)
        cue = cue / len(lines)
        cue = cue.astype(int)
    # print(lines)

    if lines is not None:
        center = np.array([320, 240])
        d0 = np.linalg.norm(cue[0:2] - center)
        d1 = np.linalg.norm(cue[2:4] - center)
        if d0 < d1:
            cue[0], cue[2] = cue[2], cue[0]
            cue[1], cue[3] = cue[3], cue[1]
        # print("Cue stick coordinates:", cue)

    hull = ConvexHull(table[:,0,:]) # Turn the table coordinates into a convex hull

    if cue is not 0:
        # print(hull.points)
        # print('Found cue!', cue)
        cue = np.array(cue, dtype=np.half)
        stick_euclid = np.linalg.norm(cue[2:4]-cue[0:2])/15
        vec = np.array((cue[2:4]-cue[0:2])/stick_euclid, dtype=np.half)
        obj_stick = Object(cue[2:4], 3, vec, 5)
        lines = []
        lines = simulate_stick(obj_stick, 100, frame, hull, lines, 3)
        print(lines)
        for i in lines:
            # pygame.draw.line(screen, WHITE, (int(i[0]), int(i[1])), (int(i[2]), int(i[3])), 5)
            cv.line(frame, (int(i[0]), int(i[1])), (int(i[2]), int(i[3])), (0,0,0), 2, cv.LINE_AA)
			
    # pygame.display.flip() # Update the display
    cv.imshow("frame", frame)
    if cv.waitKey(1) == ord('q'):
            cap.release()
            cv.destroyAllWindows()

            break

    count += 1
    if count >= 30:
        count = 0

cap.release()
cv.destroyAllWindows()