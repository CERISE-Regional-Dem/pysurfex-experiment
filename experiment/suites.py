"""Suite for experiment."""
import os

from .configuration import Configuration
from .datetime_utils import ProgressFromConfig, as_datetime, as_timedelta, datetime2ecflow
from .logs import GLOBAL_LOGLEVEL, logger
from .scheduler.submission import TaskSettings, TroikaSettings
from .scheduler.suites import (
    EcflowSuite,
    EcflowSuiteFamily,
    EcflowSuiteTask,
    EcflowSuiteTrigger,
    EcflowSuiteTriggers,
)
from .toolbox import Platform


class SurfexSuite:
    """Surfex suite."""

    def __init__(
        self,
        suite_name,
        config,
        joboutdir,
        task_settings,
        dtgs,
        dtgbeg=None,
        ecf_micro="%",
    ):
        """Initialize a SurfexSuite object.

        Args:
            suite_name (str): Name of the suite
            config (ParsedConfig): Parsed configuration
            joboutdir (str): Directory for job and log files
            task_settings (TaskSettings): Submission environment for jobs
            dtgs (list): The DTGs you want to run
            dtgbeg (as_datetime, optional): First DTG the experiment run.
                                            Defaults to None.
            ecf_micro (str, optional): Ecflow micro. Defaults to "%"

        Raises:
            NotImplementedError: Not implmented

        """
        if dtgbeg is None:
            dtgbeg_str = datetime2ecflow(dtgs[0])
        else:
            dtgbeg_str = datetime2ecflow(dtgbeg)

        self.config = config
        settings = Configuration(config)
        platform = Platform(config)
        exp_dir = f"{platform.get_system_value('exp_dir')}"
        platform_name = f"{platform.get_platform_value('name')}"
        ecf_include = exp_dir + "/ecf"
        ecf_files = joboutdir
        os.makedirs(ecf_files, exist_ok=True)
        template = f"{platform.get_system_value('pysurfex_experiment')}/experiment/templates/ecflow/default.py"
        ecf_home = joboutdir
        ecf_out = joboutdir
        ecf_jobout = joboutdir + "/%ECF_NAME%.%ECF_TRYNO%"
        os.makedirs(ecf_out, exist_ok=True)
        logger.debug("ECF_HOME: {}", ecf_home)

        # Commands started from the scheduler does not have full environment
        ecf_job_cmd = (
            f"{ecf_micro}TROIKA{ecf_micro} "
            f"-c {ecf_micro}TROIKA_CONFIG{ecf_micro} submit "
            f"-o {ecf_micro}ECF_JOBOUT{ecf_micro} "
            f"{ecf_micro}SCHOST{ecf_micro} "
            f"{ecf_micro}ECF_JOB{ecf_micro}"
        )
        # %ECF_JOB%"
        ecf_status_cmd = (
            f"{ecf_micro}TROIKA{ecf_micro} "
            f"-c {ecf_micro}TROIKA_CONFIG{ecf_micro} monitor "
            f"{ecf_micro}SCHOST{ecf_micro} "
            f"{ecf_micro}ECF_JOB{ecf_micro}"
        )
        ecf_kill_cmd = (
            f"{ecf_micro}TROIKA{ecf_micro} "
            f"-c {ecf_micro}TROIKA_CONFIG{ecf_micro} kill "
            f"{ecf_micro}SCHOST{ecf_micro} "
            f"{ecf_micro}ECF_JOB{ecf_micro}"
        )

        try:
            config_file = config.get_value("metadata.source_file_path")
        except AttributeError:
            config_file = "NO_CONFIG_FOUND"
        loglevel = GLOBAL_LOGLEVEL
        logger.debug("Setting ecflow loglevel to={}", loglevel)
        variables = {
            "ECF_EXTN": ".py",
            "ECF_FILES": ecf_files,
            "ECF_INCLUDE": ecf_include,
            "ECF_TRIES": 1,
            "ECF_HOME": ecf_home,
            "ECF_KILL_CMD": ecf_kill_cmd,
            "ECF_JOB_CMD": ecf_job_cmd,
            "ECF_STATUS_CMD": ecf_status_cmd,
            "ECF_OUT": ecf_out,
            "ECF_JOBOUT": ecf_jobout,
            "ECF_TIMEOUT": 20,
            "LOGLEVEL": loglevel,
            "WRAPPER": "",
            "VAR_NAME": "",
            "CONFIG": str(config_file),
            "TROIKA": TroikaSettings(config).command,
            "TROIKA_CONFIG": TroikaSettings(config).config,
            "EXP_DIR": exp_dir,
            "EXP": config.get_value("general.case"),
            "DTG": dtgbeg_str,
            "DTGPP": dtgbeg_str,
            "STREAM": "",
            "ENSMBR": "",
            "ARGS": "",
            "FORCE": "",
            "CHECK_EXISTENCE": "",
            "PRINT_NAMELIST": "",
        }
        realization = None
        self.suite_name = suite_name
        logger.debug("variables: {}", variables)
        self.suite = EcflowSuite(self.suite_name, ecf_files, variables=variables)

        if config.get_value("compile.build"):
            comp = EcflowSuiteFamily("Compilation", self.suite, ecf_files)
            if config.get_value("compile.cmake"):
                EcflowSuiteTask(
                    "CMakeBuild",
                    comp,
                    config,
                    task_settings,
                    ecf_files,
                    input_template=template,
                )
                comp_complete = EcflowSuiteTrigger(comp, mode="complete")
            else:
                sync = EcflowSuiteTask(
                    "SyncSourceCode",
                    comp,
                    config,
                    task_settings,
                    ecf_files,
                    input_template=template,
                )
                sync_complete = EcflowSuiteTrigger(sync, mode="complete")
                configure = EcflowSuiteTask(
                    "ConfigureOfflineBinaries",
                    comp,
                    config,
                    task_settings,
                    ecf_files,
                    input_template=template,
                    triggers=EcflowSuiteTriggers([sync_complete]),
                )
                configure_complete = EcflowSuiteTrigger(configure, mode="complete")
                EcflowSuiteTask(
                    "MakeOfflineBinaries",
                    comp,
                    config,
                    task_settings,
                    ecf_files,
                    input_template=template,
                    triggers=EcflowSuiteTriggers([configure_complete]),
                )
                comp_complete = EcflowSuiteTrigger(comp, mode="complete")
        else:
            comp_complete = None

        triggers = EcflowSuiteTriggers([comp_complete])
        static_data = EcflowSuiteFamily(
            "StaticData", self.suite, ecf_files, triggers=triggers
        )

        pgd_input = EcflowSuiteFamily("PgdInput", static_data, ecf_files)
        EcflowSuiteTask(
            "Gmted",
            pgd_input,
            config,
            task_settings,
            ecf_files,
            input_template=template,
            variables=None,
        )

        EcflowSuiteTask(
            "Soil",
            pgd_input,
            config,
            task_settings,
            ecf_files,
            input_template=template,
            variables=None,
        )

        pgd_trigger = EcflowSuiteTriggers([EcflowSuiteTrigger(pgd_input)])
        EcflowSuiteTask(
            "Pgd",
            static_data,
            config,
            task_settings,
            ecf_files,
            input_template=template,
            triggers=pgd_trigger,
        )

        static_complete = EcflowSuiteTrigger(static_data)

        prep_complete = None
        hours_ahead = 24
        cycle_input_dtg_node = {}
        prediction_dtg_node = {}
        post_processing_dtg_node = {}
        prev_dtg = None
        for __, dtg in enumerate(dtgs):
            dtg_str = datetime2ecflow(dtg)
            variables = {"DTG": dtg_str, "DTGBEG": dtgbeg_str}
            triggers = EcflowSuiteTriggers([static_complete])

            dtg_node = EcflowSuiteFamily(
                dtg_str, self.suite, ecf_files, variables=variables, triggers=triggers
            )

            ahead_trigger = None
            for dtg_str2 in prediction_dtg_node:
                tname = prediction_dtg_node[dtg_str2]["node"]
                validtime = as_datetime(prediction_dtg_node[dtg_str2]["dtg"])
                if validtime < dtg:
                    if validtime + as_timedelta(f"PT{hours_ahead}H") <= dtg:
                        ahead_trigger = EcflowSuiteTrigger(tname)

            if ahead_trigger is None:
                triggers = EcflowSuiteTriggers([static_complete])
            else:
                triggers = EcflowSuiteTriggers([static_complete, ahead_trigger])

            prepare_cycle = EcflowSuiteTask(
                "PrepareCycle",
                dtg_node,
                config,
                task_settings,
                ecf_files,
                triggers=triggers,
                input_template=template,
            )
            prepare_cycle_complete = EcflowSuiteTrigger(prepare_cycle)

            triggers.add_triggers([EcflowSuiteTrigger(prepare_cycle)])

            cycle_input = EcflowSuiteFamily(
                "CycleInput", dtg_node, ecf_files, triggers=triggers
            )
            cycle_input_dtg_node.update({dtg_str: cycle_input})

            forcing = EcflowSuiteTask(
                "Forcing",
                cycle_input,
                config,
                task_settings,
                ecf_files,
                input_template=template,
            )
            triggers = EcflowSuiteTriggers([EcflowSuiteTrigger(forcing)])
            if config.get_value("forcing.modify_forcing"):
                EcflowSuiteTask(
                    "ModifyForcing",
                    cycle_input,
                    config,
                    task_settings,
                    ecf_files,
                    input_template=template,
                    triggers=triggers,
                )

            triggers = EcflowSuiteTriggers([static_complete, prepare_cycle_complete])
            if prev_dtg is not None:
                prev_dtg_str = datetime2ecflow(prev_dtg)
                trigger = EcflowSuiteTrigger(prediction_dtg_node[prev_dtg_str]["node"])
                triggers.add_triggers([trigger])

            # Initialization
            initialization = EcflowSuiteFamily(
                "Initialization", dtg_node, ecf_files, triggers=triggers
            )

            analysis = None
            if dtg == dtgbeg:
                prep = EcflowSuiteTask(
                    "Prep",
                    initialization,
                    config,
                    task_settings,
                    ecf_files,
                    input_template=template,
                )
                prep_complete = EcflowSuiteTrigger(prep)
                # Might need an extra trigger for input

            else:
                schemes = config.get_value("SURFEX.ASSIM.SCHEMES").dict()
                do_soda = False
                for scheme in schemes:
                    if schemes[scheme].upper() != "NONE":
                        do_soda = True

                obs_types = config.get_value("SURFEX.ASSIM.OBS.COBS_M")
                nnco = settings.get_nnco(dtg=dtg)
                for ivar in range(0, len(nnco)):
                    if nnco[ivar] == 1 and obs_types[ivar] == "SWE":
                        do_soda = True

                triggers = EcflowSuiteTriggers(prep_complete)
                if not do_soda:
                    EcflowSuiteTask(
                        "CycleFirstGuess",
                        initialization,
                        config,
                        task_settings,
                        ecf_files,
                        triggers=triggers,
                        input_template=template,
                    )
                else:
                    fg_task = EcflowSuiteTask(
                        "FirstGuess",
                        initialization,
                        config,
                        task_settings,
                        ecf_files,
                        triggers=triggers,
                        input_template=template,
                    )

                    perturbations = None
                    logger.debug(
                        "Perturbations: {}",
                        settings.setting_is(
                            "SURFEX.ASSIM.SCHEMES.ISBA", "EKF", realization=realization
                        ),
                    )
                    if settings.setting_is(
                        "SURFEX.ASSIM.SCHEMES.ISBA", "EKF", realization=realization
                    ):
                        perturbations = EcflowSuiteFamily(
                            "Perturbations", initialization, ecf_files
                        )
                        nncv = config.get_value("SURFEX.ASSIM.ISBA.EKF.NNCV")
                        names = config.get_value("SURFEX.ASSIM.ISBA.EKF.CVAR_M")
                        llincheck = config.get_value("SURFEX.ASSIM.ISBA.EKF.LLINCHECK")
                        triggers = None
                        fgint = settings.get_fgint(realization=realization)
                        fg_dtg = dtg - fgint
                        if fg_dtg in cycle_input_dtg_node:
                            triggers = EcflowSuiteTriggers(
                                EcflowSuiteTrigger(cycle_input_dtg_node[fg_dtg])
                            )

                        name = "REF"
                        pert = EcflowSuiteFamily(name, perturbations, ecf_files)
                        args = f"pert=0;name={name};ivar=0"
                        logger.debug("args: {}", args)
                        variables = {"ARGS": args}
                        EcflowSuiteTask(
                            "PerturbedRun",
                            pert,
                            config,
                            task_settings,
                            ecf_files,
                            triggers=triggers,
                            variables=variables,
                            input_template=template,
                        )

                        # Add extra families in case of llincheck
                        pert_signs = ["none"]
                        if llincheck:
                            pert_signs = ["pos", "neg"]

                        pert_families = []
                        for pert_sign in pert_signs:
                            if pert_sign == "none":
                                pert_families.append(perturbations)
                            elif pert_sign == "pos":
                                pert_families.append(
                                    EcflowSuiteFamily(
                                        "Pos",
                                        perturbations,
                                        ecf_files,
                                        variables=variables,
                                    )
                                )
                            elif pert_sign == "neg":
                                pert_families.append(
                                    EcflowSuiteFamily(
                                        "Neg",
                                        perturbations,
                                        ecf_files,
                                        variables=variables,
                                    )
                                )
                            else:
                                raise NotImplementedError

                        nivar = 1
                        for ivar, val in enumerate(nncv):
                            logger.debug("ivar {}, nncv[ivar] {}", str(ivar), str(val))
                            if val == 1:

                                name = names[ivar]
                                nfam = 0
                                for pert_parent in pert_families:
                                    pivar = str((nfam * len(nncv)) + ivar + 1)
                                    pert = EcflowSuiteFamily(name, pert_parent, ecf_files)
                                    pert_sign = pert_signs[nfam]
                                    args = f"pert={str(pivar)};name={name};ivar={str(nivar)};pert_sign={pert_sign}"
                                    logger.debug("args: {}", args)
                                    variables = {"ARGS": args}
                                    EcflowSuiteTask(
                                        "PerturbedRun",
                                        pert,
                                        config,
                                        task_settings,
                                        ecf_files,
                                        triggers=triggers,
                                        variables=variables,
                                        input_template=template,
                                    )
                                    nfam += 1
                                nivar = nivar + 1

                    prepare_oi_soil_input = None
                    prepare_oi_climate = None
                    if settings.setting_is("SURFEX.ASSIM.SCHEMES.ISBA", "OI"):
                        prepare_oi_soil_input = EcflowSuiteTask(
                            "PrepareOiSoilInput",
                            initialization,
                            config,
                            task_settings,
                            ecf_files,
                            input_template=template,
                        )
                        prepare_oi_climate = EcflowSuiteTask(
                            "PrepareOiClimate",
                            initialization,
                            config,
                            task_settings,
                            ecf_files,
                            input_template=template,
                        )

                    prepare_sst = None
                    if settings.setting_is("SURFEX.ASSIM.SCHEMES.SEA", "INPUT"):
                        if settings.setting_is(
                            "SURFEX.ASSIM.SEA.CFILE_FORMAT_SST", "ASCII"
                        ):
                            prepare_sst = EcflowSuiteTask(
                                "PrepareSST",
                                initialization,
                                config,
                                task_settings,
                                ecf_files,
                                input_template=template,
                            )

                    an_variables = {"t2m": False, "rh2m": False, "sd": False}
                    obs_types = config.get_value("SURFEX.ASSIM.OBS.COBS_M")
                    nnco = settings.get_nnco(dtg=dtg)
                    need_obs = False
                    for t_ind, val in enumerate(obs_types):
                        if nnco[t_ind] == 1:
                            if val == "T2M" or val == "T2M_P":
                                an_variables.update({"t2m": True})
                                need_obs = True
                            elif val == "HU2M" or val == "HU2M_P":
                                an_variables.update({"rh2m": True})
                                need_obs = True
                            elif val == "SWE":
                                an_variables.update({"sd": True})
                                need_obs = True

                    analysis = EcflowSuiteFamily("Analysis", initialization, ecf_files)
                    fg4oi = EcflowSuiteTask(
                        "FirstGuess4OI",
                        analysis,
                        config,
                        task_settings,
                        ecf_files,
                        input_template=template,
                    )
                    fg4oi_complete = EcflowSuiteTrigger(fg4oi)

                    cryo_obs_sd = config.get_value("observations.cryo_obs_sd")
                    cryo2json_complete = fg4oi_complete
                    if cryo_obs_sd:
                        cryo_trigger = EcflowSuiteTriggers(fg4oi_complete)
                        cryo2json = EcflowSuiteTask(
                            "CryoClim2json",
                            analysis,
                            config,
                            task_settings,
                            ecf_files,
                            triggers=cryo_trigger,
                            input_template=template,
                        )
                        cryo2json_complete = EcflowSuiteTrigger(cryo2json)

                    fetchobs_complete = None
                    if platform_name == "ECMWF-atos":
                        if need_obs:
                            fetchobs = EcflowSuiteTask(
                                "FetchMarsObs",
                                analysis,
                                config,
                                task_settings,
                                ecf_files,
                                input_template=template,
                            )
                            fetchobs_complete = EcflowSuiteTrigger(fetchobs)

                    triggers = []
                    for var, active in an_variables.items():
                        if active:
                            variables = {"VAR_NAME": var}
                            an_var_fam = EcflowSuiteFamily(
                                var, analysis, ecf_files, variables=variables
                            )
                            qc_triggers = None
                            if var == "sd":
                                qc_triggers = EcflowSuiteTriggers(
                                    [
                                        fg4oi_complete,
                                        fetchobs_complete,
                                        cryo2json_complete,
                                    ]
                                )
                            else:
                                qc_triggers = EcflowSuiteTriggers(fetchobs_complete)
                            qc_task = EcflowSuiteTask(
                                "QualityControl",
                                an_var_fam,
                                config,
                                task_settings,
                                ecf_files,
                                triggers=qc_triggers,
                                input_template=template,
                            )
                            oi_triggers = EcflowSuiteTriggers(
                                [EcflowSuiteTrigger(qc_task), EcflowSuiteTrigger(fg4oi)]
                            )
                            EcflowSuiteTask(
                                "OptimalInterpolation",
                                an_var_fam,
                                config,
                                task_settings,
                                ecf_files,
                                triggers=oi_triggers,
                                input_template=template,
                            )
                            triggers.append(EcflowSuiteTrigger(an_var_fam))

                    oi2soda_complete = None
                    if len(triggers) > 0:
                        triggers = EcflowSuiteTriggers(triggers)
                        oi2soda = EcflowSuiteTask(
                            "Oi2soda",
                            analysis,
                            config,
                            task_settings,
                            ecf_files,
                            triggers=triggers,
                            input_template=template,
                        )
                        oi2soda_complete = EcflowSuiteTrigger(oi2soda)

                    prepare_lsm = None
                    need_lsm = False
                    if settings.setting_is("SURFEX.ASSIM.SCHEMES.ISBA", "OI"):
                        need_lsm = True
                    if settings.setting_is("SURFEX.ASSIM.SCHEMES.INLAND_WATER", "WATFLX"):
                        if config.get_value("SURFEX.ASSIM.INLAND_WATER.LEXTRAP_WATER"):
                            need_lsm = True
                    if need_lsm:
                        triggers = EcflowSuiteTriggers(fg4oi_complete)
                        prepare_lsm = EcflowSuiteTask(
                            "PrepareLSM",
                            initialization,
                            config,
                            task_settings,
                            ecf_files,
                            triggers=triggers,
                            input_template=template,
                        )

                    triggers = [EcflowSuiteTrigger(fg_task), oi2soda_complete]
                    if perturbations is not None:
                        triggers.append(EcflowSuiteTrigger(perturbations))
                    if prepare_oi_soil_input is not None:
                        triggers.append(EcflowSuiteTrigger(prepare_oi_soil_input))
                    if prepare_oi_climate is not None:
                        triggers.append(EcflowSuiteTrigger(prepare_oi_climate))
                    if prepare_sst is not None:
                        triggers.append(EcflowSuiteTrigger(prepare_sst))
                    if prepare_lsm is not None:
                        triggers.append(EcflowSuiteTrigger(prepare_lsm))

                    triggers = EcflowSuiteTriggers(triggers)
                    EcflowSuiteTask(
                        "Soda",
                        analysis,
                        config,
                        task_settings,
                        ecf_files,
                        triggers=triggers,
                        input_template=template,
                    )

            triggers = EcflowSuiteTriggers(
                [EcflowSuiteTrigger(cycle_input), EcflowSuiteTrigger(initialization)]
            )
            ##### WROK HERE #####
            ensmsel = config.get_value("forecast.ensmsel")
            pert_forcing = config.get_value("eps.pert_forcing")
            pert_state = config.get_value("eps.pert_state")
            if len(ensmsel) > 0:
                ens_prep = EcflowSuiteFamily("ensemble_prep", dtg_node, ecf_files, triggers=triggers)
                if pert_forcing:
                    create_noise = EcflowSuiteTask("createNoise",
                            ens_prep,
                            config,
                            task_settings,
                            ecf_files,
                            triggers=triggers,
                            input_template=template)
                da_this = False
                if config.get_value("assim.general.do_assim") == True :  # and dtg.hour == 6:
                    da_this = True
                    prep = EcflowSuiteTask("ExternalAssim", ens_prep, config, task_settings, ecf_files,triggers=triggers, input_template=template)

                else:
                    prep = EcflowSuiteTask("CycleFirstGuess", ens_prep, config, task_settings, ecf_files,triggers=triggers, input_template=template)
                if pert_forcing:
                    triggers = EcflowSuiteTriggers([EcflowSuiteTrigger(create_noise), EcflowSuiteTrigger(prep)])
                else:
                    triggers = EcflowSuiteTriggers([EcflowSuiteTrigger(prep)])

                for m in ensmsel:
                    if pert_forcing or pert_state or not da_this:
                        logger.debug("prep member %s", m)
                        name = "mbr_%03d" % m
                        args = "pert=" + str(m) + ";name=" + name
                        logger.debug("args: %s", args)
                        variables = {"ARGS": args, "ENSMBR": int(m)}
                        pert = EcflowSuiteFamily(name, ens_prep, ecf_files, variables=variables) 
                        cpfg = EcflowSuiteTask("CopyFG", pert, config, task_settings, ecf_files, triggers=None, input_template=template) 
                        if pert_forcing:
                            EcflowSuiteTask("PerturbForcing", pert, config, task_settings, ecf_files,triggers=triggers, input_template=template)
                        if dtg == dtgbeg:
                            prep = EcflowSuiteTask("Prep", pert, config, task_settings, ecf_files,input_template=template)
                        else:
                            if not da_this:
                                prep = EcflowSuiteTask("CycleFirstGuess", pert, config, task_settings, ecf_files,triggers=triggers, input_template=template)
                                #triggers = EcflowSuiteTriggers([EcflowSuiteTrigger(prep)])
                        if pert_state:
                            EcflowSuiteTask("PerturbState", pert, config, task_settings, ecf_files,triggers=triggers, input_template=template)

                triggers = EcflowSuiteTriggers([EcflowSuiteTrigger(ens_prep)])




            #####################
            prediction = EcflowSuiteFamily(
                "Prediction", dtg_node, ecf_files, triggers=triggers
            )
            prediction_dtg_node.update({dtg_str: {"node": prediction, "dtg": dtg}})

            forecast = EcflowSuiteTask(
                "Forecast",
                prediction,
                config,
                task_settings,
                ecf_files,
                input_template=template,
            )
            #### WORK HERE ####
            if len(ensmsel) > 0:
                eps = EcflowSuiteFamily("EPS", prediction, ecf_files)
                for m in ensmsel:
                    logger.debug("member %s", m)
                    name = "mbr_%03d" % m
                    args = "pert=" + str(m) + ";name=" + name
                    logger.debug("args: %s", args)
                    variables = {"ARGS": args, "ENSMBR": str(m)}
                    member = EcflowSuiteFamily(name, eps, ecf_files, variables=variables)
                    EcflowSuiteTask("Forecast", member, config, task_settings, ecf_files, input_template=template)
                triggers = EcflowSuiteTriggers([EcflowSuiteTrigger(forecast), EcflowSuiteTrigger(member)])

            EcflowSuiteTask(
                "LogProgress",
                prediction,
                config,
                task_settings,
                ecf_files,
                triggers=triggers,
                input_template=template,
            )

            triggers = EcflowSuiteTriggers(EcflowSuiteTrigger(prediction))
            pp_fam = EcflowSuiteFamily(
                "PostProcessing", dtg_node, ecf_files, triggers=triggers
            )
            post_processing_dtg_node.update({dtg_str: pp_fam})

            log_pp_trigger = None
            obs_extract = EcflowSuiteTask("ObsExtract", pp_fam, config, task_settings, ecf_files,input_template=template)
            fgint = settings.get_fgint(realization=realization)

            if len(ensmsel) > 0:
                eps = EcflowSuiteFamily("ens_pp", pp_fam, ecf_files)
                for m in ensmsel:
                    logger.debug("member %s", m)
                    name = "mbr_%03d" % m
                    args = "pert=" + str(m) + ";name=" + name
                    logger.debug("args: %s", args)
                    variables = {"ARGS": args, "ENSMBR": str(m)}
                    member = EcflowSuiteFamily(name, eps, ecf_files, variables=variables)
                    obs_extract = EcflowSuiteTask("ObsExtract", member, config, task_settings, ecf_files,input_template=template)
                    triggers = EcflowSuiteTriggers([EcflowSuiteTrigger(obs_extract), EcflowSuiteTrigger(member)])
                    if config.get_value("general.arhive_ecfs") and (dtg + fgint).strftime("%w%H") == "000":
                        archive_ecfs = EcflowSuiteTask("ArchiveECFS", member, config, task_settings, ecf_files,input_template=template)
                        triggers = EcflowSuiteTriggers([EcflowSuiteTrigger(archive_ecfs), EcflowSuiteTrigger(member)])
            if analysis is not None:
                qc2obsmon = EcflowSuiteTask(
                    "Qc2obsmon",
                    pp_fam,
                    config,
                    task_settings,
                    ecf_files,
                    input_template=template,
                )
                trigger = EcflowSuiteTrigger(qc2obsmon)
                log_pp_trigger = EcflowSuiteTriggers(trigger)
            if config.get_value("general.arhive_ecfs") and (dtg + fgint).strftime("%w%H") == "000":
                archive_ecfs = EcflowSuiteTask("ArchiveECFS", pp_fam, config, task_settings, ecf_files,input_template=template)


            EcflowSuiteTask(
                "LogProgressPP",
                pp_fam,
                config,
                task_settings,
                ecf_files,
                triggers=log_pp_trigger,
                input_template=template,
            )

            prev_dtg = dtg

        hours_behind = 24
        for dtg in dtgs:
            dtg_str = datetime2ecflow(dtg)
            pp_dtg_str = datetime2ecflow(dtg - as_timedelta(f"PT{hours_behind}H"))
            if pp_dtg_str in post_processing_dtg_node:
                triggers = EcflowSuiteTriggers(
                    EcflowSuiteTrigger(post_processing_dtg_node[pp_dtg_str])
                )
                cycle_input_dtg_node[dtg_str].add_part_trigger(triggers)

    def save_as_defs(self, def_file):
        """Save definition file.

        Args:
            def_file (_type_): _description_
        """
        logger.debug("SurfexSuiteDefinition: Saving def file {}", def_file)
        self.suite.save_as_defs(def_file)


