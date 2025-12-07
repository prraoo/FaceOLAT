"""
source ../setup_env
metashape scan_reconstruction.py
"""
import os
import sys

#if "/HPS/RTMPC3/work/olek/miniconda/lib" not in os.environ['LD_LIBRARY_PATH']:
#  print('please add \nexport LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/HPS/RTMPC3/work/olek/miniconda/lib \n to your ~/.bash_profile to run metashape script')
#  sys.exit(0)
#   
#sys.path.append('/HPS/RTMPC3/work/olek/miniconda/site-packages/')
#sys.path.append('/HPS/RTMPC3/work/olek/miniconda/lib/python3.8/site-packages/')

import Metashape
from pathlib import Path
import time
import shutil 
from PIL import Image
import fcntl
import glob
import av
from av import time_base as AV_TIME_BASE
from threading import Thread
from scipy.spatial import KDTree
import math
#print (sys.path)


RUNNING_TIME = 23 * 60 #run 23 hours


### CHANGE THESE ONLY ###################################################################################################

SEQUENCES = [ 
          	   '/HPS/RLData1/work/test_dataset/calib_christen',
               '/HPS/RLData1/work/test_dataset/calib_christen/external',
          

             ] 

OUTPUTDIRS =[
               '/HPS/RLData1/work/test_dataset/calib_christen/calib_metashape',

            
             ]
APPLY_MASK = False
SCALE_TO_MM = False
######################################################################################################


use_video = 1 
use_onlyIR = 0
frame_start = 19 # in sec
frame_end = 0 # for video should be 0
index_offset = [-1,-1]
keyframe_interval = [-1,-1]	 
doc = Metashape.app.document
#check that length of all list is equal
#if len(SEQUENCES) != len(OUTPUTDIRS):
#   print('Number of sequences, outputdirs has to be the same!')
#   exit(-1)

seq_id = 0
SCAN_PATH = ''
OUTPUT_DIR = '' 
MASK_PATH = ''
CALIB_PATH = ''
CAMSORT_PATH = ''
SCAN_PATH_EXTRA = ''

########################################################################################################################
#CALIB_PATH = '/HPS/ObjectsInTheAir/work/RECORDINGS/RESIZED/Zhi_recordings/calib_with_floor'

video_pattern = 'stream%03d'

scan_video_container = []

mask_video_container = []

padding_global = '%06d'
### PARAMETERS ##########################################################################################################
FORMAT_IMAGE_INPUT = 1 # or 0

# masking
MASK_TOLERANCE = 10



# photos alignment
# photos alignment
ALIGNMENT_ACCURACY = 1  # HighestAccuracy, HighAccuracy, MediumAccuracy, LowAccuracy, LowestAccuracy
ALIGNMENT_PRESELECTION = True # NoPreselection, GenericPreselection, for the image alignment
KEYPOINT_LIMIT = 80000
TIEPOINT_LIMIT = 8000
FILTER_TIE_POINTS = False

# building dense cloud
CLOUD_QUALITY = 2 # UltraQuality, HighQuality, MediumQuality, LowQuality, LowestQuality
FILTER_MODE =  Metashape.MildFiltering # NoFiltering, MildFiltering, ModerateFiltering, AggressiveFiltering

#Build Model
SURFACE_QUALITY = Metashape.Arbitrary
#SURFACE_INTERPOLATION = Metashape.DisabledInterpolation#Metashape.EnabledInterpolation DisabledInterpolation
SURFACE_INTERPOLATION = Metashape.EnabledInterpolation
FACE_COUNT = Metashape.HighFaceCount # Metashape.FaceCount.LowFaceCount, Metashape.FaceCount.MediumFaceCount, Metashape.FaceCount.HighFaceCount
# mapping texture
TEXTURE_SIZE=4096
#########################################################################################################################
#obj export
MODEL_FORMAT = Metashape.ModelFormat.ModelFormatOBJ

IMAGE_W = 4112
IMAGE_H = 3008
#IMAGE_W = 2056
#IMAGE_H = 1504

camera_list = []
ir_list = [] 
camera_exist_list = []
number_of_valid_cameras = 0

class FileLock():
    def __init__(self, fpath):
        if fpath is Path:
            self.lock = fpath
        else:
            self.lock = Path(fpath)
        self.has_lock = True

    def __enter__(self):
        print('Locking file %s'%self.lock)
        self.f = open(self.lock.as_posix(),'w')
        try:
            fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            #self.f.write(hostname())
            self.f.flush()
        except IOError:
            print('Locking failed %s'%self.lock)
            self.has_lock = False
        return self
    def __exit__(self, type, value, traceback):
        if self.has_lock:
            print('Unlocking file %s'%self.lock)
            self.f.close()
            try:
                self.lock.unlink()
            except:
                pass

