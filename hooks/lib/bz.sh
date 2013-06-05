#!/bin/bash -x
###########
## helpful functions to be used on the gerrit hook scripts
source conf.sh
source tools.sh


#####
# Usage:
#   bz.get_bug [-p] bug_id
#
#  Get's the bug_id bug xml information from cache, or if not cached, from the
#  server.
#
#  -p  Get it in plain text
#
bz.get_bug()
{
    local OPTIND
    local options="&ctype=xml"
    local btype="xml"
    local clean_after='false'
    while getopts "p" option; do
        case $option in
            p)
                options=""
                btype='plain'
                ;;
        esac
    done
    shift $((OPTIND-1))
    local bug_id="${1?No bug id issued}"
    local bug_cache="$(conf.t_get bz_${bug_id}_${btype})"
    if [[ "$bug_cache" != "" ]] && [[ -f "$bug_cache" ]]; then
        cat "$bug_cache"
    else
        local cookie_jar="$(conf.t_get bz_cookie_jar)"
        [[ -f ${cookie_jar?You have to login to bugzilla first, see bz.login} ]]
        bug_cache="/tmp/bz_cache.$PPID.${bug_id}.${btype}"
        wget -qO - \
            --load-cookies "$cookie_jar" \
            --save-cookies "$cookie_jar" \
            "https://bugzilla.redhat.com/show_bug.cgi?id=${bug_id}${options}" \
        | tee "$bug_cache"
        conf.t_put "bz_${bug_id}_${btype}" "$bug_cache"
    fi
}


######
# Usage:
#   bz.update_bug bug_id [data1 [data2 [...]]]
#
#  Updates the given bug, returns 0 if updated, 1 otherwise
#
#    data
#      Each of the post arameters to send (usually as name=value).
#
bz.update_bug()
{
    local bug_id="${1?No bug id passed}"
    local param post_data rc bug_cache
    local cookie_jar="$(conf.t_get bz_cookie_jar)"
    [[ -f ${cookie_jar?You have to login to bugzilla first, see bz.login} ]]
    shift
    ## We also need the token and confirm_public_bug to avoid confirmation
    ## page
    for param in "token=$(bz.get_token $bug_id)" "confirm_public_bug=1" "$@"
    do
        post_data="${post_data:+$post_data&}$param"
    done
    wget -qO - \
        --load-cookies "$cookie_jar" \
        --save-cookies "$cookie_jar" \
        --header "Referer: https://bugzilla.redhat.com/show_bug.cgi?id=$bug_id" \
        --post-data "$post_data" \
        "https://bugzilla.redhat.com/process_bug.cgi?id=$bug_id" \
    | tee /tmp/update_bug_log.${bug_id} 2>/dev/null\
    | grep -q "Changes submitted for"
    rc=$?
    if [[ $rc -eq 0 ]]; then
        rm -f "/tmp/update_bug_log.${bug_id}"
    else
        echo "Error while updating bug #${bug_id} with post_data, response data"\
             "at /tmp/update_bug_log.${bug_id}"
        echo "Sent data: $post_data"
    fi
    ## clean the old bug data from all caches, if any
    rm -f /tmp/bz_cache.*.${bug_id}.*
    return $rc
}


######
# Usage:
#   bz.is_revert [commit]
#
#   Return 0 if the given commit is a revert, 1 otherwise
#
bz.is_revert()
{
    local commit=${1:-HEAD}
    local line found
    local revert_regexp='^This reverts commit ([[:alnum:]]+)$'
    pushd "${GIT_DIR?}" &>/dev/null
    while read line; do
        if [[ "$line" =~ $revert_regexp ]]; then
            found='true'
        fi
    done < <( git show "$commit" --quiet --format=%b )
    popd &>/dev/null
    [[ "$found" == "true" ]]
}



