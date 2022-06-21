# This code implements YOLOv3 technique in order to detect car accidents on the video frames. 
# If you want to use this with camera, you can easily modify it

''' Results you can see in folders: cars, figures, output '''

# import the necessary packages
import numpy as np
import argparse
import time
import cv2
import os
import matplotlib.pyplot as plt
import glob
import vehicle_tracking as trackingpy # functions for tracking
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
import car_accidents as accidentspy # functions for detection
from yolo import YOLOv3 # class for yolo


path_of_file = os.path.abspath(__file__)
os.chdir(os.path.dirname(path_of_file))

thr_param = 0.3 # threshold for YOLO detection
conf_param = 0.5 # confidence for YOLO detection

frame_start_with = 1 # frame to start with
frame_end_with = 170 # number of image frames to work with in each folder (dataset)

filter_flag = 1 # use moving averaging filter or not (1-On, 0 - Off)

T_var = 200 # threshold in order to show only those cars that is moving... (50 is okay)

k_overlap = 0.3 # ratio (0-1) for overlapping issue | thresh_overlap = distance_between*k_overlap
frame_overlapped_interval = 10 # the interval (- frame_overlapped_interval + frame; frame + frame_overlapped_interval) to analyze if there were accident or not

T_acc = 1 # theshold in order to detect acceleration anomaly
angle_threshold = 1 #threshold to detect crash angle
trajectory_thresold = 0.1 #threshold to detect change in path direction

show_plots = 1 # show graphs when accident found or not [1 - Yes, 0 - No]


data_dir = "Dataset/" 	#dataset directory
dataset_path = glob.glob(data_dir+"*/") 		#reading all sub-directories in folder
print('Sub-directories',dataset_path)

# derive the paths to the YOLO weights and model configuration
weightsPath = '/content/YOLOv3-Car-Accident-Detection/yolo-coco/cfg/yolov3.cfg'
configPath = '/content/YOLOv3-Car-Accident-Detection/yolo-coco/weights/yolov3.weights'

# load our YOLO object detector trained on COCO dataset (80 classes)
print("[INFO] loading YOLO from disk...")
net = cv2.dnn.readNet(weightsPath, configPath)

yolov3 = YOLOv3(thr_param, conf_param, [2,3,5,7], net, use = 'tracking')

