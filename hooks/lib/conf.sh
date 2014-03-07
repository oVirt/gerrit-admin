#!/usr/bin/env bash
## Helper configuration functions
#
#
#######
# Configuration types
#######
#
# There are two types of configurations taken into account, static and
# temporary
#
#
#######
# Static configuration
#######
# 
# Static configurations store those values that will persist after each
# execution of the hooks, for example users and passwords.
#
#
#
#######
# Temporary configurations
#######
#
# Some hooks use temporary configurations to store values for other hooks to
# recover, for example, when storing cookies.
#


# Get all the available configuration files from less relevant to more relevant
conf._get_conf_files()
{
    fname="${0##*/}"
    fpath="${0%/*}"
    local htype="${fname%%.*}"
    local chain="${fname#*.}"
    chain="${chain%%.*}"
    for conf_file in "${fpath}/${htype}.${chain}." \
                     "${fpath}/${htype}." \
                     "${fpath}/${chain}." \
                     "${fpath}/" \
                     "${GERRIT_SITE:-${HOME:-${fpath}/../../..}}/hooks/"
    do
        [[ -f "${conf_file}config" ]] \
        && echo "${conf_file}config"
    done
}


conf._get_conf_file()
{
    fname="${0##*/}"
    fpath="${0%/*}"
    local htype="${fname%%.*}"
    local chain="${fname#*.}"
    chain="${chain%%.*}"
    echo "${fpath}/${htype}.${chain}."
}


######
# Usage:
#   conf.get [-c conf_file] name [default_value]
#
#  Retrieves the given value from the config
#
#  Options:
#
#  -c conf_file
#    Use that config file
#
#  Note: the return code is 1 when the value is not found in the config files,
#        and if specified outputs the default value too
#
conf.get()
{
    local OPTIND value name default conf_file
    while getopts c: option; do
        case $option in
            c) conf_file="$OPTARG";;
        esac
    done
    default="$2"
    if [[ "$conf_file" == "" ]]; then
        for conf_file in $(conf._get_conf_files); do
            if res="$(conf.get -c "$conf_file" "$@")"; then
                echo "$res"
                return
            fi
        done
        [[ -n "$default" ]] && echo "$default"
        return 1
    fi
    shift $((OPTIND-1))
    name="$1"
    default="$2"
    if [[ -f "$conf_file" ]] && [[ "$name" != "" ]]; then
        value="$(bash -c "source \"$conf_file\"; echo \"\$$name\"")"
        eval "value=\"$value\""
    fi
    if [[ -z "$value" ]]; then
        echo "$default"
        return 1
    else
        echo -e "$value"
    fi
}


######
# Usage:
#   conf.put [-c conf_file] name value
#
#  writes the given name/value to the configuration
#
#  Options:
#
#  -c conf_file
#    Use that config file
#
conf.put()
{
    local OPTIND=0
    local conf_file="${0%.*.*}.config"
    while getopts c: option; do
        case $option in
            c) conf_file="$OPTARG";;
        esac
    done
    shift $((OPTIND-1))
    name="${1?No name passed}"
    val="${2?No value passed}"
    if [[ -f "$conf_file" ]] && grep -Eq "^\s*$name=" "$conf_file"; then
        ## delete the old entry
        local entry="$(grep "$name=" "$conf_file")"
        if [[ "$entry" =~ $name=\".*\"$ ]]; then
            sed -i -e "/$name=/d" "$conf_file"
        else
            ## It's multiline
            sed -i -e "/$name=/,/.*\"/d" "$conf_file"
        fi
    fi
    # add the new entry
    echo "$name=\"$val\"" >> "$conf_file"
}


######
# Usage:
#   conf.load [-c conf_file]
#
#  Loads the config files from less specific to most so the latest prevails
#
#  Options:
#
#  -c conf_file
#    Use that config file
#
conf.load()
{
    local OPTIND conf_file i
    while getopts c: option; do
        case $option in
            c) conf_file="$OPTARG";;
        esac
    done
    shift $((OPTIND-1))
    ## if not specific conf passed, load from all
    if [[ "$conf_file" == "" ]]; then
        ## source the conf files from less specific to more
        ## so the later ones have the last word
        conf_files=($(conf._get_conf_files))
        for i in $(seq "${#conf_files[@]}"); do
            conf.load -c "${conf_files[$((${#conf_files[@]}-$i))]}"
        done
    else
        ## if not,source that file
        source "$conf_file"
    fi
}


#############################################################
### Temporary config file functions, for the current executione
##############################################################
######
# Usage:
#   conf.t_put name value
#
conf.t_put()
{
    local conf_file="${0%.*.*}.config.$PPID"
    [[ "$0" == "/bin/bash" ]] && conf_file="/tmp/temp.config.$PPID"
    conf.put -c "$conf_file" "$@"
}


# Usage:
#   conf.t_get name value default
#
conf.t_get()
{
    local conf_file="${0%.*.*}.config.$PPID"
    [[ "$0" == "/bin/bash" ]] && conf_file="/tmp/temp.config.$PPID"
    conf.get -c "$conf_file" "$@"
}


# Usage:
#   conf.t_load
#
conf.t_load()
{
    local conf_file="${0%.*.*}.config.$PPID"
    [[ "$0" == "/bin/bash" ]] && conf_file="/tmp/temp.config.$PPID"
    conf.load -c "$conf_file"
}


# Usage:
#   conf.t_clean
#
conf.t_clean()
{
    local conf_file="${0%.*.*}.config.$PPID"
    [[ "$0" == "/bin/bash" ]] && conf_file="/tmp/temp.config.$PPID"
    [[ -f "$conf_file" ]] && rm -f $conf_file
}
