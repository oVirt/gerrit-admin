#!/bin/bash -e
lago init
lago start
lago deploy
lago copy-to-vm gerrit_server \
    hooks /gerrit_testsite/hooks
lago shell gerrit_server scripts/install_hook_dispatcher.sh


ip="$(lago status | grep ip:)"
echo "
###################################
You should make sure that you add this line to your /etc/hosts:

${ip##* } gerrit_server


For example with:
    echo "${ip##* }" | sudo tee -a /etc/hosts


Then you can go to http://gerrit_server:8080 and register a new user, it will
be created as admin.

NOTE: remember that you will have to add your user a username, and an ssh key

You can log into the gerrit server vm with:

    lago shell gerrit_server

The hook dispatcher is already installed, but there are no projects so you will
have to create at least one, and install there any hooks you want to try out.

The gerrit site dir is at /gerrit_testsite

Once done, you can remove it with:
    lago destroy -y


Also, I encourage you to use the bugzilla instance at:

    https://partner-bugzilla.redhat.com

Instead of the production one for any tests, as it's a testing instance that's
synced from the production one periodically.

Happy hacking!
"