for path in dataset_path: # Loop through folders with different video frames (situations on the road) 
	split_path = path.split('/')
	folders = glob.glob(path)
	print('Processing folder',folders[0], '...')
	img_dir = split_path[1]  
	data_path = os.path.join(path,'*g')

	frame_counter = len(glob.glob(data_path))
	print('Number of frames:',frame_counter)

	files = []
	for q in range(frame_start_with, frame_end_with): # Loop through certain number of video frames in the folder
		path = folders[0]+'/'+str(q)+'.jpg'
		files.append(path)

	
	update_times = 1
	cars_dict = {}
	counter = 1
	images_saved = []
	for f1 in files:
		image = cv2.imread(f1)
		print('Processing frame:'+str(counter)+'/'+str(frame_counter),'in folder:'+folders[0]+'...')

		if type(image) is np.ndarray:
			images_saved.append(image)
			time_start = time.time()

			(H, W) = image.shape[:2]

			new_boxes, new_boxes_id, image = yolov3.detect_objects(image)
							
			# building cars data
			cars_dict = trackingpy.BuildAndUpdate(new_boxes, cars_dict, update_times)
			cars_labels = list(cars_dict)

			for car_label in cars_labels:
				car_path = cars_dict[car_label][0]
				image = trackingpy.plot_paths(car_path, image, cars_dict, car_label) # plot paths of the cars on the image
			cv2.putText(image, 'frame ' + str(frame_start_with+counter), (20, image.shape[0]-20), cv2.FONT_HERSHEY_SIMPLEX,
						3, (255,255,200), 2)			# put number of frame on the image

			time_end = time.time()
			print('FPS = ', 1/ (time_end - time_start))
			# show the output image
			cv2.imshow("Image", image)
			if cv2.waitKey(1) == 27: # you can break the loop by clicking 'Esc'
				break
			counter +=1

	#saving output image in folder output/
	cv2.imwrite('output/'+img_dir+'_final_frame.png', image)
	cv2.destroyAllWindows()
	#building dictionary of plot data
	cars_data = {}
	for label in cars_labels: 
		position  = cars_dict[label][0]
		direction = cars_dict[label][1]
		velocity = cars_dict[label][2]
		acceleration = cars_dict[label][3]
		w,h = cars_dict[label][5][2:4]
		x_pos = []
		y_pos = []
		angle = []
		time_frame = []
		cars_data[label]={}
		for i in range(len(position)):
			x_pos.append(position[i][0])
			y_pos.append(position[i][1])
			angle.append(np.arccos(direction[i][0][0]))
			time_frame.append(i)

		# filter data by using averaging filter in order to smooth it and reduce number of peaks

		x_pos, y_pos, angle, velocity, acceleration  = trackingpy.filter_data(x_pos, y_pos, angle, velocity, acceleration, filter_flag)

		cars_data[label]['x'] = x_pos
		cars_data[label]['y'] = y_pos
		cars_data[label]['time'] = time_frame
		cars_data[label]['angle'] = angle
		cars_data[label]['velocity'] = velocity
		cars_data[label]['acceleration'] = acceleration
		cars_data[label]['car diagonal'] = np.sqrt(w**2+h**2)


	#----------------------------------------------------------------------#
	

	####						DETECTION PART 							####


	#----------------------------------------------------------------------#

	# Exlude cars that doesn't move at all (so, there wasn't any accident or smth with them)
	cars_labels_to_analyze = []
	for label in cars_labels: 
		# Data for a three-dimensional line
		if np.var(np.sqrt(np.power(cars_data[label]['x'],2)+np.power(cars_data[label]['y'],2))) <T_var:
			del cars_data[label]
		else:	
			cars_labels_to_analyze.append(label)

	path = trackingpy.Path(cars_data)

	# Interpolate data for each car (it's needed because YOLO didn't detect car in 
	# each frame. So,we need to fill empty space)
	flag_loop_continue = 0
	for label in cars_labels_to_analyze:
		interp_points, value_error = path.interpolate(label, number = frame_end_with - frame_start_with, method = 'cubic')
		if value_error == 1:
			flag_loop_continue = 1
		else:	
			cars_data[label]['x'] = interp_points[:,0]
			cars_data[label]['y'] = interp_points[:,1]
			cars_data[label]['time'] = interp_points[:,2]
			cars_data[label]['angle'] = interp_points[:,3]
			cars_data[label]['velocity'] = interp_points[:,4]
			cars_data[label]['acceleration'] = interp_points[:,5]
	if flag_loop_continue == 1:
		continue
	checks = [0,0,0]

	#------Checking vehicle overlapps--------#
	overlapped = set()
	flag = 1
	frames = [int(i) for i in range(frame_end_with - frame_start_with)]
	for frame in frames:
		for first_car in cars_labels_to_analyze:
			for second_car in cars_labels_to_analyze:
				if (int(second_car) != int(first_car)) and (accidentspy.check_overlap((cars_data[first_car]['x'][frame],cars_data[first_car]['y'][frame]),(cars_data[second_car]['x'][frame],cars_data[second_car]['y'][frame]), cars_data[first_car]['car diagonal'], cars_data[second_car]['car diagonal'],k_overlap)):
					overlapped.add(first_car)
					overlapped.add(second_car)
					if flag:
						frame_overlapped = frame
						flag = 0	
	if not flag:					
		print('labels of overlapped cars:', overlapped,'. Frame of potential accident:', frame_start_with + frame_overlapped)
		checks[0] = 1.0
	elif flag:
		print('There weren\'nt any overlapping cars this time... Let\'s check further...')
		checks[0] = 0.5
	potential_cars_labels = [label for label in overlapped]
				
	#------Checking acceleration anomaly--------#
	'''When two vehicles are overlapping, we find the acceleration of the vehicles from their speeds captured in the
	dictionary. We find the average acceleration of the vehicles
	for N frames before the overlapping condition and the
	maximum acceleration of the vehicles N frames after it.
	We find the change in accelerations of the individual vehicles
	by taking the difference of the maximum acceleration and
	average acceleration during overlapping condition'''

	frames_before = [int(i) for i in range(frame_overlapped-frame_overlapped_interval, frame_overlapped-1)]

	acc_average = []
	for label in potential_cars_labels:
		acc_av = 0
		t = 1
		for frame in frames_before:
			acc_av = acc_av*(t-1)/t + cars_data[label]['acceleration'][frame]/t
			t += 1
		acc_average.append(acc_av)
	frames_after = [int(i) for i in range(frame_overlapped, frame_overlapped+frame_overlapped_interval-1)]	
	acc_maximum = []
	for label in potential_cars_labels:
		acc_max = 0
		for frame in frames_after:
			if cars_data[label]['acceleration'][frame]>acc_max:
				acc_max = cars_data[label]['acceleration'][frame]
		acc_maximum.append(acc_max)

	acc_diff = np.mean(np.subtract(acc_maximum, acc_average))

	if acc_diff >= T_acc:
		checks[1] = 1
	else:
		checks[1] = 0.5

	#----Angle Anomalies----#
	angle_anomalies = []
	for label in potential_cars_labels:
		
		angle_difference = accidentspy.check_angle_anomaly(cars_data[label]['angle'],frame_overlapped,frame_overlapped_interval)
		angle_anomalies.append(angle_difference)

	if len(angle_anomalies)>0:	
		max_angle_change = max(angle_anomalies)
		print('change in angle :', max_angle_change)
		if max_angle_change >= trajectory_thresold:
			checks[2] = 1
		else:
			checks[2] = 0.5
	else:
		checks[2] = 0.5

	#----Checkings----#
	print('score',sum(checks))
	if (checks[0]+checks[1] + checks[2])>=1.99:
		image = images_saved[frame_overlapped]
		print('accident happened at frame ',frame_overlapped,' between cars ', overlapped)
		for car_label in potential_cars_labels:
			cv2.circle(image, (int(cars_data[car_label]['x'][frame_overlapped]), int(cars_data[car_label]['y'][frame_overlapped])), 50,  (255,255,0), 2)
		#saving output image in folder output/
		cv2.imwrite('cars/'+img_dir+'accident.png', image)			


	#-----# Plots			
	fig = plt.figure()
	ax = fig.gca(projection='3d')	
	for label in potential_cars_labels: 	
		ax.plot(cars_data[label]['x'],cars_data[label]['y'], frames, label = label)
	ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
	ax.set_xlabel('x')
	ax.set_ylabel('y')
	X = np.arange(0, W, W//10)
	Y = np.arange(0, W, W//10)
	X, Y = np.meshgrid(X, Y)
	Z = np.full((10,1),frame_overlapped)
	ax.plot_wireframe(X, Y, Z)
	Z = np.full((10,1),frame_overlapped - frame_overlapped_interval)
	ax.plot_wireframe(X, Y, Z)	
	Z = np.full((10,1),frame_overlapped + frame_overlapped_interval)
	ax.plot_wireframe(X, Y, Z)				   			   
	ax.set_zlabel('frames')
	ax.set_title('cars trajectories')
	plt.savefig('figures/'+img_dir+'_y_x_t.png')

	if show_plots:
		plt.show()

	plt.figure(figsize=(10,8))
	plt.subplots_adjust(wspace=0.5)
	plt.subplot(221)
	for label in potential_cars_labels: 
		plt.plot(frames,cars_data[label]['angle'], label = label)
	plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
	plt.xlabel('frame')
	plt.grid()
	plt.axvline(x=frame_overlapped - frame_overlapped_interval, color='r', linestyle='--')
	plt.axvline(x=frame_overlapped, color='k', linestyle='--')
	plt.axvline(x=frame_overlapped + frame_overlapped_interval, color='r', linestyle='--')
	plt.ylabel('angle (rad)')
	plt.title('cars angles')


	plt.subplot(222)
	for label in potential_cars_labels: 
		plt.plot(frames,cars_data[label]['velocity'], label = label)
	plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
	plt.xlabel('frame')
	plt.grid()
	plt.axvline(x=frame_overlapped - frame_overlapped_interval, color='r', linestyle='--')
	plt.axvline(x=frame_overlapped, color='k', linestyle='--')
	plt.axvline(x=frame_overlapped + frame_overlapped_interval, color='r', linestyle='--')
	plt.ylabel('velocity (pixel/frame)')
	plt.title('cars velocities')


	plt.subplot(223)
	for label in potential_cars_labels: 
		plt.plot(frames,cars_data[label]['acceleration'], label = label)
	plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
	plt.xlabel('frame')
	plt.ylabel(r'acceleration (pixel/${frame}^2$)')
	plt.axvline(x=frame_overlapped - frame_overlapped_interval, color='r', linestyle='--')
	plt.axvline(x=frame_overlapped, color='k', linestyle='--')
	plt.axvline(x=frame_overlapped + frame_overlapped_interval, color='r', linestyle='--')
	plt.title('cars accelerations')
	plt.grid()
	plt.savefig('figures/'+img_dir+'_Info.png')
	if show_plots:
		plt.show()

