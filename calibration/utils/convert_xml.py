"""
source ../setup_env
metashape scan_reconstruction.py
"""
import os, sys
import xml.etree.ElementTree as ET

from utils import folder_file_util


#CAMSORT_PATH_INPUT = '/HPS/RLData1/work/Nils/22-08-16-calibration' #path camSorting.txt
#CAMSORT_PATH_OUTPUT = '/HPS/RLData1/work/Nils/22-10-13-calibration' #path camSorting.txt and settings.txt

def filter_nodes(root,camera_list_output,attributes):
    iter = 0  
    num_of_removed = 0  
    num = len(root)	
	
    for child in range(0,num):	
        for attr in attributes:
           root[child - num_of_removed].set(attr,str(iter))      		 
        if root[child-num_of_removed].attrib["label"] not in camera_list_output:
           #print(root[child - num_of_removed].attrib["label"])
           root.remove(root[child - num_of_removed])
           num_of_removed += 1
           continue
        iter+=1 
    root.set('next_id', str(iter)) 		
	
def convertCalib(input_xml,output_xml,camera_list_output):

    	
   xmlTree = ET.parse(input_xml)
   rootElement = xmlTree.getroot()

   for chunk in rootElement.findall("chunk"):
      for sensors in chunk.findall("sensors"):
         filter_nodes(sensors,camera_list_output, ['id'])	
      for cameras in chunk.findall("cameras"):
         filter_nodes(cameras,camera_list_output,['id','sensor_id'])				 
    
   xmlTree.write(output_xml,encoding='UTF-8',xml_declaration=True)   

def read_cameras(camsort_path):

    with open(camsort_path) as f:
         lines = f.readlines()
    camera_list_result = []
    for line in lines: 
       camera_list_result.append(line.strip().split()[1])
	   
    return camera_list_result	   
	
  

	  
def run_convert_calib(input,output):

    if not folder_file_util.file_exists(output + '/camSorting.txt'):
       return False
	
    camera_list_output = read_cameras(output + '/camSorting.txt')
	
    if not folder_file_util.file_exists(input + '/cameras.xml'):
       return False
   
    convertCalib(input + '/cameras.xml',output + '/cameras.xml',camera_list_output)
	
    return True
    

def remove_node(root,delete_node,attrib,attrib_value):

    for child in range(0,len(root)):
       for node in root[child].findall(delete_node):	
          if(node.attrib[attrib]==attrib_value):
             root[child].remove(node)


def delete_node(input_xml,output_xml,delete_node,attrib,attrib_value):
    	
   xmlTree = ET.parse(input_xml)
   rootElement = xmlTree.getroot()

   for chunk in rootElement.findall("chunk"):
      for sensors in chunk.findall("sensors"):
         remove_node(sensors,delete_node,attrib,attrib_value)	
			 
    
   xmlTree.write(output_xml,encoding='UTF-8',xml_declaration=True) 

#delete_node('debug_cameras.xml','test.xml','calibration','class','initial')
#result = run_convert_calib(CAMSORT_PATH_INPUT,CAMSORT_PATH_OUTPUT)
#
#if result:
#   print ('all good')

def read_node(root,node_name,attrib, attrib_value):
	
    result = []
	
    for child in range(0,len(root)):
       for node in root[child].findall(node_name):
          for attr in node.findall(attrib):
             result.append(attr.attrib[attrib_value])
		  
		  
    return result
	
	
def read_out_image_resolutions(input_xml):
	
   xmlTree = ET.parse(input_xml)
   rootElement = xmlTree.getroot()

   for chunk in rootElement.findall("chunk"):
      for sensors in chunk.findall("sensors"):		  
         width_array  = read_node(sensors,'calibration','resolution','width')	
         height_array = read_node(sensors,'calibration','resolution','height')			 
    
   return width_array, height_array 





