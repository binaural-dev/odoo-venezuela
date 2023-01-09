#!/bin/bash

while getopts :m:d: flag
do
    case "${flag}" in
        m) modules=${OPTARG};;
        d) database=${OPTARG};;
        ::)
            echo "-${OPTARG} requires an argument."
            exit_failure
        ;;
        *)
            exit_failure
        ;;
    esac
done

initialize_database() {
    echo "Initializing Odoo database..."
    odoo --stop-after-init -d ${database} -i ${modules}
}

run_pytest() {
    containerenv=/opt/odoo-venv
    here=$(dirname $0)
    modules_dir_to_test=$(split_modules $modules)
    echo $modules_dir_to_test
    echo "Running Tests..."
    $containerenv/bin/pytest --odoo-database=${database} --color=yes --ignore=$here/data $modules_dir_to_test
}

split_modules() {
    modules=$(echo $1 | tr "," "\n")
    new_modules=""

    for module in $modules
    do
        new_modules+="/mnt/integra-addons/$module "
    done

    echo $new_modules
}

usage() {
    echo "USAGE: $0
    [ -m MODULES (comma separated arg1,arg2, arg3)] [ -d DATABASE_NAME ]"
}

exit_failure() {
    usage
    exit 1
}

main () {
    initialize_database
    run_pytest
}

main