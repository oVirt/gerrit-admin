#!/bin/bash
## @file tools.sh
## Helpful miscellaneous functions

TOOLS_MATCHES=0
TOOLS_DOES_NOT_MATCH=1
TOOLS_SHOULD_NOT_MATCH=2


## @fn tools.is_in()
## @param value Value to look for
## @param elem1... Elements to look among
## @briefCheck if a value is in the given list of elements
tools.is_in(){
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


## @fn tools.trim()
## @brief Remove the leading and trailing white spaces
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


## @fn tools.sanitize()
## @param word... list of words to sanitize
## @brief Replace all the bad characters from the given word to fit a bash
## variable name specification
tools.sanitize(){
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


## @fn tools.hash()
## @param what Base string for the hash
## @param length Max length for the hash, (default=10)
## @brief Get a simple md5 hash of the given string
tools.hash(){
    local what="${1?}"
    local length="${2:-10}"
    echo "$what" | md5sum | head -c$length
}


## @fn tools.log()
## @brief logs the given strings to stderr
## @param message... list of messages to log
tools.log(){
    echo "$@" >&2
}


## @fn tools.review()
## @brief print a review message with the format expeted by the hook dispatcher
## @param cr Value for the Code Review flag
## @param ver Value for the Verified flag
## @param msg Message for the review comment
tools.review(){
    local cr="${1}"
    local ver="${2}"
    local msg="${3}"
    echo "$cr"
    echo "$ver"
    echo -e "$msg"
}


######
## @fn tools.match()
## @param base_string String to check for a match
## @param match_string Tuple in the form '[!]regexp'
## @code
##       [!]regexp
##           regular expresion to match the base string against, if preceded
##            with '!' the expression will be negated
##
## Example:
##
##   tools.match 3.2.1 'master|3\.3.*' 'master|!3\.[21].*'
##
##   That will check that the string 3.2.1 matches:
##       3\.3.*
##   And does not match:
##       3\.3\.0\..*
## @endcode
## @retval TOOLS_MATCHES|0 if the base_string matches all of the match_string
## passed
## @retval TOOLS_DOES_NOT_MATCH if it does not match because of a positive
## match
## @retval TOOLS_SHOULD_NOT_MATCH if it was because of a negative match
## (started with !)
tools.match(){
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
