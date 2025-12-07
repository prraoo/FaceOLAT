"""
source ../setup_env
metashape scan_reconstruction.py
"""
import os, sys
os.environ["AGISOFT_FLS"] = 'lm-agisoft-fls.mpi-klsb.mpg.de:5842'
import math
import Metashape
import time
import glob
import numpy as np
import cv2
import xml.etree.ElementTree as ET
from threading import Thread
RUNNING_TIME = 23 * 60 #run 23 hours

from utils.convert_metashape_calib import convert_metashape_calib
from utils import convert_xml
from utils.util_metashape import calc_reprojection

str2bool = lambda v: v.lower() in ("yes", "true", "t", "1")
### CHANGE THESE ONLY ###############################################################################

#USAGE: python get_calibration_light_stage.py $SCAN_PATH $TAKE $FRAME $IMPORT_CAMERAS $CAMERAS_DIR $OUTPUT_DIR $COMPUTE_AVG
#
# Parameters:
#   SCAN_PATH      - Path to AVIF images
#   TAKE           - Take/scan name (e.g., ID20001, ID30050, ID40100)
#   FRAME          - Frame number to use
#   IMPORT_CAMERAS - Import camera calibration (True/False)
#   CAMERAS_DIR    - Path to cameras directory (contains subject-specific XML files)
#   OUTPUT_DIR     - Output directory for reconstruction
#   COMPUTE_AVG    - Compute average of multiple frames (True/False)

SCAN_PATH = sys.argv[1]
TAKE = sys.argv[2]
FRAME = int(sys.argv[3])
IMPORT_CAMERAS = str2bool(sys.argv[4])
CAMERAS_DIR = sys.argv[5]
OUTPUT_DIR = sys.argv[6]
COMPUTE_AVERAGE = str2bool(sys.argv[7])

# Extract subject number from TAKE (e.g., ID20001 -> 001, ID30050 -> 050)
# The format is IDXXYYYY where XX is the view and YYYY is the subject number
import re
match = re.search(r'ID\d{2}(\d+)', TAKE)
if match:
    subject_num = match.group(1).zfill(3)  # Pad to 3 digits (e.g., 1 -> 001, 50 -> 050)
    CAMERAS_PATH = os.path.join(CAMERAS_DIR, f"{subject_num}.xml")
    print(f"Using camera calibration: {CAMERAS_PATH} for subject {subject_num}")
else:
    print(f"Warning: Could not extract subject number from TAKE: {TAKE}")
    CAMERAS_PATH = CAMERAS_DIR

AVERAGE_NUM = 15
TAKE_2 = None

SCALE = 1.0 # 1000.0 is mm, 1 is in meters
HIGHEST_QUALITY = True # Highest quality best for rigging character, for other cases not needed, as it takes 25 min.

#set to INTR to None, if you dont want to provide your intrinsics
INTR = None#'1289.89761216 0.0 945.28262184 0.0 1289.89761216 519.70330912 0.0 0.0 1.0' 


#####################################################################################################


### PARAMETERS ##########################################################################################################

BOUNDING_BOX_SCALE = 2.0
CLOSE_HOLES = True
FILTER_MESH = True
# photos alignment
ALIGNMENT_ACCURACY = 1  # HighestAccuracy, HighAccuracy, MediumAccuracy, LowAccuracy, LowestAccuracy
ALIGNMENT_PRESELECTION = True # NoPreselection, GenericPreselection, for the image alignment
KEYPOINT_LIMIT = 100000 # Toggle for HQ
TIEPOINT_LIMIT = 10000  # Toggle for HQ
# KEYPOINT_LIMIT = 80000
# TIEPOINT_LIMIT = 7000
MASK_TOLERANCE = 10
FILTER_MASK = False
FILTER_TIE_POINTS = True


# building dense cloud
CLOUD_QUALITY = 2#1 if HIGHEST_QUALITY else 2# # UltraQuality, HighQuality, MediumQuality, LowQuality, LowestQuality
FILTER_MODE =  Metashape.ModerateFiltering # NoFiltering, MildFiltering, ModerateFiltering, AggressiveFiltering