def get_keyframe_interval(cap):
    frame_number = 0   
    
    fps = cap.streams.video[0].average_rate
    
    video_stream = cap.streams.video[0]
    
    assert int(1 / video_stream.time_base) % fps == 0
    
    
    offset_timestamp = int(1 / video_stream.time_base / fps)
    video_stream.codec_context.skip_frame = "NONKEY"
    
    target_timestamp = int((frame_number * AV_TIME_BASE ) / video_stream.framerate)
      
    cap.seek(target_timestamp)
    result  = []
    iter = 0
	
    for frame in cap.decode(video_stream):
        #print(frame)	
        if(iter>1):
           video_stream.codec_context.skip_frame = "DEFAULT"		
           return result[1] - result[0]
           break	   
        result.append(int(frame.pts /  offset_timestamp))
        iter+=1
    	 
    
       
    video_stream.codec_context.skip_frame = "DEFAULT"	
    return -1

def get_timestamp_offset(cap):

   frame_number = 0   
   
   fps = cap.streams.video[0].average_rate
  
   video_stream = cap.streams.video[0]
   
   assert int(1 / video_stream.time_base) % fps == 0
   
  
   offset_timestamp = int(1 / video_stream.time_base / fps)

  
   target_timestamp = int((frame_number * AV_TIME_BASE ) / video_stream.framerate)
     
   cap.seek(target_timestamp)

   for packet in cap.demux():

      for frame in packet.decode():
         return   int(frame.dts / offset_timestamp)
		 
   return -1
        
def get_frame_av( cap,frame_number,index_offset,keyframe_interval):


    #print('frame_number ' + str(frame_number) )     
    fps = cap.streams.video[0].average_rate
    frame_number *= fps 
    #print('fps  ' + str(fps))   
    video_stream = cap.streams.video[0]
    assert int(1/video_stream.time_base) % fps == 0
    #print('video_stream.time_base  ' + str(video_stream.time_base))    
    offset_timestamp = int(1 / video_stream.time_base / fps)
    #print('offset  ' + str(offset_timestamp))  
    #print('duration ' + str(cap.duration  /  AV_TIME_BASE  ))   
    video_stream = cap.streams.video[0]
    
    target_frame =  int(frame_number / keyframe_interval) * keyframe_interval
    target_timestamp = int(cap.duration * float(target_frame / int(cap.streams.video[0].frames))) 
    #print('target_timestamp ' + str(target_timestamp/  AV_TIME_BASE))       
    cap.seek(target_timestamp)
    framex_index	= -1
    for packet in cap.demux():
       #print(packet)  
       for frame in packet.decode():
          #print(frame)	
          if frame.dts:			
             framex_index = 		int(frame.dts/offset_timestamp) - index_offset	
          else:
              framex_index += 1         		 
          if(framex_index == frame_number):	
            #print('found frame ' + str(frame.pts / offset_timestamp) + ' ' + str(frame_number))		 
             return 
             #[True,cv2.cvtColor(frame.to_ndarray(), cv2.COLOR_YUV2BGR_I420)]	#np.asarray(frame.to_ndarray(format="bgr24"))	[True,cv2.cvtColor(frame.to_ndarray(), cv2.COLOR_YUV2BGR_I420)]		  
      	
       #if(packet.dts / offset_timestamp  - time_stamp_offset== frame_number):
       #	break
       	
	 
    #print('camera released' + str(camera))		
    return 
