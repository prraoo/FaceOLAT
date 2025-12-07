import os
import glob
import fcntl
import fnmatch
import shutil
import time
import stat
from pathlib import Path

class FileLock():
    def __init__(self, fpath, supressOutput=False):

        self.lock = fpath
        self.has_lock = True
        self.supressOutput = supressOutput

    def __enter__(self):
        if not self.supressOutput:
           print('Locking file %s'%self.lock)

        try:
            with open(self.lock, "x") as self.f:
                self.f.write(str(os.getpid()))
        except FileExistsError:
                print('Locking failed %s'%self.lock)
                self.has_lock = False

        return self
    def __exit__(self, type, value, traceback):
        if self.has_lock:
            if not self.supressOutput:
               print('Unlocking file %s'%self.lock)
            self.f.close()
            os.remove(self.lock)



def file_age_in_seconds(pathname):
    return time.time() - os.stat(pathname)[stat.ST_MTIME]

def set_mod_time(pathname):
  # Get the current time
  current_time = time.time()

  # Set the creation and modification datetime of the file
  os.utime(pathname, (current_time, current_time))
  
  
def clear_folder_content(path):
   filelist = glob.glob(path)
   for f in filelist:
       print('deleting file '+ str(f))   
       os.remove(f)	


def get_list_of_folders(path,list_to_ignore=[]):
   result =  [ name for name in os.listdir(path) if os.path.isdir(os.path.join(path, name)) ] 
   final_result = []
   if len(list_to_ignore):
     for item in result:
        found = False
        for target in list_to_ignore:	 
            if target in item:
               found = True		
               break
        if not found:			   
           final_result.append(item)	   
   return sorted(final_result)
def delete_folder(input_folder):		   
    try:
        shutil.rmtree(input_folder)
    except OSError as err:
        print("OS error: {0}".format(err))
		
   

def wait_for_file(path_file,timeout=30): #30sec wait
    start_time =time.time()
    while not os.path.exists(path_file):
        print('waiting for mesh export')
        time.sleep(3)       		
        end_time=time.time()		    
        if( end_time - start_time > timeout):
           return False

    return True	
		

def file_exists(file): 
   if not os.path.isfile(file):
      print('File ' + file + 'doesnt exist, exiting')
      return False

   return True	
   
def makeNewDir(path_dir):

    if not os.path.exists(path_dir):
       try:
           os.makedirs(path_dir,exist_ok=True)
           print("Directory " , path_dir,  " Created ")		   
       except:
             print("Directory failed  " , path_dir,  " Created ")			   
             pass	   

    else:    
        print("Directory " , path_dir,  " already exists")		
    

def get_sorted_basenames(pathFolder, exts):

   file_list = []
   
   for ext in exts:
    file_list += [os.path.basename(x) for x in glob.glob(os.path.join(pathFolder,ext))]
	

   return sorted(file_list)	
   
def read_file_as_lines(pathFile):
   if os.path.exists(pathFile):	
      with open(pathFile) as f:
           lines = f.readlines()
      return [x for x in lines if x.strip()]	   
          
       	    
   return []
   
def write_file_as_lines(pathFile,lines): 
  
   lock_file = '.cache/file_%s.lock'%(pathFile.split('/')[-1])	
   	   			 
   with FileLock(lock_file) as lock:
       if lock.has_lock:  
          f=open(pathFile, "w")
          
          for line in sorted(lines):    			  
             f.write(str(line))	 
          f.close()			 
	   
		 
def check_if_all_obj_done(OUTPUT_DIR,frame_start,frame_end, ext = '.obj'):

   all_done = True
   
   if frame_end <= 0: return False  
   
   for iframe in range(frame_start,frame_end):
      FRAME_DIR = os.path.join(OUTPUT_DIR,"%06d"%iframe)
      if os.path.exists(FRAME_DIR):	   
         if not os.path.exists(os.path.join(FRAME_DIR, 'model'+ext)):
            all_done = False			 
            break
		 
         else: #clean up
              if(Path(str(os.path.join(FRAME_DIR, 'model'+ext))).stat().st_size < 3*1000): 
                os.remove(os.path.join(FRAME_DIR, 'model'+ext))
                all_done = False
                break				
              if os.path.exists(os.path.join(FRAME_DIR, 'output')):			 
                 try:
                     shutil.rmtree(os.path.join(FRAME_DIR, 'output'))
                 except OSError as err:
                     print("OS error: {0}".format(err))
              if os.path.exists(os.path.join(FRAME_DIR, 'transform_000000')):							 
                 try:
                     shutil.rmtree(os.path.join(FRAME_DIR, 'transform_000000'))
                 except OSError as err:
                     print("OS error: {0}".format(err))
   				 
              if os.path.exists(os.path.join(FRAME_DIR, 'temp')):						  
                 try:
                     shutil.rmtree(os.path.join(FRAME_DIR,'temp'))
                 except OSError as err:
                     print("OS error: {0}".format(err))					 
      else:
           all_done = False			 
           break	
		   
   return all_done	

def all_done_videos(dir_path,num_of_cams):	
    # list to store files
    number = 0
    # Iterate directory
    for file in os.listdir(dir_path):
       #print(file)	
        # check only text files
       if fnmatch.fnmatch(file,  '*[0-9]*.mp4') and not fnmatch.fnmatch(file,  '*[0-9]*_.mp4'):
          number += 1
          command_test = "ffprobe -loglevel error -show_entries stream=codec_type -of default=nw=1 " + os.path.join(dir_path,file) 
          test_result = os.popen(command_test).read()
          if "codec_type=video" not in test_result:
             number -= 1
	  
		 
    #print('number of finished videos ' + str(number))			
    return number == num_of_cams














	