#!/bin/bash

while getopts 'm:' flag;
do
    case "${flag}" in
        m)
            message = ${OPTARG}
            run_test_with_param
    esac
done

run_test_with_param(){
    echo ${message}
    if [ "$message" == *"{"* ] || [ "$message" == *"}"*]; then
        
    fi
}