#Build Model
SURFACE_QUALITY = Metashape.Arbitrary
#SURFACE_INTERPOLATION = Metashape.DisabledInterpolation#Metashape.EnabledInterpolation DisabledInterpolation
SURFACE_INTERPOLATION = Metashape.EnabledInterpolation
FACE_COUNT = Metashape.HighFaceCount if HIGHEST_QUALITY else Metashape.MediumFaceCount # Metashape.FaceCount.LowFaceCount, Metashape.FaceCount.MediumFaceCount, Metashape.FaceCount.HighFaceCount
# mapping texture
TEXTURE_SIZE=4096
#########################################################################################################################
#obj export
MODEL_FORMAT = Metashape.ModelFormat.ModelFormatOBJ

camera_list = []
camera_reference_origin = []

camera_folders = []

def save_opencv_calib(pathFile,intr,IMAGE_W,IMAGE_H,distor='0 0 0 0 0'):

   opencv_storage =  ET.Element("opencv_storage")
   ET.SubElement(opencv_storage, 'image_Width').text = str(IMAGE_W)
   ET.SubElement(opencv_storage, 'image_Height').text = str(IMAGE_H)
   Camera_Matrix = ET.SubElement(opencv_storage, 'Camera_Matrix',{'type_id':'opencv-matrix'})
   ET.SubElement(Camera_Matrix,'rows').text = '3'
   ET.SubElement(Camera_Matrix,'cols').text = '3'
   ET.SubElement(Camera_Matrix,'dt').text = 'd'
   ET.SubElement(Camera_Matrix,	'data').text = str(intr)

   Distortion_Coefficients = ET.SubElement(opencv_storage, 'Distortion_Coefficients',{'type_id':'opencv-matrix'})
   ET.SubElement(Distortion_Coefficients,'rows').text = '5'
   ET.SubElement(Distortion_Coefficients,'cols').text = '1'
   ET.SubElement(Distortion_Coefficients,'dt').text = 'd'

   distortion = np.fromstring(distor, dtype=float, sep=' ')
   distortion[2], distortion[3] = distortion[3], distortion[2]
   d = ' '.join(str(e) for e in distortion)
   ET.SubElement(Distortion_Coefficients,	'data').text = str(d)
   tree = ET.ElementTree(opencv_storage)

   with open(pathFile, "wb") as f:
       tree.write(f,xml_declaration=True)

def add_cameras(chunk,camera_list,img_path):
   global INTR, TAKE

   calibration = Metashape.Calibration()

   for i, current_camera in enumerate(camera_list):
        camera = chunk.addCamera()
        camera.label = 'Cam%02d'%(i+1)
        camera.open(current_camera)
        # add the sensor to the camera
        sensor = chunk.addSensor() #creating camera calibration group for the loaded image
        sensor.label =  'Cam%02d'%(i+1)
        sensor.type = Metashape.Sensor.Type.Frame
        sensor.width = camera.photo.image().width
        sensor.height = camera.photo.image().height

        camera.sensor = sensor
        if INTR != None:
           if not os.path.isfile('intr.xml'):
              save_opencv_calib('intr.xml',INTR,sensor.width,sensor.height)

           calibration.load(path='intr.xml',format=Metashape.CalibrationFormat.CalibrationFormatOpenCV)
           sensor.user_calib 	= calibration
           sensor.fixed = True
           camera.sensor = sensor
   if INTR != None:
     os.remove('intr.xml')

def umeyama(P, Q):
    assert P.shape == Q.shape
    n, dim = P.shape

    centeredP = P - P.mean(axis=0)
    centeredQ = Q - Q.mean(axis=0)

    C = np.dot(np.transpose(centeredP), centeredQ) / n

    V, S, W = np.linalg.svd(C)
    d = (np.linalg.det(V) * np.linalg.det(W)) < 0.0

    if d:
        S[-1] = -S[-1]
        V[:, -1] = -V[:, -1]

    R = np.dot(V, W)

    varP = np.var(P, axis=0).sum()
    c = 1/varP * np.sum(S) # scale factor

    t = Q.mean(axis=0) - P.mean(axis=0).dot(c*R)

    return c, R, t

