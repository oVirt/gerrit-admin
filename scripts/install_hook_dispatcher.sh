#!/bin/bash -e

hooks=(
    patchset-created
    change-merged
    change-abandoned
    comment-added
)

for hook in "${hooks[@]}"; do
    ln -s \
        /gerrit_testsite/hooks/hook-dispatcher \
        "/gerrit_testsite/hooks/$hook"
done
