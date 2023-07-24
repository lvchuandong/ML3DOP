import os
from pathlib import Path
import dpkt
import datetime
import numpy as np
from tqdm import tqdm

import lidar


class LSLidarManager:
    def __init__(self, pcap_path, out_root, params):
        self.pcap_path = Path(pcap_path)
        self.params = params
        self.out_root = out_root

        self.txt_path = None
        self.pcd_path = None
        self.out_path = None
        self.lidar_reader = None
        self.pos_X = None
        self.pos_Y = None
        self.pos_Z = None
        self.intensities = None
        self.theta = None
        self.timestamps = None
        self.distances = None
        self.indices = None
        self.alpha = None
        self.cur_azimuth = None
        self.last_azimuth = None
        self.datetime = None
        self.frame_nr = 0

        self.lidar = lidar.LSC16()

    def run(self):
        """
        Extracts point clouds from pcap file
        """
        pcap_len = self.get_pcap_length()
        if pcap_len <= 0:
            return

        # open pcap file
        try:
            f_pcap = open(self.pcap_path, 'rb')
            self.lidar_reader = dpkt.pcap.Reader(f_pcap)
        except Exception as ex:
            print(str(ex))
            return

        # create output folder hierarchy
        self.create_folders()

        # iterate through each data packet and timestamps
        pbar = tqdm(total=pcap_len)
        for idx, (ts, buf) in enumerate(self.lidar_reader):
            if idx < self.params['from']:
                continue
            if 0 < self.params['to'] < idx:
                break

            eth = dpkt.ethernet.Ethernet(buf)

            data = eth.data.data.data

            # Handle Data-Frame (Point clouds)
            if eth.data.data.sport == self.params['data-port']:
                self.process_data_frame(data, ts, idx)

            pbar.update(1)

    def get_pcap_length(self):
        # open pcap file
        try:
            f_pcap = open(self.pcap_path, 'rb')
            lidar_reader = dpkt.pcap.Reader(f_pcap)  

        except Exception as ex:
            print(str(ex))
            return 0

        counter = 0
        # iterate through each data packet and timestamps
        for _, _ in enumerate(lidar_reader):
            counter += 1
        f_pcap.close()
        print("message lenth:", counter)
        return counter

    def create_folders(self):
        self.out_path = Path("{}/{}".format(self.out_root, self.pcap_path.stem))

        # create output dir
        os.makedirs(self.out_path.absolute(), exist_ok=True)

        # create txt-file dir
        if self.params['txt']:
            self.txt_path = Path("{}/{}".format(self.out_path, "data_txt"))
            os.makedirs(self.txt_path.absolute(), exist_ok=True)

        # create pcd-file dir
        if self.params['pcd']:
            self.pcd_path = Path("{}/{}".format(self.out_path, "data_pcd"))
            os.makedirs(self.pcd_path.absolute(), exist_ok=True)

    def process_data_frame(self, data, timestamp, index):
        cur_X, cur_Y, cur_Z, cur_intensities, cur_theta, cur_timestamps, cur_distances = \
            self.lidar.process_data_frame(data, timestamp)
        n_seq = int(len(cur_X) / self.lidar.count_lasers)
        cur_indices = np.tile(np.arange(self.lidar.count_lasers), n_seq)
        cur_alpha = np.tile(self.lidar.omega, n_seq)

        # initialise states
        if index == 0:
            self.pos_X = cur_X
            self.pos_Y = cur_Y
            self.pos_Z = cur_Z
            self.intensities = cur_intensities
            self.theta = cur_theta
            self.timestamps = cur_timestamps
            self.distances = cur_distances
            self.indices = cur_indices
            self.alpha = cur_alpha

        if self.cur_azimuth is None:    
            self.cur_azimuth = cur_theta
            self.last_azimuth = cur_theta

        # update current azimuth before checking for roll over
        self.cur_azimuth = cur_theta

        idx_rollover = self.is_roll_over()

        # handle rollover (full 360° frame store in a file)
        if idx_rollover is not None:
            if idx_rollover > 0:
                self.pos_X = np.hstack((self.pos_X, cur_X[0:idx_rollover]))
                self.pos_Y = np.hstack((self.pos_Y, cur_Y[0:idx_rollover]))
                self.pos_Z = np.hstack((self.pos_Z, cur_Z[0:idx_rollover]))
                self.intensities = np.hstack((self.intensities, cur_intensities[0:idx_rollover]))
                self.theta = np.hstack((self.theta, cur_theta[0:idx_rollover]))
                self.timestamps = np.hstack((self.timestamps, cur_timestamps[0:idx_rollover]))
                self.distances = np.hstack((self.distances, cur_distances[0:idx_rollover]))
                self.indices = np.hstack((self.indices, cur_indices[0:idx_rollover]))
                self.alpha = np.hstack((self.alpha, cur_alpha[0:idx_rollover]))

            ts0 = self.timestamps[0]
            curr_time = str(datetime.datetime.utcfromtimestamp(ts0) + datetime.timedelta(hours=8))
            curr_time = curr_time.replace(":", "-")
            curr_time = curr_time.replace(" ", "_")

            if self.params['txt']:
                fpath = "{}/{}_{}.txt".format(self.txt_path, self.frame_nr, curr_time)
                write_txt(fpath, self.timestamps, self.indices, self.pos_X, self.pos_Y, self.pos_Z,
                          self.intensities, self.alpha, self.theta, self.distances)

            if self.params['pcd']:
                fpath = "{}/{}_{}.pcd".format(self.pcd_path, self.frame_nr, curr_time)
                write_pcd(fpath, self.pos_X, self.pos_Y, self.pos_Z, self.intensities)

            self.pos_X = cur_X[idx_rollover:]
            self.pos_Y = cur_Y[idx_rollover:]
            self.pos_Z = cur_Z[idx_rollover:]
            self.intensities = cur_intensities[idx_rollover:]
            self.theta = cur_theta[idx_rollover:]
            self.timestamps = cur_timestamps[idx_rollover:]
            self.distances = cur_distances[idx_rollover:]
            self.indices = cur_indices[idx_rollover:]
            self.alpha = cur_alpha[idx_rollover:]

            self.frame_nr += 1

            # reset roll over check
            self.cur_azimuth = None
            return

        if index > 0:
            self.pos_X = np.hstack((self.pos_X, cur_X))
            self.pos_Y = np.hstack((self.pos_Y, cur_Y))
            self.pos_Z = np.hstack((self.pos_Z, cur_Z))
            self.intensities = np.hstack((self.intensities, cur_intensities))
            self.theta = np.hstack((self.theta, cur_theta))
            self.timestamps = np.hstack((self.timestamps, cur_timestamps))
            self.distances = np.hstack((self.distances, cur_distances))
            self.indices = np.hstack((self.indices, cur_indices))
            self.alpha = np.hstack((self.alpha, cur_alpha))

        self.last_azimuth = cur_theta

    def is_roll_over(self):
        """
        Check whether 360° rotation of the lidar happens or not
        """
        # check whether the roll-over happens in the same data packet or not
        diff_cur = self.cur_azimuth[1:] - self.cur_azimuth[0:-1]
        # if not, then check whether the roll-over happens in the adjacent data packet or not
        diff_cur_last = 0
        if self.cur_azimuth[0] != self.last_azimuth[0]:
            diff_cur_last = self.cur_azimuth[0] - self.last_azimuth[-1]
        
        res_cur = np.where(diff_cur < 0.)[0]
        if res_cur.size > 0:
            index = res_cur[0] + 1  # the first index after roll-over
            return index
        elif diff_cur_last < 0.:
            index = 0
            return index
        else:
            return None


