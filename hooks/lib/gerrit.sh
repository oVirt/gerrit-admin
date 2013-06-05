#!/bin/bash
###########
## helpful functions to be used on the gerrit hook scripts
source conf.sh

## Get the bug info
## NOTE: it is cached for faster access
gerrit.get_patch()
{
    patch_id="${1?}"
    local patch_cache="$(conf.t_get gerrit_${patch_id})"
    if [[ "$patch_cache" != "" ]] && [[ -f "$patch_cache" ]]; then
        cat "$patch_cache"
    else
        patch_cache="/tmp/gerrit_cache.$PPID.${patch_id}"
        ssh "${GERRIT_SRV?}" -p 29418 \
            gerrit query --current-patch-set "$patch_id" \
        | tee "$patch_cache"
        conf.t_put "gerrit_${patch_id}" "$patch_cache"
    fi
}

## Check if the patch has the Related-To tag
gerrit.is_related()
{
    local commit=${1:-HEAD}
    local line
    local related_regexp='^[^#]*Related-To:(.*)$'
    pushd "${GIT_DIR?}" &>/dev/null
    while read line; do
        if [[ "$line"  =~ $related_regexp ]]; then
            popd &>/dev/null
            return 0
        fi
    done < <( git log "$commit^1..$commit" --format=%b )
    popd &>/dev/null
    return 1
}


## Parse all the aprameters as env variables:
## $0 --param1 val1 param2 --param-3 val3
##   => param1="val1" && param_3="val3" && [[ $1 == "param2" ]]
gerrit.parse_params()
{
    source tools.sh
    while [[ "$1" != "" && "$2" != "" ]]; do
        if [[ "${1:0:2}" != '--' ]]; then
            shift
            continue
        fi
        eval "$(tools.sanitize ${1:2})=\"${2//\"/\\\"}\""
        shift 2
    done
}


## Write a review, it will use the env commit and project vars, as set by
##  parse_params
gerrit.review()
{
    local result=${1?}
    local message="$( echo "${2?}" | fold -w 60 -s )"
    local project=${3:-$project}
    local commit=${4:-$commit}
    local footer="
 help:$HELP_URL"
    ssh "${GERRIT_SRV?}" -p 29418 gerrit review \
        --verified="$result" \
        --message="\"$message${HELP_URL:+$footer}\"" \
        --project="${project?}" \
        "${commit?}"
}


## Get the status of the given patch
gerrit.status()
{
    local id=${1?}
    gerrit.get_patch "$id" \
    | grep -Po "(?<=^  status: )\w*"
}

## Check if a patch is open
gerrit.is_open()
{
    local id=${1?}
    gerrit.get_patch "$id" \
    | grep -Pq "^  open: true"
}


## Clean up all temporary files for the current run
gerrit.clean()
{
    rm -f /tmp/gerrit_cache.$PPID.*
}
