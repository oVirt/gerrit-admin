#!/usr/bin/env python
"""
functions.py
-------------
This file holds all the hook functions
"""
import os
import logging
import sys
import socket
import re
import ast
from config import load_config
from gerrit import Gerrit
from bz import Bugzilla, WrongProduct
from tools import get_parser_pc, get_newer_branches, get_branches
from termcolor import colored
logger = logging.getLogger(__name__)


class NotRelevant(Exception):
    """
    Customized exception for checks that should be ignored
    (master branch, no bug url)
    """
    def __init__(self, message):
        message = '{0}::{1}'.format(HDR, message)
        print_review_results(message)
        print_title('END HOOK: ' + FNAME)
        sys.exit(0)


def set_globals(hdr, fname):
    """
    Sets global variables

    :param hdr: hook header string (i.e '* Check Bug-Url')
    :param fname: hook name string (i.e 'check_bug_url')
    """
    global HDR, FNAME, HOOK_NAME
    HDR, FNAME, HOOK_NAME = hdr, fname, fname.split('.')[-1]


def init_logging(verbose=False, log_file=False):
    """
    Initialize logging

    :param verbose: boolean, if set to True setting log level to DEBUG
    :param log_file: boolean, if set to True writes logs to a file
    """
    if verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    if log_file:
        log_name = HOOK_NAME + '.log'
        log_path = os.path.join(os.path.dirname(__file__), '..', 'logs')
        logging.basicConfig(
            filename=os.path.join(log_path, log_name),
            level=log_level,
            format=(
                '%(asctime)s::' + str(os.getpid()) +
                '::%(levelname)s::%(message)s'
            )
        )
    else:
        logging.basicConfig(
            level=log_level,
            format=(
                '%(asctime)s::' + str(os.getpid()) +
                '::%(levelname)s::%(message)s'
            )
        )


def print_review_results(
    message, cr_value='0', v_value='0',
):
    """
    Prints the review results

    :param message: the review message
    :param cr_value: code-review value
    :param v_value: verified value
    """
    if v_value != '0':
        message += " ({0})".format(v_value)

    review_results = "\n".join((cr_value, v_value, message))
    print review_results


def check_config(config):
    """
    Check that all the necessary configuration values are defined

    :param config: dict of configuration keys and values
    """
    not_defined_confs = [
        elem for elem
        in (
            'BZ_USER', 'BZ_PASS', 'BZ_SERVER',
            'GERRIT_SRV', 'PRODUCTS', 'TRACKER_ID',
            'CLASSIFICATIONS',
        )
        if elem not in config
    ]

    if not_defined_confs:
        logger.error("Missing configuration values {0}".format(
            ', '.join(not_defined_confs)))
        sys.exit(1)


def print_title(title):
    """
    Prints the title with line of dashes above and below

    :param title: title name (start/end hook: <hook name>)
    """
    logger.debug(colored('-' * len(title), 'blue'))
    logger.debug(colored("{0}".format(title), 'cyan'))
    logger.debug(colored('-' * len(title), 'blue'))


def get_configuration():
    """
    Gets configuration parameters from config file

    :return: dict of config keys and values
    """
    # load the configuration file
    config = load_config()

    # check the configuration file
    check_config(config=config)

    # set bugzilla url
    config['BZ_URL'] = config['BZ_SERVER'] + '/xmlrpc.cgi'

    for option in ['CLASSIFICATIONS', 'PRODUCTS']:
        config[option] = config[option].split(',') \
            if config[option] is not None or config[option] != '' else []

    logger.debug("==> config: {0}".format(config))
    logger.debug("==> bz user: {0}".format(config['BZ_USER']))
    logger.debug("==> bz password: {0}".format(config['BZ_PASS']))
    logger.debug("==> bz url: {0}\n".format(config['BZ_URL']))

    return config