def align_cameras_to_reference(chunk):
   global camera_reference_origin, SCALE

   delta_y = SCALE *  0.025 # 0.07 # delta 2mm, to move the bounding box a bit up from the floor
   distancepx = SCALE * 1.22  #Keeping it simple with the size here
   distancepy = SCALE * 1.13


   boxwidth = SCALE * 2.0
   boxheight = SCALE * 2.373
   boxdepth = SCALE * 1.1


   #for camera in chunk.cameras:
   #   #print(camera.label)
   #   print(camera.center)
   np.set_printoptions(precision=3)

   metashape_pos = None
   camera_reference_origin_np = None

   for camera in range(0,len(chunk.cameras)):
       scale_conver = 1000.0 / SCALE
       if metashape_pos is not None:
         metashape_pos=np.append(metashape_pos,[[float(chunk.cameras[camera].center[0]),float(chunk.cameras[camera].center[1]),float(chunk.cameras[camera].center[2])]],axis=0)
         camera_reference_origin_np = np.append(camera_reference_origin_np,[camera_reference_origin[camera]/scale_conver],axis=0)
       else:
           camera_reference_origin_np = np.array([camera_reference_origin[camera]/scale_conver])
           metashape_pos=np.array([[float(chunk.cameras[camera].center[0]),float(chunk.cameras[camera].center[1]),float(chunk.cameras[camera].center[2])]])

   c, R, t = umeyama(metashape_pos,camera_reference_origin_np)
   print ("R =")
   print( R )
   print ("c = %f"%c)
   print ("t = ")
   print(t)

   print ("Check:  metashape_pos*cR + t = camera_reference_origin  is")
   print(np.allclose(metashape_pos.dot(c*R) + t, camera_reference_origin_np))
   err = np.linalg.norm(metashape_pos.dot(c * R) + t - camera_reference_origin_np)
   print ("Residual error %f"%err)

   res_error = metashape_pos.dot(c * R) + t #- camera_reference_origin_np
   print(chunk.transform.matrix.mulp(chunk.cameras[0].center))
   print(res_error[0])



   #s = c 		#scaling # T.scale()
   S = Metashape.Matrix().Diag([c, c, c, 1]) #scale matrix

   T = Metashape.Matrix( [[R[0,0], R[0,1], R[0,2], 0], [R[1,0], R[1,1], R[1,2], 0], [R[2,0], R[2,1], R[2,2], 0], [0, 0, 0, 1]])

   chunk.transform.matrix = Metashape.Matrix().Translation(Metashape.Vector([t[0], t[1], t[2]]))* S * T.inv()#translation scale and inv tr

   chunk.updateTransform()
   print(chunk.transform.matrix.mulp(chunk.cameras[0].center))

   newregion = chunk.region

   T = chunk.transform.matrix
   v_t = T * Metashape.Vector( [0,0,0,1] )
   m = Metashape.Matrix.Diag((1,1,1,1))

   m = m * T
   s = math.sqrt(m[0,0] ** 2 + m[0,1] ** 2 + m[0,2] ** 2) #scale factor
   R = Metashape.Matrix( [[m[0,0],m[0,1],m[0,2]], [m[1,0],m[1,1],m[1,2]], [m[2,0],m[2,1],m[2,2]]])
   R = R * (1. / s)
   newregion.rot = R.t()
   print(newregion.rot)

   p0 =  chunk.transform.matrix.inv().mulp( Metashape.Vector( [0,0,0] )) #"target 1"
   px =  chunk.transform.matrix.inv().mulp( Metashape.Vector( [distancepx,0,0] ))#"target 94"
   py =  chunk.transform.matrix.inv().mulp( Metashape.Vector( [0,0,distancepy] ))  # "target 42"
   pyb = chunk.transform.matrix.inv().mulp( Metashape.Vector( [distancepx,0,distancepy] ))  #"target 7"

   #print(chunk.transform.matrix.inv().mulp( Metashape.Vector( [0,0,0] )))


   dist = p0 - py
   dist = dist.norm()
   ratio = dist / distancepy

   z = Metashape.Vector.cross(Metashape.Vector(px - p0), Metashape.Vector(px - py))
   mx = (p0 + py + px + pyb) / 4
   mx = Metashape.Vector([mx[0], mx[1], mx[2]]) + (boxheight / 2) * ratio * Metashape.Vector([z[0], z[1], z[2]]).normalized()
   newregion.center = mx
   print(mx)


   boxheight = boxheight-delta_y

   newregion.size = Metashape.Vector([boxwidth* ratio, boxheight* ratio, boxdepth * ratio])
   if SCALE > 1.0:
      chunk.crs = Metashape.CoordinateSystem('LOCAL_CS["Local CS",LOCAL_DATUM["Local Datum",0],UNIT["millimetre",1]]')
   else:
      chunk.crs = Metashape.CoordinateSystem('LOCAL_CS["Local CS",LOCAL_DATUM["Local Datum",0],UNIT["meters",1]]')
   chunk.region = newregion
   chunk.updateTransform()

   return chunk

