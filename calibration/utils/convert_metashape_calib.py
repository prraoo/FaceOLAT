import os
import sys
os.environ["AGISOFT_FLS"] = 'lm-agisoft-fls.mpi-klsb.mpg.de:5842'


import Metashape
import sys
import shutil
import xml.etree.ElementTree as ET
import numpy as np
import glob
# sys.path.append("../../util")

from utils import convert_xml

######################################################################

#IMAGE_W = 4112
#IMAGE_H = 3008
#IMAGE_W = 3840
#IMAGE_H = 2160
#IMAGE_W = 1920
#IMAGE_H = 1080
#IMAGE_W = 346
#IMAGE_H = 260
#IMAGE_W = 2464
#IMAGE_H = 3280


NUM_CAMS = 42
volucap_label = 'cam.%04d'


#INPUT_PATH = '/HPS/RLData1/work/test_dataset/dummy_recon/rigging_test/10379'
#OUTPUT_DIR = '/HPS/RLData1/work/test_dataset/dummy_recon/rigging_test/10379'


INPUT_PATH = '/CT/RLData3/static00/VoluCap_3/REC008_/seq/recon/000000'
OUTPUT_DIR = '/CT/RLData3/static00/VoluCap_3/REC008_/seq/recon/000000'
#INPUT_PATH = '/CT/RLData2/work/LargeScaleDataset/Subject0011_/loose/scans/recon/10407/captury'
#OUTPUT_DIR = '/CT/RLData2/work/LargeScaleDataset/Subject0011_/loose/scans/recon/10407/captury'

######################################################################


Sensor_Size_X = 10.0 # in mm, hardcoded and will work just fine, as we do not know real sensor size

INTR = []
EXTR = []
DISTORTION = []
def get_camera_by_label(chunk,label):
   for i in range(0,len(chunk.cameras)):
      if(label==chunk.cameras[i].label):
         return int(i)
   
   return -1	
def format_float(num):
   return format(float(num), '.9f')

	
def read_xml_calib(path,chunk):    
    global INTR, DISTORTION
	
    INTR.clear()
    DISTORTION.clear()
	
    for i in range(0, len(chunk.cameras)):
        #print('reading xml '+chunk.cameras[i].sensor.label)
        xmlTree = ET.parse(path + '/calib-opencv' +'/' + chunk.cameras[i].label + '.xml')
        rootElement = xmlTree.getroot()
        
        DISTORTION.append(rootElement.find('Distortion_Coefficients').find('data').text)
        temp = DISTORTION[i].split()
        temp[2], temp[3] = temp[3], temp[2]#swapping to match captury format
        DISTORTION[i] = " ".join(temp)
      
        INTR.append(rootElement.find('Camera_Matrix').find('data').text)   


	