def detect_markers_and_update_bbox(chunk):
    #Detect Markers
    p0 = "target 1"
    px = "target 94"
    py = "target 42"
    pyb = "target 7"
    SCALE = 1000.0
	
    delta_y = SCALE * 0.005 # 0.07 # delta 2mm, to move the bounding box a bit up from the floor
    distancepx = SCALE * 0.9  #Keeping it simple with the size here
    distancepy = SCALE * 0.6

    # side targetsasdasd

    c1target = "target 29" 
    c2target = "target 30"
    c3target = "target 31"     
    c4target = "target 32"

    chunk.detectMarkers(Metashape.TargetType.CircularTarget12bit, 50, inverted=False, noparity=True)
	
    boxwidth = SCALE * 1.8
    boxheight = SCALE * 2.373
    boxdepth = SCALE * 0.9
    #Orient space
	
    mp0 = 0
    mpy = 0
    mpx = 0
    mpyb = 0
    fp0 = 0
    fpy = 0
    fpx = 0
	
    #setting for Y up, Z forward -> needed for mixamo/unity
	
    vector0 = Metashape.Vector((0,0,0))
    vectorY = Metashape.Vector((0,0,distancepy))   # Specify Y Distance
    vectorX = Metashape.Vector((distancepx,0,0))   # Specify X Distance
    c1 = 0
    c2 = 0
    c3 = 0
    c4 = 0
    c = 0
    for m in chunk.markers:
       print(m.label)
    
    return	
    for m in chunk.markers:
        if m.label == c1target:
            c1 = c
        if m.label == c2target:
            c2 = c
        if m.label == c3target:
            c3 = c
        if m.label == c4target:
            c4 = c
        if m.label == p0:
            mp0 = c
            fp0 = 1
            m.reference.location = vector0
            m.reference.enabled = 1
        if m.label == py:
            mpy = c
            fpy = 1
            m.reference.location = vectorY
            m.reference.enabled = 1
        if m.label == px:
            mpx = c
            fpx = 1
            m.reference.location = vectorX
            m.reference.enabled = 1
        if m.label == pyb:
            mpyb = c
        c = c + 1
	
    if fp0 and fpx and fpy:
        chunk.updateTransform()
    else:
        print("Error: not all markers found")
	
    newregion = chunk.region
	
    T = chunk.transform.matrix
    v_t = T * Metashape.Vector( [0,0,0,1] )
    m = Metashape.Matrix.Diag((1,1,1,1))
	
    m = m * T
    s = math.sqrt(m[0,0] ** 2 + m[0,1] ** 2 + m[0,2] ** 2) #scale factor
    R = Metashape.Matrix( [[m[0,0],m[0,1],m[0,2]], [m[1,0],m[1,1],m[1,2]], [m[2,0],m[2,1],m[2,2]]])
    R = R * (1. / s)
    newregion.rot = R.t()
	
    dist = chunk.markers[mp0].position - chunk.markers[mpy].position
    dist = dist.norm()
    ratio = dist / distancepy	

    z = Metashape.Vector.cross(Metashape.Vector(chunk.markers[mpx].position - chunk.markers[mp0].position), Metashape.Vector(chunk.markers[mpx].position - chunk.markers[mpy].position))
    mx = (chunk.markers[mp0].position + chunk.markers[mpy].position + chunk.markers[mpx].position + chunk.markers[mpyb].position) / 4	
    mx = Metashape.Vector([mx[0], mx[1], mx[2]]) + (boxheight / 2) * ratio * Metashape.Vector([z[0], z[1], z[2]]).normalized() 
    newregion.center = mx
	
    boxheight = boxheight-delta_y
	
    newregion.size = Metashape.Vector([boxwidth* ratio, boxheight* ratio, boxdepth * ratio])
    chunk.crs = Metashape.CoordinateSystem('LOCAL_CS["Local CS",LOCAL_DATUM["Local Datum",0],UNIT["millimetre",1]]')		
    chunk.region = newregion
    chunk.updateTransform()

def dump_masks(i,FRAME_DIR,iframe):
    global doc

    #doc = Metashape.app.document
    chunk = doc.chunks[-1]
    camera = chunk.cameras[i]
	

    #for camera in chunk.cameras:
    if camera in chunk.depth_maps.keys():
        depth = chunk.depth_maps[camera].image()
        depth.save(os.path.join(FRAME_DIR,'image_c_'+str(i)+'_f_'+str(iframe) + ".exr"))	
    	

def grab_image(path,current_camera,iframe,format_input=0,padding=padding_global):
    if(format_input==0):
       parse='%s/'+'%d'+'/%s%d%s%d%s'
       if(use_video):
         parse='%s%s%d%s%d%s'
         return  str(Path(parse%(path,'/image_c_',current_camera,'_f_',iframe,'.jpg')))   	   
       else:
           return  str(Path(parse%(path,current_camera,'image_c_',current_camera,'_f_',iframe,'.jpg')))   
    if(format_input==1):
       parse='%s/'+padding+'/%s%s'
       return  str(Path(parse%(path,iframe,camera_list[current_camera],'.jpg')))     

