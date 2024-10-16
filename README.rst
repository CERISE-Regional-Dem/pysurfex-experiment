.. _README:

.. image:: https://coveralls.io/repos/github/metno/pysurfex-experiment/badge.svg?branch=master

https://coveralls.io/github/metno/pysurfex-experiment


This repository is a setup to create and run offline SURFEX experiments.
=========================================================================

See online documentation in https://metno.github.io/pysurfex-experiment/
The setup is dependent of pysurfex (https://metno.github.io/pysurfex)

You need a python3 parser and the following dependencies are needed. Install the non-standard ones e.g. with pip or your system installation system. Requirements can be found in https://github.com/metno/pysurfex-experiment/blob/master/requirements.txt


General dependencies (from pypi)
---------------------------------

.. code-block:: bash

 pysurfex

pysurfex bring extra dependencies like gridpp, titanlib. If you install from pypi with pip these should be handled automatically.

Installation
-------------

The recommended installation method is using poetry. First install poetry. This can be done in several ways like a system package or ftom pypi. The recommended way is:

.. code-block:: bash

 curl -sSL https://install.python-poetry.org | python3 -


When you have poetry installed make sure you have it in path. It might be installed in ~/.local/bin.
To install the script system first clone https://github.com/metno/pysurfex-experiment and install it.
To run commands interactively in the poetry environment you need to run either "poetry shell" or "poetry run [cmd]"


.. code-block:: bash

 cd
 mkdir -p projects
 cd projects

 # Clone the source code
 clone https://github.com/metno/pysurfex-experiment

 # Install the script system
 cd pysurfex-experiment
 poetry install

 # Enter the environment
 poetry shell


Usage
---------------------------------------------

There are two ways to set up an experiment. Either in an experiment with the config files inside the experiment,
or as a self contained configuration file with all settings inside.

Cerise Regional demonstrator on atos
-------------------------------------
Follow above instructions to install poetry evnvironment
Note clone from "git@github.com:CERISE-Regional-Dem/pysurfex-experiment.git"
with env activated:

.. code-block:: bash

 cd /home/$USER/sfx_home/
 mkdir my_reanalysis
 cd my_reanalysis

 export PYSURFEX_EXPERIMENT_PATH="pysurfex-experiment-clone-dir"
 export OFFLINE_SOURCE_CODE="path-to-your-offline-source-code"
 # OFFLINE_SOURCE_CODE should point to a clone of "git@github.com:CERISE-Regional-Dem/Harmonie.git"
 # Note that it by default compiles single precision reals. Since PGD needs to be created with double precision PGD either needs to be copied, 
 # or OFFLINE_SOURCE_CODE/util/cmake/config/config.aa.Intel.offline.json needs to be modified ("precision":"single" -> "precision":"double") to run double precision reals.

 PySurfexExpSetup -exp_name my_reanalysis -o /home/$USER/sfx_home/my_reanalysis/my_reanalysis.json --config cerise-land-pv1 -host ECMWF-atos-Intel -experiment $PYSURFEX_EXPERIMENT_PATH -offline $OFFLINE_SOURCE_CODE
 
 # This will create a json file in your experiment directory. You will now have to open it and change:
 # 1. "ecf_host" to your ecflow server.
 # 2. "ACCOUNT" to your slurm account

 # Start your experiment
 PySurfexExp start -dtg "2023-09-01T00:00:00Z" -dtgend "2023-09-01T06:00:00Z" -config my_reanalysis.json 

The suite should now appear in your ecflow server.


Approach 1: All sub-config files in an experiment
----------------------------------------------------

Assume you have cloned experiment in pysurfex-experiment-clone-dir. Let us set some variables we can use in the examples in addition to some system settings.
Adjust it to your clone, host-tag and system. First you will set up an experiment. This will merge configuration based on your settings and split them back to configuration files.
You have the following config files in the config directories:

 * config_exp.toml
 * config_exp_surfex.toml
 * config_exp_observations.toml
 * config_exp_eps.toml
 
In addition you will get some other config files used in the tasks. An example on how to use it inside a poetry environment ("poetry shell")

.. code-block:: bash

 # First make sure you are in a poetry environment after executing "poetry shell"
 cd ~/projects/pysurfex-experiment
 poetry shell

 export PYSURFEX_EXPERIMENT_PATH="pysurfex-experiment-clone-dir"
 export HOST_TAG="my-host-tag"
 export OFFLINE_SOURCE_CODE="path-to-your-offline-source-code"
 
 cd
 mkdir -p sfx_home
 cd sfx_home
 mkdir -p my_exp
 cd my_exp
 
 # The -offline argument is optional if you want to run with existing binaries
 PySurfexExpSetup -experiment $PYSURFEX_EXPERIMENT_PATH -host $HOST_TAG -offline $OFFLINE_SOURCE_CODE
 # This will create a file exp_dependencies.json

 # Alternative way of setting up a pre-defined SEKF configuration
 PySurfexExpSetup -experiment $PYSURFEX_EXPERIMENT_PATH -host $HOST_TAG -offline $OFFLINE_SOURCE_CODE --config sekf
 
 # To re-configure your config and (re-)create exp_configuration.json
 PySurfexExpConfig

 

 # To start you experiment
 PySurfexExp start -dtg 202301010300 -dtgend 202301010600

Alternative 2 is using the poetry run functionality:

.. code-block:: bash

 # First make sure you are in a poetry environment after executing "poetry shell"
 cd ~/projects/pysurfex-experiment

 export PYSURFEX_EXPERIMENT_PATH="pysurfex-experiment-clone-dir"
 export HOST_TAG="my-host-tag"
 export OFFLINE_SOURCE_CODE="path-to-your-offline-source-code"
 export WD=$HOME/sfx_home/my_exp
 
 # The -offline argument is optional if you want to run with existing binaries
 poetry run PySurfexExpSetup -experiment $PYSURFEX_EXPERIMENT_PATH -host $HOST_TAG -offline $OFFLINE_SOURCE_CODE -exp_name my_exp --wd $WD
 # This will create a file exp_dependencies.json
 
 # Alternative way of setting up a pre-defined SEKF configuration
 WD=$HOME/sfx_home/my_sekf_exp
 poetry run PySurfexExpSetup -experiment $PYSURFEX_EXPERIMENT_PATH -host $HOST_TAG -offline $OFFLINE_SOURCE_CODE --config sekf -exp_name my_sekf_exp --wd $WD
 
 # To re-configure your config and (re-)create exp_configuration.json
 poetry run PySurfexExpConfig -exp_name my_sekf_exp --wd $WD
 
 # To start you experiment
 poetry run PySurfexExp start -dtg 202301010300 -dtgend 202301010600


The second approach is to create a self-contained configuration file, can be started.
The altering of the configuration must then be done by applying a defined configuration or a configuration file with patches from original configuration.
Here is an example with CARRA2.

.. code-block:: bash
 cd ~/projects/pysurfex-experiment

 # Create experiment in file CARRA2_MINI_NEW.json
 poetry run PySurfexExpSetup -exp_name CARRA2_MINI -experiment $PWD -offline /perm/sbu/git/carra/CARRA2-Harmonie/ -host ECMWF-atos --config carra2 -o CARRA2_MINI.json
  
 # Run experiment from config file CARRA2_MINI_NEW.json
 poetry run PySurfexExp start -exp_name CARRA2_MINI -dtg "2017-09-01T03:00:00Z" -dtgend "2017-09-01T06:00:00Z" -config CARRA2_MINI.json



Following host tags are tested:

 * ECMWF-atos (ATOS at ECMWF)
 * ppi-rhel8  (RH8 PPI at met.no)
 * nebula     (nebula.nsc.liu.se)
 
 The experiment specific file exp_dependencies.json will tell you the location of the system dependent files.
 You might want to override them with local copies if needed.

Extra environment on PPI-RHEL8 needed to start experiments
---------------------------------------------------------------

.. code-block:: bash

 module use /modules/MET/rhel8/user-modules/
 module load ecflow/5.8.1
 export ECF_SSL=1
 export UDUNITS2_XML_PATH=/usr/share/udunits/udunits2.xml


Trainings
-----------------------

`Budapest May 2022 <https://github.com/metno/pysurfex-experiment/blob/master/trainings/budapest_may_2022.rst/>`_ (Old version)
