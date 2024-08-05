"""Tasks running surfex binaries."""
import json
import os

import yaml
from pysurfex.binary_input import InputDataFromNamelist, JsonOutputData
from pysurfex.configuration import Configuration
from pysurfex.file import PGDFile, PREPFile, SURFFile
from pysurfex.namelist import NamelistGenerator
from pysurfex.platform_deps import SystemFilePaths
from pysurfex.run import BatchJob, PerturbedOffline, SURFEXBinary

from ..logs import logger
from ..tasks.tasks import AbstractTask


class SurfexBinaryTask(AbstractTask):
    """Main surfex binary task executing all tasks.

    Args:
        AbstractTask (object): Inheritance of base task class
    """

    def __init__(self, config, name=None, mode=None):
        """Construct a surfex binary task.

        Args:
            config (ParsedConfig): Parsed config
            name (str): Task name
            mode (str): mode
        """
        if name is None:
            name = self.__class__.__name__
        AbstractTask.__init__(self, config, name)

        self.mode = mode
        self.need_pgd = True
        self.need_prep = True
        self.pgd = False
        self.prep = False
        self.perturbed = False
        self.soda = False
        self.namelist = None
        # SURFEX config added to general config
        cfg = self.config.get_value("SURFEX").dict()
        sfx_config = {"SURFEX": cfg}
        self.sfx_config = Configuration(sfx_config)

        # TODO get all needed paths
        system_paths = self.config.get_value("system").dict()
        platform_paths = self.config.get_value("platform").dict()
        exp_file_paths = {}
        for key, val in system_paths.items():
            exp_file_paths.update({key: val})
        for key, val in platform_paths.items():
            exp_file_paths.update({key: val})
        obs_dir = self.platform.get_system_value("obs_dir")
        # To sub EEE/RRR
        obs_dir = self.platform.substitute(obs_dir)

        logger.debug("exp_file_paths: {}", exp_file_paths)
        self.exp_file_paths = SystemFilePaths(exp_file_paths)

        kwargs = self.config.get_value("task.args").dict()
        logger.debug("kwargs: {}", kwargs)
        print_namelist = kwargs.get("print_namelist")
        if print_namelist is None:
            print_namelist = True

        self.print_namelist = print_namelist
        check_existence = kwargs.get("check_existence")
        if check_existence is None:
            check_existence = True
        self.check_existence = check_existence
        logger.debug("check_existence {}", check_existence)

        force = kwargs.get("force")
        if force is None:
            force = False
        self.force = force

        pert = kwargs.get("pert")
        if pert is not None:
            pert = int(pert)
        self.pert = pert
        logger.debug("Pert {}", self.pert)
        negpert = False
        pert_sign = kwargs.get("pert_sign")
        if pert_sign is not None and pert_sign == "neg":
            negpert = True
        self.negpert = negpert
        self.ivar = kwargs.get("ivar")

        xyz = ".exe"
        libdir = self.platform.get_system_value("sfx_exp_lib")
        xyz_file = libdir + "/xyz"
        if os.path.isfile(xyz_file):
            with open(xyz_file, mode="r", encoding="utf-8") as zyz_fh:
                xyz = zyz_fh.read().rstrip()
        else:
            logger.info("{} not found. Assume XYZ={}", xyz_file, xyz)
        self.xyz = xyz

    def execute(self):
        """Execute task."""
        logger.debug("Using empty class execute")

    def execute_binary(
        self,
        binary,
        output,
        pgd_file_path=None,
        prep_file_path=None,
        archive_data=None,
        prep_file=None,
        prep_pgdfile=None,
    ):
        """Execute the surfex binary.

        Args:
            binary (str): Full path to binary
            output (str): Full path to output file
            pgd_file_path (str, optional): _description_. Defaults to None.
            prep_file_path (str, optional): _description_. Defaults to None.
            archive_data (surfex.OutputDataFromSurfexBinaries, optional): A mapping of produced
                files and where to archive them. Defaults to None.
            prep_file (_type_, optional): _description_. Defaults to None.
            prep_pgdfile (_type_, optional): _description_. Defaults to None.

        """
        rte = os.environ

        if self.mode == "pgd":
            self.pgd = True
            self.need_pgd = False
            self.need_prep = False
        elif self.mode == "prep":
            self.prep = True
            self.need_prep = False
        elif self.mode == "offline":
            pass
        elif self.mode == "soda":
            self.soda = True
        elif self.mode == "perturbed":
            self.perturbed = True

        self.sfx_config.update_setting("SURFEX#PREP#FILE", prep_file)
        self.sfx_config.update_setting("SURFEX#PREP#FILEPGD", prep_pgdfile)
        if self.dtg is not None:
            self.sfx_config.update_setting("SURFEX#SODA#HH", f"{self.dtg.hour:02d}")
            self.sfx_config.update_setting("SURFEX#PREP#NDAY", self.dtg.day)
            self.sfx_config.update_setting("SURFEX#PREP#NMONTH", self.dtg.month)
            self.sfx_config.update_setting("SURFEX#PREP#NYEAR", self.dtg.year)
            xtime = (
                self.dtg - self.dtg.replace(hour=0, second=0, microsecond=0)
            ).total_seconds()
            self.sfx_config.update_setting("SURFEX#PREP#XTIME", xtime)
        if self.perturbed:
            nvar = 0
            for __, val in enumerate(
                self.sfx_config.get_setting("SURFEX#ASSIM#ISBA#EKF#NNCV")
            ):
                if val == 1:
                    nvar += 1
            self.sfx_config.update_setting("SURFEX#SODA#NVAR", nvar)

        # TODO file handling should be in pysurfex
        with open(self.namelist_defs, mode="r", encoding="utf-8") as fhandler:
            definitions = yaml.safe_load(fhandler)
        namelist = NamelistGenerator(self.mode, self.sfx_config, definitions)
        settings = namelist.get_namelist()

        if self.mode == "pgd":
            settings = self.geo.update_namelist(settings)

        with open(self.binary_input_files, mode="r", encoding="utf-8") as fhandler:
            input_data = json.load(fhandler)

        input_data = InputDataFromNamelist(
            settings,
            input_data,
            self.mode,
            self.exp_file_paths,
            basetime=self.dtg,
            validtime=self.dtg,
        )

        batch = BatchJob(rte, wrapper=self.wrapper)

        # Create input
        filetype = settings["nam_io_offline"]["csurf_filetype"]
        pgdfile = settings["nam_io_offline"]["cpgdfile"]
        prepfile = settings["nam_io_offline"]["cprepfile"]
        surffile = settings["nam_io_offline"]["csurffile"]
        lfagmap = False
        if "lfagmap" in settings["nam_io_offline"]:
            lfagmap = settings["nam_io_offline"]["lfagmap"]

        if self.need_pgd:
            pgdfile = PGDFile(
                filetype, pgdfile, input_file=pgd_file_path, lfagmap=lfagmap
            )

        if self.need_prep:
            prepfile = PREPFile(
                filetype, prepfile, input_file=prep_file_path, lfagmap=lfagmap
            )

        if self.need_prep and self.need_pgd:
            surffile = SURFFile(filetype, surffile, archive_file=output, lfagmap=lfagmap)
        else:
            surffile = None

        if self.perturbed:
            if self.pert > 0:
                PerturbedOffline(
                    binary,
                    batch,
                    prepfile,
                    self.ivar,
                    settings,
                    input_data,
                    negpert=self.negpert,
                    pgdfile=pgdfile,
                    surfout=surffile,
                    archive_data=archive_data,
                    print_namelist=self.print_namelist,
                )
            else:
                SURFEXBinary(
                    binary,
                    batch,
                    prepfile,
                    settings,
                    input_data,
                    pgdfile=pgdfile,
                    surfout=surffile,
                    archive_data=archive_data,
                    print_namelist=self.print_namelist,
                )
        elif self.pgd:
            pgdfile = PGDFile(
                filetype,
                pgdfile,
                input_file=pgd_file_path,
                archive_file=output,
                lfagmap=lfagmap,
            )
            SURFEXBinary(
                binary,
                batch,
                pgdfile,
                settings,
                input_data,
                archive_data=archive_data,
                print_namelist=self.print_namelist,
            )
        elif self.prep:
            prepfile = PREPFile(filetype, prepfile, archive_file=output, lfagmap=lfagmap)
            SURFEXBinary(
                binary,
                batch,
                prepfile,
                settings,
                input_data,
                pgdfile=pgdfile,
                archive_data=archive_data,
                print_namelist=self.print_namelist,
            )
        else:
            SURFEXBinary(
                binary,
                batch,
                prepfile,
                settings,
                input_data,
                pgdfile=pgdfile,
                surfout=surffile,
                archive_data=archive_data,
                print_namelist=self.print_namelist,
            )


