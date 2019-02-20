# -*- coding: future_fstrings -*-
import os
from utils import get_logger
import yaml

log = get_logger(__name__)


class Config(object):
    CONFIG_FILENAME = "netskope.yaml"

    def get_config(self, input_cfgpath=''):
        ''' reads base config and merges with user config'''
        cur_dir = os.path.dirname(__file__)
        base_config_path = os.path.join(cur_dir, self.CONFIG_FILENAME)
        base_config = self.read_config(base_config_path)
        home_dir = os.path.join(os.path.expanduser("~"), self.CONFIG_FILENAME)
        cfg_locations = [input_cfgpath, home_dir, os.getenv("NETSKOPE_CNF", '')]
        configpath = self.get_config_path(cfg_locations)
        usercfg = self.read_config(configpath)
        config = self.merge_config(base_config, usercfg)
        log.info(f"config object created")
        return config

    def merge_config(self, base_config, usercfg):
        for k, v in usercfg.items():
            if k in base_config:
                base_config[k].update(v)
            else:
                base_config[k] = v
        return base_config

    def get_config_path(self, cfg_locations):
        for filepath in cfg_locations:
            if os.path.isfile(filepath):
                return filepath

        raise Exception(f"No Config file Found in following locations {cfg_locations}")

    @classmethod
    def read_config(cls, filepath):
        log.info(f"Reading config file: {filepath}")
        config = None
        with open(filepath, 'r') as stream:
            try:
                config = yaml.load(stream)
            except yaml.YAMLError as exc:
                log.error(f"Unable to read config {filepath} Error: {exc}")
        return config
