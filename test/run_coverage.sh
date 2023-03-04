#!/bin/bash

while getopts :t:m:d: flag
do
    case "${flag}" in
        t) tags=${OPTARG};;
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

execute_coverage_run() {
    analyze_folder="/mnt/integra-addons"
    omit_files="*/__manifest__.py,*/__init__.py"
    echo "Starting Coverage Run..."
    if [ -z "${tags}" ]; then
        echo "Runing coverage without tags..."
        coverage run --source=${analyze_folder} --omit=${omit_files} /opt/odoo/odoo-bin --test-enable --stop-after-init --log-level=test -d ${database} -i ${modules} --without-demo=all 
    else
        echo "Runing coverage with tags..."
        coverage run --source=${analyze_folder} --omit=${omit_files} /opt/odoo/odoo-bin --test-tags=${tags} --stop-after-init --log-level=test -d ${database} -i ${modules} --without-demo=all
    fi
}

usage() {
    echo "USAGE: $0
    [ -m TAGS (comma separated tag1,tag2,tag3)]
    [ -m MODULES (comma separated module1,module2,module3)]
    [ -d DATABASE_NAME ]"
}

exit_failure() {
    usage
    exit 1
}

main() {
    execute_coverage_run
    coverage report -m
}

main