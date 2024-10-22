"""Forcing task."""
import json
import os

import yaml
from pysurfex.forcing import modify_forcing, run_time_loop, set_forcing_config

from ..logs import logger
from ..tasks.tasks import AbstractTask


class Forcing(AbstractTask):
    """Create forcing task."""

    def __init__(self, config):
        """Construct forcing task.

        Args:
            config (dict): Actual configuration dict

        """
        AbstractTask.__init__(self, config, "Forcing")
        self.var_name = self.config.get_value("task.var_name")
        try:
            #user_config = self.config.get_value("task.forcing_user_config")
            user_config = self.platform.substitute(self.config.get_value("forcing.user_config"))
        except AttributeError:
            user_config = None
        self.user_config = user_config

    def execute(self):
        """Execute the forcing task.

        Raises:
            NotImplementedError: _description_
        """
        kwargs = {}
        if self.user_config is not None:
            user_config = yaml.safe_load(
                open(self.user_config, mode="r", encoding="utf-8")
            )
            kwargs.update({"user_config": user_config})

        domain_json = self.geo.json
        domain_json.update({"nam_pgd_grid": {"cgrid": "CONF PROJ"}})
        with open(self.wdir + "/domain.json", mode="w", encoding="utf-8") as file_handler:
            json.dump(domain_json, file_handler, indent=2)
        kwargs.update({"domain": self.wdir + "/domain.json"})
        global_config = self.platform.get_system_value("config_yml")
        with open(global_config, mode="r", encoding="utf-8") as file_handler:
            global_config = yaml.safe_load(file_handler)
        kwargs.update({"config": global_config})

        kwargs.update({"dtg_start": self.dtg.strftime("%Y%m%d%H")})
        kwargs.update({"dtg_stop": (self.dtg + self.fcint).strftime("%Y%m%d%H")})

        forcing_dir = self.platform.get_system_value("forcing_dir")
        forcing_dir = self.platform.substitute(forcing_dir, basetime=self.dtg)
        os.makedirs(forcing_dir, exist_ok=True)

        output_format = self.config.get_value("SURFEX.IO.CFORCING_FILETYPE").lower()
        if output_format == "netcdf":
            output = forcing_dir + "/FORCING.nc"
        else:
            raise NotImplementedError(output_format)

        kwargs.update({"of": output})
        kwargs.update({"output_format": output_format})

        pattern = self.config.get_value("forcing.pattern").replace("@sfx_exp_data@", 
                    self.config.get_value("system.sfx_exp_data"))
        
        input_format = self.config.get_value("forcing.input_format")
        kwargs.update({"geo_input_file": self.config.get_value("forcing.input_geo_file")})
        zref = self.config.get_value("forcing.zref")
        zval = self.config.get_value("forcing.zval")
        uref = self.config.get_value("forcing.uref")
        uval = self.config.get_value("forcing.uval")
        zsoro_converter = self.config.get_value("forcing.zsoro_converter")
        qa_converter = self.config.get_value("forcing.qa_converter")
        dir_sw_converter = self.config.get_value("forcing.dir_sw_converter")
        sca_sw_converter = self.config.get_value("forcing.sca_sw_converter")
        sca_sw = self.config.get_value("forcing.sca_sw")
        lw_converter = self.config.get_value("forcing.lw_converter")
        co2 = self.config.get_value("forcing.co2")
        rain_converter = self.config.get_value("forcing.rain_converter")
        snow_converter = self.config.get_value("forcing.snow_converter")
        wind_converter = self.config.get_value("forcing.wind_converter")
        wind_dir_converter = self.config.get_value("forcing.winddir_converter")
        ps_converter = self.config.get_value("forcing.ps_converter")
        analysis = self.config.get_value("forcing.analysis")
        debug = self.config.get_value("forcing.debug")
        timestep = self.config.get_value("forcing.timestep")
        interpolation = self.config.get_value("forcing.interpolation")

        kwargs.update({"input_format": input_format})
        kwargs.update({"pattern": pattern})
        kwargs.update({"zref": zref})
        kwargs.update({"zval": zval})
        kwargs.update({"uref": uref})
        kwargs.update({"uval": uval})
        kwargs.update({"zsoro_converter": zsoro_converter})
        kwargs.update({"qa_converter": qa_converter})
        kwargs.update({"dir_sw_converter": dir_sw_converter})
        kwargs.update({"sca_sw_converter": sca_sw_converter})
        kwargs.update({"sca_sw": sca_sw})
        kwargs.update({"lw_converter": lw_converter})
        kwargs.update({"co2": co2})
        kwargs.update({"rain_converter": rain_converter})
        kwargs.update({"snow_converter": snow_converter})
        kwargs.update({"wind_converter": wind_converter})
        kwargs.update({"wind_dir_converter": wind_dir_converter})
        kwargs.update({"ps_converter": ps_converter})
        kwargs.update({"debug": debug})
        kwargs.update({"timestep": timestep})
        kwargs.update({"analysis": analysis})
        kwargs.update({"interpolation": interpolation})

        if os.path.exists(output):
            logger.info("Output already exists: {}", output)
        else:
            options, var_objs, att_objs = set_forcing_config(**kwargs)
            run_time_loop(options, var_objs, att_objs)
        # Modify forcing
        if self.config.get_value("forcing.modify_forcing"):
            dtg = self.dtg
            dtg_prev = dtg - self.fcint
            
            dtg_c = dtg.strftime('%Y%m%d%H')
            dtg_p = dtg_prev.strftime('%Y%m%d%H')

            logger.debug("modify forcing dtg={} dtg_prev={}", dtg, dtg_prev)
            forcing_dir = self.platform.get_system_value("forcing_dir")
            input_file = forcing_dir.replace( dtg_c, dtg_p )      
            input_file = input_file + "FORCING.nc"
            output_file = forcing_dir + "/FORCING.nc"
            time_step = -1
            variables = ["LWdown", "DIR_SWdown", "SCA_SWdown"]
            kwargs = {}

            kwargs.update({"input_file": input_file})
            kwargs.update({"output_file": output_file})
            kwargs.update({"time_step": time_step})
            kwargs.update({"variables": variables})
            if os.path.exists(output_file) and os.path.exists(input_file):
                modify_forcing(**kwargs)
            else:
                logger.info("Output or input is missing: {}", output_file)


