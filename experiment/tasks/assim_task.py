"""Forcing task."""
import os
import shutil
from datetime import timedelta
import json
#import logging
import yaml
from netCDF4 import Dataset
import numpy as np
from sfcpert.letkf_exp import run_enkf
from experiment.tasks import AbstractTask


class ExternalAssim(AbstractTask):
    """Perturb state task."""

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

    def execute(self):
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
        #mbr = self.config.get_value("general.realization")
        nens = len(self.config.get_value("forecast.ensmsel"))
        archive_dir = self.config.get_value("system.archive_dir")
        first_guess_dir = self.platform.substitute(archive_dir, basetime=self.fg_dtg)
        ana_dir = self.platform.substitute(archive_dir, basetime=self.dtg)
 
        obpattern = self.config.get_value("assim.general.obpath")
        obpattern = self.platform.substitute(obpattern, basetime=self.dtg)
        hofxpattern = self.config.get_value("assim.general.hofxpath")
        print(hofxpattern)
        hofxpattern = self.platform.substitute(hofxpattern, basetime=self.dtg - self.fcint, validtime=self.dtg)
        bgpattern = first_guess_dir + "@mbr@/" + "SURFOUT" + self.suffix
        anpattern = ana_dir + "@mbr@/" + "ANALYSIS" + self.suffix
        imp_r = self.config.get_value("assim.localization.horizontal_gp")
        vert_d = self.config.get_value("assim.localization.vertical_m")
        cfg_dict = self.config.get_value("assim.control").dict()
        cfg_file = "cfg_assim.json" 
        print(cfg_dict)
        with open(cfg_file, "w") as f:
            json.dump(cfg_dict, f)
        #cfg_file = self.platform.substitute(self.config.get_value("assim.config"))
        print(bgpattern)
        print(anpattern)
        print("hofx",hofxpattern)
        print(obpattern)
        print(cfg_file)
        domain = {
            "lon0": self.geo.xlon0,
            "lat0": self.geo.xlat0,
            "latc": self.geo.xlatcen,
            "lonc": self.geo.xloncen,
            "nx": self.geo.nimax,
            "ny": self.geo.njmax,
            "dx": self.geo.xdx}

        run_enkf(cfg_file, bgpattern, obpattern, anpattern, hofxpattern, nens, domain, imp_r=imp_r, vert_d=vert_d, write_cv=True)
        
        for i in range(nens):
            fc_start_sfx = self.wrk + "%03d" % i + "/fc_start_sfx"
            os.makedirs(os.path.dirname(fc_start_sfx), exist_ok=True)
            if os.path.islink(fc_start_sfx):
                os.unlink(fc_start_sfx)
            os.symlink(anpattern.replace("@mbr@", "%03d" % i), fc_start_sfx)



