"""Forcing task."""
import os
import shutil
from datetime import timedelta
import json
import yaml
from netCDF4 import Dataset
import numpy as np
from obsOp.Predictions import run_GNN
from experiment.tasks import AbstractTask

class ObsOp(AbstractTask):
    """Perturb state task."""

    def __init__(self, config):
        """Construct assim task.

        Args:
            config (dict): Actual configuration dict

        """
        AbstractTask.__init__(self, config, name="ObsOp")
        self.var_name = self.config.get_value("task.var_name")
        #try:
        #    user_config = self.config.get_value("task.forcing_user_config")
        #except AttributeError:
        #    user_config = None
        #self.user_config = user_config

    def execute(self):
        """Execute the perturb state task.

        Raises:
            NotImplementedError: _description_
        """
        dtg = self.dtg
        fcint = self.fcint
        mbr = self.config.get_value("general.realization")

        kwargs = {}
                
        kwargs.update({"dtg_start": dtg.strftime("%Y%m%d%H")})
        kwargs.update({"dtg_stop": (dtg + fcint).strftime("%Y%m%d%H")})

        nens = len(self.config.get_value("forecast.ensmsel"))
        archive_dir = self.config.get_value("system.archive_dir")
        first_guess_dir = self.platform.substitute(archive_dir, basetime=self.fg_dtg)
        ana_dir = self.platform.substitute(archive_dir, basetime=self.dtg)
        
        obpattern = self.config.get_value("assim.general.obpath")
        obpattern = self.platform.substitute(obpattern, basetime=self.dtg)

        normdir = self.config.get_value("assim.ObsOp.normdir")
        modeldir = self.config.get_value("assim.ObsOp.modeldir")

        hofxpattern = self.config.get_value("assim.general.hofxpath")
        print(hofxpattern)
        hofxpattern = self.platform.substitute(hofxpattern, basetime=self.dtg - self.fcint, validtime=self.dtg)
        bgpattern = first_guess_dir + "@mbr@/" + "SURFOUT" + self.suffix
        
        csurf_filetype = self.config.get_value("SURFEX.IO.CSURF_FILETYPE").lower()
        pgdfile = self.config.get_value("system.climdir") + "/PGD." + csurf_filetype
        print("PGD:", pgdfile)

        mbrin = "%03d" % int(mbr)        
        date_start = dtg.strftime("%Y%m%d")
        date_stop = date_start

        run_GNN(mbrin, date_start, date_stop, ana_dir, pgdfile, normdir, modeldir)

