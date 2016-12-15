#!/usr/bin/env python
# encoding: utf-8
import subprocess
import json
import logging

logger = logging.getLogger(__name__)


class Gerrit(object):
    def __init__(self, server):
        self.server = server
        self.cmd = (
            'ssh',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'StrictHostKeyChecking=no',
            self.server,
            '-p', '29418',
            'gerrit',
        )

    def generate_cmd(self, action, *options):
        cmd = list(self.cmd)
        cmd.append(action)
        cmd.extend(options)
        return cmd

    def review(self, commit, project, message, review=None, verify=None,
               ci=None):
        gerrit_cmd = self.generate_cmd(
            'review',
            commit,
            '--message="%s"' % message,
            '--project=%s' % project,
        )
        if verify is not None:
            gerrit_cmd.append('--verified=%s' % str(verify))
        if review is not None:
            gerrit_cmd.append('--code-review=%s' % str(review))
        if ci is not None:
            gerrit_cmd.append('--continuous-integration=%s' % str(ci))
        logging.info("Running gerrit_cmd:%s" % gerrit_cmd)
        cmd = subprocess.Popen(gerrit_cmd,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        out, err = cmd.communicate()
        if cmd.returncode:
            raise Exception("Execution of %s returned %d:\n%s"
                            % (' '.join(gerrit_cmd),
                               cmd.returncode,
                               err))
        return 0

    def query(
        self, query, all_approvals=False, all_reviewers=False,
        comment=False, commit_message=False, current_patch_set=False,
        dependencies=False, files=False, patch_sets=False, start=0,
        submit_records=False, out_format='json'
    ):
        cmd_params = [
            '--format=%s' % out_format,
            '--start=%d' % start,
        ]
        flags = [
            'all_approvals', 'all_reviewers', 'comment', 'commit_message',
            'current_patch_set', 'dependencies', 'files', 'patch_sets',
            'submit_records'
        ]
        for flag in flags:
            if vars().get(flag, False):
                cmd_params.append('--' + flag.replace('_', '-'))
        cmd_params.extend([
            '--',
            query
        ])
        gerrit_cmd = self.generate_cmd(
            'query',
            *cmd_params
        )
        logger.debug("Executing %s" % ' '.join(gerrit_cmd))
        cmd = subprocess.Popen(
            gerrit_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = cmd.communicate()
        if cmd.returncode:
            raise Exception(
                "Execution of %s returned %d:\n%s"
                % (
                    ' '.join(gerrit_cmd),
                    cmd.returncode,
                    err
                )
            )
        if out_format == 'json':
            res = []
            try:
                for line in out.splitlines():
                    res.append(json.loads(line))
            except ValueError:
                logger.error("Unable to decode json from:\n%s" % line)
                raise
        else:
            res = out
        return res

    def query_patchsets(self, *args, **kwargs):
        res = self.query(*args, **kwargs)
        if not res:
            raise Exception('Error trying to get patches:\n%s' % res)
        return res[0].get('patchSets', [])


class Change:
    @staticmethod
    def has_code_change(change):
        return change.get('kind', None) != 'NO_CODE_CHANGE'

    @staticmethod
    def get_ci_value(change, by_users=None):
        """
        Get the global patchset CI flag value, taking into account that +1 is
        more prioritary than -1

        :param change: dict with the change info as returned by Gerrit.query
        :param by_users: list of user names whose reviews will be taken into
            account to calculate the global value, if empty or None will not
            filter the reviewers
        """
        by_users = by_users or []
        ci_values = Change.get_flag_values(
            change=change,
            flag_name='Continuous-Integration',
            by_users=by_users,
        ).values()
        # calculate the sum of the values, +1 has priority
        cur_ci = 0
        for value in ci_values:
            if value < 0:
                cur_ci = value
            if value > 0:
                return value
        return cur_ci

    @staticmethod
    def get_ci_reviewers_name(change):
        return Change.get_reviewers_name(
            change=change,
            flag_name='Continuous-Integration',
        )

    @staticmethod
    def get_flag_values(change, flag_name, by_users=None):
        """
        :param change: dict with the change info as returned by Gerrit.query
        :param flag_name: Name of the flag to get the review values for
        :param by_users: List of users to filter the reviews by, if empty or
            not set will get them all
        """
        by_users = by_users or []
        approvals = change.get('approvals', [])
        # if any more recent change has ci flag by given users, take that
        return dict(
            (approval.get('by').get('name'), int(approval.get('value')))
            for approval in approvals
            if approval.get('type') == flag_name
            and (
                (by_users and approval.get('by').get('name') in by_users)
                or not by_users
            )
        )

    @staticmethod
    def get_reviewers_name(change, flag_name):
        approvals = change.get('approvals', [])
        return [
            approval.get('by').get('name')
            for approval in approvals
            if approval.get('type') == flag_name
        ]
