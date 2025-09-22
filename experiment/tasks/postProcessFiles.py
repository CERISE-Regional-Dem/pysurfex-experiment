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
from experiment.tasks import AbstractTask


class postProcessFiles(AbstractTask):
    """Perturb state task."""

    def __init__(self, config):
        """Construct assim task.

        Args:
            config (dict): Actual configuration dict

        """
        AbstractTask.__init__(self, config, name="postProcessFiles")
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
        mbr = self.config.get_value("general.realization")

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
        mbrstr = ""
        print(mbr, len(mbr), type(mbr))
        if nens > 0 and len(mbr) > 0:
            mbrstr = "_%03d" % int(mbr)

        diag_file = self.platform.substitute("SURFOUT.@YYYY_LL@@MM_LL@@DD_LL@_@HH_LL@h00.nc", basetime=dtg, validtime=dtg+fcint)        

        input_dir = self.platform.substitute(archive_dir, basetime=dtg)

        print(diag_file)
        print(input_dir)

        first_guess_dir = self.platform.substitute(input_dir, basetime=dtg)

        with open("/perm/sbjb/Projects/CERISE/git/cerise_regdem_land_dev06/data/nam/surfex_namelists.yml", "r") as file:
            config = yaml.safe_load(file)
            variable_list = config["offline_selected_output"]["NAM_WRITE_DIAG_SURFN"]["CSELECT"]

                                
        for mbr in range(nens):

            mbrin = "%03d" % int(mbr)

            # SURFOUT file
#            bgpattern = first_guess_dir + "@mbrin@/" + "SURFOUT.nc"            
#            fg_fname = f"{bgpattern.replace('@mbrin@', mbrin)}"
#
#            outpattern = first_guess_dir + "@mbrin@/" + "SURFOUT_SELECTED.nc"
#            out_fname = f"{outpattern.replace('@mbrin@', mbrin)}"

            # Analysis file
            anpattern = first_guess_dir + "@mbrin@/" + "ANALYSIS.nc"            
            an_fname = f"{anpattern.replace('@mbrin@', mbrin)}"

            outpattern = first_guess_dir + "@mbrin@/" + "ANALYSIS_SELECTED.nc"
            out_fname = f"{outpattern.replace('@mbrin@', mbrin)}"
                        
            readAndWrite(an_fname, out_fname, variable_list)

def readAndWrite(fg_fname, outfile, variables_to_copy):
      

      # Open the input NetCDF file
      with Dataset(fg_fname, mode="r") as src:

      # Create a new NetCDF file
        with Dataset(outfile, mode="w") as dst:
            # Copy global attributes
            dst.setncatts({attr: src.getncattr(attr) for attr in src.ncattrs()})

            # Copy dimensions
            for name, dimension in src.dimensions.items():
                dst.createDimension(
                    name, (len(dimension) if not dimension.isunlimited() else None)
                )

            # Copy the selected variables
            for var_name in variables_to_copy:
                if var_name in src.variables:
                    var = src.variables[var_name]

                    # Create the variable in the new file
                    #new_var = dst.createVariable(
                    #    var_name, var.datatype, var.dimensions
                    #)
                    new_var = dst.createVariable(
                    var_name,
                    var.datatype,
                    var.dimensions,
                    zlib=True,  # Enable compression
                    complevel=4  # Compression level (1=fast, 9=best compression)
                    )

                    # Copy the variable attributes
                    new_var.setncatts({attr: var.getncattr(attr) for attr in var.ncattrs()})

                    # Copy the variable data
                    new_var[:] = var[:]


    #print(f"Variables {variables_to_copy} have been written to {output_file}.")      
            



        


            
            






        # ECFS paths
#        ecpattern = self.config.get_value("general.ecfs_pattern")
#
#        if (dtg + fcint).strftime("%w%H") == "000": #  last cycle of week 
#            print("do archiveing")
#            ecdir = self.platform.substitute(ecpattern, basetime=dtg)
#            subprocess.run(["emkdir", "-p", ecdir])
#
#            dtstart = dtg + fcint - datetime.timedelta(weeks=1)
#            ntimes = int((dtg - dtstart).total_seconds()/fcint.total_seconds() + 1)
#            files = []
#            print("dtstart", dtstart)
#            savestate = False
#            for i in range(ntimes):
#                dt = dtstart + fcint*i
#                print("dt", dt)
#                if dt.strftime("%H") in self.config.get_value("general.archive_hours"):
#                    input_dir = self.platform.substitute(archive_dir, basetime=dt)
#                    input_dirp = self.platform.substitute(archive_dir, basetime=dt-fcint)
#                    histfile = input_dir + "SURFOUT" + self.suffix
#                    #analfile = input_dir + "ANALYSIS_summary" + self.suffix
#                    diag_file = self.platform.substitute("SURFOUT.@YYYY_LL@@MM_LL@@DD_LL@_@HH_LL@h00.nc", basetime=dt-fcint, validtime=dt)
#                    selefile = input_dirp + diag_file
#                    files += [selefile]
#
#                    print(i,histfile)
#                    if savestate:
#                        files += [histfile]
#                        savestate = False
#
#            missing = []
#            for i, f in enumerate(files):
#                if not os.path.isfile(files[i]):
#                    missing += [files.pop(i)]
#            tarfile = "output_mbr%s%s.tar" % (dtstart.strftime("%Y_w%U"), mbrstr)
#            print("MISSING FILES!!! %d " % len(missing), missing)
#            print(["tar", "-cf", tarfile] + files)
#            subprocess.run(["tar", "-cf", tarfile] + files)
#            print(["ecp", tarfile, ecdir])
#            subprocess.run(["ecp", tarfile, ecdir])



        