class Pgd(SurfexBinaryTask):
    """Running PGD task.

    Args:
        SurfexBinaryTask(AbstractTask): Inheritance of surfex binary task class
    """

    def __init__(self, config):
        """Construct a Pgd task object.

        Args:
            config (ParsedObject): Parsed configuration

        """
        SurfexBinaryTask.__init__(self, config, "Pgd", "pgd")

    def execute(self):
        """Execute."""
        pgdfile = self.config.get_value("SURFEX.IO.CPGDFILE") + self.suffix
        output = f"{self.platform.get_system_value('climdir')}/{pgdfile}"
        binary = self.bindir + "/PGD" + self.xyz

        if not os.path.exists(output) or self.force:
            SurfexBinaryTask.execute_binary(self, binary=binary, output=output)
        else:
            print("Output already exists: ", output)


class Prep(SurfexBinaryTask):
    """Running PREP task.

    Args:
        SurfexBinaryTask(AbstractTask): Inheritance of surfex binary task class
    """

    def __init__(self, config):
        """Construct Prep task.

        Args:
            config (ParsedObject): Parsed configuration

        """
        SurfexBinaryTask.__init__(self, config, "Prep", "prep")

    def execute(self):
        """Execute."""
        pgdfile = self.config.get_value("SURFEX.IO.CPGDFILE") + self.suffix
        pgd_file_path = f"{self.platform.get_system_value('climdir')}/{pgdfile}"
        try:
            prep_file = self.config.get_value("initial_conditions.prep_input_file")
        except AttributeError:
            prep_file = None
        if prep_file is not None:
            if prep_file == "":
                prep_file = None
            else:
                prep_file = self.platform.substitute(
                    prep_file, validtime=self.dtg, basetime=self.fg_dtg
                )
        try:
            prep_pgdfile = self.config.get_value("initial_conditions.prep_pgdfile")
        except AttributeError:
            prep_pgdfile = None
        if prep_pgdfile == "":
            prep_pgdfile = None
        prepfile = self.config.get_value("SURFEX.IO.CPREPFILE") + self.suffix
        archive = self.platform.get_system_value("archive_dir")
        output = f"{self.platform.substitute(archive, basetime=self.dtg)}/{prepfile}"
        binary = self.bindir + "/PREP" + self.xyz

        if not os.path.exists(output) or self.force:
            SurfexBinaryTask.execute_binary(
                self,
                binary,
                output,
                pgd_file_path=pgd_file_path,
                prep_file=prep_file,
                prep_pgdfile=prep_pgdfile,
            )
        else:
            logger.info("Output already exists: {}", output)

        # PREP should prepare for forecast
        if os.path.exists(self.fc_start_sfx):
            os.unlink(self.fc_start_sfx)
        os.symlink(output, self.fc_start_sfx)


