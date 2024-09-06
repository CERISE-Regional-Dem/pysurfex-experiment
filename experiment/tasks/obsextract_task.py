"""Forcing task."""
import os
import shutil
from datetime import timedelta
import json
#import logging
import yaml
from netCDF4 import Dataset
import numpy as np
from sfcpert.observations import extract_obs
from experiment.tasks import AbstractTask


class ObsExtract(AbstractTask):
    """Extract observations task."""

    def __init__(self, config):
        """Construct assim task.

        Args:
            config (dict): Actual configuration dict

        """
        AbstractTask.__init__(self, config, name="PerturbState")
        self.var_name = self.config.get_value("task.var_name")
        try:
            user_config = self.config.get_value("task.forcing_user_config")
        except AttributeError:
            user_config = None
        self.user_config = user_config

    def exectue(self):
        pass

    def dont_execute(self):
        """Execute the perturb state task.

        Raises:
            NotImplementedError: _description_
        """
        dtg = self.dtg
        fcint = self.fcint
        
        kwargs = {}
        if self.user_config is not None:
            user_config = yaml.safe_load(open(self.user_config, mode="r", encoding="utf-8"))
            kwargs.update({"user_config": user_config})

        with open(self.wdir + "/domain.json", mode="w", encoding="utf-8") as file_handler:
            json.dump(self.geo.json, file_handler, indent=2)
        kwargs.update({"domain": self.wdir + "/domain.json"})
        
        kwargs.update({"dtg_start": dtg.strftime("%Y%m%d%H")})
        kwargs.update({"dtg_stop": (dtg + fcint).strftime("%Y%m%d%H")})
        mbr = self.config.get_value("general.realization")
        nens = len(self.config.get_value("forecast.ensmsel"))
        mbrstr = ""
        if nens > 0 and len(str(mbr))>0:
            mbrstr = "%03d" % int(mbr)
        archive_dir = self.config.get_value("system.archive_dir")
        input_dir = self.platform.substitute(archive_dir, basetime=self.dtg)
        print("input_dir", input_dir)
 
        diag_file = self.platform.substitute("SURFOUT.@YYYY_LL@@MM_LL@@DD_LL@_@HH_LL@h00.nc",basetime=self.dtg, validtime=self.dtg + self.fcint)
        print("diag_file", diag_file)
        obpattern = self.config.get_value("assim.hofxpath")
        obpattern = self.platform.substitute(obpattern, basetime=self.dtg + self.fcint).replace("@mbr@", mbrstr)
        hofxpattern = input_dir + diag_file
        cfg_file = self.platform.substitute(self.config.get_value("assim.config"))
        obslocfile = self.platform.substitute(self.config.get_value("assim.station_location_file"))
        domain = {"lat0": self.geo.xlat0,
                  "lon0": self.geo.xlon0,
                  "latc": self.geo.xlatcen,
                  "lonc": self.geo.xloncen,
                  "nx": self.geo.nimax,
                  "ny": self.geo.njmax,
                  "dx": self.geo.xdx}
        print("hofx_pattern", hofxpattern)
        print("obpattern", obpattern)
        print("cfg_file", cfg_file)
        os.makedirs(os.path.dirname(obpattern), exist_ok=True)
        extract_obs(cfg_file, hofxpattern, obpattern, obslocfile, domain)


        

