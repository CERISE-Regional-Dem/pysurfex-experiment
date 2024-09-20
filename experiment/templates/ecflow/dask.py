"""Default ecflow container."""
# @ENV_SUB1@
from dask.distributed import Client, LocalCluster
from experiment import PACKAGE_NAME
from experiment.config_parser import MAIN_CONFIG_JSON_SCHEMA, ParsedConfig
from experiment.datetime_utils import ecflow2datetime_string
from experiment.logs import GLOBAL_LOGLEVEL, LoggerHandlers, logger
from experiment.scheduler.scheduler import (
    EcflowClient,
    EcflowServerFromConfig,
    EcflowTask,
)
from experiment.tasks.discover_tasks import get_task

# @ENV_SUB2@


logger.enable(PACKAGE_NAME)


def parse_ecflow_vars():
    """Parse the ecflow variables."""
    return {
        "CONFIG": "%CONFIG%",
        "WRAPPER": "%WRAPPER%",
        "ENSMBR": "%ENSMBR%",
        "DTG": "%DTG%",
        "DTGPP": "%DTGPP%",
        "STREAM": "%STREAM%",
        "TASK_NAME": "%TASK%",
        "VAR_NAME": "%VAR_NAME%",
        "LOGLEVEL": "%LOGLEVEL%",
        "ARGS": "%ARGS%",
        "ECF_NAME": "%ECF_NAME%",
        "ECF_PASS": "%ECF_PASS%",
        "ECF_TRYNO": "%ECF_TRYNO%",
        "ECF_RID": "%ECF_RID%",
    }


"""
%nopp"
"""


def default_main(**kwargs):
    """Ecflow container default method."""
    config = kwargs.get("CONFIG")
    config = ParsedConfig.from_file(config, json_schema=MAIN_CONFIG_JSON_SCHEMA)

    # Reset loglevel according to (in order of priority):
    #     (a) Configs in ECFLOW UI
    #     (b) What was originally set in the config file
    #     (c) The default `GLOBAL_LOGLEVEL` if none of the above is found.
    loglevel = kwargs.get(
        "LOGLEVEL", config.get_value("general.loglevel", GLOBAL_LOGLEVEL)
    ).upper()
    logger.configure(handlers=LoggerHandlers(default_level=loglevel))
    logger.info("Loglevel={}", loglevel)

    ecf_name = kwargs.get("ECF_NAME")
    ecf_pass = kwargs.get("ECF_PASS")
    ecf_tryno = kwargs.get("ECF_TRYNO")
    ecf_rid = kwargs.get("ECF_RID")
    task = EcflowTask(ecf_name, ecf_tryno, ecf_pass, ecf_rid)
    scheduler = EcflowServerFromConfig(config)

    # This will also handle call to sys.exit(), i.e. Client._   _exit__ will still be called.
    with EcflowClient(scheduler, task):
        task_name = kwargs.get("TASK_NAME")
        logger.info("Running task {}", task_name)
        args = kwargs.get("ARGS")
        args_dict = {}
        if args != "":
            logger.debug("args={}", args)
            for arg in args.split(";"):
                parts = arg.split("=")
                logger.debug("arg={} parts={} len(parts)={}", arg, parts, len(parts))
                if len(parts) == 2:
                    args_dict.update({parts[0]: parts[1]})

        update = {
            "general": {
                "stream": kwargs.get("STREAM"),
                "realization": kwargs.get("ENSMBR"),
                "times": {
                    "basetime": ecflow2datetime_string(kwargs.get("DTG")),
                    "validtime": ecflow2datetime_string(kwargs.get("DTG")),
                    "basetime_pp": ecflow2datetime_string(kwargs.get("DTGPP")),
                },
            },
            "task": {
                "wrapper": kwargs.get("WRAPPER"),
                "var_name": kwargs.get("VAR_NAME"),
                "args": args_dict,
            },
        }
        config = config.copy(update=update)
        get_task(task.ecf_task, config).run()
        logger.info("Finished task {}", task_name)


if __name__ == "__main__":

    cluster = LocalCluster(
            n_workers=10,
            threads_per_worker=1,
            processes=True, 
            memory_limit="8GiB")
    client = Client(cluster)
    # Get ecflow variables
    kwargs_main = parse_ecflow_vars()

    default_main(**kwargs_main)

    client.close()
    cluster.close()

"""    # noqa
%end"  # noqa
"""  # noqa