def set_objects(config):
    """
    Sets bugzilla and gerrit objects

    :param config: dict of configuration keys and values
    :return: bugzilla and gerrit objects
    """

    # set bugzilla object
    bz_obj = Bugzilla(
        user=config['BZ_USER'],
        passwd=config['BZ_PASS'],
        url=config['BZ_URL'],
    )

    # set gerrit object
    gerrit_obj = Gerrit(config['GERRIT_SRV'])

    return bz_obj, gerrit_obj


def get_arguments():
    """
    Get arguments

    :return: args object with all the received parameters
    """
    logger.debug("==> received params: {0}".format(sys.argv))
    parser = get_parser_pc()
    args, unknown = parser.parse_known_args()
    logger.debug("==> args: {0}\n".format(args))

    ignore_master = [
        'check_product', 'check_target_milestone', 'set_modified'
    ]

    if HOOK_NAME in ignore_master and 'master' in args.branch:
        message = "IGNORE, not relevant for branch: {0}".format(args.branch)
        raise NotRelevant(message)

    return args


def get_commit_message(gerrit_obj, commit):
    """
    Get bug urls from commit message

    :param gerrit_obj: gerrit object
    :param commit: patch commit id
    :return: string of the commit message
    """

    # get the change from commit id
    change = gerrit_obj.query(commit)[0]
    logger.debug("==> change: {0}".format(change))

    # return commit message
    return change.get('commitMessage')


def get_bug_ids(bz_obj, bug_urls):
    """
    Get bug ids from patch commit message

    :param bz_obj: bugzilla object
    :param bug_urls: list of bug urls
    :return: list of bug ids
    """
    # get bug ids from bug urls
    bug_ids = bz_obj.get_bug_ids(bug_urls=bug_urls)
    logger.debug("==> bug_ids: {0}\n".format(bug_ids))

    return bug_ids


def get_bug_urls(bz_obj, gerrit_obj, commit, bz_server):
    """
    Get bug url/s from patch commit message

    :param bz_obj: bugzilla object
    :param gerrit_obj: gerrit object
    :param commit: patch commit id
    :param bz_server: bugzilla server
    :return: list of bug urls
    """
    # get bug url\s from the commit message
    bug_urls = bz_obj.get_bug_urls(
        commit=get_commit_message(gerrit_obj=gerrit_obj, commit=commit),
        bz_server=bz_server
    )
    logger.debug("==> bug_urls: {0}".format(bug_urls))

    if not bug_urls:
        message = "IGNORE, no bug url/s found"
        raise NotRelevant(message)

    return bug_urls


def get_bug_info(bz_obj, bug_id):
    """
    Get bug information from the passed bug id

    :param bz_obj: bugzilla object
    :param bug_id: bug id
    :return: tuple of object with all the bug info and a reason string
    """
    reason = ''
    bug_info = None

    logger.debug("==> checking bug_id: {0}".format(bug_id))
    try:
        bug_info = bz_obj.extract_bug_info(bug_id=bug_id)

        if bug_info is None:
            reason = "(private bug or bug doesn't exist)"

    except socket.gaierror:
        reason = "(network issues). Please contact infra@ovirt.org."

    return bug_info, reason


def check_bug_url(bz_obj, bug_urls, branch, classifications, products):
    """
    Validate the bug url

    :param bz_obj: bugzilla object
    :param bug_urls: list of bug urls
    :param branch: patch branch
    :param classifications: list of classifications
    :param products: list of products
    :return: tuple of message and cr_value
    """
    warn = False
    v_value = "0"
    cr_value = "0"
    messages = []
    skip_branches = ['master', 'refs/meta/config', 'meta/config']

    if not bug_urls:
        if branch in skip_branches:
            status = "IGNORE, no bug url/s found "
            status += "(optional for '{0}' branch, ".format(branch)
            status += "but mandatory for 'stable' branches)"
        else:
            status = "WARN, no bug url/s found"
            warn = True

        message = "{0}::{1}".format(HDR, status)
        messages = [message]
    else:
        for bug_url in bug_urls:

            bug_id = re.findall(r'\d+\b', bug_url)[0]

            # check that we receive bug info
            bug_info, reason = get_bug_info(bz_obj=bz_obj, bug_id=bug_id)

            if bug_info is None:
                status = "WARN, failed to get bug info "
                status += reason if reason != '' else ''
                if branch not in skip_branches:
                    warn = True
            else:
                classification = bug_info.classification
                logger.debug("==> classification: {0}".format(classification))
                product = bug_info.product
                logger.debug("==> product: {0}".format(product))

                if classification in classifications or product in products:
                    status = "OK, classification: '{0}'".format(classification)
                    status += ", product: '{0}'".format(product)
                else:
                    status = "IGNORE, not relevant for "
                    status += "classification: '{0}'".format(classification)
                    status += ", product: {0}".format(product)

            message = "{0}::{1}::{2}".format(HDR, bug_id, status)
            messages.append(message)

    if warn:
        v_value = "-1"

    return "\n".join(messages), v_value, cr_value


