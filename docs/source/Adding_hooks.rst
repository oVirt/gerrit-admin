Small tutorial on adding a new hook
====================================

Hello world
------------

To create a dummy hello world, you can just create a binary (C, C++, Python,
Ruby, Java, Go...) and put it under your project's git repo under the hooks
directory with the name::

    $gerrit_event.hello_world

For example, if we used a bash script, just::

   $ echo -e '#!/bin/bash\necho hello world' \
       > /home/gerrit2/review_site/git/lago.git/hooks/comment-added.hello_world
   $ chmod +x /home/gerrit2/review_site/git/lago.git/hooks/comment-added.hello_world

And our hook would be run automatically on each new comment, and you will start
seeing some feedback on the comments, something like::

   * hello_word: hello world


Note that the stdout and stderr are shown only in the logs, we'll see later how
to do reviews.


Using some config values (bash only)
-------------------------------------

So, imagine that we wanted to get some configuration values extracted, to do
so, you have to source the conf.sh library (conveniently added to the path by
the hook dispacher), so an example could be::

    source conf.sh
    conf.load

    echo "Hello world, the config value of SOMETHING is $SOMETHING"

As you can see, all the configuration values that are defined on any of the
configuration files for that hook are now global variables.


Doing reviews (bash only)
--------------------------
If you want to add some custom values for the code review and verified flags,
your hook must adopt a specific format on it's output, but don't worry, there's
a function to help you with that, here's an example::

    source tools.sh
    code_review_value="-1"
    verified_value="1"
    message="Some helpful message here"
    tools.review "$code_review_value" "$verified_value" "$message"

That will add a review with a CR value of -1, and a V value of +1.

Skipping review flags
++++++++++++++++++++++
Something tricky here, as doing a review with 0 is not the same as not doing
it, if you want to skip the vote for the hook, you should use an empty string
for the CR/V flags value, like this::

    tools.review "" "" "Info message"

If you use '0' instead, the review value will be added to the list, and for the
reviews, the lowest value among all the hooks that ran is the one that
prevails, so if you have a +1 and a 0, 0 is the final value you will have.


Interacting with bugzilla (bash only)
--------------------------------------
Similar to the conf.sh, we have the bz.sh library, that will allow us to
interact with a bugzilla server, a simple example getting some info::

    source bz.sh
    source conf.sh

    conf.load

    bz.login "$BZ_USER" "$BZ_PASS" \
    || {
        message+="${message:+\n}* Bug-Url: ERROR, There was an error logging into bugzilla, "
        message+="please contact the administrator $CONTACT"
        tools.review "" "" "$message"
        bz.clean
        exit 2
    }
    bug_ids=($(bz.get_bug_id $commit))
    for bug_id in ${bug_ids[@]}; do
        prod="$(bz.get_product "$bug_id")"
        echo "Bug $bug_id has prod $prod"
    done
    bz.clean

**NOTE**: Make sure to run bz.clean at the end, that will get rid of any cache
and temporary configurations (to increase speed, bz.get uses a local cache for
the bugs)

Another interesting thing to point out, is that *bz.get_bug_id* call, that will
extract from the current commit (the one that triggered the hook) all the
*Bug-Url:* headers and return an array with the numerical bug ids.
