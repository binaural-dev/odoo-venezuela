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

execute_odoo_tests() {
    echo "Starting Odoo tests..."
    # if [ -z "${tags}" ]; then
    #     echo "Running tests without tags..."
    #     odoo --test-enable --stop-after-init --log-level=test -d ${database} -i ${modules}
    # else
    #     echo "Running tests with tags..." 
    #     echo ${modules}
    #     odoo --test-tags=${tags} --stop-after-init --log-level=test -d ${database} -i ${modules}
    # fi
    if [ -z "${tags}" ] && [ -z "${modules}" ]; then
        echo "Running tests without tags and modules..."
        odoo --test-enable --stop-after-init --log-level=test -d ${database}
    elif [ -z "${tags}" ]; then
        echo "Running tests without tags..."
        odoo --test-enable --stop-after-init --log-level=test -d ${database} -i ${modules}
    elif [ -z "${modules}" ]; then
        echo "Running tests without modules..."
        odoo --test-tags=${tags} --stop-after-init --log-level=test -d ${database}
    else
        echo "Running tests with tags and modules..." 
        echo ${modules}
        odoo --test-tags=${tags} --stop-after-init --log-level=test -d ${database} -i ${modules}
    fi
}

usage() {
    echo "USAGE: $0
    [ -t TAGS (comma separated tag1,tag2,tag3)]
    [ -m MODULES (comma separated module1,module2,module3)]
    [ -d DATABASE_NAME ]"
}

exit_failure() {
    usage
    exit 1
}

main() {
    execute_odoo_tests
}

main