"""Experiment classes and methods."""
import collections
import json
import os
import shutil

import tomlkit
from pysurfex.configuration import Configuration

from .config_parser import ParsedConfig
from .logs import GLOBAL_LOGLEVEL, logger
from .system import System

NO_DEFAULT_PROVIDED = object()


class ExpFromConfig:
    """Experiment class."""

    def __init__(self, merged_config, progress, json_schema=None):
        """Instaniate an object of the main experiment class.

        Args:
            merged_config (dict): Experiment configuration
            progress (dict): Updated time information
            json_schema (dict, optional): Validating schema. Defaults to None

        """
        logger.debug("Construct ExpFromConfig")
        merged_config = merged_config.copy()
        times = merged_config["general"]["times"]
        logger.info("Times before={}", times)
        epoch = "1970-01-01T00:00:00Z"
        keys = ["start", "end", "basetime", "basetime_pp", "validtime"]
        for key in keys:
            if key in progress:
                times.update({key: progress[key]})
            else:
                if key not in times:
                    times.update({key: epoch})
            logger.info("key={} value{}", key, times[key])
        if "end" not in times:
            times.update({"end": times["basetime"]})
        logger.info("Times after={}", times)
        merged_config["general"]["times"].update(times)
        merged_config["general"]["loglevel"] = GLOBAL_LOGLEVEL

        json_schema = None
        self.config = ParsedConfig.parse_obj(merged_config, json_schema=json_schema)

    def dump_json(self, filename, indent=None):
        """Dump a json file with configuration.

        Args:
            filename (str): Filename of json file to write
            indent (int): Indentation in filename

        """
        with open(filename, mode="w", encoding="UTF-8") as file_handler:
            json.dump(self.config.dict(), file_handler, indent=indent)


class Exp(ExpFromConfig):
    """Experiment class."""

    def __init__(
        self,
        exp_dependencies,
        merged_config,
        system,
        system_file_paths,
        env_server,
        env_submit,
        progress,
        stream=None,
        json_schema=None,
    ):
        """Instaniate an object of the main experiment class.

        Args:
            exp_dependencies (dict):  Eperiment dependencies
            merged_config (dict): Experiment configuration
            system (dict): System settings
            system_file_paths (dict): Platform path settings
            env_server (dict): Server settings
            env_submit (dict): Submission settings
            progress (dict): Date/time settings
            stream (str, optional): Stream identifier. Defaults to None.
            json_schema (dict, optional): Validating schema. Defaults to None

        """
        logger.debug("Construct Exp")

        # Date/time
        times = merged_config["general"]["times"]
        epoch = "1970-01-01T00:00:00Z"
        keys = ["start", "end", "basetime", "basetime_pp", "validtime"]
        for key in keys:
            if key in progress:
                times.update({key: progress[key]})
            else:
                if key not in times:
                    times.update({key: epoch})
        if "validtime" not in progress:
            times.update({"validtime": times["basetime"]})
        if "end" not in times:
            times.update({"end": times["basetime"]})
        merged_config["general"]["times"].update(times)
        logger.info("Progress: {}", progress)

        case = exp_dependencies.get("exp_name")
        host = "0"

        troika_config = exp_dependencies["config"]["other_files"]["troika_config.yml"]
        troika = None
        try:
            troika = system.get_var("troika", "0")
        except KeyError:
            try:
                troika = shutil.which("troika")
            except RuntimeError:
                logger.warning("Troika not found!")

        sfx_config = Configuration(merged_config)

        sfx_data = system.get_var("sfx_exp_data", host)
        exp_dir = exp_dependencies.get("exp_dir")
        if exp_dir is None:
            exp_dir = sfx_data
        platform_name = exp_dependencies.get("platform")
        if "name" not in system_file_paths:
            system_file_paths.update({"name": platform_name})
        update = {
            "general": {
                "stream": stream,
                "case": case,
                "keep_workdirs": False,
                "times": times,
            },
            "system": {
                "joboutdir": system.get_var("joboutdir", host),
                "wrk": sfx_data + "/@YYYY@@MM@@DD@_@HH@/@RRR@/",
                "bin_dir": sfx_data + "/lib/offline/exe/",
                "climdir": sfx_data + "/climate/",
                "archive_dir": sfx_data + "/archive/@YYYY@/@MM@/@DD@/@HH@/@RRR@/",
                "extrarch_dir": sfx_data + "/archive/extract/",
                "forcing_dir": sfx_data + "/forcing/@YYYY@@MM@@DD@@HH@/@RRR@/",
                "obs_dir": f"{sfx_data}/archive/observations/@YYYY@/@MM@/@DD@/@HH@/",
                "namelist_defs": exp_dependencies.get("namelist_defs"),
                "binary_input_files": exp_dependencies.get("binary_input_files"),
                "exp_dir": exp_dir,
                "sfx_exp_lib": system.get_var("sfx_exp_lib", host),
                "sfx_exp_data": system.get_var("sfx_exp_data", host),
                "pysurfex": exp_dependencies.get("pysurfex"),
                "pysurfex_experiment": exp_dependencies.get("pysurfex_experiment"),
                "first_guess_yml": exp_dependencies["config"]["other_files"][
                    "first_guess.yml"
                ],
                "config_yml": exp_dependencies["config"]["other_files"]["config.yml"],
                "surfex_config": system.get_var("surfex_config", host),
                "rsync": system.get_var("rsync", host),
            },
            "platform": system_file_paths,
            "compile": {"offline_source": exp_dependencies.get("offline_source")},
            "scheduler": env_server,
            "submission": env_submit,
            "troika": {"command": troika, "config": troika_config},
            "SURFEX": sfx_config.settings["SURFEX"],
        }

        # Initialize task settings
        if "task" not in merged_config:
            merged_config.update({"task": {}})
        task = {}
        task_attrs = ["wrapper", "var_name", "args"]
        for att in task_attrs:
            if att not in merged_config["task"]:
                if att == "args":
                    val = {}
                else:
                    val = ""
                task.update({att: val})
            else:
                task.update({att: merged_config["task"][att]})
        merged_config["task"].update(task)
        config = ParsedConfig.parse_obj(merged_config, json_schema=json_schema)
        config = config.copy(update=update)
        ExpFromConfig.__init__(self, config.dict(), progress, json_schema=json_schema)


