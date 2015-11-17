#!/usr/bin/env python
import os
import xmlrpclib
import re
from dulwich.repo import Repo
import logging
import argparse
import json
import sys


class WrongProduct(Exception):
    pass


class Bugzilla(object):
    def __init__(self, user=None, passwd=None,
                 url='https://bugzilla.redhat.com/xmlrpc.cgi'):
        self.rpc = xmlrpclib.ServerProxy(url)
        self.user = user
        self.passwd = passwd

    def wrap(self, dictionary):
        if self.user:
            dictionary['Bugzilla_login'] = self.user
        if self.passwd:
            dictionary['Bugzilla_password'] = self.passwd
        return dictionary

    def __getattr__(self, what):
        return getattr(self.rpc, what)

    def update_bug(self, bug_id, **fields):
        bug = self.wrap({
            'ids': bug_id,
        })
        bug.update(fields)
        return self.rpc.Bug.update(bug)['bugs']

    def get_external(self, bug_id, external_bug_id, ensure_product=None):
        bug = self.rpc.Bug.get(self.wrap({
            'ids': bug_id,
            'extra_fields': ['external_bugs'],
        }))
        if not bug['bugs']:
            logging.error("Unable to get bug %s\n%s"
                          % (str(bug_id), bug['faults']))
            return None
        # Only one response when asking by the commit hash
        bug = bug['bugs'][0]
        # check product
        if ensure_product is not None and bug['product'] != ensure_product:
            raise WrongProduct(bug['product'])
        for external in bug['external_bugs']:
            if external['ext_bz_bug_id'] == external_bug_id:
                return external
        return None

    def update_external(self, bug_id, external_bug_id, ext_type_id,
                        status=None, description=None, branch=None,
                        ensure_product=None):
        orig_external = self.get_external(
            bug_id,
            external_bug_id,
            ensure_product=ensure_product)
        external = {}
        external['ext_type_id'] = ext_type_id
        external['ext_bz_bug_id'] = external_bug_id
        if description is not None:
            external['ext_description'] = description
        elif orig_external:
            external['ext_description'] = orig_external['ext_description']
        if status is not None:
            external['ext_status'] = status
        elif orig_external:
            external['ext_status'] = orig_external['ext_status']
        if branch is not None:
            external['ext_priority'] = branch
        elif orig_external:
            external['ext_priority'] = orig_external['ext_priority']
        if not orig_external:
            self.ExternalBugs.add_external_bug(self.wrap({
                'bug_ids': [bug_id],
                'external_bugs': [external],
            }))
        else:
            self.ExternalBugs.update_external_bug(self.wrap(external))


def get_bug_ids(commit):
    """
    Get the bug ids that were specified in the commit message

    :param commit: Commit to get the message from
    """
    bug_regexp = re.compile(
        r'''
        ^Bug-Url:\ https?://bugzilla\.redhat\.com/ ## base url
            (show_bug\.cgi\?id=)? ## optional cgi
            (?P<bug_id>\d+) ## bug id itself
        $''',
        re.VERBOSE
    )
    revert_regexp = re.compile(
        '^This reverts commit (?P<commit>[[:alnum:]]+)$')
    repo = Repo(os.environ['GIT_DIR'])
    bugs = []
    message = repo[commit].message
    for line in message.splitlines():
        rev_match = revert_regexp.search(line)
        if rev_match and rev_match.groupsdict()['commit'] != commit:
            return get_bug_ids(rev_match.groupsdict()['commit'])
        match = bug_regexp.search(line)
        if match:
            bugs.append(match.groupdict()['bug_id'])
    return bugs


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bz-user', required=False, default=None,
                        help='User to use when logging into bugzilla')
    parser.add_argument('--bz-pass', required=False, default=None,
                        help='Password to use when logging into bugzilla')
    parser.add_argument('action', help='Action to execute')
    parser.add_argument('params', action='append', nargs='*',
                        help='Arguments to be passed to the method')
    args = parser.parse_args()
    real_params = {}
    for param in args.params[0]:
        if '=' in param:
            name, value = param.split('=', 1)
        else:
            name = None
            value = param
        try:
            value = json.loads(value)
        except ValueError:
            pass
        if name is not None:
            real_params[name] = value
        else:
            real_params.update(value)
    server = Bugzilla(args.bz_user, args.bz_pass)
    call_obj = server.rpc
    obj_path = args.action.split('.')
    while obj_path:
        call_obj = getattr(call_obj, obj_path.pop(0))
    try:
        res = call_obj(server.wrap(real_params))
    except xmlrpclib.Fault as fault:
        if fault.faultCode == 300:
            print "LOGIN ERROR:%s" % fault
            sys.exit(2)
        else:
            print "ERROR:%s" % fault
            sys.exit(1)
    print json.dumps(res, indent=4, default=str)
