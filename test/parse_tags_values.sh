#!/bin/bash

parse_tags_values() {
    pattern="{(\w+)([,\w]*)}$"
    echo $(echo $message | grep -oP $pattern | sed 's/^.//;s/.$//')
}

while getopts :m: flag;
do
    case "${flag}" in
        m)
            message=${OPTARG}
            parse_tags_values
        ;;
    esac
done


