""" Plot OMF statistics for a single time """

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde
import cartopy.crs as ccrs
import datetime
import dask
from scripts.config_wrapper import ConfigWrapper, setup_cluster
from scripts.plot_utils import timeaxis
from sfcpert.tools.area_def import sfx2areadef
from sfcpert.settings import Settings
from sfcpert.tools import io
from sfcpert.letkf_exp import prep_observations

matplotlib.rcParams["image.interpolation"] = "none"
matplotlib.rcParams["image.origin"] = "lower"
matplotlib.rcParams["axes.facecolor"] = "lightgrey"


def get_inc_ridge(fgfile, anfile, varnames):
    xf = io.read_state(fgfile, varnames=varnames, filetype="nc").flatten()
    xa = io.read_state(anfile, varnames=varnames, filetype="nc").flatten()
    mask = np.logical_and(~np.isnan(xf), ~np.isnan(xa))
    inc = xa[mask] - xf[mask]
    try:
        kde = gaussian_kde(inc)
    except:
        kde = None
    return (np.min(inc), np.max(inc),  kde) 


def get_ridge(filename, varnames):
    xf = io.read_state(filename, varnames=varnames, filetype="nc").flatten()
    xf = xf[~np.isnan(xf)]
    kde = gaussian_kde(xf)
    return (np.min(xf), np.max(xf),  kde) #(np.linspace(np.min(xf, np.max(xf)))))


def get_fg_dep(cfgfile, dtg, var='airTemperatureAt2M'):
    dtgfg = dtg - datetime.timedelta(hours=3)
    conf = ConfigWrapper(cfgfile, dtg)
    domain = conf.config.get_value("domain").dict()
    areadef = sfx2areadef(
        domain["xlat0"],
        domain["xlon0"],
        domain["xlatcen"],
        domain["xloncen"],
        domain["nimax"],
        domain["njmax"],
        domain["xdx"]
        )
    crs = areadef.to_cartopy_crs()
    x, y = areadef.get_proj_coords()

    nens = conf.nens
    
    setup = Settings(conf.config.assim.dict()["control"])
    cv = setup.control_vector
    ov = setup.dict["observation_vector"]
    for obstype in ov:
        if "filepath" in ov[obstype]:
            gpath = ov[obstype]["filepath"]
            fpath = conf.platform.substitute(gpath, basetime=dtg)
            ov[obstype]["filepath"] = fpath
    
    hofxpath = conf.config.get_value("assim.general.hofxpath").replace("@RRR@", "@mbr@")
    hofxpath = conf.platform.substitute(hofxpath, basetime=conf.dtg - conf.fcint, validtime=conf.dtg)
    
    ov0 = {var: ov[var]}
    try:
        return prep_observations(
            ov0, 
            hofxpath, 
            nens=nens, 
            domain=domain, 
            read_ens=io.read_ens)
    except:
        return None


def ridge_plot(result, times, var, outdir="."):
    # Prepare figure
    ncycles = len(times)
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Overlap factor: smaller = more overlap
    overlap = 0.05
    max_height = 1
    colors = plt.cm.viridis(np.linspace(0, 1, len(result)))
    
    # First pass: find global max height
    global_max = 0
    for i in range(len(result)):
        if result[i] is not None:
            if result[i].obsVal is not None:
                residuals = result[i].obsVal - result[i].hofxEns.mean(axis=1)
                kde = gaussian_kde(residuals)
                y_vals = kde(np.linspace(min(residuals), max(residuals), 200))
                global_max = max(global_max, y_vals.max())
    print(f"Global max |innov| {var}: {global_max}")
    # Second pass: plot with normalized heights
    for i in range(len(result)):
        if result[i] is not None:
            if result[i].obsVal is not None:
                residuals = result[i].obsVal - result[i].hofxEns.mean(axis=1)
                kde = gaussian_kde(residuals)
                x_vals = np.linspace(min(residuals), max(residuals), 200)
                y_vals = kde(x_vals)
        
                y_vals = y_vals / global_max * max_height
                y_offset = (ncycles - i) * overlap
                ax.fill_between(x_vals, y_offset, y_vals + y_offset,
                                color=colors[i], alpha=0.7, edgecolor='k', linewidth=0.5)

    ax.set_yticks([(i+1) * overlap for i in range(len(result))])
    ax.set_yticklabels([times[i].strftime("%Y-%m-%d %H") for i in range(len(result))][::-1])
    ax.set_xlabel("O-F")
    ax.set_ylabel("Time")
    plt.tight_layout()
    plt.grid()
    plt.savefig(f"{outdir}/omf_ridge_{var}_{times[0].strftime('%Y%m%d')}.png")
    plt.close()
    #plt.show()


