import multiprocessing
from math import radians, cos, sin, asin, sqrt
import pandas as pd
from joblib import Parallel, delayed
from .data_loader import *


def cal_distance(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371
    return c * r * 1000


def cluster_check(tmp_cluster, threshold_dis):
    for i in range(len(tmp_cluster)):
        for j in range(i, len(tmp_cluster)):
            if cal_distance(tmp_cluster[i][0], tmp_cluster[i][1], tmp_cluster[j][0], tmp_cluster[j][1]) > threshold_dis:
                return False
    return True


class StayPointDetector:

    def __init__(self, args):

        self.input_file = args.input_file
        self.output_folder = args.output_folder
        self.time_threshold = args.time_threshold
        self.distance_threshold = args.distance_threshold

    def naive_stay_point_detection(self, traj):
        traj = traj.reset_index(drop=True)
        num_points = len(traj)

        time_threshold_ = pd.Timedelta('{}minute'.format(self.time_threshold))
        sp_ = pd.DataFrame()
        s = pd.DataFrame()
        i = 0
        while i < num_points - 1:
            k = [i]
            j = i + 1

            while j < num_points:
                distance_tmp = cal_distance(lon1=traj.loc[i, 'lon'], lat1=traj.loc[i, 'lat'],
                                            lon2=traj.loc[j, 'lon'], lat2=traj.loc[j, 'lat'])
                if distance_tmp <= self.distance_threshold:

                    if traj.loc[j, 'timestamp'] - traj.loc[i, 'timestamp'] >= time_threshold_:
                        k.append(j)
                        j += 1
                    else:
                        i = j
                        break
                else:
                    i = j
                    break
            else:
                if len(k) >= 2:
                    ix = k[0]
                    jx = k[-1]
                    s.loc[0, 'user_id'] = traj.loc[ix, 'user_id']
                    s.loc[0, 'lon'] = traj.loc[ix:jx, 'lon'].mean()
                    s.loc[0, 'lat'] = traj.loc[ix:jx, 'lat'].mean()
                    s.loc[0, 'arrival_time'] = traj.loc[ix, 'timestamp']
                    s.loc[0, 'departure_time'] = traj.loc[jx, 'timestamp']
                    s.loc[0, 'venue_name'] = traj.loc[ix, 'venue_name']
                    sp_ = pd.concat([sp_, s], axis=0)
                break

            if len(k) >= 2:
                ix = k[0]
                jx = k[-1]
                s.loc[0, 'user_id'] = traj.loc[ix, 'user_id']
                s.loc[0, 'lon'] = traj.loc[ix:jx, 'lon'].mean()
                s.loc[0, 'lat'] = traj.loc[ix:jx, 'lat'].mean()
                s.loc[0, 'arrival_time'] = traj.loc[ix, 'timestamp']
                s.loc[0, 'departure_time'] = traj.loc[jx, 'timestamp']
                s.loc[0, 'venue_name'] = traj.loc[ix, 'venue_name']
                sp_ = pd.concat([sp_, s], axis=0)
        return sp_


def stay_point_detection_process(args):
    """
    We will consider multiple input GPS files in the future.
    """

    data = load_tsmc2014_tky(args.input_file)
    output_file_name = args.input_file.split('/')[-1].replace('.csv', '_stay_points.csv')
    stay_point_detector = StayPointDetector(args)
    try:
        data = data.sort_values(by=['user_id', 'timestamp'])
        data = data.reset_index(drop=True)[['user_id', 'timestamp',
                                            'lat', 'lon', 'venue_name']]
        sp = apply_parallel(data.groupby('user_id'), stay_point_detector.naive_stay_point_detection)
        sp.to_csv(args.output_folder + output_file_name, index=False)
        return sp, data
    except OSError:
        print('error found...')
        return


def apply_parallel(df_grouped, func):
    ret_lst = Parallel(n_jobs=multiprocessing.cpu_count())(delayed(func)(group) for name, group in df_grouped)
    return pd.concat(ret_lst)