def check_tracker(gerrit_obj, tracker_number, branch):
    """
    Check that the external tracker is MERGED by querying gerrit

    :param gerrit_obj: gerrit object
    :param tracker_number: external tracker number (gerrit patch number)
    :param branch: patch branch (i.e ovirt-engine-4.1)
    :return: bool value, True if the change is not MERGED, False otherwise
    """
    if tracker_number is None:
        return False

    changes = gerrit_obj.query(tracker_number)
    for change in changes:
        if not change.get('status'):
            continue

        # verify that the patch branch is the same as the change branch
        # to make sure that we are checking the right change
        if change.get('branch') == branch:
            change_status = change['status']
            if change_status != 'MERGED':
                return True

    return False


def check_external_trackers(trackers, gerrit_obj, change):
    """
    Check external trackers for an open patches or status other than MERGED

    :param trackers: list of trackers
    :param gerrit_obj: gerrit object
    :param change: dict with patch information
    :return: tuple of status string and warn bool value
    """
    if not trackers:
        status = "WARN, can't change bug status to 'MODIFIED' "
        status += "(no external tracker info found)"
        return status, True

    for tracker in trackers:
        if not tracker.get('type'):
            continue

        description = tracker['type'].get('description')
        if description is None or description != 'oVirt gerrit':
            continue

        tracker_number = tracker.get('ext_bz_bug_id')
        if check_tracker(
            gerrit_obj=gerrit_obj, tracker_number=tracker_number,
            branch=change.get('branch'),
        ):
            status = "WARN, can't change bug status to 'MODIFIED' "
            status += "(There are still open patches)"
            return status, True

    return '', False


def set_status(bz_obj, bug_id, change, bug_info, gerrit_obj):
    """
    Sets bug status to 'MODIFIED' only if the current status is 'POST'

    :param bz_obj: bugzilla object
    :param bug_id: bug number
    :param change: dict with patch information
    :param bug_info: bug object
    :param gerrit_obj: gerrit object
    :return: status message string
    """
    change_status = change.get('status')
    bug_status = bug_info.status if hasattr(bug_info, 'status') else ''
    logger.debug("==> patch status: {0}".format(change_status))
    logger.debug("==> bug status: {0}\n".format(bug_status))

    if HOOK_NAME == 'set_modified':
        # ignore bugs that their status already on 'MODIFIED'
        if bug_status == 'MODIFIED':
            return "IGNORE, bug is already on '{0}' status".format(bug_status)

        # ignore bugs that their status other than 'POST'
        if bug_status != 'POST':
            return "IGNORE, not relevant for bug with '{0}' status".format(
                bug_status)

        # ignore patches that their status other than 'MODIFIED'
        if change_status != 'MODIFIED':
            return "IGNORE, not relevant for patch with '{0}' status".format(
                change_status)

        if bug_status == 'POST' and change_status == 'MODIFIED':
            trackers = bug_info.external_bugs \
                if hasattr(bug_info, 'external_bugs') else ''

            # if we have open patches, return a warn message
            status, warn = check_external_trackers(
                trackers=trackers, gerrit_obj=gerrit_obj, change=change
            )
            if not warn:
                # if the change branch doesn't match the bug milestone,
                # check that the branch for that milestone doesn't exist,
                # if it exist return warn status message
                status, warn = cmp_change_branch_and_bug_tm(
                    bug_info=bug_info, change=change)
            if warn:
                return status

    if HOOK_NAME == 'set_post':
        # ignore bugs that their status already on 'POST'
        if bug_status == 'POST':
            return "IGNORE, bug is already on '{0}' status".format(bug_status)

        # ignore bugs that their status other than 'NEW' or 'ASSIGNED'
        if bug_status not in ['NEW', 'ASSIGNED']:
            return "IGNORE, not relevant for bug with '{0}' status".format(
                bug_status)

    try:
        bz_obj.update_bug(bug_id=bug_id, status=change_status)
        status = "OK, bug status updated to '{0}'".format(change_status)
    except socket.error as err:
        status = "ERROR, failed to change bug status ({0})".format(err)
    return status