######
# Usage:
#   bz.get_bug_id [commit]
#
#  Extracts the bug ids from the Bug-Url in the given commit
#  NOTE: If the patch is a 'revert', it extracts the bug from the reverted
#        commit
#
bz.get_bug_id()
{
    local commit=${1:-HEAD}
    local line found
    local bug_regexp1='^Bug-Url: (https?://bugzilla\.redhat\.com/)show_bug\.cgi\?id=([[:digit:]]+)$'
    local bug_regexp2='^Bug-Url: (https?://bugzilla\.redhat\.com/)([[:digit:]]+)$'
    local revert_regexp='^This reverts commit ([[:alnum:]]+)$'
    pushd "${GIT_DIR?}" &>/dev/null
    while read line; do
        if [[ "$line" =~ $revert_regexp ]]; then
            commit_id="${BASH_REMATCH[1]}"
            bz.get_bug_id "$commit_id"
            return $?
        fi
        if [[ "$line"  =~ $bug_regexp1 || "$line"  =~ $bug_regexp2 ]]; then
            echo "${BASH_REMATCH[2]}"
            found='true'
        fi
    done < <( git show --quiet "$commit" --format=%b )
    popd &>/dev/null
    [[ "$found" == "true" ]]
}


######
# Usage:
#   bz.login [-s server_url] [-b bug_id] user password
#
#   Logs into bugzilla if not logged in already.
#
#   -b bug_id
#     If you pass a bug_id, the token for that bug will already be set and
#     cached for further reference
#
#   -s server_url
#     Use that url instead of the one in the config file
#     (https://bugzilla.redhat.com by default)
#
# Configuration parameters:
#    bugzilla_server
#      full url to the bugzilla server
#
bz.login()
{
    local server_url="$(conf.get 'bugzilla_server' 'https://bugzilla.redhat.com')"
    local OPTIND bug_id plain_bug
    while getopts "s:b:" option; do
        case $option in
            s) server_url="$OPTARG";;
            i)
                bug_id="$OPTARG"
                plain_bug="/tmp/bz_cache.$PPID.${bug_id}.plain"
                conf.t_put "bz_${bug_id}_plain" "$plain_bug"
                ;;
        esac
    done
    server_url="${server_url}${bug_id:+/show_bug.cgi?id=${bug_id}}"
    shift $((OPTIND - 1))
    local cookie_jar="$(conf.t_get bz_cookie_jar)"
    if ! [[ -f "$cookie_jar" ]] ; then
        local bz_user="${1?No user passed}"
        local bz_password="${2?No password passed}"
        [[ "$cookie_jar" == "" ]] \
        && cookie_jar="/tmp/bz_cache.$PPID.cookies"
        conf.t_put "bz_cookie_jar" "$cookie_jar"
        wget -qO ${plain_bug:-/dev/null} --save-cookies "$cookie_jar" \
            --post-data "Bugzilla_login=${bz_user//@/%40}&Bugzilla_password=${bz_password}&GoAheadAndLogIn=Log+in" \
            "$server_url"
    fi
}


######
# Usage:
#   bz.get_bug_flags bug_id
#
# Retrieves all the '+' flags of the given bug
#
bz.get_bug_flags()
{
    local bugid=${1?}
    local line fname
    local status_regexp='status=\"\+\"'
    local flag_regexp='.*\<flag\ name=\"([^\"].*)\"'
    while read line; do
        if [[ "$line" =~ $flag_regexp ]]; then
            fname="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ $status_regexp ]]; then
            echo "$fname"
        fi
    done < <( bz.get_bug "$bugid" | grep -aPzo "(?s)^( *)[^#\n]*<flag[^>]*>" )
}


######
# Usage:
#   bz.get_bug_status bug_id
#
# Retrieves the current status of the bug
#
bz.get_bug_status()
{
    local bugid=${1?}
    bz.get_bug "$bugid" \
    | grep -aPzo "(?<=<bug_status>)[^<]*"
}


