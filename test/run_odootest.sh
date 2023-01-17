#!/bin/bash

while getopts 'm:' flag;
do
    case "${flag}" in
        m)
            message=${OPTARG}
            run_test_with_param
    esac
done

run_test_with_param(){
    echo ${message}
    pattern='{(\w+)([,\w]*)}$'
    if [[ $message =~ $pattern ]]; then
        echo $(echo $message | grep -oP '{(\w+)([,\w]*)}$')
    else
        echo "Oops!"
        exit 1
    fi
}