def get_version_suffix(string):
    """
    Get version suffix from string

    :param string: string with
    :return: version suffix
    """
    pattern = r'\d+(\.\d)+\b'
    search_pattern = re.search(pattern=pattern, string=string)
    suffix = search_pattern.group() if search_pattern is not None else ''

    return suffix


def cmp_change_branch_and_bug_tm(bug_info, change):
    """
    Compare change branch suffix with bug target milestone suffix

    :param bug_info: bug object
    :param change: dict with patch information
    :return: tuple of status string and bool value
    """
    bm = bug_info.milestone if hasattr(bug_info, 'milestone') else ''
    logging.debug("==> bug milestone: {0}".format(bm))
    cb = change.get('branch')
    logging.debug("==> patch branch: {0}".format(cb))

    if not bm or bm == '---':
        status = "WARN, bug status won't be changed to MODIFIED "
        status += "(milestone: '{0}')".format(bm)
        return status, True

    # get bug milestone suffix version (ovirt-X.Y.Z ==> X.Y.Z)
    bm_suffix = get_version_suffix(string=bm)
    logging.debug("==> milestone suffix: {0}".format(bm_suffix))

    # get change branch suffix version (ovirt-engine-X.Y.Z ==> X.Y.Z)
    cb_suffix = get_version_suffix(string=cb)
    logging.debug("==> branch suffix: {0}".format(cb_suffix))

    # if bug milestone suffix version not equal to change brunch suffix
    # version, the bug status should be changed from POST ==> MODIFIED
    # only if the newer branch doesn't exist
    if bm_suffix != cb_suffix:

        # get all the branches for the current git project
        branches = get_branches(repo_path=os.environ['GIT_DIR'])

        nb = ''
        # check if newer branch exist
        pattern = re.compile(r'.*' + bm_suffix + r'.*')
        for branch in branches:
            search_obj = re.search(pattern, branch)
            if search_obj is not None:
                nb = search_obj.group()
                break

        if nb != '':
            status = "WARN, bug status won't be changed to MODIFIED "
            status += "(detected a newer branch '{0}' ".format(nb)
            status += "that matches the milestone)"
            return status, True

    return '', False