def write_txt(path, timestamps, laser_id, X, Y, Z, intensities=None, alpha=None, theta=None, distances=None):
    header = "timestamp,laser_id,X,Y,Z,intensity,vertical_angle,horizontal_angle,distance\n"
    try:
        fp = open(path, 'w')
        fp.write(header)
    except Exception as ex:
        print(str(ex))
        return

    M = np.vstack((timestamps, laser_id, X, Y, Z))

    if intensities is not None:
        M = np.vstack((M, intensities))
    if alpha is not None:
        M = np.vstack((M, alpha))
    if theta is not None:
        M = np.vstack((M, theta))
    if distances is not None:
        M = np.vstack((M, distances))

    M =  M.T
    M = M[np.where(M[:,-1]!=0)]  # remove invalid values
    np.savetxt(fp, M, fmt=('%.6f', '%d', '%.6f', '%.6f', '%.6f', '%d', '%d', '%.3f', '%.4f'), delimiter=',')
    fp.close()


def write_pcd(path, X, Y, Z, I):
    X = X.reshape(1, -1)
    Y = Y.reshape(1, -1)
    Z = Z.reshape(1, -1)
    I = I.reshape(1, -1)
    points = np.hstack((X.T, Y.T, Z.T, I.T)).reshape(-1, 4)
    points = points[np.where((points[:,0]!=0) & (points[:,1]!=0) & (points[:,2]!=0))]  # remove invalid values

    handle = open(path, 'a')

    point_num = points.shape[0]

    # pcd header
    handle.write('# .PCD v0.7 - Point Cloud Data file format\nVERSION 0.7\nFIELDS x y z intensity\nSIZE 4 4 4 4\nTYPE F F F F\nCOUNT 1 1 1 1')
    string = '\nWIDTH ' + str(point_num)
    handle.write(string)
    handle.write('\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0')
    string = '\nPOINTS ' + str(point_num)
    handle.write(string)
    handle.write('\nDATA ascii')

    for i in range(point_num):
        string = '\n' + str(points[i, 0]) + ' ' + str(points[i, 1]) + ' ' + str(points[i, 2]) + ' ' + str(points[i, 3])
        handle.write(string)
    handle.close()
