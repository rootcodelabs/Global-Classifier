#!/bin/bash

# Function to parse ini file and extract the value for a given key under a given section
get_ini_value() {
    local file=$1
    local key=$2
    awk -F '=' -v key="$key" '$1 == key { gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2; exit }' "$file"
}

# Get the values from dsl_config.ini
INI_FILE="constants.ini"
DB_PASSWORD=$(get_ini_value "$INI_FILE" "DB_PASSWORD")


docker run --rm --network bykstack -v `pwd`/DSL/Liquibase/changelog:/liquibase/changelog -v `pwd`/DSL/Liquibase/master.yml:/liquibase/master.yml -v `pwd`/DSL/Liquibase/data:/liquibase/data liquibase/liquibase --defaultsFile=/liquibase/changelog/liquibase.properties --changelog-file=master.yml --url=jdbc:postgresql://users_db:5432/classifier?user=postgres --password=$DB_PASSWORD update