def update_bug_status(
        bz_obj, gerrit_obj, bug_ids, change, classifications, products,
        draft=None
):
    """
    Update bugs status only for the specified classification

    :param bz_obj: bugzilla object
    :param gerrit_obj: gerrit object
    :param bug_ids: list of bug ids
    :param change: dict with patch information
    :param classifications: list of classifications
    :param products: list of products
    :param draft: bool value (true if it's draft patch, false otherwise)
    :return: tuple of message and v_value
    """
    v_value = "0"
    cr_value = "0"
    messages = []

    for bug_id in bug_ids:

        bug_info, reason = get_bug_info(bz_obj=bz_obj, bug_id=bug_id)
        if bug_info is None:
            status = "WARN, failed to get bug info "
            status += reason if reason != '' else ''
            message = "{0}::#{1}::{2}".format(HDR, bug_id, status)
            return message, v_value, cr_value

        change_status = change.get('status')

        # for set_post hook, if patch status is 'NEW'
        # and the patch is not a draft, replace its status to POST
        if HOOK_NAME == 'set_post' and change_status == 'NEW':
            draft = ast.literal_eval(draft.capitalize())
            if not draft:
                change['status'] = 'POST'

        # for set_modified hook, if change (patch) status is 'MERGED',
        # replace the patch status to 'MODIFIED'
        if HOOK_NAME == 'set_modified' and change_status == 'MERGED':
            change['status'] = 'MODIFIED'

        classification = bug_info.classification
        logger.debug("==> classification: {0}".format(classification))
        product = bug_info.product
        logger.debug("==> product: {0}".format(product))

        if classification in classifications or product in products:
            status = set_status(
                bz_obj=bz_obj, bug_id=bug_id, change=change,
                bug_info=bug_info, gerrit_obj=gerrit_obj)
        else:
            status = "IGNORE, not relevant for "
            status += "classification: '{0}'".format(classification)
            status += ", product: '{0}'".format(product)

        message = "{0}::#{1}::{2}".format(HDR, bug_id, status)
        messages.append(message)

    return "\n".join(messages), v_value, cr_value


def get_change(gerrit_obj, commit):
    """
    Get change info from commit message

    :param gerrit_obj: gerrit object
    :param commit: patch commit id
    :return: dict with change info
    """
    # get the change from commit id
    change = gerrit_obj.query(commit)[0]
    logger.debug("==> change: {0}".format(change))
    for key, value in change.items():
        if key == 'commitMessage':
            continue

        logger.debug("==> {0}: {1}".format(key, value))

    return change


def check_branches(changes, newer_branches, current_branch):
    """
    Checks that patch branch is in the newer branches list

    :param changes: list with changes
    :param newer_branches: list with newer branches
    :param current_branch: string of the current branch
    :return: tuple of
        - merged branches list with patch status: open
        - merged branches list with patch status: close
        - not relevant branches list (branches that have the required
          change id but aren't in the newer branches list)
        - not merged branches list (branches that don't have the required
          change id and are in the newer branches list)
    """
    mb_open_patch = []              # merged branches with open patches
    mb_close_patch = []             # merged branches with close patches
    nr_branches = []                # not relevant branches
    nm_branches = newer_branches    # not merged branches

    for change in changes:
        try:
            branch = change['branch']
        except KeyError:
            continue

        if branch == current_branch:
            continue

        if branch not in nm_branches:
            nr_branches.append(branch)
            continue

        if change['status'] == 'MERGED':
            mb_close_patch.append(branch)
        elif change['open']:
            mb_open_patch.append(branch)

        # remove branch from not merged branches list
        nm_branches.remove(branch)

    return {
        "nm_branches": nm_branches, "mb_open_patch": mb_open_patch,
        "mb_close_patch": mb_close_patch, "nr_branches": nr_branches
    }


def check_patch_merged(branches):
    """
    Checks that the patch was merged to the relevant (newer) stable branches

    :param branches: dictionary with branches lists:
    nm_branches: list of not merged branches
    mb_open_patch: list of merged branches with open patch
    mb_close_patch:  list of merged branches with close patch
    nr_branches: list with not relevant branches
    :return: tuple with message and bool value
    """
    warn = False
    v_value = "0"
    cr_value = "0"
    status = ''

    # if patch wasn't merged to all the relevant branches, show WARN message
    if branches["nm_branches"] or branches["mb_open_patch"]:
        status = "WARN, The patch wasn't backported to all the relevant "
        status += "stable branches."
        warn = True
        if branches["mb_open_patch"]:
            b_word = \
                'branches' if len(branches["mb_open_patch"]) > 1 else 'branch'
            status += " It is still open in the following {0}: '{1}'.".format(
                b_word, ', '.join(branches["mb_open_patch"])
            )
    elif branches["mb_close_patch"]:
            status = "OK, The patch backported to all the relevant "
            status += "stable branches."

    if branches["nr_branches"]:
        b_word = 'branches' if len(branches["nr_branches"]) > 1 else 'branch'
        status += " In addition the patch was found "
        status += "in the following {0}: '{1}' ".format(
            b_word, ', '.join(branches["nr_branches"])
        )

    message = "{0}::{1}".format(HDR, status)

    if warn:
        v_value = "-1"

    return message, v_value, cr_value