def detect_markers_and_update_bbox(chunk):
    global SCALE
    #Detect Markers
    p0 =  "target 1"
    px =  "target 94"
    py =  "target 42"
    pyb = "target 7"


    delta_y = SCALE *  0.025 # 0.07 # delta 2mm, to move the bounding box a bit up from the floor
    distancepx = SCALE * 1.22  #Keeping it simple with the size here
    distancepy = SCALE * 1.13


    # side targetsasdasd


    chunk.detectMarkers(Metashape.TargetType.CircularTarget12bit, 30)


    boxwidth = SCALE * 2.0
    boxheight = SCALE * 2.373
    boxdepth = SCALE * 1.1


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

    c = 0
    new_origin = Metashape.Vector((0,0,0))
    for m in chunk.markers:
        if m.label == p0:
            new_origin=	m.position
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

    if fp0 and fpx and fpy and \
	 chunk.markers[mpx].position is not None and \
	 chunk.markers[mp0].position is not None and \
	 chunk.markers[mpy].position is not None:
        # TODO: Does this have any effect?
        # import pdb; pdb.set_trace()
        # align_cameras_to_reference(chunk)
        chunk.updateTransform()
    else:
        print("Error: not all markers found, no scalining then!")
        print("falling back to base calibration")
        return	align_cameras_to_reference(chunk)

    newregion = chunk.region

    T = chunk.transform.matrix
    v_t = T * Metashape.Vector( [0,0,0,1] )
    m = Metashape.Matrix.Diag((1,1,1,1))

    m = m * T
    s = math.sqrt(m[0,0] ** 2 + m[0,1] ** 2 + m[0,2] ** 2) #scale factor
    R = Metashape.Matrix( [[m[0,0],m[0,1],m[0,2]], [m[1,0],m[1,1],m[1,2]], [m[2,0],m[2,1],m[2,2]]])
    R = R * (1. / s)
    newregion.rot = R.t()
    print(newregion.rot)


    dist = chunk.markers[mp0].position - chunk.markers[mpy].position
    dist = dist.norm()
    ratio = dist / distancepy

    z = Metashape.Vector.cross(Metashape.Vector(chunk.markers[mpx].position - chunk.markers[mp0].position), Metashape.Vector(chunk.markers[mpx].position - chunk.markers[mpy].position))
    mx = (chunk.markers[mp0].position + chunk.markers[mpy].position + chunk.markers[mpx].position + chunk.markers[mpyb].position) / 4
    mx = Metashape.Vector([mx[0], mx[1], mx[2]]) + (boxheight / 2) * ratio * Metashape.Vector([z[0], z[1], z[2]]).normalized()
    newregion.center = mx
    print(mx)


    boxheight = boxheight-delta_y

    newregion.size = Metashape.Vector([boxwidth* ratio, boxheight* ratio, boxdepth * ratio])
    if SCALE > 1.0:
       chunk.crs = Metashape.CoordinateSystem('LOCAL_CS["Local CS",LOCAL_DATUM["Local Datum",0],UNIT["millimetre",1]]')
    else:
       chunk.crs = Metashape.CoordinateSystem('LOCAL_CS["Local CS",LOCAL_DATUM["Local Datum",0],UNIT["meters",1]]')
    chunk.region = newregion
    chunk.updateTransform()
    return chunk

