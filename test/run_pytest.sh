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
    if [ -z "${modules}" ]; then
        modules=$(list_directories)
    fi   
    odoo --stop-after-init -d ${database} -i ${modules}
}

run_pytest() {
    containerenv=/opt/odoo-venv
    here=$(dirname $0)

    if [ -z "${modules}" ]; then
        modules=$(list_directories)
    fi

    modules_dir_to_test=$(split_modules $modules)
    echo $modules_dir_to_test
    echo "Running Tests..."
    $containerenv/bin/pytest --odoo-database=${database} --color=yes --ignore=$here/data $modules_dir_to_test
}

# Función que devuelve una lista de carpetas separadas por comas, by chatGPT
list_directories() {
  directories=$(ls "/mnt/integra-addons" | grep -v "tools" | grep -v "l10n_binaural")
  IFS=","
  result=$(echo "$directories" | tr "\n" "," | sed 's/,$//')
  unset IFS
  echo "$result"
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
    [ -m MODULES (comma separated arg1,arg2,arg3)] [ -d DATABASE_NAME ]"
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