def check_backport(gerrit_obj, change_id, current_branch, project):
    """
    Checks that the patch was merged to the relevant (newer) stable branches

    :param gerrit_obj: gerrit object
    :param change_id: patch change id
    :param current_branch: current_branch (i.e master, ovirt-engine-3.6.9)
    :param project: project (i.e ovirt-engine)
    :return: tuple of message and v_value
    """
    if 'master' in current_branch:
        message = 'IGNORE, not relevant for branch: {0}'.format(current_branch)
        NotRelevant(message)

    # get newer branches than the current branch
    newer_branches = get_newer_branches(
        current_branch, os.environ['GIT_DIR']
    )
    logger.debug("==> relevant_branches: {0}".format(newer_branches))

    # get all the changes that have the same change_id
    changes = gerrit_obj.query(change_id + ' project:' + project)
    logger.debug("==> changes: {0}".format(changes))

    # check if current branch exist in the newer branches list
    branches = check_branches(
        changes=changes, newer_branches=newer_branches,
        current_branch=current_branch
    )

    return check_patch_merged(branches=branches)


def get_maj_version(full_version):
    """
    Extract major version out of full version

    :param full_version: full version (i.e *-X.Y.Z[-*] or *-X.Y[-*])
    :return: string with major version (i.e X.Y)
    """
    regex_version = r'\d+.\d+\b'

    # get major version of branch or target milestone
    version = re.findall(regex_version, full_version)

    # if target milestone empty or equal to '---' return '999.999'
    maj_version = version[0] if version else '999.999'

    return maj_version


def check_clone_flags(flags, tm_maj_version):
    """
    Check for clone flags for the passed tm major version
    :param flags: list of flags
    :param tm_maj_version: tm major version (i.e 3.6)
    :return: status string
    """

    for flag in flags:
        if tm_maj_version in flag:
            status = "OK, found clone candidate '{0}' ".format(flag)
            status += "for target milestone"
            break
    else:
        status = "WARN, no clone candidate for target milestone"

    return status


def check_target_milestone(bz_obj, bug_ids, branch, classifications):
    """
    Checks that the bug target milestone is the same as the
    patch Branch version

    :param bz_obj: bugzilla object
    :param bug_ids: list of bug ids
    :param branch: branch (i.e ovirt-engine-3.6.9)
    :param classifications: list of classifications
    :return: tuple of message and cr_value
    """
    warn = False
    v_value = "0"
    cr_value = "0"
    messages = []

    for bug_id in bug_ids:
        bug_info, reason = get_bug_info(bz_obj=bz_obj, bug_id=bug_id)

        if bug_info is None:
            message = "{0}::#{1}::WARN, failed to get bug info ".format(
                HDR, bug_id)
            message += reason if reason != '' else ''
            messages.append(message)
            continue

        classification = bug_info.classification
        logger.debug("==> classification: {0}".format(classification))

        tm = bug_info.milestone
        logger.debug("==> target milestone: {0}".format(tm))

        # check for 'oVirt' classification
        if classification not in classifications:
            message = (
                "{0}::#{1}::IGNORE, not relevant for '{2}' "
                "classification".format(HDR, bug_id, classification))
            messages.append(message)
            continue

        if tm == "---":
            message = "{0}::#{1}::WARN, target milestone: '{2}'".format(
                HDR, bug_id, tm)
            messages.append(message)
            warn = True
            continue

        logger.debug("==> branch: {0}".format(branch))

        # get branch major version
        branch_maj_version = get_maj_version(branch)
        logger.debug("==> branch_maj_version: {0}".format(branch_maj_version))

        # get target milestone major version
        tm_maj_version = get_maj_version(tm)
        logger.debug("==> tm_maj_version: {0}".format(tm_maj_version))

        # check that branch major version matches
        # target milestone major version
        if branch_maj_version == tm_maj_version:
            status = "OK, target milestone"
        # if branch maj version larger than target milestone maj
        # version, check for clone candidate flags
        elif float(branch_maj_version) > float(tm_maj_version):
            status = check_clone_flags(
                flags=bug_info.flags, tm_maj_version=tm_maj_version)
        else:
            status = "WARN, wrong target milestone"
            warn = True

        message = "{0}::#{1}::{2}: '{3}'".format(HDR, bug_id, status, tm)
        messages.append(message)

    if warn:
        v_value = "-1"

    return "\n".join(messages), v_value, cr_value


