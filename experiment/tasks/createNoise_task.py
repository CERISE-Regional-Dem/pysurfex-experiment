"""
#################################################
White noise atmospheric forcing
Created 6.11.17 JB
##################################################
"""

from netCDF4 import Dataset
import numpy as np
import numpy.ma as ma
import os,glob,sys

from datetime import datetime
import json
import yaml
#import surfex
from experiment.tasks import AbstractTask
from sfcpert.create_noise import write_noise

class createNoise(AbstractTask):
    """ Create Noise task """
    

    def __init__(self, config):
        """Construct create noise task.

        Args:
            config (dict): Actual configuration dict

        """

        AbstractTask.__init__(self, config, "CreateNoise")
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
        kwargs = {}
        if self.user_config is not None:
            user_config = yaml.safe_load(
                    open(self.user_config, mode="r", encoding="utf-8")
            )
            kwargs.update({"user_config": user_config})

        dtg = self.dtg
        fcint = self.fcint
        dtg_prev = self.dtg - fcint
        cfg = self.config.get_value("eps.offline.noise").dict(descend_recursively=False)
        dt = self.config.get_value("forcing.timestep")
        nens = len(self.config.get_value("forecast.ensmsel"))
        tau = self.config.get_value("eps.tau")       #24.0 # decorrelation time
        forc_dir = self.config.get_value("system.forcing_dir")
        output_dir = self.platform.substitute(forc_dir, basetime=dtg)
        input_dir = self.platform.substitute(forc_dir, basetime=dtg_prev)

        input_file = output_dir + "FORCING.nc"
        with Dataset(input_file) as f:
            N = f.dimensions["Number_of_points"].size
            T = f.dimensions["time"].size

        for i in range(nens):
            noisefile_in = input_dir + "%03d/noise_%03d.nc" % (i, i)
            if not os.path.isfile(noisefile_in):
                noisefile_in = None
            noisefile_out = output_dir + "%03d/noise_%03d.nc" % (i, i)
            os.makedirs(output_dir + '%03d' % i, exist_ok=True)
            write_noise(cfg, 
                    T, 
                    dt, 
                    N, 
                    noisefile_out, 
                    input_file=noisefile_in, 
                    ny=self.geo.nlats, 
                    nx=self.geo.nlons)


def main():

   nens = int(sys.argv[1]) - 1
   nvar = int(sys.argv[2])      #3             # number of variables, rainf, sw, lw
   T = int(sys.argv[3])         #4                # number of timesteps in forcing file
   dt = int(sys.argv[4])        #1.0             # forcing timestep
   tau = int(sys.argv[5])       #24.0           # decorrelation time
   N = 57121                    # Domain size, should be extracted from file

   createNoise(nens, nvar, T, dt, tau, N)

if __name__ == '__main__':
    main()

