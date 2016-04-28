#!/usr/bin/env bash
## @file conf.sh
## Helper configuration functions
## @code
## Configuration types
## ---------------------
##
## There are two types of configurations taken into account, static and
## temporary
##
##
## Static configuration
## ++++++++++++++++++++++
##
## Static configurations store those values that will persist after each
## execution of the hooks, for example users and passwords.
##
##
## Temporary configurations
## ++++++++++++++++++++++++++
##
## Some hooks use temporary configurations to store values for other hooks to
## recover, for example, when storing cookies.
##
## Configuration hierarchy
## ++++++++++++++++++++++++
##
## It will source the configuration files in order, skipping any non-existing
## ones. The paths where it will look for them are, in source order (the most
## prioritary first)::
##
## * $hook_path/$event_type.$chain.conf
## * $hook_path/$event_type.conf
## * $hook_path/$chain.conf
## * $hook_path/conf
## * $GERRIT_SITE/hooks/conf
## * $HOME/hook/conf
## * $hook_path/../../../hooks/conf
##
## When running in gerrit, the $hook_path is usually the git repository of the
## project the event was triggered for, for example::
##
##    /home/gerrit2/review_site/git/ovirt-engine.git
##
## @endcode


## @fn conf._get_conf_files()
## @brief Print all the available configuration files from less relevant to
## more relevant
conf._get_conf_files(){
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


## @fn conf._get_conf_file()
## @brief Print current's hook config file
conf._get_conf_file(){
    fname="${0##*/}"
    fpath="${0%/*}"
    local htype="${fname%%.*}"
    local chain="${fname#*.}"
    chain="${chain%%.*}"
    echo "${fpath}/${htype}.${chain}."
}


######
## @fn conf.get()
## @brief Prints the given key from the config
## @param name Name of the key to get the value for
## @param default Default value if not found
##
## @code
##  Options:
##
##  -c conf_file
##    Use that config file
## @endcode
##
## @note the return code is 1 when the value is not found in the config files,
## and if specified outputs the default value too
conf.get(){
    local OPTIND value name default conf_file
    while getopts c: option; do
        case $option in
            c) conf_file="$OPTARG";;
        esac
    done
    declare default="$2"
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
    declare name="$1"
    declare default="$2"
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
## @fn conf.put()
## @param name Key to store the conf value under
## @param value Value to store
## @brief Writes the given name/value to the configuration
##
## @code
##  Options:
##
##  -c conf_file
##    Use that config file
## @endcode
conf.put(){
    local OPTIND=0
    local conf_file="${0%.*.*}.config"
    while getopts c: option; do
        case $option in
            c) conf_file="$OPTARG";;
        esac
    done
    shift $((OPTIND-1))
    declare name="${1?No name passed}"
    declare val="${2?No value passed}"
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
## @fn conf.load()
## @brief Loads the config files from less specific to most so the latest
## prevails, all the conf entries are loaded as vars
##
## @code
##  Options:
##
##  -c conf_file
##    Use that config file
## @endcode
conf.load(){
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
## Temporary config file functions, for the current executione
##############################################################
######
## @fn conf.t_put()
## @param key Key to store
## @param value Value to store
## @brief Store the given key/value to temporary storage
conf.t_put(){
    local conf_file="${0%.*.*}.config.$PPID"
    [[ "$0" == "/bin/bash" ]] && conf_file="/tmp/temp.config.$PPID"
    conf.put -c "$conf_file" "$@"
}


## @fn conf.t_get()
## @param key Key to store
## @param default Default value to print if not found
## @brief Print the given key from temporary storage
conf.t_get(){
    local conf_file="${0%.*.*}.config.$PPID"
    [[ "$0" == "/bin/bash" ]] && conf_file="/tmp/temp.config.$PPID"
    conf.get -c "$conf_file" "$@"
}


## @fn conf.t_load()
## @brief load the temporary config
conf.t_load(){
    local conf_file="${0%.*.*}.config.$PPID"
    [[ "$0" == "/bin/bash" ]] && conf_file="/tmp/temp.config.$PPID"
    conf.load -c "$conf_file"
}


## @fn conf.t_clean()
## @brief Cleanup the temporary config related temporary files
conf.t_clean(){
    local conf_file="${0%.*.*}.config.$PPID"
    [[ "$0" == "/bin/bash" ]] && conf_file="/tmp/temp.config.$PPID"
    [[ -f "$conf_file" ]] && rm -f $conf_file
}
