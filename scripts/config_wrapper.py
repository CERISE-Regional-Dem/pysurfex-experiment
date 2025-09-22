import numpy as np
import datetime
from experiment.config_parser import ParsedConfig
from experiment.toolbox import FileManager
from sfcpert.settings import Settings


### Configuration block ###
class ConfigWrapper:

    def __init__(self, cfgfile, dtg=None, fcint=None):
        self.cfgfile = cfgfile
        self.config = ParsedConfig.from_file(cfgfile)
        self.platform = FileManager(self.config).platform
        self.assimconf = Settings(self.config.get_value("assim.control").dict())
        if dtg is None:
            self.dtg = datetime.datetime.fromisoformat(self.config.get_value("general.times.basetime").replace("Z", "+00:00"))
        else:
            self.dtg = dtg
        if fcint is None:
            self.fcint = parse_iso_duration(self.config.get_value("general.times.cycle_length"))
        else:
            self.fcint = fcint
        self.fg_dtg = self.dtg - self.fcint

        self.archive_dir = self.config.get_value("system.archive_dir").replace("@RRR@", "@mbr@")
        self.first_guess_dir = self.platform.substitute(self.archive_dir, basetime=self.fg_dtg)
        self.ana_dir = self.platform.substitute(self.archive_dir, basetime=self.dtg)
        self.nens = len(self.config.get_value("forecast.ensmsel"))
        self.fgpath = f"{self.first_guess_dir}/SURFOUT.nc"
        self.anpath = f"{self.ana_dir}/ANALYSIS.nc"
        self.fg_diag_path = f"{self.first_guess_dir}/SURFOUT.{self.dtg.strftime('%Y%m%d_%Hh00')}.nc"
        self.an_diag_path = f"{self.ana_dir}/ANALYSIS_diagnostics.nc"
        self.domain = self.config.domain.dict()

    def get_config_for(self, dtg):
        return ConfigWrapper(self.cfgfile, dtg)        

    def for_member(self, path):
        return [path.replace("@mbr@", f"{i:03d}") for i in range(self.nens)]


def fill_pattern(gpath, dt, td=None):
    """ Fill the pattern in the file path with the date and time"""
    gpath = gpath.replace("@YYYY@", dt.strftime("%Y"))
    gpath = gpath.replace("@MM@", dt.strftime("%m"))
    gpath = gpath.replace("@DD@", dt.strftime("%d"))
    gpath = gpath.replace("@HH@", dt.strftime("%H"))
    if td is not None:
        gpath = gpath.replace("@YYYY_LL@", (dt+td).strftime("%Y"))
        gpath = gpath.replace("@MM_LL@", (dt+td).strftime("%m"))
        gpath = gpath.replace("@DD_LL@", (dt+td).strftime("%d"))
        gpath = gpath.replace("@HH_LL@", (dt+td).strftime("%H"))
    return gpath
    

def parse_iso_duration(iso_duration: str) -> datetime.timedelta:
    import re
    """Convert an ISO 8601 duration string to timedelta."""
    days = hours = minutes = seconds = 0
    
    match = re.match(r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
    if match:
        days = int(match.group(1) or 0)
        hours = int(match.group(2) or 0)
        minutes = int(match.group(3) or 0)
        seconds = int(match.group(4) or 0)
    
    return datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


def add_time(ds):
    s = [int(i) for i in ds.encoding["source"].split("/")[-6:-2]]
    tvars_ = [v for v in ds.variables]
    cvars = ["lon", "lat", "xx", "yy", "ZS", "FRAC", "LAI", "PATCH", "Distance", "COVER"]
    tvars = [item for item in tvars_ if not any(ex in item for ex in cvars)]
    tvars = tvars_
    dt = datetime.datetime(*s)
    ds[tvars] = ds[tvars].expand_dims({"time": [dt]})
    print(ds.dims)
    if "phony_dim_0" in ds.dims:
        ds = ds.rename({"phony_dim_0": "Nobs"})
    #ds = ds.rename({"Nobs": "Nobs"+dt.strftime("%j")})
    ds = ds.assign_coords({"Nobs": np.arange(ds.sizes["Nobs"]) + 1e6*float(dt.strftime("%Y%j"))})
    return ds


def add_time_n_member(ds):
    ds = add_time(ds)
    mbr = int(ds.encoding["source"].split("/")[-2])
    cvars = ["lon", "lat", "xx", "yy", "ZS", "FRAC", "LAI", "PATCH", "Distance", "COVER", "time", "Target"]
    tvars_ = [v for v in ds.variables]
    mtvars = [item for item in tvars_ if not any(ex in item for ex in cvars)]
    mvars = tvars_
    #ds[mtvars] = ds[mtvars].expand_dims({"member": [mbr]})
    ds = ds.expand_dims({"member": [mbr]})
    return ds



def setup_cluster(jobs=1, processes=1, mem="50GB", walltime="00:35:00"):
    from dask_jobqueue import SLURMCluster
    from dask.distributed import Client
    import sys
    cluster = SLURMCluster(
        cores=processes,  # each worker will have # threads
        processes=processes,
        memory=mem,  # each worker will have 24GB memory
        #interface="ib0",  # makes sure workers can communicate with eachother, maybe not needed
        walltime=walltime,  # set wall    time of Dask workers
        job_extra_directives=['--qos=nf',  # spin up each worker on "nf" queue
                              '--output=pdask.%j.out',
                              '--error=pdask.%j.out'], 
        #job_script_prologue=['source /hpcperm/fab0/git/sfcpert_oops/.venv/bin/activate; export HDF5_USE_FILE_LOCKING=FALSE'],  # ensure correct python environment used
        job_script_prologue=[f'source {sys.prefix}/bin/activate;export HDF5_USE_FILE_LOCKING=FALSE'],  # ensure correct python environment used
        )
    cluster.scale(jobs=jobs)
    #cluster.adapt(minimum=1, maximum=jobs)
    client = Client(cluster)
    print(client.dashboard_link)
    return client