def get_defs(config, suite_type):
    """Get the definitions.

    Args:
        config (experiment.ExpConfiguration): Experiment
        suite_type (str): What kind of suite

    Raises:
        NotImplementedError: _description_

    Returns:
        SuiteDefinition: A suite definitition
    """
    name = config.get_value("general.case")
    settings = Configuration(config)
    suite_name = name.replace("-", "_")
    suite_name = suite_name.replace(".", "_")
    logger.debug("Config name {}", name)
    logger.debug("Get defs for {}", suite_name)

    progress = ProgressFromConfig(config)
    platform = Platform(config)
    joboutdir = platform.get_system_value("joboutdir")
    task_settings = TaskSettings(config)
    unique_cycles = settings.get_total_unique_cycle_list()
    progress = ProgressFromConfig(config)
    basetime = progress.basetime
    starttime = progress.starttime
    endtime = progress.endtime
    logger.debug("DTGSTART: {} DTGBEG: {} DTGEND: {}", basetime, starttime, endtime)
    basetime_list = []
    dtg = basetime
    logger.debug("Building list of DTGs")
    cont = True
    while cont:
        for cycle in unique_cycles:
            while dtg <= endtime:
                basetime_list.append(dtg)
                logger.debug("DTG: {}, fcint: {}", dtg, cycle)
                dtg = dtg + cycle
            if dtg >= endtime:
                cont = False

    logger.debug("Built DTGS: {}", basetime_list)
    if suite_type == "surfex":
        return SurfexSuite(
            suite_name, config, joboutdir, task_settings, basetime_list, dtgbeg=starttime
        )
    raise NotImplementedError(f"Suite definition for {suite_type} is not implemented!")