def reconstruct_frame(iframe,non_zero_index):
    global number_of_valid_cameras, doc
	
    # Create new project
    doc = Metashape.app.document
		   
    FRAME_DIR = os.path.join(OUTPUT_DIR,padding_global%non_zero_index)

    scan_path = SCAN_PATH
    format_image_input = FORMAT_IMAGE_INPUT
    padding_local = 	padding_global

    if(use_video == True):
       scan_path = os.path.join(FRAME_DIR, 'temp','rgb')
       format_image_input = 0
       padding_local = 	'%01d' 

    print('scan_path' + scan_path)	   
	
    doc.addChunk()
    chunk = doc.chunks[-1]

    if not os.path.exists(FRAME_DIR):
       os.mkdir(FRAME_DIR)
       print("Directory " , FRAME_DIR ,  " Created ")
    else:    
        print("Directory " , FRAME_DIR ,  " already exists")
        if not use_video:
          return	
		
    if not os.path.exists(os.path.join(FRAME_DIR,'temp')):
       os.mkdir(os.path.join(FRAME_DIR,'temp'))
       print("Directory " , os.path.join(FRAME_DIR,'temp') ,  " Created ")
    else:    
        print("Directory " , os.path.join(FRAME_DIR,'temp') ,  " already exists")		
	

    chunk.crs = Metashape.CoordinateSystem('LOCAL_CS["Local CS",LOCAL_DATUM["Local Datum",0],UNIT["millimetre",1]]')	

    if(len(glob.glob(scan_path + "/*.jpg"))	!= number_of_valid_cameras):
       print("some frames are missing! for" + scan_path)
       return
      
  
    for current_camera in range(0,len(camera_list)):
        camera = chunk.addCamera()
        #print(current_camera)
        #camera.label = str(current_camera+1)
        camera.label = camera_list[current_camera]
        print("camera label")
        print(camera.label)
        #camera.open(os.path.join('/CT/Human-Body-NeRF-2/static00/fore_statue/',str(current_camera+1)+'.png'))
        camera.open(grab_image(scan_path,current_camera,iframe,format_image_input,padding_local))
        # add the sensor to the camera
        sensor = chunk.addSensor() #creating camera calibration group for the loaded image
        sensor.label =   camera_list[current_camera]
        sensor.type = Metashape.Sensor.Type.Frame
        sensor.width = camera.photo.image().width
        sensor.height = camera.photo.image().height
        #sensor.user_calib 	=   Metashape.Calibration()
        if current_camera < 113:		   
           sensor.fixed_rotation = True
           sensor.fixed_location = True	
        sensor.fixed = True		   
        camera.sensor = sensor
    chunk.importCameras(CALIB_PATH+'/calib_metashape/event/cameras.xml')
    chunk.importCameras(CALIB_PATH+'/calib_metashape/sony/cameras.xml')	 
    chunk.importCameras(CALIB_PATH+'/cameras.xml')	
		
    ##doc.save(os.path.join(OUTPUT_DIR, project_name))    # checkpoint, save the project
    #print('Matching photos.........................')
    chunk.matchPhotos(
        #accuracy=ALIGNMENT_ACCURACY,
        #preselection=ALIGNMENT_PRESELECTION,
        downscale=0,
        #filter_mask=APPLY_MASK,
        #guided_matching=False,
        #filter_stationary_points=True,
		#generic_preselection=False,
        keypoint_limit=KEYPOINT_LIMIT,
        tiepoint_limit=TIEPOINT_LIMIT,
    )
    print('Align photos and Optimising Cameras ...')
    chunk.alignCameras()
    #chunk.triangulatePoints()
    #chunk.optimizeCameras(fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=False, fit_p1=True, fit_p2=True)

    #detect_markers_and_update_bbox(chunk)
	   
    #if SCALE_TO_MM:	   
    #   newregion = chunk.region
    #   newregion.size = Metashape.Vector([chunk.region.size[0]*1000.0, chunk.region.size[1]*1000.0, chunk.region.size[2]*1000.0])
    #   chunk.crs = Metashape.CoordinateSystem('LOCAL_CS["Local CS",LOCAL_DATUM["Local Datum",0],UNIT["millimetre",1]]')			   
    #   chunk.region = newregion
    #   chunk.updateTransform()
	#
    #   for i in range(0,len(chunk.cameras)):
	#   
    #      matrix_extr = chunk.cameras[i].transform 
	#      	   
    #      matrix_extr[0,3] *= 1000.0
    #      matrix_extr[1,3] *= 1000.0
    #      matrix_extr[2,3] *= 1000.0
	#             
    #      #print(matrix_extr[0,3])
    #      chunk.cameras[i].transform  = matrix_extr	   
      	
	
    chunk.exportCameras(path=os.path.join(FRAME_DIR, 'cameras.xml'))	
    doc.save(os.path.join(FRAME_DIR, 'project.psx'))  # checkpoint, save the project    
    sys.exit(0)     

 	

    #for current_camera in range(0,len(chunk.cameras)):
    #   if not chunk.cameras[current_camera].center == None:   
    #      cameras_pos.append(chunk.cameras[current_camera].center)
    #   else:
    #       cameras_pos.append(Metashape.Vector([0, 0, 0]))
	#	   
    #
	#	  
	#      
    #    
    #print(cameras_pos)   
    #kdtree=KDTree(cameras_pos)
    #
    #dist,points=kdtree.query(cameras_pos,len(chunk.cameras)-1)
    #
    #for current_camera in range(0,len(chunk.cameras)):
    #    a = chunk.cameras[current_camera]
    #    for point in range(1, len(points[current_camera])):
    #       b=chunk.cameras[points[current_camera][point]]
    #       PAIRS_CAMERAS.append((a,b))	
    #
    #print('Matching photos')
    #chunk.matchPhotos(
    #          downscale = ALIGNMENT_ACCURACY,
    #          keypoint_limit = KEYPOINT_LIMIT,
    #          #filter_mask  = APPLY_MASK and not USE_DENSE_CLOUD,
    #          mask_tiepoints = FILTER_TIE_POINTS,
    #          tiepoint_limit = TIEPOINT_LIMIT,
    #		  guided_matching = True,			  
    #          generic_preselection = False,
    #          reference_preselection = False,		  
    #		  pairs=PAIRS_CAMERAS,
	#		  #reset_matches = True
    #		  )		   
    #chunk.matchPhotos(
    #    #accuracy=ALIGNMENT_ACCURACY,
    #    #preselection=ALIGNMENT_PRESELECTION,
    #    downscale=1,
    #    filter_mask=False,
    #    guided_matching=False,
    #    filter_stationary_points=True,
	#	generic_preselection=False,
    #    keypoint_limit=KEYPOINT_LIMIT,
    #    tiepoint_limit=TIEPOINT_LIMIT,
    #)			  
	#
    #chunk.alignCameras()
    #chunk.optimizeCameras(fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=True, fit_p1=True, fit_p2=True)
	
    #chunk.triangulatePoints()
    #print(' saving project')	
  
    chunk.buildDepthMaps(downscale=CLOUD_QUALITY, filter_mode=FILTER_MODE,workitem_size_cameras = 20, max_neighbors=12)	
	
    #print('export depths')	
    #chunk.exportCameras(path=os.path.join(FRAME_DIR, 'cameras.xml'))	
    doc.save(os.path.join(FRAME_DIR, 'project.psx'))  # checkpoint, save the project    
    sys.exit(0) 
    chunk.buildModel(surface_type=SURFACE_QUALITY, source_data=Metashape.DataSource.DepthMapsData,interpolation=SURFACE_INTERPOLATION, face_count=FACE_COUNT,workitem_size_cameras = 50,trimming_radius = 0,volumetric_masks= APPLY_MASK)
	
    chunk.model.removeComponents(10000)
    
    chunk.model.closeHoles(100) 
    #print('Build Texture')
    chunk.buildUV()
    chunk.buildTexture( texture_size=TEXTURE_SIZE) 	
    ## Export model
    chunk.exportModel(path=os.path.join(FRAME_DIR, 'model.obj'), format=Metashape.ModelFormat.ModelFormatOBJ)	
		

    #doc.save(os.path.join(FRAME_DIR, 'project.psx'))  # checkpoint, save the project    	
 

    threads = []
    for video in range(0,len(scan_video_container)):
       if(camera_exist_list[video]):  	
         t = Thread(target=dump_masks, args=[video,FRAME_DIR,iframe])
         t.start()
         threads.append(t)
    for t in threads:
        t.join() 	
	
    	
    #sys.exit(0) 		

    #doc.clear()	
    #os.remove(os.path.join(FRAME_DIR, 'project.psx'))
    try:
        shutil.rmtree(os.path.join(FRAME_DIR, 'project.files'))
    except OSError as err:
        print("OS error: {0}".format(err))
    try:
        shutil.rmtree(os.path.join(FRAME_DIR,'temp'))
    except OSError as err:
        print("OS error: {0}".format(err))		
    
    #sys.exit(0) 
    print("Script finished")