def check_product(bz_obj, bug_ids, project, classifications):
    """
    Checks that bug product is the same as patch project

    :param bz_obj: bugzilla object
    :param bug_ids: list of bug ids
    :param project: patch project (i.e ovirt-engine)
    :param classifications: list of classifications
    :return: tuple of message and cr_value
    """
    warn = False
    v_value = "0"
    cr_value = "0"
    messages = []

    for bug_id in bug_ids:
        bug_info, reason = get_bug_info(bz_obj=bz_obj, bug_id=bug_id)

        if bug_info is None:
            message = "{0}::#{1}::WARN, failed to get bug info ".format(
                HDR, bug_id)
            message += reason if reason != '' else ''
            messages.append(message)
            continue

        product = bug_info.product
        logger.debug("==> product: {0}".format(product))
        logger.debug("==> project: {0}".format(project))

        classification = bug_info.classification
        logger.debug("==> classification: {0}".format(classification))

        # check for 'oVirt' classification
        if classification in classifications:
            if project == product:
                status = 'OK, product'
            else:
                status = 'WARN, wrong product'
                warn = True

            message = "{0}::#{1}::{2}: {3}".format(
                HDR, bug_id, status, product
            )
        else:
            message = "{0}::#{1}::IGNORE, ".format(HDR, bug_id)
            message += "not relevant for '{0}' classification".format(
                classification
            )
        messages.append(message)

    if warn:
        v_value = "-1"

    return "\n".join(messages), v_value, cr_value


def update_tracker(
        bz_obj, bug_ids, change, tracker_id, branch, draft,
        classifications, products,
):
    """
    Update bugzilla external tracker info

    :param bz_obj: bugzilla object
    :param bug_ids: list of bug ids
    :param change: change object
    :param tracker_id: external tracker id (i.e: 81 --> oVirt gerrit)
    :param branch: patch branch
    :param draft: 'true' string if it's a draft patch, 'false' string otherwise
    or None if it's a merge
    :param classifications: list of classifications
    :param products: list of products
    :return: tuple of message and cr_value
    """
    v_value = "0"
    cr_value = "0"
    messages = []

    draft = ast.literal_eval(draft.capitalize()) if draft else None

    for bug_id in bug_ids:
        logger.debug("==> updating tracker with bug_id: {0}\n".format(bug_id))

        bug_info, reason = get_bug_info(bz_obj=bz_obj, bug_id=bug_id)

        if bug_info is None:
            status = "WARN, failed to get bug info "
            status += reason if reason != '' else ''
        else:
            # if the patch status is 'NEW' and it's not a draft patch,
            # replace the patch status to 'POST'
            if change['status'] == 'NEW' and not draft:
                change['status'] = 'POST'

            classification = bug_info.classification
            logger.debug("==> classification: {0}".format(classification))
            product = bug_info.product
            logger.debug("==> product: {0}".format(product))

            if classification in classifications or product in products:
                try:
                    bz_obj.update_external(
                        bug_id=bug_id, external_bug_id=change['number'],
                        ext_type_id=tracker_id, description=change['subject'],
                        status=change['status'], branch=branch,
                    )
                except WrongProduct, exc:
                    status = "WARN, failed to update external tracker ({0})"
                    status = status.format(exc.message)
                else:
                    status = "OK, tracker status updated to '{0}'"
                    status = status.format(change['status'])
            else:
                status = "IGNORE, not relevant for "
                status += "classification: '{0}', product: '{1}'"
                status = status.format(classification, product)

        message = "{0}::#{1}::{2}".format(HDR, bug_id, status)
        messages.append(message)

    return "\n".join(messages), v_value, cr_value


