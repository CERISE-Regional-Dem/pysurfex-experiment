"""Forcing task."""
import os
import shutil
from datetime import timedelta
import json
import glob
#import logging
import yaml
from netCDF4 import Dataset
import numpy as np
from experiment.tasks import AbstractTask


from sfcpert.phys_util import compute_snow_diagnostics
from obsOp.Training_data_static import makeData
from obsOp.Predictions import run_GNN


# Hack for epygram
np.str = str
np.bool = bool

class AssimPP(AbstractTask):
    """postprocessing of analysis"""

    def __init__(self, config):
        """Construct assim task.

        Args:
            config (dict): Actual configuration dict

        """
        AbstractTask.__init__(self, config, name="AssimPP")
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
        
        mbr = self.config.get_value("general.realization")
        nens = len(self.config.get_value("forecast.ensmsel"))
        archive_dir = self.config.get_value("system.archive_dir")
        first_guess_dir = self.platform.substitute(archive_dir, basetime=self.fg_dtg)
        ana_dir = self.platform.substitute(archive_dir, basetime=self.dtg)
        print(self.config.dict())
        bgfile = f"{first_guess_dir}/SURFOUT{self.suffix}"
        anfile = f"{ana_dir}/ANALYSIS{self.suffix}"
        anadiagfile = f"{ana_dir}/ANALYSIS_diagnostics{self.suffix}"
        
        print("BG", bgfile)
        print("AN", anfile)
        
        hofxpattern = self.config.get_value("assim.general.hofxpath") #.replace("@RRR@", "@mbr@")
        hofxpattern = self.platform.substitute(hofxpattern, basetime=self.dtg - self.fcint, validtime=self.dtg)
        print(hofxpattern)
        cfg_dict = self.config.get_value("assim.control").dict()
        date_start = dtg.strftime("%Y%m%d")
        date_stop = date_start
        csurf_filetype = self.config.get_value("SURFEX.IO.CSURF_FILETYPE").lower()
        pgdfile = self.config.get_value("system.climdir") + "/PGD." + csurf_filetype
        satpattern = self.config.get_value("observations.satpath")
        sfxpattern = self.config.get_value("assim.general.sfxpath")        
        sfxpattern = self.platform.substitute(sfxpattern, basetime=self.dtg - self.fcint, validtime=self.dtg)
        channel_list = self.config.get_value("assim.ObsOp.channel_list")
        normdir = self.config.get_value("assim.ObsOp.normdir")
        modeldir = self.config.get_value("assim.ObsOp.modeldir")
        
        compute_snow_diagnostics(anfile, hofxpattern, anadiagfile)
                
        for channel_freq in channel_list:
            if os.path.exists(f"{ana_dir.replace('@mbr@', mbr)}/Graphs_{channel_freq.replace('.','_')}_{date_start}.h5"):
                graphpattern = f"{ana_dir.replace('@mbr@', mbr)}/xa_Graphs_{channel_freq.replace('.','_')}_{date_start}.h5"        
                predictionpattern = f"{ana_dir.replace('@mbr@', mbr)}/xa_Predictions_{channel_freq.replace('.','_')}_{date_start}.nc"
                
                makeData(
                    mbr, 
                    date_start, 
                    date_stop, 
                    pgdfile=pgdfile,
                    satpattern=satpattern, 
                    hofxpattern=anadiagfile,
                    outpattern=graphpattern,
                    sfxpath=anfile,
                    channel_freq=channel_freq)
                
                run_GNN(
                    mbr,
                    date_start,
                    date_stop,
                    inputfile=graphpattern,
                    outputfile=predictionpattern,
                    pgdfile=pgdfile,
                    normdir=normdir,
                    modeldir=modeldir,
                    channel_freq=channel_freq
                    )
            