def convert_metashape_calib(image_w,image_h,input_path,output_path,filename='cameras.calib',chunk=None,SCALE_TO_MM=False,CHANGE_TO_Y_UP=False):	
    global   Sensor_Size_X,INTR,EXTR,DISTORTION,NUM_CAMS



	
    INTR = []
    EXTR = []
    DISTORTION = [] 
		 
    if chunk==None:
       image_w_list, image_h_list = convert_xml.read_out_image_resolutions(input_path + '/cameras.xml')
	
       camera_list = []
       try:
           with open(input_path + '/camSorting.txt') as f:
                lines = f.readlines()
           for line in lines: 
               camera_list.append(line.strip().split()[1])  
       except IOError:
              print("File camSorting.txt is needed to get right ids for cameras. exiting")
              print('assuming normal indexing')
              for cam in range(NUM_CAMS):			  
                  camera_list.append(volucap_label%cam)  
              SCALE_TO_MM = True				  
              #sys.exit(0)			  
       
       ##specifically for metashape!
       #if(len(camera_list)==0):
       #  camera_list = glob.glob1(input_path+'/images/', "*.jpg") 
       #  camera_list = sorted(camera_list, key=lambda e: int(e.split('_')[0]))
       #  for current_camera in range(0,len(camera_list)):
       #     camera_list[current_camera] = camera_list[current_camera].split('_')[0]
	   
       doc = Metashape.Document()
       chunk = doc.addChunk()
	   
       print(camera_list)

	   
       for current_camera in range(0,len(camera_list)):	
		   
              image_w = int(image_w_list[current_camera]) 
              image_h = int(image_h_list[current_camera])
 			  
              camera = chunk.addCamera()
              camera.label = camera_list[current_camera]
              # add the sensor to the camera
              sensor = chunk.addSensor() #creating camera calibration group for the loaded image
              sensor.label =  camera_list[current_camera]
              sensor.type = Metashape.Sensor.Type.Frame
              sensor.width = image_w
              sensor.height = image_h
              camera.sensor = sensor
       
       chunk.importCameras(input_path + '/cameras.xml')
       #chunk.exportCameras(input_path + '/cameras_.xml')
	   
    if CHANGE_TO_Y_UP:
       T = chunk.transform.matrix
       s = T.scale()
       S = Metashape.Matrix().Diag((s, s, s, 1))
       xm = Metashape.Matrix( [[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]] )
       chunk.transform.matrix = xm * S * T


    if SCALE_TO_MM:	 
 	
       newregion = chunk.region
       newregion.size = Metashape.Vector([chunk.region.size[0]*1000.0, chunk.region.size[1]*1000.0, chunk.region.size[2]*1000.0])
       chunk.crs = Metashape.CoordinateSystem('LOCAL_CS["Local CS",LOCAL_DATUM["Local Datum",0],UNIT["millimetre",1]]')			   
       chunk.region = newregion
	   
	   
       chunk.updateTransform()
	   


	
       for i in range(0,len(chunk.cameras)):
	   
          matrix_extr = chunk.cameras[i].transform 
	      	   
          matrix_extr[0,3] *= 1000.0
          matrix_extr[1,3] *= 1000.0
          matrix_extr[2,3] *= 1000.0
	             
          #print(matrix_extr[0,3])
          chunk.cameras[i].transform  = matrix_extr	
    
    
    OPENCV_DIR = os.path.join(output_path,'calib-opencv')
    if not os.path.exists(OPENCV_DIR):
       os.makedirs(OPENCV_DIR)
    
    
    
    
    T = chunk.transform.matrix
    for i in range(0,len(chunk.cameras)):	
          
       chunk.cameras[i].sensor.calibration.save(OPENCV_DIR + '/'+ chunk.cameras[i].label+'.xml',format=Metashape.CalibrationFormat.CalibrationFormatOpenCV)
      
       extr = ''
    
       if chunk.cameras[i].transform is None:
           continue
       #transfrom camera coordinate system from internal to defined by user (in this by markers for example)
       matrix_extr = 	T *  (1.0/T.scale()) * chunk.cameras[i].transform
    	  
       extr_metashape = matrix_extr.inv() 
       
       for row in range(0,3):
          for column in range(0,4): 
             extr+=(str(extr_metashape[row,column])+ ' ')
    	  
       EXTR.append(extr)	
       
    read_xml_calib(output_path,chunk)	
 
    
    calibFile = output_path + '/' + filename	 
    outputFile = open(calibFile, 'w')
     
    HEADER_CALIB = 'tc camera calibration v0.3'
    
    outputFile.write(HEADER_CALIB + '\n')  
  
    	   	  
    tab = '\t'   
    f_distortion =   '\t\t {0:<10.8f}\t  {1:<10.8f}\t  {2:<10.8f}\t  {3:<10.8f}\t  {4:<10.8f}\t\n' 
    f_matrix_row_4 = '\t\t {0:>10.8f}\t  {1:>10.8f}\t  {2:>10.8f}\t  {3:>10.8f}\n' 
    f_matrix_row_3 = '\t\t {0:>10.8f}\t  {1:>10.8f}\t  {2:>10.8f}\n' 
    f_matrix_row_2 = '\t\t {0:>10.8f}\t  {1:>10.8f}\t' 
    f_matrix_row_1 = '\t\t {0:>10.8f}\t' 
    
    
    color_correction = '	colorCorrection\n\
    		red   0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65 66 67 68 69 70 71 72 73 74 75 76 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95 96 97 98 99 100 101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119 120 121 122 123 124 125 126 127 128 129 130 131 132 133 134 135 136 137 138 139 140 141 142 143 144 145 146 147 148 149 150 151 152 153 154 155 156 157 158 159 160 161 162 163 164 165 166 167 168 169 170 171 172 173 174 175 176 177 178 179 180 181 182 183 184 185 186 187 188 189 190 191 192 193 194 195 196 197 198 199 200 201 202 203 204 205 206 207 208 209 210 211 212 213 214 215 216 217 218 219 220 221 222 223 224 225 226 227 228 229 230 231 232 233 234 235 236 237 238 239 240 241 242 243 244 245 246 247 248 249 250 251 252 253 254 255\n\
    		green 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65 66 67 68 69 70 71 72 73 74 75 76 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95 96 97 98 99 100 101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119 120 121 122 123 124 125 126 127 128 129 130 131 132 133 134 135 136 137 138 139 140 141 142 143 144 145 146 147 148 149 150 151 152 153 154 155 156 157 158 159 160 161 162 163 164 165 166 167 168 169 170 171 172 173 174 175 176 177 178 179 180 181 182 183 184 185 186 187 188 189 190 191 192 193 194 195 196 197 198 199 200 201 202 203 204 205 206 207 208 209 210 211 212 213 214 215 216 217 218 219 220 221 222 223 224 225 226 227 228 229 230 231 232 233 234 235 236 237 238 239 240 241 242 243 244 245 246 247 248 249 250 251 252 253 254 255\n\
    		blue  0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65 66 67 68 69 70 71 72 73 74 75 76 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95 96 97 98 99 100 101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119 120 121 122 123 124 125 126 127 128 129 130 131 132 133 134 135 136 137 138 139 140 141 142 143 144 145 146 147 148 149 150 151 152 153 154 155 156 157 158 159 160 161 162 163 164 165 166 167 168 169 170 171 172 173 174 175 176 177 178 179 180 181 182 183 184 185 186 187 188 189 190 191 192 193 194 195 196 197 198 199 200 201 202 203 204 205 206 207 208 209 210 211 212 213 214 215 216 217 218 219 220 221 222 223 224 225 226 227 228 229 230 231 232 233 234 235 236 237 238 239 240 241 242 243 244 245 246 247 248 249 250 251 252 253 254 255'
    
    
    frame = '	frame	0'
    ending = tab+tab+'orientation		3\n' + tab+tab+'time			0 # unix timestamp'


 	
	
    for current_camera in range(0,len(chunk.cameras)):

        if chunk.cameras[i].transform is None:
            continue

        outputFile.write('camera'+tab+str(current_camera)+tab+'Camera_' +str(current_camera  + 1) + '\n')
        outputFile.write(color_correction  + '\n')
        outputFile.write(frame + '\n')
    	
        intr = np.fromstring(INTR[current_camera], dtype=float, sep=' ').reshape(3,3)
        extr = np.fromstring(EXTR[current_camera], dtype=float, sep=' ').reshape(3,4)
    
        image_w = int(chunk.cameras[current_camera].sensor.width) 
        image_h = int(chunk.cameras[current_camera].sensor.height)    
    	
        Sensor_Size_Y = Sensor_Size_X / (image_w / image_h)
		
		
    	
        outputFile.write(tab+tab+'sensorSize')
    	
        outputFile.write(f_matrix_row_2.format(Sensor_Size_X,Sensor_Size_Y) + tab +'# in mm\n') 		
    	
    	
        outputFile.write(tab+tab+'focalLength'+f_matrix_row_1.format(Sensor_Size_X * intr[0,0]/float(image_w))+'      	 	    # in mm\n')
    	
        outputFile.write(tab+tab+'pixelAspect'+f_matrix_row_1.format(intr[1,1] / intr[0,0])+'      	 	    # y / x\n')
    	
    
    
        centerOffset_X_mm =	Sensor_Size_X * (( intr[0,2] - (float(image_w) / 2.0)) / float(image_w))
        centerOffset_Y_mm =	Sensor_Size_Y * (( intr[1,2] - (float(image_h) / 2.0)) / float(image_h))
        
        
        outputFile.write(tab+tab+'centerOffset'+f_matrix_row_2.format(centerOffset_X_mm,centerOffset_Y_mm)+tab+'# in mm\n')		
    	
  		
        outputFile.write(tab+tab+'distortionModel	OpenCV\n')	
    
        distortion = 	DISTORTION[current_camera].split(' ')
        outputFile.write(tab+tab+'distortion')	
        outputFile.write(f_distortion.format(float(distortion[0]),float(distortion[1]),float(distortion[2]),float(distortion[3]),float(distortion[4])))
    
	 
  
        origin = -np.matmul(extr[:3,:3].transpose(), extr[:,3:]).reshape(1,3)  # -R^T*t	
    
    	   
        up		= -extr[1:2,:3]
        right	=  extr[0:1,:3]
    	
   
    
        outputFile.write(tab+tab+'origin'+f_matrix_row_3.format(origin[0][0],origin[0][1],origin[0][2]))	
        outputFile.write(tab+tab+'up'+f_matrix_row_3.format(up[0][0],up[0][1],up[0][2]))	
        outputFile.write(tab+tab+'right'+f_matrix_row_3.format(right[0][0],right[0][1],right[0][2]))	
    	
        outputFile.write('#    extrinsics' + '\n')
   	
    
        for row in range(0,3):
           outputFile.write('#'+f_matrix_row_4.format(extr[row,0],extr[row,1],extr[row,2],extr[row,3]))
    	   
        outputFile.write('#    intrinsics' + '\n')
    	
    
    
        for row in range(0,2):
           outputFile.write('#'+f_matrix_row_3.format(float(intr[row,0]/float(image_w)),float(intr[row,1]/float(image_w)),float(intr[row,2]/float(image_w))))	   
       
        outputFile.write('#'+f_matrix_row_3.format(float(intr[2,0]),float(intr[2,1]),float(intr[2,2])))	
    
        outputFile.write(ending + '\n')
    
    
    
    outputFile.close()
    
    try:
        shutil.rmtree(OPENCV_DIR)
    except OSError as err:
        print("OS error: {0}".format(err))
    

#####################################################################

#convert_metashape_calib(IMAGE_W,IMAGE_H,'/scratch/camstore/LargeScaleDataset/volucap/REC008_sven_movements_2_FS00046-FE13500_C02/01CAL','/scratch/camstore/LargeScaleDataset/volucap/REC008_sven_movements_2_FS00046-FE13500_C02/01CAL',chunk=None,SCALE_TO_MM=True)



#convert_metashape_calib(-1,-1,'/scratch/camstore/LargeScaleDataset/volucap/REC003_sven_face_impressions/01CAL','/scratch/camstore/LargeScaleDataset/volucap/REC003_sven_face_impressions/01CAL',chunk=None,SCALE_TO_MM=True)

