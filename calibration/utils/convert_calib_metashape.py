"""
source ../setup_env
metashape scan_reconstruction.py
"""
import os
import sys

os.environ["AGISOFT_FLS"] = 'lm-agisoft-fls.mpi-klsb.mpg.de:5842'

import Metashape
import numpy as np
from pathlib import Path
import time
import shutil 
import glob
import xml.etree.ElementTree as ET
import re
### CHANGE THESE ONLY ###################################################################################################

#INPUT_PATH = '/HPS/RLData1/work/Nils/22-10-13-calibration' #path camSorting.txt
#OUTPUT_DIR = '/HPS/RLData1/work/Nils/22-10-13-calibration'

#IMAGE_W = 3840
#IMAGE_H = 2160	
#IMAGE_W = 2048
#IMAGE_H = 2048

#IMAGE_W = 2056
#IMAGE_H = 1504


#IMAGE_W = 346
#IMAGE_H = 260
#IMAGE_W = 1920
#IMAGE_H = 1080

IMAGE_W = 4112
IMAGE_H = 3008


#IMAGE_W = 2160
#IMAGE_H = 4096

#IMAGE_W = 7000#5348 #2674
#IMAGE_H = 9344#7140  #3570


INPUT_PATH = '/HPS/RLData1/work/StudioCalibrations'  #path camSorting.txt

INPUT_PATH = os.path.join(INPUT_PATH,sorted([os.path.basename(x) for x in glob.glob(os.path.join(INPUT_PATH,'*')) if os.path.isfile(os.path.join(x,'cameras.calib'))])[-1])

#INPUT_PATH = '/CT/RLData3/static00/VoluCap_3/REC008/seq'

#INPUT_PATH = '/HPS/RLData1/work/test_dataset/face_rig/distortion'  #path camSorting.txt

OUTPUT_DIR = INPUT_PATH



#########################################################################################################################

CALIB_PATH = INPUT_PATH + '/cameras.calib'

##default volucap
#boxwidth = 3 * 1000
#boxheight = 3 * 1000 
#boxdepth = 3 * 1000
#offset_from_floor = 0.01 * 1000 # 5mm up from the floor 
#new_checkerboard_offset = 0


##default
boxwidth = 5.5 * 1000
boxheight = 2.5 * 1000 
boxdepth = 4.75 * 1000
offset_from_floor = 0.01 * 1000 # 5mm up from the floor 
new_checkerboard_offset = boxwidth * 0.4

#old one with green screen
#boxwidth = 3.9 * 1000
#boxheight = 2.5 * 1000 
#boxdepth = 5.0 * 1000
#offset_from_floor = 0.0026 * 1000 # 5mm up from the floor
#new_checkerboard_offset = boxwidth * 0.2 #only for old sequence, from ddc

##full room, for background	
#boxwidth = 12.5 * 1000
#boxheight = 3.6 * 1000 
#boxdepth = 10.5 * 1000	
#offset_from_floor = -0.26 * 1000

###full room,and only floor
#boxwidth = 5.5 * 1000
#boxheight = 2.5 * 1000 
#boxdepth = 4.75 * 1000
##offset_from_floor = 0.0026 * 1000 # 5mm up from the floor #was -0.06 with green screen
#offset_from_floor = -0.26  * 1000 # 5mm up from the floor #was -0.06 with green screen




	
def update_bbox(chunk):

	
    newregion = chunk.region
	
    newregion.center = Metashape.Vector([new_checkerboard_offset, boxheight / 2 + offset_from_floor,0])

    newregion.size = Metashape.Vector([boxwidth, boxheight, boxdepth ])
	
    chunk.region = newregion
    chunk.updateTransform()



