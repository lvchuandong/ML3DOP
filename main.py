import argparse
import yaml

from lidar_manager import *


def read_params(path):
    try:
        f = open(path, 'rb')
    except Exception as ex:
        print(str(ex))

    params = yaml.safe_load(f.read())
    return params


def main(args):
    path = args['path']
    out_dir = args['out_dir']
    config = args['config']
    params = read_params(config)
    lidar_manager = LSLidarManager(path, out_dir, params)
    lidar_manager.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--path', type=str, help="Path of the pcap file", required=True)
    parser.add_argument('-o', '--out-dir', type=str, help="Path of the output directory", required=True)
    parser.add_argument('-c', '--config', type=str, help="Path of the configuration file", required=True)

    args = vars(parser.parse_args())
    main(args)
