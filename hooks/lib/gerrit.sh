#!/bin/bash
## @file gerrit.sh
## Helpful functions to manage gerrit related actions
source conf.sh

## @fn gerrit.get_patch()
## @brief Print the bug info
## @note it is cached for faster access
## @param patch_id Patch id to retrieve info, as in 1234 (don't confuse with
## the change id)
gerrit.get_patch(){
    declare patch_id="${1?}"
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

## @fn gerrit.is_related()
## @brief Check if the patch has the Related-To tag
## @param commit Refspec to check
## @retval 0 if it did not have it
## @retval 1 otherwise
gerrit.is_related(){
    declare commit=${1:-HEAD}
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


## @fn gerrit.parse_params()
## @brief Parse all the parameters as env variables, leave the rest as
## positional args
## @code
##   gerrit.parse_params --param1 val1 param2 --param-3 val3
##       => [[ param1 == "val1" ]] \
##          && [[ param_3 == "val3" ]] \
##          && [[ "$1" == "param2" ]]
## @endcode
gerrit.parse_params(){
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


## @fn gerrit.review()
## @brief Write a review, it will use the env commit and project vars, as set
## by parse_params
## @param result Value for the verified flag (1, 0, -1)
## @param message Message for the comment
## @param project Gerrit project that owns the commit
## @param commit Refspec for the commit of the patch to write a review for
gerrit.review(){
    declare result=${1?}
#    local message="$( echo "${2?}" | fold -w 80 -s )"
    declare message="${2?}"
    declare project=${3:-$project}
    declare commit=${4:-$commit}
    local footer="
 help:$HELP_URL"
    echo "Message:\n$message"
    ssh "${GERRIT_SRV?}" -p 29418 gerrit review \
        --verified="$result" \
        --message="\"$message${HELP_URL:+$footer}\"" \
        --project="${project?}" \
        "${commit?}"
}


## @fn gerrit.status()
## @brief Print the status of the given patch
## @param id Patch id to get the status for
gerrit.status(){
    local id=${1?}
    gerrit.get_patch "$id" \
    | grep -Po "(?<=^  status: )\w*"
}

## @fn gerrit.is_open()
## @brief Check if a patch is open
## @param id Patch id to check
## @retval 0 if the patch is open
## @retval 1 otherwise
gerrit.is_open(){
    local id=${1?}
    gerrit.get_patch "$id" \
    | grep -Pq "^  open: true"
}

## @fn gerrit.clean()
## @brief Clean up all the temporary files for the current run
## @param nothing No parameters needed
gerrit.clean(){
    rm -f /tmp/gerrit_cache.$PPID.*
}


## @fn gerrit.get_branches()
## @brief Print the list of branches for the current project
## @param pattern If passed, will filter out branches by that pattern
## (shell-like)
gerrit.get_branches(){
    declare pattern="${1}"
    pushd "${GIT_DIR?}" &>/dev/null
    declare branch
    while read branch; do
        branch="${branch#* }"
        branch="${branch#  }"
        echo "${branch}"
    done < <( git branch -a | grep -E ${pattern:+$pattern} )
    popd &>/dev/null
    return 0
}