def init ( doc,cam_path = CAMERAS_PATH, frame_dir = OUTPUT_DIR,import_cameras = IMPORT_CAMERAS ):
    global SCAN_PATH
   # Check for Metashape version comaptibility

    #doc = Metashape.Document()
    #doc.open(os.path.join(OUTPUT_DIR, 'project.psx'))
    ##doc.clear()
    doc.addChunk()
    chunk = doc.chunks[-1]
    #doc.addChunk()



    add_cameras(chunk,camera_list,SCAN_PATH)
    #chunk.importCameras(cam_path)
    #chunk.exportCameras(os.path.join(frame_dir,'cameras.xml'))
    #sys.exit(0)
    #print('Matching photos')
    #chunk.matchPhotos(
    #          downscale = ALIGNMENT_ACCURACY,
    #          keypoint_limit = KEYPOINT_LIMIT,
    #          filter_mask  = FILTER_MASK,
    #          mask_tiepoints = FILTER_TIE_POINTS,
    #          tiepoint_limit = TIEPOINT_LIMIT,
    #          generic_preselection = ALIGNMENT_PRESELECTION,
    #          reference_preselection = True)
	#
	#
    #if(import_cameras == True):
    #   #R0 = chunk.region.rot
    #   #C0 = chunk.region.center
    #   #s0 = chunk.region.size
    #   ##chunk.alignCameras()
    #   #newregion = chunk.region
    #   #newregion.rot = R0
    #   #newregion.center = C0
    #   #newregion.size 	=  s0 * BOUNDING_BOX_SCALE
    #   #chunk.region = newregion
    #   #chunk.updateTransform()
    #   chunk.triangulatePoints()
    #else:
    #    chunk.alignCameras()


def remove_invalid_cameras_and_images(chunk):
    # Create a list to store cameras that will be removed
    cameras_to_remove = []

    # Iterate over all cameras in the chunk
    for camera in chunk.cameras:
        # Check if the camera's transform is None (not calibrated)
        if camera.transform is None:
            # Add camera to the list for removal
            cameras_to_remove.append(camera)

            # Print camera name (optional)
            print(f"Camera {camera.label} has invalid transform {camera.transform} and will be removed.")

            # Remove corresponding image file if you want to delete the actual file from the disk
            image_path = camera.photo.path
            if os.path.exists(image_path):
                os.remove(image_path)  # Remove the image from the disk
                print(f"Image file {image_path} has been deleted from disk.")
            else:
                print(f"Image file {image_path} not found.")

    # Now remove all invalid cameras from the chunk
    for camera in cameras_to_remove:
        # WARNING: uncomment to remove non calibrated views
        chunk.remove(camera)
        print(f"Camera {camera.label} removed from the chunk.")

    return chunk


def write_error_report(path_filename,chunk):

    error_pix_threshold = 2.9
    proj_num_threshold = 50
    succ = True
    file = open(path_filename, "w")
    total_error, ind_error = calc_reprojection(chunk)
    if total_error == None or ind_error == None:
       #return False
       print('error no alignment happened')
       #chunk.exportCameras('./debug_cameras.xml')
       #sys.exit(0)
       file.close()
       return False
    file.write("\t".join(["#label","error_pix","proj_num\n"]))
    num_of_cameras = 0
    average_error = 0

    camera_list_to_delete = list()
    sensor_list_to_delete = list()
    for camera in ind_error.keys():
       num_of_cameras+=1
       file.write("\t".join([chunk.cameras[camera].label, str(ind_error[camera][0]), str(ind_error[camera][1])])+"\n")
       average_error +=	ind_error[camera][0]
       if(ind_error[camera][0]>error_pix_threshold or ind_error[camera][1]<proj_num_threshold):
          succ = False
	
    file.write("\t".join(["#average error ",str(average_error/num_of_cameras)]))	   
        	
    file.close() 
    if(num_of_cameras!=len(chunk.cameras)):
       print('Not all cameras got calibrated!')
       return False	

    return succ


