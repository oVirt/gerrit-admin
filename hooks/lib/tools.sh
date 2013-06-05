#!/bin/bash
###########
## helpful functions to be used on the gerrit hook scripts

## Check if a value is in the given list of elements
## Usage:
##    tools.is_in value elem1 [elem2 [...]]
tools.is_in()
{
    local what=$1
    local where i
    shift
    i=0
    for where in "$@"; do
        if [[ "$what" == "$where" ]]; then
            echo "$i"
            return 0
        fi
        i=$(($i + 1))
    done
    return 1
}


## Remove the leading and trailing white spaces
tools.trim(){
    local word
    shopt -q -s extglob
    for word in "$@"; do
        word="${word##+([[:space:]])}"
        word="${word%%+([[:space:]])}"
        echo "$word"
    done
    shopt -q -u extglob
}


## Replace all the bad characters from the given word to fit a bash variable
## name specification
tools.sanitize()
{
    local word
    for word in "$@"; do
        word="$( tools.trim "${word}" )"
        # if you do not make sure that extglob is disabled the patterns with
        # square brackets will not work...
        shopt -q -u extglob
        # some utf-8 chars are not valid in var names, but are included in
        # ranges, avoid using ranges
        word="${word//[^abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_]/_}"
        [[ $word =~ ^[0-9] ]] \
            && echo "Malformed $word, should not start with a digit." \
            && return 1
        echo "$word"
    done
}


## Get a simple md5 hash of the given string
tools.hash()
{
    local what="${1?}"
    local length="${2:-10}"
    echo "$what" | md5sum | head -c$length
}