class Forecast(SurfexBinaryTask):
    """Running Forecast task.

    Args:
        SurfexBinaryTask(AbstractTask): Inheritance of surfex binary task class
    """

    def __init__(self, config):
        """Construct the forecast task.

        Args:
            config (ParsedObject): Parsed configuration

        """
        SurfexBinaryTask.__init__(self, config, "Forecast", "offline")

    def execute(self):
        """Execute."""
        pgdfile = self.config.get_value("SURFEX.IO.CPGDFILE") + self.suffix
        pgd_file_path = f"{self.platform.get_system_value('climdir')}/{pgdfile}"
        binary = self.bindir + "/OFFLINE" + self.xyz

        output = (
            self.archive
            + "/"
            + self.config.get_value("SURFEX.IO.CSURFFILE")
            + self.suffix
        )

        archive_data = None
        if self.config.get_value("SURFEX.IO.CTIMESERIES_FILETYPE") == "NC":
            last_ll = self.dtg + self.fcint

            logger.debug("LAST_LL: {}", last_ll)
            fname = (
                "SURFOUT."
                + last_ll.strftime("%Y%m%d")
                + "_"
                + last_ll.strftime("%H")
                + "h"
                + last_ll.strftime("%M")
                + ".nc"
            )
            logger.debug("Filename: {}", fname)
            archive_data = JsonOutputData({fname: self.archive + "/" + fname})
            logger.debug("archive_data={}", archive_data)

        # Forcing dir
        forcing_dir = self.platform.get_system_value("forcing_dir")
        forcing_dir = self.platform.substitute(forcing_dir, basetime=self.basetime)
        self.exp_file_paths.add_system_file_path("forcing_dir", forcing_dir)

        if not os.path.exists(output) or self.force:
            SurfexBinaryTask.execute_binary(
                self,
                binary,
                output,
                pgd_file_path=pgd_file_path,
                prep_file_path=self.fc_start_sfx,
                archive_data=archive_data,
            )
        else:
            logger.info("Output already exists: {}", output)