######
# Usage:
#   bz.check_flags bug_id [flagspec1 [flagspec2 [...]]]
#
# Checks that all the flags exist with '+' in the given bug
#
#     flagspec
#       can be a single flag or a sequence ot flags separated by '|' to
#       express that those flags are interchangeable
#
#  Ex: bz.check_flags 12345 flag1 flag2|flag2_bis flag3
#
bz.check_flags()
{
    local bug_id="${1?No bug id passed}"
    shift
    local flags missing_flags and_flag found or_flag
    ## Check the flags
    flags=($(bz.get_bug_flags $bug_id))
    missing_flags=""
    ## Flags are defined like this: flag1|flag2 flag3
    ## That means fag1 or flag2 are required and flag3 is required
    ## ' ' -> and, '|' -> or
    for and_flag in "$@"; do
        found=0
        for or_flag in ${and_flag//|/ }; do
            if tools.is_in "$or_flag" "${flags[@]}" >/dev/null; then
                found=1
            fi
        done
        if [[ $found -eq 0 ]]; then
            missing_flags="${missing_flags:+$missing_flags, }$and_flag"
        fi
    done
    if [[ "$missing_flags" != "" ]]; then
        echo -e "No ${missing_flags} flag/s"
        return 1
    fi
    echo -e "OK"
    return 0
}


######
# Usage:
#   bz.get_token bug_id
#
# Gets the session token to be able to do submits (update a bug)
#
bz.get_token()
{
    bug_id=${1?No bug id passed}
    bz.get_bug -p "$bug_id" \
    | grep -Po "(?<=<input type=\"hidden\" name=\"token\" value=\")[^\"]*"
}


######
# Usage:
#   bz.add_tracker bug_id tracker_id external_id
#
#     tracker_id
#       This is the internal tracker id that bugzilla assigns to
#       each external tracker (RHEV gerrit -> 82, oVirt gerrit -> 81)
#
#     external_id
#       Id for the bug in the external tracker
#
# Add a new external bug to the external bugs list
bz.add_tracker()
{
    bug_id="${1?}"
    tracker_id="${2?}"
    external_id="${3?}"
    bz.update_bug "$bug_id" \
        "external_bug_id=${external_id}" \
        "external_id=${tracker_id}"
}

## Update fixed in version field
bz.update_fixed_in_version()
{
    bug_id="${1?}"
    fixed_in_version="${2?}"
    bz.update_bug "$bug_id" "cf_fixed_in=${fixed_in_version}"
}


## Update fixed in version field
bz.update_status_and_version()
{
    bug_id="${1?}"
    bug_status="${2?}"
    fixed_in_version="${3?}"
    bz.update_bug "$bug_id" \
        "bug_status=${bug_status}" \
        "cf_fixed_in=${fixed_in_version}"
}

######
# Usage:
#  bz.update_status bug_id new_status
#
#    bug_id
#      Id of the bug to update
#
#    new_status
#      New status to set the bug to, only the allowed transitions will end in
#      a positive result (return code 0)
#
#
#  Legal status transitions:
#    ASSIGNED -> POST
#    POST -> MODIFIED
#
#  If it's a revert any source status is allowed
#
bz.update_status()
{
    bug_id="${1?}"
    new_status="${2?}"
    commit_id="${3?}"
    current_status="$(bz.get_bug_status "$bug_id")"
    if [[ "$current_status" == "$new_status" ]]; then
        echo "already on $new_status"
        return 0
    fi
    if ! bz.is_revert "$commit_id"; then
        case $current_status in
            ASSIGNED)
                if [[ "$new_status" != "POST" ]]; then
                    echo "ilegal change from $current_status"
                    return 1
                fi
                ;;
            POST)
                if [[ "$new_status" != "MODIFIED" ]]; then
                    echo "ilegal change from $current_status"
                    return 1
                fi
                ;;
            *)
                echo "ilegal change from $current_status"
                return 1
        esac
    fi
    bz.update_bug "$bug_id" "bug_status=${new_status}"
}


######
# Usage:
#  bz.get_external_bugs bug_id [external_name]
#
#    bug_id
#      Id of the parent bug
#
#    external_name
#      External string to get the bugs from. If none given it will get all the
#      external bugs.
#      Usually one of:
#        - "oVirt gerrit"
#        - "RHEV gerrit"
#
bz.get_external_bugs()
{
    bug_id="${1?}"
    external_name="${2:-[^.*]}"
    bz.get_bug "$bug_id" \
    | grep -Po "(?<=<external_bugs name=\"$external_name\">)\d*"
}


######
# Usage:
#   bz.clean
#
#  Cleans up all the cached config and data. Make sure that your last scripts
#  calls it before exitting
bz.clean()
{
    rm -f /tmp/bz_cache.$PPID.*
    conf.t_clean
}


######
# Usage:
#   bz.get_product bug_id
#
#  Return the product name of the given bug
bz.get_product()
{
    bug_id="${1?}"
    bz.get_bug "$bug_id" \
    | grep -Po "(?<=<product>)[^<]*"
}



######
# Usage:
#   bz.is_private_id
#
#  return 0 if it's private, 1 otherwise
bz.is_private()
{
    bug_id="${1?}"
    bz.get_bug "$bug_id" \
    | grep -q '<group id="218">private</group>'
}
