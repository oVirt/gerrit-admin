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


## log to stderr
tools.log()
{
    echo "$@" >&2
}


## print a review message with the format expeted by the hook dispatcher
tools.review()
{
    local cr="${1}"
    local ver="${2}"
    local msg="${3}"
    echo "$cr"
    echo "$ver"
    echo -e "$msg"
}


######
# Usage:
#   tools.match base_string match_string [match_string [...]]
#
#     base_string
#       String to check for a match
#
#     match_string
#       Tuple in the form '[!]regexp'
#
#       [!]regexp
#           regular expresion to match the base string against, if preceded
#            with '!' the expression will be negated
#
# Example:
#
#   tools.match 3.2.1 'master|3\.3.*' 'master|!3\.[21].*'
#
#   That will check that the string 3.2.1 matches:
#       3\.3.*
#   And does not match:
#       3\.3\.0\..*
#
# Return TOOLS.MATCHES|0 if the base_string matches all of the match_string
# passed, TOOLS.DOES_NOT_MATCH if it does not match because of a positive
# match and TOOLS.SHOULD_NOT_MATCH if it was because of a negative match
# (started with !)
TOOLS_MATCHES=0
TOOLS_DOES_NOT_MATCH=1
TOOLS_SHOULD_NOT_MATCH=2

tools.match()
{
    local base_string="${1?}"
    local match_strings=("${@:2}")
    for regexp in "${match_strings[@]}"; do
        if [[ "${regexp:0:1}" == '!' ]]; then
            ## Negate the regexp
            regexp="${regexp:1}"
            if [[ "$base_string" =~ $regexp ]]; then
                return $TOOLS_SHOULD_NOT_MATCH
            fi
        else
            if ! [[ "$base_string" =~ $regexp ]]; then
                return $TOOLS_DOES_NOT_MATCH
            fi
        fi
    done
    return $TOOLS_MATCHES
}