def process_date(dt, varname, inc=False, cfgfile=None):
    results = []
    conf = ConfigWrapper(cfgfile, dt)
    for mbr in range(conf.nens):
        conf = ConfigWrapper(cfgfile, dt)
        fgpattern = conf.platform.substitute(f"{conf.archive_dir}/SURFOUT.nc", dt-conf.fcint)
        fgpath = fgpattern.replace("@mbr@", f"{mbr:03d}")
        if inc:
            anpattern = conf.platform.substitute(f"{conf.archive_dir}/ANALYSIS.nc", dt)
            anpath = anpattern.replace("@mbr@", f"{mbr:03d}")
            results.append(dask.delayed(get_inc_ridge)(fgpath, anpath, [varname]))
        else:
            results.append(dask.delayed(get_ridge)(fgpath, [varname]))
    
    mins = [r[0] for r in results]
    maxs = [r[1] for r in results]
    global_min = dask.delayed(min)(mins)
    global_max = dask.delayed(max)(maxs)
    #print(f"Processing {dt} {varname} inc={inc}: min={global_min.compute():.2f}, max={global_max.compute():.2f}")
    @dask.delayed
    def evaluate_kde(kde, grid):
        try:
            return kde(grid)
        except TypeError:
            return np.zeros_like(grid)
    
    
    @dask.delayed
    def make_grid(minval, maxval, num=50):
        return np.linspace(minval, maxval, num)
    

    grid = make_grid(global_min, global_max)
    densities = [evaluate_kde(r[2], grid) for r in results]
    @dask.delayed
    def average_densities(densities):
        return sum(densities) / len(densities)
    
    avg_density = average_densities(densities)
    return grid, avg_density


def process_var(varname, times, inc=False, outdir=".", cfgfile=None):
    ncycles = len(times)
    results = [process_date(dt, varname, inc=inc, cfgfile=cfgfile) for dt in times]
    res = dask.compute(*results)
    colors = plt.cm.viridis(np.linspace(0, 1, len(res)))
    global_max = np.max([r[1].max() for r in res])
    minval = np.min([r[0].min() for r in res])
    maxval = np.max([r[0].max() for r in res])
    print(f"{'increments' if inc else 'state     '} for {varname}: min={minval:.2f}, max={maxval:.2f}")
    max_height = 1
    overlap = .1
    fig, ax =  plt.subplots()
    for i, ri in enumerate(res):
        x_vals = ri[0]
        y_vals = ri[1]
        y_vals = y_vals / global_max * max_height
        y_offset = (ncycles - i) * overlap
        ax.fill_between(x_vals, y_offset, y_vals + y_offset,
                        color=colors[i], alpha=0.7, edgecolor='k', linewidth=0.5)
    
    ax.set_yticks([(i+1) * overlap for i in range(len(res))])
    ax.set_yticklabels([times[i].strftime("%Y-%m-%d %H") for i in range(len(res))][::-1])
    ax.set_title(f"{varname}")
    plt.grid()
    plt.tight_layout()
    if inc:
        figname = f"{outdir}/{varname}_inc_ridge_{times[-1].strftime('%Y%m%d%H')}.png"
    else:
        figname = f"{outdir}/{varname}_state_ridge_{times[-1].strftime('%Y%m%d%H')}.png"
    plt.savefig(figname)
    plt.close()


def map_obs(obs, dt, crs, outdir="."):
    fig, ax = plt.subplots(subplot_kw=dict(projection=crs))
    ax.coastlines()
    sc = ax.scatter(
        obs.obsLon, 
        obs.obsLat, 
        c=obs.obsVal,
        s=20,
        cmap="RdBu_r",
        edgecolors="k",
        transform=ccrs.PlateCarree(),
        )
    plt.colorbar(sc, ax=ax, label=obs.obsVariable)
    ax.set_extent(crs.bounds, crs=crs)
    ax.gridlines(draw_labels=True)
    plt.title(f"Observations {obs.obsVariable} {dt.strftime('%Y-%m-%d %H')}")
    plt.savefig(f"{outdir}/obs_map_{obs.obsVariable}_{dt.strftime('%Y%m%d%H')}.png")
    plt.close()


def nobs_ts(result, times, var, outdir="."):
    nobs = [len(r.obsVal) if r is not None and r.obsVal is not None else 0 for r in result]
    plt.plot(times, nobs)
    plt.title(f"Number of {var} obs")
    plt.xlabel("Time")
    plt.ylabel("Nobs")
    timeaxis(plt.gca())
    plt.grid()
    plt.savefig(f"{outdir}/nobs_ts_{var}_{times[0].strftime('%Y%m%d')}.png")
    plt.close()