def calibrate(chunk,FRAME_DIR):
    global FILTER_TIE_POINTS, CAM_DROP_ALLOWED_MAX, camera_list
	
    error_pix_threshold = 2.5
    proj_num_threshold = 50
   
	
    #chunk.tiepoint_accuracy = 2	
    ##for frame in range(0,len(chunk.frames)):
    #if chunk.tie_points:
    #   threshold = 3.5
    #   f = Metashape.TiePoints.Filter()
    #   f.init(chunk, criterion = Metashape.TiePoints.Filter.ReprojectionError)
    #   f.removePoints(threshold) 	
    print('Matching photos')
    chunk.matchPhotos(
              downscale = ALIGNMENT_ACCURACY,
              keypoint_limit = KEYPOINT_LIMIT,
              #filter_mask  = USE_MARKERS,
			 # filter_mask = False,
              mask_tiepoints = FILTER_TIE_POINTS,
              tiepoint_limit = TIEPOINT_LIMIT,
              guided_matching=False,
              # filter_stationary_points=True, # Toggle for HQ
              # generic_preselection = False,  # Toggle for HQ
              filter_stationary_points=False,
              generic_preselection = True,
			  reset_matches = True
    )
    #chunk.triangulatePoints()
    chunk.alignCameras()

    #chunk.triangulatePoints()
    chunk.optimizeCameras(fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=False, fit_p1=True, fit_p2=True, \
                          fit_f=True, fit_cx=True, fit_cy=True, fit_b1=True )

    return write_error_report(FRAME_DIR+'/error.txt',chunk)
 	   

def read_calib(calib_path ='cameras.calib'):
   global camera_reference_origin

   camera_reference_origin.clear()

   with open(calib_path, 'r') as fp:
        while True:
            text = fp.readline()
            if not text:
               break

            if ('origin' in text):
                origin = np.fromstring(text.replace('origin',''), dtype=float, sep=' ')
                camera_reference_origin.append(origin)


