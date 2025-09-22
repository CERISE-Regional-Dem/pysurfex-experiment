"""Forcing task."""
import os
import shutil
import datetime
import json
#import logging
import yaml
from netCDF4 import Dataset
import numpy as np
import subprocess
from sfcpert.observations import extract_obs
from experiment.tasks import AbstractTask


class ArchiveECFS(AbstractTask):
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
        mbr = self.config.get_value("general.realization")
        nens = len(self.config.get_value("forecast.ensmsel"))
        archive_dir = self.config.get_value("system.archive_dir")
        forcing_dir = self.config.get_value("system.forcing_dir")
        
        mbrstr = ""
        print(mbr, len(mbr), type(mbr))
        if nens > 0 and len(mbr) > 0:
            mbrstr = "_%03d" % int(mbr)

        # ECFS paths
        ecpattern = self.config.get_value("general.ecfs_pattern")

        day_of_year = (dtg).timetuple().tm_yday

        #if (dtg + fcint).strftime("%w%H") == "000": #  last cycle of week 
        if day_of_year % 3 == 0:            
            
            print("do archiveing")
            ecdir = self.platform.substitute(ecpattern, basetime=dtg)
            subprocess.run(["emkdir", "-p", ecdir])
            
            dtstart = dtg + fcint - datetime.timedelta(days=3)            
#            dtstart = dtg + fcint - datetime.timedelta(weeks=1)            

            ntimes = int((dtg - dtstart).total_seconds()/fcint.total_seconds() + 1)
            files = []
            print("dtstart", dtstart)
            savestate = True
            for i in range(ntimes):
                dt = dtstart + fcint*i
                print("dt", dt)
                if dt.strftime("%H") in self.config.get_value("general.archive_hours"):
                    input_dir = self.platform.substitute(archive_dir, basetime=dt)
                    input_dirp = self.platform.substitute(archive_dir, basetime=dt-fcint)
                    anfile = input_dir + "ANALYSIS_SELECTED" + self.suffix
                    histfile = input_dir + "SURFOUT.nc"
                    #analfile = input_dir + "ANALYSIS_summary" + self.suffix
                    diag_file = self.platform.substitute("SURFOUT.@YYYY_LL@@MM_LL@@DD_LL@_@HH_LL@h00.nc", basetime=dt-fcint, validtime=dt)
                    selefile = input_dirp + diag_file
                    files += [selefile]
                    files += [anfile]

                    print(i,histfile)
                    if savestate and dt == dtg:
                        files += [histfile]
                        savestate = False

            missing = []
            for i, f in enumerate(files):
                if not os.path.isfile(files[i]):
                    missing += [files.pop(i)]
            tarfile = "output_restart_%s_%s_mbr%s.tar" % (dtstart.strftime("%Y%m%d%H"),dtg.strftime("%Y%m%d%H"), mbrstr)
            print("MISSING FILES!!! %d " % len(missing), missing)
            print(["tar", "-cf", tarfile] + files)
            subprocess.run(["tar", "-cf", tarfile] + files)
            print(["ecp", tarfile, ecdir])
            result = subprocess.run(["ecp", tarfile, ecdir])     

            if result.returncode == 0:
                print("Subprocess ran successfully. Continuing...")

            else:
                print(f"Subprocess failed with exit code {result.returncode}. Exiting...")
                exit(result.returncode)       

            dtstart_rm = dtstart - datetime.timedelta(days=3)
#            dtstart_rm = dtstart - datetime.timedelta(weeks=1)
            ntimes_rm = int((dtstart - dtstart_rm).total_seconds()/fcint.total_seconds() + 1)
            files_to_remove = []
            print("dtstart_rm", dtstart_rm)
            print(ntimes_rm)

            for i in range(ntimes_rm):
                dt = dtstart - fcint*i

                if dt.strftime("%H") in self.config.get_value("general.archive_hours"):

                    input_dir = self.platform.substitute(archive_dir, basetime=dt)
                    input_dirp = self.platform.substitute(archive_dir, basetime=dt-fcint)
                    forc_dir = self.platform.substitute(forcing_dir, basetime=dt)
                    
                    anfile = input_dir + "ANALYSIS_SELECTED" + self.suffix
                    histfile = input_dir + "SURFOUT.nc"                    
                    analfile = input_dir + "ANALYSIS.nc"
                    forcingfile = forc_dir + "FORCING.nc"
                    noisefile = forc_dir + "noise_000.nc"
                    diag_file = self.platform.substitute("SURFOUT.@YYYY_LL@@MM_LL@@DD_LL@_@HH_LL@h00.nc", basetime=dt-fcint, validtime=dt)
                    selefile = input_dirp + diag_file
                    files_to_remove += [selefile]
                    files_to_remove += [anfile]
                    files_to_remove += [histfile]
                    files_to_remove += [analfile]
                    files_to_remove += [forcingfile]
                    files_to_remove += [noisefile]
                    
            print(files_to_remove)
            for file in files_to_remove:
                if os.path.exists(file):  # Check if the file exists
                    os.remove(file)       # Remove the file
                    print(f"Removed: {file}")
                else:
                    print(f"File not found: {file}")
                




        

