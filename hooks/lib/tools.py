#!/usr/bin/env python
import argparse
import re
from dulwich.repo import Repo


class NotComparableVersions(Exception):
    pass


def get_parser_pc():
    """
    Build the parser for patchset-created hook type
    """
    parser = argparse.ArgumentParser(
        description=('This dispatcher handles the'
                     ' special tags and hook'
                     ' execution'),
    )
    for arg in ('change', 'project', 'branch', 'commit'):
        parser.add_argument('--' + arg,
                            action='store',
                            required=True)
    for arg in ('author', 'is-draft', 'change-url', 'comment', 'uploader',
                'patchset', 'topic'):
        parser.add_argument('--' + arg,
                            action='store',
                            required=False)
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
    return parser


def ver_is_newer(branch1, branch2):
    """
    Returns true if branch1 isnewer than branch2, according to:

    (X+1).Y > X.(Y+1) > X.Y > X.Y.Z
    """
    try:
        ## Special case for master
        if branch1 == 'master' and branch2 != 'master':
            return True
        elif branch2 == 'master' and branch1 != 'master':
            return False
        elif branch1 == branch2:
            return False
        ## strip the non-numbered part
        if '-' in branch1:
            branch1 = branch1.rsplit('-', 1)[1]
        if '-' in branch2:
            branch2 = branch2.rsplit('-', 1)[1]
        ## get the first digit of the version string
        if '.' in branch1:
            b1_maj, b1_rest = branch1.split('.', 1)
        else:
            b1_maj = branch1
            b1_rest = None
        if '.' in branch2:
            b2_maj, b2_rest = branch2.split('.', 1)
        else:
            b2_maj = branch2
            b2_rest = None
        ## make sure we have integers as majors
        b1_maj = int(b1_maj)
        b2_maj = int(b2_maj)
        ## Check which one is newer
        if b1_maj > b2_maj:
            return True
        elif b2_maj > b1_maj:
            return False
        else:
            ## in case the majors match, strip them and check again
            if b1_rest and b2_rest:
                return ver_is_newer(b1_rest, b2_rest)
            ## if b1=X and b2=X.Y, b1 is newer
            elif b2_rest:
                return True
            ## if b1=X.Y and b2=X, b1 is newer
            elif b1_rest:
                return False
    except (IndexError, ValueError):
        raise NotComparableVersions(
            "Unable to parse version strings (%s, %s)"
            % (branch1, branch2))


def get_branches(repo_path):
    repo = Repo(repo_path)
    return [ref[11:] for ref in repo.get_refs()
            if ref.startswith('refs/heads/')]


def get_newer_branches(my_branch, repo_path):
    newer = []
    ignore_match = re.compile(r'[^.]*-\d+\.\d+\..*')
    for branch in get_branches(repo_path):
        if ignore_match.match(branch):
            continue
        try:
            if ver_is_newer(branch, my_branch):
                newer.append(branch)
        except NotComparableVersions:
            pass
    return newer