def reconstruct_frame():
    global FILTER_MESH, camera_reference_origin,CAMERAS_PATH
    doc = Metashape.Document()

    #doc.open(os.path.join(OUTPUT_DIR, 'project.psx'))
    ##doc.clear()



    ##doc.clear()

    FRAME_DIR = os.path.join(OUTPUT_DIR)
    #doc.open(os.path.join(FRAME_DIR, 'project.psx'))

    init(doc)
    chunk = doc.chunks[-1]


    if(IMPORT_CAMERAS == False):
       read_calib()
       #for origin in camera_reference_origin:
       #   print(origin)
       num_of_tries = 5

       calib_done = False
       for iter in range(0,num_of_tries):
          calib_done = calibrate(chunk,FRAME_DIR)
          if calib_done:
             print('Calibration is good! with number of tries:' + str(iter+1))
             break

       if not calib_done:
          print('failed to compute calib')
          remove_invalid_cameras_and_images(chunk)
          # sys.exit(0)



       #doc.save(os.path.join(FRAME_DIR, 'project.psx'))  # checkpoint, save the project

       #chunk.detectMarkers(Metashape.TargetType.CircularTarget12bit, 30)
       detect_markers_and_update_bbox(chunk)
       #align_cameras_to_reference(chunk)
       #doc.save(os.path.join(FRAME_DIR, 'project.psx'))

       outputPath =os.path.join(FRAME_DIR,'camSorting.txt')
       if(not os.path.isfile(outputPath)):
           outputFile = open(outputPath, 'w')
           for c in range(len(camera_list)):
              outputFile.write(str(c) + ' ' + 'Cam%02d'%(c+1)  + '\n')
           outputFile.close()


       chunk.exportCameras(os.path.join(FRAME_DIR,'cameras.xml'))

       convert_metashape_calib.convert_metashape_calib(int(chunk.cameras[-1].sensor.width),int(chunk.cameras[-1].sensor.height),FRAME_DIR,FRAME_DIR,'cameras.calib',chunk)
    else:
         print('Matching photos')
         chunk.matchPhotos(
                   downscale = ALIGNMENT_ACCURACY,
                   keypoint_limit = KEYPOINT_LIMIT,
                   #filter_mask  = USE_MARKERS,
         		 # filter_mask = False,
                   mask_tiepoints = FILTER_TIE_POINTS,
                   tiepoint_limit = TIEPOINT_LIMIT,
                  guided_matching=False,
                  filter_stationary_points=True,
                  generic_preselection = False,
        		  reset_matches = True)

         # Import cameras from subject-specific XML file
         # CAMERAS_PATH now points directly to the XML file (e.g., cameras/001.xml)
         if os.path.isfile(CAMERAS_PATH):
             # CAMERAS_PATH is the direct path to the XML file
             chunk.importCameras(CAMERAS_PATH)
             print(f"Imported cameras from: {CAMERAS_PATH}")
         else:
             # Fallback: try old format (directory with cameras.xml)
             cameras_xml = os.path.join(CAMERAS_PATH, 'cameras.xml')
             if os.path.exists(cameras_xml):
                 chunk.importCameras(cameras_xml)
                 print(f"Imported cameras from: {cameras_xml}")
             else:
                 print(f"ERROR: Camera calibration file not found: {CAMERAS_PATH}")
                 raise FileNotFoundError(f"Camera calibration not found: {CAMERAS_PATH}")
         
         chunk.triangulateTiePoints()
         # chunk = detect_markers_and_update_bbox(chunk)

    #doc.save(os.path.join(FRAME_DIR, 'project.psx'))  # checkpoint, save the project
    #if(IMPORT_CAMERAS == False):
    #  doc.clear()
    #  init(doc,cam_path = FRAME_DIR,import_cameras = True)
	#  
    #chunk = doc.chunks[-1]


    #print('Build Depth Maps')
    chunk.buildDepthMaps(downscale=CLOUD_QUALITY, filter_mode=FILTER_MODE)
    # Build Dense Cloud
    #chunk.buildDenseCloud(point_colors=True,point_confidence=True)
    #if(IMPORT_CAMERAS == True):
    #   R0 = chunk.region.rot
    #   C0 = chunk.region.center
    #   s0 = chunk.region.size
    #   newregion = chunk.region
    #   newregion.rot = R0
    #   newregion.center = 	C0
    #   newregion.size 	=     s0 / BOUNDING_BOX_SCALE
	#   
    #   chunk.region = newregion
    #   chunk.updateTransform()
    #if(FILTER_MESH == True):
    #  chunk.dense_cloud.setConfidenceFilter(min_confidence=0,max_confidence=2)
    #  chunk.dense_cloud.selectPointsByColor(color=[0,0,0], tolerance=255, channels='RGB')
    #  chunk.dense_cloud.removeSelectedPoints()
    #chunk.dense_cloud.setConfidenceFilter(min_confidence=0,max_confidence=3)
    #chunk.dense_cloud.selectPointsByColor(color=[0,0,0], tolerance=255, channels='RGB')
    #chunk.dense_cloud.removeSelectedPoints()
    #Build Mesh

    print('Build Mesh')
    #print('Build Depth Maps')
    #chunk.buildDepthMaps(downscale=CLOUD_QUALITY, filter_mode=FILTER_MODE,reuse_depth=True)
    chunk.buildModel(surface_type=SURFACE_QUALITY,source_data=Metashape.DataSource.DepthMapsData, interpolation=SURFACE_INTERPOLATION, face_count=FACE_COUNT)

    chunk.model.removeComponents(10000)
    if(CLOSE_HOLES == True):
       print('Close Holes')
       chunk.model.closeHoles(100)
    #print('Build Texture')
    chunk.buildUV()
    chunk.buildTexture( texture_size=TEXTURE_SIZE)
    ## Export model
    chunk.exportModel(path=os.path.join(FRAME_DIR, 'model.obj'), format=Metashape.ModelFormat.ModelFormatOBJ)


    #doc.clear()
    #os.remove(os.path.join(FRAME_DIR, 'project.psx'))
    #try:
    #    shutil.rmtree(os.path.join(FRAME_DIR, 'project.files'))
    #except OSError as err:
    #    print("OS error: {0}".format(err))

    doc.save(os.path.join(FRAME_DIR, 'calibration.psx'))  # checkpoint, save the project

    print("Script finished")


