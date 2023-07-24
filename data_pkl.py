import os
import numpy as np
import time
from datetime import datetime
import pickle
from tqdm import tqdm
import argparse


class generate_data_pkl():
    def __init__(self, args):
        self.imgs_path = args['imgs_path']
        self.lidar_path = args['lidar_path']
        self.camera_num = 4
        
        self.scene_names_list = sorted(os.listdir(self.imgs_path))
        self.imgs_list = None
        self.lidar_list = None
        # get a list of all imgs and lidar data's path
        self.get_imgs_lidar_list()
        
        self.imgs_tp_dict = None
        self.img0_path_array = None
        # get a timestamp dict of imgs and a array consisted of camera_0's path 
        self.get_imgs_tp()
        
        self.lidar_tp_dict = None
        self.lidar_path_dict = None
        # get a timestamp dict of lidar and a path dict of lidar's timestamp 
        self.get_lidar_tp()
        
        self.get_data_pkl()
        
    def __len__(self):
        return len(self.img0_path_array)
    
    def get_imgs_lidar_list(self):
        start_time = time.time()
        imgs_list = []
        for dirpath, dirnames, filenames in os.walk(self.imgs_path):
            for filename in filenames:
                imgs_name = os.path.join(dirpath, filename)
                imgs_list.append(imgs_name)
        self.imgs_list = sorted(imgs_list)
        
        lidar_list = []
        for dirpath, dirnames, filenames in os.walk(self.lidar_path):
            for filename in filenames:
                if filename.endswith('txt'):
                    lidar_name = os.path.join(dirpath, filename)
                    lidar_list.append(lidar_name)
        self.lidar_list = sorted(lidar_list)
        print("get_imgs_lidar_list done, use time: {}".format(time.time() - start_time))
    
    def get_imgs_tp(self):
        start_time = time.time()
        imgs_tp_dict = {}
        img0_path_list = []
        
        # timestamp are classified by scene_name and camera_id
        for i in range(len(self.scene_names_list)):
            scene_name = self.scene_names_list[i]
            imgs_tp_dict[scene_name] = {}
            for j in range(self.camera_num):
                imgs_tp_dict[scene_name]["img{}".format(j)] = np.array([])
        for i in range(len(self.imgs_list)):
            imgs_path_list = self.imgs_list[i].split("/")
            scene_name = imgs_path_list[-2]
            img_name = imgs_path_list[-1]
            name_list = os.path.splitext(img_name)[0].split("_")
            timestamp = name_list[0]
            cam_id = name_list[1]
            imgs_tp_dict[scene_name]["img{}".format(cam_id)] = \
                np.append(imgs_tp_dict[scene_name]["img{}".format(cam_id)], float(timestamp))
            if cam_id == "0":
                img0_path_list.append(self.imgs_list[i])
        self.imgs_tp_dict = imgs_tp_dict
        img0_path_list = sorted(img0_path_list)
        self.img0_path_array = np.array(img0_path_list)
        print("get_imgs_tp done, use time: {}".format(time.time() - start_time))
    
    def get_lidar_tp(self):
        start_time = time.time()
        lidar_tp_dict = {}
        lidar_path_dict = {}
        
        # timestamp are classified by scene_name, lidar_path are classified by scene_name and timestamp
        for i in range(len(self.scene_names_list)):
            scene_name = self.scene_names_list[i]
            scene_name = scene_name.replace("imgs", "lidar")
            lidar_tp_dict[scene_name] = np.array([])
            lidar_path_dict[scene_name] = {}
        for i in range(len(self.lidar_list)):
            lidar_path_list = self.lidar_list[i].split("/")
            scene_name = lidar_path_list[-3]
            lidar_name = lidar_path_list[-1]
            name_list = os.path.splitext(lidar_name)[0].split("_")
            timestamp = datetime.timestamp(datetime.strptime("{}_{}".format(name_list[1], name_list[2]), '%Y-%m-%d_%H-%M-%S.%f'))
            lidar_tp_dict[scene_name] = np.append(lidar_tp_dict[scene_name], timestamp)
            lidar_path_dict[scene_name]["{}".format(timestamp)] = self.lidar_list[i]
        self.lidar_tp_dict = lidar_tp_dict
        self.lidar_path_dict = lidar_path_dict
        print("get_lidar_tp done, use time: {}".format(time.time() - start_time))
        
    def get_data_pkl(self):
        data_dict = {}
        for idx in tqdm(range(len(self.img0_path_array))):
            img0_path = self.img0_path_array[idx]
            img0_dir_list = img0_path.split("/")
            scene_name = img0_dir_list[-2]
            img0_name = img0_dir_list[-1]
            img0_key = os.path.join(scene_name, img0_name)
            data_dict[img0_key] = {}
            
            # imgs_path are classified by img0_key and camera_id
            lidar_path_list = os.path.splitext(img0_name)[0].split("_")
            img0_tp = float(lidar_path_list[0])
            for i in range(1, self.camera_num):
                tp_diff_min_index = np.argmin(np.absolute(self.imgs_tp_dict[scene_name]["img{}".format(i)] - img0_tp))
                img_tp = self.imgs_tp_dict[scene_name]["img{}".format(i)][tp_diff_min_index]
                img_key = os.path.join(scene_name, "{:.6f}_{}.jpg".format(img_tp, i))
                data_dict[img0_key]["img{}".format(i)] = img_key
                
            # lidar_path are classified by img0_key
            scene_name = scene_name.replace("imgs", "lidar")
            tp_diff_min_index = np.argmin(np.absolute(self.lidar_tp_dict[scene_name] - img0_tp))
            lidar_tp = self.lidar_tp_dict[scene_name][tp_diff_min_index]
            lidar_path = self.lidar_path_dict[scene_name]["{}".format(lidar_tp)]
            lidar_path_list = lidar_path.split("/")
            lidar_txt_key = os.path.join(lidar_path_list[-3],lidar_path_list[-2],lidar_path_list[-1])
            lidar_pcd_key = os.path.join(lidar_path_list[-3],"data_pcd",lidar_path_list[-1].replace("txt", "pcd"))
            data_dict[img0_key]["lidar_txt"] = lidar_txt_key
            data_dict[img0_key]["lidar_pcd"] = lidar_pcd_key
        with open('data_all.pkl', 'wb') as f:
            pickle.dump(data_dict, f)


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-im', '--imgs_path', type=str, help="Path of the imgs data", required=True)
    parser.add_argument('-lp', '--lidar_path', type=str, help="Path of the lidar data", required=True)
    args = vars(parser.parse_args())
    
    generate_data_pkl(args)
