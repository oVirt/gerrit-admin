Some tips on configuring the hooks
------------------------------------

**NOTE**: make sure to check the latest docs for each programming language
under the `bash libs`_ or `python libs`_ pages, in the conf.sh/config libs
sections


As specified in the `bash libs`_ config.sh section, the hooks can get their
config from multiple places, the most common pattern is to have a generic
configuration file and a per-project one (both are supported also by the python
hooks, any other is bash-specific, more on than on `Bash hooks`_).

So usually you'd have a *config* file under */home/gerrit2/review_site/hooks*
with the general options, like admin email and such. For a list of the needed
options check on the `hooks`_ section for whichever hooks you have configured.

That file should be a valid shell script, as it will be sourced on runtime and
right now there's a limitation that all the values must be on the same line as
the variable name (for python hooks to pick them up).

For example::

    #!/bin/bash
    ## Credentials to use when connecting to bugzilla
    BZ_USER='something@somewh.ere'
    BZ_PASS='supersecterpass'

    ## Gerrit credentials/url used to review the patches (through ssh cli)
    GERRIT_SRV="user@gerrit.server"

    ## Tracker id on bugzilla for the autotracker hook
    ## 81 -> oVirt gerrit
    TRACKER_ID='81'
    TRACKER_NAME="oVirt gerrit"

    PRODUCT='oVirt'
    PRODUCTS=('oVirt' 'Red Hat Enterprise Virtualization Manager')
    CLASSIFICATION='oVirt'

If there's anything that's specific for a project (like branches and tags) that
will go under the project's git repo, under *hooks/cofing*, for example, if the
project was named ovirt-engine.git, the config file at
*/home/gerrit2/review_site/git/ovirt-engine.git/hooks/config* might be::

    #!/bin/bash
    ## Branches to take into account
    BRANCHES=('ovirt-engine-3.6' 'ovirt-engine-3.6.0' 'ovirt-engine-3.6.1' 'ovirt-engine-3.6.2')
    STABLE_BRANCHES="ovirt-engine-3.6 ovirt-engine-3.6.5 ovirt-engine-3.6.6"
    CHECK_TARGET_RELEASE=("ovirt-engine-3.6|^3\.[6543210].*")
    CHECK_TARGET_MILESTONE=('ovirt-engine-3.6|^.*3\.6.*')
    PRODUCT="oVirt"

Those values will be available only to hooks for that project, and will
override any parameter in the more generic config (like *PRODUCT* here).


Bash hooks
===========

If you are using bash hooks, there are a few more levels of config supported,
those are:

* Per project + chain, for example::
    /home/gerrit2/git/ovirt-engine.git/hooks/bz.config
* Per project + chain + event, like::
    /home/gerrit2/git/ovirt-engine.git/hooks/bz.change-merged.config
* Per project + chain + event + hook::
    /home/gerrit2/git/ovirt-engine.git/hooks/bz.change-merged.99.review_ok.config

Those are not used usually and are meant only for very specific cases.

.. _bash libs: Bash_libs.html
.. _python libs: Python_libs.html
.. _hooks: index.html#hooks
