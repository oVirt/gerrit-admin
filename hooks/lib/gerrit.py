#!/usr/bin/env python
#encoding: utf-8
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
        cmd =  list(self.cmd)
        cmd.append(action)
        cmd.extend(options)
        return cmd

    def review(self, commit, message, project, verify=None, review=None):
        gerrit_cmd = self.generate_cmd(
            'review',
            commit,
            '--message="%s"' % message,
            '--project=%s' % project,
        )
        if verify is not None:
            gerrit_cmd.append('--verify=%s' % str(verify))
        if review is not None:
            gerrit_cmd.append('--code-review=%s' % str(review))
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

    def query(self, query, out_format='json'):
        gerrit_cmd = self.generate_cmd(
            'query',
            '--format=%s' % out_format,
            query,
        )
        logger.debug("Executing %s" % ' '.join(gerrit_cmd))
        cmd = subprocess.Popen(gerrit_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
        out, err = cmd.communicate()
        if cmd.returncode:
            raise Exception("Execution of %s returned %d:\n%s"
                            % (' '.join(gerrit_cmd),
                                cmd.returncode,
                                err))
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
