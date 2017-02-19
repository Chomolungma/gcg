import os
import time
from collections import defaultdict
import copy
import threading

import numpy as np
import tensorflow as tf

from rllab.sampler.utils import rollout
import rllab.misc.logger as logger

class RNNCriticSampler(object):

    def __init__(self, env, policy, rollouts_per_sample, max_path_length, render=False):
        self._env = env
        self._policy = policy
        self._rollouts_per_sample = rollouts_per_sample
        self._max_path_length = max_path_length
        self._render = render

        ### statistics
        self._stats = defaultdict(int)
        self._total_timesteps = 0
        ### files
        self._curr_file_num = 0
        self._policy_lock = threading.RLock()
        ### both
        self._update_lock = threading.RLock()
        ### for logging
        self._logger_stats = defaultdict(int)

    ##################
    ### Statistics ###
    ##################

    def _update_statistics(self, paths):
        for path in paths:
            path_timesteps = len(path['observations'])
            new_total_timesteps = self._total_timesteps + path_timesteps
            old_pct = self._total_timesteps / float(new_total_timesteps)
            new_pct = path_timesteps / float(new_total_timesteps)

            for name, values in (('observations', path['observations']),
                                 ('actions', path['actions']),
                                 ('rewards', path['rewards'])):
                self._stats[name+'_mean'] = old_pct * self._stats[name+'_mean'] + new_pct * np.mean(values, axis=0)
                if np.shape(self._stats[name+'_mean']) is tuple():
                    self._stats[name+'_mean'] = np.array([self._stats[name+'_mean']])
                self._stats[name+'_cov'] = old_pct * self._stats[name+'_cov'] + new_pct * np.cov(np.transpose(values))
                if np.shape(self._stats[name+'_cov']) is tuple():
                    self._stats[name+'_cov'] = np.array([[self._stats[name+'_cov']]])
                orth, eigs, _ = np.linalg.svd(self._stats[name+'_cov'])
                self._stats[name+'_orth'] = orth / np.sqrt(eigs + 1e-5)

            self._total_timesteps = new_total_timesteps

    #############
    ### Files ###
    #############

    def _tfrecord_fname(self, file_num):
        assert(logger.get_snapshot_dir() is not None)
        tfrecords_dir = os.path.join(logger.get_snapshot_dir(), 'tfrecords')
        if not os.path.exists(tfrecords_dir):
            os.makedirs(tfrecords_dir)
        return os.path.join(tfrecords_dir, '{0}_tfrecords_itr{1}.tfrecords'.format(
            os.path.basename(logger.get_snapshot_dir()), file_num))

    def _save_tfrecord(self, paths):
        def _floatlist_feature(value):
            return tf.train.Feature(float_list=tf.train.FloatList(value=np.ravel(value).tolist()))

        fname = self._tfrecord_fname(self._curr_file_num)
        self._curr_file_num += 1

        writer = tf.python_io.TFRecordWriter(fname)
        for path in paths:
            for t in range(len(path['observations']) - self._policy.H):
                feature = {
                    'observation': _floatlist_feature(path['observations'][t]),
                    'actions': _floatlist_feature(path['actions'][t:t+self._policy.H]),
                    'rewards': _floatlist_feature(path['rewards'][t:t+self._policy.H])
                }
                example = tf.train.Example(features=tf.train.Features(feature=feature))
                writer.write(example.SerializeToString())
        writer.close()

    ################
    ### Rollouts ###
    ################

    def sample_rollouts(self):
        start_time = time.time()

        paths = []
        for _ in range(self._rollouts_per_sample):
            with self._policy_lock:
                paths.append(rollout(self._env, self._policy, max_path_length=self._max_path_length))

        with self._update_lock:
            self._update_statistics(paths)
            self._save_tfrecord(paths)
            self._logger_stats = {
                'FinalRewardMean': np.mean([path['rewards'][-1] for path in paths]),
                'FinalRewardStd': np.std([path['rewards'][-1] for path in paths]),
                'AvgRewardMean': np.mean([np.mean(path['rewards']) for path in paths]),
                'AvgRewardStd': np.std([np.mean(path['rewards']) for path in paths]),
                'RolloutTime': time.time() - start_time
            }

    #######################
    ### Policy training ###
    #######################

    def get_tfrecords_and_statistics(self):
        with self._update_lock:
            tfrecords = [self._tfrecord_fname(i) for i in range(self._curr_file_num)]
            statistics = copy.deepcopy(self._stats)
            logger_stats = copy.deepcopy(self._logger_stats)
        return tfrecords, statistics, logger_stats

    def update_policy(self, training_policy):
        with self._update_lock:
            self._policy.match(training_policy)