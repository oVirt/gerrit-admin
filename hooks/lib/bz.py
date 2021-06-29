#!/usr/bin/env python
import xmlrpclib
import re
import logging
import argparse
import json
import sys


class WrongProduct(Exception):
    pass


class Bug(object):
    """
    Bug structure
    """

    def __init__(
        self, product, status, title, flags, target_rel, milestone,
        component, classification, external_bugs,
    ):

        self.product = product
        self.status = status
        self.title = title
        self.flags = flags
        self.target_rel = target_rel
        self.milestone = milestone
        self.component = component
        self.classification = classification
        self.external_bugs = external_bugs


class Bugzilla(object):
    """
    Bugzilla Object
    """

    def __init__(
        self, user=None, passwd=None,
        url='https://bugzilla.redhat.com/xmlrpc.cgi'
    ):
        self.rpc = xmlrpclib.ServerProxy(url)
        self.user = user
        self.passwd = passwd
        self.url = url

    def wrap(self, dictionary):
        if self.user:
            dictionary['Bugzilla_login'] = self.user
        if self.passwd:
            dictionary['Bugzilla_password'] = self.passwd
        if self.url:
            dictionary['Bugzilla_url'] = self.url
        return dictionary

    def __getattr__(self, what):
        return getattr(self.rpc, what)

    @staticmethod
    def extract_flags(list_of_dicts):
        """
        Get bugzilla bug flags

        :param list_of_dicts: list of dict flags
        :return dict of flag names (key) and flag statuses (value)
        """
        flag_dict = {}
        for entry in list_of_dicts:
            flag_dict[entry['name']] = entry['status']

        return flag_dict

    def extract_bug_info(self, bug_id):
        """
        Extract parameters from bz ticket

        :param bug_id: bug number
        :return bug object: bug object that will hold all the bug data info
        """
        try:
            bug = self.rpc.Bug.get(
                self.wrap({
                    'ids': bug_id, 'extra_fields': ['flags', 'external_bugs'],
                })
            )
        except (xmlrpclib.Fault, xmlrpclib.ProtocolError) as err:
            logging.error("Failed to retrieve bug {0}:\n{1}".format(
                bug_id, err
            ))
            return None

        product = bug['bugs'][0]['product']
        title = bug['bugs'][0]['summary']
        status = bug['bugs'][0]['status']
        flags = self.extract_flags(bug['bugs'][0]['flags'])
        target_rel = bug['bugs'][0]['target_release']
        milestone = bug['bugs'][0]['target_milestone']
        classification = bug['bugs'][0]['classification']
        component = bug['bugs'][0]['component']
        external_bugs = bug['bugs'][0]['external_bugs']

        bug_data = Bug(
            product=product, status=status, component=component,
            title=title, flags=flags, milestone=milestone,
            classification=classification, target_rel=target_rel,
            external_bugs=external_bugs,
        )
        return bug_data

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
            logging.error("Unable to get bug {0}\n{1}".format(
                str(bug_id), bug['faults']
            ))
            return None
        # Only one response when asking by the commit hash
        bug = bug['bugs'][0]
        # check product
        if ensure_product is not None and bug['product'] != ensure_product:
            raise WrongProduct(bug['product'])
        for external in bug['external_bugs']:
            if external.get('ext_bz_bug_id') == str(external_bug_id):
                return external
        return None

    def update_external(self, bug_id, external_bug_id, ext_type_id,
                        status=None, description=None, branch=None,
                        ensure_product=None):
        orig_external = self.get_external(
            bug_id,
            external_bug_id,
            ensure_product=ensure_product)
        external = dict()
        external['ext_type_id'] = ext_type_id
        external['ext_bz_bug_id'] = external_bug_id

        if description:
            external['ext_description'] = description

        if status:
            external['ext_status'] = status

        if branch:
            external['ext_priority'] = branch

        # if we don't have external bug tracker, add a new one or else update
        # the exist one
        if not orig_external:
            self.ExternalBugs.add_external_bug(self.wrap({
                'bug_ids': [bug_id],
                'external_bugs': [external],
            }))
        else:
            if description is None:
                external['ext_description'] = orig_external['ext_description']

            if status is None:
                external['ext_status'] = orig_external['ext_status']

            if branch is None:
                external['ext_priority'] = orig_external['ext_priority']

            self.ExternalBugs.update_external_bug(self.wrap(external))

    @staticmethod
    def get_bug_urls(commit, bz_server="https://bugzilla.redhat.com"):
        """
        Get bug url\s from the passed commit

        :param commit: commit message string
        :param bz_server: bugzilla server
        :return: list of bug urls or empty list
        """

        regex_search = r'^Bug-Url:[\s]*(https*:\/\/' + \
            bz_server.split("//")[-1] + r'\/.*\d+\b)'

        return re.findall(regex_search, commit, flags=re.IGNORECASE | re.MULTILINE)


    @staticmethod
    def get_bug_ids(bug_urls):
        """
        Get bug id from bug url

        :param bug_urls: list of bug urls
        :return: set of unique bug ids
        """
        regex_bug_id = r'\d+\b'
        bug_ids = set()

        # get bug_id from bug_url
        for url in bug_urls:
            bug_ids.add(re.findall(regex_bug_id, url)[0])

        return bug_ids


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