def run_hook_func(*args):
    """
    Run function for a particular hook

    :param args: local arguments
    :return: message, v_value, cr_value
    """
    for arg in args:

        logger.debug("==> hook name: {0}".format(HOOK_NAME))

        # check if bug url exist
        if HOOK_NAME == 'check_bug_url':
            return check_bug_url(
                bz_obj=arg['bz_obj'], bug_urls=arg['bug_urls'],
                branch=arg['args'].branch, products=arg['config']['PRODUCTS'],
                classifications=arg['config']['CLASSIFICATIONS'],
            )

        # check bug product and patch project
        if HOOK_NAME == 'check_product':
            return check_product(
                bz_obj=arg['bz_obj'], bug_ids=arg['bug_ids'],
                project=arg['args'].project,
                classifications=arg['config']['CLASSIFICATION'],
            )

        # check target milestone and patch branch
        if HOOK_NAME == 'check_target_milestone':
            return check_target_milestone(
                bz_obj=arg['bz_obj'], bug_ids=arg['bug_ids'],
                branch=arg['args'].branch,
                classifications=arg['config']['CLASSIFICATION'],
            )

        # checks that the patch was merged to all the relevant stable branches
        if HOOK_NAME == 'check_backport':
            return check_backport(
                gerrit_obj=arg['gerrit_obj'], project=arg['args'].project,
                change_id=arg['change']['id'],
                current_branch=arg['args'].branch,
            )

        # update bug status
        if HOOK_NAME in ['set_post', 'set_modified']:
            return update_bug_status(
                bz_obj=arg['bz_obj'], gerrit_obj=arg['gerrit_obj'],
                bug_ids=arg['bug_ids'], draft=arg['args'].is_draft,
                change=arg['change'], products=arg['config']['PRODUCTS'],
                classifications=arg['config']['CLASSIFICATIONS'],
            )

        # update external tracker
        if HOOK_NAME == 'update_tracker':
            return update_tracker(
                bz_obj=arg['bz_obj'], bug_ids=arg['bug_ids'],
                draft=arg['args'].is_draft, change=arg['change'],
                products=arg['config']['PRODUCTS'], branch=arg['args'].branch,
                tracker_id=arg['config']['TRACKER_ID'],
                classifications=arg['config']['CLASSIFICATIONS'],
            )


def main(**kwargs):
    """
    Main function

    :param hdr: hook header (i.e '* Check Bug-Url')
    :param fname: hook name (i.e 'check_bug_url')
    """
    # set global variables
    set_globals(hdr=kwargs['hdr'], fname=kwargs['fname'])

    # initialize logging
    init_logging(verbose=True)
    print_title('START HOOK: ' + FNAME)

    # get all passed arguments
    args = get_arguments()

    # get configuration
    config = get_configuration()

    # set bugzilla and gerrit objects
    bz_obj, gerrit_obj = set_objects(config=config)

    # get bug urls
    bug_urls = get_bug_urls(
        bz_obj=bz_obj, gerrit_obj=gerrit_obj, commit=args.commit,
        bz_server=config['BZ_SERVER'])

    # get bug ids
    if HOOK_NAME in [
        'check_target_milestone', 'check_product', 'set_post',
        'set_modified', 'update_tracker'
    ]:
        bug_ids = get_bug_ids(bz_obj=bz_obj, bug_urls=bug_urls)

    # get gerrit change
    if HOOK_NAME in [
        'check_backport', 'set_post', 'set_modified', 'update_tracker'
    ]:
        change = get_change(gerrit_obj=gerrit_obj, commit=args.commit)

    # run specific hook function according to the hook name
    message, v_value, cr_value = run_hook_func(locals())

    # prints the message, verify and code review values
    print_review_results(message=message, v_value=v_value, cr_value=cr_value)
    print_title('END HOOK: ' + FNAME)