class ModifyForcing(AbstractTask):
    """Create modify forcing task."""

    def __init__(self, config):
        """Construct modify forcing task.

        Args:
            config (ParsedObject): Parsed configuration

        """
        AbstractTask.__init__(self, config, "ModifyForcing")
        self.var_name = self.config.get_value("task.var_name")
        try:
            user_config = self.config.get_value("task.forcing_user_config")
        except AttributeError:
            user_config = None
        self.user_config = user_config

    def execute(self):
        """Execute the forcing task."""
        dtg = self.dtg
        dtg_prev = dtg - self.fcint
        
        dtg_c = dtg.strftime('%Y%m%d%H')
        dtg_p = dtg_prev.strftime('%Y%m%d%H')

        logger.debug("modify forcing dtg={} dtg_prev={}", dtg, dtg_prev)
        forcing_dir = self.platform.get_system_value("forcing_dir")
        input_file = forcing_dir.replace( dtg_c, dtg_p )      
        input_file = input_file + "FORCING.nc"
        output_file = forcing_dir + "/FORCING.nc"
        time_step = -1
        variables = ["LWdown", "DIR_SWdown", "SCA_SWdown"]
        kwargs = {}

        kwargs.update({"input_file": input_file})
        kwargs.update({"output_file": output_file})
        kwargs.update({"time_step": time_step})
        kwargs.update({"variables": variables})
        if os.path.exists(output_file) and os.path.exists(input_file):
            modify_forcing(**kwargs)
        else:
            logger.info("Output or input is missing: {}", output_file)