class PerturbedRun(SurfexBinaryTask):
    """Running a perturbed forecast task.

    Args:
        SurfexBinaryTask(AbstractTask): Inheritance of surfex binary task class

    """

    def __init__(self, config):
        """Construct a perturbed run task.

        Args:
            config (ParsedObject): Parsed configuration

        """
        SurfexBinaryTask.__init__(self, config, "PerturbedRun", "perturbed")

    def execute(self):
        """Execute."""
        pgdfile = self.config.get_value("SURFEX.IO.CPGDFILE") + self.suffix
        pgd_file_path = f"{self.platform.get_system_value('climdir')}/{pgdfile}"
        bindir = self.platform.get_system_value("bin_dir")
        binary = bindir + "/OFFLINE" + self.xyz

        # PREP file is previous analysis unless first assimilation cycle
        if self.fg_dtg == self.dtgbeg:
            prepfile = f"{self.config.get_value('SURFEX.IO.CPREPFILE')}{self.suffix}"
        else:
            prepfile = "ANALYSIS" + self.suffix

        archive_pattern = self.config.get_value("system.archive_dir")
        prep_file_path = self.platform.substitute(archive_pattern, basetime=self.fg_dtg)
        prep_file_path = f"{prep_file_path}/{prepfile}"
        surffile = self.config.get_value("SURFEX.IO.CSURFFILE")
        output = f"{self.archive}/{surffile}_PERT{str(self.pert)}{self.suffix}"

        # Forcing dir is for previous cycle
        # TODO If pertubed runs moved to pp it should be a diffenent dtg
        forcing_dir = self.config.get_value("system.forcing_dir")
        forcing_dir = self.platform.substitute(forcing_dir, basetime=self.fg_dtg)
        self.exp_file_paths.add_system_file_path("forcing_dir", forcing_dir)

        if not os.path.exists(output) or self.force:
            SurfexBinaryTask.execute_binary(
                self,
                binary,
                output,
                pgd_file_path=pgd_file_path,
                prep_file_path=prep_file_path,
            )
        else:
            logger.info("Output already exists: {}", output)


class Soda(SurfexBinaryTask):
    """Running SODA (Surfex Offline Data Assimilation) task.

    Args:
        SurfexBinaryTask(AbstractTask): Inheritance of surfex binary task class
    """

    def __init__(self, config):
        """Construct a Soda task.

        Args:
            config (ParsedObject): Parsed configuration

        """
        SurfexBinaryTask.__init__(self, config, "Soda", "soda")

    def execute(self):
        """Execute."""
        binary = self.bindir + "/SODA" + self.xyz

        pgdfile = self.config.get_value("SURFEX.IO.CPGDFILE") + self.suffix
        pgd_file_path = self.platform.get_system_value("climdir")
        pgd_file_path = f"{self.platform.substitute(pgd_file_path)}/{pgdfile}"

        prep_file_path = self.fg_guess_sfx
        output = self.archive + "/ANALYSIS" + self.suffix
        if self.settings.setting_is("SURFEX.ASSIM.SCHEMES.ISBA", "EKF"):
            # TODO If pertubed runs moved to pp it should be a diffenent dtg
            archive_dir = self.config.get_value("system.archive_dir")
            pert_run_dir = self.platform.substitute(archive_dir, basetime=self.dtg)
            self.exp_file_paths.add_system_file_path("perturbed_run_dir", pert_run_dir)
            first_guess_dir = self.platform.substitute(archive_dir, basetime=self.fg_dtg)
            self.exp_file_paths.add_system_file_path("first_guess_dir", first_guess_dir)

        if not os.path.exists(output) or self.force:
            SurfexBinaryTask.execute_binary(
                self,
                binary,
                output,
                pgd_file_path=pgd_file_path,
                prep_file_path=prep_file_path,
            )
        else:
            logger.info("Output already exists: {}", output)

        # SODA should prepare for forecast
        if os.path.exists(self.fc_start_sfx):
            os.unlink(self.fc_start_sfx)
        os.symlink(output, self.fc_start_sfx)