def obj_exists(iframe):
    exists = False
    FRAME_DIR = os.path.join(OUTPUT_DIR,padding_global%iframe)
	
    if os.path.exists(FRAME_DIR):	   
       if os.path.exists(os.path.join(FRAME_DIR,'model.obj')):
          exists = True	
		  
    return exists

def dump_image(video,FRAME_DIR,iframe,dump_frames):
   global scan_video_container    
   global mask_video_container 	

  
   dump_frames_temp =dump_frames 
   iframe_temp = iframe   
   for frame in scan_video_container[video].decode(video=0):   
      if(dump_frames_temp):
        img = frame.to_image()
        #w = frame.width	
        #h = frame.height
        #if(w<IMAGE_W):
        #  print(int(IMAGE_W/w)) 		
        #img = img.resize(( int(IMAGE_W/w)*w, int(IMAGE_W/w)*h), Image.ANTIALIAS)	 	  
        img.save(FRAME_DIR + '/temp/rgb/' +'image_c_' + str(video) + '_f_' + str(iframe_temp) + '.jpg', quality=100, subsampling=0)	
      else:
          if(iframe_temp + 2 != frame_end):	  
             break
      if(iframe_temp + 2 == frame_end and not obj_exists(iframe + 1)):	# bug when last frame doesnt dumbs, but it dumbs with previous one	 
         iframe_temp+=1
         dump_frames_temp = True		
         FRAME_DIR = os.path.join(OUTPUT_DIR,padding_global%iframe_temp)
         if(len(glob.glob(FRAME_DIR + '/temp/rgb/' + "*.jpg")) == len(camera_list)): # if already were done then dont need to do it
            break			 
      else:
           break
			
   dump_frames_temp =  dump_frames		   
   iframe_temp = iframe
   FRAME_DIR = os.path.join(OUTPUT_DIR,padding_global%iframe)  
   if(APPLY_MASK == True and hasattr(mask_video_container[video], 'decode')):   
     for frame in mask_video_container[video].decode(video=0):   
        if(dump_frames_temp):
          img = frame.to_image()
          #w = frame.width	
          #h = frame.height		  
          #img = img.resize(( int(IMAGE_W/w)*w, int(IMAGE_H/w)*h), Image.ANTIALIAS)			
          img.save(FRAME_DIR + '/temp/' +'image_c_' + str(video) + '_f_' + str(iframe_temp) + '.jpg', quality=100, subsampling=0)
        else:
            if(iframe_temp + 2 != frame_end):	  
               break
        if(iframe_temp + 2 == frame_end and not obj_exists(iframe + 1)):	# bug when last frame doesnt dumbs, but it dumbs with previous one	  
           iframe_temp+=1
           dump_frames_temp = True		
           FRAME_DIR = os.path.join(OUTPUT_DIR,padding_global%iframe_temp)
           if(len(glob.glob(FRAME_DIR + '/temp/' + "*.jpg")) == len(camera_list)): # if already were done then dont need to do it
              break	  
        else:
             break    