def convert_calib(camera_list):


    # Create new project
    doc = Metashape.Document()
    FRAME_DIR = os.path.join(OUTPUT_DIR,'calib_converted')
    doc.addChunk()
    chunk = doc.chunks[-1]
	
    if not os.path.exists(OUTPUT_DIR):
       os.mkdir(OUTPUT_DIR)
       print("Directory " , OUTPUT_DIR ,  " Created ")
    else:    
        print("Directory " , OUTPUT_DIR ,  " already exists")	

    if not os.path.exists(FRAME_DIR):
       os.mkdir(FRAME_DIR)
       print("Directory " , FRAME_DIR ,  " Created ")
    else:    
        print("Directory " , FRAME_DIR ,  " already exists")
		
	

    chunk.crs = Metashape.CoordinateSystem('LOCAL_CS["Local CS",LOCAL_DATUM["Local Datum",0],UNIT["millimetre",1]]')	
    calibration   		= Metashape.Calibration()
    calibration.width 	= IMAGE_W
    calibration.height 	= IMAGE_H
    calibration.cx 		= float(0) 
    calibration.cy 		= float(0)  
    calibration.f 		= float(0) 
    calibration.b1 		= float(0)
    calibration.b2 		= float(0)
    calibration.k1 		= float(0)
    calibration.k2 		= float(0)	
    calibration.p1 		= float(0)
    calibration.p2 		= float(0)
    calibration.k3 		= float(0)
	
    extr=[]
    intr=[]
    distor=[]
    with open(CALIB_PATH) as f:
         lines = f.readlines()
    for line in range(0,len(lines)):
        if ('distortionModel' in lines[line]):
           continue
        if ('distortion' in lines[line]):
            d = lines[line].replace('distortion','')
            distortion = np.fromstring(d, dtype=float, sep=' ')	 							
            distortion[2], distortion[3] = distortion[3], distortion[2]	
            distor.append( ' '.join(str(e) for e in distortion))	
        if ('intrinsics' in lines[line]):
           temp_str = ''		
           temp_str+=np.array2string(np.fromstring(lines[line + 1].replace('#',''), dtype=np.float32, sep=' ').reshape((3,1))*float(IMAGE_W)).replace('[',' ').replace(']',' ')
           temp_str+=np.array2string(np.fromstring(lines[line + 2].replace('#',''), dtype=np.float32, sep=' ').reshape((3,1))*float(IMAGE_W)).replace('[',' ').replace(']',' ')
           temp_str+=lines[line + 3].replace('#','')		 
           intr.append(temp_str)	   
           continue		
        if ('extrinsic' in lines[line]):	 
           temp_str = ''		
           temp_str+=lines[line + 1].replace('#','')
           temp_str+=lines[line + 2].replace('#','')
           temp_str+=lines[line + 3].replace('#','')
           pose = np.fromstring(temp_str, dtype=np.float32, sep=' ').reshape((3,4)).transpose()
           z = np.zeros((4,1), dtype=np.float32)
           z[3]=1
           final_pose = np.append(pose,z,axis=1)	   
           extr.append(np.linalg.solve(final_pose,np.identity(4)))    
           continue				
	
    for i in range(0,len(intr)):
        opencv_storage =  ET.Element("opencv_storage")
        ET.SubElement(opencv_storage, 'image_Width').text = str(IMAGE_W)
        ET.SubElement(opencv_storage, 'image_Height').text = str(IMAGE_H)
        Camera_Matrix = ET.SubElement(opencv_storage, 'Camera_Matrix',{'type_id':'opencv-matrix'})		
        ET.SubElement(Camera_Matrix,'rows').text = '3'
        ET.SubElement(Camera_Matrix,'cols').text = '3'
        ET.SubElement(Camera_Matrix,'dt').text = 'd'
        ET.SubElement(Camera_Matrix,	'data').text = str(intr[i])
		
        Distortion_Coefficients = ET.SubElement(opencv_storage, 'Distortion_Coefficients',{'type_id':'opencv-matrix'})		
        ET.SubElement(Distortion_Coefficients,'rows').text = '5'
        ET.SubElement(Distortion_Coefficients,'cols').text = '1'
        ET.SubElement(Distortion_Coefficients,'dt').text = 'd'
        ET.SubElement(Distortion_Coefficients,	'data').text = str(distor[i])				
        tree = ET.ElementTree(opencv_storage)
		
        with open(FRAME_DIR+ '/'+ camera_list[i]+'.xml', "wb") as f: 
            tree.write(f,xml_declaration=True) 
       		
    for current_camera in range(0,len(camera_list)):	
       camera = chunk.addCamera()
       camera.label = camera_list[current_camera]
       #camera.open(grab_image(SCAN_PATH,current_camera,iframe))
       # add the sensor to the camera
       sensor = chunk.addSensor() #creating camera calibration group for the loaded image
       sensor.label =  camera_list[current_camera]
       sensor.type = Metashape.Sensor.Type.Frame
       sensor.width = IMAGE_W
       sensor.height = IMAGE_H
       calibration.load(path=os.path.join(FRAME_DIR,camera.label)+'.xml',format=Metashape.CalibrationFormat.CalibrationFormatOpenCV)		
 
       sensor.user_calib 	= calibration
       sensor.fixed = True
       camera.sensor = sensor
       camera.transform = extr[current_camera] 

    update_bbox(chunk)

    shutil.rmtree(os.path.join(OUTPUT_DIR,'calib_converted'))

    chunk.exportCameras(OUTPUT_DIR+'/cameras.xml')	

    #doc.save(os.path.join(FRAME_DIR, 'project.psx'))  # checkpoint, save the project

    print("Script finished")
	
if __name__ == '__main__':
	
    if len(sys.argv)>1:
       IMAGE_W = int(sys.argv[1])
       IMAGE_H =  int(sys.argv[2])	
       INPUT_PATH	= str(sys.argv[3])
       boxwidth = float(sys.argv[4])#2.5 * 1000
       boxheight = float(sys.argv[5])#2.5 * 1000 
       boxdepth = float(sys.argv[6])#2.5 * 1000
       offset_from_floor =float(sys.argv[7]) #0 # 5mm up from the floor 
       new_checkerboard_offset = float(sys.argv[8])#0
       OUTPUT_DIR = INPUT_PATH
       CALIB_PATH = INPUT_PATH + '/cameras.calib'
    try:
        with open(INPUT_PATH + '/camSorting.txt') as f:
             lines = f.readlines()
        camera_list = []
        for line in lines: 
           camera_list.append(line.strip().split()[1])  
    except IOError:
          print("File camSorting.txt is not found, assuming we don't need it!!!")
          video_list = glob.glob(INPUT_PATH + "/*.avi")
          video_list.sort()		  
          camera_list = []
          for video in range(0,len(video_list)):
             camera_list.append(os.path.splitext(os.path.basename(video_list[video]))[0]) 		  

    start_total = time.time()
    convert_calib(camera_list)
  		 
    end_total = time.time()
    print("Total running time: %d"%((end_total - start_total) / 60))