def omf_plots(stream, ncycles=8, output_dir="."):
    cfgfile = f"/home/nor3005/sfx_home/CARRA_Land_Pv2_stream_{stream}/CARRA_Land_Pv2_stream_{stream}.json"
    conf = ConfigWrapper(cfgfile)
    domain = conf.config.get_value("domain").dict()
    areadef = sfx2areadef(
        domain["xlat0"],
        domain["xlon0"],
        domain["xlatcen"],
        domain["xloncen"],
        domain["nimax"],
        domain["njmax"],
        domain["xdx"]
        )
    crs = areadef.to_cartopy_crs()
    for var in conf.config.get_value("assim.control.observation_vector").dict():
        if not conf.config.get_value(f"assim.control.observation_vector.{var}.assimilate"):
            break
        res = []
        times = []
        for dt in conf.dtg - ncycles*conf.fcint  + np.arange(ncycles)*conf.fcint:
            times.append(dt)
            obsi = dask.delayed(get_fg_dep)(cfgfile, dt, var=var)
            res.append(obsi)
        
        result = dask.compute(*res)
        ridge_plot(result, times, var, outdir=output_dir)
        nobs_ts(result, times, var, outdir=output_dir)
        if result[-1].obsVariable is not None:
            map_obs(result[-1], times[-1], crs, outdir=output_dir)
        else:
            map_obs(result[-2], times[-2], crs, outdir=output_dir)


def plot_increments(stream, ncycles=8, output_dir="."):
    cfgfile = f"/home/nor3005/sfx_home/CARRA_Land_Pv2_stream_{stream}/CARRA_Land_Pv2_stream_{stream}.json"
    conf = ConfigWrapper(cfgfile)
    domain = conf.config.get_value("domain").dict()
    areadef = sfx2areadef(
        domain["xlat0"],
        domain["xlon0"],
        domain["xlatcen"],
        domain["xloncen"],
        domain["nimax"],
        domain["njmax"],
        domain["xdx"]
        )
    crs = areadef.to_cartopy_crs()
    dtgfg = conf.dtg - datetime.timedelta(hours=3)
    times = [dt for dt in conf.dtg - ncycles*conf.fcint  + np.arange(ncycles)*conf.fcint]
  
    fgpattern = conf.platform.substitute(f"{conf.archive_dir}/SURFOUT.nc", dtgfg)
    fgpath = [fgpattern.replace("@mbr@", f"{mbr:03d}") for mbr in range(conf.nens)]
    anpattern = conf.platform.substitute(f"{conf.archive_dir}/ANALYSIS.nc", conf.dtg)
    anpath = [anpattern.replace("@mbr@", f"{mbr:03d}") for mbr in range(conf.nens)]
    ctrlpattern = conf.platform.substitute(f"{conf.archive_dir}/SURFOUT.nc", dtgfg).replace("@mbr@", "")
    ctrlpath = ctrlpattern
    
    setup = Settings(conf.config.assim.dict()["control"])
    cvs = ["WSN_VEG", "RSN_VEG", "HSN_VEG", "TG", "WG"]
    cvs = ["WSN_VEG5", "RSN_VEG5", "HSN_VEG1", "TG1", "TG3", "WG1", "WG3"]
    for varname in cvs:
        process_var(varname, times, inc=True, outdir=output_dir, cfgfile=cfgfile)
        process_var(varname, times, inc=False, outdir=output_dir, cfgfile=cfgfile)


def main(args):
    ncycles = args.ncycles
    stream = args.stream
    client = setup_cluster(ncycles)
    cfgfile = f"/home/nor3005/sfx_home/CARRA_Land_Pv2_stream_{stream}/CARRA_Land_Pv2_stream_{stream}.json"
    conf = ConfigWrapper(cfgfile)
    domain = conf.config.get_value("domain").dict()
    areadef = sfx2areadef(
        domain["xlat0"],
        domain["xlon0"],
        domain["xlatcen"],
        domain["xloncen"],
        domain["nimax"],
        domain["njmax"],
        domain["xdx"]
        )
    crs = areadef.to_cartopy_crs()
    plot_increments(stream, ncycles=ncycles, output_dir=args.output_dir)
    omf_plots(stream, ncycles=ncycles, output_dir=args.output_dir)
    client.close()
    return 0


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="Plot OMF statistics for a single time")
    parser.add_argument("--ncycles", type=int, default=8, help="Number of cycles to include in plots")
    parser.add_argument("--stream", type=int, default="2015", help="Stream year")
    parser.add_argument("-o", "--output-dir", default="./", help="output directory for figure files")
    return parser.parse_args()


if __name__ == "__main__":
    
    args = parse_args()
    main(args)