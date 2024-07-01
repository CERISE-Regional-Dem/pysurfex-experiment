"""Forcing task."""
import os
import shutil
from datetime import timedelta
import json
#import logging
import yaml
from netCDF4 import Dataset
import numpy as np
from sfcpert.perturb_forcing import perturb_forcing, remap_precip
from experiment.tasks import AbstractTask


class PerturbForcing(AbstractTask):
    """Perturb forcing task."""

    def __init__(self, config):
        """Construct perturb forcing task.

        Args:
            config (dict): Actual configuration dict

        """
        AbstractTask.__init__(self, config, name="PerturbForcing")
        self.var_name = self.config.get_value("task.var_name")
        try:
            user_config = self.config.get_value("task.forcing_user_config")
        except AttributeError:
            user_config = None
        self.user_config = user_config

    def execute(self):
        """Execute the perturb forcing task.

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
        cfg = self.platform.substitute(self.config.get_value("eps.offline.noise")).dict()
        forcing_dir = self.platform.get_system_value("forcing_dir")
        forcing_dir = self.platform.substitute(forcing_dir, basetime=self.dtg)
        input_forcing_dir = forcing_dir[:-4]
        
        noise_file = forcing_dir + "noise_%03d.nc" % int(mbr)
        output_format = self.config.get_value("SURFEX.IO.CFORCING_FILETYPE").lower()
        input_forcing_file = input_forcing_dir + "/FORCING.nc"
        if output_format == "netcdf":
            output = forcing_dir + "/FORCING.nc"
        else:
            raise NotImplementedError(output_format)

        kwargs.update({"of": output})
        kwargs.update({"output_format": output_format})

        pattern = self.config.get_value("forcing.pattern")
        input_format = self.config.get_value("forcing.input_format")
        kwargs.update({"geo_input_file": self.config.get_value("forcing.input_geo_file")})
        timestep = self.config.get_value("forcing.timestep")
        debug = self.config.get_value("forcing.debug")

        kwargs.update({"input_format": input_format})
        kwargs.update({"pattern": pattern})
        kwargs.update({"debug": debug})
        kwargs.update({"timestep": timestep})

        print(self.geo.nlats, self.geo.nlons)

        print(input_forcing_file, output)

        if self.config.get_value("eps.pert_forcing") == True:
            print("call perturb atm forcing for mbr %s" % mbr)
            perturb_forcing(input_forcing_file, noise_file, output, cfg)
            if self.config.get_value("eps.remap_precip") == True:
                remap_precip(output, self.geo.nlats, self.geo.nlons, 200, 4, keep_orographic=True)
        else:
            os.makedirs(forcing_dir, exist_ok=True)
            shutil.copyfile(input_forcing_file, output)



