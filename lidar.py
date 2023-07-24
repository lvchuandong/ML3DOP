import numpy as np


class LSC16:
    # factor distance centimeter value to meter
    FACTOR_CM2M = 0.01

    # factor distance value to cm, each LSC16 distance unit is 2.5 mm
    FACTOR_MM2CM = 0.25

    def __init__(self):
        self.timing_offsets = self.calc_timing_offsets()

        # The following is the channel vertical angle of the uniform 2 degree lidar
        self.omega = np.array([-15, 1, -13, 3, -11, 5, -9, 7, -7, 9, -5, 11, -3, 13, -1, 15])

        self.count_lasers = 16

    def calc_timing_offsets(self):
        single_firing = 3.125  # μs  Firing time interval of each channel of LSC16
        # Time units converted to s
        offset = -single_firing * np.linspace(16 * 24 - 1, 0, num=16 * 24) / 1000000
        return offset

    def process_data_frame(self, data, timestamp):
        """
        Process data packet
        :param data: A LSC16 packet consisting of 12 (n) blocks and 24 (m) sequences and 16 firing pre sequence
        :param timestamp:
        :return: X,Y,Z-coordinate, intensity, azimuth, timestamp, distance of each firing, shape of each=[384x1]
        """
        data = np.frombuffer(data, dtype=np.uint8).astype(np.uint32)

        # LSC16 has 12 blocks each 100 bytes data
        # data-length = 1206 bytes
        blocks = data[0:1200].reshape(12, 100)

        distances = []
        intensities = []
        azimuth_per_block = []

        for i, blk in enumerate(blocks):
            dists, intense, angles = self.read_firing_data(blk)
            distances.append(dists[0:16])
            distances.append(dists[16:32])
            intensities.append(intense[0:16])
            intensities.append(intense[16:32])
            azimuth_per_block.append(angles)

        azimuth_per_block = np.array(azimuth_per_block)

        # Calculate the azimuth of each channel
        # Convert the dimension of azimuth into the same dimension as that of distances and intensities
        azimuth = self.calc_precise_azimuth(azimuth_per_block).reshape(24, 16)
        distances = np.array(distances)
        intensities = np.array(intensities)

        # now calculate the cartesian coordinate of each point
        X, Y, Z = self.calc_cart_coord(distances, azimuth)

        X = X.flatten()
        Y = Y.flatten()
        Z = Z.flatten()
        intensities = intensities.flatten()
        azimuth = azimuth.flatten()
        # calculating timestamp [μs] of each firing
        timestamps = timestamp + self.timing_offsets
        distances = distances.flatten() * self.FACTOR_MM2CM * self.FACTOR_CM2M

        return X, Y, Z, intensities, azimuth, timestamps, distances

    def read_firing_data(self, data):
        block_id = data[0] + data[1] * 256
        # 0xeeff is upper block
        assert block_id == 0xeeff

        # The returned result is only the azimuth of the first address of a data block,
        # and interpolation calculation is required to obtain the azimuth of other channels
        azimuth = (data[2] + data[3] * 256) / 100

        firings = data[4:].reshape(32, 3)
        distances = firings[:, 0] + firings[:, 1] * 256
        intensities = firings[:, 2]
        return distances, intensities, azimuth

    def calc_precise_azimuth(self, azimuth):
        """
        Linear interpolation of azimuth values
        """
        org_azi = azimuth.copy()

        precision_azimuths = []
        for n in range(12):
            azimuth = org_azi.copy()
            try:
                # First, adjust for an Azimuth rollover from 359.99° to 0°
                if azimuth[n+1] < azimuth[n]:
                    azimuth[n+1] += 360.

                # Determine the azimuth Gap between data blocks
                azimuth_gap = azimuth[n+1] - azimuth[n]
            except:
                if azimuth[n] < azimuth[n-1]:
                    azimuth[n] += 360.
                azimuth_gap = azimuth[n] - azimuth[n-1]

            factor = azimuth_gap / 32.

            # iterate through each firing
            for k in range(32):
                precise_azimuth = azimuth[n] + factor * k
                if precise_azimuth >= 360.:
                    precise_azimuth -= 360.
                precision_azimuths.append(precise_azimuth)

        precision_azimuths = np.array(precision_azimuths)
        return precision_azimuths

    def calc_cart_coord(self, distances, azimuth):
        # convert distances to meters
        distances = distances * self.FACTOR_MM2CM * self.FACTOR_CM2M
        alpha = np.tile(self.omega * np.pi / 180., 1)
        theta = azimuth * np.pi / 180.

        X = distances * np.cos(alpha) * np.cos(theta)
        Y = distances * np.cos(alpha) * np.sin(-theta)
        Z = distances * np.sin(alpha)
        return X, Y, Z