def create_dir_for_temp_images(iframe):
    FRAME_DIR = os.path.join(OUTPUT_DIR,padding_global%iframe)
	
    if not os.path.exists(FRAME_DIR):
       os.mkdir(FRAME_DIR)
       print("Directory " , FRAME_DIR ,  " Created ")
    else:    
        print("Directory " , FRAME_DIR ,  " already exists")
    	
    if not os.path.exists(os.path.join(FRAME_DIR,'temp')):
       os.mkdir(os.path.join(FRAME_DIR,'temp'))
       print("Directory " , os.path.join(FRAME_DIR,'temp') ,  " Created ")
    else:    
        print("Directory " , os.path.join(FRAME_DIR,'temp') ,  " already exists")		
    
    if not os.path.exists(os.path.join(FRAME_DIR,'temp/rgb')):
       os.mkdir(os.path.join(FRAME_DIR,'temp/rgb'))
       print("Directory " , os.path.join(FRAME_DIR,'temp/rgb') ,  " Created ")
    else:    
        print("Directory " , os.path.join(FRAME_DIR,'temp/rgb') ,  " already exists")
				
def prepare_next_frames(iframe, dump_frames = True):
    global camera_exist_list
	
    FRAME_DIR = os.path.join(OUTPUT_DIR,padding_global%iframe)
	
    if(iframe + 1 == frame_end): #last frame is dumped with previous frame
       return
	   
    if(dump_frames):
      create_dir_for_temp_images(iframe)	
    if(iframe + 2 == frame_end and not obj_exists(iframe + 1)): #last frame is dumped with previous frame
      create_dir_for_temp_images(iframe + 1)       
	
    threads = []
    for video in range(0,len(scan_video_container)):
       if(camera_exist_list[video]):  	
         t = Thread(target=dump_image, args=[video,FRAME_DIR,iframe,dump_frames])
         t.start()
         threads.append(t)
    for t in threads:
        t.join()
		  
