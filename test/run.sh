#!/bin/bash

while getopts :m:r: flag;
do
    case "${flag}" in
        m)
            message=${OPTARG}
        ;;
        r)
            script_to_run=${OPTARG}
        ;;
        ::)
            echo "-${OPTARG} requires an argument."
            exit_failure
        ;;
        *)
            exit_failure
        ;;
    esac
done

parse_tags() {
    pattern="{(\w+)([,\w]*)}"
    echo $(echo $message | grep -oP $pattern | sed 's/^.//;s/.$//')
}

parse_modules() {
    pattern="\[(\w+)([,\w]*)\]"
    echo $(echo $message | grep -oP $pattern | sed 's/^.//;s/.$//')
}

run_odoo_test(){
    tags=$(parse_tags)
    modules=$(parse_modules)
    database=odoo

    source /mnt/test/run_odoo_tests.sh -t ${tags} -m ${modules} -d ${database}
}

run_pytest(){
    modules=$(parse_modules)
    database=odoo

    source /mnt/test/run_pytest.sh -m ${modules} -d ${database}
}

run_coverage(){
    tags=$(parse_tags)
    modules=$(parse_modules)
    database=odoo

    source /mnt/test/run_coverage.sh -t ${tags} -m ${modules} -d ${database}
}

usage() {
    echo "USAGE: $0
    [ -m MESSAGE message with the tags and modules needed to run the scripts]
    [ -r RUN SCRIPT select which script you want to run]
    [ -d DATABASE_NAME ]"
}

exit_failure() {
    usage
    exit 1
}

main() { 
    case "$script_to_run" in
        odoo)
            run_odoo_test
        ;;
        pytest)
            run_pytest
        ;;
        coverage)
            run_coverage
        ;;
        *)
            echo "No ${script_to_run} were found to execute"
        ;;
    esac

}

main