def compute_average(input_folder,camera):
   global OUTPUT_DIR,AVERAGE_NUM, TAKE_2, SCAN_PATH, camera_folders

   images = sorted([os.path.basename(x) for x in  glob.glob(os.path.join(input_folder,"*.jpg"))])
   images = images[1:AVERAGE_NUM]
   #print(images)

   image_data = []
   for img in range(1,len(images)):
       this_image = cv2.imread(os.path.join(input_folder,images[img]), 1)
       image_data.append(this_image)

   avg_image = image_data[0]
   for i in range(len(image_data)):
       if i == 0:
           pass
       else:
           alpha = 1.0/(i + 1)
           beta = 1.0 - alpha
           avg_image = cv2.addWeighted(image_data[i], alpha, avg_image, beta, 0.0)

   #avg_image=cv2.cvtColor(avg_image, cv2.COLOR_BGR2RGB)
   if TAKE_2 is not None:
      images = sorted([os.path.basename(x) for x in  glob.glob(os.path.join(os.path.join(SCAN_PATH,camera_folders[camera],TAKE_2),"*.jpg"))])
      this_image = cv2.imread(os.path.join(SCAN_PATH,camera_folders[camera],TAKE_2,images[0]), 1)	  
      avg_image = cv2.addWeighted(this_image, 0.3, avg_image, 0.6, 0.0)	
      contrast = 3. # Contrast control ( 0 to 127)
      brightness = 20.0 # Brightness control (0-100)
      
      # call addWeighted function. use beta = 0 to effectively only
      #operate on one image
      avg_image = cv2.addWeighted( avg_image, contrast, avg_image, 0, brightness)	  
   cv2.imwrite(os.path.join(OUTPUT_DIR,'avg_images','avg_img_%02d.png'%camera), avg_image)

if __name__ == '__main__':
    Metashape.app.cpu_enable = True
    Metashape.app.gpu_mask = 1
    camera_folders = sorted([os.path.basename(x) for x in  glob.glob(os.path.join(SCAN_PATH,'*'))  if 'Cam'in os.path.basename(x)])
    camera_list = []
    threads = []

    if COMPUTE_AVERAGE:
       os.makedirs(os.path.join(OUTPUT_DIR,'avg_images'),exist_ok=True)
       for camera in range(0,len(camera_folders)):
          t = Thread(target=compute_average, args=[os.path.join(SCAN_PATH,camera_folders[camera],TAKE),camera])
          t.start()
          threads.append(t)

          camera_list.append(os.path.join(OUTPUT_DIR,'avg_images','avg_img_%02d.jpg'%camera))
       for t in threads:
           t.join()
    else:
        os.makedirs(os.path.join(OUTPUT_DIR, 'avg_images'), exist_ok=True)
        for idx, camera in enumerate(camera_folders):
            if os.path.exists(os.path.join(OUTPUT_DIR, 'avg_images', f'avg_img_{idx:02d}.png')):
               camera_list.append(os.path.join(OUTPUT_DIR, 'avg_images', f'avg_img_{idx:02d}.png'))  
               continue
            FRAME_path = sorted([os.path.basename(x) for x in  glob.glob(os.path.join(SCAN_PATH,camera,TAKE,'*.avif'))])[FRAME]
            # Copy image to output directory
            import shutil
            shutil.copy(os.path.join(SCAN_PATH,camera,TAKE,FRAME_path), os.path.join(OUTPUT_DIR, 'avg_images', f'{camera}.avif'))
            
            command = f'convert {os.path.join(SCAN_PATH,camera,TAKE,FRAME_path)} -resize 100% ' + os.path.join(OUTPUT_DIR, 'avg_images', f'avg_img_{idx:02d}.png')
            os.system(command)

            if len(FRAME_path):
               camera_list.append(os.path.join(OUTPUT_DIR, 'avg_images', f'avg_img_{idx:02d}.png'))  
            
            # Delete AVIF file
            os.remove(os.path.join(OUTPUT_DIR, 'avg_images', f'{camera}.avif'))

    print("valid cameras:",len(camera_list))

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

    start_total = time.time()
    reconstruct_frame()
    end_total = time.time()
    print("Total running time: %d"%((end_total - start_total) / 60))