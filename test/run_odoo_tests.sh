#!/bin/bash

while getopts :c:t:m:d: flag
do
    case "${flag}" in
        c) container=${OPTARG};;
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
    if [ -z "${tags}" ] && [ -z "${modules}" ]; then
        echo "Running tests without tags and modules..."
        modules=$(list_directories)
        docker exec -it ${container} odoo --test-enable --test-tags=bin --stop-after-init --log-level=test --load-language=es_VE --without-demo=all -d ${database} -i ${modules}
    else
        echo "Running tests with tags and modules..."         
        docker exec -it ${container} odoo --test-tags=${tags} --stop-after-init --log-level=test --load-language=es_VE --without-demo=all -d ${database} -i ${modules}
    fi
}

# Función que devuelve una lista de carpetas separadas por comas, by chatGPT
list_directories() {
  directories=$(ls "/mnt/integra-addons" | grep -v "tools" | grep -v "l10n_binaural")
  IFS=","
  result=$(echo "$directories" | tr "\n" "," | sed 's/,$//')
  unset IFS
  echo "$result"
}

usage() {
    echo "USAGE: $0
    [ -c ODOO CONTAINER (docker container name)]
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