def skip_frames(iframe):
    global camera_exist_list,index_offset,keyframe_interval
	
    print('skipping till frame ' + str(iframe))
    print('index_offset ' + str(index_offset))
    print('keyframe_interval ' + str(keyframe_interval))	
	 
    threads = []
    for video in range(0,len(scan_video_container)):
       if(camera_exist_list[video]):  	
         t = Thread(target=get_frame_av, args=[scan_video_container[video],iframe,index_offset[0],keyframe_interval[0]])
         t.start()
         threads.append(t)
    for t in threads:
        t.join()
		
    threads = []		
    for video in range(0,len(mask_video_container)):
       if(camera_exist_list[video]):  	
         t = Thread(target=get_frame_av, args=[mask_video_container[video],iframe,index_offset[1],keyframe_interval[1]])
         t.start()
         threads.append(t)
    for t in threads:
        t.join()		  
    print('finished skipping till frame ' + str(iframe))						
				
def prepare_video_container():
    global number_of_valid_cameras,frame_start,video_pattern, scan_video_container,mask_video_container, IMAGE_W,IMAGE_H
    number_of_valid_cameras = 0
	
    num_of_tries = 10	

    if(os.path.isfile(SCAN_PATH + "/missingCameras.txt")):
     try:
       f = open(SCAN_PATH + "/missingCameras.txt", 'rb')
     except OSError:
         print("File %s not found.  Run first convert_calib_to_other_seq.py script!" % SCAN_PATH + "/missingCameras.txt")
         sys.exit(1)
         
     
     with open(SCAN_PATH + "/missingCameras.txt") as f:
          lines = f.readlines()
		   
     for line in lines: 
        camera_exist_list.append(int(line))	 
    else:
        file_list_len = len(glob.glob(SCAN_PATH + "/*.avi") + glob.glob(SCAN_PATH + "/*.mp4"))		
        for video in range(0,file_list_len):
            camera_exist_list.append(1)	

    frame_end = -1
		
    file_list = glob.glob(SCAN_PATH + "/*.avi")	+ glob.glob(SCAN_PATH + "/*.mp4") 
    file_list_extra = glob.glob(SCAN_PATH_EXTRA + "/*.avi")	+ glob.glob(SCAN_PATH_EXTRA + "/*.mp4")


    file_list += file_list_extra
	
    for video in range(0,len(file_list_extra)):
        camera_exist_list.append(1)	
	
    _ , file_ext = 	os.path.splitext(file_list[-1])

    frame_ends = []	
    for video in range(0,len(file_list)):	
       cap = av.container
       
       if(camera_exist_list[video]):
         number_of_valid_cameras += 1	
         if video < 113:		 
           cap = av.open(SCAN_PATH + "/" + (video_pattern+file_ext)%(video))
         else:
             cap = av.open(SCAN_PATH_EXTRA + "/" + (video_pattern+file_ext)%(video))		 
         scan_video_container.append(cap)
         frame_ends.append(scan_video_container[-1].streams.video[0].frames)    
       else:
           scan_video_container.append(cap)
           if(APPLY_MASK == True):		   
              mask_video_container.append(cap)
              frame_ends.append(min(frame_ends))  	
           continue
	  
       #if(cap.isOpened() == False):
       #   for num_try in range(0,num_of_tries):
       #      cap.open(SCAN_PATH + "/" + video_pattern%(video))		    
       #      if(cap.isOpened() == True):
       #        break
       #   if(cap.isOpened() == False):				   
       #     print("couldnt open the video " + SCAN_PATH + "/" + video_pattern%(video))
       #     sys.exit(0) 		  


       #cap.set(cv.CAP_PROP_BUFFERSIZE, 1)          	
       #frame_end = int(cap.get(cv.CAP_PROP_FRAME_COUNT))   
       #frame_end = scan_video_container[-1].streams.video[0].frames 
       frame_end  = min(frame_ends)

       if(APPLY_MASK == True):
         try:
            cap = av.open(MASK_PATH + "/" + (video_pattern+file_ext)%(video))
         except OSError:
               mask_video_container.append(av.container)
               continue			   
         #cap = cv.VideoCapture(MASK_PATH + "/" + str(video) + "/" + video_pattern%(video))

         #print(MASK_PATH + "/" + video_pattern%(video))		 
         mask_video_container.append(cap)
	     
         #if(cap.isOpened() == False):
         #   for num_try in range(0,num_of_tries):
         #      cap.open(MASK_PATH + "/"  + str(video) + "/" + video_pattern%(video))		    
         #      if(cap.isOpened() == True):
         #        break
         #   if(cap.isOpened() == False):				   
         #     print("couldnt open the video " + MASK_PATH + "/"  + str(video) + "/" + video_pattern%(video))
         #     sys.exit(0)
         #cap.set(cv.CAP_PROP_BUFFERSIZE, 1)  			
	

   #IMAGE_W = scan_video_container[-1].streams.video[0].width
   #IMAGE_H = scan_video_container[-1].streams.video[0].height
	

    
    return frame_end 
	

     
              				
	