class ExpFromFiles(Exp):
    """Generate Exp object from existing files. Use config files from a setup."""

    def __init__(
        self,
        exp_dependencies,
        stream=None,
        config_settings=None,
        progress=None,
        json_schema=None,
    ):
        """Construct an Exp object from files.

        Args:
            exp_dependencies (dict): Exp dependencies
            stream(str, optional): Stream identifier
            config_settings(dict): Possible input config settings
            progress(dict, optional): Time/date information to update.
            json_schema (dict, optional): Validating schema. Defaults to None

        Raises:
            FileNotFoundError: If host file(s) not found
            KeyError: Key not found

        """
        logger.debug("Construct ExpFromFiles")
        logger.debug("Experiment dependencies: {}", exp_dependencies)

        # System
        exp_name = exp_dependencies.get("exp_name")
        env_system = exp_dependencies.get("env_system")
        if os.path.exists(env_system):
            system = System(self.toml_load(env_system), exp_name)
        else:
            raise FileNotFoundError("System settings not found " + env_system)

        # System file path
        input_paths = exp_dependencies.get("input_paths")
        if os.path.exists(input_paths):
            with open(input_paths, mode="r", encoding="utf-8") as input_paths:
                system_file_paths = json.load(input_paths)
        else:
            raise FileNotFoundError("System setting input paths not found " + input_paths)

        # Submission settings
        env_submit = exp_dependencies.get("env_submit")
        if os.path.exists(env_submit):
            with open(env_submit, mode="r", encoding="utf-8") as env_submit:
                env_submit = json.load(env_submit)
        else:
            raise FileNotFoundError("Submision settings not found " + env_submit)

        # Scheduler settings
        env_server = exp_dependencies.get("env_server")
        if os.path.exists(env_server):
            with open(env_server, mode="r", encoding="utf-8") as env_server:
                env_server = json.load(env_server)
        else:
            raise FileNotFoundError("Server settings missing " + env_server)

        # Date/time settings
        if progress is None:
            progress = {}

        # Configuration
        if config_settings is None:
            config_files_dict = ExpFromFiles.get_config_files(
                exp_dependencies["config"]["config_files"],
                exp_dependencies["config"]["blocks"],
            )
            config_settings = self.merge_dict_from_config_dicts(config_files_dict)

        domain_file = exp_dependencies.get("domain_file")
        domain = config_settings["domain"]
        domain_name = domain["name"]
        with open(domain_file, mode="r", encoding="utf-8") as fhandler:
            domain_props = json.load(fhandler)
            if domain_name in domain_props:
                fill_domain = domain_props[domain_name]
                try:
                    gsize = fill_domain["GSIZE"]
                    lat0 = fill_domain["LAT0"]
                    latc = fill_domain["LATC"]
                    lon0 = fill_domain["LON0"]
                    lonc = fill_domain["LONC"]
                    nlat = fill_domain["NLAT"]
                    nlon = fill_domain["NLON"]
                    if "EZONE" in fill_domain:
                        ezone = fill_domain["EZONE"]
                    else:
                        ezone = 11
                except KeyError as exc:
                    raise KeyError from exc

                domain_from_file = {
                    "name": domain_name,
                    "nimax": nlon,
                    "njmax": nlat,
                    "xloncen": lonc,
                    "xlatcen": latc,
                    "xdx": gsize,
                    "xdy": gsize,
                    "ilone": ezone,
                    "ilate": ezone,
                    "xlon0": lon0,
                    "xlat0": lat0,
                }
                domain = self.merge_dict(domain_from_file, domain)
                config_settings.update({"domain": domain})
            else:
                raise KeyError("Domain definition not found")

        Exp.__init__(
            self,
            exp_dependencies,
            config_settings,
            system,
            system_file_paths,
            env_server,
            env_submit,
            progress,
            stream=stream,
            json_schema=json_schema,
        )

    @staticmethod
    def update_domain_from_json_file(domain_file, keep_domain):
        """Update domain info from a json file with HM domains.

        Args:
            domain_file (str): File name
            keep_domain (str): Original domain information to keep

        Raises:
            KeyError: Key not found

        Returns:
            dict: Updated domain
        """
        with open(domain_file, mode="r", encoding="utf-8") as fhandler:
            domain_props = json.load(fhandler)
            domain_name = keep_domain["name"]
            if domain_name in domain_props:
                fill_domain = domain_props[domain_name]
                return ExpFromFiles.update_domain(keep_domain, fill_domain, hm_mode=True)
            else:
                raise KeyError("Domain definition not found")

    @staticmethod
    def update_domain(keep_doman, fill_domain, hm_mode=True):
        """Update domain information.

        Args:
            keep_doman (dict): Domain properties to keep
            fill_domain (dict): Domain properties to fill in
            hm_mode (bool, optional): Properties are in HM syntax. Defaults to True.

        Raises:
            KeyError: Key not found

        Returns:
            dict: Updated domain
        """
        if hm_mode:
            try:
                gsize = fill_domain["GSIZE"]
                lat0 = fill_domain["LAT0"]
                latc = fill_domain["LATC"]
                lon0 = fill_domain["LON0"]
                lonc = fill_domain["LONC"]
                nlat = fill_domain["NLAT"]
                nlon = fill_domain["NLON"]
                if "EZONE" in fill_domain:
                    ezone = fill_domain["EZONE"]
                else:
                    ezone = 11
            except KeyError as exc:
                raise KeyError from exc

            fill_domain = {
                "nimax": nlon,
                "njmax": nlat,
                "xloncen": lonc,
                "xlatcen": latc,
                "xdx": gsize,
                "xdy": gsize,
                "ilone": ezone,
                "ilate": ezone,
                "xlon0": lon0,
                "xlat0": lat0,
            }
        keep_doman = ExpFromFiles.merge_dict(fill_domain, keep_doman)
        return keep_doman

    @staticmethod
    def toml_load(fname):
        """Load from toml file.

        Using tomlkit to preserve stucture

        Args:
            fname (str): Filename

        Returns:
            _type_: _description_

        """
        f_h = open(fname, "r", encoding="utf-8")
        res = tomlkit.parse(f_h.read())
        f_h.close()
        return res

    @staticmethod
    def toml_dump(to_dump, fname):
        """Dump toml to file.

        Using tomlkit to preserve stucture

        Args:
            to_dump (_type_): _description_
            fname (str): Filename

        """
        f_h = open(fname, mode="w", encoding="utf-8")
        f_h.write(tomlkit.dumps(to_dump))
        f_h.close()

    @staticmethod
    def merge_dict_from_config_dicts(config_files):
        """Merge the settings in a config dict with config files.

        Args:
            config_files (dict): Config files dictionaries inside a
                                 dict with config file names

        Returns:
            dict: Merged settings as a config dict with config files

        """
        logger.debug("config_files: {}", str(config_files))
        merged_env = {}
        for fff in config_files:
            modification = config_files[fff]["toml"]
            merged_env = ExpFromFiles.merge_dict(merged_env, modification)
        return merged_env

    @staticmethod
    def deep_update(source, overrides):
        """Update a nested dictionary or similar mapping.

        Modify ``source`` in place.

        Args:
            source (dict): Source
            overrides (dict): Updates

        Returns:
            dict: Updated dictionary

        """
        for key, value in overrides.items():
            if isinstance(value, collections.abc.Mapping) and value:
                returned = ExpFromFiles.deep_update(source.get(key, {}), value)
                source[key] = returned
            else:
                override = overrides[key]

                source[key] = override

        return source

    @staticmethod
    def merge_dict(old_env, mods):
        """Merge the dicts from toml by a deep update.

        Args:
            old_env (dict): Source dictionary
            mods (dict): Modifications

        Returns:
            dict: Merged dict

        """
        return ExpFromFiles.deep_update(old_env, mods)

    @staticmethod
    def get_config_files(config_files_in, blocks):
        """Get the config files.

        Args:
            config_files_in (dict): config file and path
            blocks (dict): Blocks

        Raises:
            FileNotFoundError: Did not find config file.

        Returns:
            dict: returns a config files dict

        """
        # Check existence of needed config files
        config_files = {}
        for ftype, fname in config_files_in.items():
            if os.path.exists(fname):
                toml_dict = ExpFromFiles.toml_load(fname)
            else:
                raise FileNotFoundError("No config file found for " + fname)
            config_files.update(
                {ftype: {"toml": toml_dict, "blocks": blocks[ftype]["blocks"]}}
            )
        return config_files

    @staticmethod
    def merge_config_files_dict(
        config_files,
        configuration=None,
        testbed_configuration=None,
        user_settings=None,
    ):
        """Merge config files dicts.

        Args:
            config_files (dict): Dictionary with configuration and files
            configuration (str, optional): Configuration name. Defaults to None.
            testbed_configuration (str, optional): Testbed name. Defaults to None.
            user_settings (dict, optional): User input. Defaults to None.

        Raises:
            TypeError: Settings should be a dict

        Returns:
            dict: Merged config files dicts.

        """
        logger.debug("Merge config files")
        for this_config_file in config_files:
            logger.debug("This config file {}", this_config_file)
            hm_exp = config_files[this_config_file]["toml"].copy()

            block_config = tomlkit.document()
            if configuration is not None:
                fff = this_config_file.split("/")[-1]
                if fff == "config_exp.toml":
                    block_config.add(
                        tomlkit.comment("\n# SURFEX experiment configuration file\n#")
                    )

            for block in config_files[this_config_file]["blocks"]:
                block_config.update({block: hm_exp[block]})
                if configuration is not None:
                    if block in configuration:
                        merged_config = ExpFromFiles.merge_dict(
                            hm_exp[block], configuration[block]
                        )
                        logger.info("Merged: {} {}", block, str(configuration[block]))
                    else:
                        merged_config = hm_exp[block]

                    block_config.update({block: merged_config})

                if testbed_configuration is not None:
                    if block in testbed_configuration:
                        hm_testbed = ExpFromFiles.merge_dict(
                            block_config[block], testbed_configuration[block]
                        )
                    else:
                        hm_testbed = block_config[block]
                    block_config.update({block: hm_testbed})

                if user_settings is not None:
                    if not isinstance(user_settings, dict):
                        raise TypeError("User settings should be a dict here!")
                    if block in user_settings:
                        logger.info("Merge user settings in block {}", block)
                        user = ExpFromFiles.merge_dict(
                            block_config[block], user_settings[block]
                        )
                        block_config.update({block: user})

            logger.debug("block config {}", block_config)
            config_files.update({this_config_file: {"toml": block_config}})
        return config_files

    @staticmethod
    def merge_to_toml_config_files(
        config_files,
        wdir,
        configuration=None,
        testbed_configuration=None,
        user_settings=None,
        write_config_files=True,
    ):
        """Merge to toml config files.

        Args:
            config_files (dict): Dictionary with configuration and files
            wdir (str): Experiment directory
            configuration (str, optional): Configuration name. Defaults to None.
            testbed_configuration (str, optional): Testbed name. Defaults to None.
            user_settings (dict, optional): User input. Defaults to None.
            write_config_files (bool, optional): Write updated config files.
                                                 Defaults to True.

        Returns:
            config_files (dict): Dictionary with configuration and files

        """
        config_files = config_files.copy()
        config_files = ExpFromFiles.merge_config_files_dict(
            config_files,
            configuration=configuration,
            testbed_configuration=testbed_configuration,
            user_settings=user_settings,
        )

        for fname in config_files:
            this_config_file = f"config/{fname}"

            block_config = config_files[fname]["toml"]
            if write_config_files:
                f_out = f"{wdir}/{this_config_file}"
                dirname = os.path.dirname(f_out)
                dirs = dirname.split("/")
                if len(dirs) > 1:
                    pth = "/"
                    for dname in dirs[1:]:
                        pth = pth + str(dname)
                        os.makedirs(pth, exist_ok=True)
                        pth = pth + "/"
                f_out = open(f_out, mode="w", encoding="utf-8")
                f_out.write(tomlkit.dumps(block_config))
                f_out.close()
        return config_files

    @staticmethod
    def setup_files(
        wdir,
        exp_name,
        host,
        pysurfex,
        pysurfex_experiment,
        offline_source=None,
        namelist_defs=None,
        binary_input_files=None,
    ):
        """Set up the files for an experiment.

        Args:
            wdir (str): Experiment directory
            exp_name (str): Experiment name
            host (str): Host label
            pysurfex (str): Pysurfex path
            pysurfex_experiment (str): Pysurfex experiment script system path
            offline_source (str, optional): Offline source code. Defaults to None.
            namelist_defs (str, optional): Namelist directory. Defaults to None.
            binary_input_files (str, optional): Binary input files. Defaults to None.

        Raises:
            FileNotFoundError: System files not found

        Returns:
            exp_dependencies(dict): Experiment dependencies from setup.

        """
        exp_dependencies = {}
        logger.info("Setting up for host {}", host)

        # Create needed system files
        if host is None:
            logger.warning("No host specified")
        else:
            system_files = {}
            system_files.update(
                {
                    "env_system": "config/system/" + host + ".toml",
                    "env": "config/env/" + host + ".py",
                    "env_submit": "config/submit/" + host + ".json",
                    "env_server": "config/server/" + host + ".json",
                    "input_paths": "config/input_paths/" + host + ".json",
                }
            )

            for key, fname in system_files.items():
                gname = f"{pysurfex_experiment}/data/{fname}"
                found = False
                if wdir is not None:
                    lname = f"{wdir}/{fname}"
                    if os.path.exists(lname):
                        logger.info("Using local host specific file {} as {}", lname, key)
                        exp_dependencies.update({key: fname})
                        found = True
                if not found:
                    if os.path.exists(gname):
                        logger.info(
                            "Using general host specific file {} as {}", gname, key
                        )
                        exp_dependencies.update({key: gname})
                    else:
                        raise FileNotFoundError(
                            f"No host file found for lname={lname} or gname={gname}"
                        )

        fname = "config/domains/Harmonie_domains.json"
        gname = f"{pysurfex_experiment}/data/{fname}"
        found = False
        if wdir is not None:
            lname = f"{wdir}/{fname}"
            if os.path.exists(lname):
                logger.info("Using local host specific domain file {}", lname)
                exp_dependencies.update({"domain_file": lname})
                found = True
        if not found:
            if os.path.exists(gname):
                logger.info("Using general host specific domain file {}", gname)
                exp_dependencies.update({"domain_file": gname})

        # Check existence of needed config files
        config = None
        gconfig = f"{pysurfex_experiment}/data/config/config.toml"
        if wdir is not None:
            lconfig = f"{wdir}/config/config.toml"
            if os.path.exists(lconfig):
                logger.info("Local config definition {}", lconfig)
                config = lconfig
        if config is None:
            if os.path.exists(gconfig):
                logger.info("Global config definition {}", gconfig)
                config = gconfig
            else:
                raise FileNotFoundError

        c_files = ExpFromFiles.toml_load(config)["config_files"]
        blocks = ExpFromFiles.toml_load(config)
        pysurfex_files = ["config_exp_surfex.toml", "first_guess.yml", "config.yml"]
        c_files = c_files + ["config_exp_surfex.toml"]
        logger.info("Set up toml config files {}", str(c_files))
        cc_files = {}
        for c_f in c_files:
            gname = f"{pysurfex_experiment}/data/config/{c_f}"
            if c_f in pysurfex_files:
                gname = f"{pysurfex}/pysurfex/cfg/{c_f}"
            found = False
            if wdir is not None:
                lname = f"{wdir}/config/{c_f}"
                if os.path.exists(lname):
                    logger.info("Using local toml config file {}", lname)
                    cc_files.update({c_f: lname})
                    found = True
            if not found:
                if os.path.exists(gname):
                    logger.info("Using general toml config file {}", gname)
                    cc_files.update({c_f: gname})
                else:
                    raise FileNotFoundError(
                        f"No toml config file found for lname={lname} or gname={gname}"
                    )

        logger.info("Set up other config files {}", str(c_files))
        other_files = {}
        for c_f in ["first_guess.yml", "config.yml", "troika_config.yml"]:
            gname = f"{pysurfex_experiment}/data/config/{c_f}"
            if c_f in pysurfex_files:
                gname = f"{pysurfex}/pysurfex/cfg/{c_f}"
            found = False
            if wdir is not None:
                lname = f"{wdir}/config/{c_f}"
                if os.path.exists(lname):
                    logger.info("Using local extra file {}", lname)
                    other_files.update({c_f: lname})
                    found = True
            if not found:
                if os.path.exists(gname):
                    logger.info("Using general extra file {}", gname)
                    other_files.update({c_f: gname})
                else:
                    raise FileNotFoundError(
                        f"No extra file found for lname={lname} or gname={gname}"
                    )

        exp_dependencies.update(
            {
                "config": {
                    "config_files": cc_files,
                    "other_files": other_files,
                    "blocks": blocks,
                }
            }
        )

        if namelist_defs is None:
            namelist_defs = f"{pysurfex_experiment}/data/nam/surfex_namelists.yml"
            logger.info("Using default namelist directory {}", namelist_defs)

        if binary_input_files is None:
            binary_input_files = (
                f"{pysurfex_experiment}/data/input/binary_input_data.json"
            )
            logger.info("Using default binary input {}", binary_input_files)

        exp_dependencies.update(
            {
                "platform": host,
                "exp_dir": wdir,
                "exp_name": exp_name,
                "pysurfex_experiment": pysurfex_experiment,
                "pysurfex": pysurfex,
                "offline_source": offline_source,
                "namelist_defs": namelist_defs,
                "binary_input_files": binary_input_files,
            }
        )
        return exp_dependencies

    @staticmethod
    def write_exp_config(
        exp_dependencies,
        configuration=None,
        configuration_file=None,
        write_config_files=True,
    ):
        """Write the exp config to files.

        Args:
            exp_dependencies (dict): Experiment dependencies
            configuration (str, optional): Configuration name. Defaults to None.
            configuration_file (str, optional): Configuration filename with settings.
                                                Defaults to None.
            write_config_files (bool, optional): Write updated config files.
                                                 Defaults to True.

        Raises:
            FileNotFoundError: Config files not found

        Returns:
            config_files (dict): Config files dict with settings and file names

        """
        wdir = exp_dependencies["exp_dir"]
        pysurfex_experiment = exp_dependencies["pysurfex_experiment"]
        other_files = exp_dependencies["config"]["other_files"]
        # First priority is config
        if configuration is not None:
            logger.info("Using configuration {}", configuration)
            gconf = f"{pysurfex_experiment}/data/config/configurations/{configuration.lower()}.toml"
            found = False
            if wdir is not None:
                lconf = f"{wdir}/data/config/configurations/{configuration.lower()}.toml"
                if os.path.exists(lconf):
                    logger.info("Using local configuration file {}", lconf)
                    configuration = ExpFromFiles.toml_load(lconf)
                    found = True
            if not found:
                if os.path.exists(gconf):
                    logger.info("Using general configuration file {}", gconf)
                    configuration = ExpFromFiles.toml_load(gconf)
                else:
                    raise FileNotFoundError

        # Second check for configuration file
        if configuration is None:
            if configuration_file is not None:
                if os.path.exists(configuration_file):
                    logger.info("Using configuration from file {}", configuration_file)
                    configuration = ExpFromFiles.toml_load(configuration_file)
                else:
                    raise FileNotFoundError(configuration_file)

        # Load config files
        config_files = ExpFromFiles.get_config_files(
            exp_dependencies["config"]["config_files"],
            exp_dependencies["config"]["blocks"],
        )
        # Merge dicts and write to toml config files
        ExpFromFiles.merge_to_toml_config_files(
            config_files,
            wdir,
            configuration=configuration,
            write_config_files=write_config_files,
        )

        logger.debug("Configuration is: {}", configuration)
        if wdir is not None and write_config_files:
            for ename, extra_file in other_files.items():
                fname = f"{wdir}/config/{ename}"
                if not os.path.exists(fname):
                    logger.info("Copy {} to {}", extra_file, fname)
                    shutil.copy(extra_file, fname)
                else:
                    logger.info("File {} exists", fname)
        return config_files

    @staticmethod
    def dump_exp_dependencies(exp_dependencies, exp_dependencies_file, indent=2):
        """Dump an experimet dependency file.

        Args:
            exp_dependencies (dict): Experiment dependencies
            exp_dependencies_file (str): Filename to dump to
            indent (int, optional): Intendation. Defaults to 2.
        """
        json.dump(
            exp_dependencies,
            open(exp_dependencies_file, mode="w", encoding="utf-8"),
            indent=indent,
        )


