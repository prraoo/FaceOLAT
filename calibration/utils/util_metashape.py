import os
import Metashape
import math

TEXTURE_SIZE=4096



def build_texture(chunk):
    global TEXTURE_SIZE
	
    chunk.buildUV()
    chunk.buildTexture( texture_size=TEXTURE_SIZE)
	
    colorizeModel = Metashape.Tasks.ColorizeModel()
    colorizeModel.source_data =Metashape.DataSource.ImagesData
    colorizeModel.apply(chunk) 	
	
	
def calc_reprojection(chunk):
	point_cloud = chunk.tie_points 
	points = point_cloud.points
	if points == None:
		return (None,None)
	npoints = len(points)
	projections = point_cloud.projections
	err_sum = 0
	num = 0
	photo_avg = {}
	
	for camera in range(0,len(chunk.cameras)):
		if not chunk.cameras[camera].transform:
			continue
		T = chunk.cameras[camera].transform.inv()
		calib = chunk.cameras[camera].sensor.calibration
		point_index = 0
		photo_num = 0
		photo_err = 0
		for proj in projections[chunk.cameras[camera]]:
			track_id = proj.track_id
			while point_index < npoints and points[point_index].track_id < track_id:
				point_index += 1
			if point_index < npoints and points[point_index].track_id == track_id:
				if not points[point_index].valid:
					continue
				dist = chunk.cameras[camera].error(points[point_index].coord, proj.coord).norm() ** 2
				err_sum += dist
				num += 1
				photo_num += 1
				photo_err += dist
		if photo_num:				
			photo_avg[camera] = (math.sqrt(photo_err / photo_num), photo_num)
		else:
			photo_avg[camera]	= (0,0) #n/a	   
	sigma = math.sqrt(err_sum / num)
	rep_avg = sigma
	return (rep_avg, photo_avg)	