def recon( start_total ):
    global frame_start,frame_end,camera_list,ir_list,camera_exist_list,scan_video_container,mask_video_container,number_of_valid_cameras,keyframe_interval,index_offset
	
    camera_list.clear()
    ir_list.clear()
    camera_exist_list.clear()
    scan_video_container.clear()    
    mask_video_container.clear()
	
    Metashape.app.cpu_enable = True    
    Metashape.app.gpu_mask = 1

    with open(CAMSORT_PATH + '/camSorting.txt') as f:
         lines = f.readlines()

    for line in lines: 
       camera_list.append(line.strip().split()[1])
      

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR,exist_ok=True)
        print("Directory " , OUTPUT_DIR ,  " Created ")
    else:    
        print("Directory " , OUTPUT_DIR ,  " already exists")	
    if not os.path.exists('.cache'):
        os.mkdir('.cache')
        print("Directory " , '.cache' ,  " Created ")
    else:    
        print("Directory " , '.cache' ,  " already exists")	
	
    if(use_onlyIR):     
      for camera in camera_list:
         if camera[0:2] == 'BF':
            ir_list.append(camera)


    if(use_video):
       frame_end = prepare_video_container()
       keyframe_interval[0] = get_keyframe_interval(scan_video_container[0])
       index_offset[0] = get_timestamp_offset(scan_video_container[0])	
       if APPLY_MASK:	   
         keyframe_interval[1] = get_keyframe_interval(mask_video_container[0])
         index_offset[1] = get_timestamp_offset(mask_video_container[0])	   
       all_done = True	   
       for iframe in range(frame_start,frame_end):
          FRAME_DIR = os.path.join(OUTPUT_DIR,"%06d"%iframe)
          if os.path.exists(FRAME_DIR):	   
             if not os.path.exists(os.path.join(FRAME_DIR, 'model.obj')):
                all_done = False			 
                break
          else:
               all_done = False			 
               break
			   
       if(all_done):
         print("all done, so not running")
         return	 
	

    camera_list.append('event')	
    camera_list.append('sony')	
    print("scan_video_container size " + str(len(scan_video_container))) 
    print("mask_video_container size " + str(len(mask_video_container)))  
	
    print("camera_exist_list size " + str(len(camera_exist_list)))
    print("camera_list size " + str(len(camera_list)))
    print("frame_end size " + str(frame_end)) 	
	
		
  
	
    step = 1	  
    non_zero_index=0	
    #number_of_valid_cameras	= 116
    #frame_end =1
    iframe	= frame_start
    while iframe < frame_end:   
       start_local = time.time()
     	  
       while(iframe>non_zero_index):
            skip_frames(iframe-1)
            non_zero_index = iframe			
            #prepare_next_frames(non_zero_index,False)	
            #non_zero_index+=1
		 
       lock_file = '.cache/metashape_%d_%d.lock'%(seq_id,iframe)
       with FileLock(lock_file) as lock:
           if lock.has_lock:
              if(use_video == True):
                 if obj_exists(non_zero_index):			  
                    while( obj_exists(non_zero_index) and iframe<frame_end):
                         non_zero_index += step
                         iframe += step	
                    						 
                    if(iframe>=frame_end):
                       break
                    					   
                    skip_frames(non_zero_index-1)  
                    continue 					
                 prepare_next_frames(non_zero_index)
              print('iframe ' + str(iframe))				 
              reconstruct_frame(iframe,non_zero_index)
           else:
               if(use_video == True):		   
                  prepare_next_frames(non_zero_index,False)		  
               			 
       end_local = time.time()
       print("Frame number %04d was running: %d min"%(iframe,(end_local - start_local) / 60))
       if((end_local - start_total) / 60 >= RUNNING_TIME):
          break

       iframe +=step		  
       non_zero_index+=step
	   
if __name__ == '__main__':

  
  start_total = time.time()	
  #for seq in range(0, len(SEQUENCES)):
  seq_id = 0
  
  SCAN_PATH = SEQUENCES[0]
  OUTPUT_DIR = OUTPUTDIRS[0]
  CALIB_PATH = SCAN_PATH
  CAMSORT_PATH = SCAN_PATH #path camSorting.txt
  
    
  SCAN_PATH_EXTRA = SEQUENCES[1]

  
  MASK_PATH = SCAN_PATH + '/foregroundSegmentation'	  
  recon(start_total)
  end_total = time.time()
   
 #print("Total running time: %d"%((end_total - start_total) / 60))
 #if((end_total - start_total) / 60 >= RUNNING_TIME):
 #   break	 	  