class ExpFromFilesDep(ExpFromFiles):
    """Generate Exp object from existing files. Use config files from a setup."""

    def __init__(
        self,
        exp_dependencies,
        stream=None,
        config_settings=None,
        progress=None,
        json_schema=None,
    ):
        """Construct an Exp object from files.

        Args:
            exp_dependencies (str): File with exp dependencies
            stream (str): Stream identifier
            config_settings (dict): Possible input config setting to
            progress (dict, optional): Updated date/time. Default to None
            json_schema (dict, optional): Validating schema. Defaults to None

        """
        logger.debug("Construct ExpFromFilesDep")
        ExpFromFiles.__init__(
            self,
            exp_dependencies,
            stream=stream,
            config_settings=config_settings,
            progress=progress,
            json_schema=json_schema,
        )


class ExpFromFilesDepFile(ExpFromFiles):
    """Generate Exp object from existing files. Use config files from a setup."""

    def __init__(
        self,
        exp_dependencies_file,
        config_settings=None,
        stream=None,
        progress=None,
        json_schema=None,
    ):
        """Construct an Exp object from files.

        Args:
            exp_dependencies_file (str): File with exp dependencies
            stream (str): Stream identifier
            config_settings (dict): Possible input config setting to
            progress (dict, optional): Updated date/time. Default to None
            json_schema (dict, optional): Validating schema. Defaults to None

        Raises:
            FileNotFoundError: If file is not found

        """
        logger.debug("Construct ExpFromFilesDepFile")
        if os.path.exists(exp_dependencies_file):
            with open(
                exp_dependencies_file, mode="r", encoding="utf-8"
            ) as exp_dependencies_file:
                exp_dependencies = json.load(exp_dependencies_file)
                ExpFromFiles.__init__(
                    self,
                    exp_dependencies,
                    stream=stream,
                    config_settings=config_settings,
                    progress=progress,
                    json_schema=json_schema,
                )
        else:
            raise FileNotFoundError(
                f"Experiment dependencies not found {exp_dependencies_file}"
            )
